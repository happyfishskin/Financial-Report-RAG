#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
100 題架構測試集消歧生成器
===========================
輸入：system_architecture_test_questions_100.json
輸出：system_architecture_test_questions_100_v2.json

僅改寫「同題有多個事實正確答案」的圖譜題（候選列 > 1），在題幹加入唯一鑑別子句；
候選唯一的題目與其他題型（direct lookup / vector / supply_chain / risk_event）原樣保留。

鑑別子句規則（與 generate_wrong_questions_v2.py 一致）：
  投資題    ：所在地 → 主要業務 → 持股比率 → 期末帳面價值（依序取第一個唯一者）
  關係人題  ：交易對手方（value_2）＋ 交易科目（value_4）

標準答案一律不變。
"""

import json
import re
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent
SRC  = BASE / "system_architecture_test_questions_100.json"
DST  = BASE / "system_architecture_test_questions_100_v2.json"

_KV_RE = re.compile(r"(value_\d+)=([^;]+)")
_SUFFIX_RE = re.compile(r"(股份有限公司|\(股\)公司|（股）公司|有限公司|公司)$")


def _kv(amount_summary: str) -> dict[str, str]:
    return {k: v.strip() for k, v in _KV_RE.findall(amount_summary or "")}


def _fmt_num(raw: str) -> str:
    try:
        f = float(str(raw).replace(",", "").strip())
    except ValueError:
        return str(raw)
    return f"{int(f):,}" if f == int(f) else str(f)


def main() -> None:
    data = json.loads(SRC.read_text(encoding="utf-8"))

    ie = pd.read_csv(BASE / "investment_graph_output/graph_edges.csv",
                     dtype=str, keep_default_na=False, encoding="utf-8-sig")
    inodes = pd.read_csv(BASE / "investment_graph_output/graph_nodes.csv",
                         dtype=str, keep_default_na=False, encoding="utf-8-sig")
    nm = dict(zip(inodes["id"], inodes["name"]))
    rpe = pd.read_csv(BASE / "related_party_graph_output/graph_edges.csv",
                      dtype=str, keep_default_na=False, encoding="utf-8-sig")

    out: list[dict] = []
    stats = {"inv_rewritten": 0, "inv_unique": 0,
             "rp_rewritten": 0, "rp_unique": 0, "kept": 0}
    problems: list[str] = []

    for item in data:
        item = dict(item)
        md = dict(item.get("metadata", {}))
        route = md.get("target_route", "")

        if route == "graph_rag_investment":
            co, per = md["company_name"], md["quarter"]
            investor, investee = md["investor_name"], md["investee_name"]
            m = ie[(ie["type"] == "INVESTS_IN")
                   & (ie["report_company_name"] == co)
                   & (ie["report_period"] == per)]
            inv_base = _SUFFIX_RE.sub("", investor)
            m2 = m[m["source"].map(lambda s: nm.get(s, "")).map(
                lambda n: bool(n) and (n in investor or n == inv_base))]
            exp = m2[m2["target"].map(lambda t: nm.get(t, t).strip().lower())
                     == investee.strip().lower()]
            if exp.empty:
                problems.append(f"[{item['id']}] 投資題期望列不存在：{investee!r}（候選 {len(m2)}）")
                out.append(item); continue
            if len(m2) <= 1:
                stats["inv_unique"] += 1
                out.append(item); continue

            er = exp.iloc[0]
            clause = None
            for col, label, numeric in [
                ("location",          "所在地為",       False),
                ("main_business",     "主要業務為",     False),
                ("ownership_percent", "持股比率為",     True),
                ("book_value",        "期末帳面價值為", True),
            ]:
                val = er[col]
                if not str(val).strip():
                    continue
                if (m2[col] == val).sum() == 1:
                    disp = (_fmt_num(val) + ("%" if col == "ownership_percent" else "")) \
                           if numeric else str(val).strip()
                    clause = f"{label}【{disp}】"
                    md["discriminator"] = {"column": col, "value": str(val).strip()}
                    break
            if clause is None:
                problems.append(f"[{item['id']}] 投資題無唯一鑑別欄位（候選 {len(m2)}）")
                out.append(item); continue

            item["question"] = (
                f"根據投資關係圖譜，【{co}】在【{per}】揭露的投資方【{investor}】"
                f"投資了哪一家{clause}的被投資公司？"
            )
            item["metadata"] = md
            stats["inv_rewritten"] += 1

        elif route == "graph_rag_related_party":
            co, per, acc = md["company_name"], md["quarter"], md["account"]
            exp_amt = item["expected_answer"].split("；", 1)[1] \
                      if "；" in item["expected_answer"] else ""
            m = rpe[(rpe["type"] == "HAS_RELATED_PARTY_TRANSACTION")
                    & (rpe["report_company_name"] == co)
                    & (rpe["report_period"] == per)
                    & (rpe["account"] == acc)]
            exp_row = None
            for _, r in m.iterrows():
                if r["amount_summary"] == exp_amt or (exp_amt and exp_amt in r["amount_summary"]):
                    exp_row = r
                    break
            if exp_row is None:
                problems.append(f"[{item['id']}] 關係人題期望列不存在（候選 {len(m)}）")
                out.append(item); continue
            if len(m) <= 1:
                stats["rp_unique"] += 1
                out.append(item); continue

            kv = _kv(exp_row["amount_summary"])
            v2, v4 = kv.get("value_2", ""), kv.get("value_4", "")
            hits = sum(
                1 for _, r in m.iterrows()
                if _kv(r["amount_summary"]).get("value_2", "") == v2
                and _kv(r["amount_summary"]).get("value_4", "") == v4
            )
            if hits != 1:
                problems.append(f"[{item['id']}] 關係人題 v2+v4 鑑別不唯一（{hits}/{len(m)}）")
                out.append(item); continue

            item["question"] = (
                f"根據關係人交易圖譜，【{co}】在【{per}】的【{acc}】中，"
                f"與【{v2}】之間的【{v4}】交易涉及哪個關係人或類別？金額摘要是多少？"
            )
            md["discriminator"] = {"value_2": v2, "value_4": v4}
            item["metadata"] = md
            stats["rp_rewritten"] += 1

        else:
            stats["kept"] += 1
            out.append(item)
            continue

        out.append(item)

    DST.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"已生成 {DST.name}")
    print(f"  投資題：改寫 {stats['inv_rewritten']}，原本唯一 {stats['inv_unique']}")
    print(f"  關係人題：改寫 {stats['rp_rewritten']}，原本唯一 {stats['rp_unique']}")
    print(f"  其他題型原樣保留：{stats['kept']}")
    if problems:
        print("\n⚠️ 無法消歧的題目：")
        for p in problems:
            print(f"  {p}")


if __name__ == "__main__":
    main()
