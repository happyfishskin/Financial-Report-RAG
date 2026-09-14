#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
跨公司比率比較消融：Pipeline A（LLM 算術）vs Pipeline B（確定性代數）
======================================================================
實驗七的延伸。原實驗只測「一次除法」，本實驗測「兩次除法＋一次比大小」，
因為實驗七的動機敘述舉的例子本來就是跨公司比較（「聯發科與鴻海的營業利益率
誰比較高」），而真實使用者最常問的也是這種相對問題。

與單公司題的關鍵差異：**錯誤會複合，且會改變結論**。
單公司題答錯只是數字不準；跨公司題只要任一次除法算偏，就可能把「誰比較高」
判反——後者對使用者的傷害遠大於前者（看到錯的數字還可能起疑，看到錯的結論
通常直接採信）。故本實驗除了比率精確率之外，另外獨立統計**結論正確率**，
並依兩比率差距（margin）分層呈現。

兩條 Pipeline 拿到完全相同的四個原始金額（兩家公司的分子與分母），
唯一的變數仍然只有「誰做除法與比較」：

  Pipeline A：四個數字連同題意一起交給 Qwen3-4B-AWQ，開放思考模式，
              要求輸出兩個比率與孰高的結論。
  Pipeline B：Python 各算一次 round(num/den*100, 2)，再比大小。

輸出：results/benchmark_ratio_cross_company.json ＋ console 對照表
用法：python3 benchmark_ratio_cross_company.py
"""

import json
import re
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))

import rag_test_system_v14 as v14  # noqa: E402

TOLERANCE_PP = 0.10
BAND_ORDER = ["near", "mid", "far"]
BAND_LABEL = {"near": "margin < 1pp", "mid": "1–5pp", "far": "≥ 5pp"}


def _to_float(s: str) -> float | None:
    t = str(s).replace(",", "").strip()
    m = re.search(r"-?\d+(?:\.\d+)?", t)
    if not m:
        return None
    v = float(m.group(0))
    return -v if ("(" in t and v > 0) else v


_RATIO_XC_SYSTEM = """你是精確的財務分析師。請根據提供的兩家公司財務數字，各自計算比率並比較高低。

【計算規則】
1. 公式：比率 = (分子 / 分母) × 100%，四捨五入至小數點後兩位。
2. 兩家公司都要各算一次。
3. 所有計算過程請寫在 <think></think> 標籤內，離開標籤後只能輸出 \\boxed{...}。
4. \\boxed{} 內必須嚴格為以下格式：
   \\boxed{【第一家公司名】: 12.34% ｜ 【第二家公司名】: 56.78% ｜ 較高: 【比率較高者之公司名】}
   其中【…】必須替換成**題目中出現的公司名稱原文**（繁體中文，逐字照抄，
   不可翻譯、不可簡化、不可寫成「公司A」之類的代稱）。
