#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
確定性雙軌架構：凍結資料之統計合併與等價性檢核
================================================
**不重新執行任何推論**。本腳本只讀既有的評測結果檔，做兩件事：

  (A) 統計合併：把原第三軌（圖譜 Layer 0）的命中數與正確數併入
      「軌道一 確定性直查軌」，重新輸出各資料集的雙軌分布與逐軌 EM。
      合併依據：`llm_contract.track_of()` 的 answer_mode → 軌道對照表。

  (B) 等價性檢核：證明「下架線上圖遍歷」對凍結資料的 EM 影響為 0。
      檢核兩件事——
        1. 全題庫 602 道關係題 100% 由 Layer 0 攔下（讀 answer_mode_and_multihop.json）
        2. 唯一真正落入拓撲層的 6 題，EM 全為 0；故移除該層不會扣掉任何一分

**answer_mode 標籤的處理**：凍結結果檔寫入的 `graph_rag_topology` /
`graph_rag_local` 是舊版由 `query_type` 推斷的標籤，與實際命中層無關
（見附錄 B.5 之標註修正）。修正後的實測顯示，除 held-out 口語題中 6 題外，
其餘關係題全數由 Layer 0 答出。本腳本據此把 `graph_rag_*` 歸入軌道一，
並將該 6 題（id 明列於 answer_mode_and_multihop.json）單獨列為
「線上圖遍歷（已下架）」，不混入軌道一。

    python3 report_dual_track.py [--out results/dual_track_summary]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import llm_contract as C

ROOT = Path(__file__).resolve().parent
AMM = ROOT / "results" / "answer_mode_and_multihop.json"

# 論文引用之凍結評測檔（節次 → 標籤、路徑）
DATASETS: list[tuple[str, str, str]] = [
    ("§4.4", "實驗三 架構測試 100（最終資料 ＋Fix 16）",
     "results/rerun/eval_arch100_v2_fix16.json"),
    ("§4.4", "實驗三 架構測試 100（原始資料集 ＋Fix 16）",
     "results/rerun/eval_arch100_orig_fix16.json"),
    ("§4.5", "實驗四 口語化 100（v2 補充資訊版）",
     "results/rerun/eval_colloq100_v2_regress_fix16.json"),
    ("§3.13", "關係能力題 30（explicit）",
     "results/rerun/eval_graphcap_v3.json"),
    ("§3.13", "關係自然路由題 30",
     "results/rerun/eval_graphnat30_v3.json"),
    ("§3.14", "自然語句路由 100",
     "results/rerun/eval_gnat100.json"),
    ("附錄B", "held-out 架構 100", "results/heldout/eval_heldout_arch_100.json"),
    ("附錄B", "held-out 口語 100", "results/heldout/eval_heldout_colloq_100.json"),
    ("附錄B", "held-out 口語自然 100",
     "results/heldout/eval_heldout_colloq_nat_100.json"),
    ("附錄B", "held-out 關係能力 30",
     "results/heldout/eval_heldout_graph_cap_30.json"),
    ("附錄B", "held-out 關係自然 30",
     "results/heldout/eval_heldout_graph_nat_30.json"),
    ("§4.3", "實驗二 混合路由 60（消融對照）",
     "../legacy_v12/rag_evaluation_v12_full.json"),
]

TRACK_ZH = {
    "deterministic_lookup":   "軌道一 確定性直查",
    "vector_fallback":        "軌道二 語意向量",
    "no_evidence":            "無證據拒答",
    "llm_only":               "純 LLM（消融）",
    "online_graph_traversal": "線上圖遍歷（已下架）",
    "unknown":                "未知標記",
}

# 軌道一之內部分支：數值事實 vs 關係事實
NUMERIC_MODES = {"direct_lookup"}


def topology_exception_ids() -> set[str]:
    """真正落入線上拓撲層之題目 id（不得併入軌道一）。"""
    if not AMM.exists():
        return set()
    d = json.loads(AMM.read_text(encoding="utf-8"))
    return {it["id"] for it in d.get("topology_in_heldout", {}).get("items", [])}


