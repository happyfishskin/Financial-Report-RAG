import time
import os
from flask import Flask, jsonify, request, render_template
from neo4j import GraphDatabase
from neo4j.graph import Node, Relationship
from neo4j.exceptions import ServiceUnavailable

from questions import QUESTIONS

app = Flask(__name__)

# ── Neo4j 連線設定 ─────────────────────────────────────────────────────────────
NEO4J_URI  = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASS = os.getenv("NEO4J_PASSWORD", "")

try:
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))
except Exception as e:
    print(f"[WARN] 無法建立 Neo4j driver：{e}")
    driver = None


# ── 全域錯誤處理 ──────────────────────────────────────────────────────────────
@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "not found", "detail": str(e)}), 404

@app.errorhandler(Exception)
def handle_exception(e):
    return jsonify({"error": type(e).__name__, "detail": str(e)}), 500


# ── 工具函式 ──────────────────────────────────────────────────────────────────
def _run_query(cypher, **params):
    if driver is None:
        raise RuntimeError("Neo4j driver 未初始化")
    with driver.session() as session:
        result = session.run(cypher, **params)
        return [dict(rec) for rec in result]


def _has_graph_elements(records):
    """判斷結果是否含有節點或關係（決定用圖還是表格渲染）。"""
    for rec in records:
        for val in rec.values():
            if isinstance(val, (Node, Relationship)):
                return True
    return False


def _to_vis_elements(records, node_classes: dict):
    """把含 Node/Relationship 的 records 轉成 vis.js {nodes, edges}。"""
    nodes, edges = {}, []
    for rec in records:
        for val in rec.values():
            if val is None:
                continue
            if isinstance(val, Relationship):
                edges.append({
                    "id":   val.element_id,
                    "from": val.start_node.element_id,
                    "to":   val.end_node.element_id,
                    "label": val.type,
                })
            elif isinstance(val, Node):
                eid    = val.element_id
                labels = list(val.labels)
                props  = dict(val)
                group  = node_classes.get(labels[0], "default") if labels else "default"
                if eid not in nodes:
                    nodes[eid] = {
                        "id":    eid,
                        "label": props.get("name", labels[0] if labels else eid),
                        "group": group,
                        "title": _build_tooltip(props),
                        "data":  props,
                    }
    return {"nodes": list(nodes.values()), "edges": edges}


def _to_table(records):
    """把純屬性 records 轉成前端 table 格式。"""
    if not records:
        return {"columns": [], "rows": []}
    columns = list(records[0].keys())
    rows = []
    for rec in records:
        row = []
        for col in columns:
            val = rec[col]
            if isinstance(val, list):
                val = "、".join(str(v) for v in val)
            row.append("" if val is None else str(val))
        rows.append(row)
    return {"columns": columns, "rows": rows}


def _build_tooltip(props: dict) -> str:
    lines = [f"<b>{props.get('name', '')}</b>"]
    for k, v in props.items():
        if k != "name":
            lines.append(f"{k}: {v}")
    return "<br>".join(lines)


NODE_CLASSES = {
    "Company": "company", "RelatedParty": "related_party",
    "Location": "location", "Business": "business",
    "Stage": "stage", "Segment": "segment",
    "IndustryChain": "industry", "RiskEvent": "risk",
    "RelationType": "relation_type",
}


# ── 頁面 ───────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")


# ── 問題清單 API ──────────────────────────────────────────────────────────────
@app.route("/api/questions")
def list_questions():
    result = []
    for qid, q in QUESTIONS.items():
        result.append({
            "id":         qid,
            "title":      q["title"],
            "category":   q["category"],
            "difficulty": q["difficulty"],
            "result_type": q["result_type"],
        })
    return jsonify(result)


# ── 執行指定問題 API ──────────────────────────────────────────────────────────
@app.route("/api/run/<qid>")
def run_question(qid):
    q = QUESTIONS.get(qid)
    if not q:
        return jsonify({"error": f"找不到問題 {qid}"}), 404

    t0 = time.perf_counter()
    records = _run_query(q["cypher"])
    elapsed = round((time.perf_counter() - t0) * 1000, 2)

    if _has_graph_elements(records):
        payload = _to_vis_elements(records, NODE_CLASSES)
        payload["result_type"] = "graph"
    else:
        payload = _to_table(records)
        payload["result_type"] = "table"

    payload["query_ms"]   = elapsed
    payload["question_id"] = qid
    payload["title"]       = q["title"]
    return jsonify(payload)


