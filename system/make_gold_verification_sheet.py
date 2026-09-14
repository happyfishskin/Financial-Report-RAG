#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
金標人工抽樣核對清單（make_gold_verification_sheet.py）— B1–B3
================================================================
自動產生一份 24 題的人工核對清單，並**把核對所需的原始證據一併抽出**，
使人工只需做「比對與判斷」，不必自己去翻 CSV。

抽樣原則（刻意偏向風險最高處，而非均勻抽樣）
────────────────────────────────────────────
B1「自動稽核照不到的題型」：audit_datasets.py 對圖譜題只檢查 D3（金標是否毀損），
   完全沒有驗證答案內容 → 投資／關係人／大陸投資／產業鏈／風險 各抽樣。
B2「語意判斷題」：跨公司「較高」、跨期「趨勢」、口語詞義映射（如「欠了多少錢」
   是否真的該對到負債總計）——這些是機器無法自我驗證的語意約定。
B3「從未經人工看過的 held-out 題」：五組孿生集是新生成的，優先抽驗。

每題輸出：題幹、金標、來源檔、**自動抽出的原始證據列**、以及該題要人工確認什麼。
輸出：results/gold_verification_sheet.md（可列印勾選）
      results/gold_verification_sheet.json（供回填結果後統計）

用法：python3 make_gold_verification_sheet.py [--project DIR] [--n 24]
"""
from __future__ import annotations

import json
import random
import re
import sys
from pathlib import Path

import pandas as pd


def _arg(flag: str, default: str) -> str:
    if flag in sys.argv:
        i = sys.argv.index(flag)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return default


ROOT = Path(_arg("--project", ".")).resolve()
N_TOTAL = int(_arg("--n", "24"))
SEED = 20260725
OUT_MD = ROOT / "results" / "gold_verification_sheet.md"
OUT_JSON = ROOT / "results" / "gold_verification_sheet.json"

FACTS = ROOT / "reports_csv_output" / "__all_company_all_period_numeric_facts.csv"
RP_CSV = ROOT / "related_party_graph_output" / "related_party_transaction_table.csv"
SC_CSV = ROOT / "supply_chain_graph_output" / "company_table.csv"

# (檔案, 是否 held-out)
SOURCES = [
    ("questions/heldout/heldout_arch_100.json", True),
    ("questions/heldout/heldout_colloq_100.json", True),
    ("questions/heldout/heldout_colloq_nat_100.json", True),
    ("questions/heldout/heldout_graph_nat_30.json", True),
    ("questions/system_architecture_test_questions_100_v4.json", False),
    ("questions/customer_colloquial_test_questions_100_v2_v3.json", False),
    ("questions/customer_colloquial_natural_100.json", False),
]

# 抽樣配額：題型 → 題數（合計 = N_TOTAL）
QUOTA = [
    ("investment_graph", 3, "B1 圖譜題（自動稽核只驗 D3）"),
    ("related_party_transaction_graph", 3, "B1 圖譜題（三元主鍵唯一性）"),
    ("mainland_investment_graph", 2, "B1 圖譜題（大陸投資，題型曾被誤標）"),
    ("supply_chain_graph", 2, "B1 圖譜題（單一階段假設）"),
    ("risk_event_graph", 3, "B1 圖譜題（風險標籤集合完整性）"),
    ("cross_company_compare", 2, "B2 語意：「較高」方向"),
    ("cross_period_compare", 2, "B2 語意：「趨勢」方向與當期欄"),
    ("colloquial_period_compare", 1, "B2 語意：口語跨期"),
    ("colloquial_company_compare", 1, "B2 語意：口語跨公司"),
    ("colloquial_natural", 3, "B2 語意：口語詞 → 標準科目之映射"),
    ("direct_numeric_lookup", 1, "B3 對照：結構化直查（風險最低，作為基準）"),
    ("colloquial_single_metric", 1, "B3 對照：口語直查"),
]

# 題庫 → 對應之評測檔（供抽出「系統實際輸出」）
EVAL_OF = {
    "questions/heldout/heldout_arch_100.json":
        "results/heldout/eval_heldout_arch_100.json",
    "questions/heldout/heldout_colloq_100.json":
        "results/heldout/eval_heldout_colloq_100.json",
    "questions/heldout/heldout_colloq_nat_100.json":
        "results/heldout/eval_heldout_colloq_nat_100.json",
    "questions/heldout/heldout_graph_nat_30.json":
        "results/heldout/eval_heldout_graph_nat_30.json",
    "questions/system_architecture_test_questions_100_v4.json":
        "results/rerun/eval_arch100_v4_v3.json",
    "questions/customer_colloquial_test_questions_100_v2_v3.json":
        "results/rerun/eval_colloq100_v2_fix16.json",
    "questions/customer_colloquial_natural_100.json":
        "results/rerun/eval_colloq_nat100_fix16.json",
}

# 已知污染 token（實體欄位被填入 CSV 欄位名 → 該題無效，見 heldout_contamination.py）
BAD_TOKEN = re.compile(
    r"^(record_type|source_kind|row_text|row_json|include_reason|value_number|"
    r"value_type|fiscal_year|source_csv|stock_code|company_name|item_name|"
    r"column_header|value_raw|period|table_name|code|unit|year|quarter|"
    r"source_all_facts_csv|fact_text|row_index)$")


def _contaminated(q: dict) -> list[str]:
    md = q.get("metadata", {}) or {}
    vals = [md.get("investor_name"), md.get("investee_name"), md.get("counterparty"),
            md.get("transacting_party"), md.get("main_business"),
            str(q.get("expected_answer", ""))]
    d = md.get("discriminator")
    if isinstance(d, dict):
        vals.append(str(d.get("value", "")))
    return sorted({str(v).strip() for v in vals
                   if v and BAD_TOKEN.match(str(v).strip())})


CHECK_POINTS = {
    "investment_graph":
        "①鑑別子句（所在地／主要業務）在該公司該期是否**只**對到這一家被投資公司？"
        "②被投資公司名稱是否與原表一致（含法人後綴、大小寫）？",
    "related_party_transaction_graph":
        "①「交易人＋交易對象＋科目」三元鍵在該公司該期是否唯一？"
        "②金額是否取自正確欄位（value_5）而非其他欄？",
    "mainland_investment_graph":
        "①該筆是否確實來自「轉投資大陸地區之事業相關資訊」表？"
        "②「本期認列投資損益」數值與括號負號是否正確？",
    "supply_chain_graph":
        "①該公司是否確實只被分到單一階段（多階段者不應入題）？"
        "②stage／segment 的分號格式是否與系統輸出一致？",
    "risk_event_graph":
        "①該科目在該期對應的風險標籤是否**全部**列出（多標籤以 ; 分隔）？"
        "②標籤順序不影響評分，但集合須完全相同。",
    "cross_company_compare":
        "①兩家的數值是否都取自該期**當期欄**（非去年同期比較欄）？"
        "②（若有）「較高」判定方向是否正確——注意括號代表負數。",
    "cross_period_compare":
        "①兩期是否**各自**取自該期當期欄（同一欄不得套用於兩期）？"
        "②（若有）「趨勢」方向是否正確。",
    "colloquial_period_compare":
        "①同上；②口語題幹是否足以唯一定位該科目。",
    "colloquial_company_compare":
        "①同跨公司題；②口語題幹是否足以唯一定位該科目。",
    "colloquial_natural":
        "①**口語詞與標準科目的映射是否合理**（如「欠了多少錢」→負債總計、"
        "「本業賺多少」→營業利益）？②金標是否為該期當期欄唯一值？",
    "direct_numeric_lookup":
        "①題幹明寫的欄位標頭與金標是否一致？",
    "colloquial_single_metric":
        "①題幹括號內的科目／表／欄位與金標是否一致？",
}


def col_years(c) -> set[int]:
    return {int(y) for y in re.findall(r"(20\d{2})", str(c))}


def roc_ad(p) -> int | None:
    m = re.match(r"^(\d{3})Q([1-4])$", str(p))
    return int(m.group(1)) + 1911 if m else None


def main() -> int:
    rng = random.Random(SEED)
    pools: dict[str, list] = {}
    for rel, is_ho in SOURCES:
        p = ROOT / rel
        if not p.exists():
            continue
        for q in json.loads(p.read_text(encoding="utf-8")):
            q = dict(q)
            q["_src"] = rel
            q["_heldout"] = is_ho
            pools.setdefault(q.get("question_type", "?"), []).append(q)

    facts = pd.read_csv(FACTS, dtype=str, low_memory=False,
                        keep_default_na=False, encoding="utf-8-sig")
    facts.columns = [c.lstrip("﻿") for c in facts.columns]
    rp = pd.read_csv(RP_CSV, dtype=str)
    rp.columns = [c.lstrip("﻿") for c in rp.columns]
    sc = pd.read_csv(SC_CSV, dtype=str)
    sc.columns = [c.lstrip("﻿") for c in sc.columns]

    def evidence(q: dict) -> list[str]:
        """自動抽出人工核對所需的原始證據列。"""
        md = q.get("metadata", {}) or {}
        t = q.get("question_type", "")
        out: list[str] = []
        try:
            if "supply" in t:
                co = md.get("company_name", "")
                r = sc[sc.company_name == co]
                for x in r.itertuples(index=False):
                    out.append(f"company_table.csv: {co} → stage={x.stage} "
                               f"segment={x.segment} market={getattr(x,'market','')}")
                out.append(f"（該公司在表中共 {len(r)} 列；>1 列代表多階段）")
            elif "related_party" in t or "mainland" in t:
                co = md.get("company_name", "")
                per = md.get("quarter", "")
                sub = rp[(rp.report_company_name == co) & (rp.report_period == per)]
                key = (md.get("transacting_party") or md.get("party_or_category")
                       or md.get("investee_name") or "")
                hit = sub[sub.party_or_category.fillna("").str.strip() == str(key).strip()]
                if hit.empty and md.get("main_business"):
                    hit = sub[sub.account == md["main_business"]]
                for x in hit.head(4).itertuples(index=False):
                    out.append(f"來源表={x.source_csv}")
                    out.append(f"  party={x.party_or_category} | account={x.account}")
                    out.append(f"  amount_summary={str(x.amount_summary)[:300]}")
                out.append(f"（同公司同期符合此交易人之列數：{len(hit)}）")
            elif "risk" in t:
                co = md.get("company_name", "")
                per = md.get("quarter", "")
                item = md.get("item_name", "")
                sub = facts[(facts.company_name == co) & (facts.period == per)
                            & (facts.item_name == item)]
                out.append(f"風險標籤（金標）：{q.get('expected_answer')}")
                out.append(f"對應科目於 facts 之列數：{len(sub)}；"
                           f"表別={sorted(set(sub.table_name))[:3]}")
                out.append("→ 請至 risk_event_graph_output 確認該科目該期的"
                           "全部風險標籤是否與金標集合相同")
            elif "investment" in t:
                out.append(f"投資方={md.get('investor_name')} → "
                           f"被投資={md.get('investee_name')}")
                out.append(f"鑑別子句={json.dumps(md.get('discriminator'), ensure_ascii=False)}")
                out.append(f"來源={md.get('source_csv','（見 investment_graph_output）')}")
            else:
                code = md.get("company_code")
                item = md.get("item_name") or md.get("item_canonical")
                tbl = md.get("table_name")
                periods = md.get("periods") or [md.get("quarter")]
                codes = md.get("companies") or [code]
                for c in codes:
                    for per in periods:
                        if not (c and per and item):
                            continue
                        sub = facts[(facts.stock_code == str(c))
                                    & (facts.period == str(per))]
                        ex = sub[sub.item_name == item]
                        if ex.empty:
                            pat = re.escape(str(item)) + r"(?:[^一-鿿]|$)"
                            ex = sub[sub.item_name.str.match(pat, na=False)]
                        if tbl:
                            t2 = ex[ex.table_name == tbl]
                            ex = t2 if not t2.empty else ex
                        ad = roc_ad(per)
                        cur = ex[ex.column_header.apply(lambda x: ad in col_years(x))]
                        nm = facts[facts.stock_code == str(c)]
                        nm = nm.iloc[0].company_name if len(nm) else c
                        out.append(f"[{nm} {per}] 當期欄（{ad} 年）共 {len(cur)} 列：")
                        for x in cur.head(4).itertuples(index=False):
                            out.append(f"    {x.table_name} | {x.column_header} "
                                       f"| {x.value_raw}")
                        other = ex[~ex.index.isin(cur.index)]
                        if len(other):
                            out.append(f"    （非當期欄另有 {len(other)} 列，"
                                       f"例：{other.iloc[0].column_header} = "
                                       f"{other.iloc[0].value_raw}）")
        except Exception as exc:                      # 證據抽取失敗不應中斷出表
            out.append(f"（證據自動抽取失敗：{exc}）")
        return out

    # 各評測檔之「系統實際輸出」
    sysout: dict[str, dict] = {}
    for src, evrel in EVAL_OF.items():
        ep = ROOT / evrel
        if not ep.exists():
            continue
        for r in json.loads(ep.read_text(encoding="utf-8")).get("results", []):
            sysout[f"{src}::{r.get('id')}"] = {
                "answer": str(r.get("answer", "")),
                "em": int(bool((r.get("scores") or {}).get("exact_match"))),
                "mode": r.get("answer_mode", ""),
                "eval_file": evrel,
            }

    picked: list[dict] = []
    for qtype, n, why in QUOTA:
        cands = pools.get(qtype, [])
        if not cands:
            continue
        # held-out 與 dev 各半（held-out 從未人工看過；dev 是主結果的依據，
        # 兩者都必須被抽到，否則其一的金標品質等於沒被人工檢驗過）
        ho = [c for c in cands if c["_heldout"]]
        dv = [c for c in cands if not c["_heldout"]]
        rng.shuffle(ho)
        rng.shuffle(dv)
        n_ho = (n + 1) // 2
        take = ho[:n_ho] + dv[:n - n_ho]
        if len(take) < n:                       # 某一邊不足時以另一邊補滿
            take += [c for c in (ho + dv) if c not in take][:n - len(take)]
        for q in take:
            picked.append({"qtype": qtype, "why": why, "q": q})

    rows = []
    for i, item in enumerate(picked, 1):
        q = item["q"]
        so = sysout.get(f"{q['_src']}::{q.get('id')}", {})
        rows.append({
            "no": i, "id": q.get("id"), "dataset": q["_src"],
            "system_answer": so.get("answer", "（該題庫尚無評測結果）"),
            "system_em": so.get("em"), "answer_mode": so.get("mode", ""),
            "eval_file": so.get("eval_file", ""),
            "contaminated": _contaminated(q),
            "heldout": q["_heldout"], "question_type": item["qtype"],
            "sample_reason": item["why"],
            "question": q.get("question"), "gold": q.get("expected_answer"),
            "metadata": q.get("metadata", {}),
            "evidence": evidence(q),
            "check_points": CHECK_POINTS.get(item["qtype"], ""),
            "verdict": "",       # 人工回填：正確／錯誤／存疑
            "note": "",
        })

    OUT_JSON.write_text(json.dumps(rows, ensure_ascii=False, indent=2),
                        encoding="utf-8")

    L = ["# 金標人工抽樣核對清單（B1–B3）", "",
         f"共 {len(rows)} 題，抽樣種子 {SEED}（可重現）。",
         "抽樣**刻意偏向風險最高處**：自動稽核 `audit_datasets.py` 對圖譜題只檢查 D3",
         "（金標是否毀損），完全沒有驗證答案內容；口語詞義映射與「較高／趨勢」方向",
         "也是機器無法自我驗證的語意約定。held-out 孿生集為新生成、從未經人工檢視，故優先抽驗。", "",
         "**每題提供**：題目、金標、**系統實際輸出**（含 EM 判定與路由）、"
         "以及自動抽出的財報原始欄位／表格證據。", "",
         "**填寫方式**：每題在「判定」欄勾選 `正確` / `錯誤` / `存疑`，需要時在「備註」補充。",
         "填完把結果回填 `results/gold_verification_sheet.json` 的 `verdict` 欄即可統計。", "",
         "> 注意：「EM ✓ 相符」只代表系統輸出與金標字串相同，**不代表金標本身正確**——",
         "> 本次抽驗要驗的正是金標。已知無效題已在標題下標註。", "",
         "## 速覽", "",
         "| # | id | 題型 | 來源 | 金標 | EM |",
         "|---:|---|---|---|---|:--:|"]
    for r in rows:
        em = r["system_em"]
        L.append(f"| {r['no']} | `{r['id']}` | {r['question_type']} | "
                 f"{'held-out' if r['heldout'] else 'dev'} | "
                 f"`{str(r['gold'])[:34]}` | "
                 f"{'—' if em is None else ('✓' if em else '✗')} |")
    L += ["", "---", ""]
    for r in rows:
        tag = "held-out" if r["heldout"] else "dev"
        em = r["system_em"]
        mark = "—" if em is None else ("EM ✓ 相符" if em else "EM ✗ 不符")
        L += [f"## {r['no']:02d}. `{r['id']}`　[{tag}]　{r['question_type']}", ""]
        if r["contaminated"]:
            L += [f"> ⚠ **本題已知無效**：實體欄位被填入語料欄位名 "
                  f"`{'`, `'.join(r['contaminated'])}`，語意上不可回答。"
                  f"金標與系統輸出同源於同一筆損壞資料，故雖判 EM=1 仍屬**假性通過**。"
                  f"請直接記為「錯誤」，毋須細查。", ""]
        L += [f"- **抽樣理由**：{r['sample_reason']}",
              f"- **題庫**：`{r['dataset']}`",
              f"- **評測檔**：`{r['eval_file'] or '—'}`", "",
              "**題目**", "", f"> {r['question']}", "",
              f"**金標（expected_answer）**：`{r['gold']}`", "",
              f"**系統輸出（{mark}｜路由 {r['answer_mode'] or '—'}）**：", "",
              "```", (r["system_answer"][:600] or "（空）"), "```", "",
              "**對應之財報原始欄位／表格**", "", "```"]
        L += (r["evidence"] or ["（無）"])
        L += ["```", "",
              f"**請確認**：{r['check_points']}", "",
              "| 判定 | 備註 |", "|---|---|", "| ☐ 正確　☐ 錯誤　☐ 存疑 |  |", "",
              "---", ""]

    OUT_MD.write_text("\n".join(L), encoding="utf-8")
    print(f"已產生 {len(rows)} 題核對清單")
    from collections import Counter
    print("題型分布：", dict(Counter(r["question_type"] for r in rows)))
    print("held-out / dev：",
          f"{sum(1 for r in rows if r['heldout'])} / "
          f"{sum(1 for r in rows if not r['heldout'])}")
    print(f"→ {OUT_MD}")
    print(f"→ {OUT_JSON}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
