#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
實驗二補充：外部強模型對照組（Gemini-2.5-flash）

目的
────
實驗二既有的五個配置全部是「本系統拆掉某些模組」的內部消融，缺乏外部座標，
無法回答「混合路由的 78.3% 是架構貢獻，還是換一個更強的模型就有了？」。

本腳本固定**檢索與資料完全不變**，僅將「生成端」由本機 Qwen3-4B-AWQ 換成
雲端 gemini-2.5-flash，跑實驗二同一批 60 題（multi_company_test_dataset.json），
並沿用 version7/rag_test_system_v12.py 的同一套檢索元件與評分器，確保可比性。

兩個 arm
────────
  arm=parallel  圖譜＋向量【真並行】檢索（與 benchmark_parallel_ablation.py
                完全相同的檢索路徑）→ Gemini 生成。
                對照：真並行＋Qwen = EM 20.0%
  arm=vector    純向量檢索（與「純向量」消融完全相同）→ Gemini 生成。
                對照：純向量＋Qwen = EM 6.7%

兩者共同對照：混合路由（確定性作答，不經生成）= EM 78.3%

為何不做「混合路由＋Gemini」
──────────────────────────
混合路由 60 題的 answer_mode 為 38 direct_lookup ＋ 12 graph_rag_local ＋
10 graph_rag_topology，**該路徑上沒有生成步驟**（答案由確定性查表／圖譜樣板組出，
LLM 只做意圖路由）。把生成端換成 Gemini 對該配置不會產生任何變化；若改為把
確定性層算出的答案當作「證據」餵給 Gemini，則模型只是照抄，形成循環論證。
故改以上述兩個 arm 取得有意義的外部座標。

公平性設定（刻意不利於本研究的方向）
──────────────────────────────────
  · 意圖路由仍由本機 Qwen 執行（「只換生成端」之字面要求）。
  · Prompt 與 Qwen 組逐字相同，僅移除 `/no_think`——該 token 是 Qwen3 專用控制指令，
    對 Gemini 是無意義雜訊，留著反而可能不當削弱對照模型。
  · Gemini 採**預設 thinking 開啟**（即比 Qwen 組的 `/no_think` 更強的配置），
    確保任何「架構優於強模型」之結論皆為保守估計，不可被質疑削弱 baseline。
  · temperature=0，與 Qwen 組一致。

金鑰
────
從專案根目錄 `.env` 讀取 `GEMINI_API_KEY`（python-dotenv 若已安裝則優先使用，
否則以內建極簡解析器載入至環境變數），一律經 os.getenv 取用。
金鑰不寫入任何輸出檔、不進 URL、不出現在日誌。

用法
────
    python3 benchmark_gemini_external_baseline.py --arm parallel
    python3 benchmark_gemini_external_baseline.py --arm vector

計分（沿用實驗二同一評分器）：
    cd ../legacy_v12 && python3 rag_test_system_v12.py evaluate \
        --results <上面輸出的 json> --output <eval.json>
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from collections import defaultdict
from pathlib import Path

import requests

# version7 之 v12 為實驗二全部配置共用的程式路徑，此處沿用以確保可比性。
_V7 = (Path(__file__).resolve().parent.parent / "legacy_v12")
if str(_V7) not in sys.path:
    sys.path.insert(0, str(_V7))

import rag_test_system_v12 as V12  # noqa: E402

_GEMINI_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)

# ── 系統提示詞：與 Qwen 對照組逐字相同，僅移除 Qwen 專用的 /no_think ──────
_PARALLEL_SYSTEM_PROMPT_GEMINI = (
    "你是嚴謹的台灣財報問答助手。\n"
    "以下提供兩種來源的資料：（一）知識圖譜查詢結果，（二）財報資料片段"
    "（Markdown 表格）。請綜合兩者找出問題對應的數值。\n"
    "只能使用提供的資料回答，不得補造數字、期間或單位。\n"
    "若找到精確數值，直接回答數字（例如：104,217,382），不要加任何解釋。\n"
    "括號負數、百分比、單位均需逐字保留（例如：( 7,439,634 )）。\n"
    "若資料中找不到答案，明確回答「找不到相關資料」。"
)

_VECTOR_SYSTEM_PROMPT_GEMINI = (
    "你是嚴謹的台灣財報問答助手。\n"
    "以下提供的財報資料片段均為 Markdown 格式的表格，請從中找出問題對應的數值。\n"
    "只能使用提供的財報資料回答，不得補造數字、期間或單位。\n"
    "若找到精確數值，直接回答數字（例如：104,217,382），不要加任何解釋。\n"
    "括號負數、百分比、單位均需逐字保留（例如：( 7,439,634 )）。\n"
    "若資料中找不到答案，明確回答「找不到相關資料」。"
)


