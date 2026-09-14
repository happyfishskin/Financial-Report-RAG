#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
比率計算之外部效度對照：Pipeline C（Gemini 算術）
====================================================
`benchmark_ratio_pipelines.py` 已比較 Pipeline A（Qwen3-4B-AWQ 算術）與
Pipeline B（Python 確定性代數），結論是「可由程式完成的算術不交由 LLM」。

**但該結論的實驗基礎只有一個 4B 量化模型**。委員可合理質疑：換前沿模型是否
仍然如此？本腳本補上 Pipeline C，把同一批題目的算術交給 gemini-2.5-flash。

**控制變因**：分子與分母**完全沿用** A/B 兩管線用的 `numerator_raw` /
`denominator_raw`（皆由 `_direct_lookup_flex` 抽出），system prompt 與
user prompt 逐字沿用 `_RATIO_LLM_SYSTEM`，判分函式亦相同。
唯一變動的是「誰做除法」——這才能乾淨地隔離模型能力，
而不與檢索品質或提示詞設計混在一起。

金標由分子／分母直接算得，不經任何 LLM，可視為 100% 正確。

    python3 benchmark_ratio_gemini.py [--limit N]
      → results/benchmark_ratio_gemini.json
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))

import benchmark_ratio_pipelines as A   # noqa: E402  沿用其 prompt 與解析函式

OUT = BASE / "results" / "benchmark_ratio_gemini.json"
CKPT = BASE / "results" / "_ratio_gemini_checkpoint.json"
QUESTIONS = BASE / "questions" / "ratio_questions_50.json"
MODEL = "gemini-2.5-flash"
ENDPOINT = ("https://generativelanguage.googleapis.com/v1beta/models/"
            "{model}:generateContent")
TOLERANCE_PP = getattr(A, "TOLERANCE_PP", 0.05)


def _api_key() -> str:
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        for line in (BASE / ".env").read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("GEMINI_API_KEY"):
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
    if not key:
        sys.exit("[ERROR] 找不到 GEMINI_API_KEY（環境變數或 .env）")
    return key


