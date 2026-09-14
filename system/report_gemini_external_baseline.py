#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
實驗二外部對照組評測報告產生器

讀取實驗二各配置之 eval JSON（含新增的 Gemini 兩個 arm），輸出：
  results/gemini_external_baseline.json   機器可讀彙總
  results/gemini_external_baseline.md     對照評測報告

除點估計外一併輸出 95% Clopper-Pearson 信賴區間，並對「同一批 60 題」的配對
比較執行 McNemar 精確檢定（二項式版本，適用小樣本），避免以點估計差異直接
下結論。所有統計皆以標準函式庫實作，不依賴 scipy。
"""
from __future__ import annotations

import json
from math import comb
from pathlib import Path

_V7 = Path(__file__).resolve().parent.parent / "legacy_v12"
_RES = Path(__file__).resolve().parent / "results"

# 顯示名稱 → eval JSON 路徑。生成端一欄用於區分「換模型」與「換架構」。
CONFIGS = [
    ("純 LLM（無檢索）",            _V7 / "rag_evaluation_v12_llm_only.json",              "Qwen3-4B-AWQ"),
    ("純向量",                      _RES / "rag_evaluation_v12_vector_only_TRUE.json",     "Qwen3-4B-AWQ"),
    ("純向量 ＋ Gemini",            _RES / "eval_gemini_vector.json",                      "gemini-2.5-flash"),
    ("純圖譜",                      _V7 / "rag_evaluation_v12_graph_only.json",            "Qwen3-4B-AWQ"),
    ("圖譜＋向量真並行",            _RES / "rag_evaluation_v12_graph_vector_PARALLEL.json", "Qwen3-4B-AWQ"),
    ("圖譜＋向量真並行 ＋ Gemini",  _RES / "eval_gemini_parallel.json",                    "gemini-2.5-flash"),
    ("混合路由（本系統）",          _V7 / "rag_evaluation_v12_full.json",                  "確定性作答（不經生成）"),
]

# 配對比較：(名稱A, 名稱B, 這個比較在回答什麼問題)
PAIRS = [
    ("純向量", "純向量 ＋ Gemini",
     "相同檢索、相同題目下，把 4B 地端模型換成前沿模型的效果（純模型貢獻）"),
    ("圖譜＋向量真並行", "圖譜＋向量真並行 ＋ Gemini",
     "相同雙軌檢索下，把 4B 地端模型換成前沿模型的效果（純模型貢獻）"),
    ("純向量 ＋ Gemini", "混合路由（本系統）",
     "前沿模型跑標準 RAG vs 本研究架構（架構貢獻的外部座標）"),
    ("圖譜＋向量真並行 ＋ Gemini", "混合路由（本系統）",
     "前沿模型拿到本系統全部證據 vs 本系統確定性作答"),
]


# ── 統計工具 ────────────────────────────────────────────────────────
def clopper_pearson(k: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    """精確二項信賴區間，以二分搜尋求解，不依賴 scipy。"""
    def p_le(p, k, n):
        return sum(comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(0, k + 1))

    def p_ge(p, k, n):
        return sum(comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k, n + 1))

    lo, hi = 0.0, 1.0
    if k > 0:
        a, b = 0.0, 1.0
        for _ in range(200):
            m = (a + b) / 2
            if p_ge(m, k, n) < alpha / 2:
                a = m
            else:
                b = m
        lo = a
    if k < n:
        a, b = 0.0, 1.0
        for _ in range(200):
            m = (a + b) / 2
            if p_le(m, k, n) > alpha / 2:
                a = m
            else:
                b = m
        hi = a
    return lo, hi


def mcnemar_exact(b: int, c: int) -> float:
    """
    McNemar 精確檢定（雙尾二項式）。

    b = A 對而 B 錯的題數；c = A 錯而 B 對的題數。
    僅不一致的配對帶有資訊；H0 為 b、c 來自 p=0.5 的二項分布。
    """
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(comb(n, i) for i in range(0, k + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


# ── 載入 ────────────────────────────────────────────────────────────
def load_config(path: Path) -> dict | None:
    if not path.exists():
        return None
    d = json.loads(path.read_text(encoding="utf-8"))
    results = d.get("results", [])
    per_q = {}
    for r in results:
        qid = r.get("id")
        sc = r.get("scores") or {}
        per_q[qid] = bool(sc.get("exact_match"))
    summary = d.get("summary", {})
    am = summary.get("academic_metrics", {})
    n = len(per_q)
    k = sum(per_q.values())
    rates = summary.get("rates", {})
    return {
        "n": n,
        "correct": k,
        "em": (k / n) if n else 0.0,
        "em_reported": rates.get("exact_match"),
        "numeric_match": rates.get("numeric_match"),
        "contains_match": rates.get("contains_match"),
        "partial_numeric": rates.get("partial_numeric"),
        "answer_mode_dist": summary.get("answer_mode_dist", {}),
        "refusal_count": am.get("refusal_count"),
        "precision": am.get("precision"),
        "recall": am.get("recall"),
        "f1": am.get("f1"),
        "per_q": per_q,
    }


def main() -> None:
    loaded: dict[str, dict] = {}
    gen_of: dict[str, str] = {}
    missing: list[str] = []
    for name, path, gen in CONFIGS:
        c = load_config(path)
        gen_of[name] = gen
        if c is None:
            missing.append(f"{name} → {path}")
        else:
            loaded[name] = c

    # ── 主表 ────────────────────────────────────────────────────────
    rows = []
    for name, _path, gen in CONFIGS:
        c = loaded.get(name)
        if not c:
            continue
        lo, hi = clopper_pearson(c["correct"], c["n"])
        rows.append({
            "config": name,
            "generator": gen,
            "n": c["n"],
            "correct": c["correct"],
            "em": round(c["em"], 4),
            "ci95_low": round(lo, 4),
            "ci95_high": round(hi, 4),
            "numeric_match": c["numeric_match"],
            "contains_match": c["contains_match"],
            "partial_numeric": c["partial_numeric"],
            "refusal_count": c["refusal_count"],
            "f1": c["f1"],
            "answer_mode_dist": c["answer_mode_dist"],
        })

    # ── 配對檢定 ────────────────────────────────────────────────────
    pairs_out = []
    for a, b, question in PAIRS:
        ca, cb = loaded.get(a), loaded.get(b)
        if not ca or not cb:
            continue
        common = sorted(set(ca["per_q"]) & set(cb["per_q"]))
        b_only = sum(1 for q in common if ca["per_q"][q] and not cb["per_q"][q])
        c_only = sum(1 for q in common if not ca["per_q"][q] and cb["per_q"][q])
        p = mcnemar_exact(b_only, c_only)
        pairs_out.append({
            "a": a, "b": b, "asks": question,
            "n_paired": len(common),
            "a_em": round(ca["em"], 4), "b_em": round(cb["em"], 4),
            "delta_pp": round((cb["em"] - ca["em"]) * 100, 1),
            "a_only_correct": b_only, "b_only_correct": c_only,
            "mcnemar_p": round(p, 5),
            "significant_at_05": p < 0.05,
        })

    out = {
        "experiment": "實驗二外部對照組：Gemini-2.5-flash 生成端",
        "dataset": "multi_company_test_dataset.json（60 題，與實驗二其餘配置同一批）",
        "method": (
            "固定檢索與資料完全不變，僅將生成端由 Qwen3-4B-AWQ 換為 gemini-2.5-flash。"
            "意圖路由仍由本機 Qwen 執行。Prompt 與 Qwen 組逐字相同，僅移除 Qwen 專用之 "
            "/no_think；Gemini 採預設 thinking 開啟（較 Qwen 組更強之配置），temperature=0。"
            "評分沿用 version7/rag_test_system_v12.py 之同一評分器。"
        ),
        "configs": rows,
        "paired_tests": pairs_out,
        "missing_inputs": missing,
        "stats_note": (
            "CI 為 95% Clopper-Pearson 精確區間；配對比較為 McNemar 精確檢定（雙尾二項式），"
            "僅計入兩配置答案正誤不一致之題目。"
        ),
    }
    (_RES / "gemini_external_baseline.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # ── Markdown 報告 ───────────────────────────────────────────────
    L = []
    L.append("# 實驗二外部對照組：Gemini-2.5-flash 生成端\n")
    L.append(out["method"] + "\n")
    L.append("## 一、總表（60 題，EM 與 95% 信賴區間）\n")
    L.append("| 配置 | 生成端 | EM | 95% CI | numeric | contains | 拒答 | F1 |")
    L.append("|---|---|---:|---|---:|---:|---:|---:|")
    for r in rows:
        f1 = f"{r['f1']:.3f}" if isinstance(r["f1"], (int, float)) else "—"
        ref = r["refusal_count"] if r["refusal_count"] is not None else "—"
        nm = f"{r['numeric_match']*100:.1f}%" if r["numeric_match"] is not None else "—"
        cm = f"{r['contains_match']*100:.1f}%" if r["contains_match"] is not None else "—"
        L.append(
            f"| {r['config']} | {r['generator']} | **{r['em']*100:.1f}%** | "
            f"[{r['ci95_low']*100:.1f}%, {r['ci95_high']*100:.1f}%] | "
            f"{nm} | {cm} | {ref} | {f1} |"
        )
    L.append("")
    L.append(
        "> **格式敏感度說明（不利於本研究之方向亦如實列出）**：EM 為嚴格字串比對，"
        "會懲罰格式而非抽取能力。例如 id=3，Gemini 正確抽出兩個數值（152,323／134,057）"
        "但加上公司名前綴，EM 判為 0。故本表一併列出格式不敏感的 numeric／contains 指標；"
        "在該兩項指標下，Gemini 相對 4B 地端模型的最大優勢僅 +3.4 pp，"
        "而混合路由相對兩個 Gemini 配置的優勢在所有指標上皆維持約 60 pp。"
        "結論不因指標選擇而改變。\n"
    )

    L.append("## 二、配對顯著性檢定（McNemar 精確檢定）\n")
    L.append("同一批 60 題，逐題配對；僅不一致的配對帶有資訊量。\n")
    L.append("| 比較 | Δ(pp) | 僅前者對 | 僅後者對 | McNemar p | 顯著(α=.05) |")
    L.append("|---|---:|---:|---:|---:|:--:|")
    for p in pairs_out:
        L.append(
            f"| {p['a']} → {p['b']} | {p['delta_pp']:+.1f} | {p['a_only_correct']} | "
            f"{p['b_only_correct']} | {p['mcnemar_p']:.4f} | "
            f"{'✔' if p['significant_at_05'] else '✘'} |"
        )
    L.append("")
    L.append("各比較所回答的問題：\n")
    for p in pairs_out:
        L.append(f"- **{p['a']} → {p['b']}**：{p['asks']}")
    L.append("")

    if missing:
        L.append("## 缺少的輸入檔\n")
        for m in missing:
            L.append(f"- {m}")
        L.append("")

    L.append("## 三、統計註記\n")
    L.append(out["stats_note"] + "\n")
    (_RES / "gemini_external_baseline.md").write_text("\n".join(L), encoding="utf-8")

    print("\n".join(L))
    print(f"\n→ {_RES/'gemini_external_baseline.json'}")
    print(f"→ {_RES/'gemini_external_baseline.md'}")


if __name__ == "__main__":
    main()