# ── 金鑰載入 ────────────────────────────────────────────────────────
def _load_env(env_path: Path) -> None:
    """優先使用 python-dotenv；未安裝則以極簡解析器載入 .env 至環境變數。"""
    try:
        from dotenv import load_dotenv  # type: ignore
        load_dotenv(env_path)
        return
    except ImportError:
        pass
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


def _require_api_key() -> str:
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        sys.exit(
            "[ERROR] 找不到 GEMINI_API_KEY。請確認專案根目錄 .env 內含該變數，"
            "或於環境變數中設定。"
        )
    return key


# ── Gemini 生成端 ──────────────────────────────────────────────────
def _call_gemini(
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    *,
    timeout: int = 120,
    max_retries: int = 5,
) -> tuple[str, dict]:
    """
    呼叫 Gemini generateContent。回傳 (答案字串, 診斷資訊)。

    金鑰以 x-goog-api-key 標頭傳送，不放入 URL，避免出現在日誌或錯誤訊息中。
    對 429／5xx 採指數退避重試；其餘錯誤直接回報，不靜默吞掉。
    """
    url = _GEMINI_ENDPOINT.format(model=model)
    payload = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {
            "temperature": 0,
            "maxOutputTokens": 2048,
        },
    }
    headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}

    last_err = ""
    for attempt in range(max_retries):
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=timeout)
        except requests.RequestException as exc:
            last_err = f"{type(exc).__name__}: {exc}"
            time.sleep(min(2 ** attempt + random.random(), 30))
            continue

        if r.status_code == 200:
            data = r.json()
            cands = data.get("candidates") or []
            if not cands:
                fb = data.get("promptFeedback", {})
                return "找不到相關資料", {
                    "gemini_status": "no_candidate",
                    "prompt_feedback": fb,
                }
            cand = cands[0]
            parts = (cand.get("content") or {}).get("parts") or []
            text = "".join(p.get("text", "") for p in parts).strip()
            usage = data.get("usageMetadata", {})
            diag = {
                "gemini_status": "ok",
                "finish_reason": cand.get("finishReason"),
                "prompt_tokens": usage.get("promptTokenCount"),
                "output_tokens": usage.get("candidatesTokenCount"),
                "thoughts_tokens": usage.get("thoughtsTokenCount"),
            }
            if not text:
                # thinking 用盡 token 而未產出答案：如實記錄，不假裝拒答
                diag["gemini_status"] = "empty_text"
                return "找不到相關資料", diag
            return text, diag

        if r.status_code in (429, 500, 502, 503, 504):
            last_err = f"HTTP {r.status_code}: {r.text[:200]}"
            time.sleep(min(2 ** attempt + random.random(), 30))
            continue

        return f"[Gemini 錯誤 HTTP {r.status_code}]", {
            "gemini_status": "http_error",
            "http_code": r.status_code,
            "detail": r.text[:300],
        }

    return f"[Gemini 重試耗盡] {last_err}", {
        "gemini_status": "retry_exhausted",
        "detail": last_err,
    }


# ── Arm A：圖譜＋向量真並行檢索 → Gemini 生成 ─────────────────────
def _query_one_parallel_gemini(
    question: str, collection, embedder, company_map: dict,
    vllm_url: str, llm_model: str, top_k: int, entity_df,
    api_key: str, gemini_model: str,
) -> dict:
    """檢索路徑與 benchmark_parallel_ablation._query_one_parallel 完全一致。"""
    # Step 1：意圖路由仍由本機 Qwen 執行（只換生成端）
    intent = V12._llm_intent_router(question, vllm_url, llm_model)

    # Step 2：圖譜軌（無論是否命中都不提前返回）
    graph_answer, graph_err = None, None
    try:
        graph_answer = V12._execute_graph_rag_search(
            intent, question, entity_df=entity_df,
            vllm_url=vllm_url, llm_model=llm_model,
        )
    except Exception as exc:
        graph_err = f"{type(exc).__name__}: {exc}"

    # Step 3：向量軌（採與純向量組相同的多公司×多季度迭代檢索，不弱化）
    companies = intent.get("companies", []) or []
    quarters = intent.get("quarters", []) or []
    company_codes = [
        c for c in (V12._resolve_company_code(n, company_map) for n in companies) if c
    ]
    query_quarters = [q for q in quarters if V12._PERIOD_LABEL_RE.match(str(q))]

    hits, filter_level = _retrieve_multi(
        question, collection, embedder, company_codes, query_quarters, top_k
    )

    graph_substantive = bool(graph_answer) and not V12._is_refusal(graph_answer)
    graph_block = graph_answer if graph_answer else "（圖譜無相關結果）"
    vector_block = V12._format_context_from_hits(hits) if hits else "（無相關財報資料）"

    if not graph_substantive and not hits:
        return _no_evidence_result(
            question, intent, "graph_vector_parallel_gemini",
            {"_graph_hit": False, "_vector_hit": False, "_graph_raw": graph_answer},
        )

    user_prompt = (
        f"問題：{question}\n\n"
        f"【知識圖譜查詢結果】\n{graph_block}\n\n"
        f"【財報資料片段】\n{vector_block}"
    )
    answer, diag = _call_gemini(
        api_key, gemini_model, _PARALLEL_SYSTEM_PROMPT_GEMINI, user_prompt
    )

    return _vector_style_result(
        question, answer, hits, filter_level,
        {
            **intent,
            "_ablation": "graph_vector_parallel_gemini",
            "_graph_hit": graph_substantive,
            "_vector_hit": bool(hits),
            "_graph_raw": graph_answer,
            **({"_graph_error": graph_err} if graph_err else {}),
        },
        diag,
    )


