#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
三路互斥性稽核：直查軌與圖譜軌能答對的題目是否重疊
======================================================
起因：直查軌與圖譜軌**實作上都是 pandas 查表**，可合理質疑
「這兩路是不是同一路，只是資料放兩個地方」。若兩者能答對的題目大量重疊，
三路設計就有冗餘；若完全互斥，則每一路都不可省。

作法：把圖譜題丟給直查軌、把直查題丟給圖譜 Layer 0，各自量測答對率。
**交叉的兩格才是重點**；對角線僅供參照（本腳本的直查探針未帶
col_hint／table_hint、也未走 cross_company 批次邏輯，會低估直查軌真實表現）。

    python3 audit_track_exclusivity.py
      → results/track_exclusivity.json
"""
from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
V9 = BASE.parent / "version9"
sys.path.insert(0, str(V9))

from finrag.config import Settings                        # noqa: E402
from finrag.corpus import FactsRepository                 # noqa: E402
from finrag.evaluation import Scorer                      # noqa: E402
from finrag.graphrag.layer0 import Layer0Answerer         # noqa: E402
from finrag.graphs import KnowledgeGraphStore             # noqa: E402
from finrag.lookup import DirectLookupEngine              # noqa: E402

OUT = BASE / "results" / "track_exclusivity.json"


def load(pred) -> list[dict]:
    out = []
    for p in (sorted(glob.glob(str(V9 / "questions" / "*.json")))
              + sorted(glob.glob(str(V9 / "questions" / "heldout" / "*.json")))):
        try:
            qs = json.loads(Path(p).read_text(encoding="utf-8"))
        except Exception:                                  # noqa: BLE001
            continue
        if not isinstance(qs, list):
            continue
        for q in qs:
            md = q.get("metadata") or {}
            if q.get("question") and pred(md):
                out.append(q)
    return out


def main() -> int:
    s = Settings.load(V9, quiet=True)
    facts = FactsRepository(s.system, verbose=False)
    dl = DirectLookupEngine(facts, s.companies, s.ontology)
    l0 = Layer0Answerer(KnowledgeGraphStore(s.system, s.companies, verbose=False),
                        s.companies, verbose=False)

    graph_q = load(lambda m: str(m.get("target_route", "")).startswith("graph_rag"))
    direct_q = load(lambda m: str(m.get("target_route", "")).startswith("direct_lookup"))
    print(f"圖譜題 {len(graph_q)}｜直查題 {len(direct_q)}", flush=True)

    def by_direct(q):
        md = q["metadata"]
        item = (md.get("item_name") or md.get("investor_name")
                or md.get("account_item") or "")
        co = md.get("company_name")
        if not (item and co):
            return None
        return dl.lookup_value_or_ratio(co, item, md.get("quarter"))

    def by_graph(q):
        md = q["metadata"]
        return l0.answer(q["question"], {
            "route": "graph_rag", "query_type": "multi_hop_graph_reasoning",
            "companies": [md["company_name"]] if md.get("company_name") else [],
            "quarters": [md["quarter"]] if md.get("quarter") else [],
            "table_name": md.get("table_name"),
            "item_name": md.get("investor_name") or md.get("item_name") or ""})

    def score(ds, fn):
        ok, ids = 0, []
        for q in ds:
            try:
                a = fn(q)
            except Exception:                              # noqa: BLE001
                a = None
            if a is not None and Scorer.score(
                    str(a), str(q.get("expected_answer", "")))["exact_match"]:
                ok += 1
                ids.append(q.get("id"))
        return ok, ids

    gg, _ = score(graph_q, by_graph)
    gd, gd_ids = score(graph_q, by_direct)
    dd, _ = score(direct_q, by_direct)
    dg, dg_ids = score(direct_q, by_graph)

    rec = {
        "title": "三路互斥性稽核：直查軌 vs 圖譜軌",
        "why": "兩軌實作上皆為 pandas 查表，需證明並非冗餘設計。",
        "n_graph_questions": len(graph_q),
        "n_direct_questions": len(direct_q),
        "matrix": {
            "graph_questions": {"answered_by_graph_layer0": gg,
                                "answered_by_direct_track": gd},
            "direct_questions": {"answered_by_direct_track": dd,
                                 "answered_by_graph_layer0": dg},
        },
        "cross_answered_ids": {"graph_q_by_direct": gd_ids[:20],
                               "direct_q_by_graph": dg_ids[:20]},
        "conclusion": ("兩軌能答對的題目集合完全互斥"
                       if gd == 0 and dg == 0 else "兩軌存在重疊，需重新檢視三路設計"),
        "caveat": ("對角線僅供參照：直查探針未帶 col_hint／table_hint、"
                   "亦未走 cross_company 批次邏輯，低估直查軌真實表現。"
                   "本稽核的結論只依賴交叉的兩格。"),
    }
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")

    print(f"\n{'':24}{'圖譜題 ' + str(len(graph_q)):>18}{'直查題 ' + str(len(direct_q)):>18}")
    print(f"{'直查軌能答對':<22}"
          f"{f'{gd}/{len(graph_q)} ({gd/len(graph_q):.1%})':>18}"
          f"{f'{dd}/{len(direct_q)} ({dd/len(direct_q):.1%})':>18}")
    print(f"{'圖譜 Layer 0 能答對':<20}"
          f"{f'{gg}/{len(graph_q)} ({gg/len(graph_q):.1%})':>18}"
          f"{f'{dg}/{len(direct_q)} ({dg/len(direct_q):.1%})':>18}")
    print(f"\n{rec['conclusion']}\n→ {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
