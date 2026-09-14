#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
衍生比率指標測試資料集生成器（Fix 14 專用）
===============================================
針對 5 種比率（毛利率／營業利益率／淨利率／負債比率／研發費用率），
逐一用既有 _direct_lookup_flex 查出分子、分母原始金額並在本地直接算出
「真實金標」（round(分子/分母*100, 2)），只收兩個原始金額都能無歧義
解析的組合——避免像先前版本一樣把「金標歧義」和「系統準確率」混在一起。

輸出：questions/ratio_questions_50.json
用法：python3 generate_ratio_questions.py（在本檔所在目錄執行即可）
"""

import json
import random
import re
import sys
from pathlib import Path

BASE  = Path(__file__).resolve().parent          # questions/generators/
Q_DIR = BASE.parent                               # questions/
V8    = Q_DIR.parent                              # version8/
sys.path.insert(0, str(V8))

import rag_test_system_v14 as v14                 # noqa: E402

N_QUESTIONS = 50
SEED        = 20260720

# 公司市場簡稱（與 rag_test_system_v14._COMPANY_ALIASES 一致，用於自然口語問法）
ALIASES = list(v14._COMPANY_ALIASES.keys())

QUESTION_TEMPLATES = {
    "毛利率":     "{co}{q}的毛利率是多少？",
    "營業利益率": "{co}{q}的營業利益率是多少？",
    "淨利率":     "{co}{q}的淨利率是多少？",
    "負債比率":   "{co}{q}的負債比率是多少？",
    "研發費用率": "{co}{q}的研發費用率是多少？",
}
# 實驗七是固定 5 種比率的算術消融；生產用 ratio_ontology 可持續擴充，
# 但不得讓外部新增比率靜默改變既有實驗的自變量與資料分布。
EXPERIMENT_RATIO_TYPES = tuple(QUESTION_TEMPLATES)


def _to_float(s: str) -> float | None:
    t = str(s).replace(",", "").strip()
    m = re.search(r"-?\d+(?:\.\d+)?", t)
    if not m:
        return None
    v = float(m.group(0))
    return -v if ("(" in t and v > 0) else v


def main() -> None:
    rng = random.Random(SEED)
    facts = v14._load_facts_df(v14.REPORTS_ROOT)
    _, _, deduped = v14._prep_facts_for_gen(facts)
    company_map = v14._build_company_map(v14.REPORTS_ROOT)
    quarters = sorted(facts["period"].unique())

    pool: list[dict] = []
    for alias, full in v14._COMPANY_ALIASES.items():
        code = company_map.get(full)
        if not code:
            continue
        for q in quarters:
            for ratio_canon in EXPERIMENT_RATIO_TYPES:
                spec = v14._RATIO_ONTOLOGY[ratio_canon]
                num_raw = v14._direct_lookup_flex(facts, deduped, full, spec["numerator"], q)
                den_raw = v14._direct_lookup_flex(facts, deduped, full, spec["denominator"], q)
                if num_raw is None or den_raw is None:
                    continue
                num_val, den_val = _to_float(num_raw), _to_float(den_raw)
                if num_val is None or den_val is None or den_val == 0:
                    continue
                gold = round(num_val / den_val * 100, 2)
                pool.append({
                    "alias": alias, "full": full, "code": code, "quarter": q,
                    "ratio": ratio_canon, "numerator_raw": num_raw,
                    "denominator_raw": den_raw, "gold_ratio": gold,
                })
    print(f"無歧義比率組合池：{len(pool)} 組")

    by_ratio: dict[str, list[dict]] = {}
    for c in pool:
        by_ratio.setdefault(c["ratio"], []).append(c)
    per = max(1, N_QUESTIONS // len(by_ratio))
    chosen: list[dict] = []
    for ratio_canon, cands in by_ratio.items():
        rng.shuffle(cands)
        chosen.extend(cands[:per])
    rest = [c for c in pool if c not in chosen]
    rng.shuffle(rest)
    while len(chosen) < N_QUESTIONS and rest:
        chosen.append(rest.pop())
    chosen = chosen[:N_QUESTIONS]
    rng.shuffle(chosen)

    records = []
    for i, c in enumerate(chosen, 1):
        tpl = QUESTION_TEMPLATES[c["ratio"]]
        question = tpl.format(co=c["alias"], q=c["quarter"])
        spec = v14._RATIO_ONTOLOGY[c["ratio"]]
        records.append({
            "id": f"ratio_{i:03d}",
            "question": question,
            "expected_ratio": c["gold_ratio"],
            "expected_answer": f"{c['gold_ratio']}%",
            "metadata": {
                "company_alias": c["alias"], "company_name": c["full"],
                "company_code": c["code"], "quarter": c["quarter"],
                "ratio_type": c["ratio"],
                "numerator_item": spec["numerator"], "numerator_raw": c["numerator_raw"],
                "denominator_item": spec["denominator"], "denominator_raw": c["denominator_raw"],
            },
        })

    out = Q_DIR / "ratio_questions_50.json"
    out.write_text(json.dumps(records, ensure_ascii=False, indent=1), encoding="utf-8")
    from collections import Counter
    print(f"已輸出 {out.name}：{len(records)} 題")
    print("比率類型分布:", dict(Counter(r['metadata']['ratio_type'] for r in records)))
    print("公司數:", len({r['metadata']['company_code'] for r in records}))
    for r in records[:5]:
        print(" 例:", r["question"], "→", r["expected_answer"],
              f"(= {r['metadata']['numerator_raw']} / {r['metadata']['denominator_raw']})")


if __name__ == "__main__":
    main()
