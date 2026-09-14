#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Held-out 孿生集驗收（verify_heldout.py）
=========================================
在凍結預註冊 manifest **之前**執行，三道獨立檢查：

  ① 題數與題型分布是否與 dev 對應集完全相同
  ② 與 dev 題庫是否真正不重疊（獨立重算，不採信生成器自身的簿記）
     · 正規化題幹字串
     · 語意主鍵（公司×期別×科目／跨公司對／跨期對／交易三元鍵／被投資公司…）
  ③ 金標缺陷：直接呼叫專案既有的 audit_datasets.py（D1–D11）稽核孿生集

輸出：results/heldout_verification.json（+ 終端摘要）
退出碼 0 表示三項全過，可進行凍結。

用法：
  python3 verify_heldout.py --project <version8> --heldout <heldout 目錄> \
                            [--out <報告路徑>]
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path


def _arg(flag: str, default: str | None = None) -> str | None:
    if flag in sys.argv:
        i = sys.argv.index(flag)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return default


ROOT = Path(_arg("--project", ".")).resolve()
HELDOUT = Path(_arg("--heldout", str(ROOT / "questions" / "heldout"))).resolve()
OUT = Path(_arg("--out", str(HELDOUT.parent.parent / "results"
                             / "heldout_verification.json")))
QDIR = ROOT / "questions"
sys.path.insert(0, str(ROOT))

# 孿生對應關係
TWINS = {
    "heldout_arch_100.json": "system_architecture_test_questions_100_v4.json",
    "heldout_colloq_100.json": "customer_colloquial_test_questions_100_v2_v3.json",
    "heldout_colloq_nat_100.json": "customer_colloquial_natural_100.json",
    "heldout_graph_cap_30.json": "graph_capability_explicit.json",
    "heldout_graph_nat_30.json": "graph_routing_natural.json",
}


def norm_q(text: str) -> str:
    return re.sub(r"[\s　（）()【】]", "", str(text))


def semantic_keys(q: dict) -> set[tuple]:
    """一題可對應多個語意主鍵；只要有任一鍵與 dev 相同即視為重疊。"""
    md = q.get("metadata", {}) or {}
    t = str(q.get("question_type") or "")
    keys: set[tuple] = set()
    code = str(md.get("company_code") or "")
    name = str(md.get("company_name") or "")
    period = str(md.get("quarter") or "")
    item = str(md.get("item_name") or md.get("item_canonical") or "")
    codes = tuple(sorted(str(c) for c in (md.get("companies") or []) if str(c)))
    periods = tuple(sorted(str(p) for p in (md.get("periods") or []) if str(p)))

    if code and period and item:
        keys.add(("dl", code, period, item))
    if codes and period and item:
        keys.add(("cc", codes, period, item))
    if code and len(periods) == 2 and item:
        keys.add(("cp", code, periods, item))
    if md.get("metric") and code and period:
        keys.add(("metric", code, period, str(md["metric"])))
    if "vector" in t and code and period and md.get("table_name"):
        keys.add(("vec", code, period, str(md["table_name"])))

    who = tuple(x for x in (code, name) if x)
    disc = md.get("discriminator")
    disc = disc if isinstance(disc, dict) else {}
    if md.get("investee_name"):
        tag = "ml" if "mainland" in t else "inv"
        for w in who:
            keys.add((tag, w, period, str(md["investee_name"])))
    payer = (md.get("transacting_party") or md.get("party_or_category")
             or md.get("payer"))
    cpty = md.get("counterparty") or disc.get("value_2")
    acct = md.get("account_item") or disc.get("value_4")
    if payer:
        for w in who:
            keys.add(("rp", w, period, str(payer), str(cpty or ""), str(acct or "")))
    if "supply" in t and name:
        keys.add(("sc", name))
    if "risk" in t and item:
        for w in who:
            keys.add(("risk", w, period, item))
    return keys


def check_distribution() -> tuple[list, bool]:
    rows, ok = [], True
    for twin, dev in TWINS.items():
        tp, dp = HELDOUT / twin, QDIR / dev
        td = json.loads(tp.read_text(encoding="utf-8"))
        dd = json.loads(dp.read_text(encoding="utf-8"))
        tc, dc = Counter(q["question_type"] for q in td), Counter(
            q["question_type"] for q in dd)
        same = (len(td) == len(dd)) and (tc == dc)
        ok &= same
        rows.append({"twin": twin, "dev": dev, "n_twin": len(td), "n_dev": len(dd),
                     "types_twin": dict(tc), "types_dev": dict(dc),
                     "distribution_identical": same})
    return rows, ok