# ── Arm B：純向量檢索 → Gemini 生成 ────────────────────────────────
def _query_one_vector_gemini(
    question: str, collection, embedder, company_map: dict,
    top_k: int, api_key: str, gemini_model: str,
) -> dict:
    """檢索路徑與 V12 vector_only 消融完全一致（純正則抽取，不經 LLM 路由）。"""
    company_codes, query_quarters = V12._regex_extract_for_vector_only(
        question, company_map
    )
    intent = {
        "route": "semantic_rag", "query_type": "single",
        "companies": company_codes, "quarters": query_quarters,
        "table_name": None, "item_name": "",
        "_ablation": "vector_only_gemini",
    }

    hits, filter_level = _retrieve_multi(
        question, collection, embedder, company_codes, query_quarters, top_k
    )
    if not hits:
        return _no_evidence_result(question, intent, "vector_only_gemini", {})

    context = V12._format_context_from_hits(hits)
    user_prompt = f"問題：{question}\n\n財報資料片段：\n{context}"
    answer, diag = _call_gemini(
        api_key, gemini_model, _VECTOR_SYSTEM_PROMPT_GEMINI, user_prompt
    )
    return _vector_style_result(
        question, answer, hits, filter_level, intent, diag
    )


# ── 共用小工具 ──────────────────────────────────────────────────────
def _retrieve_multi(question, collection, embedder, company_codes,
                    query_quarters, top_k):
    """多公司 × 多季度迭代檢索 + 去重 + 上限裁切（與兩個 Qwen 對照組一致）。"""
    all_hits, filter_levels = [], []
    iter_quarters = query_quarters if query_quarters else [None]
    for code in company_codes:
        for qtr in iter_quarters:
            h, fl = V12._retrieve_from_vectordb(
                question, collection, embedder, code, qtr, top_k
            )
            all_hits.extend(h)
            filter_levels.append(fl)

    seen, unique_hits = set(), []
    for h in sorted(all_hits, key=lambda x: x["score"], reverse=True):
        uid = h.get("source", "") + h["content"][:40]
        if uid not in seen:
            seen.add(uid)
            unique_hits.append(h)
    cap = top_k * max(len(company_codes), 1) * max(len(query_quarters), 1)
    return unique_hits[:cap], (filter_levels[0] if filter_levels else "no_match")


def _no_evidence_result(question, intent, ablation, extra):
    return {
        "question": question, "answer": "找不到相關資料",
        "answer_mode": "no_evidence", "retrieved_count": 0,
        "sources": [], "retrieved_chunks": [], "filter_level": "no_match",
        "router_decision": {**intent, "_ablation": ablation, **extra},
    }


def _vector_style_result(question, answer, hits, filter_level, router_decision, diag):
    """輸出 schema 與 V12 vector_search 一致，使評分器以 retrieved_chunks 計算檢索指標。"""
    return {
        "question": question,
        "answer": answer,
        "answer_mode": "vector_search",
        "gemini_diag": diag,
        "retrieved_count": len(hits),
        "sources": [
            f"{h['company_name']} {h['quarter']} {h['table_name']} (score={h['score']:.3f})"
            for h in hits
        ],
        "retrieved_chunks": [
            {
                "company_name": h.get("company_name", ""),
                "quarter": h.get("quarter", ""),
                "table_name": h.get("table_name", ""),
                "score": h.get("score", 0.0),
                "content": h.get("content", ""),
            }
            for h in hits
        ],
        "filter_level": filter_level,
        "router_decision": router_decision,
    }


