#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""五條檢索臂在同一批 130 題上的第②③層命中率（無任何 metadata 過濾）。"""
from __future__ import annotations
import importlib.util, json, pickle, re, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "system"))
CACHE = ROOT / "_cache"
K = 5

sys.argv = ['x']
spec = importlib.util.spec_from_file_location('b', ROOT / 'benchmark_pure_rag_27b.py')
B = importlib.util.module_from_spec(spec); spec.loader.exec_module(B)
A = importlib.util.spec_from_file_location('a', ROOT / 'audit_retrieval_arms.py')
AR = importlib.util.module_from_spec(A); A.loader.exec_module(AR)

norm = lambda s: re.sub(r'[（）()\s,，]', '', str(s))
corpus = pickle.loads((CACHE / 'corpus.pkl').read_bytes())
docs, keys = corpus['docs'], corpus['keys']
items = [(l, it) for l, it in B.build_suite('main') if B.gold_sources(it)]
print(f'題目 {len(items)}｜語料 {len(docs):,}')
# 完整文本 → 語料索引。不可用前綴當 key：同一張表的相鄰 chunk 共用
# 「# 代號_公司｜期別｜表名」標頭，前一兩百字完全相同，前綴會反查到錯的切塊。
DOC2IDX = {}
for _i, _d in enumerate(docs):
    DOC2IDX.setdefault(_d, _i)

from sentence_transformers import SentenceTransformer
import chromadb, rag_test_system_v14 as V

# 稠密臂：bge-small 直接用既有 Chroma；bge-m3 用自建矩陣
col = chromadb.PersistentClient(path=str(V.DEFAULT_VECTOR_DB)).get_collection(
    V._CHROMA_COLLECTION)
small = V._BGEEmbedder(V.DEFAULT_EMBED_MODEL, device='cpu')
# chroma 的 id 順序與 corpus 匯出順序一致（同一次 get 全掃），故可用索引對齊
bm25 = AR.build_bm25(docs)
emb_m3 = np.load(CACHE / 'emb_m3.npy') if (CACHE / 'emb_m3.npy').exists() else None
m3 = None
if emb_m3 is not None:
    m3 = SentenceTransformer('BAAI/bge-m3', device='cuda'); m3.half(); m3.max_seq_length = 512
    print(f'bge-m3 矩陣 {emb_m3.shape}')

def top_small(q):
    e = small.embed_query(q)
    r = col.query(query_embeddings=[e], n_results=K,
                  include=["documents", "metadatas"])
    return list(zip(r['documents'][0], r['metadatas'][0]))

def idx_to_hits(ids):
    return [(docs[i], {'company_code': keys[i][0], 'quarter': keys[i][1],
                       'table_name': keys[i][2], 'company_name': '', 'source': ''})
            for i in ids]

def rank_bm25(q, top=K):
    s = AR.bm25_scores(bm25, q)
    return list(np.argsort(-s)[:top])

def rank_m3(q, top=K):
    v = np.asarray(m3.encode([q], normalize_embeddings=True), dtype=np.float32)[0]
    return list(np.argsort(-(emb_m3 @ v))[:top])

def score(hits, it):
    golds = B.gold_sources(it)
    top = [(m['company_code'], m['quarter'], m['table_name']) for _, m in hits]
    L2 = all(any(t[0] == g[0] and t[1] == g[1] and g[2][:4] in t[2] for t in top)
             for g in golds)
    hh = [{'content': d, 'company_code': m['company_code'],
           'company_name': '', 'quarter': m['quarter'],
           'table_name': m['table_name'], 'source': '', 'score': 0} for d, m in hits]
    ctx, _ = B.format_context(hh); c = norm(ctx)
    gold = str(it.get('expected_answer', ''))
    vals = [norm(re.sub(r'^[^:：]*[:：]', '', p)) for p in re.split(r'[｜|]', gold)]
    L3 = all(v and v in c for v in vals)
    return L2, L3

arms = {'1 dense bge-small (現行)': [], '2 dense bge-m3': [], '3 BM25 字面檢索': [],
        '4 hybrid small+BM25': [], '5 hybrid m3+BM25': []}
for n, (lab, it) in enumerate(items, 1):
    q = it['question']
    s_hits = top_small(q)
    b_ids = rank_bm25(q, 50)
    arms['1 dense bge-small (現行)'].append(score(s_hits, it))
    arms['3 BM25 字面檢索'].append(score(idx_to_hits(b_ids[:K]), it))
    # RRF 需要 small 命中的語料索引：用預建表反查
    s_ids = [DOC2IDX[d] for d, _ in s_hits if d in DOC2IDX]
    arms['4 hybrid small+BM25'].append(
        score(idx_to_hits(AR.rrf(s_ids, b_ids)), it))
    if m3 is not None:
        m_ids = rank_m3(q, 50)
        arms['2 dense bge-m3'].append(score(idx_to_hits(m_ids[:K]), it))
        arms['5 hybrid m3+BM25'].append(
            score(idx_to_hits(AR.rrf(m_ids, b_ids)), it))
    if n % 20 == 0:
        print(f'  ...{n}/{len(items)}')

print(f'\n{"檢索臂":<26}{"L2 表名對@5":>14}{"L3 答案在prompt":>18}')
out = {}
for k, v in arms.items():
    if not v: continue
    n = len(v)
    l2 = sum(1 for a, _ in v if a) / n; l3 = sum(1 for _, b in v if b) / n
    out[k] = {'n': n, 'L2': round(l2, 4), 'L3': round(l3, 4)}
    print(f'{k:<26}{l2:>13.1%}{l3:>17.1%}')
(ROOT / 'results' / 'retrieval_arms.json').write_text(
    json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
print('\n輸出：results/retrieval_arms.json')
