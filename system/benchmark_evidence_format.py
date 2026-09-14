#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
證據格式受控消融（A／B／C）
==========================
§4.4 的四階段增益軌跡是**實際開發時序的快照**，技術界線不嚴格可分。本腳本補上
一組真正的受控消融，只變動「送進 LLM 的證據長什麼樣」，其餘一律固定：

| 組別 | 輸入 LLM 的證據 |
|---|---|
| A：原始 RAG | 檢索到的 Markdown 表格 |
| B：扁平化 RAG | **同一批**檢索結果，但轉成「表名／科目／欄位／數值」鍵值列 |
| C：Fact 直查 | 不經 LLM，作為可達上限與對照 |

控制變因有兩層：**A 與 B 共用同一次檢索的同一批 chunk**（本腳本每題只檢索一次，
兩組共用 `hits`），且**共用同一份中性系統提示詞**——線上提示詞第一句寫「從提供的
K-V 財報資料列中提取數值」，若照用會讓提示詞本身偏袒 B 組，故改為不提及格式的
中性版本，其餘規則逐字不動。兩層固定後，A 與 B 之差**只可能**來自證據格式。
C 組不呼叫 LLM，量的是「答案就在事實表裡時，確定性取值能拿到多少分」，即該題組
的可達上限。

注意：本腳本會**實際執行推論**（A／B 各一次 LLM 生成），故其結果是新資料，
不寫回、也不影響 §4.3–§4.9 任何既有的凍結結果檔。

    python3 benchmark_evidence_format.py \
        [--dataset questions/system_architecture_test_questions_100_v4.json] \
        [--limit 0] [--top-k 5] [--out results/evidence_format_ablation]
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import rag_test_system_v14 as V

ROOT = Path(__file__).resolve().parent
DEFAULT_DS = ROOT / "questions" / "system_architecture_test_questions_100_v4.json"

# 中性系統提示詞：線上提示詞的第一句是「從提供的 **K-V 財報資料列** 中提取數值」，
# 直接沿用會讓提示詞本身偏袒 B 組（提示詞—格式匹配），組間差異就不再只是證據格式。
# 故 A／B 兩組一律改用不提及任何格式的中性版本，其餘規則逐字不動。
_ORIG_CLAUSE = "從提供的 K-V 財報資料列中提取數值"
_NEUTRAL_CLAUSE = "從提供的財報資料中提取數值"
assert _ORIG_CLAUSE in V._LLM_SYSTEM_PROMPT_JSON, "線上提示詞已變動，請重新確認中性化改寫"
NEUTRAL_PROMPT = V._LLM_SYSTEM_PROMPT_JSON.replace(_ORIG_CLAUSE, _NEUTRAL_CLAUSE)


def arg(flag: str, default):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default


def pick_questions(path: Path, limit: int) -> list[dict]:
    """
    只取數值事實題（target_route 為 direct_lookup*）。

    關係題與向量題不納入：A／B 之對照是「同一張表格 chunk 的兩種呈現」，
    關係題的證據不是財報數值表，納入會讓組間差異混入題型差異。
    """
    ds = json.loads(path.read_text(encoding="utf-8"))
    items = ds if isinstance(ds, list) else ds.get("questions", [])
    out = [it for it in items
           if str(it.get("metadata", {}).get("target_route", "")).startswith("direct_lookup")]
    return out[:limit] if limit else out


