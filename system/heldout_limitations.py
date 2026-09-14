#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Held-out 結果之限制分析（heldout_limitations.py）
==================================================
A3 跑完後執行，量化並附註一項**孿生集設計上的已知混淆因子**：

  孿生集的金標規則要求「該期當期欄之相異值唯一」，否則整組候選丟棄。
  這保證了金標零缺陷（audit D1–D11 全過），但同時**系統性排除了「列歧義」
  題目**——而 dev 的殘餘失敗恰好集中在該層。因此「held-out ≥ dev」的表面
  數字有一部分來自**難度分層失配**，而非系統變強。

本腳本把 dev 與孿生集依「當期欄是否唯一」分層，算出各層題數與 EM，
輸出同層（like-for-like）對照，並把結果附加到 results/heldout_vs_dev.md。

所有數字皆由語料與評測檔算出，無手寫。
用法：python3 heldout_limitations.py [--project DIR]
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd


def _arg(flag: str, default: str) -> str:
    if flag in sys.argv:
        i = sys.argv.index(flag)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return default


ROOT = Path(_arg("--project", ".")).resolve()
FACTS = ROOT / "reports_csv_output" / "__all_company_all_period_numeric_facts.csv"
REPORT = ROOT / "results" / "heldout_vs_dev.md"
OUT_JSON = ROOT / "results" / "heldout_limitations.json"

# (標籤, dev 題庫, dev 評測檔, 孿生集)
PAIRS = [
    ("架構測試 100 題", "system_architecture_test_questions_100_v4.json",
     "results/rerun/eval_arch100_v4_v3.json", "heldout_arch_100.json"),
    ("口語化 100 題", "customer_colloquial_test_questions_100_v2_v3.json",
     "results/rerun/eval_colloq100_v2_fix16.json", "heldout_colloq_100.json"),
    ("純口語自然 100 題", "customer_colloquial_natural_100.json",
     "results/rerun/eval_colloq_nat100_fix16.json", "heldout_colloq_nat_100.json"),
]

NUMERIC_TYPES = ("direct_numeric_lookup", "cross_company_compare",
                 "cross_period_compare", "colloquial_single_metric",
                 "colloquial_company_compare", "colloquial_period_compare",
                 "colloquial_natural")


def col_years(c) -> set[int]:
    return {int(y) for y in re.findall(r"(20\d{2})", str(c))}


def norm_num(s) -> str | None:
    t = str(s).strip()
    neg = t.startswith("(") and t.endswith(")")
    t = t.strip("()").strip().replace(",", "").replace(" ", "")
    if not re.fullmatch(r"-?\d+(\.\d+)?", t):
        return None
    v = float(t)
    return f"{-abs(v) if neg else v:.4f}"