# ── 控制組 API ────────────────────────────────────────────────────────────────
@app.route("/api/control/all")
def control_all():
    t0 = time.perf_counter()
    records = _run_query("""
        MATCH (c:Company)-[r:HAS_FINANCIAL_ITEM]->(fi:FinancialItem)
        RETURN c, r, fi
    """)
    elapsed = round((time.perf_counter() - t0) * 1000, 2)
    payload = _to_vis_elements(records, {"Company": "company", "FinancialItem": "financial"})
    payload["query_ms"] = elapsed
    return jsonify(payload)


# ── 實驗組 API 1：只取核心公司（有財報科目的申報公司，約 30 家）──────────────
@app.route("/api/experiment/companies")
def experiment_companies():
    t0 = time.perf_counter()
    records = _run_query("""
        MATCH (c:Company)-[:HAS_FINANCIAL_ITEM]->()
        RETURN DISTINCT c
    """)
    elapsed = round((time.perf_counter() - t0) * 1000, 2)
    payload = _to_vis_elements(records, {"Company": "company"})
    payload["query_ms"] = elapsed
    return jsonify(payload)


# ── 實驗組 API 2：點擊後動態外擴（預設只長出財報科目層）─────────────────────
@app.route("/api/experiment/expand")
def experiment_expand():
    company_name = request.args.get("name", "")
    if not company_name:
        return jsonify({"error": "missing ?name= parameter"}), 400

    t0 = time.perf_counter()
    records = _run_query("""
        MATCH (c:Company {name: $name})-[r:HAS_FINANCIAL_ITEM]->(n:FinancialItem)
        RETURN c, r, n
    """, name=company_name)
    elapsed = round((time.perf_counter() - t0) * 1000, 2)
    payload = _to_vis_elements(records, {"Company": "company", "FinancialItem": "financial"})
    payload["query_ms"] = elapsed
    return jsonify(payload)


# ── rag_test_system_v14 整合：GraphRAG Layer 0 直答 API ──────────────────────
import json as _json
import sys as _sys
import threading as _threading
from pathlib import Path as _Path

_V8_ROOT = _Path(__file__).resolve().parent.parent   # version8 根目錄
_v14_lock = _threading.Lock()
_v14_ctx: dict = {"mod": None, "company_map": None, "error": None}


def _get_v14() -> dict:
    """惰性載入 rag_test_system_v14（torch 匯入＋圖譜載入約 3 秒，僅首次執行）。"""
    with _v14_lock:
        if _v14_ctx["mod"] is None and _v14_ctx["error"] is None:
            try:
                _sys.path.insert(0, str(_V8_ROOT))
                import rag_test_system_v14 as v14
                v14._load_all_compiled_graphs()
                _v14_ctx["company_map"] = v14._build_company_map(v14.REPORTS_ROOT)
                _v14_ctx["mod"] = v14
            except Exception as e:
                _v14_ctx["error"] = f"{type(e).__name__}: {e}"
    return _v14_ctx


@app.route("/api/v14/ask")
def v14_ask():
    """用 v14 內建圖譜引擎（Layer 0 樣板直答，零 LLM）回答圖譜問題。"""
    question = request.args.get("q", "").strip()
    if not question:
        return jsonify({"error": "missing ?q= parameter"}), 400
    ctx = _get_v14()
    if ctx["error"]:
        return jsonify({"error": "v14 載入失敗", "detail": ctx["error"]}), 503
    v14 = ctx["mod"]
    t0 = time.perf_counter()
    answer = v14._gkg_pattern_direct_answer(question, {}, ctx["company_map"])
    elapsed = round((time.perf_counter() - t0) * 1000, 2)
    return jsonify({
        "question": question,
        "hit":      answer is not None,
        "answer":   answer if answer is not None else
                    "（Layer 0 樣板未命中：此問題需走完整 LLM 路由，"
                    "請改用 python3 rag_test_system_v14.py query 執行）",
        "query_ms": elapsed,
        "engine":   "rag_test_system_v14 GraphRAG Layer 0（pandas 圖譜直答，零 LLM）",
    })


@app.route("/api/v14/examples")
def v14_examples():
    """回傳 arch100_v2 的 30 題圖譜範例問題（供前端下拉選單）。"""
    f = _V8_ROOT / "questions" / "system_architecture_test_questions_100_v4.json"
    ds = _json.loads(f.read_text(encoding="utf-8"))
    out = [{"id": x["id"], "question": x["question"],
            "route": x["metadata"]["target_route"],
            "expected": x.get("expected_answer", "")}
           for x in ds
           if x.get("metadata", {}).get("target_route", "").startswith("graph_rag")]
    return jsonify(out)


# ── 健康檢查 ──────────────────────────────────────────────────────────────────
@app.route("/api/health")
def health():
    try:
        _run_query("RETURN 1")
        return jsonify({"status": "ok", "neo4j": "connected"})
    except Exception as e:
        return jsonify({"status": "error", "neo4j": str(e)}), 503


if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", use_reloader=False, port=5001)

   

