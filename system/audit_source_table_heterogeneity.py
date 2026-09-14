#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
原始申報表異質性稽核：為什麼實體資訊需要先編譯成圖譜
========================================================
`audit_track_exclusivity.py` 證明了直查軌與圖譜軌互斥，但沒回答下一個問題：
**既然圖譜層只是查表，為什麼不直接查原始 CSV 就好？**

本稽核量化「直接查」的實質成本，並確認兩件事實：

  1. 實體欄位（被投資公司名稱、所在地區、關係人關係…）**不在直查軌的事實表內**
     ——事實表建構時以 `record_type == "numeric_fact"` 過濾，文字列在建表階段
     即被排除。故直查軌答不出圖譜題是結構決定的，不是調校問題。
  2. 這些欄位散落在每季每公司自己那疊原始表 CSV，且**每張表的欄位排列都不同**。
     「直接查 CSV」實際上等於對每一種表頭各寫一套 parser。

圖譜編譯做的正是把這些異質表壓成單一 (source, type, target, 屬性) schema。
本稽核的結論是：圖譜層的貢獻在於**異質表格的實體解析與統一 schema**，
而非圖演算法——這也是論文不宜將該路徑稱為 GraphRAG 的實證依據。

    python3 audit_source_table_heterogeneity.py
      → results/source_table_heterogeneity.json
"""
from __future__ import annotations

import collections
import csv
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports_csv_output"
OUT = ROOT / "results" / "source_table_heterogeneity.json"

# 實體類表：申報表中承載「公司—關係—公司」而非數值的那幾張
ENTITY_KEYWORDS = ("被投資", "轉投資", "關係人", "子公司", "關聯企業")
# 檔名前綴 `<代號>_<期別>_`，去掉才能歸併同一種表
FILENAME_PREFIX = re.compile(r"^\d+_\d+Q\d_")


def table_kind(path: Path) -> str:
    return FILENAME_PREFIX.sub("", path.stem)


def header_of(path: Path) -> str | None:
    """讀首列並以 csv 模組切欄——欄值內含逗號時，字串切割會算錯欄數。"""
    try:
        with path.open(encoding="utf-8-sig", newline="") as fh:
            row = next(csv.reader(fh), None)
    except Exception:                                        # noqa: BLE001
        return None
    return ",".join(c.strip() for c in row) if row else None


def facts_record_types(limit: int = 60) -> dict[str, int]:
    """抽樣確認事實表只收 numeric_fact（此過濾即實體欄位缺席的成因）。"""
    counter: collections.Counter[str] = collections.Counter()
    for i, p in enumerate(sorted(REPORTS.glob("*/*/*_all_table_facts.csv"))):
        if i >= limit:
            break
        try:
            with p.open(encoding="utf-8-sig", newline="") as fh:
                for row in csv.DictReader(fh):
                    counter[row.get("record_type", "")] += 1
        except Exception:                                    # noqa: BLE001
            continue
    return dict(counter)


def main() -> int:
    if not REPORTS.is_dir():
        print(f"✗ 找不到 {REPORTS.name}/")
        return 2

    all_csv = list(REPORTS.glob("*/*/*.csv"))
    dirs = [p for p in REPORTS.glob("*/*") if p.is_dir()]
    entity = [p for p in all_csv
              if any(k in p.name for k in ENTITY_KEYWORDS) and "_facts" not in p.name]

    kinds = collections.Counter(table_kind(p) for p in entity)
    headers: collections.Counter[str] = collections.Counter()
    ncols: collections.Counter[int] = collections.Counter()
    unreadable = 0
    for p in entity:                                         # 全掃，不抽樣
        h = header_of(p)
        if h is None:
            unreadable += 1
            continue
        headers[h] += 1
        ncols[len(h.split(","))] += 1

    rt = facts_record_types()
    numeric_only = set(rt) <= {"numeric_fact"}

    rec = {
        "title": "原始申報表異質性稽核：為什麼實體資訊需要先編譯",
        "why": "回答「圖譜層既然只是查表，為何不直接查原始 CSV」。",
        "corpus": {
            "csv_files_total": len(all_csv),
            "company_quarter_dirs": len(dirs),
            "csv_per_dir_avg": round(len(all_csv) / max(1, len(dirs)), 1),
        },
        "entity_tables": {
            "files": len(entity),
            "table_kinds": len(kinds),
            "distinct_headers": len(headers),
            "column_count_range": [min(ncols), max(ncols)] if ncols else [],
            "unreadable_files": unreadable,
        },
        "table_kind_breakdown": dict(kinds.most_common()),
        "top_headers": [{"columns": len(h.split(",")), "files": n,
                         "header": h[:160]}
                        for h, n in headers.most_common(6)],
        "facts_table_filter": {
            "record_types_seen": rt,
            "numeric_fact_only": numeric_only,
            "note": ("事實表建構時過濾 record_type == 'numeric_fact'，"
                     "實體/文字列在建表階段即被排除——直查軌答不出圖譜題"
                     "是結構決定的。"),
        },
        "conclusion": (
            f"實體資訊分散於 {len(entity):,} 個原始表 CSV、{len(kinds)} 種表、"
            f"{len(headers)} 種相異表頭；圖譜編譯的貢獻在於實體解析與統一三元組"
            "schema，而非圖演算法。"),
    }
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")

    c, e = rec["corpus"], rec["entity_tables"]
    print(f"語料：CSV {c['csv_files_total']:,} 個｜公司×季目錄 "
          f"{c['company_quarter_dirs']}｜平均每目錄 {c['csv_per_dir_avg']} 個")
    print(f"實體類原始表：{e['files']:,} 檔｜{e['table_kinds']} 種表｜"
          f"{e['distinct_headers']} 種相異表頭｜欄數 "
          f"{e['column_count_range'][0]}–{e['column_count_range'][1]}")
    print(f"事實表 record_type：{rt}　→ 僅 numeric_fact：{numeric_only}")
    print("\n表名分布：")
    for k, n in kinds.most_common(10):
        print(f"    {k[:44]:<44}{n:>5} 檔")
    print(f"\n{rec['conclusion']}\n→ {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
