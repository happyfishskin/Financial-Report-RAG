#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
跨公司比率比較測試資料集生成器（實驗七延伸）
================================================
原 `ratio_questions_50.json` 只有「單一公司單一比率」，但實驗七的動機敘述舉的
例子其實是跨公司比較（「聯發科與鴻海的營業利益率誰比較高」）。本生成器補上這個
缺口：每題要求同期別下兩家公司的同一比率，並判斷孰高。

與單公司題的差別在於**錯誤會複合**：一題要算兩次除法，任一次算錯都可能使
「誰比較高」的結論翻轉。故本資料集依兩比率之差距（margin）分層抽樣，
使「結論正確率 vs 差距」可以被量化，而非只看整體平均。

分層（margin = |ratio_A − ratio_B|，單位為百分點）：
    near   : margin < 1.0     ← 最容易因算術誤差翻轉結論
    mid    : 1.0 ≤ margin < 5.0
    far    : margin ≥ 5.0     ← 即使算得不準，結論通常仍正確

金標與單公司題同法：由 Python 以分子/分母直接算出，不經任何 LLM，
且只收兩家公司四個原始金額都能無歧義解析的組合。

輸出：questions/ratio_cross_company_50.json
用法：python3 generate_ratio_cross_company.py
"""

import json
import random
import re
import sys
from collections import Counter
from itertools import combinations
from pathlib import Path

BASE = Path(__file__).resolve().parent      # questions/generators/
Q_DIR = BASE.parent                          # questions/
V8 = Q_DIR.parent                            # version8/
sys.path.insert(0, str(V8))

import rag_test_system_v14 as v14            # noqa: E402

N_QUESTIONS = 50
SEED = 20260724

# 各分層目標題數（合計 50）；不足時由其他層遞補
STRATA = {"near": 18, "mid": 18, "far": 14}
BANDS = (("near", 0.0, 1.0), ("mid", 1.0, 5.0), ("far", 5.0, float("inf")))

TEMPLATES = [
    "{a}和{b}在{q}的{r}誰比較高？",
    "{a}跟{b}比，{q}的{r}哪一家高？",
    "幫我比一下{a}和{b}，{q}的{r}各是多少？誰比較高？",
]


def _to_float(s: str) -> float | None:
    t = str(s).replace(",", "").strip()
    m = re.search(r"-?\d+(?:\.\d+)?", t)
    if not m:
        return None
    v = float(m.group(0))
    return -v if ("(" in t and v > 0) else v


def band_of(margin: float) -> str:
    for name, lo, hi in BANDS:
        if lo <= margin < hi:
            return name
    return "far"


def main() -> None:
    rng = random.Random(SEED)
    facts = v14._load_facts_df(v14.REPORTS_ROOT)
    _, _, deduped = v14._prep_facts_for_gen(facts)
    company_map = v14._build_company_map(v14.REPORTS_ROOT)
    quarters = sorted(facts["period"].unique())

    # ── 先建單公司比率表：(quarter, ratio) -> [ (alias, full, code, ratio值, 分子, 分母) ]
    per_key: dict[tuple[str, str], list[dict]] = {}
    for alias, full in v14._COMPANY_ALIASES.items():
        code = company_map.get(full)
        if not code:
            continue
        for q in quarters:
            for ratio_canon, spec in v14._RATIO_ONTOLOGY.items():
                num_raw = v14._direct_lookup_flex(facts, deduped, full,
                                                  spec["numerator"], q)
                den_raw = v14._direct_lookup_flex(facts, deduped, full,
                                                  spec["denominator"], q)
                if num_raw is None or den_raw is None:
                    continue
                nv, dv = _to_float(num_raw), _to_float(den_raw)
                if nv is None or dv is None or dv == 0:
                    continue
                per_key.setdefault((q, ratio_canon), []).append({
                    "alias": alias, "full": full, "code": code,
                    "ratio_value": round(nv / dv * 100, 2),
                    "numerator_raw": num_raw, "denominator_raw": den_raw,
                })

    # ── 配對成跨公司題，並依 margin 分層
    pool: dict[str, list[dict]] = {b: [] for b, _, _ in BANDS}
    for (q, ratio_canon), rows in per_key.items():
        for a, b in combinations(rows, 2):
            margin = round(abs(a["ratio_value"] - b["ratio_value"]), 2)
            # 完全相同的比率無法判定孰高，排除（金標須唯一）
            if margin == 0:
                continue
            pool[band_of(margin)].append({
                "quarter": q, "ratio": ratio_canon, "a": a, "b": b, "margin": margin,
            })

    print("配對池（依 margin 分層）：",
          {k: len(v) for k, v in pool.items()}, "合計", sum(len(v) for v in pool.values()))

    chosen: list[dict] = []
    for band, target in STRATA.items():
        cands = pool[band]
        rng.shuffle(cands)
        # 層內再依比率類型輪流抽取，避免可用配對較多的比率（如研發費用率）
        # 壟斷樣本；同一 (公司對, 比率) 不重複抽，避免題目高度相似。
        by_ratio: dict[str, list[dict]] = {}
        for c in cands:
            by_ratio.setdefault(c["ratio"], []).append(c)
        seen: set[tuple] = set()
        picked: list[dict] = []
        order = sorted(by_ratio)
        idx = {r: 0 for r in order}
        while len(picked) < target and any(idx[r] < len(by_ratio[r]) for r in order):
            for r in order:
                if len(picked) >= target:
                    break
                lst = by_ratio[r]
                while idx[r] < len(lst):
                    c = lst[idx[r]]
                    idx[r] += 1
                    key = (c["a"]["code"], c["b"]["code"], c["ratio"])
                    if key in seen:
                        continue
                    seen.add(key)
                    picked.append(c)
                    break
        chosen.extend(picked)

    # 不足 50 題時由剩餘配對遞補
    if len(chosen) < N_QUESTIONS:
        rest = [c for b in pool for c in pool[b] if c not in chosen]
        rng.shuffle(rest)
        chosen.extend(rest[: N_QUESTIONS - len(chosen)])
    chosen = chosen[:N_QUESTIONS]
    rng.shuffle(chosen)

    records = []
    for i, c in enumerate(chosen, 1):
        a, b = c["a"], c["b"]
        # 隨機決定題目中的先後順序，避免「先出現者較高」成為可被學到的捷徑
        if rng.random() < 0.5:
            a, b = b, a
        winner = a["alias"] if a["ratio_value"] > b["ratio_value"] else b["alias"]
        spec = v14._RATIO_ONTOLOGY[c["ratio"]]
        tpl = TEMPLATES[i % len(TEMPLATES)]
        records.append({
            "id": f"ratio_xc_{i:03d}",
            "question_type": "ratio_cross_company",
            "question": tpl.format(a=a["alias"], b=b["alias"],
                                   q=c["quarter"], r=c["ratio"]),
            "expected_answer": (f"{a['alias']}: {a['ratio_value']}% ｜ "
                                f"{b['alias']}: {b['ratio_value']}% ｜ 較高: {winner}"),
            "expected_winner": winner,
            "metadata": {
                "target_route": "direct_lookup_multi_company",
                "quarter": c["quarter"],
                "ratio_type": c["ratio"],
                "margin_pp": c["margin"],
                "margin_band": band_of(c["margin"]),
                "numerator_item": spec["numerator"],
                "denominator_item": spec["denominator"],
                "companies": [
                    {"alias": x["alias"], "company_name": x["full"],
                     "company_code": x["code"], "ratio_value": x["ratio_value"],
                     "numerator_raw": x["numerator_raw"],
                     "denominator_raw": x["denominator_raw"]}
                    for x in (a, b)
                ],
            },
        })

    out = Q_DIR / "ratio_cross_company_50.json"
    out.write_text(json.dumps(records, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"已輸出 {out.name}：{len(records)} 題")
    print("  比率類型:", dict(Counter(r["metadata"]["ratio_type"] for r in records)))
    print("  margin 分層:", dict(Counter(r["metadata"]["margin_band"] for r in records)))
    print("  期別數:", len({r["metadata"]["quarter"] for r in records}),
          " 公司數:", len({c["company_code"] for r in records
                          for c in r["metadata"]["companies"]}))
    for r in records[:3]:
        m = r["metadata"]
        print(f"  例: {r['question']}")
        print(f"      → {r['expected_answer']}  (margin {m['margin_pp']} pp / {m['margin_band']})")


if __name__ == "__main__":
    main()