def check_disjoint() -> tuple[dict, bool]:
    dev_text, dev_keys = set(), set()
    dev_files = []
    for p in sorted(QDIR.glob("*.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            continue
        dev_files.append(p.name)
        for q in data:
            dev_text.add(norm_q(q.get("question", "")))
            dev_keys |= semantic_keys(q)

    result, ok = {}, True
    twin_text_seen: dict[str, str] = {}
    for twin in TWINS:
        data = json.loads((HELDOUT / twin).read_text(encoding="utf-8"))
        text_hits = [q["id"] for q in data if norm_q(q["question"]) in dev_text]
        key_hits = [q["id"] for q in data if semantic_keys(q) & dev_keys]
        # 孿生集彼此之間亦不得有重複題幹（graph_cap / graph_nat 為同 30 題之
        # 兩種問法，屬設計內的配對，故互相豁免）
        dup = []
        for q in data:
            k = norm_q(q["question"])
            if k in twin_text_seen and not (
                    {twin, twin_text_seen[k]} <= {"heldout_graph_cap_30.json",
                                                  "heldout_graph_nat_30.json",
                                                  "heldout_arch_100.json"}):
                dup.append(q["id"])
            twin_text_seen.setdefault(k, twin)
        good = not text_hits and not key_hits and not dup
        ok &= good
        result[twin] = {"question_text_overlap": text_hits,
                        "semantic_key_overlap": key_hits,
                        "intra_heldout_duplicate": dup, "clean": good}
    result["_dev_corpus"] = {"files": dev_files, "n_text_keys": len(dev_text),
                             "n_semantic_keys": len(dev_keys)}
    return result, ok


def check_gold() -> tuple[dict, bool]:
    """以專案既有 audit_datasets.py 的 D1–D11 規則稽核孿生集。"""
    import audit_datasets as A

    corpus = A.Corpus(A.FACTS)
    per_file: dict[str, dict] = {}
    ok = True
    for twin in TWINS:
        data = json.loads((HELDOUT / twin).read_text(encoding="utf-8"))
        findings: list[dict] = []
        for q in data:
            t = (q.get("question_type") or "").lower()
            A.audit_question_type_consistency(q, findings, twin)
            A.audit_row_index_in_question(q, findings, twin)
            if "period_compare" in t:
                A.audit_period_compare(q, corpus, findings, twin)
            elif "company_compare" in t:
                A.audit_company_compare(q, corpus, findings, twin)
            elif ("graph" in t or "risk" in t or "supply" in t
                  or "investment" in t or "related_party" in t):
                if A.is_corrupt_gold(q.get("expected_answer")):
                    findings.append(dict(dataset=twin, id=q["id"],
                                         defect="D3_corrupt_gold",
                                         detail="圖譜題金標為附註代號或整列傾印"))
            else:
                A.audit_numeric(q, corpus, findings, twin)
        real = [f for f in findings if not str(f["defect"]).startswith("OK_")]
        ok &= not real
        per_file[twin] = {
            "n": len(data), "n_defects": len(real),
            "defect_types": dict(Counter(f["defect"] for f in real)),
            "defects": real[:20],
            "explicit_ok_notes": len(findings) - len(real),
        }
    return per_file, ok


def main() -> int:
    print(f"專案：{ROOT}")
    print(f"孿生集：{HELDOUT}\n")

    print("① 題型分布比對 …")
    dist, ok1 = check_distribution()
    for r in dist:
        print(f"  {'✓' if r['distribution_identical'] else '✗'} "
              f"{r['twin']:30} {r['n_twin']:>3} 題（dev {r['n_dev']}）")

    print("\n② 與 dev 題庫不重疊檢查 …")
    dis, ok2 = check_disjoint()
    print(f"  dev 語料：{len(dis['_dev_corpus']['files'])} 檔、"
          f"{dis['_dev_corpus']['n_text_keys']} 題幹鍵、"
          f"{dis['_dev_corpus']['n_semantic_keys']} 語意鍵")
    for twin in TWINS:
        r = dis[twin]
        print(f"  {'✓' if r['clean'] else '✗'} {twin:30} "
              f"題幹重疊 {len(r['question_text_overlap'])} ｜ "
              f"語意鍵重疊 {len(r['semantic_key_overlap'])} ｜ "
              f"集內重複 {len(r['intra_heldout_duplicate'])}")

    print("\n③ 金標缺陷稽核（audit_datasets.py D1–D11）…")
    gold, ok3 = check_gold()
    for twin, r in gold.items():
        print(f"  {'✓' if r['n_defects'] == 0 else '✗'} {twin:30} "
              f"{r['n_defects']} 個缺陷 {r['defect_types'] or ''}")

    ok = ok1 and ok2 and ok3
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "project": str(ROOT), "heldout_dir": str(HELDOUT),
        "distribution": dist, "disjointness": dis, "gold_audit": gold,
        "all_checks_passed": ok,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{'✓ 三項全過，可凍結。' if ok else '✗ 有未通過項目，不得凍結。'}")
    print(f"→ {OUT}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
