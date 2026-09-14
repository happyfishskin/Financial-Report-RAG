#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
補測：把檢索端由稠密向量換成 BM25，其餘一切不變，量端到端 EM
=============================================================
唯一變動是檢索器（bge-small 稠密 → jieba BM25 字面），
生成模型、prompt、context 預算、判分函式、題組全部沿用
benchmark_pure_rag_27b.py，故 EM 差異只可能來自檢索方式。

    python3 benchmark_bm25_27b.py [--suite main] [--limit 0]
"""
from __future__ import annotations
import importlib.util, json, sys, time
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "system"))
sys.argv_backup = list(sys.argv); sys.argv = ['x']
spec = importlib.util.spec_from_file_location('b', ROOT / 'benchmark_pure_rag_27b.py')
B = importlib.util.module_from_spec(spec); spec.loader.exec_module(B)
A = importlib.util.spec_from_file_location('a', ROOT / 'audit_retrieval_arms.py')
AR = importlib.util.module_from_spec(A); A.loader.exec_module(AR)
sys.argv = sys.argv_backup
import rag_test_system_v14 as V

def arg(flag, default):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default

def main() -> int:
    suite = arg('--suite', 'main'); limit = int(arg('--limit', 0))
    out = Path(arg('--out', ROOT / 'results' / 'bm25_27b_main'))
    model = arg('--model', 'qwen3.8-27b-iq3xxs')
    if suite == 'colloq_nat':
        QD = ROOT.parent / 'system' / 'questions'
        items = []
        for f in (QD/'heldout'/'heldout_colloq_nat_100.json',
                  QD/'heldout2'/'heldout_colloq_nat_100.json'):
            raw = json.loads(f.read_text(encoding='utf-8'))
            for it in (raw if isinstance(raw, list) else raw.get('questions', [])):
                items.append((f'NAT｜{f.parent.name}', it))
    else:
        items = B.build_suite(suite)
    if limit: items = items[:limit]
    corpus = AR.load_corpus(); docs, keys = corpus['docs'], corpus['keys']
    bm25 = AR.build_bm25(docs)
    print(f'題目 {len(items)}｜語料 {len(docs):,}｜檢索器 BM25')

    rows = []; t0 = time.time()
    for i, (lab, it) in enumerate(items, 1):
        q, gold = it['question'], str(it.get('expected_answer', ''))
        ids = list(np.argsort(-AR.bm25_scores(bm25, q))[:B.TOP_K])
        hits = [{'content': docs[j], 'company_code': keys[j][0], 'company_name': '',
                 'quarter': keys[j][1], 'table_name': keys[j][2], 'source': '',
                 'score': 0.0} for j in ids]
        ctx, nc = B.format_context(hits)
        gen = B.generate('ollama', B.DEFAULT_OLLAMA, model,
                         B.PROMPT_TEMPLATE.format(context=ctx, question=q))
        strict, lenient = B.hit_at_k(it, hits)
        rec = {'key': f'{lab}#{it.get("id")}', 'dataset': lab, 'id': it.get('id'),
               'question_type': it.get('question_type', ''), 'question': q,
               'expected_answer': gold, 'answer': gen['answer'],
               'scores': V._score_one(gen['answer'], gold),
               'refused': V._is_refusal(gen['answer']),
               'hit5_strict': strict, 'hit5_lenient': lenient,
               'chunks_in_context': nc, 'prompt_tokens': gen['prompt_tokens'],
               'completion_tokens': gen['completion_tokens'],
               'latency_sec': gen['latency_sec'], 'error': gen['error']}
        rows.append(rec)
        m = '✓' if rec['scores']['exact_match'] else '✗'
        print(f'  [{i:4d}/{len(items)}] {m} {gen["latency_sec"]:5.1f}s  {q[:36]}  →  {rec["answer"][:22]}')
        if i % 20 == 0:
            out.parent.mkdir(parents=True, exist_ok=True)
            Path(f'{out}_checkpoint.json').write_text(json.dumps(rows, ensure_ascii=False), 'utf-8')

    n = len(rows)
    s = {'n': n, 'exact': sum(1 for r in rows if r['scores']['exact_match']),
         'refused': sum(1 for r in rows if r['refused']),
         'hit5': sum(1 for r in rows if r['hit5_strict'])}
    s['em'] = round(s['exact'] / n, 4); s['refusal_rate'] = round(s['refused'] / n, 4)
    s['hit5_rate'] = round(s['hit5'] / n, 4)
    s['elapsed_sec'] = round(time.time() - t0, 1)
    out.parent.mkdir(parents=True, exist_ok=True)
    Path(f'{out}.json').write_text(json.dumps(
        {'retriever': 'BM25 (jieba, k1=1.5, b=0.75)', 'suite': suite,
         'summary': s, 'results': rows}, ensure_ascii=False, indent=2), 'utf-8')
    print(f'\nBM25 + 27B：EM {s["em"]:.1%}（{s["exact"]}/{n}）'
          f'｜Hit@5 {s["hit5_rate"]:.1%}｜拒答 {s["refusal_rate"]:.1%}')
    print(f'輸出：{out}.json')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
