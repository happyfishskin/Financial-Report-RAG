#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
客戶問答前端（確定性雙軌展示）— v15 重構版
==========================================
薄殼 Flask 層：業務邏輯全部收斂到 version8/rag_api.RAGSystem
（完整雙軌管線 + 子圖擷取 + 證據片段），本檔只負責 HTTP 與初始化狀態。

啟動：
  conda activate financial_crawler
  python3 app.py          # → http://localhost:5002
（需要 vLLM 服務 http://127.0.0.1:8000 提供意圖路由與生成）
"""

import json
import sys
import threading
from pathlib import Path

from flask import Flask, jsonify, request, render_template

BASE    = Path(__file__).resolve().parent
V8_ROOT = BASE.parent
sys.path.insert(0, str(V8_ROOT))

app = Flask(__name__)

# ── RAGSystem 惰性初始化（背景執行緒；約 30–60 秒）──────────────────────────
CTX: dict = {"rag": None, "ready": False, "error": None, "stage": "尚未開始"}


def _init_resources() -> None:
    try:
        CTX["stage"] = "載入 RAGSystem（向量庫/Embedder/精確索引/圖譜）…"
        from rag_api import RAGSystem
        CTX["rag"] = RAGSystem(embed_device="cpu")
        CTX["stage"] = "就緒"
        CTX["ready"] = True
    except Exception as e:                                   # noqa: BLE001
        CTX["error"] = f"{type(e).__name__}: {e}"
        CTX["stage"] = "初始化失敗"


threading.Thread(target=_init_resources, daemon=True).start()


# ── API ───────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status")
def status():
    return jsonify({"ready": CTX["ready"], "stage": CTX["stage"], "error": CTX["error"]})


@app.route("/api/examples")
def examples():
    """從 arch100_v2 各路由 + 純口語 natural 集抽幾題當範例。"""
    out: list[dict] = []
    try:
        arch = json.loads((V8_ROOT / "questions" /
                           "system_architecture_test_questions_100_v4.json").read_text(encoding="utf-8"))
        by_route: dict[str, list] = {}
        for x in arch:
            route = x.get("metadata", {}).get("target_route", "")
            key = ("graph" if route.startswith("graph_rag")
                   else "vector" if "vector" in route or "semantic" in route
                   else "direct")
            by_route.setdefault(key, []).append(x)
        for key, label in (("direct", "數值直查"), ("graph", "關係直查"), ("vector", "向量降級")):
            for x in by_route.get(key, [])[:3]:
                out.append({"route": label, "question": x["question"]})
        nat = json.loads((V8_ROOT / "questions" /
                          "customer_colloquial_natural_100.json").read_text(encoding="utf-8"))
        for x in nat[:3]:
            out.append({"route": "口語", "question": x["question"]})
    except Exception:                                        # noqa: BLE001
        pass
    return jsonify(out)


@app.route("/api/ask")
def ask():
    question = request.args.get("q", "").strip()
    if not question:
        return jsonify({"error": "missing ?q= parameter"}), 400
    if CTX["error"]:
        return jsonify({"error": "初始化失敗", "detail": CTX["error"]}), 503
    if not CTX["ready"]:
        return jsonify({"error": "系統初始化中", "stage": CTX["stage"]}), 503
    return jsonify(CTX["rag"].ask(question))


@app.errorhandler(Exception)
def handle_exception(e):                                     # noqa: ANN001
    return jsonify({"error": type(e).__name__, "detail": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", use_reloader=False, port=5002)
