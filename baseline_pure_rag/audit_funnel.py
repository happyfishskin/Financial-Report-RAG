#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分層衰減鏈（三層漏斗）：在**線上管線**上量測，非以金標模擬
==========================================================
層級定義（由寬到嚴）：
  L1 公司＋期別命中 —— 即 §2.5.1／`_relevance_grade` 之 rel>=1，**不要求表名正確**
  L2 表名亦命中     —— 即 rel==2
  L3 金標數值確實出現在依 Top-5 組成之提示詞內 —— 模型真正看得到

三種檢索設定：
  full   全庫檢索、無任何 metadata 過濾（附錄六（五）之純 RAG 設定）
  online 線上管線：SLM Router 推斷公司與期別 → 漸進式硬過濾（軌道二實際行為）
  oracle 以金標公司與期別過濾（過濾器之上界，用以分離「Router 推錯」之影響）
"""
from __future__ import annotations
import importlib.util, json, re, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "system"))
_a = list(sys.argv); sys.argv = ['x']
spec = importlib.util.spec_from_file_location('b', ROOT / 'benchmark_pure_rag_27b.py')
B = importlib.util.module_from_spec(spec); spec.loader.exec_module(B)
sys.argv = _a
import rag_test_system_v14 as V

norm = lambda s: re.sub(r'[（）()\s,，]', '', str(s))
K = 5


def layers(hits, it):
    g = B.gold_sources(it)
    top = [(h['company_code'], h['quarter'], h['table_name']) for h in hits]
    L1 = all(any(t[0] == x[0] and t[1] == x[1] for t in top) for x in g)
    L2 = all(any(t[0] == x[0] and t[1] == x[1] and x[2][:4] in t[2] for t in top) for x in g)
    ctx = V._format_context_from_hits(hits, flatten=True)
    c = norm(ctx)
    vals = [norm(re.sub(r'^[^:：]*[:：]', '', p))
            for p in re.split(r'[｜|]', str(it.get('expected_answer', '')))]
    return L1, L2, all(v and v in c for v in vals)


def main() -> int:
    import chromadb
    items = [(l, it) for l, it in B.build_suite('main') if B.gold_sources(it)]
    cmap = V._build_company_map(V.REPORTS_ROOT)
    emb = V._BGEEmbedder(V.DEFAULT_EMBED_MODEL, device='cpu')
    col = chromadb.PersistentClient(path=str(V.DEFAULT_VECTOR_DB)).get_collection(
        V._CHROMA_COLLECTION)
    rows = []          # 逐題記錄，供單一來源子集之乾淨漏斗使用
    router_ok = 0
    n = 0
    for i, (lab, it) in enumerate(items, 1):
        q = it['question']; g = B.gold_sources(it)[0]; n += 1
        # full：原始問題、全庫、無過濾
        e = emb.embed_query(q)
        r = col.query(query_embeddings=[e], n_results=K,
                      include=["documents", "metadatas"])
        hf = [{'content': d, 'company_code': m.get('company_code', ''),
               'company_name': m.get('company_name', ''), 'quarter': m.get('quarter', ''),
               'table_name': m.get('table_name', ''), 'source': '', 'score': 0.0}
              for d, m in zip(r['documents'][0], r['metadatas'][0])]
        rec = {'id': it.get('id'), 'n_gold': len(B.gold_sources(it)),
               'full': list(layers(hf, it))}
        # online：Router 推斷 → 漸進式過濾（軌道二實際行為）
        intent = V._llm_intent_router(q, V.DEFAULT_VLLM_URL, V.DEFAULT_LLM_MODEL)
        intent = V._enrich_intent_from_question(q, intent, cmap)
        comps = intent.get('companies') or []
        code = V._resolve_company_code(comps[0], cmap) if comps else None
        qs = intent.get('quarters') or []
        qtr = qs[0] if len(qs) == 1 and V._PERIOD_LABEL_RE.match(str(qs[0])) else None
        router_ok += (code == g[0] and qtr == g[1])
        ho, _ = V._retrieve_from_vectordb(V._rewrite_query_for_retrieval(q, intent),
                                          col, emb, code, qtr, K)
        rec['online'] = list(layers(ho, it))
        rec['router_slot_ok'] = bool(code == g[0] and qtr == g[1])
        # oracle：以金標公司期別過濾（過濾器上界）
        hg, _ = V._retrieve_from_vectordb(q, col, emb, g[0], g[1], K)
        rec['oracle'] = list(layers(hg, it)); rows.append(rec)
        if i % 20 == 0:
            print(f'  ...{i}/{len(items)}')

    names = {'full': 'full  全庫、無過濾', 'online': 'online 線上 Router 過濾',
             'oracle': 'oracle 金標過濾（上界）'}
    out = {}
    for tag, sub in (('single', [r for r in rows if r['n_gold'] == 1]), ('all', rows)):
        m = len(sub)
        lab = '單一金標來源題（乾淨漏斗）' if tag == 'single' else '全部題目（含批次題）'
        print(f'\n分層衰減鏈｜{lab}（n={m}）')
        print(f'{"檢索設定":<26}{"L1":>9}{"L2":>9}{"L3":>9}')
        out[tag] = {'n': m}
        for k in ('full', 'online', 'oracle'):
            c = [sum(1 for r in sub if r[k][j]) for j in range(3)]
            out[tag][k] = {'L1': round(c[0]/m, 4), 'L2': round(c[1]/m, 4),
                           'L3': round(c[2]/m, 4), 'counts': c}
            print(f'{names[k]:<26}{c[0]/m:>8.1%}{c[1]/m:>9.1%}{c[2]/m:>9.1%}')
        out[tag]['router_slot_accuracy'] = round(
            sum(1 for r in sub if r['router_slot_ok'])/m, 4)
        print(f'  Router 公司＋期別同時推對：{out[tag]["router_slot_accuracy"]:.1%}')
    out['note'] = ('批次題（跨公司／跨期）之金標有多個來源，oracle 僅能以其中之一過濾，'
                   '嚴格判準下必然失敗，故乾淨漏斗以單一來源題為準。')
    out['rows'] = rows
    (ROOT/'results'/'funnel_layers.json').write_text(
        json.dumps(out, ensure_ascii=False, indent=2), 'utf-8')
    print('輸出：results/funnel_layers.json')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
