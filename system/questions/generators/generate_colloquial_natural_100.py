#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
純口語化測試資料集生成器（100 題）
===================================
特徵（比 customer_colloquial_v2 更口語）：
  · 公司用市場簡稱（台積電、聯電、聯發科…），不用申報全名
  · 完全沒有【】括號、沒有（科目：…）（表：…）（欄位標頭）提示
  · 口語科目詞（營收 / 賺了多少 / 現金水位 / 欠多少錢 / EPS…）
  · 口語語氣詞與句式變化（幫我看一下 / 欸 / 想知道 / 啊）

金標策略（無歧義保證）：
  對 (公司, 季度, 標準科目, 語意表格) 取「當期西元年欄位」的全部候選值，
  僅當候選值唯一時收錄該組合 → 金標 = 該唯一值。
  （損益表科目在 Q2/Q3 有單季＋累計兩欄 → 自然被排除；資產負債表／
    現金流量表科目全季度可用。）

輸出：questions/customer_colloquial_natural_100.json
用法：python3 generate_colloquial_natural_100.py（在本檔所在目錄執行即可）
"""

import json
import random
import re
from pathlib import Path

import pandas as pd

BASE   = Path(__file__).resolve().parent          # questions/generators/
Q_DIR  = BASE.parent                              # questions/
V8     = Q_DIR.parent                             # version8/
FACTS  = V8 / "reports_csv_output" / "__all_company_all_period_numeric_facts.csv"
OUTPUT = Q_DIR / "customer_colloquial_natural_100.json"

N_QUESTIONS = 100
SEED        = 20260717

# ── 市場簡稱 ↔ 申報全名（與 rag_test_system_v14._COMPANY_ALIASES 一致）────────
COMPANY_ALIASES: dict[str, str] = {
    "台積電":   "台灣積體電路製造",
    "聯電":     "聯華電子",
    "聯發科":   "聯發科技",
    "聯詠":     "聯詠科技",
    "瑞昱":     "瑞昱半導體",
    "南亞科":   "南亞科技",
    "華邦電":   "華邦電子",
    "日月光":   "日月光投資控股",
    "日月光投控": "日月光投資控股",
    "大聯大":   "大聯大控股",
    "世界先進": "世界先進積體電路",
    "力積電":   "力晶積成電子製造",
    "群聯":     "群聯電子",
    "穩懋":     "穩懋半導體",
    "環球晶":   "環球晶圓",
    "京元電":   "京元電子",
    "智原":     "智原科技",
    "景碩":     "景碩科技",
    "京鼎":     "京鼎精密科技",
    "力旺":     "力旺電子",
    "力成":     "力成科技",
    "祥碩":     "祥碩科技",
    "旺矽":     "旺矽科技",
    "辛耘":     "辛耘企業",
    "家登":     "家登精密工業",
    "致茂":     "致茂電子",
    "達興":     "達興材料",
    "中華精測": "中華精測科技",
    "創意電子": "創意電子",     # 已是常用名
    "台灣光罩": "台灣光罩",
    "新應材":   "新應材",
}

# ── 口語科目：標準 CSV 科目前綴 → (語意表格關鍵字, 口語問法模板, metric 標籤)──
# 模板佔位：{co}=公司簡稱 {q}=季度
ITEM_SPECS: list[dict] = [
    {"canonical": "營業收入合計", "table": "損益", "metric": "revenue",
     "templates": [
        "{co}{q}營收多少？", "{co}{q}的營收是多少啊？",
        "想知道{co}在{q}的營業收入有多少", "幫我看一下{co}{q}營收",
        "欸 {co}{q}業績做了多少？"]},
    {"canonical": "本期淨利（淨損）", "table": "損益", "metric": "net_income",
     "templates": [
        "{co}{q}賺了多少錢？", "{co}{q}淨利多少？",
        "幫我查{co}{q}賺多少", "{co}在{q}稅後賺了多少啊？"]},
    {"canonical": "營業毛利（毛損）", "table": "損益", "metric": "gross_profit",
     "templates": [
        "{co}{q}毛利多少？", "幫我看{co}{q}的毛利",
        "{co}在{q}毛利做了多少啊？"]},
    {"canonical": "營業利益（損失）", "table": "損益", "metric": "op_income",
     "templates": [
        "{co}{q}本業賺多少？", "{co}{q}營業利益多少？",
        "想知道{co}{q}本業獲利多少"]},
    {"canonical": "基本每股盈餘（虧損）", "table": "損益", "metric": "eps",
     "templates": [
        "{co}{q}EPS多少？", "{co}{q}每股賺多少？",
        "幫我查一下{co}{q}的每股盈餘"]},
    {"canonical": "資產總計", "table": "資產負債", "metric": "total_assets",
     "templates": [
        "{co}{q}總資產多少？", "{co}在{q}資產規模多大？",
        "幫我看{co}{q}的資產總額"]},
    {"canonical": "負債總計", "table": "資產負債", "metric": "total_liabilities",
     "templates": [
        "{co}{q}總負債多少？", "{co}{q}欠了多少錢？",
        "想知道{co}{q}負債有多少"]},
    {"canonical": "權益總計", "table": "資產負債", "metric": "total_equity",
     "templates": [
        "{co}{q}股東權益多少？", "{co}{q}淨值多少？",
        "幫我查{co}{q}的權益總計"]},
    {"canonical": "現金及約當現金", "table": "資產負債", "metric": "cash",
     "templates": [
        "{co}{q}手上現金有多少？", "{co}{q}現金水位多少？",
        "欸 {co}{q}帳上現金還剩多少啊？", "{co}{q}現金部位多大？"]},
    {"canonical": "營業活動之淨現金流入（流出）", "table": "現金流量", "metric": "cfo",
     "templates": [
        "{co}{q}營業活動現金流多少？", "{co}{q}本業現金流進來多少？",
        "幫我看{co}{q}營運現金流量"]},
]

_ROC_YEAR_RE = re.compile(r"^(\d{3})Q([1-4])$")


def _west_year(roc_q: str) -> str:
    m = _ROC_YEAR_RE.match(roc_q)
    return str(int(m.group(1)) + 1911)


def _load_facts() -> pd.DataFrame:
    df = pd.read_csv(
        FACTS, dtype=str, keep_default_na=False, encoding="utf-8-sig",
        usecols=["stock_code", "company_name", "period", "table_name",
                 "item_name", "column_header", "value_raw"])
    return df[df["value_raw"].str.strip() != ""]


def _unambiguous_gold(df: pd.DataFrame, code: str, quarter: str,
                      spec: dict) -> dict | None:
    """回傳無歧義金標 {value, table_name, column_header}；有歧義/無資料回 None。"""
    canon = spec["canonical"]
    # 與系統 _direct_lookup_flex Stage 2a 相同的「前綴＋非 CJK 邊界」規則
    pat = re.escape(canon) + r"(?:[^一-鿿]|$)"
    sub = df[(df["stock_code"] == code)
             & (df["period"] == quarter)
             & df["table_name"].str.contains(spec["table"], na=False)
             & df["item_name"].str.match(pat, na=False)]
    if sub.empty:
        return None
    cur = sub[sub["column_header"].str.contains(_west_year(quarter), na=False)]
    if cur.empty:
        return None
    values = set(cur["value_raw"].str.strip())
    if len(values) != 1:
        return None                                   # 有歧義 → 跳過
    row = cur.iloc[0]
    return {"value": row["value_raw"].strip(),
            "table_name": row["table_name"],
            "column_header": row["column_header"]}


def main() -> None:
    rng = random.Random(SEED)
    df = _load_facts()
    full2code = dict(zip(df["company_name"], df["stock_code"]))
    quarters = sorted(df["period"].unique())

    # 枚舉全部 (簡稱, 季度, 科目) 無歧義組合
    pool: list[dict] = []
    for alias, full in COMPANY_ALIASES.items():
        code = full2code.get(full)
        if not code:
            continue
        for q in quarters:
            for spec in ITEM_SPECS:
                gold = _unambiguous_gold(df, code, q, spec)
                if gold is None:
                    continue
                pool.append({"alias": alias, "full": full, "code": code,
                             "quarter": q, "spec": spec, "gold": gold})
    print(f"無歧義組合池：{len(pool)} 組")

    # 分層抽樣：每個 metric 均勻取，公司/季度盡量分散
    by_metric: dict[str, list[dict]] = {}
    for c in pool:
        by_metric.setdefault(c["spec"]["metric"], []).append(c)
    per = max(1, N_QUESTIONS // len(by_metric))
    chosen: list[dict] = []
    used_keys: set[tuple] = set()
    for metric, cands in by_metric.items():
        rng.shuffle(cands)
        cnt = 0
        for c in cands:
            key = (c["code"], c["quarter"], metric)
            if key in used_keys:
                continue
            used_keys.add(key)
            chosen.append(c)
            cnt += 1
            if cnt >= per:
                break
    # 補滿 100
    rest = [c for m in by_metric.values() for c in m
            if (c["code"], c["quarter"], c["spec"]["metric"]) not in used_keys]
    rng.shuffle(rest)
    while len(chosen) < N_QUESTIONS and rest:
        c = rest.pop()
        key = (c["code"], c["quarter"], c["spec"]["metric"])
        if key in used_keys:
            continue
        used_keys.add(key)
        chosen.append(c)
    chosen = chosen[:N_QUESTIONS]
    rng.shuffle(chosen)

    records: list[dict] = []
    for i, c in enumerate(chosen, 1):
        tpl = rng.choice(c["spec"]["templates"])
        question = tpl.format(co=c["alias"], q=c["quarter"])
        records.append({
            "id": f"colloq_nat_{i:03d}",
            "question_type": "colloquial_natural",
            "question_style": "customer_colloquial_natural",
            "question": question,
            "expected_answer": c["gold"]["value"],
            "metadata": {
                "target_route": "direct_lookup_or_vector",
                "metric": c["spec"]["metric"],
                "company_alias": c["alias"],
                "company_name": c["full"],
                "company_code": c["code"],
                "quarter": c["quarter"],
                "item_canonical": c["spec"]["canonical"],
                "table_name": c["gold"]["table_name"],
                "column_header": c["gold"]["column_header"],
            },
        })

    OUTPUT.write_text(json.dumps(records, ensure_ascii=False, indent=1),
                      encoding="utf-8")
    from collections import Counter
    print(f"已輸出 {OUTPUT.name}：{len(records)} 題")
    print("metric 分布:", dict(Counter(r['metadata']['metric'] for r in records)))
    print("季度分布:", dict(Counter(r['metadata']['quarter'] for r in records)))
    print("公司數:", len({r['metadata']['company_code'] for r in records}))
    for r in records[:5]:
        print(" 例:", r["question"], "→", r["expected_answer"])


if __name__ == "__main__":
    main()