"""


def compute_xc_llm(item: dict, vllm_url: str, llm_model: str):
    """Pipeline A：兩個比率與結論全交給 LLM。回傳 (boxed, latency, truncated)。"""
    a, b = item["metadata"]["companies"]
    user = (
        f"請比較以下兩家公司的{item['metadata']['ratio_type']}"
        f"（{item['metadata']['quarter']}）：\n\n"
        f"{a['alias']}：\n  分子（{item['metadata']['numerator_item']}）：{a['numerator_raw']}\n"
        f"  分母（{item['metadata']['denominator_item']}）：{a['denominator_raw']}\n\n"
        f"{b['alias']}：\n  分子（{item['metadata']['numerator_item']}）：{b['numerator_raw']}\n"
        f"  分母（{item['metadata']['denominator_item']}）：{b['denominator_raw']}\n\n"
        f"請分別計算兩家的比率，並指出誰比較高。"
    )
    t0 = time.perf_counter()
    raw = v14._call_vllm(vllm_url, llm_model, _RATIO_XC_SYSTEM, user,
                         max_tokens=4000, timeout=240)
    elapsed = time.perf_counter() - t0
    is_error = raw.startswith("[vLLM ")
    truncated = is_error or "\\boxed{" not in raw
    boxed = "" if is_error else v14._extract_boxed_answer(raw)
    return boxed, elapsed, truncated


def compute_xc_python(item: dict):
    """Pipeline B：Python 各算一次再比大小。"""
    a, b = item["metadata"]["companies"]
    t0 = time.perf_counter()
    out = []
    vals = []
    for c in (a, b):
        nv, dv = _to_float(c["numerator_raw"]), _to_float(c["denominator_raw"])
        if nv is None or dv is None or dv == 0:
            return None, time.perf_counter() - t0, None
        r = round(nv / dv * 100, 2)
        vals.append(r)
        out.append(f"{c['alias']}: {r}%")
    winner = a["alias"] if vals[0] > vals[1] else b["alias"]
    ans = " ｜ ".join(out) + f" ｜ 較高: {winner}"
    return ans, time.perf_counter() - t0, winner


def _norm_ans(s: str) -> str:
    """EM 比對前的正規化：去除模型從格式範本抄來的【】裝飾與所有空白。
    括號裝飾不是算術錯誤，計入 EM 會讓指標失去鑑別力（未正規化時為 0/50）。"""
    return re.sub(r"\s+", "", str(s).replace("【", "").replace("】", ""))


def parse_xc(text: str, aliases: list[str]):
    """
    從答案字串抽出 {alias: 比率} 與結論公司。

    小模型常見兩種命名偏差，兩者都不是「算錯」，不應計為結論錯誤：
      (a) 原樣抄用提示詞裡的代稱（「公司A」「公司B」）；
      (b) 以簡體輸出公司名（「联发科」對「聯發科」）。
    故名稱無法直接比對時，改以「輸出的兩個比率段落順序」對應提示詞中的公司順序
    （提示詞固定先列 aliases[0] 再列 aliases[1]），再據此判定結論。
    """
    t = str(text)
    segs = re.findall(r"([^｜|{}\n]+?)\s*[:：]\s*(-?\d+(?:\.\d+)?)\s*%", t)
    segs = [(n.strip(), float(v)) for n, v in segs if "較高" not in n]

    ratios: dict[str, float] = {}
    for al in aliases:
        m = re.search(re.escape(al) + r"\s*[:：]\s*(-?\d+(?:\.\d+)?)\s*%?", t)
        if m:
            ratios[al] = float(m.group(1))
    # 名稱對不上但剛好兩段 → 依序位對應
    if len(ratios) < 2 and len(segs) == 2:
        ratios = {aliases[0]: segs[0][1], aliases[1]: segs[1][1]}

    winner = None
    m = re.search(r"較高\s*[:：]\s*([^\s｜|，,。}]+)", t)
    if m:
        tok = m.group(1).strip()
        for al in aliases:                              # (1) 直接名稱比對
            if al in tok or tok in al:
                winner = al
                break
        if winner is None and len(segs) == 2:           # (2) 對應到輸出段落名稱
            for idx, (nm, _v) in enumerate(segs):
                if nm and (nm in tok or tok in nm):
                    winner = aliases[idx]
                    break
        if winner is None:                              # (3) 代稱/序位關鍵詞
            for idx, cues in enumerate((("公司A", "公司甲", "第一", "前者", "A"),
                                        ("公司B", "公司乙", "第二", "後者", "B"))):
                if any(c == tok or c in tok for c in cues):
                    winner = aliases[idx]
                    break
    return ratios, winner


def main() -> None:
    ds_path = BASE / "questions" / "ratio_cross_company_50.json"
    if not ds_path.exists():
        sys.exit(f"找不到 {ds_path}，請先執行 "
                 f"questions/generators/generate_ratio_cross_company.py")
    dataset = json.loads(ds_path.read_text(encoding="utf-8"))

    ckpt = BASE / "results" / "_ratio_xc_checkpoint.json"
    rows: list[dict] = []
    done: set[str] = set()
    if ckpt.exists():
        rows = json.loads(ckpt.read_text(encoding="utf-8"))
        done = {r["id"] for r in rows}
        print(f"  ↻ 從 checkpoint 續跑，已完成 {len(rows)} 題")

    print("═" * 84)
    print("  跨公司比率比較消融：Pipeline A（LLM 算術）vs Pipeline B（Python 代數）")
    print(f"  資料集：{len(dataset)} 題（{ds_path.name}）")
    print("═" * 84)

    for i, item in enumerate(dataset, 1):
        if item["id"] in done:
            continue
        meta = item["metadata"]
        aliases = [c["alias"] for c in meta["companies"]]
        gold_r = {c["alias"]: c["ratio_value"] for c in meta["companies"]}
        gold_w = item["expected_winner"]

        try:
            llm_ans, llm_lat, trunc = compute_xc_llm(
                item, v14.DEFAULT_VLLM_URL, v14.DEFAULT_LLM_MODEL)
        except Exception as exc:                                  # noqa: BLE001
            llm_ans, llm_lat, trunc = f"[例外：{exc}]", 0.0, True
        py_ans, py_lat, py_w = compute_xc_python(item)

        lr, lw = ({}, None) if trunc else parse_xc(llm_ans, aliases)
        pr, _ = parse_xc(py_ans or "", aliases)

        llm_both = (len(lr) == 2 and
                    all(abs(lr[a] - gold_r[a]) < 1e-9 for a in aliases))
        llm_tol = (len(lr) == 2 and
                   all(abs(lr[a] - gold_r[a]) <= TOLERANCE_PP for a in aliases))
        llm_conc = (lw == gold_w)
        py_both = (len(pr) == 2 and
                   all(abs(pr[a] - gold_r[a]) < 1e-9 for a in aliases))
        py_conc = (py_w == gold_w)
        # EM：整串答案與金標完全一致（與其他實驗同一把尺）
        llm_em = (_norm_ans(llm_ans) == _norm_ans(item["expected_answer"]))
        py_em = (_norm_ans(py_ans) == _norm_ans(item["expected_answer"]))

        rows.append({
            "id": item["id"], "question": item["question"],
            "ratio_type": meta["ratio_type"], "margin_pp": meta["margin_pp"],
            "margin_band": meta["margin_band"], "gold": item["expected_answer"],
            "gold_winner": gold_w,
            "llm_answer": llm_ans, "llm_ratios": lr, "llm_winner": lw,
            "llm_truncated": trunc, "llm_both_exact": llm_both,
            "llm_within_tol": llm_tol, "llm_conclusion_ok": llm_conc, "llm_em": llm_em,
            "llm_latency_sec": round(llm_lat, 3),
            "py_answer": py_ans, "py_both_exact": py_both,
            "py_conclusion_ok": py_conc, "py_em": py_em,
            "py_latency_sec": round(py_lat, 6),
        })
        ckpt.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")

        mk = "TRUNC" if trunc else ("✓" if llm_both else ("≈" if llm_tol else "✗"))
        cc = "結論✓" if llm_conc else "結論✗"
        print(f"  [{i:02d}/{len(dataset)}] {item['question'][:30]:<32} "
              f"[{meta['margin_band']:<4} {meta['margin_pp']:>5.2f}pp] "
              f"LLM {mk} {cc} ({llm_lat:5.1f}s) | Py ✓ ({py_lat*1000:.2f}ms)", flush=True)

    order = {it["id"]: i for i, it in enumerate(dataset)}
    rows.sort(key=lambda r: order.get(r["id"], 1 << 30))
    n = len(rows)

    def rate(key):
        return sum(r[key] for r in rows), sum(r[key] for r in rows) / n

    lb, lbr = rate("llm_both_exact")
    lt, ltr = rate("llm_within_tol")
    lc, lcr = rate("llm_conclusion_ok")
    le, ler = rate("llm_em")
    ltr_n, ltr_r = rate("llm_truncated")
    pb, pbr = rate("py_both_exact")
    pc, pcr = rate("py_conclusion_ok")
    pe, per_ = rate("py_em")
    llm_lats = [r["llm_latency_sec"] for r in rows]
    py_lats = [r["py_latency_sec"] for r in rows]

    print("\n" + "═" * 84)
    print("  彙總結果（跨公司比率比較，n = %d）" % n)
    print("═" * 84)
    print(f"  {'指標':<30}{'Pipeline A (LLM)':>24}{'Pipeline B (Python)':>24}")
    print(f"  {'兩個比率皆精確':<30}{f'{lb}/{n} ({lbr:.1%})':>24}{f'{pb}/{n} ({pbr:.1%})':>24}")
    print(f"  {f'兩個比率皆在 ±{TOLERANCE_PP}pp 內':<30}{f'{lt}/{n} ({ltr:.1%})':>24}{'—':>24}")
    print(f"  {'結論（誰比較高）正確':<30}{f'{lc}/{n} ({lcr:.1%})':>24}{f'{pc}/{n} ({pcr:.1%})':>24}")
    print(f"  {'完整字串 EM':<30}{f'{le}/{n} ({ler:.1%})':>24}{f'{pe}/{n} ({per_:.1%})':>24}")
    print(f"  {'思考預算耗盡未答':<30}{f'{ltr_n}/{n} ({ltr_r:.1%})':>24}{'—':>24}")
    print(f"  {'平均延遲':<30}{f'{statistics.mean(llm_lats):.2f}s':>24}"
          f"{f'{statistics.mean(py_lats)*1000:.4f}ms':>24}")

    print(f"\n  結論正確率 vs 兩比率差距（margin）：")
    by_band: dict[str, list[dict]] = {}
    for r in rows:
        by_band.setdefault(r["margin_band"], []).append(r)
    band_stats = {}
    for b in BAND_ORDER:
        rs = by_band.get(b, [])
        if not rs:
            continue
        c = sum(x["llm_conclusion_ok"] for x in rs)
        e = sum(x["llm_both_exact"] for x in rs)
        band_stats[b] = {"n": len(rs), "llm_conclusion_ok": c, "llm_both_exact": e,
                         "py_conclusion_ok": sum(x["py_conclusion_ok"] for x in rs)}
        print(f"    {b:<5}({BAND_LABEL[b]:<12}) n={len(rs):<3} "
              f"LLM 結論 {c}/{len(rs)} ({c/len(rs):5.1%})  "
              f"LLM 兩率皆精確 {e}/{len(rs)} ({e/len(rs):5.1%})  "
              f"Py 結論 {band_stats[b]['py_conclusion_ok']}/{len(rs)}")

    flips = [r for r in rows if not r["llm_conclusion_ok"] and not r["llm_truncated"]]
    if flips:
        print(f"\n  結論判反之案例（{len(flips)} 題）：")
        for r in flips[:10]:
            print(f"    [{r['margin_band']} {r['margin_pp']}pp] {r['question'][:34]:<36}")
            print(f"        金標 {r['gold']}")
            print(f"        LLM  {str(r['llm_answer'])[:76]}")

    out = {
        "dataset": ds_path.name, "n": n, "tolerance_pp": TOLERANCE_PP,
        "summary": {
            "llm_both_exact": lb, "llm_both_exact_rate": round(lbr, 4),
            "llm_within_tolerance": lt, "llm_within_tolerance_rate": round(ltr, 4),
            "llm_conclusion_ok": lc, "llm_conclusion_rate": round(lcr, 4),
            "llm_em": le, "llm_em_rate": round(ler, 4),
            "llm_truncated": ltr_n, "llm_truncated_rate": round(ltr_r, 4),
            "py_both_exact": pb, "py_both_exact_rate": round(pbr, 4),
            "py_conclusion_ok": pc, "py_conclusion_rate": round(pcr, 4),
            "py_em": pe, "py_em_rate": round(per_, 4),
            "llm_avg_latency_sec": round(statistics.mean(llm_lats), 4),
            "py_avg_latency_sec": round(statistics.mean(py_lats), 6),
            "speedup": round(statistics.mean(llm_lats) /
                             max(statistics.mean(py_lats), 1e-9), 1),
        },
        "by_margin_band": band_stats,
        "by_ratio_type": {
            rt: {"n": len(rs),
                 "llm_both_exact": sum(x["llm_both_exact"] for x in rs),
                 "llm_conclusion_ok": sum(x["llm_conclusion_ok"] for x in rs)}
            for rt, rs in
            {k: [r for r in rows if r["ratio_type"] == k]
             for k in Counter(r["ratio_type"] for r in rows)}.items()
        },
        "results": rows,
    }
    out_path = BASE / "results" / "benchmark_ratio_cross_company.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    ckpt.unlink(missing_ok=True)
    print(f"\n已輸出 {out_path.relative_to(BASE)}")


if __name__ == "__main__":
    main()
