#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
補上 2×2 之第四格：純 RAG（無過濾、無規則）× 生成端 4B，題組同為 held-out 130 題
==============================================================================
使四格皆落在同一題組（凍結 held-out 之 130 題數值題），兩兩之間只差一個變因：

                    │ 生成端 4B          │ 生成端 27B
  ──────────────────┼────────────────────┼──────────────────
  純 RAG（無過濾）   │ 本腳本             │ 13.1%（附錄六 F.5）
  軌道一封住（有過濾）│ 26.9%（F.6）       │ benchmark_track1_off_27b.py

本腳本之設定與 benchmark_pure_rag_27b.py 逐項相同——原始問題向量化、ChromaDB
全庫 Top-5、無任何 metadata 過濾、原始 Markdown 不做 K-V 扁平化、規格書 §6 之
固定 prompt、temperature 0、seed 42、context 4096、輸出上限 384、同一支 EM 評分器
——唯一變動為生成端改用線上之 Qwen3-4B-AWQ（vLLM）。

    python3 benchmark_purerag_4b.py [--limit 0]
"""
from __future__ import annotations
import importlib.util, json, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "system"))
_a = list(sys.argv); sys.argv = ['x']
spec = importlib.util.spec_from_file_location('b', ROOT / 'benchmark_pure_rag_27b.py')
B = importlib.util.module_from_spec(spec); spec.loader.exec_module(B)
sys.argv = _a
import rag_test_system_v14 as V


def arg(f, d):
    return sys.argv[sys.argv.index(f) + 1] if f in sys.argv else d


def gen_4b(prompt: str) -> dict:
    """
    純 RAG 契約：與 27B 組同一份 §6 固定 prompt、單一 user 訊息、無 JSON Schema、
    單次生成。特別以 chat_template_kwargs 關閉思考鏈——27B 組使用 Ollama 之
    `think: False`，若此處不關，4B 會輸出完整 CoT，兩臂之差將混入輸出格式而非
    模型能力。V._call_vllm 未開放該參數（線上路徑靠 JSON Schema 強制結構），
    故此處自行組請求。
    """
    import json as _json, re, urllib.request, urllib.error
    t0 = time.time()
    payload = {"model": V.DEFAULT_LLM_MODEL,
               "messages": [{"role": "user", "content": prompt}],
               "temperature": B.TEMPERATURE, "seed": B.SEED,
               "max_tokens": B.MAX_OUT_TOKENS,
               "chat_template_kwargs": {"enable_thinking": False}}
    req = urllib.request.Request(
        f"{V.DEFAULT_VLLM_URL.rstrip('/')}/chat/completions",
        data=_json.dumps(payload, ensure_ascii=False).encode(),
        headers={"Content-Type": "application/json", "Authorization": "Bearer EMPTY"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            raw = ((_json.loads(r.read().decode()).get("choices") or [{}])[0]
                   .get("message") or {}).get("content", "") or ""
    except Exception as exc:                                          # noqa: BLE001
        return {"answer": "找不到相關資料", "latency_sec": round(time.time()-t0, 2),
                "error": f"{type(exc).__name__}: {exc}"[:100]}
    lat = round(time.time() - t0, 2)
    ans = re.sub(r"</?think>", "", B._THINK_RE.sub("", raw)).strip()
    m = re.search(r"[「『]([^」』]*)[」』]", ans)
    if m and m.group(1).strip():
        ans = m.group(1).strip()
    return {"answer": (ans.strip().strip("。").strip() or "找不到相關資料"),
            "latency_sec": lat, "error": ""}


def main() -> int:
    limit = int(arg('--limit', 0))
    out = Path(arg('--out', ROOT / 'results' / 'pure_rag_4b_main'))
    items = B.build_suite('main')
    if limit:
        items = items[:limit]

    import chromadb
    emb = V._BGEEmbedder(V.DEFAULT_EMBED_MODEL, device='cpu')
    col = chromadb.PersistentClient(path=str(V.DEFAULT_VECTOR_DB)).get_collection(
        V._CHROMA_COLLECTION)
    print(f'題目 {len(items)}｜純 RAG（全庫 Top-5、無過濾）｜生成端 '
          f'{V.DEFAULT_LLM_MODEL}')

    rows = []; t0 = time.time()
    for i, (lab, it) in enumerate(items, 1):
        q, gold = it['question'], str(it.get('expected_answer', ''))
        hits = B.retrieve(col, emb, q)                      # 無過濾，與 27B 組同一函式
        ctx, nc = B.format_context(hits)
        g = gen_4b(B.PROMPT_TEMPLATE.format(context=ctx, question=q))
        strict, lenient = B.hit_at_k(it, hits)
        rows.append({'id': it.get('id'), 'dataset': lab, 'question': q,
                     'question_type': it.get('question_type', ''),
                     'expected_answer': gold, 'answer': g['answer'],
                     'scores': V._score_one(g['answer'], gold),
                     'refused': V._is_refusal(g['answer']),
                     'hit5_strict': strict, 'chunks_in_context': nc,
                     'latency_sec': g['latency_sec'], 'error': g['error']})
        m = '✓' if rows[-1]['scores']['exact_match'] else '✗'
        print(f'  [{i:4d}/{len(items)}] {m} {q[:42]} → {g["answer"][:22]}')
        if i % 20 == 0:
            out.parent.mkdir(parents=True, exist_ok=True)
            Path(f'{out}_checkpoint.json').write_text(
                json.dumps(rows, ensure_ascii=False), 'utf-8')

    n = len(rows); ex = sum(1 for r in rows if r['scores']['exact_match'])
    s = {'n': n, 'exact': ex, 'em': round(ex / n, 4),
         'refusal_rate': round(sum(1 for r in rows if r['refused']) / n, 4),
         'hit5': round(sum(1 for r in rows if r['hit5_strict']) / n, 4),
         'avg_latency_sec': round(sum(r['latency_sec'] for r in rows) / n, 2),
         'errors': sum(1 for r in rows if r['error']),
         'elapsed_sec': round(time.time() - t0, 1)}
    out.parent.mkdir(parents=True, exist_ok=True)
    Path(f'{out}.json').write_text(json.dumps(
        {'title': '純向量 RAG（無過濾）× 生成端 4B',
         'design': {'fixed': '原始問題向量化、ChromaDB 全庫 Top-5、無 metadata 過濾、'
                             '原始 Markdown（不扁平化）、規格書 §6 固定 prompt、'
                             'temperature 0、seed 42、ctx 4096、out 384、_score_one 判分',
                    'varied': f'生成端 = {V.DEFAULT_LLM_MODEL}（對照 27B 組）'},
         'dataset': '凍結 held-out 130 題數值題', 'summary': s, 'results': rows},
        ensure_ascii=False, indent=2), 'utf-8')
    print(f'\n純 RAG + 4B：EM {s["em"]:.1%}（{ex}/{n}）｜Hit@5 {s["hit5"]:.1%}'
          f'｜拒答 {s["refusal_rate"]:.1%}｜平均延遲 {s["avg_latency_sec"]}s')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
