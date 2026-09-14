#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
人工金標核對結果彙整（ingest_gold_verification.py）
====================================================
讀取人工填寫的 `gold`（CSV：#,id,判定,備註），回填
`results/gold_verification_sheet.json` 的 verdict/note 欄，
並產生彙整報告 `results/gold_verification_result.md`。

兩題原判「存疑」係因清單的證據抽取只印前 4 列而截斷，經補齊完整證據後
均可結案為「正確」；本腳本以 RESOLVED 明列，保留原判定並附上結案依據。

用法：python3 ingest_gold_verification.py [--project DIR] [--notes gold]
"""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path

def _arg(f, d):
    return sys.argv[sys.argv.index(f)+1] if f in sys.argv and sys.argv.index(f)+1 < len(sys.argv) else d

ROOT = Path(_arg("--project", ".")).resolve()
NOTES = ROOT / _arg("--notes", "gold")
SHEET = ROOT / "results" / "gold_verification_sheet.json"
OUT = ROOT / "results" / "gold_verification_result.md"

# 原判「存疑」之結案依據（補齊完整證據後確認）
RESOLVED = {
    "ho_arch_086": (
        "正確",
        "清單證據原只印前 4 列而截斷。補齊後：該公司該期該交易人共 12 列，"
        "三元鍵（GWS＋MEMC Sdn Bhd＋進貨）精準命中 **1 列**，唯一性成立，"
        "金額 666,004 取自 value_5，與金標相符。"),
    "ho_graph_nat_030": (
        "正確",
        "清單證據原誤印關係人表。補齊後：來源表確為 "
        "`6223_114Q3_轉投資大陸地區之事業相關資訊.csv`，該期大陸投資共 3 列，"
        "主要業務字串唯一對應「旺矽科技(蘇州)有限公司」，"
        "本期認列投資損益 85,157 相符。"),
}

# 判為「錯誤」者之後續處置
ACTIONS = {
    "ho_arch_077": (
        "已知無效題（題庫污染）",
        "投資題實體欄位被填入語料欄位名（record_type / source_kind / row_text）。"
        "已於 `heldout_contamination.py` 全面偵測並完成敏感度分析："
        "held-out 五組共 18 題、dev `graph_routing_natural_100` 另有 3 題。"
        "依預註冊禁止調參條款不修改已凍結題庫，修正留待第二份孿生集（新種子）。"),
    "arch_test_031": (
        "**新發現**：題幹釘住非當期欄",
        "題問【113Q1】（當期欄應為 2024/3/31）但題幹括號釘住 2023/12/31（前一年底比較欄），"
        "金標亦取自該比較欄。實際當期欄值為 穩懋 0、環球晶圓 13,416,852，與金標 "
        "4,743,834 / 13,745,450 完全不同。`audit_datasets.py` 因「題目明寫欄位」"
        "視為有效消歧而放行（OK_explicit_column 分支）。"),
}


def main() -> int:
    sheet = json.loads(SHEET.read_text(encoding="utf-8"))
    by_no = {r["no"]: r for r in sheet}
    rows = list(csv.DictReader(NOTES.open(encoding="utf-8")))

    mismatch = []
    for r in rows:
        no = int(r["#"])
        verdict = r["判定"].replace("☑", "").strip()
        note = (r.get("備註") or "").strip()
        rec = by_no.get(no)
        if not rec or rec["id"] != r["id"].strip():
            mismatch.append(no)
            continue
        rec["verdict"] = verdict
        rec["note"] = note
        if rec["id"] in RESOLVED:
            rec["verdict_resolved"], rec["resolution"] = RESOLVED[rec["id"]]
    SHEET.write_text(json.dumps(sheet, ensure_ascii=False, indent=2), encoding="utf-8")

    raw = Counter(r["verdict"] for r in sheet if r.get("verdict"))
    final = Counter(r.get("verdict_resolved") or r.get("verdict")
                    for r in sheet if r.get("verdict"))

    L = ["# 金標人工抽樣核對結果（B1–B3）", "",
         f"清單 {len(sheet)} 題，人工填寫來源：`{NOTES.name}`。", "",
         "## 結果彙整", "",
         "| 判定 | 人工原判 | 補證據後結案 |", "|---|---:|---:|"]
    for k in ("正確", "錯誤", "存疑"):
        L.append(f"| {k} | {raw.get(k, 0)} | {final.get(k, 0)} |")
    L += ["", f"**通過率**：{final.get('正確', 0)}/{len(sheet)} "
          f"= {final.get('正確', 0)/len(sheet)*100:.1f}%（結案後）", "",
          "## 原判「存疑」之結案", ""]
    for qid, (v, why) in RESOLVED.items():
        rec = next((r for r in sheet if r["id"] == qid), None)
        if not rec:
            continue
        L += [f"### `{qid}`（#{rec['no']}）→ **{v}**", "",
              f"- 人工備註：{rec.get('note', '')}", f"- 結案依據：{why}", ""]
    L += ["## 判為「錯誤」者與後續處置", ""]
    for qid, (title, why) in ACTIONS.items():
        rec = next((r for r in sheet if r["id"] == qid), None)
        if not rec:
            continue
        L += [f"### `{qid}`（#{rec['no']}，{rec['question_type']}）— {title}", "",
              f"- 人工備註：{rec.get('note', '')}", f"- 查證：{why}", ""]
    L += ["## 抽樣涵蓋", "",
          "| 面向 | 題數 |", "|---|---:|",
          f"| held-out 孿生集 | {sum(1 for r in sheet if r['heldout'])} |",
          f"| dev 開發集 | {sum(1 for r in sheet if not r['heldout'])} |"]
    for t, n in Counter(r["question_type"] for r in sheet).most_common():
        L.append(f"| {t} | {n} |")
    L += ["", "> 抽樣刻意偏向風險最高處：`audit_datasets.py` 對圖譜題只檢查 D3"
          "（金標是否毀損），答案內容完全未經機器驗證；口語詞義映射與"
          "「較高／趨勢」方向亦屬機器無法自我驗證的語意約定。", ""]
    if mismatch:
        L += [f"> ⚠ 編號對應不符：{mismatch}", ""]
    OUT.write_text("\n".join(L), encoding="utf-8")

    print(f"回填 {len(rows)} 題 → {SHEET.name}")
    print("人工原判：", dict(raw))
    print("結案後：  ", dict(final))
    print(f"→ {OUT}")
    return 1 if mismatch else 0


if __name__ == "__main__":
    sys.exit(main())
