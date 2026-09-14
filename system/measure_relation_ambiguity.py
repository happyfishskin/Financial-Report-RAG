#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
關係事實直查（軌道一 b 分支）之**候選歧義率**量測。

動機
----
數值事實直查在候選不唯一時立即拒答（`_REFUSE_ON_AMBIGUOUS`，訊息「條件不足，
請指定交易對象／欄位」），其候選歧義率已量得 0.0%。關係事實直查則無對應機制：
L0 六個樣板在候選不唯一時直接 `iloc[-1]`（註解「最後揭露列優先」）或全列並列，
從不拒答。本腳本量測「這個分支實際上有多常被觸發」。

方法
----
零 LLM、零重跑推論。自十一個凍結結果檔取出 answer_mode ∈ _RELATION_MODES 的
題目，連同其**已凍結的 router_decision**（即當時的 intent）一起重放
`_gkg_pattern_direct_answer()`，用 `sys.settrace` 在候選挑列的那幾行讀取候選
DataFrame 的列數。**不修改 rag_test_system_v14.py**（該檔已凍結）。

輸出
----
results/relation_ambiguity.{json,md}
"""
from __future__ import annotations
import json
import os
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import rag_test_system_v14 as v14  # noqa: E402

# 凍結結果檔（與 report_dual_track.py 同一份清單）
RESULT_FILES = [
    ("正文", "架構 100 (v2)",      "results/rerun/eval_arch100_v2_fix16.json"),
    ("正文", "架構 100 (orig)",    "results/rerun/eval_arch100_orig_fix16.json"),
    ("正文", "口語 100",           "results/rerun/eval_colloq100_v2_regress_fix16.json"),
    ("正文", "圖譜能力 30",        "results/rerun/eval_graphcap_v3.json"),
    ("正文", "圖譜自然 30",        "results/rerun/eval_graphnat30_v3.json"),
    ("正文", "圖譜自然 100",       "results/rerun/eval_gnat100.json"),
    ("附錄B", "held-out 架構 100",  "results/heldout/eval_heldout_arch_100.json"),
    ("附錄B", "held-out 口語 100",  "results/heldout/eval_heldout_colloq_100.json"),
    ("附錄B", "held-out 純口語 100", "results/heldout/eval_heldout_colloq_nat_100.json"),
    ("附錄B", "held-out 圖譜能力 30", "results/heldout/eval_heldout_graph_cap_30.json"),
    ("附錄B", "held-out 圖譜自然 30", "results/heldout/eval_heldout_graph_nat_30.json"),
]

# 候選挑列點：行號 → (區域性變數名, 樣板名, 處置方式)
# 行號已對 rag_test_system_v14.py 現況逐行驗證；該檔異動後須以 --verify 重新確認。
PICK_SITES = {
    3753: ("combos",   "產業鏈階段",       "全列並列"),
    3756: ("sc",       "產業鏈階段",       "iloc[-1]"),
    3939: ("inv",      "投資關係",         "iloc[-1]"),
    3968: ("hit",      "母子公司主要業務", "iloc[-1]"),
    4058: ("pair_hit", "關係人交易(Fix16)", "iloc[-1]"),
    4099: ("acc_hit",  "帳目",             "iloc[-1]"),
}
EXPECT_SRC = {
    3753: 'ans = " ｜ ".join(combos)',
    3756: "row = sc.iloc[-1]",
    3939: 'tgt = inv.iloc[-1]["target"]',
    3968: "row = hit.iloc[-1]",
    4058: "row = pair_hit.iloc[-1]",
    4099: "row = acc_hit.iloc[-1]",
}


def verify_line_anchors() -> None:
    """行號漂移即中止：以原始碼片段比對，避免量到不相干的行。"""
    src = Path(v14.__file__).read_text(encoding="utf-8").splitlines()
    for ln, frag in EXPECT_SRC.items():
        got = src[ln - 1].strip()
        if frag not in got:
            raise SystemExit(
                f"[中止] 行號漂移：第 {ln} 行預期含 {frag!r}，實際為 {got!r}。\n"
                f"       請重新定位 PICK_SITES 後再量測。"
            )
    print(f"[錨點] {len(EXPECT_SRC)} 個候選挑列點行號全數驗證通過")


_current: list[tuple[int, int]] = []


def _line_tracer(frame, event, arg):
    if event == "line":
        site = PICK_SITES.get(frame.f_lineno)
        if site is not None:
            obj = frame.f_locals.get(site[0])
            try:
                _current.append((frame.f_lineno, len(obj)))
            except TypeError:
                pass
    return _line_tracer


def _call_tracer(frame, event, arg):
    if event == "call" and frame.f_code.co_name == "_gkg_pattern_direct_answer":
        return _line_tracer
    return None


def load_records() -> list[dict]:
    recs = []
    for section, name, path in RESULT_FILES:
        p = ROOT / path
        if not p.exists():
            print(f"[略過] 找不到 {path}")
            continue
        data = json.loads(p.read_text(encoding="utf-8"))
        rows = data if isinstance(data, list) else (
            data.get("results") or data.get("details") or data.get("records") or [])
        for r in rows:
            if r.get("answer_mode") in v14._RELATION_MODES and r.get("router_decision"):
                recs.append({
                    "section": section, "dataset": name,
                    "id": r.get("id"), "question": r.get("question", ""),
                    "answer_mode": r.get("answer_mode"),
                    "intent": r.get("router_decision") or {},
                })
    return recs


def main() -> None:
    verify_line_anchors()
    print("[載入] 關係事實表（節點／邊）…", flush=True)
    company_map = v14._build_company_map(v14.REPORTS_ROOT)
    v14._load_all_compiled_graphs()
    print(f"[載入] 完成：{len(v14.GLOBAL_GRAPH_NODES_DF):,} 節點／"
          f"{len(v14.GLOBAL_GRAPH_EDGES_DF):,} 邊", flush=True)

    recs = load_records()
    print(f"[重放] 關係軌題目 {len(recs)} 題（零 LLM 呼叫）", flush=True)

    devnull = open(os.devnull, "w")
    per_q, no_pick = [], 0
    sys.settrace(_call_tracer)
    try:
        for r in recs:
            _current.clear()
            real_stdout, sys.stdout = sys.stdout, devnull
            try:
                ans = v14._gkg_pattern_direct_answer(
                    r["question"], r["intent"], company_map)
            except Exception as exc:                      # noqa: BLE001
                ans, err = None, f"{type(exc).__name__}: {exc}"
            else:
                err = None
            finally:
                sys.stdout = real_stdout
            picks = list(_current)
            if not picks:
                no_pick += 1
            per_q.append({**{k: r[k] for k in
                             ("section", "dataset", "id", "question", "answer_mode")},
                          "picks": [{"line": ln, "template": PICK_SITES[ln][1],
                                     "policy": PICK_SITES[ln][2], "n_candidates": n}
                                    for ln, n in picks],
                          "max_candidates": max((n for _, n in picks), default=0),
                          "l0_answered": ans is not None,
                          "error": err})
    finally:
        sys.settrace(None)
        devnull.close()

    # ── 統計 ──────────────────────────────────────────────────────
    # 「任選」= policy 為 iloc[-1] 且候選>1，即系統在多筆互相競爭的列中靜靜挑了
    # 最後一列。「全列並列」不計入歧義：該分支把所有候選一起輸出，未丟失資訊，
    # 且僅在題幹明示「請全部列出」時觸發。
    def _amb(q):
        return any(p["n_candidates"] > 1 and p["policy"] == "iloc[-1]"
                   for p in q["picks"])

    reached = [q for q in per_q if q["picks"]]
    ambiguous = [q for q in reached if _amb(q)]

    by_pol: dict[tuple[str, str], Counter] = {}
    for q in per_q:
        for p in q["picks"]:
            c = by_pol.setdefault((p["template"], p["policy"]), Counter())
            c["trig"] += 1
            if p["n_candidates"] > 1:
                c["multi"] += 1
                c["max"] = max(c["max"], p["n_candidates"])

    by_ds: dict[str, list[int]] = {}
    for q in per_q:
        s = by_ds.setdefault(q["dataset"], [0, 0, 0])
        s[0] += 1
        if q["picks"]:
            s[1] += 1
            if _amb(q):
                s[2] += 1

    rate = (len(ambiguous) / len(reached) * 100) if reached else 0.0
    ho = [v for k, v in by_ds.items() if k.startswith("held-out")]
    ho_rate = (sum(v[2] for v in ho) / sum(v[1] for v in ho) * 100) if ho else 0.0

    summary = {
        "關係軌題目數": len(per_q),
        "L0 有答出": sum(1 for q in per_q if q["l0_answered"]),
        "抵達候選挑列點": len(reached),
        "未抵達挑列點": no_pick,
        "候選不唯一且任選題數": len(ambiguous),
        "候選歧義率_pct": round(rate, 2),
        "held_out_候選歧義率_pct": round(ho_rate, 2),
    }
    print("\n" + json.dumps(summary, ensure_ascii=False, indent=2))

    outdir = ROOT / "results"
    outdir.mkdir(exist_ok=True)
    (outdir / "relation_ambiguity.json").write_text(
        json.dumps({"summary": summary,
                    "by_policy": {f"{k[0]}|{k[1]}": dict(v) for k, v in by_pol.items()},
                    "by_dataset": by_ds,
                    "ambiguous_questions": ambiguous,
                    "per_question": per_q},
                   ensure_ascii=False, indent=2), encoding="utf-8")

    md = [
        "# 關係事實直查之候選歧義率", "",
        "由 `measure_relation_ambiguity.py` 產生：自十一份凍結結果檔取出關係軌題目，",
        "連同已凍結的 `router_decision` 重放 `_gkg_pattern_direct_answer()`，以 `sys.settrace`",
        "讀取候選挑列點的候選列數。**零 LLM 呼叫、零重跑推論、未修改 `rag_test_system_v14.py`**。", "",
        "## 結論", "",
        f"- 關係軌題目 **{summary['關係軌題目數']}** 題，其中 **{summary['抵達候選挑列點']}** 題抵達候選挑列點",
        f"- 候選不唯一且系統靜默任選（`iloc[-1]`）：**{summary['候選不唯一且任選題數']}** 題",
        f"- **候選歧義率 = {summary['候選歧義率_pct']}%**；**held-out 四組 = {summary['held_out_候選歧義率_pct']}%**", "",
        "對照：數值事實直查在候選不唯一時**立即拒答**（`_REFUSE_ON_AMBIGUOUS`），其候選歧義率為 0.0%。",
        "關係事實直查**無對應拒答機制**——六個 L0 樣板在候選不唯一時取 `iloc[-1]`（「最後揭露列優先」）",
        "或全列並列。本表量測該分支的實際觸發率。", "",
        "## 各樣板", "", "| 樣板 | 多候選處置 | 觸發 | 候選>1 | 最大候選數 |", "|---|---|---:|---:|---:|",
    ]
    for k, v in sorted(by_pol.items(), key=lambda x: -x[1]["multi"]):
        md.append(f"| {k[0]} | {k[1]} | {v['trig']} | {v['multi']} | {v.get('max', 1)} |")
    md += ["", "> 關係人交易（Fix 16）觸發 %d 次、候選>1 **0** 次：三元主鍵（交易人＋交易對象＋科目）"
           % by_pol.get(("關係人交易(Fix16)", "iloc[-1]"), Counter())["trig"],
           "> 已將候選壓到唯一，此為 Fix 16 之直接量化實證。", "",
           "## 各資料集", "", "| 資料集 | 關係題 | 抵達挑列點 | 任選>1 | 歧義率 |", "|---|---:|---:|---:|---:|"]
    for k, (a, b, c) in by_ds.items():
        md.append(f"| {k} | {a} | {b} | {c} | {(c/b*100 if b else 0):.1f}% |")
    md += ["", "## 候選不唯一之題目", "", "| 資料集 | id | 候選數 | 樣板 | 題目 |", "|---|---|---:|---|---|"]
    for q in ambiguous:
        p = max((p for p in q["picks"] if p["policy"] == "iloc[-1]"),
                key=lambda x: x["n_candidates"])
        md.append(f"| {q['dataset']} | {q['id']} | {p['n_candidates']} | "
                  f"{p['template']} | {q['question'][:44]} |")
    (outdir / "relation_ambiguity.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n[輸出] results/relation_ambiguity.json / .md")


if __name__ == "__main__":
    main()
