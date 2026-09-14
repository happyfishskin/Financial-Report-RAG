#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""關係事實直查之候選收斂分支稽核。

問題：關係軌在候選不唯一時不套用唯一值閘門（refuse_on_ambiguous 僅作用於數值軌），
而是依 _graphrag_entity_table_lookup() 尾段自行收斂——已給期別取首筆、未給則全量
串接。本腳本回放全部凍結評測中 answer_mode 屬關係軌者，統計各分支的實際使用比例
與 EM 正確率，用以量化「取首筆」這個啟發式承擔了多少成績。

回放方式：直接取結果檔中已記錄的 router_decision 當作 intent，複製函式尾段的分支
判定條件，故不需呼叫 LLM，亦不改動原函式。

    python3 benchmark_relation_branch.py   # → results/relation_branch_stats.json
"""
from __future__ import annotations
import json, glob, re, sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import rag_test_system_v14 as R                                   # noqa: E402

RELATION_MODES = {"relation_lookup", "graph_rag", "graph_rag_l0",
                  "graph_rag_local", "graph_rag_topology"}


def classify(question: str, intent: dict, entity_df: pd.DataFrame) -> str:
    """複製 _graphrag_entity_table_lookup() 尾段之收斂判定，回報所走分支。"""
    m = R._ENTITY_QA_RE.search(question)
    if m:
        q_company, q_entity = m.group(1), m.group(3)
    else:
        q_company = (intent.get("companies") or [""])[0]
        q_entity = intent.get("item_name", "")
    if not q_entity:
        return "no_entity"

    if q_company:
        exact = entity_df["company_name"] == q_company
        co_mask = exact if exact.any() else entity_df["company_name"].str.contains(
            re.escape(q_company), na=False, regex=True)
    else:
        co_mask = pd.Series(True, index=entity_df.index)
    sub = entity_df[co_mask]
    if sub.empty:
        return "empty"

    exact = sub["item_name"] == q_entity
    if exact.any():
        sub = sub[exact]
    else:
        best = R._fuzzy_item_match(
            q_entity, sub["item_name"].dropna().unique().tolist(), cutoff=0.65)
        if best:
            sub = sub[sub["item_name"] == best]
        else:
            cm = sub["item_name"].str.contains(
                re.escape(q_entity[:8]), na=False, regex=True)
            if cm.any():
                sub = sub[cm]

    vals = sub["value_raw"].dropna()
    if vals.empty:
        return "empty"
    if vals.nunique() == 1:
        return "unique"
    quarters = intent.get("quarters") or [None]
    period = quarters[0] if quarters else None
    return "first" if (period and R._PERIOD_LABEL_RE.match(str(period))) else "concat"


def main() -> None:
    _, entity_df, _ = R._prep_facts_for_gen(R._load_facts_df(ROOT))
    stat = defaultdict(lambda: {"n": 0, "em": 0})
    seen: set = set()
    scanned = 0

    for f in sorted(glob.glob(str(ROOT / "results/**/*.json"), recursive=True)):
        try:
            doc = json.loads(Path(f).read_text(encoding="utf-8"))
        except Exception:
            continue
        for row in (doc.get("results") if isinstance(doc, dict) else None) or []:
            if not isinstance(row, dict) or row.get("answer_mode") not in RELATION_MODES:
                continue
            scores = row.get("scores") or {}
            if "exact_match" not in scores:
                continue
            scanned += 1
            question = str(row.get("question") or "")
            intent = row.get("router_decision") or {}
            key = (question, json.dumps(intent, sort_keys=True, ensure_ascii=False)[:120])
            if key in seen:
                continue
            seen.add(key)
            try:
                branch = classify(question, intent, entity_df)
            except Exception:
                branch = "error"
            stat[branch]["n"] += 1
            stat[branch]["em"] += 1 if scores["exact_match"] else 0

    total = sum(v["n"] for v in stat.values())
    out = {
        "scanned_relation_rows": scanned,
        "deduped_samples": total,
        "branches": {
            k: {"n": v["n"], "em_correct": v["em"],
                "em_rate": round(v["em"] / v["n"], 4) if v["n"] else None,
                "share": round(v["n"] / total, 4) if total else None}
            for k, v in sorted(stat.items(), key=lambda x: -x[1]["n"])
        },
        "note": ("first＝候選不唯一且已給期別，取原始列序首筆；concat＝候選不唯一且未給"
                 "期別，全量以「｜」串接；兩者皆不拒答。數值直查軌之 refuse_on_ambiguous "
                 "不作用於本路徑。"),
    }
    dst = ROOT / "results" / "relation_branch_stats.json"
    dst.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"→ {dst.relative_to(ROOT)}")
    print(f"  掃描關係軌結果列 {scanned:,}｜去重樣本 {total}")
    for k, v in out["branches"].items():
        print(f"    {k:<10} n={v['n']:<5} EM={v['em_correct']:<5} "
              f"正確率={v['em_rate']:.1%}  佔比={v['share']:.1%}")


if __name__ == "__main__":
    main()
