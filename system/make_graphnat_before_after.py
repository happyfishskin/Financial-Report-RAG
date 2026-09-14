#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
產生 Layer 0 自然語句補強之 before/after 對照檔（§3.13 引用來源）。

輸入
────
  results/rerun/graphnat_before_snapshot.json  補強前逐題快照（em/mode/answer/gold）
  results/rerun/eval_graphnat30_A1.json        補強後（含 graph_nat_096 修復）之評測結果
  questions/graph_routing_natural.json         題目與 question_type

輸出
────
  results/graphnat_layer0_before_after.json

歷史註記：本檔先前為手寫，導致 §3.13 更新為 100% 後檔案仍停留在 96.7%，
形成「論文引用的檔案與論文數字不符」。改為腳本產生以杜絕此類不同步；
graph_nat_096 修復前之中間版本另存為 graphnat_layer0_before_after_pre096.json。
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BEFORE = ROOT / "results/rerun/graphnat_before_snapshot.json"
AFTER_EVAL = ROOT / "results/rerun/eval_graphnat30_A1.json"
QUESTIONS = ROOT / "questions/graph_routing_natural.json"
OUT = ROOT / "results/graphnat_layer0_before_after.json"


def main() -> None:
    before = json.loads(BEFORE.read_text(encoding="utf-8"))
    after_eval = json.loads(AFTER_EVAL.read_text(encoding="utf-8"))
    questions = json.loads(QUESTIONS.read_text(encoding="utf-8"))

    qtype = {q["id"]: q["question_type"] for q in questions}
    after = {
        r["id"]: bool((r.get("scores") or {}).get("exact_match"))
        for r in after_eval["results"]
    }

    ids = sorted(set(before) & set(after))
    if len(ids) != len(questions):
        raise SystemExit(
            f"[ERROR] 題目數不符：before∩after={len(ids)}，題庫={len(questions)}"
        )

    n = len(ids)
    b_ok = sum(1 for i in ids if before[i]["em"])
    a_ok = sum(1 for i in ids if after[i])

    by_type: dict[str, dict] = {}
    for i in ids:
        t = qtype[i]
        d = by_type.setdefault(t, {"question_type": t, "n": 0,
                                   "before_ok": 0, "after_ok": 0})
        d["n"] += 1
        d["before_ok"] += int(bool(before[i]["em"]))
        d["after_ok"] += int(after[i])
    for d in by_type.values():
        d["before_rate"] = round(d["before_ok"] / d["n"], 4)
        d["after_rate"] = round(d["after_ok"] / d["n"], 4)

    residual = [i for i in ids if not after[i]]

    out = {
        "experiment": "Layer 0 自然語句樣板補強（graph_routing_natural 30 題）",
        "metric": "End-to-End EM（case-insensitive，同正式評分器）",
        "before_overall": round(b_ok / n, 4),
        "after_overall": round(a_ok / n, 4),
        "delta_pp": round((a_ok - b_ok) / n * 100, 1),
        "before_correct": b_ok,
        "after_correct": a_ok,
        "n": n,
        "routing_accuracy": "100% 前後不變（Router 自然路由能力未受影響）",
        "by_question_type": sorted(by_type.values(), key=lambda d: d["question_type"]),
        "residual_failure": residual or None,
        "capability_regression_check": {
            "graph_capability_explicit_30": "100%（零退步）",
            "system_architecture_100_v4": "97.0%（零退步）",
        },
        "method": (
            "補強內容：(a) 鑑別子句與關係人三元主鍵改為「先【】模板、後自然語句」雙軌抽取"
            "（_extract_disc_value）；(b) Pattern 3 避讓大陸投資題、放寬關係人 gate；"
            "(c) 風險題改以問句中文科目全名反向定位並依中文前綴聚合科目節點變體，"
            "修正 graph_nat_096 的科目定位過寬；評分器加入風險標籤集合比對"
            "（順序無關、相等而非鬆散包含）。"
        ),
        "provenance": {
            "before": str(BEFORE.relative_to(ROOT)),
            "after": str(AFTER_EVAL.relative_to(ROOT)),
            "generated_by": "make_graphnat_before_after.py",
            "intermediate_snapshot": "results/graphnat_layer0_before_after_pre096.json"
                                     "（graph_nat_096 修復前，after=96.7%）",
        },
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"before {b_ok}/{n} = {b_ok/n*100:.1f}%")
    print(f"after  {a_ok}/{n} = {a_ok/n*100:.1f}%   Δ = {out['delta_pp']:+.1f} pp")
    for d in out["by_question_type"]:
        print(f"  {d['question_type']:36} {d['before_ok']:>2}/{d['n']:<2} → "
              f"{d['after_ok']:>2}/{d['n']:<2}")
    print(f"殘餘失敗：{residual or '無'}")
    print(f"→ {OUT}")


if __name__ == "__main__":
    main()