def main() -> int:
    ds_path = Path(arg("--dataset", DEFAULT_DS))
    limit = int(arg("--limit", 0))
    top_k = int(arg("--top-k", 5))
    out_stem = Path(arg("--out", ROOT / "results" / "evidence_format_ablation"))

    items = pick_questions(ds_path, limit)
    if not items:
        print(f"✗ {ds_path} 沒有 direct_lookup 題目")
        return 2
    print(f"題目：{len(items)}（{ds_path.name}，僅數值事實題）")

    import chromadb

    company_map = V._build_company_map(V.REPORTS_ROOT)
    facts_df = V._load_facts_df(V.REPORTS_ROOT)
    # _prep_facts_for_gen 回傳 (std_df, entity_df, deduped_df)；C 組與線上直查軌
    # 一致，傳入全量 facts_df 與 deduped_df（見 _rag_query_one 的呼叫方式）
    _std_df, _entity_df, deduped_df = V._prep_facts_for_gen(facts_df)
    embedder = V._BGEEmbedder(V.DEFAULT_EMBED_MODEL, device="cpu")
    client = chromadb.PersistentClient(path=str(V.DEFAULT_VECTOR_DB))
    collection = client.get_collection(name=V._CHROMA_COLLECTION)
    print(f"  facts_df {len(facts_df):,} 筆｜deduped_df {len(deduped_df):,} 筆｜"
          f"chunks {collection.count():,}")

    rows: list[dict] = []
    t0 = time.time()
    for i, it in enumerate(items, 1):
        q, gold = it["question"], str(it.get("expected_answer", ""))
        intent = V._llm_intent_router(q, V.DEFAULT_VLLM_URL, V.DEFAULT_LLM_MODEL)
        intent = V._enrich_intent_from_question(q, intent, company_map)

        # ── 一次檢索，A／B 共用（控制變因的關鍵）──────────────
        companies = intent.get("companies") or []
        code = V._resolve_company_code(companies[0], company_map) if companies else None
        qs = intent.get("quarters") or []
        quarter = qs[0] if len(qs) == 1 and V._PERIOD_LABEL_RE.match(str(qs[0])) else None
        hits, filter_level = V._retrieve_from_vectordb(
            V._rewrite_query_for_retrieval(q, intent), collection, embedder,
            code, quarter, top_k)

        md = it.get("metadata", {}) or {}
        rec: dict = {"id": it.get("id"), "question": q, "expected_answer": gold,
                     "retrieved_count": len(hits), "filter_level": filter_level,
                     "gold_item": md.get("item_name", ""),
                     "gold_column": md.get("column_header", ""),
                     "groups": {}}

        for grp, flatten in (("A_raw_markdown", False), ("B_flattened_kv", True)):
            if not hits:
                ans, diag = "找不到相關資料", {"status": "no_evidence"}
            else:
                ctx = V._format_context_from_hits(hits, flatten=flatten)
                ans, diag = V._generate_answer_json(
                    V.DEFAULT_VLLM_URL, V.DEFAULT_LLM_MODEL, q, ctx,
                    system_prompt=NEUTRAL_PROMPT)
            # diag 帶 status 與模型自報命中的科目／期間，供欄位定位率、
            # 候選歧義率與拒答率之計算（見 pool_evidence_format.py）
            rec["groups"][grp] = {
                "answer": ans, "scores": V._score_one(ans, gold),
                "status": diag.get("status", ""),
                "reported_item": diag.get("item", ""),
                "reported_period": diag.get("period", ""),
            }

        # ── C：Fact 直查（零 LLM 生成）──────────────────────
        c_traces: list = []
        c_ans = V._execute_direct_lookup_batch(intent, facts_df, deduped_df,
                                               traces=c_traces)
        refused = c_ans is None
        c_ans = c_ans if c_ans is not None else "找不到相關資料"
        # 批次題（跨公司／跨季）每個子查詢各一份 trace；取首份代表命中的科目與
        # 欄位，並以「任一子查詢歧義」判定該題是否落入候選歧義
        first = c_traces[0] if c_traces else {}
        rec["groups"]["C_fact_lookup"] = {
            "answer": c_ans, "scores": V._score_one(c_ans, gold),
            "status": "not_found" if refused else "ok",
            "reported_item": first.get("matched_item", ""),
            "reported_period": first.get("matched_col", ""),
            "traces": c_traces,
            "ambiguous": any(t.get("decision") == "ambiguous" for t in c_traces),
        }
        rows.append(rec)

        marks = "".join("✓" if rec["groups"][g]["scores"]["exact_match"] else "✗"
                        for g in ("A_raw_markdown", "B_flattened_kv", "C_fact_lookup"))
        print(f"  [{i:3d}/{len(items)}] {marks}  {q[:44]}")

    n = len(rows)
    summary = {
        g: {
            "exact": sum(1 for r in rows if r["groups"][g]["scores"]["exact_match"]),
            "numeric": sum(1 for r in rows if r["groups"][g]["scores"]["numeric_match"]),
            "n": n,
        }
        for g in ("A_raw_markdown", "B_flattened_kv", "C_fact_lookup")
    }
    for g, v in summary.items():
        v["em"] = round(v["exact"] / n, 4) if n else 0.0

    payload = {
        "title": "證據格式受控消融（A 原始 Markdown／B 扁平化 K-V／C Fact 直查）",
        "design": {
            "A_raw_markdown": "檢索到的 Markdown 表格原樣送入 LLM",
            "B_flattened_kv": "同一批檢索結果，_md_table_to_kv() 轉表名／科目／欄位／數值鍵值列",
            "C_fact_lookup":  "不經 LLM，_execute_direct_lookup_batch() 確定性取值（可達上限）",
            "control": "A 與 B 共用同一次檢索的同一批 chunk，且共用同一份"
                       "「不提及證據格式」的中性系統提示詞，組間差異只可能來自證據格式",
            "neutral_prompt_clause": f"{_ORIG_CLAUSE} → {_NEUTRAL_CLAUSE}",
        },
        "dataset": str(ds_path), "n": n, "top_k": top_k,
        "elapsed_sec": round(time.time() - t0, 1),
        "summary": summary, "results": rows,
    }
    js = Path(f"{out_stem}.json")
    js.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    md = [f"# 證據格式受控消融（n={n}）\n",
          "| 組別 | 輸入 LLM 的證據 | EM | 數值一致 |",
          "|---|---|---:|---:|"]
    labels = {
        "A_raw_markdown": "A：原始 RAG｜檢索到的 Markdown 表格",
        "B_flattened_kv": "B：扁平化 RAG｜同一批檢索結果轉鍵值列",
        "C_fact_lookup":  "C：Fact 直查｜不經 LLM（可達上限與對照）",
    }
    for g, lab in labels.items():
        v = summary[g]
        md.append(f"| {lab.split('｜')[0]} | {lab.split('｜')[1]} | "
                  f"{v['em']:.1%}（{v['exact']}/{n}） | {v['numeric']}/{n} |")
    md.append("\nA 與 B 共用同一次檢索之同一批 chunk，故兩組之差只可能來自證據格式。")
    Path(f"{out_stem}.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    print("\n" + "\n".join(md))
    print(f"\n輸出：{js}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
