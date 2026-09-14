#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
檢索端稽核：低分到底是「向量庫沒有這筆資料」還是「純語意排序排不上來」？
========================================================================
對主要評測的 130 題數值題，逐題檢查三件事：

  A. 覆蓋率  —— 金標來源 (company_code, quarter, table_name) 在 collection 裡
                「存在幾個 chunk」。0 個 = 向量庫缺料（資料問題）。
  B. 排名    —— 全庫語意搜尋下，金標 chunk 第一次出現在第幾名（掃到 top-200）。
                存在但名次 >5 = 純 RAG 排序能力問題，不是資料問題。
  C. 過濾後  —— 加上 company_code（＋quarter）硬過濾後，金標排第幾名。
                若大幅前移，證明庫是好的，失分來自「沒有過濾」這個實驗設定本身。

本腳本不呼叫 LLM，只做檢索，故不影響任何已凍結結果。
"""
from __future__ import annotations
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "system"))
import rag_test_system_v14 as V
import importlib.util

spec = importlib.util.spec_from_file_location("b", ROOT / "benchmark_pure_rag_27b.py")
B = importlib.util.module_from_spec(spec); spec.loader.exec_module(B)

DEEP_K = 200


def main() -> int:
    import chromadb
    items = B.build_suite("main")
    embedder = V._BGEEmbedder(V.DEFAULT_EMBED_MODEL, device="cpu")
    col = chromadb.PersistentClient(path=str(V.DEFAULT_VECTOR_DB)).get_collection(
        V._CHROMA_COLLECTION)
    print(f"題目 {len(items)}｜collection {col.count():,} chunks\n")

    rows = []
    for i, (_lab, it) in enumerate(items, 1):
        golds = B.gold_sources(it)
        if not golds:
            continue
        q = it["question"]
        emb = embedder.embed_query(q)

        # A. 覆蓋率：金標 (公司,期別,表) 在庫裡有幾個 chunk
        cover = []
        for code, qtr, tbl in golds:
            got = col.get(where={"$and": [{"company_code": {"$eq": code}},
                                          {"quarter": {"$eq": qtr}},
                                          {"table_name": {"$eq": tbl}}]},
                          include=[], limit=100)
            cover.append(len(got["ids"]))

        # B. 全庫深檢索下金標的名次
        res = col.query(query_embeddings=[emb], n_results=DEEP_K,
                        include=["metadatas"])
        seq = [(m.get("company_code",""), m.get("quarter",""), m.get("table_name",""))
               for m in res["metadatas"][0]]
        ranks_full = []
        for g in golds:
            ranks_full.append(seq.index(g) + 1 if g in seq else None)

        # C. 加公司(+期別)硬過濾後的名次
        ranks_filt = []
        for code, qtr, tbl in golds:
            r2 = col.query(query_embeddings=[emb], n_results=50,
                           where={"$and": [{"company_code": {"$eq": code}},
                                           {"quarter": {"$eq": qtr}}]},
                           include=["metadatas"])
            s2 = [m.get("table_name", "") for m in r2["metadatas"][0]]
            ranks_filt.append(s2.index(tbl) + 1 if tbl in s2 else None)

        rows.append({"id": it.get("id"), "n_gold": len(golds), "coverage": cover,
                     "rank_full": ranks_full, "rank_filtered": ranks_filt})
        if i % 20 == 0:
            print(f"  ...{i}/{len(items)}")

    # ── 匯總 ────────────────────────────────────────────────
    all_gold = [(c, rf, rl) for r in rows
                for c, rf, rl in zip(r["coverage"], r["rank_full"], r["rank_filtered"])]
    n = len(all_gold)
    missing = [x for x in all_gold if x[0] == 0]
    present = [x for x in all_gold if x[0] > 0]

    def hit_at(k, idx):
        return sum(1 for x in present if x[idx] is not None and x[idx] <= k)

    print(f"\n{'='*66}")
    print(f"金標來源總數（含批次題的多個來源）：{n}")
    print(f"A. 向量庫覆蓋率：存在 {len(present)}/{n} = {len(present)/n:.1%}"
          f"｜缺料 {len(missing)} 個")
    print(f"   （存在者平均 {sum(x[0] for x in present)/len(present):.1f} 個 chunk）")
    print(f"\nB. 全庫語意搜尋（無過濾）金標名次分布 — 分母＝庫裡存在的 {len(present)}")
    for k in (1, 5, 10, 20, 50, 100, 200):
        print(f"   Recall@{k:<3} = {hit_at(k,1)/len(present):6.1%}  ({hit_at(k,1)}/{len(present)})")
    beyond = sum(1 for x in present if x[1] is None)
    print(f"   連 top-{DEEP_K} 都排不進：{beyond}/{len(present)} = {beyond/len(present):.1%}")

    print(f"\nC. 加 company+quarter 硬過濾後金標名次")
    for k in (1, 5, 10):
        print(f"   Recall@{k:<3} = {hit_at(k,2)/len(present):6.1%}  ({hit_at(k,2)}/{len(present)})")

    Path("results/retrieval_ceiling_audit.json").write_text(
        json.dumps({"deep_k": DEEP_K, "n_gold": n,
                    "coverage_present": len(present), "coverage_missing": len(missing),
                    "recall_full": {k: hit_at(k,1)/len(present) for k in (1,5,10,20,50,100,200)},
                    "recall_filtered": {k: hit_at(k,2)/len(present) for k in (1,5,10)},
                    "rows": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n輸出：results/retrieval_ceiling_audit.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
