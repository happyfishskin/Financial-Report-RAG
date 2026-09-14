#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
圖譜查詢秒數對比測試
=====================
A 組：Neo4j（bolt://localhost:7687）跑 neo4j_graph_demo/questions.py 的 17 題 Cypher
B 組：rag_test_system_v14 內建圖譜引擎（pandas DataFrame + Layer 0 直答，零 LLM）
      跑 questions/system_architecture_test_questions_100_v4.json 的 30 題圖譜題
C 組：參考值 — v14 E2E 圖譜題延遲（含 LLM 路由，取自 results/test_v14_arch100_v2_regress.json）

每題計時方式：1 次冷啟（cold）+ 5 次熱跑（warm，取平均與最小值）。
輸出：console 表格 + results/benchmark_graph_seconds.json
"""

import json
import os
import statistics
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
WARM_RUNS = 5

# ─────────────────────────────────────────────────────────────
# A 組：Neo4j
# ─────────────────────────────────────────────────────────────
def bench_neo4j() -> dict:
    from neo4j import GraphDatabase
    sys.path.insert(0, str(BASE / "neo4j_graph_demo"))
    from questions import QUESTIONS

    t0 = time.perf_counter()
    driver = GraphDatabase.driver("bolt://localhost:7687",
                                  auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "")))
    driver.verify_connectivity()
    connect_ms = (time.perf_counter() - t0) * 1000

    def run(cypher: str) -> tuple[float, int]:
        t = time.perf_counter()
        with driver.session() as s:
            n = len(list(s.run(cypher)))
        return (time.perf_counter() - t) * 1000, n

    rows = []
    for qid, q in QUESTIONS.items():
        cold_ms, n_rows = run(q["cypher"])
        warm = [run(q["cypher"])[0] for _ in range(WARM_RUNS)]
        rows.append({
            "id": qid, "title": q["title"], "category": q["category"],
            "difficulty": q["difficulty"], "rows": n_rows,
            "cold_ms": round(cold_ms, 2),
            "warm_avg_ms": round(statistics.mean(warm), 2),
            "warm_min_ms": round(min(warm), 2),
        })
    driver.close()
    return {"connect_ms": round(connect_ms, 2), "questions": rows}


# ─────────────────────────────────────────────────────────────
# B 組：v14 內建圖譜引擎（Layer 0 直答，零 LLM）
# ─────────────────────────────────────────────────────────────
def bench_v14() -> dict:
    t0 = time.perf_counter()
    sys.path.insert(0, str(BASE))
    import rag_test_system_v14 as v14
    import_s = time.perf_counter() - t0

    t0 = time.perf_counter()
    nodes_df, edges_df = v14._load_all_compiled_graphs()
    load_s = time.perf_counter() - t0

    company_map = v14._build_company_map(v14.REPORTS_ROOT)

    ds = json.loads((BASE / "questions" / "system_architecture_test_questions_100_v4.json")
                    .read_text(encoding="utf-8"))
    graph_qs = [x for x in ds
                if x.get("metadata", {}).get("target_route", "").startswith("graph_rag")]

    rows = []
    for item in graph_qs:
        q = item["question"]
        t = time.perf_counter()
        ans = v14._gkg_pattern_direct_answer(q, {}, company_map)
        cold_ms = (time.perf_counter() - t) * 1000
        warm = []
        for _ in range(WARM_RUNS):
            t = time.perf_counter()
            v14._gkg_pattern_direct_answer(q, {}, company_map)
            warm.append((time.perf_counter() - t) * 1000)
        rows.append({
            "id": item["id"],
            "route": item["metadata"]["target_route"],
            "layer0_hit": ans is not None,
            "cold_ms": round(cold_ms, 2),
            "warm_avg_ms": round(statistics.mean(warm), 2),
            "warm_min_ms": round(min(warm), 2),
        })
    return {
        "import_s": round(import_s, 2),
        "graph_load_s": round(load_s, 2),
        "n_nodes": len(nodes_df), "n_edges": len(edges_df),
        "questions": rows,
    }


# ─────────────────────────────────────────────────────────────
# C 組：v14 E2E 參考延遲（含 LLM 路由與生成）
# ─────────────────────────────────────────────────────────────
def e2e_reference() -> dict:
    f = BASE / "results" / "test_v14_arch100_v2_regress.json"
    if not f.exists():
        return {}
    d = json.loads(f.read_text(encoding="utf-8"))
    recs = d if isinstance(d, list) else d.get("results", [])
    lat = [r["latency_sec"] for r in recs
           if str(r.get("metadata", {}).get("target_route", "")).startswith("graph_rag")
           and r.get("latency_sec") is not None]
    if not lat:
        return {}
    return {
        "n": len(lat),
        "avg_s": round(statistics.mean(lat), 3),
        "median_s": round(statistics.median(lat), 3),
        "min_s": round(min(lat), 3),
        "max_s": round(max(lat), 3),
    }


def main() -> None:
    print("═" * 72)
    print("  圖譜查詢秒數對比測試（cold ＝ 首次；warm ＝ 5 次平均）")
    print("═" * 72)

    print("\n▍A 組：Neo4j Cypher（neo4j_graph_demo 17 題）")
    neo = bench_neo4j()
    print(f"  driver 連線：{neo['connect_ms']} ms")
    print(f"  {'題號':<5}{'類別':<14}{'列數':>6}{'cold(ms)':>11}{'warm均(ms)':>12}{'warm低(ms)':>12}")
    for r in neo["questions"]:
        print(f"  {r['id']:<5}{r['category']:<14}{r['rows']:>6}"
              f"{r['cold_ms']:>11}{r['warm_avg_ms']:>12}{r['warm_min_ms']:>12}")
    neo_w = [r["warm_avg_ms"] for r in neo["questions"]]
    neo_c = [r["cold_ms"] for r in neo["questions"]]
    print(f"  ── 彙總：cold 平均 {statistics.mean(neo_c):.1f} ms ｜ "
          f"warm 平均 {statistics.mean(neo_w):.1f} ms ｜ warm 中位 {statistics.median(neo_w):.1f} ms")

    print("\n▍B 組：v14 內建圖譜引擎 Layer 0（arch100_v2 30 題圖譜題，零 LLM）")
    v = bench_v14()
    print(f"  模組載入：{v['import_s']} s ｜ 圖譜載入：{v['graph_load_s']} s "
          f"（{v['n_nodes']:,} 節點 / {v['n_edges']:,} 邊）")
    by_route: dict[str, list[float]] = {}
    for r in v["questions"]:
        by_route.setdefault(r["route"], []).append(r["warm_avg_ms"])
    print(f"  {'路由':<28}{'題數':>5}{'warm均(ms)':>12}{'warm低(ms)':>12}")
    for route, ms in sorted(by_route.items()):
        lo = min(x["warm_min_ms"] for x in v["questions"] if x["route"] == route)
        print(f"  {route:<28}{len(ms):>5}{statistics.mean(ms):>12.2f}{lo:>12.2f}")
    v_w = [r["warm_avg_ms"] for r in v["questions"]]
    v_c = [r["cold_ms"] for r in v["questions"]]
    hits = sum(r["layer0_hit"] for r in v["questions"])
    print(f"  ── 彙總：cold 平均 {statistics.mean(v_c):.2f} ms ｜ "
          f"warm 平均 {statistics.mean(v_w):.2f} ms ｜ warm 中位 {statistics.median(v_w):.2f} ms "
          f"｜ Layer0 命中 {hits}/{len(v['questions'])}")

    print("\n▍C 組：v14 E2E 參考（含 LLM 路由/生成，取自既有回歸結果）")
    ref = e2e_reference()
    if ref:
        print(f"  圖譜題 {ref['n']} 題 E2E：平均 {ref['avg_s']} s ｜ 中位 {ref['median_s']} s "
              f"｜ 最小 {ref['min_s']} s ｜ 最大 {ref['max_s']} s")
    else:
        print("  （找不到既有 E2E 結果檔，略過）")

    out = {"neo4j": neo, "v14_layer0": v, "v14_e2e_graph_ref": ref,
           "warm_runs": WARM_RUNS}
    (BASE / "results" / "benchmark_graph_seconds.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n已輸出 results/benchmark_graph_seconds.json")


if __name__ == "__main__":
    main()
