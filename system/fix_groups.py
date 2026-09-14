#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fix 1–20 的五個修復群——命名的單一事實來源。

為什麼要命名
------------
「Fix 1–20」是實作時的流水號，編號本身不帶語意：口委問「Fix 8 在做什麼」，
答案得回頭查表。但這二十條並不是二十件不相干的事，它們分別作用於 §3.5.2
形式化管線的五個階段（表 3-4b 已經建立這個對應）。本檔把該對應**命名**，
讓正文、附錄、圖 3-2 與簡報第 8 頁用同一組名字稱呼同一群修復。

編號一律保留
------------
群名是加在編號**之上**的一層，不取代編號。凍結的實驗資料、日誌、
DISABLE_FIX17 環境變數與 §4.8.1 的敘述都以編號指涉，改名會使既有數據
對不回去。

跨階段的 Fix
------------
Fix 13 同時屬於群一與群二（原句同義詞掃描既補槽位、也做本體論對映），
Fix 14 同時屬於群一與群五（先認出比率語意，最後由 Python 做除法）。
這是執行位置，不是重複計數——與表 3-4b、圖 3-2 的處理一致。
"""
from __future__ import annotations

from typing import NamedTuple


class Group(NamedTuple):
    key: str
    name: str          # 修復群名（正文、圖、簡報共用）
    en: str
    stage_no: str      # 對應 §3.5.2 階段
    stage: str
    purpose: str       # 表 3-4b 的「作用」欄
    fixes: tuple[int, ...]
    detail: tuple[str, ...]   # 簡報小字：逐條的短敘述


GROUPS: tuple[Group, ...] = (
    Group("slot", "槽位補全", "Slot Recovery", "一", "語意候選產生",
          "補回小模型遺失或截斷的槽位",
          (1, 5, 6, 13, 14, 17, 18),
          ("Fix 1　欄位標頭與科目全名",
           "Fix 5·6　檢索通道守衛",
           "Fix 13·14　口語與比率同義詞",
           "Fix 17　公司清單與期別",
           "Fix 18　自然語句槽位")),
    Group("schema", "體系對映", "Schema Mapping", "二", "槽位正規化",
          "使用者語言 → 申報體系的鍵",
          (12, 13),
          ("Fix 12　市場簡稱 → 申報全名",
           "Fix 13　科目本體論最長匹配")),
    Group("narrow", "候選收斂", "Candidate Narrowing", "三", "候選集合過濾",
          "縮小候選至可判定唯一",
          (2, 7, 8, 9, 11, 16),
          ("Fix 11　表名鎖定",
           "Fix 2　年份感知去重",
           "Fix 7·8·9　申報公司與鑑別子句",
           "Fix 16　關係三元主鍵")),
    Group("gate", "唯一性閘門", "Uniqueness Gate", "四", "唯一性判定",
          "決定可否作答",
          (20,),
          ("相異值恰為 1 才作答，不唯一即拒答",
           "Fix 20　未給期別之單值題：採最新期別並於答案內揭露",
           "比較題不套用預設（結論會因期別翻轉）")),
    Group("assemble", "組裝與降級", "Assembly & Fallback", "五", "回答或降級",
          "程式組裝或安全降級",
          (3, 4, 10, 14, 15, 19),
          ("Fix 3·4　語境補全與樣板直答",
           "Fix 10　比較與趨勢後綴",
           "Fix 14　Python 除法",
           "Fix 15　逾時轉可恢復錯誤",
           "Fix 19　多候選全列並列")),
)

# Fix 編號 → 所屬修復群名（跨階段者列出全部）
OF_FIX: dict[int, tuple[str, ...]] = {}
for _g in GROUPS:
    for _n in _g.fixes:
        OF_FIX[_n] = OF_FIX.get(_n, ()) + (_g.name,)


def label(n: int) -> str:
    """附錄一覽表用：Fix 編號的修復群標示。"""
    return "／".join(OF_FIX.get(n, ("—",)))


if __name__ == "__main__":
    for g in GROUPS:
        print(f"群{g.stage_no}　{g.name}（{g.en}）｜階段{g.stage_no}　{g.stage}")
        print(f"    {g.purpose}｜Fix {'、'.join(map(str, g.fixes)) or '無'}")
    print()
    for n in sorted(OF_FIX):
        print(f"  Fix {n:>2}：{label(n)}")
