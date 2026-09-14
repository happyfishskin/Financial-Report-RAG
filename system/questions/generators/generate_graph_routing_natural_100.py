#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自然語句路由大規模評測集生成器（graph_routing_natural_100）
=============================================================
建立 100 題**無【】結構化 token** 的自然問法，同時測 Router 自然路由能力與
端到端答案正確率。涵蓋 prompt_audit_issues.txt §29 要求之各面向：

  investment_graph            自然投資題（以所在地／主要業務鑑別唯一被投資公司）
  related_party_transaction   關係人三元式（交易人＋對象＋科目 → 交易金額）
  mainland_investment_graph   大陸投資（主要業務 → 被投資公司＋本期認列投資損益）
  risk_event_graph            風險分類（含多標籤，如「供應鏈壓力;營運資金壓力」）
  supply_chain_graph          產業鏈階段分類
  cross_company_value         多公司對比（同期同科目，口語問法 → 兩值＋較高）
  cross_period_value          多期間對比（同公司同科目，口語問法 → 兩值＋趨勢）

**每一題金標都在生成時反查來源資料驗證**，且鑑別子句必須唯一定位答案，
故金標零歧義、可達滿分（與純口語 100 題同一方法論）。

輸出：questions/graph_routing_natural_100.json
用法：python3 generate_graph_routing_natural_100.py
"""
from __future__ import annotations

import json
import random
import re
import sys
from collections import defaultdict
from itertools import combinations
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent
Q_DIR = BASE.parent
V8 = Q_DIR.parent
sys.path.insert(0, str(V8))

import rag_test_system_v14 as v14  # noqa: E402

SEED = 20260725
TARGET = {
    "investment_graph": 20,
    "related_party_transaction_graph": 20,
    "mainland_investment_graph": 12,
    "risk_event_graph": 16,        # 內含 ≥4 多標籤
    "supply_chain_graph": 12,
    "cross_company_value": 12,
    "cross_period_value": 8,
}

_PERIOD_RE = re.compile(r"^(\d{3})Q([1-4])$")


def _to_float(s):
    t = str(s).replace(",", "").strip()
    m = re.search(r"-?\d+(?:\.\d+)?", t)
    if not m:
        return None
    v = float(m.group(0))
    return -v if ("(" in str(s) and v > 0) else v


def _roc_ad(period):
    m = _PERIOD_RE.match(str(period))
    return int(m.group(1)) + 1911 if m else None


def _col_years(col):
    return {int(y) for y in re.findall(r"(20\d{2})", str(col))}


# ══════════════════════════════════════════════════════════════
def gen_investment(nodes, edges, rng, n):
    """投資題：以所在地或主要業務唯一鑑別被投資公司。"""
    inv = edges[edges["type"] == "INVESTS_IN"].copy()
    out = []
    groups = list(inv.groupby(["report_company_name", "report_period", "source"]))
    rng.shuffle(groups)
    for (co, period, src), g in groups:
        if len(out) >= n or not co or not period:
            continue
        investor = v14._gkg_resolve_node_name(src, nodes)
        if not investor:
            continue
        for field, label in (("location", "所在地為"), ("main_business", "主要業務為")):
            if field not in g.columns:
                continue
            vc = g[field].fillna("").value_counts()
            uniq = [val for val, c in vc.items() if val and c == 1]
            if not uniq:
                continue
            val = rng.choice(uniq)
            row = g[g[field] == val].iloc[0]
            investee = v14._gkg_resolve_node_name(row["target"], nodes)
            if not investee or len(str(val)) < 3:
                continue
            out.append({
                "question_type": "investment_graph",
                "question": (f"{co}在{period}揭露的投資方{investor}投資了哪一家"
                             f"{label}{val}的被投資公司？"),
                "expected_answer": investee,
                "metadata": {"target_route": "graph_rag_investment",
                             "company_name": co, "quarter": period,
                             "investor_name": investor, "discriminator": f"{label}{val}",
                             "investee_name": investee},
            })
            break
    return out[:n]


def gen_related_party(rp, rng, n):
    """關係人三元式：交易人＋對象＋科目 → 交易金額（唯一）。"""
    sub = rp[rp["amount_summary"].fillna("").str.contains("value_2=", regex=False)].copy()
    kv = re.compile(r"(value_\d+)=([^;]+)")
    out = []
    rows = list(sub.itertuples(index=False))
    rng.shuffle(rows)
    for r in rows:
        if len(out) >= n:
            break
        d = dict(kv.findall(str(r.amount_summary)))
        payer = str(r.party_or_category or "").strip()
        counterparty = d.get("value_2", "").strip()
        account = d.get("value_4", "").strip()
        amount = d.get("value_5", "").strip()
        if not (payer and counterparty and account and amount and _to_float(amount)):
            continue
        # 三元鍵在同公司同期須唯一
        same = sub[(sub.report_stock_id == r.report_stock_id)
                   & (sub.report_period == r.report_period)
                   & (sub.party_or_category.fillna("").str.strip() == payer)
                   & sub.amount_summary.fillna("").str.contains(
                       re.escape(f"value_2={counterparty}"), regex=True)
                   & sub.amount_summary.fillna("").str.contains(
                       re.escape(f"value_4={account}"), regex=True)]
        if len(same) != 1:
            continue
        out.append({
            "question_type": "related_party_transaction_graph",
            "question": (f"{r.report_company_name}在{r.report_period}，{payer}與"
                         f"{counterparty}之間的{account}交易金額是多少？"),
            "expected_answer": amount,
            "metadata": {"target_route": "graph_rag_related_party",
                         "company_name": r.report_company_name,
                         "quarter": r.report_period, "payer": payer,
                         "counterparty": counterparty, "account_item": account},
        })
    return out[:n]


def gen_mainland(rp, rng, n):
    """大陸投資：主要業務唯一 → 被投資公司＋本期認列投資損益。"""
    ml = rp[rp["source_csv"].fillna("").str.contains("大陸", na=False)].copy()
    out = []
    for (co, period), g in ml.groupby(["report_company_name", "report_period"]):
        if len(out) >= n or not co:
            continue
        vc = g["account"].fillna("").value_counts()
        uniq = [b for b, c in vc.items() if b and c == 1 and len(str(b)) >= 4]
        rng.shuffle(uniq)
        for biz in uniq[:1]:
            row = g[g["account"] == biz].iloc[0]
            investee = str(row["party_or_category"] or "").strip()
            m = re.search(r"本期認列投資損益\s*=\s*([^;]+)", str(row["amount_summary"]))
            profit = m.group(1).strip() if m else ""
            if not (investee and profit):
                continue
            out.append({
                "question_type": "mainland_investment_graph",
                "question": (f"{co}在{period}投資之大陸事業中，主要業務為{biz}的"
                             f"被投資公司是哪一家？其本期認列投資損益是多少？"),
                "expected_answer": f"{investee}；本期認列投資損益：{profit}",
                "metadata": {"target_route": "graph_rag_mainland_investment",
                             "company_name": co, "quarter": period,
                             "main_business": biz, "investee_name": investee,
                             "profit_recognised": profit},
            })
    return out[:n]


def gen_risk(nodes, edges, rng, n):
    """風險分類：item → 風險標籤集合（含多標籤）。"""
    ev = nodes[nodes["label"].fillna("") == "RiskEvidence"].copy()
    ev_edges = edges[edges["type"] == "EVIDENCES"]
    tgt_name = {}
    out, multi = [], []
    groups = list(ev.groupby(["company_name", "period", "item_name"]))
    rng.shuffle(groups)
    for (co, period, item), g in groups:
        if not (co and period and item):
            continue
        roc = None
        for p, mm in [(period, _PERIOD_RE.match(str(period)))]:
            roc = p if mm else None
        # period 欄可能為西元 → 轉民國
        roc_period = period if _PERIOD_RE.match(str(period)) else _west_to_roc(period)
        if not roc_period:
            continue
        labels = []
        for eid in g["id"]:
            for t in ev_edges[ev_edges["source"] == eid]["target"]:
                nm = tgt_name.setdefault(t, v14._gkg_resolve_node_name(t, nodes))
                if nm and nm not in labels:
                    labels.append(nm)
        if not labels:
            continue
        zh = re.match(r"[^A-Za-z]*", str(item)).group(0).strip()
        if len(zh) < 3:
            continue
        rec = {
            "question_type": "risk_event_graph",
            "question": (f"{co}在{roc_period}的財務科目{item}被標記為哪一類風險候選？"),
            "expected_answer": ";".join(labels),
            "metadata": {"target_route": "graph_rag_risk_event",
                         "company_name": co, "quarter": roc_period,
                         "item_name": item, "matched_risks": ";".join(labels)},
        }
        (multi if len(labels) > 1 else out).append(rec)
    rng.shuffle(out)
    rng.shuffle(multi)
    # 保證至少 4 題多標籤
    take_multi = multi[:max(4, n // 4)]
    return (take_multi + out)[:n]


def _west_to_roc(period):
    m = re.match(r"(\d{4})Q([1-4])", str(period))
    if m:
        return f"{int(m.group(1)) - 1911}Q{m.group(2)}"
    return str(period) if _PERIOD_RE.match(str(period)) else None


def gen_supply_chain(rng, n):
    # 公司→階段/細分 存於 company_table.csv（一列一公司）
    p = V8 / "supply_chain_graph_output" / "company_table.csv"
    df = pd.read_csv(p, dtype=str)
    df.columns = [c.lstrip("﻿") for c in df.columns]
    # 只收「單一階段」的公司——部分公司同時被分到多段（如辛耘 中游＋下游），
    # 金標無唯一解，依無歧義金標原則排除。
    stage_seg = defaultdict(set)
    for r in df.itertuples(index=False):
        co = str(getattr(r, "company_name", "") or "").strip()
        stage = str(getattr(r, "stage", "") or "").strip()
        seg = str(getattr(r, "segment", "") or "").strip()
        if co and stage and stage.lower() != "nan":
            stage_seg[co].add((stage, seg))
    out, seen = [], set()
    rows = list(df.itertuples(index=False))
    rng.shuffle(rows)
    for r in rows:
        co = str(getattr(r, "company_name", "") or "").strip()
        stage = str(getattr(r, "stage", "") or "").strip()
        seg = str(getattr(r, "segment", "") or "").strip()
        if (not (co and stage) or co in seen or len(co) < 2
                or stage.lower() == "nan" or len(stage_seg.get(co, ())) != 1):
            continue
        seen.add(co)
        ans = f"{stage}；{seg}" if seg and seg.lower() != "nan" else stage
        out.append({
            "question_type": "supply_chain_graph",
            "question": f"{co}在半導體產業鏈裡屬於哪一段？",
            "expected_answer": ans,
            "metadata": {"target_route": "graph_rag_supply_chain",
                         "company_name": co, "stage": stage, "segment": seg},
        })
        if len(out) >= n:
            break
    return out


def gen_value_compare(facts, deduped, company_map, rng, n_co, n_pd):
    """多公司／多期間對比（口語問法 → 兩值＋較高/趨勢），走 direct_lookup。"""
    aliases = list(v14._COMPANY_ALIASES.items())
    quarters = sorted(facts["period"].unique())
    items = ["資產總計 Total assets", "本期淨利（淨損） Profit (loss)",
             "營業收入合計 Total operating revenue"]
    out_co, out_pd = [], []

    def cur_val(code, period, item):
        ad = _roc_ad(period)
        sub = facts[(facts.stock_code == str(code)) & (facts.period == str(period))
                    & (facts.item_name == item)]
        hits = sub[sub.column_header.apply(lambda c: ad in _col_years(c))]
        vals = {str(v) for v in hits.value_raw}
        return list(vals)[0] if len(vals) == 1 else None

    # 跨公司
    tries = 0
    while len(out_co) < n_co and tries < 4000:
        tries += 1
        (a_al, a_full), (b_al, b_full) = rng.sample(aliases, 2)
        ac, bc = company_map.get(a_full), company_map.get(b_full)
        period = rng.choice(quarters)
        item = rng.choice(items)
        va, vb = cur_val(ac, period, item), cur_val(bc, period, item)
        if not (va and vb and ac and bc):
            continue
        fa, fb = _to_float(va), _to_float(vb)
        if fa is None or fb is None or fa == fb:
            continue
        zh = item.split(" ")[0]
        winner = a_al if fa > fb else b_al
        out_co.append({
            "question_type": "cross_company_value",
            "question": f"{a_al}和{b_al}在{period}的{zh}誰比較高？",
            "expected_answer": f"{a_al}: {va} ｜ {b_al}: {vb} ｜ 較高: {winner}",
            "metadata": {"target_route": "direct_lookup_multi_company",
                         "companies": [ac, bc], "quarter": period,
                         "item_name": item},
        })
    # 跨期間
    tries = 0
    while len(out_pd) < n_pd and tries < 4000:
        tries += 1
        al, full = rng.choice(aliases)
        code = company_map.get(full)
        item = rng.choice(items)
        p1, p2 = sorted(rng.sample(quarters, 2))
        v1, v2 = cur_val(code, p1, item), cur_val(code, p2, item)
        if not (v1 and v2 and code):
            continue
        f1, f2 = _to_float(v1), _to_float(v2)
        if f1 is None or f2 is None:
            continue
        zh = item.split(" ")[0]
        trend = "持平" if f1 == f2 else ("上升" if f2 > f1 else "下降")
        out_pd.append({
            "question_type": "cross_period_value",
            "question": f"{al}這兩季({p1}、{p2})的{zh}變化如何？",
            "expected_answer": f"{p1}: {v1} ｜ {p2}: {v2} ｜ 趨勢: {trend}",
            "metadata": {"target_route": "direct_lookup_multi_period",
                         "company_code": code, "periods": [p1, p2],
                         "item_name": item},
        })
    return out_co, out_pd


def main():
    rng = random.Random(SEED)
    nodes, edges = v14._load_all_compiled_graphs()
    rp = pd.read_csv(V8 / "related_party_graph_output"
                     / "related_party_transaction_table.csv", dtype=str)
    rp.columns = [c.lstrip("﻿") for c in rp.columns]
    facts = v14._load_facts_df(v14.REPORTS_ROOT)
    _, _, deduped = v14._prep_facts_for_gen(facts)
    company_map = v14._build_company_map(v14.REPORTS_ROOT)

    parts = []
    parts += gen_investment(nodes, edges, rng, TARGET["investment_graph"])
    parts += gen_related_party(rp, rng, TARGET["related_party_transaction_graph"])
    parts += gen_mainland(rp, rng, TARGET["mainland_investment_graph"])
    parts += gen_risk(nodes, edges, rng, TARGET["risk_event_graph"])
    parts += gen_supply_chain(rng, TARGET["supply_chain_graph"])
    co, pd_ = gen_value_compare(facts, deduped, company_map, rng,
                                TARGET["cross_company_value"],
                                TARGET["cross_period_value"])
    parts += co + pd_

    rng.shuffle(parts)
    records = []
    for i, r in enumerate(parts, 1):
        r["id"] = f"gnat_{i:03d}"
        r["metadata"]["test_purpose"] = "graph_routing_natural_large"
        records.append(r)

    out = Q_DIR / "graph_routing_natural_100.json"
    out.write_text(json.dumps(records, ensure_ascii=False, indent=1), encoding="utf-8")
    from collections import Counter
    print(f"已輸出 {out.name}：{len(records)} 題")
    for t, c in Counter(r["question_type"] for r in records).most_common():
        print(f"  {t:<36} {c}")
    n_multi = sum(1 for r in records if r["question_type"] == "risk_event_graph"
                  and ";" in r["expected_answer"])
    print(f"  其中多標籤風險題：{n_multi}")


if __name__ == "__main__":
    main()
