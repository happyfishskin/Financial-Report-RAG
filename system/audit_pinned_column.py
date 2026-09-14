#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D12 稽核：題幹釘住「非當期欄」（audit_pinned_column.py）
=========================================================
由 B1–B3 人工抽樣核對發現（`arch_test_031`）：題目問【113Q1】（當期欄應為
2024/3/31），題幹括號卻釘住 2023/12/31（前一年底比較欄），金標亦取自該比較欄。

`audit_datasets.py` 走到「題目明寫欄位標頭 → 視為有效消歧」的
`OK_explicit_column` 分支即 return，因此這個語意落差**從未被機器偵測到**。

**為何獨立成一支腳本，而不併入 audit_datasets.py**
`verify_docs.py` 會斷言 `results/dataset_audit_after.json` 的 findings 為空；
若把 D12 併入該檔的 findings 流，重跑稽核會使該斷言失敗，連鎖破壞已驗證的
文件一致性鏈。D12 的性質也不同——它**不是金標值錯誤**（題目明寫欄位，答案仍唯一），
而是「題幹期別標籤與答案所屬期別不一致」的**設計層警示**，需人工判斷是否可接受。

輸出：results/pinned_column_audit.json
用法：python3 audit_pinned_column.py [--project DIR]
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

def _arg(f, d):
    return sys.argv[sys.argv.index(f)+1] if f in sys.argv and sys.argv.index(f)+1 < len(sys.argv) else d

ROOT = Path(_arg("--project", ".")).resolve()
OUT = ROOT / "results" / "pinned_column_audit.json"

# (標籤, 題庫, 評測檔)
TARGETS = [
    ("架構 100 題（v4 canonical）", "questions/system_architecture_test_questions_100_v4.json",
     "results/rerun/eval_arch100_v4_v3.json"),
    ("口語化 100 題（v2 修正版）", "questions/customer_colloquial_test_questions_100_v2_v3.json",
     "results/rerun/eval_colloq100_v2_fix16.json"),
    ("錯題回歸 24 題（v2 修正版）", "questions/system_architecture_wrong_questions_dataset_v2_v3.json",
     "results/rerun/eval_wrong24_v2_fix16.json"),
    ("held-out 架構 100 題", "questions/heldout/heldout_arch_100.json",
     "results/heldout/eval_heldout_arch_100.json"),
    ("held-out 口語化 100 題", "questions/heldout/heldout_colloq_100.json",
     "results/heldout/eval_heldout_colloq_100.json"),
    ("held-out 純口語 100 題", "questions/heldout/heldout_colloq_nat_100.json",
     "results/heldout/eval_heldout_colloq_nat_100.json"),
]


def col_years(c) -> set[int]:
    return {int(y) for y in re.findall(r"(20\d{2})", str(c))}


def roc_ad(p) -> int | None:
    m = re.match(r"^(\d{3})Q([1-4])$", str(p))
    return int(m.group(1)) + 1911 if m else None


def main() -> int:
    rows = []
    for label, qrel, erel in TARGETS:
        qp, ep = ROOT / qrel, ROOT / erel
        if not qp.exists():
            continue
        qs = json.loads(qp.read_text(encoding="utf-8"))
        em = {}
        if ep.exists():
            em = {str(r.get("id")): int(bool((r.get("scores") or {}).get("exact_match")))
                  for r in json.loads(ep.read_text(encoding="utf-8"))["results"]}
        hits = []
        for q in qs:
            md = q.get("metadata", {}) or {}
            col = md.get("column_header")
            per = md.get("quarter")
            # 只檢查「單一欄位標頭」且「題幹確實釘住該欄位」者；
            # 跨期題的 dict 型欄位（各期取各期當期欄）本就正確，不在此列
            if not isinstance(col, str) or not col_years(col):
                continue
            ad = roc_ad(per)
            if ad is None or str(col) not in str(q.get("question", "")):
                continue
            if ad in col_years(col):
                continue
            hits.append({"id": q.get("id"), "question_type": q.get("question_type"),
                         "quarter": per, "current_year": ad,
                         "pinned_column": col, "gold": q.get("expected_answer"),
                         "em": em.get(str(q.get("id")))})
        n_em = [h["em"] for h in hits if h["em"] is not None]
        rows.append({"label": label, "dataset": qrel, "n": len(qs),
                     "n_pinned_non_current": len(hits),
                     "pct": round(len(hits) / len(qs) * 100, 1) if qs else 0.0,
                     "em_all_correct": bool(n_em) and all(x == 1 for x in n_em),
                     "em_correct": sum(n_em), "em_scored": len(n_em),
                     "by_type": dict(Counter(h["question_type"] for h in hits)),
                     "items": hits})

    OUT.write_text(json.dumps({"defect": "D12_pinned_non_current_column",
                               "rows": rows}, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print("D12：題幹釘住「非當期欄」\n")
    print(f"{'資料集':<26}{'題數':>6}{'命中':>6}{'占比':>8}   EM")
    for r in rows:
        e = (f"{r['em_correct']}/{r['em_scored']} 全對"
             if r["em_all_correct"] else
             (f"{r['em_correct']}/{r['em_scored']}" if r["em_scored"] else "—"))
        print(f"{r['label']:<24}{r['n']:>6}{r['n_pinned_non_current']:>6}"
              f"{r['pct']:>7.1f}%   {e}")
    print(f"\n→ {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
