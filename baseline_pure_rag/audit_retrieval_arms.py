#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
檢索臂消融：換更強的嵌入模型或加上字面檢索，能否補上「表級鑑別」？
==================================================================
第②層（公司+期別已對，但表名不對）是純向量 RAG 失分的主因。本腳本在**同一批
130 題、同一個 30,887 chunk 語料**上比較五條檢索臂，全部不使用任何 metadata 過濾：

  1. dense-small  bge-small-zh-v1.5（512 維，本實驗與線上系統所用）
  2. dense-m3     bge-m3（1024 維，多語大模型）
  3. bm25         jieba 斷詞之字面檢索（離散鍵應該最吃香）
  4. hybrid-small RRF(dense-small, bm25)
  5. hybrid-m3    RRF(dense-m3, bm25)

指標沿用同一組階梯：
  L2 = Top-5 內含正確 (公司,期別,表名)
  L3 = 金標數值真的出現在依 Top-5 組出的 context 內（模型真正看得到）

    python3 audit_retrieval_arms.py --stage corpus|bm25|m3|eval
"""
from __future__ import annotations

import json, pickle, re, sys, time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "system"))
CACHE = ROOT / "_cache"
CACHE.mkdir(exist_ok=True)
K = 5
RRF_K = 60


def load_corpus():
    """匯出全部 chunk（文本＋metadata），只做一次。"""
    p = CACHE / "corpus.pkl"
    if p.exists():
        return pickle.loads(p.read_bytes())
    import chromadb, rag_test_system_v14 as V
    col = chromadb.PersistentClient(path=str(V.DEFAULT_VECTOR_DB)).get_collection(
        V._CHROMA_COLLECTION)
    n = col.count()
    docs, metas = [], []
    off = 0
    while off < n:
        r = col.get(limit=2000, offset=off, include=["documents", "metadatas"])
        docs += r["documents"]; metas += r["metadatas"]
        off += 2000
        print(f"  匯出 {off:,}/{n:,}", end="\r")
    keys = [(m.get("company_code", ""), m.get("quarter", ""), m.get("table_name", ""))
            for m in metas]
    obj = {"docs": docs, "keys": keys}
    p.write_bytes(pickle.dumps(obj))
    print(f"\n語料匯出完成：{len(docs):,} chunks")
    return obj


# ── BM25（scipy 稀疏實作，k1=1.5、b=0.75）────────────────────────
def build_bm25(docs):
    p = CACHE / "bm25.pkl"
    if p.exists():
        return pickle.loads(p.read_bytes())
    import jieba, logging
    from scipy.sparse import csr_matrix
    jieba.setLogLevel(logging.WARNING)
    vocab: dict[str, int] = {}
    indptr, indices, data = [0], [], []
    dl = np.zeros(len(docs), dtype=np.float32)
    for i, d in enumerate(docs):
        toks = [t for t in jieba.lcut(d.lower()) if t.strip()]
        dl[i] = len(toks)
        cnt: dict[int, int] = {}
        for t in toks:
            j = vocab.setdefault(t, len(vocab))
            cnt[j] = cnt.get(j, 0) + 1
        indices.extend(cnt.keys()); data.extend(cnt.values())
        indptr.append(len(indices))
        if i % 2000 == 0:
            print(f"  斷詞 {i:,}/{len(docs):,}", end="\r")
    tf = csr_matrix((np.array(data, dtype=np.float32), np.array(indices),
                     np.array(indptr)), shape=(len(docs), len(vocab)))
    df = np.asarray((tf > 0).sum(axis=0)).ravel()
    N = len(docs)
    idf = np.log(1 + (N - df + 0.5) / (df + 0.5)).astype(np.float32)
    obj = {"tf": tf.tocsc(), "idf": idf, "dl": dl, "avgdl": float(dl.mean()),
           "vocab": vocab}
    p.write_bytes(pickle.dumps(obj))
    print(f"\nBM25 索引完成：詞彙 {len(vocab):,}")
    return obj


def bm25_scores(idx, query, k1=1.5, b=0.75):
    import jieba
    tf, idf, dl, avgdl, vocab = (idx["tf"], idx["idf"], idx["dl"],
                                 idx["avgdl"], idx["vocab"])
    s = np.zeros(tf.shape[0], dtype=np.float32)
    denom_norm = k1 * (1 - b + b * dl / avgdl)
    for t in jieba.lcut(query.lower()):
        j = vocab.get(t)
        if j is None:
            continue
        col = tf.getcol(j).tocoo()
        r, v = col.row, col.data
        s[r] += idf[j] * (v * (k1 + 1)) / (v + denom_norm[r])
    return s


def rrf(*rank_lists, k=RRF_K, top=K):
    """Reciprocal Rank Fusion。"""
    sc: dict[int, float] = {}
    for rl in rank_lists:
        for rank, doc in enumerate(rl, 1):
            sc[doc] = sc.get(doc, 0.0) + 1.0 / (k + rank)
    return [d for d, _ in sorted(sc.items(), key=lambda x: -x[1])[:top]]


if __name__ == "__main__":
    stage = sys.argv[sys.argv.index("--stage") + 1] if "--stage" in sys.argv else "corpus"
    c = load_corpus()
    if stage in ("bm25", "all"):
        t = time.time()
        build_bm25(c["docs"])
        print(f"耗時 {time.time()-t:.0f}s")
