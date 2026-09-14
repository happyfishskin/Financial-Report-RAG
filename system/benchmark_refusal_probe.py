#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
拒答行為之針對性實測（讓「拒答率」成為可解讀的實驗指標）
========================================================
§4.4.1 量到軌道一的拒答率與候選歧義率**皆為 0.0%**。0% 本身不構成證據——
它同樣可以是「拒答路徑根本沒接上」。本腳本以兩道**刻意設計**的題目直接觸發
唯一性判定的兩種失敗成因，證明該路徑會依成因給出可區分的回覆：

  1. 查無資料（候選集合為空）
     → 期望回覆「找不到符合條件的資料」，trace.decision = no_item／no_candidate
  2. 多筆候選（候選集合不唯一）
     → 期望回覆「條件不足，請指定交易對象／欄位」，trace.decision = ambiguous

兩題皆以真實資料構造，非人工捏造字串：查無資料題取一個確實不存在於 211,263
筆事實庫中的科目；多筆候選題取一組實際存在、且在（公司, 期別, 科目, 欄位）
四鍵齊備下仍有數十個相異值的組合。

另附一題**對照組**（條件補足後應正常作答），用以證明拒答不是「這類題一律答不出來」，
而是條件不足才拒答——補上鑑別條件即可得到唯一值。

    python3 benchmark_refusal_probe.py [--out results/refusal_probe]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import rag_test_system_v14 as V

ROOT = Path(__file__).resolve().parent


def arg(flag: str, default):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default


def probe_relation(question: str, intent: dict, company_map) -> dict:
    """走軌道一的關係事實直查（Fix 16 三元主鍵）。"""
    ans = V._gkg_pattern_direct_answer(question, intent, company_map)
    return {"answered": ans is not None,
            "reply": ans if ans is not None else "找不到符合條件的資料",
            "refusal_reason": None if ans is not None else "no_candidate",
            "traces": [], "n_candidates": 1 if ans else 0,
            "n_distinct_values": 1 if ans else 0}


def probe(intent: dict, facts, deduped) -> dict:
    """走軌道一的數值直查，回傳答案與唯一性判定的過程。"""
    traces: list = []
    ans = V._execute_direct_lookup_batch(intent, facts, deduped, traces=traces)
    decisions = [t.get("decision") for t in traces if t.get("decision")]
    reason = ("ambiguous" if "ambiguous" in decisions
              else (decisions[0] if decisions else None))
    reply = ans if ans is not None else V._REFUSAL_MESSAGES.get(
        str(reason or ""), "找不到相關資料")
    return {
        "answered": ans is not None,
        "reply": reply,
        "refusal_reason": reason,
        "traces": traces,
        "n_candidates": max((t.get("n_rows", 0) for t in traces), default=0),
        "n_distinct_values": max((t.get("n_unique", 0) for t in traces), default=0),
    }


