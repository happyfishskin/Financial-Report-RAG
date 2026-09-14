#!/usr/bin/env python3
"""
實驗二補充消融：圖譜 ＋ 向量「真並行」餵入（Graph + Vector True-Parallel Ablation）

背景
────
原 `rag_test_system_v12.py --no-direct` 模式原意為「圖譜＋向量並行」，但其實作
沿用降級鏈（fallback chain）：`_rag_query_one` 於圖譜軌回傳字串後即 `return`，
使向量軌（Step 3）永遠執行不到。實測 `rag_evaluation_v12_graph_vector.json`
60 題 `retrieved_count` 全為 0，證實向量軌自始未召回，該配置實為純圖譜之重跑。

本腳本實作真正的並行消融，以檢驗「更多上下文是否更好」：

    Step 1  LLM 意圖路由（與其他配置相同）
    Step 2  圖譜軌檢索      → graph_answer（字串或 None）      ┐ 兩軌皆執行
    Step 3  向量軌檢索      → hits（top_k chunks）             ┘ 不因對方命中而略過
    Step 4  兩軌結果一併寫入單一 prompt → 單次 LLM 生成最終答案

與其他配置的控制變因
────────────────────
  · 同一份 60 題資料集（multi_company_test_dataset.json）
  · 同一個 LLM（vLLM / Qwen3-4B-AWQ）、同一組路由器與系統提示詞風格
  · 同一 top_k（預設 5）、同一 embedder
  · 刻意跳過 direct_lookup 軌（對應原「圖譜＋向量」之設計意圖）

輸出可直接餵入 `rag_test_system_v12.py evaluate` 計分，與其餘配置指標同源。

用法
────
    conda activate financial_crawler
    python3 benchmark_parallel_ablation.py \
        --dataset ../legacy_v12/multi_company_test_dataset.json \
        --output  results/rag_query_results_v12_graph_vector_PARALLEL.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

# rag_test_system_v12.py 位於 version7；本腳本沿用其載入/檢索/生成元件，
# 確保與實驗二其餘配置共用完全相同的程式路徑。
_V7 = (Path(__file__).resolve().parent.parent / "legacy_v12")
if str(_V7) not in sys.path:
    sys.path.insert(0, str(_V7))

import rag_test_system_v12 as V12  # noqa: E402


# ── 並行模式專用系統提示詞 ──────────────────────────────────────
# 與 V12._LLM_SYSTEM_PROMPT 的差異僅在於「說明有兩種來源」，其餘約束
# （不得補造、括號負數逐字保留、找不到須明說）完全一致，以維持可比性。
_PARALLEL_SYSTEM_PROMPT = (
    "你是嚴謹的台灣財報問答助手。\n"
    "以下提供兩種來源的資料：（一）知識圖譜查詢結果，（二）財報資料片段"
    "（Markdown 表格）。請綜合兩者找出問題對應的數值。\n"
    "只能使用提供的資料回答，不得補造數字、期間或單位。\n"
    "若找到精確數值，直接回答數字（例如：104,217,382），不要加任何解釋。\n"
    "括號負數、百分比、單位均需逐字保留（例如：( 7,439,634 )）。\n"
    "若資料中找不到答案，明確回答「找不到相關資料」。\n"
    "/no_think"
)


def _query_one_parallel(
    question: str,
    collection,
    embedder,
    company_map: dict,
    vllm_url: str,
    llm_model: str,
    top_k: int,
    facts_df,
    deduped_df,
    entity_df,
) -> dict:
    """單題真並行查詢：圖譜與向量兩軌皆執行，結果合併後單次生成。"""
    # ── Step 1：LLM 意圖路由（與其他配置共用同一函式）────────────
    intent = V12._llm_intent_router(question, vllm_url, llm_model)

    # ── Step 2：圖譜軌（無論是否命中，都不提前返回）──────────────
    graph_answer = None
    graph_err = None
    try:
        graph_answer = V12._execute_graph_rag_search(
            intent, question,
            entity_df=entity_df,
            vllm_url=vllm_url,
            llm_model=llm_model,
        )
    except Exception as exc:                     # 圖譜軌異常不應中斷並行實驗
        graph_err = f"{type(exc).__name__}: {exc}"

    # ── Step 3：向量軌（無論圖譜是否命中，一律執行）────────────────
    # 注意：此處刻意採用與「純向量消融」相同的多公司 × 多季度迭代檢索，
    # 而非系統 Step 3 預設的「僅 companies[0]」單公司檢索。理由是本消融旨在
    # 檢驗「額外餵入向量證據是否有助益」，若使用較弱的單公司檢索，任何負面
    # 結果都可被歸咎於向量軌被削弱。給予向量軌與純向量組完全相同（且較強）
    # 的檢索待遇，可確保結論不受此質疑。
    companies = intent.get("companies", []) or []
    quarters = intent.get("quarters", []) or []

    company_codes = [
        c for c in (V12._resolve_company_code(n, company_map) for n in companies) if c
    ]
    query_quarters = [
        q for q in quarters if V12._PERIOD_LABEL_RE.match(str(q))
    ]

    all_hits: list[dict] = []
    filter_levels: list[str] = []
    iter_quarters = query_quarters if query_quarters else [None]
    for code in company_codes:
        for qtr in iter_quarters:
            h, fl = V12._retrieve_from_vectordb(
                question, collection, embedder, code, qtr, top_k
            )
            all_hits.extend(h)
            filter_levels.append(fl)

    # 依相似度降冪去重（多組 公司×季度 可能召回同一 chunk）
    seen: set[str] = set()
    unique_hits: list[dict] = []
    for h in sorted(all_hits, key=lambda x: x["score"], reverse=True):
        uid = h.get("source", "") + h["content"][:40]
        if uid not in seen:
            seen.add(uid)
            unique_hits.append(h)
    cap = top_k * max(len(company_codes), 1) * max(len(query_quarters), 1)
    hits = unique_hits[:cap]
    filter_level = filter_levels[0] if filter_levels else "no_match"

    # ── Step 4：兩軌結果合併為單一 prompt，單次生成 ────────────────
    # 圖譜軌可能回傳「找不到相關資料」字串（非 None），此種情形視為未取得實質
    # 內容，統計時與真正命中區分，避免高估圖譜貢獻。
    graph_substantive = bool(graph_answer) and not V12._is_refusal(graph_answer)
    graph_block = graph_answer if graph_answer else "（圖譜無相關結果）"
    vector_block = V12._format_context_from_hits(hits) if hits else "（無相關財報資料）"

    # 兩軌皆無實質內容 → 不必浪費一次 LLM 呼叫
    if not graph_substantive and not hits:
        return {
            "question":         question,
            "answer":           "找不到相關資料",
            "answer_mode":      "no_evidence",
            "retrieved_count":  0,
            "sources":          [],
            "retrieved_chunks": [],
            "filter_level":     "no_match",
            "router_decision":  {**intent, "_ablation": "graph_vector_parallel",
                                 "_graph_hit": False, "_vector_hit": False,
                                 "_graph_raw": graph_answer},
        }

    user_prompt = (
        f"問題：{question}\n\n"
        f"【知識圖譜查詢結果】\n{graph_block}\n\n"
        f"【財報資料片段】\n{vector_block}\n\n"
        f"/no_think"
    )
    answer = V12._call_vllm(vllm_url, llm_model, _PARALLEL_SYSTEM_PROMPT, user_prompt)

    return {
        "question":        question,
        "answer":          answer,
        # 標記為 vector_search：本配置最終答案一律由 LLM 依「已召回之上下文」生成，
        # 與純向量軌同屬 VS（生成式）路徑，故檢索指標依 retrieved_chunks 計算，
        # 不套用 DL/GR 的虛擬 rank-1 規則（避免重蹈舊版標記造成的指標假象）。
        "answer_mode":     "vector_search",
        "retrieved_count": len(hits),
        "sources": [
            f"{h['company_name']} {h['quarter']} {h['table_name']} (score={h['score']:.3f})"
            for h in hits
        ],
        "retrieved_chunks": [
            {
                "company_name": h.get("company_name", ""),
                "quarter":      h.get("quarter", ""),
                "table_name":   h.get("table_name", ""),
                "score":        h.get("score", 0.0),
                "content":      h.get("content", ""),
            }
            for h in hits
        ],
        "filter_level":    filter_level,
        "router_decision": {
            **intent,
            "_ablation":    "graph_vector_parallel",
            "_graph_hit":   graph_substantive,
            "_vector_hit":  bool(hits),
            "_graph_raw":   graph_answer,
            **({"_graph_error": graph_err} if graph_err else {}),
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="圖譜＋向量真並行消融（實驗二補充）")
    ap.add_argument("--dataset", type=Path,
                    default=_V7 / "multi_company_test_dataset.json")
    ap.add_argument("--output", type=Path,
                    default=Path("results/rag_query_results_v12_graph_vector_PARALLEL.json"))
    ap.add_argument("--root", type=Path, default=_V7 / "reports_csv_output")
    ap.add_argument("--db-path", type=Path, default=_V7 / "vector_db")
    ap.add_argument("--vllm-url", default="http://127.0.0.1:8000/v1")
    ap.add_argument("--llm-model", default="Qwen/Qwen3-4B-AWQ")
    ap.add_argument("--embedding-model", default="BAAI/bge-small-zh-v1.5")
    ap.add_argument("--embed-device", default="cpu")
    ap.add_argument("--top-k", type=int, default=5)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    import chromadb

    print("=" * 72)
    print("  實驗二補充消融：圖譜 ＋ 向量【真並行】餵入")
    print("=" * 72)

    client = chromadb.PersistentClient(path=str(args.db_path))
    collection = client.get_collection(name=V12._CHROMA_COLLECTION)
    print(f"  ▶ Vector DB：{collection.count():,} chunks")

    embedder = V12._BGEEmbedder(args.embedding_model, device=args.embed_device)
    company_map = V12._build_company_map(args.root)
    print(f"  ▶ 公司對應表：{len(company_map)} 家")

    facts_df = V12._load_facts_df(args.root)
    _, entity_df, deduped_df = V12._prep_facts_for_gen(facts_df)
    print(f"  ▶ facts_df {len(facts_df):,}／deduped {len(deduped_df):,}／entity {len(entity_df):,}")

    V12._load_all_compiled_graphs()
    print("  ▶ 四大圖譜已載入")

    dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
    if args.limit:
        dataset = dataset[: args.limit]
    print(f"  ▶ 資料集：{args.dataset.name}（{len(dataset)} 題）\n")

    results: list[dict] = []
    modes: dict[str, int] = defaultdict(int)
    both_hit = graph_hit = vector_hit = neither = 0
    t0 = time.time()

    for i, item in enumerate(dataset, 1):
        q = item["question"]
        print(f"  [{i:02d}/{len(dataset)}] {q[:58]}...", end="", flush=True)
        q_t0 = time.time()
        try:
            res = _query_one_parallel(
                q, collection, embedder, company_map,
                args.vllm_url, args.llm_model, args.top_k,
                facts_df, deduped_df, entity_df,
            )
        except Exception as exc:
            print(f"  [ERROR] {type(exc).__name__}: {exc}")
            res = {
                "question": q, "answer": f"[執行錯誤：{exc}]",
                "answer_mode": "no_evidence", "retrieved_count": 0,
                "sources": [], "retrieved_chunks": [], "filter_level": "no_match",
                "router_decision": {"_ablation": "graph_vector_parallel",
                                    "_error": str(exc)},
            }
        res["latency_sec"] = round(time.time() - q_t0, 2)
        res["vram_peak_mb"] = V12._vram_peak_mb()
        res["vllm_vram_mb"] = V12._get_vllm_external_vram_mb()
        res["id"] = item["id"]
        res["expected_answer"] = item["expected_answer"]
        res["metadata"] = item.get("metadata", {})
        results.append(res)

        rd = res.get("router_decision", {})
        g, v = bool(rd.get("_graph_hit")), bool(rd.get("_vector_hit"))
        if g and v:
            both_hit += 1
        elif g:
            graph_hit += 1
        elif v:
            vector_hit += 1
        else:
            neither += 1
        modes[res["answer_mode"]] += 1
        print(f"  → {res['answer_mode']:14} G={'✓' if g else '×'} V={'✓' if v else '×'} "
              f"({res['latency_sec']}s)")

        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    dt = time.time() - t0
    print("\n" + "=" * 72)
    print(f"  完成 {len(results)} 題，總耗時 {dt:.1f}s（平均 {dt/max(len(results),1):.2f}s/題）")
    print(f"  answer_mode：{dict(modes)}")
    print(f"  兩軌皆命中 {both_hit}｜僅圖譜 {graph_hit}｜僅向量 {vector_hit}｜皆未命中 {neither}")
    print(f"  → {args.output}")
    print("=" * 72)
    print("\n  計分：")
    print(f"    cd {_V7} && python3 rag_test_system_v12.py evaluate \\")
    print(f"      --results {args.output.resolve()} --output <eval.json>")


if __name__ == "__main__":
    main()