def main() -> None:
    ap = argparse.ArgumentParser(
        description="實驗二外部對照組：Gemini-2.5-flash 生成端"
    )
    ap.add_argument("--arm", choices=("parallel", "vector"), required=True,
                    help="parallel=圖譜+向量真並行檢索；vector=純向量檢索")
    ap.add_argument("--dataset", type=Path,
                    default=_V7 / "multi_company_test_dataset.json")
    ap.add_argument("--output", type=Path, default=None)
    ap.add_argument("--root", type=Path, default=_V7 / "reports_csv_output")
    ap.add_argument("--db-path", type=Path, default=_V7 / "vector_db")
    ap.add_argument("--vllm-url", default="http://127.0.0.1:8000/v1")
    ap.add_argument("--llm-model", default="Qwen/Qwen3-4B-AWQ")
    ap.add_argument("--gemini-model", default="gemini-2.5-flash")
    ap.add_argument("--embedding-model", default="BAAI/bge-small-zh-v1.5")
    ap.add_argument("--embed-device", default="cpu")
    ap.add_argument("--top-k", type=int, default=5)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--env", type=Path, default=Path(__file__).resolve().parent / ".env")
    args = ap.parse_args()

    _load_env(args.env)
    api_key = _require_api_key()

    if args.output is None:
        args.output = Path(f"results/rag_query_results_gemini_{args.arm}.json")

    import chromadb

    print("=" * 72)
    print(f"  實驗二外部對照組：Gemini-{args.gemini_model} 生成端（arm={args.arm}）")
    print("=" * 72)
    print(f"  ▶ 金鑰來源：{args.env}（已載入，長度 {len(api_key)}，內容不顯示）")

    client = chromadb.PersistentClient(path=str(args.db_path))
    collection = client.get_collection(name=V12._CHROMA_COLLECTION)
    print(f"  ▶ Vector DB：{collection.count():,} chunks")

    embedder = V12._BGEEmbedder(args.embedding_model, device=args.embed_device)
    company_map = V12._build_company_map(args.root)
    print(f"  ▶ 公司對應表：{len(company_map)} 家")

    entity_df = None
    if args.arm == "parallel":
        facts_df = V12._load_facts_df(args.root)
        _, entity_df, _deduped = V12._prep_facts_for_gen(facts_df)
        V12._load_all_compiled_graphs()
        print(f"  ▶ facts {len(facts_df):,}／entity {len(entity_df):,}；四大圖譜已載入")

    dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
    if args.limit:
        dataset = dataset[: args.limit]
    print(f"  ▶ 資料集：{args.dataset.name}（{len(dataset)} 題）\n")

    results: list[dict] = []
    modes: dict[str, int] = defaultdict(int)
    api_fail = 0
    t0 = time.time()

    for i, item in enumerate(dataset, 1):
        q = item["question"]
        print(f"  [{i:02d}/{len(dataset)}] {q[:54]}...", end="", flush=True)
        q_t0 = time.time()
        try:
            if args.arm == "parallel":
                res = _query_one_parallel_gemini(
                    q, collection, embedder, company_map,
                    args.vllm_url, args.llm_model, args.top_k, entity_df,
                    api_key, args.gemini_model,
                )
            else:
                res = _query_one_vector_gemini(
                    q, collection, embedder, company_map,
                    args.top_k, api_key, args.gemini_model,
                )
        except Exception as exc:
            print(f"  [ERROR] {type(exc).__name__}: {exc}")
            res = _no_evidence_result(
                q, {"_error": str(exc)}, f"{args.arm}_gemini", {}
            )
            res["answer"] = f"[執行錯誤：{exc}]"

        res["latency_sec"] = round(time.time() - q_t0, 2)
        res["id"] = item["id"]
        res["expected_answer"] = item["expected_answer"]
        res["metadata"] = item.get("metadata", {})
        results.append(res)

        st = (res.get("gemini_diag") or {}).get("gemini_status", "-")
        if st not in ("ok", "-"):
            api_fail += 1
        modes[res["answer_mode"]] += 1
        print(f"  → {res['answer_mode']:14} gemini={st:10} ({res['latency_sec']}s)")

        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    dt = time.time() - t0
    print("\n" + "=" * 72)
    print(f"  完成 {len(results)} 題，總耗時 {dt:.1f}s（平均 {dt/max(len(results),1):.2f}s/題）")
    print(f"  answer_mode：{dict(modes)}｜Gemini 非正常回應 {api_fail} 題")
    print(f"  → {args.output}")
    print("=" * 72)
    print("\n  計分：")
    print(f"    cd {_V7} && python3 rag_test_system_v12.py evaluate \\")
    print(f"      --results {args.output.resolve()} \\")
    print(f"      --output {Path('results').resolve()}/eval_gemini_{args.arm}.json")


if __name__ == "__main__":
    main()