def main() -> int:
    out_stem = Path(arg("--out", ROOT / "results" / "refusal_probe"))
    facts = V._load_facts_df(V.REPORTS_ROOT)
    _std, _ent, deduped = V._prep_facts_for_gen(facts)
    print(f"事實庫 {len(facts):,} 筆｜去重視圖 {len(deduped):,} 筆\n")

    cases = [
        {
            "key": "no_data",
            "label": "查無資料（候選集合為空）",
            "question": "請查詢【台灣積體電路製造】在【114Q2】的"
                        "【碳權交易收入】是多少？",
            "design": "科目「碳權交易收入」不存在於事實庫；公司與期別皆合法，"
                      "故失敗必然發生在科目過濾而非公司或期別。",
            "expected_reply": "找不到符合條件的資料",
            "expected_reason": ("no_item", "no_candidate"),
            "intent": {"route": "direct_lookup", "query_type": "single",
                       "companies": ["台灣積體電路製造"], "quarters": ["114Q2"],
                       "item_name": "碳權交易收入"},
        },
        {
            "key": "ambiguous",
            "label": "多筆候選（候選集合不唯一）",
            "question": "請查詢【聯發科技】在【113Q1】的【研究發展費用】（金額）"
                        "是多少？",
            "design": "該期「研究發展費用」出現在母子公司間重要交易往來表，"
                      "28 個不同交易對象各一筆；四鍵（公司, 期別, 科目, 欄位）"
                      "齊備後仍有數十個相異值，題目缺的是交易對象。",
            "expected_reply": "條件不足，請指定交易對象／欄位",
            "expected_reason": ("ambiguous",),
            "branch": "numeric",
            "intent": {"route": "direct_lookup", "query_type": "single",
                       "companies": ["聯發科技"], "quarters": ["113Q1"],
                       "item_name": "研究發展費用", "_col_hint": "金額"},
        },
        {
            "key": "control_resolved",
            "label": "對照組：補上交易對象後正常作答",
            "question": "根據關係人交易圖譜，【聯發科技】在【113Q1】，"
                        "【聯發科技(股)公司】與【MediaTek Bangalore Private "
                        "Limited】之間的【研究發展費用】交易金額是多少？",
            "design": "與前一題同公司、同期別、同科目，只補上交易對象。"
                      "Fix 16 之三元主鍵（交易人×交易對象×科目）使候選收斂為唯一，"
                      "證明拒答來自條件不足，而非系統答不出這類題目。",
            "expected_reply": None,
            "expected_answer": "658,319",
            "expected_reason": (None,),
            "branch": "relation",
            "intent": {"route": "direct_lookup", "query_type": "entity_lookup",
                       "_relation_query": True, "companies": ["聯發科技"],
                       "quarters": ["113Q1"], "table_name": None,
                       "item_name": "MediaTek Bangalore Private Limited"},
        },
    ]

    rows, ok_all = [], True
    company_map = V._build_company_map(V.REPORTS_ROOT)
    V._load_all_compiled_graphs()
    for c in cases:
        r = (probe_relation(c["question"], c["intent"], company_map)
             if c.get("branch") == "relation"
             else probe(c["intent"], facts, deduped))
        expect_answer = c["expected_reply"] is None
        ok = ((r["answered"] == expect_answer)
              and (expect_answer or r["reply"] == c["expected_reply"])
              and (r["refusal_reason"] in c["expected_reason"]))
        if expect_answer and c.get("expected_answer"):
            ok &= (r["reply"] == c["expected_answer"])
        ok_all &= ok
        rows.append({**{k: c[k] for k in
                        ("key", "label", "question", "design", "expected_reply")},
                     "branch": c.get("branch", "numeric"),
                     **r, "pass": ok})
        print(f"[{'✓' if ok else '✗'}] {c['label']}")
        print(f"    問句     : {c['question']}")
        print(f"    系統回覆 : {r['reply'][:46]}")
        print(f"    判定成因 : {r['refusal_reason']}"
              f"（候選 {r['n_candidates']} 列／相異值 {r['n_distinct_values']}）\n")

    payload = {
        "title": "拒答行為之針對性實測",
        "why": "受控消融量到的拒答率與候選歧義率皆為 0.0%；0% 需要證明"
               "「路徑存在且會依成因回覆」，否則無法解讀。",
        "refusal_messages": V._REFUSAL_MESSAGES,
        "refuse_on_ambiguous": V._REFUSE_ON_AMBIGUOUS,
        "cases": rows,
        "all_pass": ok_all,
    }
    Path(f"{out_stem}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    md = ["# 拒答行為之針對性實測\n",
          "| 情境 | 題目設計 | 系統回覆 | 判定成因 | 候選相異值 |",
          "|---|---|---|---|---:|"]
    for r in rows:
        md.append(f"| {r['label']} | {r['design'][:34]}… | {r['reply'][:24]} | "
                  f"`{r['refusal_reason']}` | {r['n_distinct_values']} |")
    Path(f"{out_stem}.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"輸出：{out_stem}.json / .md")
    print("全部通過" if ok_all else "✗ 有案例未達預期")
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
