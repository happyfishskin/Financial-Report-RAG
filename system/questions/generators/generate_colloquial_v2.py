#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
口語測試集消歧生成器
=====================
輸入：customer_colloquial_test_questions_100.json
輸出：customer_colloquial_test_questions_100_v2.json

修正三類「題目本身無唯一答案」的設計缺陷（口語語氣保留，僅補鑑別資訊）：
  1. 投資題（候選>1）  ：句尾補「（我指的是{所在地/主要業務/持股比率/期末帳面價值}為【X】的那一家）」
  2. 關係人題（候選>1）：句尾補「（與【對手方】之間的【科目】交易）」
  3. 產業鏈題（多段）  ：句尾補「（若涵蓋多個階段，請全部列出）」，
                         標準答案改為全部階段去重列舉（原單一答案為隨機抽樣，事實不完整）
  4. 跨公司比較題缺科目：句尾補「（科目：【完整科目名】）」

除產業鏈多段題外，標準答案一律不變。
"""

import json
import re
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent
SRC  = BASE / "customer_colloquial_test_questions_100.json"
DST  = BASE / "customer_colloquial_test_questions_100_v2.json"

_KV_RE = re.compile(r"(value_\d+)=([^;]+)")
_SUFFIX_RE = re.compile(r"(股份有限公司|\(股\)公司|（股）公司|有限公司|公司)$")


def _kv(s: str) -> dict[str, str]:
    return {k: v.strip() for k, v in _KV_RE.findall(s or "")}


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
    scn = pd.read_csv(BASE / "supply_chain_graph_output/graph_nodes.csv",
                      dtype=str, keep_default_na=False, encoding="utf-8-sig")
    sce = pd.read_csv(BASE / "supply_chain_graph_output/graph_edges.csv",
                      dtype=str, keep_default_na=False, encoding="utf-8-sig")

    out: list[dict] = []
    stats: dict[str, int] = {}
    problems: list[str] = []

    def _bump(k: str) -> None:
        stats[k] = stats.get(k, 0) + 1

    for item in data:
        item = dict(item)
        md = dict(item.get("metadata", {}))
        route = md.get("target_route", "")
        q = item["question"]

        # ── 投資題 ───────────────────────────────────────────
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
                problems.append(f"[{item['id']}] 投資期望列不存在")
                out.append(item); continue
            if len(m2) <= 1:
                _bump("inv_unique"); out.append(item); continue
            er = exp.iloc[0]
            clause = None
            for col, label, numeric in [
                ("location",          "所在地為",       False),
                ("main_business",     "主要業務為",     False),
                ("ownership_percent", "持股比率為",     True),
                ("book_value",        "期末帳面價值為", True),
            ]:
                val = er[col]
                if str(val).strip() and (m2[col] == val).sum() == 1:
                    disp = (_fmt_num(val) + ("%" if col == "ownership_percent" else "")) \
                           if numeric else str(val).strip()
                    clause = f"{label}【{disp}】"
                    md["discriminator"] = {"column": col, "value": str(val).strip()}
                    break
            if clause is None:
                problems.append(f"[{item['id']}] 投資無唯一鑑別欄位（{len(m2)} 候選）")
                out.append(item); continue
            item["question"] = q.rstrip("？?") + f"？（我指的是{clause}的那一家）"
            item["metadata"] = md
            _bump("inv_rewritten")

        # ── 關係人題 ─────────────────────────────────────────
        elif route == "graph_rag_related_party":
            co, per, acc = md["company_name"], md["quarter"], md.get("account", "")
            exp_amt = item["expected_answer"].split("；", 1)[1] \
                      if "；" in item["expected_answer"] else ""
            m = rpe[(rpe["type"] == "HAS_RELATED_PARTY_TRANSACTION")
                    & (rpe["report_company_name"] == co)
                    & (rpe["report_period"] == per)
                    & (rpe["account"] == acc)]
            exp_row = None
            for _, r in m.iterrows():
                if r["amount_summary"] == exp_amt or (exp_amt and exp_amt in r["amount_summary"]):
                    exp_row = r; break
            if exp_row is None:
                problems.append(f"[{item['id']}] 關係人期望列不存在（{len(m)} 候選）")
                out.append(item); continue
            if len(m) <= 1:
                _bump("rp_unique"); out.append(item); continue
            kv = _kv(exp_row["amount_summary"])
            v2, v4 = kv.get("value_2", ""), kv.get("value_4", "")
            hits = sum(1 for _, r in m.iterrows()
                       if _kv(r["amount_summary"]).get("value_2", "") == v2
                       and _kv(r["amount_summary"]).get("value_4", "") == v4)
            if v2 and v4 and hits == 1:
                item["question"] = q.rstrip("？?") + f"？（與【{v2}】之間的【{v4}】交易）"
                md["discriminator"] = {"value_2": v2, "value_4": v4}
                item["metadata"] = md
                _bump("rp_rewritten")
            else:
                # fallback：大陸投資/母子公司表無 value_2/value_4 → 以期望列中
                # 任一「在候選間唯一」的 k=v 金額欄位作鑑別（不洩漏關係人名答案）
                pairs = re.findall(r"([^;=]+)=([^;]+)", exp_row["amount_summary"])
                clause = None
                for k, v in pairs:
                    k, v = k.strip(), v.strip()
                    if not k or not v or k in ("value_2",):
                        continue
                    n_hit = sum(1 for _, r in m.iterrows()
                                if f"{k}={v}" in r["amount_summary"])
                    if n_hit == 1:
                        clause = (k, v)
                        break
                if clause is None:
                    problems.append(f"[{item['id']}] 關係人無唯一 k=v 鑑別（{len(m)} 候選）")
                    out.append(item); continue
                k, v = clause
                item["question"] = q.rstrip("？?") + f"？（{k}為【{v}】的那筆）"
                md["discriminator"] = {"kv_key": k, "kv_value": v}
                item["metadata"] = md
                _bump("rp_kv_rewritten")

        # ── 產業鏈題（多段公司 → 全列題）─────────────────────
        elif route == "graph_rag_supply_chain":
            co = md["company_name"]
            cn = scn[scn["name"] == co]
            cids = set(cn["id"])
            m = sce[(sce["type"] == "HAS_COMPANY")
                    & (sce["source"].isin(cids) | sce["target"].isin(cids))]
            combos: list[str] = []
            for _, r in m.iterrows():
                c = f"{r['stage']}；{r['segment']}".strip("；")
                if c and c not in combos:
                    combos.append(c)
            if len(combos) <= 1:
                _bump("sc_unique"); out.append(item); continue
            item["question"] = q.rstrip("？?") + "？（若涵蓋多個階段，請全部列出）"
            item["expected_answer"] = " ｜ ".join(combos)
            md["note_v2"] = "multi-position company; expected rewritten to full enumeration"
            item["metadata"] = md
            _bump("sc_multi_rewritten")

        # ── Direct Lookup 題：科目／表格／欄位標頭注入 ────────────
        # 口語 DL 金標常是「隨機報表列」（如「營收多少？」金標實為附註表某列），
        # 同名科目跨表並存、同期並列多年份欄。一律注入三項鑑別資訊使題目有唯一答案。
        elif route.startswith("direct_lookup"):
            item_full = md.get("item_name", "")
            tbl_name  = md.get("table_name", "")
            col_hdr   = md.get("column_header", "")
            add = ""
            if item_full:
                add += f"（科目：【{item_full}】）"
            if tbl_name:
                add += f"（表：【{tbl_name}】）"
            if col_hdr and col_hdr not in q:
                add += f"（{col_hdr}）"
            if add:
                item["question"] = q.rstrip("。") + add
                md["note_v2"] = "item/table/column injected into stem (was ambiguous)"
                item["metadata"] = md
                _bump(f"{route.split('_')[-1]}_injected")
            else:
                _bump(f"{route.split('_')[-1]}_ok")

        else:
            _bump("kept")

        out.append(item)

    DST.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"已生成 {DST.name}")
    for k, v in sorted(stats.items()):
        print(f"  {k}: {v}")
    if problems:
        print("\n⚠️ 無法消歧：")
        for p in problems:
            print(f"  {p}")


if __name__ == "__main__":
    main()