def compute_ratio_gemini(num_raw: str, den_raw: str, key: str,
                         model: str = MODEL) -> tuple[str, float, bool]:
    """
    Pipeline C：回傳 `(boxed_answer, latency_sec, truncated)`。

    prompt 與 Pipeline A 逐字相同——換模型不換題目、不換提問方式，
    否則比較的就不只是「誰會算」。
    """
    user_prompt = (
        f"請計算比率：\n"
        f"分子：{num_raw}\n"
        f"分母：{den_raw}\n"
        f"公式：比率 = (分子 / 分母) × 100%\n"
        f"請計算並將結果（四捨五入至小數點後兩位，格式如 23.45%）放入 \\boxed{{}}。"
    )
    payload = {
        "systemInstruction": {"parts": [{"text": A._RATIO_LLM_SYSTEM}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {"temperature": 0, "maxOutputTokens": 3000},
    }
    req = urllib.request.Request(
        ENDPOINT.format(model=model),
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"x-goog-api-key": key, "Content-Type": "application/json"},
        method="POST")

    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        parts = (body.get("candidates") or [{}])[0].get(
            "content", {}).get("parts") or []
        raw = "".join(p.get("text", "") for p in parts)
    except urllib.error.HTTPError as exc:
        raw = f"[Gemini HTTP {exc.code}：{exc.read()[:120]!r}]"
    except Exception as exc:                                   # noqa: BLE001
        raw = f"[Gemini 例外：{type(exc).__name__}: {exc}]"
    elapsed = time.perf_counter() - t0

    is_error = raw.startswith("[Gemini")
    truncated = is_error or "\\boxed{" not in raw
    boxed = "" if is_error else A.v14._extract_boxed_answer(raw)
    return boxed, elapsed, truncated


def main() -> int:
    if not QUESTIONS.exists():
        print(f"✗ 找不到 {QUESTIONS}")
        return 2
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else 0
    dataset = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    if limit:
        dataset = dataset[:limit]
    key = _api_key()

    rows: list[dict] = []
    done: set[str] = set()
    if CKPT.exists():
        rows = json.loads(CKPT.read_text(encoding="utf-8"))
        done = {r["id"] for r in rows}
        print(f"  ↻ 自 checkpoint 續跑，已完成 {len(rows)} 題")

    print("═" * 74)
    print(f"  Pipeline C：{MODEL} 算術（分子分母與 A/B 完全相同）")
    print(f"  資料集：{len(dataset)} 題（{QUESTIONS.name}）")
    print("═" * 74)

    for i, item in enumerate(dataset, 1):
        if item["id"] in done:
            continue
        meta = item["metadata"]
        num_raw, den_raw = meta["numerator_raw"], meta["denominator_raw"]
        gold = item["expected_ratio"]

        ans, lat, trunc = compute_ratio_gemini(num_raw, den_raw, key)
        val = A._parse_ratio_answer(ans) if not trunc else None
        gold_val = A._parse_ratio_answer(gold)
        exact = (val is not None and gold_val is not None
                 and abs(val - gold_val) < 1e-9)
        within = (val is not None and gold_val is not None
                  and abs(val - gold_val) <= TOLERANCE_PP)

        rows.append({"id": item["id"], "ratio": meta.get("ratio_name", ""),
                     "numerator_raw": num_raw, "denominator_raw": den_raw,
                     "gold": str(gold), "gemini_answer": ans,
                     "gemini_exact": exact, "gemini_within_tol": within,
                     "gemini_truncated": trunc,
                     "gemini_latency_sec": round(lat, 3)})
        CKPT.write_text(json.dumps(rows, ensure_ascii=False, indent=2),
                        encoding="utf-8")
        mark = "✓" if exact else ("~" if within else ("⋯" if trunc else "✗"))
        print(f"  [{i:02d}/{len(dataset)}] {mark} "
              f"{str(meta.get('ratio_name','')):<10s} "
              f"金標 {str(gold):<9s} Gemini {str(ans)[:12]:<13s} {lat:5.2f}s",
              flush=True)

    n = len(rows)
    ex = sum(r["gemini_exact"] for r in rows)
    tol = sum(r["gemini_within_tol"] for r in rows)
    tr = sum(r["gemini_truncated"] for r in rows)
    lat = sum(r["gemini_latency_sec"] for r in rows) / n if n else 0.0

    # 併入 A/B 兩管線的既有結果以利對照
    prev = {}
    p = BASE / "results" / "benchmark_ratio_pipelines.json"
    if p.exists():
        prev = json.loads(p.read_text(encoding="utf-8")).get("summary", {})

    report = {
        "experiment": "衍生比率計算之算術端外部效度對照（Pipeline C）",
        "dataset": QUESTIONS.name, "n": n, "tolerance_pp": TOLERANCE_PP,
        "control": "分子／分母與 Pipeline A/B 完全相同（同一次 _direct_lookup_flex "
                   "抽取結果）；system/user prompt 逐字沿用；唯一變因為算術執行者。",
        "summary": {
            "gemini_model": MODEL,
            "gemini_exact": ex, "gemini_exact_rate": round(ex / n, 4) if n else 0.0,
            "gemini_within_tolerance": tol,
            "gemini_within_tolerance_rate": round(tol / n, 4) if n else 0.0,
            "gemini_truncated": tr,
            "gemini_avg_latency_sec": round(lat, 3),
        },
        "baseline_from_pipelines_json": prev,
        "rows": rows,
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                   encoding="utf-8")

    print("\n" + "═" * 74)
    print(f"  {MODEL}：精確 {ex}/{n}（{ex/n:.1%}）｜"
          f"容差內 {tol}/{n}（{tol/n:.1%}）｜截斷 {tr}｜平均 {lat:.2f}s")
    if prev:
        print(f"  Qwen3-4B-AWQ  ：精確 {prev.get('llm_exact')}/{prev.get('llm_exact')  and n}"
              f"（{prev.get('llm_exact_rate', 0):.1%}）｜"
              f"容差內 {prev.get('llm_within_tolerance')}"
              f"（{prev.get('llm_within_tolerance_rate', 0):.1%}）｜"
              f"截斷 {prev.get('llm_truncated')}")
        print(f"  Python 代數   ：精確 {prev.get('py_exact')}"
              f"（{prev.get('py_exact_rate', 0):.1%}）")
    print("═" * 74)
    print(f"\n→ {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
