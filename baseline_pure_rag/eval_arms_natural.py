#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BM25 的優勢是不是題目措辭給的？——自然口語題對照
================================================
主要評測 130 題的問法帶【公司】【期別】【科目】括號標記，字串與來源逐字相同，
BM25 天然吃香。本腳本改用**自然口語題**（heldout/heldout2 之 colloq_nat，
無括號、口語措辭）重跑同樣的檢索臂，檢驗 BM25 的領先是否為措辭假象。
"""
from __future__ import annotations
import importlib.util, json, pickle, re, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "system"))
CACHE = ROOT / "_cache"; K = 5
sys.argv = ['x']
spec = importlib.util.spec_from_file_location('b', ROOT / 'benchmark_pure_rag_27b.py')
B = importlib.util.module_from_spec(spec); spec.loader.exec_module(B)
A = importlib.util.spec_from_file_location('a', ROOT / 'audit_retrieval_arms.py')
AR = importlib.util.module_from_spec(A); A.loader.exec_module(AR)
import rag_test_system_v14 as V, chromadb

norm = lambda s: re.sub(r'[（）()\s,，]', '', str(s))
c = pickle.loads((CACHE / 'corpus.pkl').read_bytes())
docs, keys = c['docs'], c['keys']
DOC2IDX = {}
for i, d in enumerate(docs):
    DOC2IDX.setdefault(d, i)
bm25 = AR.build_bm25(docs)
small = V._BGEEmbedder(V.DEFAULT_EMBED_MODEL, device='cpu')
from sentence_transformers import SentenceTransformer
emb_m3 = np.load(CACHE / 'emb_m3.npy')
m3 = SentenceTransformer('BAAI/bge-m3', device='cuda'); m3.half(); m3.max_seq_length = 512
def rank_m3(q, top=50):
    v = np.asarray(m3.encode([q], normalize_embeddings=True), dtype=np.float32)[0]
    return list(np.argsort(-(emb_m3 @ v))[:top])
col = chromadb.PersistentClient(path=str(V.DEFAULT_VECTOR_DB)).get_collection(
    V._CHROMA_COLLECTION)

QD = ROOT.parent / "system" / "questions"
SETS = {
    '括號標記題（主要評測 130 題）': None,
    '自然口語題（colloq_nat 200 題）': [QD / 'heldout' / 'heldout_colloq_nat_100.json',
                                        QD / 'heldout2' / 'heldout_colloq_nat_100.json'],
}

def load(paths):
    out = []
    for p in paths:
        raw = json.loads(p.read_text(encoding='utf-8'))
        for it in (raw if isinstance(raw, list) else raw.get('questions', [])):
            if B.gold_sources(it):
                out.append(it)
    return out

def hits_from(ids):
    return [{'content': docs[j], 'company_code': keys[j][0], 'company_name': '',
             'quarter': keys[j][1], 'table_name': keys[j][2], 'source': '',
             'score': 0.0} for j in ids]

def score(hits, it):
    g = B.gold_sources(it)
    top = [(h['company_code'], h['quarter'], h['table_name']) for h in hits]
    L2 = all(any(t[0] == x[0] and t[1] == x[1] and x[2][:4] in t[2] for t in top) for x in g)
    ctx, _ = B.format_context(hits); cc = norm(ctx)
    vals = [norm(re.sub(r'^[^:：]*[:：]', '', p))
            for p in re.split(r'[｜|]', str(it.get('expected_answer', '')))]
    return L2, all(v and v in cc for v in vals)

report = {}
for lab, paths in SETS.items():
    items = [it for _l, it in B.build_suite('main')] if paths is None else load(paths)
    items = [it for it in items if B.gold_sources(it)]
    res = {'dense bge-small': [], 'dense bge-m3': [], 'BM25': [],
           'hybrid small+BM25': [], 'hybrid m3+BM25': []}
    for n, it in enumerate(items, 1):
        q = it['question']
        r = col.query(query_embeddings=[small.embed_query(q)], n_results=K,
                      include=["documents", "metadatas"])
        s_hits = [{'content': d, 'company_code': m.get('company_code', ''),
                   'company_name': '', 'quarter': m.get('quarter', ''),
                   'table_name': m.get('table_name', ''), 'source': '', 'score': 0}
                  for d, m in zip(r['documents'][0], r['metadatas'][0])]
        s_ids = [DOC2IDX[d] for d in r['documents'][0] if d in DOC2IDX]
        b_ids = list(np.argsort(-AR.bm25_scores(bm25, q))[:50])
        res['dense bge-small'].append(score(s_hits, it))
        res['BM25'].append(score(hits_from(b_ids[:K]), it))
        res['hybrid small+BM25'].append(score(hits_from(AR.rrf(s_ids, b_ids)), it))
        m_ids = rank_m3(q, 50)
        res['dense bge-m3'].append(score(hits_from(m_ids[:K]), it))
        res['hybrid m3+BM25'].append(score(hits_from(AR.rrf(m_ids, b_ids)), it))
        if n % 40 == 0: print(f'  {lab} ...{n}/{len(items)}')
    report[lab] = {k: {'n': len(v),
                       'L2': round(sum(1 for a, _ in v if a) / len(v), 4),
                       'L3': round(sum(1 for _, b in v if b) / len(v), 4)}
                   for k, v in res.items()}

print(f'\n{"題組 / 檢索臂":<44}{"L2 表名對@5":>13}{"L3 答案在prompt":>17}')
for lab, arms in report.items():
    print(f'\n【{lab}】')
    for k, v in arms.items():
        print(f'   {k:<38}{v["L2"]:>12.1%}{v["L3"]:>16.1%}   (n={v["n"]})')
(ROOT / 'results' / 'retrieval_arms_natural.json').write_text(
    json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print('\n輸出：results/retrieval_arms_natural.json')
