#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
補上設計矩陣缺角：軌道一封住 × 生成端 4B vs 27B（過濾已生效之條件下）
====================================================================
既有兩臂各自混了不同變因：
  ①「27B 純 RAG」EM 13.1%——27B，但無路由、無過濾、無規則；
  ④「軌道一封住 + 4B」EM 26.9%——有路由與 metadata 硬過濾，但生成端是 4B。
兩者相比同時變動「模型大小」與「有無過濾」，不可歸因。本腳本補上第三格：
**保留全部線上機制、僅停用軌道一，並把生成端換成 27B**，使「模型規模」成為
相對於 ④ 的唯一變因。

固定不變（與 benchmark_track1_off.py 之 arm A 逐項相同）：
  SLM Router 抽意圖（Qwen3-4B-AWQ @ vLLM）、company+quarter 漸進式硬過濾、
  bge-small-zh-v1.5 檢索 Top-5、_md_table_to_kv 結構扁平化、
  線上系統提示詞 _LLM_SYSTEM_PROMPT_JSON、同一份 JSON Schema 作答契約、
  _score_one 判分、凍結 held-out 130 題數值題。
唯一變動：作答生成端 Qwen3-4B-AWQ → Qwen3.8-27B（UD-IQ3_XXS，Ollama）。

    python3 benchmark_track1_off_27b.py [--limit 0]
"""
from __future__ import annotations
import importlib.util, json, re, sys, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "system"))
_a = list(sys.argv); sys.argv = ['x']
spec = importlib.util.spec_from_file_location('b', ROOT / 'benchmark_pure_rag_27b.py')
B = importlib.util.module_from_spec(spec); spec.loader.exec_module(B)
sys.argv = _a
import rag_test_system_v14 as V

TOP_K = 5
OLLAMA = "http://127.0.0.1:11434/api/chat"
MODEL = "qwen3.8-27b-iq3xxs"
_THINK = re.compile(r"<think>.*?</think>", re.DOTALL)


def arg(f, d):
    return sys.argv[sys.argv.index(f) + 1] if f in sys.argv else d


def gen_27b(question: str, context: str) -> tuple[str, dict]:
    """與 V._generate_answer_json 同一契約，僅把後端換成 Ollama 上的 27B。"""
    if not str(context or "").strip():
        return "找不到相關資料", {"status": "no_evidence"}
    user = f"{V._contract.wrap_question(question)}\n\n{V._contract.wrap_evidence(context)}"
    payload = {
        "model": MODEL,
        "messages": [{"role": "system", "content": V._LLM_SYSTEM_PROMPT_JSON},
                     {"role": "user", "content": user}],
        "stream": False, "think": False,
        "format": V._contract.answer_json_schema(),   # 同一份 Schema 強制解碼
        "options": {"temperature": 0, "seed": 42, "num_ctx": 4096, "num_predict": 384},
    }
    req = urllib.request.Request(
        OLLAMA, data=json.dumps(payload, ensure_ascii=False).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=900) as r:
            raw = (json.loads(r.read().decode()).get("message") or {}).get("content", "")
    except Exception as exc:                                          # noqa: BLE001
        return "找不到相關資料", {"status": "llm_error", "error": str(exc)[:120]}
    raw = _THINK.sub("", raw).strip()
    env, viol = V._contract.parse_answer_payload(raw)
    if env is None:
        return "找不到相關資料", {"status": "schema_invalid", "schema_violations": viol}
    return V._contract.envelope_to_text(env), {"status": env.get("status")}


def main() -> int:
    limit = int(arg('--limit', 0))
    out = Path(arg('--out', ROOT / 'results' / 'track1_off_27b'))
    items = B.build_suite('main')
    if limit:
        items = items[:limit]

    import chromadb
    cmap = V._build_company_map(V.REPORTS_ROOT)
    emb = V._BGEEmbedder(V.DEFAULT_EMBED_MODEL, device='cpu')
    col = chromadb.PersistentClient(path=str(V.DEFAULT_VECTOR_DB)).get_collection(
        V._CHROMA_COLLECTION)
    print(f'題目 {len(items)}｜軌道一封住｜生成端 27B（{MODEL}）｜其餘同線上路徑')

    rows = []; t0 = time.time()
    for i, (lab, it) in enumerate(items, 1):
        q, gold = it['question'], str(it.get('expected_answer', ''))
        intent = V._llm_intent_router(q, V.DEFAULT_VLLM_URL, V.DEFAULT_LLM_MODEL)
        intent = V._enrich_intent_from_question(q, intent, cmap)
        comps = intent.get('companies') or []
        code = V._resolve_company_code(comps[0], cmap) if comps else None
        qs = intent.get('quarters') or []
        qtr = qs[0] if len(qs) == 1 and V._PERIOD_LABEL_RE.match(str(qs[0])) else None
        hits, lvl = V._retrieve_from_vectordb(
            V._rewrite_query_for_retrieval(q, intent), col, emb, code, qtr, TOP_K)
        ctx = V._format_context_from_hits(hits, flatten=True) if hits else ""
        ans, diag = gen_27b(q, ctx)
        strict, _ = B.hit_at_k(it, hits)
        rows.append({'id': it.get('id'), 'dataset': lab, 'question': q,
                     'question_type': it.get('question_type', ''),
                     'expected_answer': gold, 'answer': ans,
                     'scores': V._score_one(ans, gold),
                     'refused': V._is_refusal(ans), 'filter_level': lvl,
                     'hit5_strict': strict, 'status': diag.get('status', '')})
        m = '✓' if rows[-1]['scores']['exact_match'] else '✗'
        print(f'  [{i:4d}/{len(items)}] {m} {q[:42]} → {ans[:22]}')
        if i % 20 == 0:
            out.parent.mkdir(parents=True, exist_ok=True)
            Path(f'{out}_checkpoint.json').write_text(
                json.dumps(rows, ensure_ascii=False), 'utf-8')

    n = len(rows)
    ex = sum(1 for r in rows if r['scores']['exact_match'])
    s = {'n': n, 'exact': ex, 'em': round(ex / n, 4),
         'refusal_rate': round(sum(1 for r in rows if r['refused']) / n, 4),
         'hit5': round(sum(1 for r in rows if r['hit5_strict']) / n, 4),
         'errors': sum(1 for r in rows if r['status'] in ('llm_error', 'schema_invalid')),
         'elapsed_sec': round(time.time() - t0, 1)}
    out.parent.mkdir(parents=True, exist_ok=True)
    Path(f'{out}.json').write_text(json.dumps(
        {'title': '軌道一封住 × 生成端 27B（過濾已生效）',
         'design': {'fixed': 'SLM Router、company+quarter 漸進式硬過濾、bge-small 檢索 '
                             'Top-5、_md_table_to_kv 扁平化、線上系統提示詞與同一份 '
                             'JSON Schema 契約、_score_one 判分',
                    'varied': '作答生成端 Qwen3-4B-AWQ → Qwen3.8-27B（UD-IQ3_XXS）',
                    'track1': 'disabled'},
         'dataset': '凍結 held-out 130 題數值題', 'summary': s, 'results': rows},
        ensure_ascii=False, indent=2), 'utf-8')
    print(f'\n軌道一封住＋27B：EM {s["em"]:.1%}（{ex}/{n}）'
          f'｜Hit@5 {s["hit5"]:.1%}｜拒答 {s["refusal_rate"]:.1%}｜契約失敗 {s["errors"]}')
    print(f'輸出：{out}.json')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
