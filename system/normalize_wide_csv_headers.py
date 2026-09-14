#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
寬表欄名正規化：把現行解析器的巢狀表頭還原為檢索層預期的扁平格式
================================================================
現行解析器對多層表頭會輸出

    資產負債表Balance Sheet_2025年6月30日2025/6/30

而 2026-06 建立的半導體語料是扁平格式

    2025年6月30日 2025/6/30

`_direct_lookup_flex` 的 col_hint 鎖定只取欄位標頭的**前 12 個字元**
（rag_test_system_v14.py:2207）。扁平格式下，前 12 字元正好是具鑑別力的日期；
巢狀格式下卻是「資產負債表Balance」——該表每一欄都相同，鎖定因而失效，
候選退回多個年份欄，唯一性判定判為 ambiguous 而拒答。

本腳本把巢狀欄名還原為扁平格式，用於隔離「欄名格式」這一個變因。
它不是修正方案——真正的修正應該是讓 col_hint 比對不依賴字首位置（見報告建議）。

    python3 normalize_wide_csv_headers.py --src <目錄> --dst <目錄>
"""
from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

import pandas as pd

# 「2025年6月30日2025/6/30」「2025年1月1日至6月30日2025/1/1To6/30」→ 中間補空白
_DATE = re.compile(r"^(.*?\d{1,2}月\d{1,2}日)(\d{4}/.*)$")
_LABEL = re.compile(r"^(代號|會計項目)([A-Za-z].*)$")


_CJK = re.compile(r"[\u4e00-\u9fff]")


def flatten(col: str) -> str:
    """巢狀欄名 → 扁平欄名。

    只在前綴含中日韓文字時才視為「表名前綴」而剝除——欄位本身就帶底線的
    schema 欄（record_type、source_kind…）不可誤傷（初版即因此把 record_type
    改成 type，毀掉 facts 檔的欄位結構）。
    """
    s = str(col)
    if "_" in s:
        head, tail = s.split("_", 1)
        if _CJK.search(head) and tail:
            s = tail
    m = _DATE.match(s)
    if m:
        return f"{m.group(1)} {m.group(2)}"
    m = _LABEL.match(s)
    if m:
        return f"{m.group(1)} {m.group(2)}"
    return s


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=Path, required=True)
    ap.add_argument("--dst", type=Path, required=True)
    a = ap.parse_args()

    if a.dst.exists():
        shutil.rmtree(a.dst)
    a.dst.mkdir(parents=True)

    n_file = n_col = 0
    samples: list[tuple[str, str]] = []
    for src in sorted(a.src.rglob("*.csv")):
        rel = src.relative_to(a.src)
        out = a.dst / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        try:
            df = pd.read_csv(src, dtype=str, keep_default_na=False)
        except Exception:
            shutil.copy2(src, out)
            continue
        # 寬表：欄「名」即標頭
        new = [flatten(c) for c in df.columns]
        changed = sum(1 for o, x in zip(df.columns, new) if o != x)
        for o, x in zip(df.columns, new):
            if o != x and len(samples) < 3:
                samples.append((o, x))
        df.columns = new
        # facts 表：標頭是 column_header 這一「欄的值」，系統實際讀的是這裡
        if "column_header" in df.columns:
            before = df["column_header"].copy()
            df["column_header"] = df["column_header"].map(flatten)
            diff = int((before != df["column_header"]).sum())
            changed += diff
            for o, x in zip(before, df["column_header"]):
                if o != x and len(samples) < 6:
                    samples.append((o, x))
                    break
        n_col += changed
        df.to_csv(out, index=False, encoding="utf-8-sig")
        n_file += 1

    print(f"處理 {n_file} 個 CSV，改寫 {n_col} 個欄名 → {a.dst}")
    for o, x in samples:
        print(f"    {o}\n  → {x}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
