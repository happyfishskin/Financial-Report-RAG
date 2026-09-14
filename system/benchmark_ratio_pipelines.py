#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
衍生比率指標計算：Pipeline A（LLM 算術）vs Pipeline B（確定性代數）
======================================================================
消融實驗：固定「用 _direct_lookup_flex 抽取分子分母」這一步完全相同，
只讓「誰做除法」這個變數不同，藉此乾淨地隔離「LLM 算術可靠度」這件事，
不與檢索品質混在一起比較。

Pipeline A（參考 csv_to38.py 的 RATIO_EXPANSION 設計）：
  抽出分子分母原始金額後，組成 Prompt 交給 Qwen3-4B-AWQ 用思維鏈計算
  比率並輸出 \\boxed{}，比照 csv_to38.py 的 Reduce 階段風格（不加
  /no_think，保留思考空間讓小模型有最大機會把除法算對——這是對 LLM
  算術最公平的測試條件，不刻意閹割思考能力讓 Python 贏得不明不白）。

Pipeline B（rag_test_system_v14 Fix 14 採用）：
  Python 端直接 round(分子/分母*100, 2)，零額外 LLM 呼叫。

測試資料：questions/ratio_questions_50.json（50 題，5 種比率 ×
無歧義金標，由 generate_ratio_questions.py 生成——金標本身就是用
分子/分母算出來的，不受任何 LLM 影響，可視為 100% 正確的 ground truth）。

輸出：results/benchmark_ratio_pipelines.json ＋ console 對照表
"""

import json
import re
import statistics
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))

import rag_test_system_v14 as v14  # noqa: E402

TOLERANCE_PP = 0.10   # 容許誤差（百分點），用來區分「格式不同」vs「算錯」


def _to_float(s: str) -> float | None:
    t = str(s).replace(",", "").strip()
    m = re.search(r"-?\d+(?:\.\d+)?", t)
    if not m:
        return None
    v = float(m.group(0))
    return -v if ("(" in t and v > 0) else v


def _parse_ratio_answer(text: str) -> float | None:
    """從任意格式的答案字串（'23.45%'/'23.45'/'約23.45%'）抽出數值。"""
    m = re.search(r"-?\d+(?:\.\d+)?", str(text).replace(",", ""))
    return float(m.group(0)) if m else None


# ─────────────────────────────────────────────────────────────
# Pipeline A：LLM 算術（同一組 numerator_raw/denominator_raw，交給 LLM 除）
# ─────────────────────────────────────────────────────────────
_RATIO_LLM_SYSTEM = """你是精確的財務分析師，請根據提供的兩個財務數字計算比率。

