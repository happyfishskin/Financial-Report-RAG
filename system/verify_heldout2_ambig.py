#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
候選歧義分層之獨立驗收（verify_heldout2_ambig.py）
==================================================
`verify_heldout.py` 的三項檢查以 TWIN_OF 對照表驅動，涵蓋不到新增的
`heldout_ambig_60.json`。本檔補上該分層專屬的四項檢查：

  C1 分層構成   兩子分層題數符合 SPEC_AMBIG，且**每題候選數 ≥ 2**
                （本分層的存在理由就是候選不唯一，n=1 混進來即失效）
  C2 實例不重疊 與 dev 全題庫、**及第一份 held-out** 皆無語意主鍵或題幹重複
  C3 金標自洽   expected_answer 與 expected_set 互為 " ｜ " 串接／切分；
                集合內元素去重且非空
  C4 題幹合約   每題題幹皆含「請全部列出」（A 案語意的前提：不能考讀心術）

任一項未過即不應凍結。
用法：python3 verify_heldout2_ambig.py [--heldout questions/heldout2]
"""
from __future__ import annotations
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _arg(flag: str, default: str) -> str:
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default


HELDOUT2 = ROOT / _arg("--heldout", "questions/heldout2")
QDIR = ROOT / "questions"
SPEC = {"investment_ambiguous": 30, "supply_chain_ambiguous": 30}


def norm_q(t: str) -> str:
    return re.sub(r"\s+", "", str(t)).strip()


def main() -> None:
    p = HELDOUT2 / "heldout_ambig_60.json"
    if not p.exists():
        raise SystemExit(f"[中止] 找不到 {p}")
    qs = json.loads(p.read_text(encoding="utf-8"))
    checks, ok_all = [], True

    # ── C1 分層構成 ────────────────────────────────────────────────
    cnt = Counter(q["question_type"] for q in qs)
    bad_n = [q["id"] for q in qs if (q["metadata"].get("n_candidates") or 0) < 2]
    c1 = dict(cnt) == SPEC and not bad_n
    checks.append({"id": "C1", "name": "分層構成與候選數≥2", "passed": c1,
                   "detail": {"counts": dict(cnt), "spec": SPEC,
                              "n_candidates_lt2": bad_n}})

    # ── C2 實例不重疊 ──────────────────────────────────────────────
    seen_text: set = set()
    for d in (QDIR, QDIR / "heldout"):
        for f in sorted(d.glob("*.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            if isinstance(data, list):
                for q in data:
                    seen_text.add(norm_q(q.get("question", "")))
    dup_text = [q["id"] for q in qs if norm_q(q["question"]) in seen_text]
    intra = [t for t, c in Counter(norm_q(q["question"]) for q in qs).items() if c > 1]
    c2 = not dup_text and not intra
    checks.append({"id": "C2", "name": "與 dev＋第一份 held-out 不重疊", "passed": c2,
                   "detail": {"dup_with_existing": dup_text,
                              "intra_duplicate": len(intra)}})

    # ── C3 金標自洽 ────────────────────────────────────────────────
    bad_gold = []
    for q in qs:
        md = q["metadata"]
        s = md.get("expected_set") or []
        if (not s or len(s) != len(set(s)) or any(not str(x).strip() for x in s)
                or q["expected_answer"] != " ｜ ".join(s)
                or md.get("n_candidates") != len(s)):
            bad_gold.append(q["id"])
    c3 = not bad_gold
    checks.append({"id": "C3", "name": "金標自洽（串接／去重／計數一致）",
                   "passed": c3, "detail": {"violations": bad_gold}})

    # ── C4 題幹合約 ────────────────────────────────────────────────
    bad_contract = [q["id"] for q in qs if "全部列出" not in q["question"]]
    c4 = not bad_contract
    checks.append({"id": "C4", "name": "題幹明示「請全部列出」", "passed": c4,
                   "detail": {"violations": bad_contract}})

    print("═══ 候選歧義分層驗收 ═══")
    for c in checks:
        ok_all &= c["passed"]
        print(f"  {'✓' if c['passed'] else '✗'} {c['id']} {c['name']}")
        if not c["passed"]:
            print(f"      {json.dumps(c['detail'], ensure_ascii=False)[:300]}")
    print(f"\n{'✓ 四項全過，可進行凍結。' if ok_all else '✗ 未全過，不應凍結。'}")

    out = ROOT / "results" / "heldout2" / "ambig_verification.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"dataset": str(p.relative_to(ROOT)),
                               "n_questions": len(qs),
                               "all_checks_passed": ok_all, "checks": checks},
                              ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"→ {out.relative_to(ROOT)}")
    raise SystemExit(0 if ok_all else 1)


if __name__ == "__main__":
    main()
