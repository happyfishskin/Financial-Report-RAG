#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Held-out vs dev 對照報告（report_heldout.py）
==============================================
A3 跑完後執行，把 dev 與 held-out 的評測檔逐組比對，輸出：

  results/heldout_vs_dev.json / results/heldout_vs_dev.md

所有數字皆自評測 JSON 讀出（不硬編），並附：
  · 預註冊預測 vs 實際（是否落在預測區間內）
  · Wilson 95% 信賴區間（n=30 組尤其重要，避免把抽樣噪音當泛化落差）
  · 逐 question_type 分層落差，用以定位是哪一類題型不泛化
  · 主要假說 H_heldout 的判定

用法：python3 report_heldout.py [--project DIR]
"""
from __future__ import annotations

import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path


def _arg(flag: str, default: str) -> str:
    if flag in sys.argv:
        i = sys.argv.index(flag)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return default


ROOT = Path(_arg("--project", ".")).resolve()
RESULTS = ROOT / "results"
HO = RESULTS / "heldout"
MANIFEST = RESULTS / "heldout_prereg_manifest.json"

TAGS = {
    "heldout_arch_100.json": "heldout_arch_100",
    "heldout_colloq_100.json": "heldout_colloq_100",
    "heldout_colloq_nat_100.json": "heldout_colloq_nat_100",
    "heldout_graph_cap_30.json": "heldout_graph_cap_30",
    "heldout_graph_nat_30.json": "heldout_graph_nat_30",
}


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, (c - m) / d) * 100, min(1.0, (c + m) / d) * 100)


def em_flag(rec: dict) -> int:
    s = rec.get("scores") or {}
    for k in ("exact_match", "em"):
        if k in s:
            return int(bool(s[k]))
    return 0


def load_eval(p: Path) -> dict | None:
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def by_type(ev: dict, qfile: Path | None) -> dict[str, tuple[int, int]]:
    """question_type → (correct, n)。題型自題庫取（評測檔未必帶）。"""
    qtype: dict[str, str] = {}
    if qfile and qfile.exists():
        for q in json.loads(qfile.read_text(encoding="utf-8")):
            qtype[str(q.get("id"))] = q.get("question_type", "?")
    agg: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for r in ev.get("results", []):
        t = qtype.get(str(r.get("id")), r.get("question_type", "?"))
        agg[t][0] += em_flag(r)
        agg[t][1] += 1
    return {k: (v[0], v[1]) for k, v in agg.items()}


def main() -> int:
    if not MANIFEST.exists():
        sys.exit(f"[ABORT] 找不到預註冊 manifest：{MANIFEST}")
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))

    rows, missing = [], []
    for twin, tag in TAGS.items():
        d = man["datasets"][twin]
        ho_eval = load_eval(HO / f"eval_{tag}.json")
        if ho_eval is None:
            missing.append(tag)
            continue
        a = ho_eval["summary"]["academic_metrics"]
        n = d["n"]
        k = round(a["em"] * n)
        lo, hi = wilson(k, n)
        dev = d["dev_counterpart"]["dev_em_pct"]
        pred = d["prediction_em_pct"]
        ho_pct = round(a["em"] * 100, 1)
        dev_ev = load_eval(ROOT / d["dev_counterpart"]["eval_json"])
        rows.append({
            "twin": twin, "label": d["label"], "n": n,
            "dev_em_pct": dev, "heldout_em_pct": ho_pct,
            "delta_pp": round(ho_pct - (dev or 0), 1) if dev is not None else None,
            "wilson95": [round(lo, 1), round(hi, 1)],
            "prediction": pred["point"],
            "prediction_interval": pred["interval"],
            "within_prediction": pred["interval"][0] <= ho_pct <= pred["interval"][1],
            "precision": round(a["precision"] * 100, 1),
            "recall": round(a["recall"] * 100, 1),
            "f1": round(a["f1"] * 100, 1),
            "refusals": a["refusal_count"],
            "by_type_heldout": by_type(ho_eval, ROOT / "questions" / "heldout" / twin),
            "by_type_dev": by_type(dev_ev, ROOT / "questions"
                                   / d["dev_counterpart"]["file"]) if dev_ev else {},
        })

    if missing:
        print(f"[warn] 尚未產生評測檔：{', '.join(missing)}（先跑 run_heldout_eval.sh）")
    if not rows:
        return 1

    deltas = [r["delta_pp"] for r in rows if r["delta_pp"] is not None]
    mean_drop = round(-sum(deltas) / len(deltas), 1) if deltas else None
    if mean_drop is None:
        verdict = "無法判定（缺 dev 對照）"
    elif mean_drop < 5:
        verdict = f"平均落差 {mean_drop} pp < 5 pp → 既有修復具跨實例泛化能力"
    elif mean_drop > 15:
        verdict = f"平均落差 {mean_drop} pp > 15 pp → 既有分數主要來自對開發集的過擬合"
    else:
        verdict = f"平均落差 {mean_drop} pp 落在 5–15 pp 預測範圍內"

    out = {"frozen_at_utc": man["frozen_at_utc"], "rows": rows,
           "mean_drop_pp": mean_drop, "hypothesis": man["primary_hypothesis"],
           "verdict": verdict, "missing": missing}
    (RESULTS / "heldout_vs_dev.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    L = ["# Held-out 孿生集 vs 開發集（dev）對照\n",
         f"預註冊凍結時間（UTC）：{man['frozen_at_utc']}\n",
         "| 資料集 | n | dev EM | held-out EM | Δ | Wilson 95% | 預測 | 落在預測區間 |",
         "|---|---:|---:|---:|---:|---|---:|---|"]
    for r in rows:
        L.append(f"| {r['label']} | {r['n']} | "
                 f"{r['dev_em_pct'] if r['dev_em_pct'] is not None else '—'}% | "
                 f"**{r['heldout_em_pct']}%** | "
                 f"{r['delta_pp']:+.1f} pp | "
                 f"{r['wilson95'][0]}–{r['wilson95'][1]}% | "
                 f"{r['prediction']}% | {'✓' if r['within_prediction'] else '✗'} |")
    L += ["", f"**平均落差**：{mean_drop} pp　**判定**：{verdict}\n",
          "## 逐題型分層（held-out）\n"]
    for r in rows:
        L.append(f"### {r['label']}\n")
        L.append("| question_type | dev | held-out |")
        L.append("|---|---:|---:|")
        for t, (c, n) in sorted(r["by_type_heldout"].items()):
            dc, dn = r["by_type_dev"].get(t, (None, None))
            devs = f"{dc}/{dn}" if dn else "—"
            L.append(f"| {t} | {devs} | {c}/{n} |")
        L.append("")
    (RESULTS / "heldout_vs_dev.md").write_text("\n".join(L), encoding="utf-8")

    print("\n".join(L[:4 + len(rows)]))
    print(f"\n平均落差 {mean_drop} pp → {verdict}")
    print(f"\n→ {RESULTS / 'heldout_vs_dev.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