【計算規則】
1. 公式：比率 = (分子 / 分母) × 100%，結果四捨五入至小數點後兩位（例如 23.45%）。
2. 所有計算過程請寫在 <think></think> 標籤內，離開標籤後只能輸出 \\boxed{...} 格式的最終答案。
3. \\boxed{} 內只能是「數字%」的格式（例如 \\boxed{23.45%}），不得包含任何文字說明或單位以外的內容。
"""


def compute_ratio_llm(numerator_raw: str, denominator_raw: str,
                      vllm_url: str, llm_model: str) -> tuple[str, float, bool]:
    """Pipeline A：回傳 (raw_llm_output, latency_sec, truncated)。
    truncated=True 代表輸出中完全找不到 \\boxed{}（多半是思考模式手算
    長除法把 token 預算耗盡，尚未得出結論就被截斷——這是與「算錯」
    不同的失敗型態，需分開統計，見 README 實驗七）。"""
    user_prompt = (
        f"請計算比率：\n"
        f"分子：{numerator_raw}\n"
        f"分母：{denominator_raw}\n"
        f"公式：比率 = (分子 / 分母) × 100%\n"
        f"請計算並將結果（四捨五入至小數點後兩位，格式如 23.45%）放入 \\boxed{{}}。"
    )
    t0 = time.perf_counter()
    # [注] Qwen3 開啟思考模式後，4B 量化模型常用手算長除法方式推理，
    # 若 max_tokens 太小會在算完之前被截斷（見 README 實驗七討論），
    # 故給予充裕的思考預算，確保「算錯」與「算不完」不會混淆。
    raw = v14._call_vllm(vllm_url, llm_model, _RATIO_LLM_SYSTEM, user_prompt,
                         max_tokens=3000, timeout=180)
    elapsed = time.perf_counter() - t0
    is_error = raw.startswith("[vLLM ")          # [Fix 15] 連線失敗/逾時錯誤字串
    truncated = is_error or "\\boxed{" not in raw
    boxed = "" if is_error else v14._extract_boxed_answer(raw)
    return boxed, elapsed, truncated


# ─────────────────────────────────────────────────────────────
# Pipeline B：確定性代數（即 v14 Fix 14 的 _compute_ratio_value）
# ─────────────────────────────────────────────────────────────
def compute_ratio_python(numerator_raw: str, denominator_raw: str) -> tuple[str | None, float]:
    """Pipeline B：回傳 (answer, latency_sec)。"""
    t0 = time.perf_counter()
    num_val, den_val = _to_float(numerator_raw), _to_float(denominator_raw)
    if num_val is None or den_val is None or den_val == 0:
        ans = None
    else:
        ans = f"{round(num_val / den_val * 100, 2)}%"
    elapsed = time.perf_counter() - t0
    return ans, elapsed


def main() -> None:
    ds_path = BASE / "questions" / "ratio_questions_50.json"
    if not ds_path.exists():
        sys.exit(f"找不到 {ds_path}，請先執行 "
                 f"questions/generators/generate_ratio_questions.py")
    dataset = json.loads(ds_path.read_text(encoding="utf-8"))

    # [Fix 15] 逐題存檔：長思考鏈耗時可達 1–2 分鐘/題，全量 50 題單次執行
    # 可能超過 1 小時；任何單一請求的例外都不該讓已完成的進度全部遺失，
    # 故每題結束即寫入 checkpoint，並支援從 checkpoint 續跑。
    ckpt_path = BASE / "results" / "_ratio_bench_checkpoint.json"
    rows: list[dict] = []
    done_ids: set[str] = set()
    if ckpt_path.exists():
        rows = json.loads(ckpt_path.read_text(encoding="utf-8"))
        done_ids = {r["id"] for r in rows}
        print(f"  ↻ 從 checkpoint 續跑，已完成 {len(rows)} 題")

    print("═" * 78)
    print(f"  比率計算消融實驗：Pipeline A（LLM 算術）vs Pipeline B（Python 代數）")
    print(f"  資料集：{len(dataset)} 題（{ds_path.name}）")
    print("═" * 78)

    for i, item in enumerate(dataset, 1):
        if item["id"] in done_ids:
            continue
        meta = item["metadata"]
        num_raw, den_raw = meta["numerator_raw"], meta["denominator_raw"]
        gold = item["expected_ratio"]

        try:
            llm_ans, llm_lat, llm_truncated = compute_ratio_llm(
                num_raw, den_raw, v14.DEFAULT_VLLM_URL, v14.DEFAULT_LLM_MODEL)
        except Exception as exc:                                  # noqa: BLE001
            llm_ans, llm_lat, llm_truncated = f"[例外：{exc}]", 0.0, True
        py_ans, py_lat = compute_ratio_python(num_raw, den_raw)

        llm_val = _parse_ratio_answer(llm_ans) if not llm_truncated else None
        py_val  = _parse_ratio_answer(py_ans) if py_ans else None

        llm_exact = (llm_val is not None and abs(llm_val - gold) < 1e-9)
        llm_tol   = (llm_val is not None and abs(llm_val - gold) <= TOLERANCE_PP)
        py_exact  = (py_val is not None and abs(py_val - gold) < 1e-9)

        rows.append({
            "id": item["id"], "question": item["question"], "ratio_type": meta["ratio_type"],
            "gold": gold, "llm_answer": llm_ans, "llm_value": llm_val,
            "llm_truncated": llm_truncated,
            "llm_exact": llm_exact, "llm_within_tol": llm_tol, "llm_latency_sec": round(llm_lat, 3),
            "py_answer": py_ans, "py_value": py_val, "py_exact": py_exact,
            "py_latency_sec": round(py_lat, 6),
        })
        ckpt_path.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")

        mark_llm = "TRUNC" if llm_truncated else ("✓" if llm_exact else ("≈" if llm_tol else "✗"))
        mark_py  = "✓" if py_exact else "✗"
        print(f"  [{i:02d}/{len(dataset)}] {item['question'][:32]:<34} "
              f"金標={gold:>6}% | LLM={str(llm_ans)[:10]:<10}{mark_llm} ({llm_lat:.2f}s) | "
              f"Py={str(py_ans):<10}{mark_py} ({py_lat*1000:.2f}ms)", flush=True)

    # 依原始資料集順序重排（checkpoint 續跑時 rows 可能非原序）
    order = {item["id"]: idx for idx, item in enumerate(dataset)}
    rows.sort(key=lambda r: order.get(r["id"], 1 << 30))

    n = len(rows)
    llm_exact_n = sum(r["llm_exact"] for r in rows)
    llm_tol_n   = sum(r["llm_within_tol"] for r in rows)
    llm_trunc_n = sum(r["llm_truncated"] for r in rows)
    py_exact_n  = sum(r["py_exact"] for r in rows)
    llm_lats = [r["llm_latency_sec"] for r in rows]
    py_lats  = [r["py_latency_sec"] for r in rows]

    print("\n" + "═" * 78)
    print("  彙總結果")
    print("═" * 78)
    print(f"  {'指標':<28}{'Pipeline A (LLM 算術)':>24}{'Pipeline B (Python 代數)':>24}")
    print(f"  {'精確匹配 (EM)':<28}{f'{llm_exact_n}/{n} ({llm_exact_n/n:.1%})':>24}"
          f"{f'{py_exact_n}/{n} ({py_exact_n/n:.1%})':>24}")
    print(f"  {f'誤差容忍 (±{TOLERANCE_PP}百分點)':<28}{f'{llm_tol_n}/{n} ({llm_tol_n/n:.1%})':>24}{'—':>24}")
    print(f"  {'思考預算耗盡未答（TRUNC）':<28}{f'{llm_trunc_n}/{n} ({llm_trunc_n/n:.1%})':>24}{'—':>24}")
    print(f"  {'平均延遲':<28}{f'{statistics.mean(llm_lats):.3f}s':>24}"
          f"{f'{statistics.mean(py_lats)*1000:.4f}ms':>24}")
    print(f"  {'延遲加速倍數':<28}{'—':>24}"
          f"{f'{statistics.mean(llm_lats)/max(statistics.mean(py_lats), 1e-9):.0f}×':>24}")

    by_ratio: dict[str, list[dict]] = {}
    for r in rows:
        by_ratio.setdefault(r["ratio_type"], []).append(r)
    print(f"\n  分比率類型 LLM 算術正確率：")
    for rt, rs in by_ratio.items():
        ok = sum(x["llm_exact"] for x in rs)
        print(f"    {rt:<8}{ok}/{len(rs)} ({ok/len(rs):.1%})")

    misses = [r for r in rows if not r["llm_exact"]]
    if misses:
        print(f"\n  LLM 算術錯誤案例（{len(misses)} 題）：")
        for r in misses[:10]:
            diff = (r["llm_value"] - r["gold"]) if r["llm_value"] is not None else None
            print(f"    {r['question'][:36]:<38} 金標={r['gold']}% | LLM輸出={r['llm_answer']}"
                  + (f" | 誤差={diff:+.2f}pp" if diff is not None else " | 無法解析"))

    out = {
        "dataset": ds_path.name, "n": n, "tolerance_pp": TOLERANCE_PP,
        "summary": {
            "llm_exact": llm_exact_n, "llm_exact_rate": round(llm_exact_n / n, 4),
            "llm_truncated": llm_trunc_n, "llm_truncated_rate": round(llm_trunc_n / n, 4),
            "llm_within_tolerance": llm_tol_n, "llm_within_tolerance_rate": round(llm_tol_n / n, 4),
            "py_exact": py_exact_n, "py_exact_rate": round(py_exact_n / n, 4),
            "llm_avg_latency_sec": round(statistics.mean(llm_lats), 4),
            "py_avg_latency_sec": round(statistics.mean(py_lats), 6),
            "speedup": round(statistics.mean(llm_lats) / max(statistics.mean(py_lats), 1e-9), 1),
        },
        "by_ratio_type": {
            rt: {"n": len(rs), "llm_exact": sum(x["llm_exact"] for x in rs)}
            for rt, rs in by_ratio.items()
        },
        "results": rows,
    }
    out_path = BASE / "results" / "benchmark_ratio_pipelines.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    ckpt_path.unlink(missing_ok=True)   # 全部完成 → 正式結果已輸出，清掉暫存 checkpoint
    print(f"\n已輸出 {out_path.relative_to(BASE)}")


if __name__ == "__main__":
    main()
