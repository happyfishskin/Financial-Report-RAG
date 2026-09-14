#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
跨產業金標生成器（非半導體三家，114Q2）
========================================
目的：把 §3.11 的跨產業檢核由「可行性」推進到「準確率」。既有檢核只證明管線走得通
（HTML→CSV→Fact 索引→一筆確定性查詢），沒有金標就無法報 EM。

金標從哪裡來——這是本腳本最關鍵的設計
--------------------------------------
論文貢獻二指出：**評測集與受測系統共用同一套邏輯時，污染會墊高分數**。若此處直接
以事實表反查產生金標、再用同一張事實表作答，EM 必然接近 100%，且該數字毫無意義。

因此金標一律取自**原始二維寬表 CSV 的儲存格**，以獨立的 pandas 讀取路徑定位
（列＝會計項目、欄＝欄位標頭），完全不經過 export_table_facts_csv 產生的事實索引，
也不呼叫 _direct_lookup_flex。兩者唯一共用的上游是 HTML→CSV 解析器。

    HTML ──解析器──> 二維寬表 CSV ──┬── 本腳本直接讀儲存格 ──> 金標
                                    └── 事實表線性化 ──> 事實索引 ──> 受測系統

故本評測驗證的是「事實表線性化 ＋ 槽位正規化 ＋ 候選過濾 ＋ 唯一性判定 ＋ 取值」，
**不驗證 HTML→CSV 解析器**（該環節另以人工抽樣核對，見 verify_cross_industry_gold.py）。

避開論文自己檢出的六類金標缺陷
------------------------------
  D2 取自去年同期比較欄  → 只取當期欄，且欄位標頭寫進題幹
  D3 金標毀損            → 濾掉附註代號、序列化傾印與非數值儲存格
  D4 跨期題兩期同一欄    → 本集只出單期題，不適用
  D5 單季／累計歧義      → 綜合損益表兩種當期欄並存，題幹明寫是哪一欄
  D6 科目中英文不一致    → 科目原樣引用寬表的「會計項目」欄，不重寫
  D7 金標來源非當期表    → 排除「去年同期*」表

抽樣不看系統答不答得出來：固定亂數種子後隨機抽，不因系統拒答而換題。

    python3 generate_cross_industry_gold.py [--n-per-company 25] [--seed 20260811]