def classify(item: dict, exceptions: set[str]) -> tuple[str, str]:
    """回傳 (軌道, 分支)。分支僅對軌道一有意義：numeric / relation。"""
    mode = str(item.get("answer_mode", ""))
    if item.get("id") in exceptions:
        return "online_graph_traversal", "topology"
    track = C.track_of(mode)
    if track == "online_graph_traversal":
        # 舊標籤 graph_rag_topology 但不在例外清單 → 實為 Layer 0 命中（附錄 B.5）
        track = "deterministic_lookup"
    branch = ("numeric" if mode in NUMERIC_MODES else
              "relation" if track == "deterministic_lookup" else "-")
    return track, branch


def summarize(path: Path, exceptions: set[str]) -> dict | None:
    if not path.exists():
        return None
    d = json.loads(path.read_text(encoding="utf-8"))
    items = d.get("results", d if isinstance(d, list) else [])
    if not items:
        return None

    tracks: dict[str, dict[str, int]] = {}
    branches: dict[str, dict[str, int]] = {}
    for it in items:
        em = bool(it.get("scores", {}).get("exact_match"))
        tr, br = classify(it, exceptions)
        t = tracks.setdefault(tr, {"n": 0, "exact": 0})
        t["n"] += 1
        t["exact"] += int(em)
        if tr == "deterministic_lookup":
            b = branches.setdefault(br, {"n": 0, "exact": 0})
            b["n"] += 1
            b["exact"] += int(em)

    n = len(items)
    exact = sum(1 for it in items if it.get("scores", {}).get("exact_match"))
    for grp in (tracks, branches):
        for v in grp.values():
            v["exact_rate"] = round(v["exact"] / v["n"], 4) if v["n"] else 0.0
    return {
        "file": str(path),
        "n": n,
        "em": round(exact / n, 4) if n else 0.0,
        "em_count": exact,
        "tracks": tracks,
        "track1_branches": branches,
        "answer_mode_dist_frozen": d.get("summary", {}).get("answer_mode_dist"),
    }


def equivalence_check(exceptions: set[str]) -> dict:
    """下架線上圖遍歷對凍結資料之 EM 影響。"""
    out: dict = {"layer0_interception": None, "topology_items": [],
                 "em_lost_by_removal": 0}
    if AMM.exists():
        d = json.loads(AMM.read_text(encoding="utf-8"))
        out["layer0_interception"] = d.get("layer0_interception")
        out["multihop_probe"] = {
            k: d.get("multihop_probe", {}).get(k)
            for k in ("n", "reached_topology", "em", "avg_latency_sec")
        }
    for _, _, rel in DATASETS:
        p = ROOT / rel
        if not p.exists():
            continue
        data = json.loads(p.read_text(encoding="utf-8"))
        for it in data.get("results", []):
            if it.get("id") in exceptions:
                em = bool(it.get("scores", {}).get("exact_match"))
                out["topology_items"].append(
                    {"id": it["id"], "file": rel, "exact_match": em})
                out["em_lost_by_removal"] += int(em)
    return out


