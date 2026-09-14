#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修正版錯題資料集生成器
========================
輸入：system_architecture_wrong_questions_dataset.json（24 題）
輸出：system_architecture_wrong_questions_dataset_v2.json

問題：原 100Q 出題器對圖譜題隨機抽樣一列作為標準答案，但題幹缺乏鑑別條件，
      同一題有 2–26 個事實上都正確的答案，EM 無法穩定命中（隨機天花板）。

修正：在題幹加入「唯一鑑別子句」，使每題只有一個正確答案——
  投資題    ：所在地 → 主要業務 → 持股比率 → 期末帳面價值（依序取第一個唯一者）
  關係人題  ：交易對手方（value_2）＋ 交易科目（value_4），已驗證 8/8 唯一
  向量題    ：原本即無歧義，原樣保留

標準答案不變（仍為原出題器抽中的那一列），僅題幹增加鑑別資訊。
"""

import json
import re
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent
SRC  = BASE / "system_architecture_wrong_questions_dataset.json"
DST  = BASE / "system_architecture_wrong_questions_dataset_v2.json"

_KV_RE = re.compile(r"(value_\d+)=([^;]+)")


def _kv(amount_summary: str) -> dict[str, str]:
    return {k: v.strip() for k, v in _KV_RE.findall(amount_summary or "")}


def _fmt_num(raw: str) -> str:
    """'2051269.0' → '2,051,269'；'45.0' → '45.0'（非整數保留小數）。"""
    try:
        f = float(str(raw).replace(",", "").strip())
    except ValueError:
        return str(raw)
    if f == int(f):
        return f"{int(f):,}"
    return str(f)


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
    n_inv = n_rp = n_keep = 0

    for item in data:
        item = dict(item)
        md = dict(item.get("metadata", {}))
        route = md.get("target_route", "")

        # ── 投資題：加入唯一鑑別子句 ─────────────────────────────
        if route == "graph_rag_investment":
            co, per = md["company_name"], md["quarter"]
            investor, investee = md["investor_name"], md["investee_name"]
            m = ie[(ie["type"] == "INVESTS_IN")
                   & (ie["report_company_name"] == co)
                   & (ie["report_period"] == per)]
            inv_base = re.sub(r"(股份有限公司|\(股\)公司|（股）公司|有限公司|公司)$", "", investor)
            m2 = m[m["source"].map(lambda s: nm.get(s, "")).map(
                lambda n: bool(n) and (n in investor or n == inv_base))]
            exp = m2[m2["target"].map(lambda t: nm.get(t, t)) == investee]
            if exp.empty:
                raise SystemExit(f"[{item['id']}] 期望列不存在：{investee!r}")
            er = exp.iloc[0]

            # 依序找第一個唯一鑑別欄位
            clause = None
            for col, label, numeric in [
                ("location",          "所在地為",     False),
                ("main_business",     "主要業務為",   False),
                ("ownership_percent", "持股比率為",   True),
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
                raise SystemExit(f"[{item['id']}] 找不到唯一鑑別欄位！")

            item["question"] = (
                f"根據投資關係圖譜，【{co}】在【{per}】揭露的投資方【{investor}】"
                f"投資了哪一家{clause}的被投資公司？"
            )
            n_inv += 1

        # ── 關係人題：加入對手方＋科目鑑別 ────────────────────────
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
                if r["amount_summary"] == exp_amt or exp_amt in r["amount_summary"]:
                    exp_row = r
                    break
            if exp_row is None:
                raise SystemExit(f"[{item['id']}] 期望列不存在！")
            kv = _kv(exp_row["amount_summary"])
            v2, v4 = kv.get("value_2", ""), kv.get("value_4", "")
            hits = sum(
                1 for _, r in m.iterrows()
                if _kv(r["amount_summary"]).get("value_2", "") == v2
                and _kv(r["amount_summary"]).get("value_4", "") == v4
            )
            if hits != 1:
                raise SystemExit(f"[{item['id']}] v2+v4 鑑別不唯一（{hits}）！")

            item["question"] = (
                f"根據關係人交易圖譜，【{co}】在【{per}】的【{acc}】中，"
                f"與【{v2}】之間的【{v4}】交易涉及哪個關係人或類別？金額摘要是多少？"
            )
            md["discriminator"] = {"value_2": v2, "value_4": v4}
            n_rp += 1

        else:
            n_keep += 1

        item["metadata"] = md
        out.append(item)

    DST.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"已生成 {DST.name}：投資題改寫 {n_inv}、關係人題改寫 {n_rp}、原樣保留 {n_keep}")
    for it in out:
        if "discriminator" in it["metadata"]:
            print(f"  [{it['id']}] {it['question'][:90]}")


if __name__ == "__main__":
    main()