"""
from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CSV_ROOT = ROOT / "_cross_industry_probe" / "reports_csv_output"
DEFAULT_OUT = ROOT / "questions" / "cross_industry_gold_114Q2.json"

PERIOD = "114Q2"
DEFAULT_TARGETS = [("2603", "長榮海運", "航運"),
                   ("2317", "鴻海精密工業", "電子代工"),
                   ("6691", "洋基工程", "機電工程")]
# 同一支生成器也用於半導體對照組——兩組必須由同一支解析器產生的 CSV 出題，
# 否則比較到的是解析器版本差異而非產業差異。
SEMI_TARGETS = [("2330", "台灣積體電路製造", "半導體"),
                ("2303", "聯華電子", "半導體"),
                ("2454", "聯發科技", "半導體")]

# 各報表的「當期」欄位關鍵字。114Q2 ＝ 民國 114 年第 2 季 ＝ 西元 2025 年 Q2。
# 綜合損益表當期有單季與累計兩種，兩者都合法，故各自成為一個題型。
STATEMENTS = [
    ("資產負債表", "2025年6月30日", "期末餘額"),
    ("綜合損益表", "2025年4月1日至6月30日", "單季"),
    ("綜合損益表", "2025年1月1日至6月30日", "累計"),
    ("現金流量表", "2025年1月1日至6月30日", "累計"),
]

ITEM_COL_KEY = "會計項目"
CODE_COL_KEY = "代號"

# D3：附註代號（如「六(三)」「附註 12」）與序列化傾印（value_N=…）
_JUNK = re.compile(r"value_\d+=|^[（(]?[一二三四五六七八九十]+[）)]|^附註")
_NUM = re.compile(r"^-?[\d,]+(?:\.\d+)?$")


# pandas 把整數欄推論成 float 時留下的尾巴（'253369890.0'）；報表上沒有這個 .0
_PANDAS_INT_ARTIFACT = re.compile(r"^(-?\d+)\.0$")


def canonical(raw: str) -> str | None:
    """儲存格 → 金標字串；非數值回傳 None。

    **保留報表上的原始寫法**，只去掉千分位逗號與 pandas 的 .0 尾巴。
    不可做 float 來回轉換——那會把每股盈餘的 '17.50' 變成 '17.5'，
    金標就不再是報表上印的數字，EM 會因為金標失真而扣分（初版即犯此錯）。
    """
    s = str(raw).strip().replace(",", "")
    if not s or not _NUM.match(s) or _JUNK.search(s):
        return None
    m = _PANDAS_INT_ARTIFACT.match(s)
    return m.group(1) if m else s


def collect(code: str, name: str, csv_root: Path) -> list[dict]:
    """走訪三大報表，收出所有可作答的（科目 × 當期欄）儲存格。"""
    base = next((d for d in csv_root.iterdir()
                 if d.is_dir() and d.name.startswith(code)), None)
    if base is None:
        raise SystemExit(f"✗ 找不到 {code} 的 CSV 目錄")
    qdir = base / PERIOD
    pool: list[dict] = []

    for table, col_key, kind in STATEMENTS:
        hits = list(qdir.glob(f"*_{table}.csv"))
        # D7：排除「去年同期權益變動表」這類整表即上年度的來源
        hits = [h for h in hits if "去年同期" not in h.name]
        if not hits:
            continue
        csv = hits[0]
        df = pd.read_csv(csv, dtype=str, keep_default_na=False)
        item_col = next((c for c in df.columns if ITEM_COL_KEY in c), None)
        code_col = next((c for c in df.columns if CODE_COL_KEY in c), None)
        val_col = next((c for c in df.columns if col_key in c), None)
        if not item_col or not val_col:
            continue

        for idx, row in df.iterrows():
            item = str(row[item_col]).strip()
            gold = canonical(row[val_col])
            if not item or gold is None:
                continue
            if _JUNK.search(item):
                continue
            pool.append({
                "stock_code": code, "company_name": name, "period": PERIOD,
                "table_name": table, "item_name": item,
                "column_header": val_col, "column_kind": kind,
                "code": str(row[code_col]).strip() if code_col else "",
                "expected_answer": gold,
                "source_csv": csv.name, "row_index": int(idx),
            })
    return pool


def phrase(r: dict) -> str:
    """題幹格式沿用 system_architecture_test_questions_100_v2（【】標記結構化槽位）。

    欄位標頭一律寫進題幹：這是本系統的輸入契約，也是避免 D2／D5 的必要條件。
    """
    return (f"請查詢【{r['company_name']}】在【{r['period']}】的"
            f"【{r['item_name']}】（{r['column_header']}）是多少？")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-per-company", type=int, default=25)
    ap.add_argument("--seed", type=int, default=20260811)
    ap.add_argument("--csv-root", type=Path, default=DEFAULT_CSV_ROOT)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--semi", action="store_true",
                    help="改出半導體對照組（同一支解析器、同一套出題規則）")
    a = ap.parse_args()
    a.csv_root = a.csv_root.resolve()
    a.out = a.out.resolve()
    targets = SEMI_TARGETS if a.semi else DEFAULT_TARGETS
    prefix = "semi" if a.semi else "xind"

    rng = random.Random(a.seed)
    out: list[dict] = []
    stats: list[dict] = []

    for code, name, industry in targets:
        pool = collect(code, name, a.csv_root)
        # 分層：四個（報表 × 當期欄）各抽約當比例，避免全部集中在資產負債表
        by_kind: dict[tuple, list] = {}
        for r in pool:
            by_kind.setdefault((r["table_name"], r["column_kind"]), []).append(r)
        per = max(1, a.n_per_company // len(by_kind))
        picked: list[dict] = []
        for k in sorted(by_kind):
            grp = by_kind[k]
            rng.shuffle(grp)
            picked += grp[:per]
        rest = [r for r in pool if r not in picked]
        rng.shuffle(rest)
        picked += rest[:max(0, a.n_per_company - len(picked))]

        for i, r in enumerate(picked, 1):
            out.append({
                "id": f"{prefix}_{code}_{i:03d}",
                "question_type": "direct_numeric_lookup",
                "question": phrase(r),
                "expected_answer": r["expected_answer"],
                "metadata": {
                    "target_route": "direct_lookup",
                    "company_code": code, "company_name": name,
                    "industry": industry, "quarter": PERIOD,
                    "table_name": r["table_name"], "item_name": r["item_name"],
                    "column_header": r["column_header"],
                    "column_kind": r["column_kind"], "code": r["code"],
                    "source_csv": r["source_csv"], "row_index": r["row_index"],
                    "gold_source": "wide_csv_cell",
                },
            })
        stats.append({"code": code, "name": name, "industry": industry,
                      "pool": len(pool), "picked": len(picked),
                      "by_kind": {f"{k[0]}／{k[1]}": len(v)
                                  for k, v in sorted(by_kind.items())}})

    a.out.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"金標題數：{len(out)}　→　{a.out.relative_to(ROOT)}")
    for s in stats:
        print(f"  {s['code']} {s['name']}（{s['industry']}）："
              f"候選池 {s['pool']} 格，抽出 {s['picked']} 題")
        for k, v in s["by_kind"].items():
            print(f"      {k}：池內 {v} 格")
    dup = len(out) - len({(o['metadata']['source_csv'], o['metadata']['row_index'],
                           o['metadata']['column_header']) for o in out})
    print(f"重複儲存格：{dup}（應為 0）")
    print("金標來源：原始二維寬表 CSV 儲存格，未經事實索引")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