def markdown(rows: list[dict], eq: dict) -> str:
    L: list[str] = []
    L.append("# 確定性雙軌架構：凍結資料之統計合併\n")
    L.append("> 本表由 `report_dual_track.py` 直接讀取既有評測結果檔產生，"
             "**未重新執行任何推論**。原「圖譜 Layer 0」之命中數與正確數"
             "已併入軌道一（確定性直查軌）。\n")
    L.append("## 一、逐資料集雙軌分布\n")
    L.append("| 節次 | 資料集 | n | EM | 軌道一 n（數值／關係） | 軌道一 EM | "
             "軌道二 n | 軌道二 EM | 其他 |")
    L.append("|---|---|---:|---:|---:|---:|---:|---:|---|")
    for r in rows:
        t1 = r["tracks"].get("deterministic_lookup", {"n": 0, "exact_rate": 0})
        t2 = r["tracks"].get("vector_fallback", {"n": 0, "exact_rate": 0})
        bn = r["track1_branches"].get("numeric", {}).get("n", 0)
        br = r["track1_branches"].get("relation", {}).get("n", 0)
        other = "、".join(
            f"{TRACK_ZH.get(k, k)} {v['n']}"
            for k, v in sorted(r["tracks"].items())
            if k not in ("deterministic_lookup", "vector_fallback")) or "—"
        # n=0 的軌道不列 EM（0.0% 會被誤讀為「全錯」而非「無題目」）
        r1 = f"{t1.get('exact_rate', 0):.1%}" if t1["n"] else "—"
        r2 = f"{t2.get('exact_rate', 0):.1%}" if t2["n"] else "—"
        L.append(
            f"| {r['section']} | {r['label']} | {r['n']} | {r['em']:.1%} | "
            f"{t1['n']}（{bn}／{br}） | {r1} | {t2['n']} | {r2} | {other} |")

    tot_n = sum(r["n"] for r in rows)
    tot_1 = sum(r["tracks"].get("deterministic_lookup", {}).get("n", 0) for r in rows)
    tot_1e = sum(r["tracks"].get("deterministic_lookup", {}).get("exact", 0) for r in rows)
    tot_2 = sum(r["tracks"].get("vector_fallback", {}).get("n", 0) for r in rows)
    tot_2e = sum(r["tracks"].get("vector_fallback", {}).get("exact", 0) for r in rows)
    tot_num = sum(r["track1_branches"].get("numeric", {}).get("n", 0) for r in rows)
    tot_rel = sum(r["track1_branches"].get("relation", {}).get("n", 0) for r in rows)
    L.append("")
    L.append("## 二、合計\n")
    L.append(f"- 總題數：**{tot_n}**")
    L.append(f"- 軌道一（確定性直查）：**{tot_1} 題（{tot_1/tot_n:.1%}）**，"
             f"其中數值事實 {tot_num} 題、關係事實 {tot_rel} 題；"
             f"EM **{tot_1e/tot_1:.1%}**（{tot_1e}/{tot_1}）")
    L.append(f"- 軌道二（語意向量降級）：**{tot_2} 題（{tot_2/tot_n:.1%}）**，"
             f"EM **{tot_2e/tot_2:.1%}**（{tot_2e}/{tot_2}）" if tot_2 else
             "- 軌道二（語意向量降級）：0 題")
    L.append("")
    L.append("## 三、下架線上圖遍歷之等價性檢核\n")
    li = eq.get("layer0_interception") or {}
    if li:
        L.append(f"- 全題庫關係題 {li.get('graph_questions_total')} 題，"
                 f"由 Layer 0 確定性攔下 **{li.get('answered_by_layer0')} 題"
                 f"（{li.get('pct')}%）**")
    L.append(f"- 真正落入線上拓撲層者共 **{len(eq['topology_items'])} 題**，"
             f"其中 EM 正確 **{eq['em_lost_by_removal']} 題**")
    L.append(f"- ⇒ 移除線上圖遍歷後，凍結資料之 EM 變動量為 "
             f"**−{eq['em_lost_by_removal']} 題**")
    mp = eq.get("multihop_probe") or {}
    if mp:
        L.append(f"- 針對性多跳壓測：{mp.get('n')} 題全數落入拓撲層，"
                 f"EM **{mp.get('em')}**，平均延遲 {mp.get('avg_latency_sec')}s"
                 f"（見論文附錄 B.5 與 §5.2 未來工作）")
    return "\n".join(L) + "\n"


def main() -> int:
    out_stem = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv \
        else ROOT / "results" / "dual_track_summary"
    exceptions = topology_exception_ids()
    print(f"線上拓撲層例外題 id（不併入軌道一）：{sorted(exceptions) or '—'}")

    rows: list[dict] = []
    for section, label, rel in DATASETS:
        r = summarize(ROOT / rel, exceptions)
        if r is None:
            print(f"  ⚠ 略過（找不到或無結果）：{rel}")
            continue
        r["section"], r["label"] = section, label
        rows.append(r)
        t1 = r["tracks"].get("deterministic_lookup", {})
        print(f"  ✓ {label:34s} n={r['n']:3d} EM={r['em']:.1%}  "
              f"軌道一 {t1.get('n', 0):3d} 題（EM {t1.get('exact_rate', 0):.1%}）")

    eq = equivalence_check(exceptions)
    payload = {
        "title": "確定性雙軌架構之凍結資料統計合併",
        "note": "未重新執行推論；圖譜 Layer 0 命中已併入軌道一。",
        "datasets": rows,
        "equivalence_check": eq,
    }
    js = Path(f"{out_stem}.json")
    md = Path(f"{out_stem}.md")
    js.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md.write_text(markdown(rows, eq), encoding="utf-8")
    print(f"\n輸出：{js}\n      {md}")
    print(f"移除線上圖遍歷之 EM 影響：−{eq['em_lost_by_removal']} 題")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
