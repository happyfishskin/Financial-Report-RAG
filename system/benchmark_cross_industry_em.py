#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
跨產業準確率實測（非半導體三家，114Q2，75 題）
==============================================
把 §3.11 的跨產業檢核由「可行性」推進到「準確率」。既有檢核只證明管線走得通，
本腳本補上金標與 EM，回答論文 §5.2 列為未來工作的那一項。

公平性設計
----------
1. **金標獨立**：取自二維寬表 CSV 儲存格，不經事實索引；並已逐題以原始 HTML 的
   行內 XBRL contextRef 核對（verify_cross_industry_gold.py，75/75 一致）。
2. **零程式修改**：切換資料來源只改 config/system_config.json 的 reports_root，
   即系統既有的領域切換機制；架構程式一行不動（沿用 benchmark_cross_industry_
   feasibility.py 的 _run_with_config 手法，因 _load_facts_df(root) 的 root 參數
   對合併索引路徑不生效）。
3. **領域知識層照舊**：不為這三家新增任何別名或科目同義詞——本測驗要看的正是
   「沒有補領域知識時，架構層本身能走多遠」。
4. **評分沿用系統自己的 _score_one**：與論文其餘 EM 同一把尺（正規化後字串全等）。

只測軌道一的數值直查：題幹已寫明表名與欄位標頭，與半導體 direct_lookup 題型同類，
故可與架構測試的直查子集對照；不宣稱可與含關係題、口語題的整體 EM 直接相比。

    python3 benchmark_cross_industry_em.py [--gold <檔>] [--out <stem>]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_CSV_DIR = ROOT / "_cross_industry_probe" / "reports_csv_output"
# 子行程要有 pandas 等執行期依賴；本檔可用任何直譯器啟動，故不沿用 sys.executable。
PY_ENV = next((p for p in (os.environ.get("PY", ""),
                           sys.executable)
               if p and Path(p).exists()), sys.executable)
GOLD = ROOT / "questions" / "cross_industry_gold_114Q2.json"
OUT = ROOT / "results" / "cross_industry_em"

# 於子行程執行：載入事實索引後逐題查表。只呼叫既有函式，不改架構程式。
RUNNER = r'''
import json, sys
import rag_test_system_v14 as V

gold = json.load(open(sys.argv[1], encoding="utf-8"))
df = V._load_facts_df(V.REPORTS_ROOT)
_s, _e, ded = V._prep_facts_for_gen(df)

names = [str(c) for c in df["company_name"].dropna().unique()]
out = []
for q in gold:
    m = q["metadata"]
    want = m["company_name"]
    comp = next((c for c in names if c.startswith(want[:2])), want)
    tr = {}
    ans = V._lookup_value_or_ratio(
        df, ded, comp, m["item_name"], m["quarter"],
        table_hint=m["table_name"], col_hint=m["column_header"], trace=tr)
    pred = "" if ans is None else str(ans)
    sc = V._score_one(pred, q["expected_answer"])
    out.append({
        "id": q["id"], "company": comp, "industry": m["industry"],
        "table": m["table_name"], "column_kind": m["column_kind"],
        "item": m["item_name"], "expected": q["expected_answer"],
        "predicted": pred, "refused": V._is_refusal(pred) or pred == "",
        "decision": tr.get("decision"), "n_rows": tr.get("n_rows"),
        "n_unique": tr.get("n_unique"),
        "matched_item": tr.get("matched_item"), "matched_col": tr.get("matched_col"),
        "scores": sc,
    })
print("RESULT:" + json.dumps(out, ensure_ascii=False))
'''


def run_with_config(gold_path: Path, csv_dir: Path) -> list[dict]:
    """暫時把 reports_root 指向探針目錄，跑完還原（try/finally 保證）。"""
    cfg_path = ROOT / "config" / "system_config.json"
    backup = cfg_path.read_text(encoding="utf-8")
    try:
        cfg = json.loads(backup)
        cfg["reports_root"] = str(csv_dir.resolve().relative_to(ROOT))
        cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=1),
                            encoding="utf-8")
        r = subprocess.run([PY_ENV, "-c", RUNNER, str(gold_path)],
                           cwd=str(ROOT), capture_output=True, text=True,
                           timeout=1800)
    finally:
        cfg_path.write_text(backup, encoding="utf-8")
        assert cfg_path.read_text(encoding="utf-8") == backup, "設定檔未還原！"
    tail = [ln for ln in (r.stdout or "").splitlines() if ln.startswith("RESULT:")]
    if not tail:
        print((r.stderr or "")[-2500:])
        raise SystemExit("✗ 子行程未輸出 RESULT")
    return json.loads(tail[-1][len("RESULT:"):])


