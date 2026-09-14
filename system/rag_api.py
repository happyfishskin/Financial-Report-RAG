#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RAGSystem — 三路混合 RAG 系統統一 API（v15 重構）
==================================================
把 rag_test_system_v14 的完整查詢管線（LLM 意圖路由 → GraphRAG →
Pandas 直接查表 → ChromaDB 向量搜尋）包成可重用的物件介面，
供前端、notebook、批次腳本與外部系統呼叫。

用法（程式）：
    from rag_api import RAGSystem
    rag = RAGSystem()                     # 首次初始化約 30–60 秒
    result = rag.ask("台積電114Q2營收多少？")
    print(result["answer"], result["answer_mode"])

用法（CLI）：
    python3 rag_api.py "台積電114Q2營收多少？"

回傳結構（dict）：
    question / answer / answer_mode / latency_sec / router / filter_level
    display        : "graph" | "fragments" | "none"（前端呈現建議）
    graph          : 圖譜路由命中時的 vis.js 子圖 {nodes, edges, ...}
    fragments      : 直查證據列（fact）或向量檢索片段（chunk）
    fragment_kind  : "fact" | "chunk"

領域設定：所有領域知識（公司別名/科目本體論/模型端點/圖譜來源）
由 config/ 內的 JSON 設定檔 externalize，換領域不需改程式。
"""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))

import rag_test_system_v14 as v14   # noqa: E402  （核心引擎）


# ── 圖譜子圖擷取設定 ─────────────────────────────────────────────
_GRAPH_HINTS = [
    (("產業鏈", "上下游", "供應鏈"), "supply_chain"),
    (("風險",),                      "risk_event"),
    (("關係人",),                    "related_party"),
    (("投資", "被投資"),             "investment"),
]

_EDGE_ATTR_COLS = {
    "investment":    ["location", "main_business", "ownership_percent", "book_value", "report_period"],
    "related_party": ["relation_category", "account", "amount_summary", "report_period"],
    "supply_chain":  ["stage", "segment", "market"],
    "risk_event":    ["period", "item_name", "value_raw", "evidence_level"],
}


class RAGSystem:
    """三路混合 RAG 系統：一次初始化，之後每題 ask() 即可。"""

    def __init__(self, embed_device: str = "cpu", verbose: bool = True):
        import chromadb

        t0 = time.perf_counter()
        if verbose:
            print("[RAGSystem] 初始化：向量庫 / Embedder / 精確索引 / 圖譜 …")
        client = chromadb.PersistentClient(path=str(v14.DEFAULT_VECTOR_DB))
        self.collection  = client.get_collection(name=v14._CHROMA_COLLECTION)
        self.embedder    = v14._BGEEmbedder(v14.DEFAULT_EMBED_MODEL, device=embed_device)
        self.company_map = v14._build_company_map(v14.REPORTS_ROOT)
        self.facts_df    = v14._load_facts_df(v14.REPORTS_ROOT)
        _, self.entity_df, self.deduped_df = v14._prep_facts_for_gen(self.facts_df)
        v14._load_all_compiled_graphs()
        self.vllm_url  = v14.DEFAULT_VLLM_URL
        self.llm_model = v14.DEFAULT_LLM_MODEL
        if verbose:
            print(f"[RAGSystem] 就緒（{time.perf_counter()-t0:.1f}s）："
                  f"{len(self.facts_df):,} facts ｜ "
                  f"{len(v14.GLOBAL_GRAPH_NODES_DF):,} 圖譜節點 ｜ "
                  f"{self.collection.count():,} 向量 chunks")

    # ── 主查詢入口 ───────────────────────────────────────────────
    def ask(self, question: str, top_k: int = 5, with_display: bool = True) -> dict[str, Any]:
        """執行完整三路管線；with_display=True 時附前端呈現素材（子圖/片段）。"""
        t0 = time.perf_counter()
        result = v14._rag_query_one(
            question, self.collection, self.embedder, self.company_map,
            self.vllm_url, self.llm_model, top_k=top_k,
            facts_df=self.facts_df, deduped_df=self.deduped_df,
            entity_df=self.entity_df)
        out: dict[str, Any] = {
            "question":     question,
            "answer":       result.get("answer", ""),
            "answer_mode":  result.get("answer_mode", ""),
            "latency_sec":  round(time.perf_counter() - t0, 3),
            "router":       result.get("router_decision", {}),
            "filter_level": result.get("filter_level", ""),
        }
        if not with_display:
            return out

        mode = out["answer_mode"]
        # [雙軌] 關係事實命中（relation_lookup）仍以子圖呈現證據——來源是離線
        # 編譯的關係事實表，畫成子圖比列成表格更能說明「誰對誰的什麼關係」。
        # `graph_rag*` 為已下架三軌之標記，保留判斷以相容舊結果檔重播。
        if mode == "relation_lookup" or mode.startswith("graph_rag"):
            out["display"] = "graph"
            out["graph"] = self.build_subgraph(question, out["router"], str(out["answer"]))
        elif mode == "direct_lookup":
            out["display"] = "fragments"
            out["fragment_kind"] = "fact"
            out["fragments"] = self.direct_fragments(question, out["router"], str(out["answer"]))
        elif mode == "vector_search":
            out["display"] = "fragments"
            out["fragment_kind"] = "chunk"
            out["fragments"] = result.get("retrieved_chunks", [])
        else:
            out["display"] = "none"
            out["fragments"] = []
        return out

    # ── 圖譜直答（零 LLM，毫秒級）────────────────────────────────
    def ask_graph_direct(self, question: str) -> str | None:
        """GraphRAG Layer 0 樣板直答；未命中回 None。"""
        return v14._gkg_pattern_direct_answer(question, {}, self.company_map)

    # ── 圖譜子圖擷取（前端 vis.js 呈現用）────────────────────────
    def build_subgraph(self, question: str, intent: dict, answer: str,
                       hop1_cap: int = 40, hop2_cap: int = 40) -> dict | None:
        """以問句公司為錨點抽 1–2 hop 子圖；與答案相關的邊優先保留。"""
        nodes_df, edges_df = v14.GLOBAL_GRAPH_NODES_DF, v14.GLOBAL_GRAPH_EDGES_DF
        if nodes_df is None or nodes_df.empty:
            return None
        company, _, entities = v14._gkg_classify_brackets(question, intent, self.company_map)
        cids = v14._gkg_anchor_company_node(company, self.company_map, nodes_df)
        if not cids:
            return None

        gsrc = next((g for kws, g in _GRAPH_HINTS if any(k in question for k in kws)), None)
        e = edges_df if gsrc is None else edges_df[edges_df["_graph_source"] == gsrc]
        name_of  = dict(zip(nodes_df["id"], nodes_df["name"]))
        label_of = dict(zip(nodes_df["id"], nodes_df["label"]))

        def _relevance(row) -> int:
            other = row["target"] if row["source"] in cids else row["source"]
            nm = str(name_of.get(other, ""))
            if nm and nm in answer:
                return 2
            if nm and any(nm in ent or ent in nm for ent in entities if ent):
                return 1
            return 0

        hop1 = e[e["source"].isin(cids) | e["target"].isin(cids)].copy()
        if hop1.empty:
            return None
        hop1["_rel"] = hop1.apply(_relevance, axis=1)
        hop1 = hop1.sort_values("_rel", ascending=False).head(hop1_cap)

        hop1_ids = set(hop1["source"]) | set(hop1["target"])
        frontier = hop1_ids - set(cids)
        hop2 = e[e["source"].isin(frontier) & ~e["target"].isin(hop1_ids)].copy()
        if not hop2.empty:
            hop2["_rel"] = hop2["target"].map(
                lambda t: 2 if str(name_of.get(t, "")) and str(name_of.get(t, "")) in answer else 0)
            hop2 = hop2.sort_values("_rel", ascending=False).head(hop2_cap)

        import pandas as pd
        sub = pd.concat([hop1, hop2], ignore_index=True) if not hop2.empty else hop1

        attr_cols = _EDGE_ATTR_COLS.get(gsrc or "", [])
        vis_nodes: dict[str, dict] = {}
        vis_edges: list[dict] = []
        for i, row in sub.iterrows():
            for nid in (row["source"], row["target"]):
                if nid in vis_nodes:
                    continue
                nm = str(name_of.get(nid, nid))
                vis_nodes[nid] = {
                    "id": nid, "label": nm[:24],
                    "group": "anchor" if nid in cids else str(label_of.get(nid, "Node")),
                    "in_answer": bool(nm and nm in answer),
                    "title": f"{label_of.get(nid, '')}｜{nm}",
                }
            attrs = {c: str(row[c]) for c in attr_cols
                     if c in sub.columns and str(row.get(c, "")).strip()}
            vis_edges.append({
                "id": f"e{i}", "from": row["source"], "to": row["target"],
                "label": str(row.get("type", "")),
                "title": "<br>".join(f"{k}: {v}" for k, v in attrs.items())
                         or str(row.get("type", "")),
            })
        return {"graph_source": gsrc or "all", "anchor_company": company,
                "nodes": list(vis_nodes.values()), "edges": vis_edges}

    # ── 直查證據片段（答案數值反查 facts）────────────────────────
    def direct_fragments(self, question: str, intent: dict, answer: str = "",
                         limit: int = 8) -> list[dict]:
        df = self.facts_df
        comps    = intent.get("companies") or []
        quarters = [str(q) for q in (intent.get("quarters") or [])]
        item     = (intent.get("item_name") or "").strip()
        if not comps:
            comp, quarter, _ = v14._gkg_classify_brackets(question, intent, self.company_map)
            comps = [comp] if comp else []
            if quarter and not quarters:
                quarters = [quarter]
        nums = {n for n in re.findall(r"\d+(?:\.\d+)?", answer.replace(",", ""))
                if len(n.replace(".", "")) >= 3}

        def _rows_to_frags(rows) -> list[dict]:
            return [{
                "company_name":  r["company_name"],
                "quarter":       r["period"],
                "table_name":    r["table_name"],
                "item_name":     r["item_name"],
                "column_header": r["column_header"],
                "value":         r["value_raw"],
            } for _, r in rows.iterrows()]

        frags: list[dict] = []
        per_comp = max(2, limit // max(len(comps), 1))
        for comp in comps[:4]:
            code = v14._resolve_company_code(comp, self.company_map)
            sub = df[df["stock_code"] == code] if code else \
                  df[df["company_name"].str.contains(re.escape(comp), na=False)]
            if quarters:
                s2 = sub[sub["period"].isin(quarters)]
                if not s2.empty:
                    sub = s2
            picked = sub.iloc[0:0]
            if nums:
                norm = sub["value_raw"].str.replace(r"[,\s()（）]", "", regex=True)
                picked = sub[norm.isin(nums)]
            if len(picked) < per_comp and item:
                s2 = sub[sub["item_name"] == item]
                if s2.empty:
                    s2 = sub[sub["item_name"].str.contains(re.escape(item[:6]), na=False)]
                import pandas as pd
                picked = pd.concat([picked, s2]).drop_duplicates()
            if picked.empty:
                picked = sub
            frags.extend(_rows_to_frags(picked.head(per_comp)))
        return frags[:limit]


# ── CLI ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit('用法：python3 rag_api.py "<問題>" [更多問題…]')
    rag = RAGSystem()
    for q in sys.argv[1:]:
        r = rag.ask(q, with_display=False)
        print(f"\nQ: {q}")
        print(f"A: {r['answer']}")
        print(f"   路由={r['answer_mode']} ｜ 耗時={r['latency_sec']}s")
