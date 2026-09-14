#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
軌道一封住 × 嵌入模型消融（2×2 的缺角）
======================================
問題：本系統向量軌之低分，是否只因所用嵌入模型（bge-small-zh-v1.5，512 維）太弱？
若換上 bge-m3，確定性直查軌是否就不再必要？

作法：強制關閉軌道一（不呼叫 `_execute_direct_lookup_batch`），令全部題目走軌道二，
其餘**一律沿用線上路徑**：同一顆 SLM Router 抽意圖、同一套 company+quarter 漸進式
metadata 硬過濾、同一份線上系統提示詞（`_LLM_SYSTEM_PROMPT_JSON`）、同一個
`_md_table_to_kv` 扁平化、同一顆 Qwen3-4B-AWQ 生成、同一支 `_score_one` 判分。
唯一變因為檢索所用之嵌入模型：

  arm A  bge-small-zh-v1.5（線上現行，走既有 ChromaDB）
  arm B  bge-m3（1024 維，走本研究另建之向量矩陣，過濾邏輯逐條複製 arm A）

題組採凍結 held-out 之 130 題數值題，避免以 dev 集調參之嫌。
本腳本不寫回任何既有凍結結果。

    python3 benchmark_track1_off.py [--limit 0] [--arms A,B]
"""
from __future__ import annotations
import importlib.util, json, sys, time
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "system"))
_argv = list(sys.argv); sys.argv = ['x']
spec = importlib.util.spec_from_file_location('b', ROOT / 'benchmark_pure_rag_27b.py')
B = importlib.util.module_from_spec(spec); spec.loader.exec_module(B)
A_ = importlib.util.spec_from_file_location('a', ROOT / 'audit_retrieval_arms.py')
AR = importlib.util.module_from_spec(A_); A_.loader.exec_module(AR)
sys.argv = _argv
import rag_test_system_v14 as V

TOP_K = 5


def arg(f, d):
    return sys.argv[sys.argv.index(f) + 1] if f in sys.argv else d


def m3_retrieve(qvec, keys, docs, emb, code, quarter, top_k=TOP_K):
    """逐條複製 V._retrieve_from_vectordb 的漸進式過濾：company+quarter → company；
    絕不回退至無過濾（維持跨公司隔離）。"""
    cand = []
    if code and quarter:
        cand.append(("company+quarter",
                     np.array([k[0] == code and k[1] == quarter for k in keys])))
    if code:
        cand.append(("company_only", np.array([k[0] == code for k in keys])))
    for level, mask in cand:
        idx = np.flatnonzero(mask)
        if idx.size == 0:
            continue
        sims = emb[idx] @ qvec
        order = idx[np.argsort(-sims)[:top_k]]
        hits = [{"content": docs[j], "company_code": keys[j][0], "company_name": "",
                 "quarter": keys[j][1], "table_name": keys[j][2], "source": "",
                 "score": float(sims[np.where(idx == j)[0][0]])} for j in order]
        if hits:
            return hits, level
    return [], "no_match"


def main() -> int:
    limit = int(arg('--limit', 0))
    arms = arg('--arms', 'A,B').split(',')
    out = Path(arg('--out', ROOT / 'results' / 'track1_off_embed_ablation'))

    items = B.build_suite('main')
    if limit:
        items = items[:limit]
    print(f'題目 {len(items)}（凍結 held-out 數值題）｜arms={arms}')

    import chromadb
    company_map = V._build_company_map(V.REPORTS_ROOT)
    small = V._BGEEmbedder(V.DEFAULT_EMBED_MODEL, device='cpu')
    col = chromadb.PersistentClient(path=str(V.DEFAULT_VECTOR_DB)).get_collection(
        V._CHROMA_COLLECTION)
    corpus = AR.load_corpus(); docs, keys = corpus['docs'], corpus['keys']
    emb_m3 = m3 = None
    if 'B' in arms:
        from sentence_transformers import SentenceTransformer
        emb_m3 = np.load(ROOT / '_cache' / 'emb_m3.npy')
        # 查詢編碼走 CPU：語料向量已離線算好，此處每題僅編碼一句，
        # batch=1 在 CPU 上約數十毫秒；GPU 需留給線上 vLLM（4B 生成端）。
        m3 = SentenceTransformer('BAAI/bge-m3', device='cpu')
        m3.max_seq_length = 512
        print(f'  bge-m3 矩陣 {emb_m3.shape}')

    rows = []; t0 = time.time()
    for i, (lab, it) in enumerate(items, 1):
        q, gold = it['question'], str(it.get('expected_answer', ''))
        # ── 與線上完全相同的意圖抽取與槽位補全（軌道一封住不影響這一步）──
        intent = V._llm_intent_router(q, V.DEFAULT_VLLM_URL, V.DEFAULT_LLM_MODEL)
        intent = V._enrich_intent_from_question(q, intent, company_map)
        comps = intent.get('companies') or []
        code = V._resolve_company_code(comps[0], company_map) if comps else None
        qs = intent.get('quarters') or []
        quarter = qs[0] if len(qs) == 1 and V._PERIOD_LABEL_RE.match(str(qs[0])) else None
        rq = V._rewrite_query_for_retrieval(q, intent)

        rec = {'id': it.get('id'), 'dataset': lab, 'question': q,
               'question_type': it.get('question_type', ''),
               'expected_answer': gold, 'arms': {}}

        for arm in arms:
            if arm == 'A':
                hits, lvl = V._retrieve_from_vectordb(rq, col, small, code, quarter, TOP_K)
            else:
                qv = np.asarray(m3.encode([rq], normalize_embeddings=True),
                                dtype=np.float32)[0]
                hits, lvl = m3_retrieve(qv, keys, docs, emb_m3, code, quarter, TOP_K)
            if not hits:
                ans, diag = '找不到相關資料', {'status': 'no_evidence'}
            else:
                ctx = V._format_context_from_hits(hits, flatten=True)   # 線上行為
                ans, diag = V._generate_answer_json(
                    V.DEFAULT_VLLM_URL, V.DEFAULT_LLM_MODEL, q, ctx)    # 線上提示詞
            strict, lenient = B.hit_at_k(it, hits)
            rec['arms'][arm] = {'answer': ans, 'scores': V._score_one(ans, gold),
                                'refused': V._is_refusal(ans), 'filter_level': lvl,
                                'hit5_strict': strict, 'status': diag.get('status', '')}
        rows.append(rec)
        marks = ''.join('✓' if rec['arms'][a]['scores']['exact_match'] else '✗' for a in arms)
        print(f'  [{i:4d}/{len(items)}] {marks}  {q[:44]}')
        if i % 20 == 0:
            out.parent.mkdir(parents=True, exist_ok=True)
            Path(f'{out}_checkpoint.json').write_text(
                json.dumps(rows, ensure_ascii=False), 'utf-8')

    n = len(rows)
    summary = {}
    for a in arms:
        ex = sum(1 for r in rows if r['arms'][a]['scores']['exact_match'])
        summary[a] = {'n': n, 'exact': ex, 'em': round(ex / n, 4),
                      'refusal_rate': round(sum(1 for r in rows if r['arms'][a]['refused']) / n, 4),
                      'hit5': round(sum(1 for r in rows if r['arms'][a]['hit5_strict']) / n, 4)}
    if len(arms) == 2:
        from math import comb
        p_ = [(r['arms'][arms[0]]['scores']['exact_match'],
               r['arms'][arms[1]]['scores']['exact_match']) for r in rows]
        b_ = sum(1 for x, y in p_ if x and not y); c_ = sum(1 for x, y in p_ if y and not x)
        m = b_ + c_; k = min(b_, c_)
        summary['mcnemar'] = {'only_A': b_, 'only_B': c_,
                              'both': sum(1 for x, y in p_ if x and y),
                              'neither': sum(1 for x, y in p_ if not x and not y),
                              'p': round(min(1.0, 2 * sum(comb(m, i) for i in range(k + 1)) / 2**m), 6) if m else 1.0}
    out.parent.mkdir(parents=True, exist_ok=True)
    Path(f'{out}.json').write_text(json.dumps({
        'title': '軌道一封住 × 嵌入模型消融',
        'design': {'A': 'bge-small-zh-v1.5（線上現行）', 'B': 'bge-m3（1024 維）',
                   'fixed': 'SLM Router、company+quarter 漸進式硬過濾、線上系統提示詞、'
                            '_md_table_to_kv 扁平化、Qwen3-4B-AWQ、_score_one 判分',
                   'track1': 'disabled（不呼叫 _execute_direct_lookup_batch）'},
        'dataset': '凍結 held-out 130 題數值題', 'n': n,
        'elapsed_sec': round(time.time() - t0, 1),
        'summary': summary, 'results': rows}, ensure_ascii=False, indent=2), 'utf-8')
    print('\n軌道一封住：')
    for a in arms:
        s = summary[a]
        print(f'  arm {a}  EM {s["em"]:.1%}（{s["exact"]}/{n}）'
              f'｜Hit@5 {s["hit5"]:.1%}｜拒答 {s["refusal_rate"]:.1%}')
    if 'mcnemar' in summary:
        print(f'  McNemar p={summary["mcnemar"]["p"]}')
    print(f'輸出：{out}.json')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