def main() -> int:
    df = pd.read_csv(FACTS, dtype=str, low_memory=False,
                     keep_default_na=False, encoding="utf-8-sig")
    df.columns = [c.lstrip("﻿") for c in df.columns]
    df = df[df["value_raw"].str.strip() != ""]

    def ambiguous(code, period, item, table) -> bool | None:
        """該（公司,期別,科目[,表]）之當期欄是否對到多個相異值。無法判定回 None。"""
        m = re.match(r"^(\d{3})Q([1-4])$", str(period))
        if not m or not item:
            return None
        ad = int(m.group(1)) + 1911
        sub = df[(df.stock_code == str(code)) & (df.period == str(period))]
        exact = sub[sub.item_name == item]
        if exact.empty:                      # 純口語集存的是科目前綴
            pat = re.escape(str(item)) + r"(?:[^一-鿿]|$)"
            exact = sub[sub.item_name.str.match(pat, na=False)]
        if table:
            t = exact[exact.table_name == table]
            if not t.empty:
                exact = t
        if exact.empty:
            return None
        cur = exact[exact.column_header.apply(lambda c: ad in col_years(c))]
        if cur.empty:
            return None
        return len({norm_num(v) for v in cur.value_raw}) > 1

    def strat(qfile: Path, evfile: Path | None):
        qs = json.loads(qfile.read_text(encoding="utf-8"))
        em = {}
        if evfile and evfile.exists():
            ev = json.loads(evfile.read_text(encoding="utf-8"))
            em = {str(r.get("id")): int(bool((r.get("scores") or {}).get("exact_match")))
                  for r in ev["results"]}
        agg = defaultdict(lambda: [0, 0])
        for q in qs:
            t = q.get("question_type", "")
            if t not in NUMERIC_TYPES:
                continue
            md = q.get("metadata", {}) or {}
            item = md.get("item_name") or md.get("item_canonical")
            table = md.get("table_name")
            if t in ("cross_company_compare", "colloquial_company_compare"):
                ck = [(c, md.get("quarter")) for c in (md.get("companies") or [])]
            elif t in ("cross_period_compare", "colloquial_period_compare"):
                ck = [(md.get("company_code"), p) for p in (md.get("periods") or [])]
            else:
                ck = [(md.get("company_code"), md.get("quarter"))]
            fl = [ambiguous(c, p, item, table) for c, p in ck]
            key = ("無法判定" if any(f is None for f in fl)
                   else ("列歧義" if any(fl) else "當期欄唯一"))
            agg[key][0] += em.get(str(q.get("id")), 0)
            agg[key][1] += 1
        return {k: tuple(v) for k, v in agg.items()}

    rows = []
    for label, devq, deve, twin in PAIRS:
        d = strat(ROOT / "questions" / devq, ROOT / deve)
        h = strat(ROOT / "questions" / "heldout" / twin,
                  ROOT / "results" / "heldout" / f"eval_{Path(twin).stem}.json")
        rows.append({"label": label, "dev_file": devq, "twin_file": twin,
                     "dev_strata": d, "heldout_strata": h})

    OUT_JSON.write_text(json.dumps(rows, ensure_ascii=False, indent=2),
                        encoding="utf-8")

    L = ["", "---", "", "## 限制：難度分層失配（由 heldout_limitations.py 產生）", "",
         "孿生集的金標規則要求「該期**當期欄之相異值唯一**」，否則整組候選丟棄。",
         "此規則保證金標零缺陷（audit D1–D11 全過），但同時**系統性排除了「列歧義」題目**。",
         "dev 的殘餘失敗恰好集中在該層，故「held-out ≥ dev」的表面數字有一部分來自",
         "分層失配，而非系統能力提升。下表把兩邊依同一標準分層後對照：", "",
         "| 資料集 | 分層 | dev 題數 | dev EM | held-out 題數 | held-out EM |",
         "|---|---|---:|---:|---:|---:|"]
    for r in rows:
        for k in ("當期欄唯一", "列歧義", "無法判定"):
            dc, dn = r["dev_strata"].get(k, (0, 0))
            hc, hn = r["heldout_strata"].get(k, (0, 0))
            if dn == 0 and hn == 0:
                continue
            L.append(f"| {r['label']} | {k} | {dn} | "
                     f"{f'{dc/dn*100:.1f}%' if dn else '—'} | {hn} | "
                     f"{f'{hc/hn*100:.1f}%' if hn else '—'} |")
    L += ["",
          "**判讀**：在「當期欄唯一」這一層，dev 與 held-out 可直接比較；",
          "「列歧義」層若孿生集題數為 0，該層的 dev 表現即無對應 held-out 數字，",
          "故**不得**用整體平均宣稱系統在含歧義題上的泛化能力。",
          "",
          "**補救（依 manifest 禁止調參條款）**：不得修改已凍結之孿生集。",
          "應另以新種子產生第二份孿生集，明確納入「列歧義」分層（金標改以",
          "「全部候選值皆可接受」或多參考答案評分），並同時報告兩次數字。", ""]
    with REPORT.open("a", encoding="utf-8") as f:
        f.write("\n".join(L))

    print("\n".join(L[4:]))
    print(f"\n→ 已附加至 {REPORT}")
    print(f"→ {OUT_JSON}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