def wilson(k: int, n: int) -> tuple[float, float]:
    """Wilson score 區間（避免 n 小時常態近似失真）。"""
    if n == 0:
        return (0.0, 0.0)
    from math import sqrt
    z, p = 1.959963985, k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(max(0.0, c - h) * 100, 1), round(min(1.0, c + h) * 100, 1))


def group(rows: list[dict], key) -> dict:
    g = defaultdict(list)
    for r in rows:
        g[key(r)].append(r)
    return {k: {"n": len(v),
                "em": round(sum(x["scores"]["exact_match"] for x in v) / len(v), 4),
                "refused": sum(x["refused"] for x in v)}
            for k, v in sorted(g.items())}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gold", type=Path, default=GOLD)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--csv-dir", type=Path, default=DEFAULT_CSV_DIR)
    ap.add_argument("--label", default="跨產業（非半導體三家）")
    a = ap.parse_args()

    gold = json.loads(a.gold.read_text(encoding="utf-8"))
    print(f"金標 {len(gold)} 題（{a.gold.name}）；切換 reports_root 後執行…")
    rows = run_with_config(a.gold, a.csv_dir)

    n = len(rows)
    em_n = sum(r["scores"]["exact_match"] for r in rows)
    num_n = sum(r["scores"]["numeric_match"] for r in rows)
    ref_n = sum(r["refused"] for r in rows)
    lo, hi = wilson(em_n, n)

    # 失效兩段分解：先問有沒有定位到（命中唯一），再問取值對不對
    loc_ok = [r for r in rows if r["decision"] in
              ("hit_unique", "hit_col_hint", "hit_single_quarter")]
    loc_fail = [r for r in rows if r not in loc_ok]
    val_fail = [r for r in loc_ok if not r["scores"]["exact_match"]]

    res = {
        "title": f"準確率實測：{a.label}（114Q2）",
        "scope": ("僅數值直查題（軌道一）；題幹寫明表名與欄位標頭，"
                  "與半導體 direct_lookup 題型同類。未新增任何領域知識設定。"),
        "gold_provenance": {
            "source": "原始二維寬表 CSV 儲存格，未經事實索引",
            "independent_check": "results/cross_industry_gold_verification.json"
                                 "（HTML 行內 XBRL contextRef，75/75 一致）",
            "shared_upstream": "HTML→CSV 解析器（故另以 XBRL 核對）",
        },
        "n": n,
        "em": round(em_n / n, 4), "em_count": em_n, "em_ci95_wilson": [lo, hi],
        "numeric_match": round(num_n / n, 4),
        "refusal_rate": round(ref_n / n, 4), "refused": ref_n,
        "failure_decomposition": {
            "localized": len(loc_ok), "localization_rate": round(len(loc_ok) / n, 4),
            "localization_failed": len(loc_fail),
            "localized_but_value_wrong": len(val_fail),
        },
        "by_company": group(rows, lambda r: f"{r['company']}（{r['industry']}）"),
        "by_table": group(rows, lambda r: f"{r['table']}／{r['column_kind']}"),
        "decision_dist": dict(sorted(
            ((k, sum(1 for r in rows if r["decision"] == k))
             for k in {r["decision"] for r in rows}), key=lambda x: -x[1])),
        "rows": rows,
    }
    a.out.parent.mkdir(exist_ok=True)
    Path(f"{a.out}.json").write_text(json.dumps(res, ensure_ascii=False, indent=2),
                                     encoding="utf-8")

    print(f"\nEM {em_n}/{n} = {em_n/n:.1%}〔{lo}, {hi}〕"
          f"｜數字集合一致 {num_n/n:.1%}｜拒答 {ref_n}")
    print(f"定位率 {len(loc_ok)/n:.1%}；定位成功但取值錯 {len(val_fail)} 題")
    print("\n分公司：")
    for k, v in res["by_company"].items():
        print(f"  {k:<24} n={v['n']:>2}  EM {v['em']:.1%}  拒答 {v['refused']}")
    print("分報表：")
    for k, v in res["by_table"].items():
        print(f"  {k:<22} n={v['n']:>2}  EM {v['em']:.1%}  拒答 {v['refused']}")
    print("判定分佈：", res["decision_dist"])

    bad = [r for r in rows if not r["scores"]["exact_match"]]
    if bad:
        print(f"\n失分 {len(bad)} 題（前 12）：")
        for r in bad[:12]:
            print(f"  {r['id']} [{r['decision']}] {r['table']} {r['item'][:34]}")
            print(f"      金標 {r['expected']}｜系統 {r['predicted'][:44]!r}")
    print(f"\n→ {a.out}.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
