#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
候選歧義分層（第二份 held-out）之評分與報告。

為何要獨立一支評分器
──────────────────
`rag_test_system_v14._score_one()` 的 `exact_match` 是正規化後**字串相等**；其唯一
的集合比對路徑被 `_RISK_LABEL_VOCAB` 綁死在風險標籤上（`:5049`）。本分層之金標是
「全部候選之集合」，順序由資料列序決定，字串 EM 會把只是順序不同的正確答案判成
0。故在**報告層**另算集合 EM，並**同時報字串 EM**——兩者差距即順序／格式造成的
低估。受測系統 `rag_test_system_v14.py` 一字未改，其雜湊仍與 manifest 相符。

評分規則（預註冊，凍結後不得更動）
────────────────────────────────
  set_em    以 [｜|;；,，、] 切分系統答案為集合，與 metadata.expected_set 之集合
            相等則為 1（順序無關；相等，非鬆散包含）
  coverage  |預測 ∩ 金標| / |金標|，用以區分「全錯」與「只答出其中一個」
  string_em 沿用系統之 scores.exact_match，原樣報告

用法
────
    python3 report_heldout_ambig.py [--eval results/heldout2/eval_heldout_ambig_60.json]
"""
from __future__ import annotations
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# 主要規則：只以各題 metadata 宣告之 set_delimiter（｜）切分。
# 凍結時的分析計畫誤寫成 [｜|;；,，、]，該字元集包含「；」——但「；」是元素**內部**
# 的分隔符（"中游；生產製程及檢測設備"），用它切分會把每個元素拆碎，量到的不是集合
# 相等而是碎片相等。此為規則自相矛盾（同一份 metadata 同時宣告 set_delimiter="｜"），
# 故依修訂 B1 改正，並**同時報告凍結原規則之數字**以供對照。
SPLIT_RE = re.compile(r"[｜|]\s*")
SPLIT_RE_FROZEN = re.compile(r"[｜|;；,，、]\s*")


def _arg(flag: str, default: str) -> str:
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default


def norm(s: str) -> str:
    """與系統 _normalize 同語意的輕量正規化：去空白、全形括號統一、去尾標點。"""
    s = str(s).strip()
    s = s.replace("（", "(").replace("）", ")").replace("　", " ")
    s = re.sub(r"\s+", "", s)
    return s.strip("。.,，、;；")


def to_set(text: str, rx=SPLIT_RE) -> set:
    return {norm(t) for t in rx.split(str(text)) if norm(t)}


# metadata.target_route → 子分層名（資料集已凍結，question_type 未落在 eval 紀錄裡，
# 故以同樣凍結於 metadata 的 target_route 分群）
ROUTE_TO_STRATUM = {
    "graph_rag_investment": "investment_ambiguous",
    "graph_rag_supply_chain": "supply_chain_ambiguous",
}
# 關係人列舉分層（第三份）之兩個子分層共用同一 target_route，改以 listed_dimension 區分。
DIM_TO_STRATUM = {
    "交易對象(value_2)": "rp_counterparty_ambiguous",
    "交易科目(value_4)": "rp_account_ambiguous",
}


def stratum_of(md: dict) -> str:
    d = str(md.get("listed_dimension", ""))
    if d in DIM_TO_STRATUM:
        return DIM_TO_STRATUM[d]
    return ROUTE_TO_STRATUM.get(str(md.get("target_route", "")), "unknown")


def main() -> None:
    ep = ROOT / _arg("--eval", "results/heldout2/eval_heldout_ambig_60.json")
    if not ep.exists():
        raise SystemExit(f"[中止] 找不到評測結果：{ep}\n"
                         f"       請先執行 run_heldout2_eval.sh")
    data = json.loads(ep.read_text(encoding="utf-8"))
    recs = data if isinstance(data, list) else (
        data.get("results") or data.get("details") or data.get("records") or [])

    rows, by_type = [], defaultdict(list)
    for r in recs:
        md = r.get("metadata") or {}
        if md.get("answer_semantics") != "set":
            continue
        gold = {norm(x) for x in (md.get("expected_set") or [])}
        pred = to_set(r.get("answer", ""))
        gold_f = to_set(r.get("expected_answer", ""), SPLIT_RE_FROZEN)
        pred_f = to_set(r.get("answer", ""), SPLIT_RE_FROZEN)
        inter = pred & gold
        row = {
            "id": r.get("id"),
            "question_type": stratum_of(md),
            "n_candidates": md.get("n_candidates"),
            "set_em": int(bool(gold) and pred == gold),
            "set_em_frozen_rule": int(bool(gold_f) and pred_f == gold_f),
            "coverage": (len(inter) / len(gold)) if gold else 0.0,
            "n_predicted": len(pred),
            "string_em": int(bool((r.get("scores") or {}).get("exact_match"))),
            "answer_mode": r.get("answer_mode"),
            "question": r.get("question", "")[:60],
            "answer": str(r.get("answer", ""))[:80],
        }
        rows.append(row)
        by_type[row["question_type"]].append(row)

    if not rows:
        raise SystemExit("[中止] 結果檔中沒有 answer_semantics=set 的題目。")

    def agg(rs):
        n = len(rs)
        return {"n": n,
                "set_em_pct": round(sum(r["set_em"] for r in rs) / n * 100, 1),
                "set_em_frozen_rule_pct": round(
                    sum(r["set_em_frozen_rule"] for r in rs) / n * 100, 1),
                "string_em_pct": round(sum(r["string_em"] for r in rs) / n * 100, 1),
                "coverage_pct": round(sum(r["coverage"] for r in rs) / n * 100, 1),
                "平均候選數": round(sum(r["n_candidates"] or 0 for r in rs) / n, 2)}

    overall = agg(rows)
    per = {k: agg(v) for k, v in sorted(by_type.items())}

    print("═══ 候選歧義分層（A 案：全部列出才算對）═══")
    print(f"{'子分層':26}{'題數':>5}{'集合EM':>9}{'原規則':>9}{'字串EM':>9}"
          f"{'覆蓋率':>9}{'平均候選':>10}")
    for k, a in per.items():
        print(f"{k:26}{a['n']:>5}{a['set_em_pct']:>8.1f}%"
              f"{a['set_em_frozen_rule_pct']:>8.1f}%{a['string_em_pct']:>8.1f}%"
              f"{a['coverage_pct']:>8.1f}%{a['平均候選數']:>10.2f}")
    print(f"{'合計':26}{overall['n']:>5}{overall['set_em_pct']:>8.1f}%"
          f"{overall['set_em_frozen_rule_pct']:>8.1f}%{overall['string_em_pct']:>8.1f}%"
          f"{overall['coverage_pct']:>8.1f}%{overall['平均候選數']:>10.2f}")

    out = ROOT / _arg("--out", "results/heldout2/ambig_report.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"overall": overall, "by_type": per,
                               "per_question": rows},
                              ensure_ascii=False, indent=2), encoding="utf-8")

    md = ["# 候選歧義分層評測（第二份 held-out）", "",
          "金標語意 **A：全部列出才算對**（集合相等、順序無關）。評分規則於量測前隨",
          "`heldout2_prereg_manifest.json` 一併凍結；受測系統未修改。", "",
          "| 子分層 | 題數 | 集合 EM | 集合 EM(凍結原規則) | 字串 EM | 覆蓋率 | 平均候選數 |",
          "|---|---:|---:|---:|---:|---:|---:|"]
    for k, a in per.items():
        md.append(f"| {k} | {a['n']} | {a['set_em_pct']}% | "
                  f"{a['set_em_frozen_rule_pct']}% | {a['string_em_pct']}% | "
                  f"{a['coverage_pct']}% | {a['平均候選數']} |")
    md.append(f"| **合計** | {overall['n']} | **{overall['set_em_pct']}%** | "
              f"{overall['set_em_frozen_rule_pct']}% | {overall['string_em_pct']}% | "
              f"{overall['coverage_pct']}% | {overall['平均候選數']} |")
    md += ["", "## 逐題", "",
           "| id | 子分層 | 候選數 | 集合EM | 覆蓋率 | 系統答案 |",
           "|---|---|---:|:--:|---:|---|"]
    for r in rows:
        md.append(f"| {r['id']} | {r['question_type']} | {r['n_candidates']} | "
                  f"{'✓' if r['set_em'] else '✗'} | {r['coverage']*100:.0f}% | "
                  f"{r['answer']} |")
    # .md 與 .json 同名（僅副檔名不同）。早期版本把 .md 寫死為 "ambig_report.md"，
    # 使不同 --out 的兩次執行互相覆蓋 .md（見修訂 B5／C2）。
    md_path = out.with_suffix(".md")
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"\n→ {out.relative_to(ROOT)} / {md_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
