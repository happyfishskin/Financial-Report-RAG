#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
建立 canonical 資料集 v4（prompt_audit_issues.txt §26 / §27 / §29）
====================================================================
以 `system_architecture_test_questions_100_v2_v3.json` 為基礎，套用 P2 修正：

1. **arch_test_084 / 085 題型更正**（§27 / N31）
   兩題來源實為「轉投資大陸地區之事業相關資訊」，卻被標成關係人交易題。
   改為 `mainland_investment_graph` / `graph_rag_mainland_investment`，
   題幹改成「根據大陸投資圖譜」，金標只保留問題真正要求的被投資公司與指定金額，
   不再傾印整列欄位。

2. **輸出 canonical 資料集**（§26）
   舊 v2 不覆蓋、保留作歷史重現用途；新檔為
   `system_architecture_test_questions_100_v4.json`，供 benchmark 與前端統一引用。

3. **拆分圖譜題為兩組**（§29）
   · `graph_capability_explicit.json` — 保留「根據○○圖譜」，固定走圖譜路徑，
     測圖譜資料與拓撲查詢的答案正確率（不受 Router 波動污染）。
   · `graph_routing_natural.json`     — 移除來源提示，改為自然問法，
     測 Router 能否自行選對圖譜路徑。

用法：python3 build_canonical_v4.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
QDIR = ROOT / "questions"
SRC = QDIR / "system_architecture_test_questions_100_v2_v3.json"
OUT_V4 = QDIR / "system_architecture_test_questions_100_v4.json"
OUT_CAP = QDIR / "graph_capability_explicit.json"
OUT_NAT = QDIR / "graph_routing_natural.json"

# §27 指定之更正內容
_MAINLAND_FIX = {
    "arch_test_084": {
        "question": ("根據大陸投資圖譜，【群聯電子】在【113Q2】投資之大陸事業中，"
                     "主要業務為【電子產品軟硬件的研發、生產、銷售、技術服務等相關業務"
                     "及一般投資業】的被投資公司是哪一家？其本期認列投資損益是多少？"),
        "expected_answer": "合肥芯鵬技術有限公司；本期認列投資損益：( 9,393 )",
        "investee": "合肥芯鵬技術有限公司",
        "profit_recognised": "( 9,393 )",
    },
    "arch_test_085": {
        "question": ("根據大陸投資圖譜，【日月光投資控股】在【114Q2】投資之大陸事業中，"
                     "主要業務為【從事半導體材料製造業務】的被投資公司是哪一家？"
                     "其本期認列投資損益是多少？"),
        "expected_answer": "日月光半導體（上海）有限公司；本期認列投資損益：55,724",
        "investee": "日月光半導體（上海）有限公司",
        "profit_recognised": "55,724",
    },
}

# 圖譜題型 → 自然問法改寫（§29：移除「根據○○圖譜」等來源提示）
_SOURCE_HINT_RE = re.compile(r"^根據[^，]{2,12}圖譜，")
_GRAPH_TYPES = ("investment_graph", "related_party_transaction_graph",
                "supply_chain_graph", "risk_event_graph",
                "mainland_investment_graph")


def _to_natural(question: str) -> str:
    """把「根據○○圖譜，【A】在【B】…」改寫為使用者自然問法。"""
    q = _SOURCE_HINT_RE.sub("", question).strip()
    q = q.replace("【", "").replace("】", "")
    return q


def main() -> None:
    data = json.loads(SRC.read_text(encoding="utf-8"))

    n_fixed = 0
    for q in data:
        fix = _MAINLAND_FIX.get(q.get("id"))
        if not fix:
            continue
        md = q.setdefault("metadata", {})
        q["question_type"] = "mainland_investment_graph"
        q["question"] = fix["question"]
        q["expected_answer"] = fix["expected_answer"]
        md["target_route"] = "graph_rag_mainland_investment"
        md["investee_name"] = fix["investee"]
        md["value_attribute"] = "本期認列投資損益"
        md["value_raw"] = fix["profit_recognised"]
        md.pop("account", None)          # 原為「主要業務」，非會計科目
        md["main_business"] = md.pop("party_or_category", "")
        md["fix_rule"] = "P2_mainland_investment_reclassified"
        n_fixed += 1

    OUT_V4.write_text(json.dumps(data, ensure_ascii=False, indent=1),
                      encoding="utf-8")
    print(f"canonical v4：{OUT_V4.name}（{len(data)} 題，更正 {n_fixed} 題）")

    graph_qs = [q for q in data if q.get("question_type") in _GRAPH_TYPES]

    cap = []
    for q in graph_qs:
        c = json.loads(json.dumps(q, ensure_ascii=False))
        c["id"] = c["id"].replace("arch_test_", "graph_cap_")
        c.setdefault("metadata", {})["force_route"] = "graph_rag"
        c["metadata"]["test_purpose"] = "graph_capability"
        cap.append(c)
    OUT_CAP.write_text(json.dumps(cap, ensure_ascii=False, indent=1),
                       encoding="utf-8")

    nat = []
    for q in graph_qs:
        n = json.loads(json.dumps(q, ensure_ascii=False))
        n["id"] = n["id"].replace("arch_test_", "graph_nat_")
        n["question"] = _to_natural(n["question"])
        n.setdefault("metadata", {})["test_purpose"] = "graph_routing"
        n["metadata"]["expected_route"] = "graph_rag"
        nat.append(n)
    OUT_NAT.write_text(json.dumps(nat, ensure_ascii=False, indent=1),
                       encoding="utf-8")

    print(f"圖譜能力題：{OUT_CAP.name}（{len(cap)} 題，固定走圖譜）")
    print(f"自然路由題：{OUT_NAT.name}（{len(nat)} 題，移除來源提示）")
    if nat:
        print(f"  自然問法範例：{nat[0]['question'][:70]}")


if __name__ == "__main__":
    main()
