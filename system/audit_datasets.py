#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
資料集金標稽核（audit_datasets.py）

對 questions/ 底下所有測試集，逐題把 expected_answer 反查
`reports_csv_output/__all_company_all_period_numeric_facts.csv`（211,263 筆事實），
檢查下列可機械驗證的缺陷：

  D1  gold_not_in_corpus   金標值在該（公司, 期別, 表, 科目）下完全查不到
  D2  wrong_column_period  金標取自「去年同期比較欄」，而題目問的是本期
                           （僅在題目文字未明寫欄位標頭時才算缺陷）
  D3  corrupt_gold         金標非數值（附註代號如 "D1"/"註1"、或整列傾印）
  D4  same_value_two_period 跨期比較題兩期金標相同，且係因兩期共用同一欄位標頭
  D5  ambiguous_row        同（公司,期別,表,科目,欄位）對到多列不同值（列歧義）
  D6  item_name_mismatch   科目名中英文指向不同科目（語料表頭誤併）
  D7  prior_period_source  金標取自「去年同期<表>」，內容為上一年度數字而非當期

輸出：results/dataset_audit.json / results/dataset_audit.md
本腳本「只稽核、不修改」。修正由 fix_datasets.py 執行。

給第一次看這支程式的人
----------------------
這支程式就像「答案校對員」。

測試題裡原本附有標準答案，欄位名稱叫 `expected_answer`。但標準答案也可能抄錯，
所以不能因為它叫「標準答案」就直接相信它。本程式會回到原始財報，重新查一次：

    題目：台積電 114Q2 的營收是多少？
    原金標：673,510,177
    財報本期欄：933,791,869
    財報去年同期欄：673,510,177

這時就能判斷：原金標不是亂寫的，而是抄到旁邊的「去年同期」欄。

建議閱讀順序：

1. `Corpus`：先把財報整理成一本方便查詢的「字典」。
2. `audit_numeric`：看最基本的單一數字題如何校對。
3. `audit_period_compare`、`audit_company_compare`：看比較題如何校對。
4. `main`：看每種題型被送到哪一個檢查函式。

請先記住三件事：
* `expected_answer` 是「等著被檢查的答案」，不是一定正確。
* 財報常把本期與去年同期放在一起，抄錯隔壁欄是最常見的問題。
* 本程式只負責找錯，不會直接改答案；修改工作交給 `fix_datasets.py`。

完整檢查流程（由上往下）
------------------------

    【步驟1：讀取題目】
    讀取 question、expected_answer 和 metadata。
    metadata 裡記錄公司、季度、報表、科目及欄位等查詢線索。
                         ↓
    【步驟2：判斷題型】
    分成普通數字題、跨季度比較題、跨公司比較題、比率題或圖譜題。
    不同題型的答案格式不同，所以不能全部用同一種方法檢查。
                         ↓
    【步驟3：回到原始財報】
    用「公司＋季度＋報表＋科目」查詢原始財報事實表。
    這一步找出的才是驗證依據，不使用模型回答驗證金標。
                         ↓
    【步驟4：找出本期欄】
    例如114Q2先換算成西元2025年。
    欄位名稱含2025的可能是本期欄；含2024的通常是去年同期比較欄。
    如果同時有單季與累計欄，必須再看題目是否已說明答案口徑。
                         ↓
    【步驟5：統一數字格式】
    移除逗號與空格，並把財報括號負數轉成一般負數：
    `( 216,566 )`和`-216566`會被視為同一個數字。
                         ↓
    【步驟6：比較金標與財報】
    普通題：金標是否等於本期值？
    跨期題：兩個季度是否各自取自己的本期欄？趨勢是否正確？
    跨公司題：兩家公司數值及「較高」結論是否正確？
    比率題：分子、分母、百分比與最後比較結論是否都正確？
                         ↓
    【步驟7：標記錯誤原因】
    D1：金標在原始財報中找不到。
    D2：金標抄到去年同期比較欄。
    D3：金標是附註代號或`value_N=`整列傾印，無法正常評分。
    D4：跨期題錯把同一欄位同時用於兩個季度。
    D5：同一題有多個合理數值，題目沒有說清楚。
    D6：科目中英文名稱錯誤合併。
    D7：資料來源是上一年度報表，不是題目所問期間。
    D9：比率的分子、分母、算術或勝者結論不一致。
    D10：題目的question_type與實際來源表不一致。
    D11：題目使用一般人無法理解的原表列序號。
                         ↓
    【步驟8：輸出報告】
    記錄題目編號、原金標、錯誤原因、財報定位及正確候選值。
    本程式到此為止，不直接修改題目或金標。
                         ↓
    【步驟9：交給修復程式】
    `fix_datasets.py`只有在原始財報能證明唯一答案時才修改金標。
    如果答案不唯一，就補充題目條件；仍無法唯一定位時則維持原狀。

最重要的原則
------------

    系統回答 ≠ 驗證依據
    原始財報事實 = 驗證依據

也就是說，本研究不是因為「系統回答100元」就把金標改成100元；
而是回到原始財報確認本期欄確實只有100元，才判定原金標有誤。
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
QDIR = ROOT / "questions"
FACTS = ROOT / "reports_csv_output" / "__all_company_all_period_numeric_facts.csv"
OUTDIR = ROOT / "results"

# 預設稽核原始資料集；加 --v3 改稽核修正後的 *_v3.json
DATASETS = [
    "customer_colloquial_test_questions_100.json",
    "customer_colloquial_test_questions_100_v2.json",
    "customer_colloquial_natural_100.json",
    "system_architecture_test_questions_100.json",
    "system_architecture_test_questions_100_v2.json",
    "system_architecture_test_questions_10_selected.json",
    "system_architecture_test_questions_10_selected_alt.json",
    "system_architecture_wrong_questions_dataset.json",
    "system_architecture_wrong_questions_dataset_v2.json",
    "ratio_questions_50.json",
    "ratio_cross_company_50.json",
    # [P2] canonical 與拆分後的圖譜題集
    "system_architecture_test_questions_100_v4.json",
    "graph_capability_explicit.json",
    "graph_routing_natural.json",
    "graph_routing_natural_100.json",
]

MAIN_STATEMENTS = ("綜合損益表", "資產負債表", "現金流量表")

# 語料表頭誤併：中文名與英文名指向不同科目
BROKEN_ITEMS = {
    "繼續營業單位淨利（淨損） Diluted earnings (loss) per share from continuing operations",
}

_PERIOD_RE = re.compile(r"^(\d{3})Q([1-4])$")
_SEG_RE = re.compile(r"\s*[｜|]\s*")


def roc_to_ad(period: str) -> int | None:
    """把民國季度換成西元年，例如 114Q2 → 2025，方便對照財報欄位。"""
    m = _PERIOD_RE.match(str(period).strip())
    return int(m.group(1)) + 1911 if m else None


def col_years(col: str) -> set[int]:
    """找出欄位名稱裡的年份，例如「2025年...」會取出 2025。"""
    return {int(y) for y in re.findall(r"(20\d{2})", str(col))}


def narrow_by_clause(hits, qtext):
    """題目若帶「累計數／單季數」消歧子句，把本期欄候選收斂到對應的那一欄。"""
    if not hits:
        return hits
    if "累計數" in str(qtext):
        sel = [(c, v) for c, v in hits if re.search(r"\d{4}年1月1日至", str(c))]
    elif "單季數" in str(qtext):
        sel = [(c, v) for c, v in hits if not re.search(r"\d{4}年1月1日至", str(c))]
    else:
        return hits
    return sel or hits


def column_is_pinned(qtext: str, col: str) -> bool:
    """題目是否已把欄位釘死：明寫欄位標頭，或帶有累計/單季消歧子句。"""
    if col and str(col) in str(qtext):
        return True
    return "累計數" in str(qtext) or "單季數" in str(qtext)


def norm_num(s) -> str | None:
    """把 '( 216,566 )' / '216,566' 正規化成可比較字串；非數值回 None。"""
    if s is None:
        return None
    t = str(s).strip()
    neg = t.startswith("(") and t.endswith(")")
    t = t.strip("()").strip().replace(",", "").replace(" ", "")
    if not re.fullmatch(r"-?\d+(\.\d+)?", t):
        return None
    v = float(t)
    if neg:
        v = -abs(v)
    return f"{v:.4f}"


def is_corrupt_gold(v) -> bool:
    """附註代號（D1 / 註4 / A12）或整列傾印（含 value_N=）視為毀損金標。"""
    t = str(v).strip()
    if not t:
        return True
    if "value_" in t and "=" in t:
        return True
    return bool(re.fullmatch(r"[A-Za-z]\d{1,2}", t)) or bool(re.fullmatch(r"註\s*\d+", t))


def parse_segments(text: str) -> dict:
    """'A: 1 ｜ B: 2 ｜ 較高: A' -> {'A':'1','B':'2','較高':'A'}"""
    out = {}
    for seg in _SEG_RE.split(str(text)):
        if ":" in seg:
            k, _, v = seg.partition(":")
            out[k.strip()] = v.strip()
        elif "：" in seg:
            k, _, v = seg.partition("：")
            out[k.strip()] = v.strip()
    return out


class Corpus:
    """把二十一萬多筆財報資料整理成容易查找的形式。

    可以把它想成兩本字典：

    * `idx`：用「公司＋季度＋報表＋科目」查資料，條件最完整。
    * `by_ci`：用「公司＋季度＋科目」查資料；不知道報表名稱時才使用。

    查到資料後仍會保留「欄位名稱」和「數值」，因為我們不只要知道數字，
    還要知道它是本期數字，還是放在旁邊的去年同期數字。
    """

    def __init__(self, path: Path):
        df = pd.read_csv(path, dtype=str, low_memory=False)
        df.columns = [c.lstrip("﻿") for c in df.columns]
        self.df = df
        self.idx = defaultdict(list)
        for r in df.itertuples(index=False):
            self.idx[(r.stock_code, r.period, r.table_name, r.item_name)].append(
                (r.column_header, r.value_raw)
            )
        # 科目名 -> 供模糊比對
        self.by_ci = defaultdict(list)
        for r in df.itertuples(index=False):
            self.by_ci[(r.stock_code, r.period, r.item_name)].append(
                (r.table_name, r.column_header, r.value_raw)
            )

    def rows(self, code, period, table, item):
        return self.idx.get((str(code), str(period), str(table), str(item)), [])

    def rows_any_table(self, code, period, item):
        return self.by_ci.get((str(code), str(period), str(item)), [])

    def value_for_period(self, code, period, table, item):
        """找出這一題可能的本期數字。

        例如題目問 114Q2，114年就是2025年，所以欄位名稱含2025的才可能是本期欄。
        但同一份報表可能同時有「第二季單季」與「上半年累計」兩個2025年欄位，
        因此這裡不會隨便挑一個，而是把候選值全部交回去繼續判斷。
        """
        ad = roc_to_ad(period)
        cands = self.rows(code, period, table, item)
        if not cands:
            cands = [(c, v) for _t, c, v in self.rows_any_table(code, period, item)]
        hits = [(c, v) for c, v in cands if ad in col_years(c)]
        if not hits:
            return None, cands
        vals = {norm_num(v) for _c, v in hits}
        return hits, cands


def audit_numeric(q, corpus: Corpus, findings: list, ds: str):
    """檢查「某公司、某季度、某科目是多少」這種基本數字題。

    白話流程：

    1. 先看金標是不是壞掉的字串，例如 `value_2=...`，這種根本不能評分。
    2. 再確認題目查的是正確報表與正確科目。
    3. 回到財報找該季度的本期欄。
    4. 比較金標是否等於本期值。
    5. 如果金標其實出現在去年同期欄，就標記成「抄錯欄」。

    檢查順序固定，是為了避免同一個錯誤被重複報告好幾次。
    """
    md = q.get("metadata", {})
    code = md.get("company_code")
    period = md.get("quarter")
    table = md.get("table_name")
    item = md.get("item_name") or md.get("item_canonical")
    col = md.get("column_header")
    gold = q.get("expected_answer")
    qtext = q.get("question", "")

    if not (code and period and item):
        return
    ad = roc_to_ad(period)

    def add(defect, detail, **kw):
        # 把「哪一題、錯在哪裡、正確候選有哪些」統一記到 findings 清單。
        findings.append(dict(dataset=ds, id=q["id"], qtype=q.get("question_type"),
                            question=qtext, gold=gold, defect=defect,
                            detail=detail, company_code=code, period=period,
                            table_name=table, item_name=item, column_header=col, **kw))

    if is_corrupt_gold(gold):
        add("D3_corrupt_gold", f"金標「{gold}」非數值（附註代號或整列傾印）")
        return

    # D6：語料表頭誤併造成中文名與英文名指向不同科目（如中文「淨利」配英文 EPS）
    if str(item) in BROKEN_ITEMS:
        add("D6_item_name_mismatch",
            f"科目名「{item}」之中英文分別指向不同科目（語料表頭誤併），"
            f"金標「{gold}」實為每股盈餘而非淨利")
        return

    hits, cands = corpus.value_for_period(code, period, table, item)
    gn = norm_num(gold)

    # D7：金標來源根本不屬於所問的會計期間。
    # 「去年同期權益變動表」這類表的欄位標頭其實是**表名加流水號**
    # （…Statements of Change in Equity_14），內容為上一年度數字。
    # 題幹即使原樣引用該字串也不構成有效消歧——指定一個錯誤的來源
    # 不會讓它變成正確答案，故此類不受「題目已明寫欄位」豁免。
    if "去年同期" in str(table) or "去年同期" in str(col):
        main = [(c, v) for _t, c, v in corpus.rows_any_table(code, period, item)
                if _t in MAIN_STATEMENTS and ad in col_years(c)]
        add("D7_prior_period_source",
            f"金標取自「{table or col}」（上一年度報表），非 {period}（{ad}）當期；"
            f"主要報表當期值為 {sorted({str(v) for _c, v in main}) or '（查無）'}",
            correct_candidates=sorted({str(v) for _c, v in main}))
        return

    # 題目文字已明寫欄位標頭 → 欄位無歧義，只驗證金標與該欄位值是否一致
    if col and str(col) in qtext:
        exact = [v for c, v in cands if str(c) == str(col)]
        if exact and gn is not None and gn not in {norm_num(v) for v in exact}:
            add("D1_gold_not_in_corpus",
                f"題目明寫欄位「{col}」，該欄值為 {sorted(set(map(str, exact)))}，"
                f"與金標「{gold}」不符",
                correct_candidates=sorted(set(map(str, exact))))
        return

    # 題目帶有「累計數／單季數」消歧子句 → 對應到本期欄中的累計或單季欄
    if "累計數" in qtext or "單季數" in qtext:
        want_cumul = "累計數" in qtext
        pick = [v for c, v in (hits or [])
                if bool(re.search(r"\d{4}年1月1日至", str(c))) == want_cumul]
        if pick and gn is not None and gn not in {norm_num(v) for v in pick}:
            add("D1_gold_not_in_corpus",
                f"題目指定{'累計' if want_cumul else '單季'}數，該欄值為 "
                f"{sorted(set(map(str, pick)))}，與金標「{gold}」不符",
                correct_candidates=sorted(set(map(str, pick))))
        return

    # D5：本期欄對到多列不同值
    if hits:
        distinct = {norm_num(v) for _c, v in hits}
        if len(distinct) > 1:
            add("D5_ambiguous_row",
                f"本期欄 {sorted({c for c, _ in hits})} 對到 {len(hits)} 列、{len(distinct)} 個相異值："
                + "、".join(sorted({str(v) for _c, v in hits})),
                correct_candidates=sorted({str(v) for _c, v in hits}))

    # D2：金標命中比較欄而非本期欄
    if cands:
        cur_vals = {norm_num(v) for _c, v in (hits or [])}
        cmp_hits = [(c, v) for c, v in cands
                    if ad not in col_years(c) and norm_num(v) == gn and gn is not None]
        if gn is not None and gn not in cur_vals and cmp_hits:
            explicit = any(str(c) and str(c) in qtext for c, _ in cmp_hits)
            correct = sorted({str(v) for _c, v in (hits or [])})
            add("D2_wrong_column_period" if not explicit else "OK_explicit_column",
                f"金標「{gold}」出現在比較欄 {sorted({c for c, _ in cmp_hits})}；"
                f"本期（{ad}）欄之正解為 {correct or '（查無）'}"
                + ("；但題目文字已明寫該欄位標頭，故不計為缺陷" if explicit else ""),
                correct_value=(correct[0] if len(correct) == 1 else None),
                correct_candidates=correct)
            return

    # D1：整個 (公司,期別,表,科目) 都查不到這個值
    if cands and gn is not None:
        allv = {norm_num(v) for _c, v in cands}
        if gn not in allv:
            add("D1_gold_not_in_corpus",
                f"金標「{gold}」不在該科目任何欄位中；可用值 "
                + "、".join(sorted({str(v) for _c, v in cands})),
                correct_candidates=sorted({str(v) for _c, v in (hits or [])}))


def audit_period_compare(q, corpus: Corpus, findings: list, ds: str):
    """檢查同一家公司兩個季度的比較題。

    例如「台積電113Q2與114Q2的營收是否上升？」必須做三件事：

    1. 113Q2回到113Q2財報找自己的本期欄。
    2. 114Q2回到114Q2財報找自己的本期欄。
    3. 用兩個正確數字重新判斷上升、下降或持平。

    不能拿同一個欄位同時代表兩個季度，否則很容易製造出假的「持平」。
    """
    md = q.get("metadata", {})
    code = md.get("company_code")
    periods = md.get("periods") or []
    item = md.get("item_name") or md.get("item_canonical")
    table = md.get("table_name")
    col = md.get("column_header")
    gold = q.get("expected_answer")
    segs = parse_segments(gold)
    if not (code and len(periods) == 2 and item):
        return
    qtext = q.get("question", "")
    qtype = q.get("question_type")
    code_repr, period_repr = code, "/".join(periods)
    # D7：金標來源為「去年同期<表>」，內容為上一年度數字而非所問期間之當期值。
    # 題幹原樣引用該字串不構成有效消歧（指定錯誤來源不會使它變成正確答案）。
    if "去年同期" in str(table) or "去年同期" in str(col):
        findings.append(dict(
            dataset=ds, id=q["id"], qtype=qtype or q.get("question_type"),
            question=qtext, gold=gold, defect="D7_prior_period_source",
            detail=f"金標取自「{table or col}」（上一年度報表），"
                   f"非所問期間之當期值",
            company_code=str(code_repr), period=str(period_repr),
            table_name=table, item_name=item, column_header=col))
        return


    # 跨期題若把「單一欄位標頭」同時套用於兩個期別，該欄至多只屬於其中一期，
    # 另一期實際被讀成它的去年同期比較欄 → 趨勢結論恆為「持平」而失去意義。
    # 題幹原樣引用該欄位不構成有效消歧（一個欄位無法同時是兩期的當期欄）。
    if col and col_years(col):
        owners = [p for p in periods if roc_to_ad(p) in col_years(col)]
        if len(owners) == 1:
            findings.append(dict(
                dataset=ds, id=q["id"], qtype=q.get("question_type"),
                question=qtext, gold=gold, defect="D4_same_value_two_period",
                detail=f"欄位標頭「{col}」僅屬 {owners[0]} 之當期欄，卻同時用於 "
                       f"{'/'.join(periods)} 兩期；另一期實為其去年同期比較欄，"
                       f"趨勢結論因此恆為「持平」",
                company_code=code, period="/".join(periods),
                table_name=table, item_name=item, column_header=col))
            return

    # 題目明寫欄位標頭 → 欄位無歧義，僅驗證金標與該欄位值一致
    if col and str(col) in qtext:
        problems = []
        for p in periods:
            g = segs.get(p)
            ex = [v for c, v in corpus.rows(code, p, table, item) if str(c) == str(col)]
            if g and ex and norm_num(g) not in {norm_num(v) for v in ex}:
                problems.append(f"{p} 明寫欄位值 {sorted(set(map(str, ex)))} 與金標「{g}」不符")
        if problems:
            findings.append(dict(
                dataset=ds, id=q["id"], qtype=q.get("question_type"),
                question=qtext, gold=gold, defect="D1_gold_not_in_corpus",
                detail="；".join(problems), company_code=code,
                period="/".join(periods), table_name=table, item_name=item,
                column_header=col))
        return

    # truth 記住兩個季度各自查到的正確候選；
    # problems 收集所有問題，最後一起寫進報告，方便一次看懂。
    truth, problems = {}, []
    for p in periods:
        hits, cands = corpus.value_for_period(code, p, table, item)
        hits = narrow_by_clause(hits, qtext)
        vals = sorted({str(v) for _c, v in (hits or [])})
        truth[p] = vals
        g = segs.get(p)
        if g is None:
            continue
        if is_corrupt_gold(g):
            problems.append(f"{p} 金標「{g}」毀損")
            continue
        if vals and norm_num(g) not in {norm_num(v) for v in vals}:
            in_cmp = any(norm_num(g) == norm_num(v) for _c, v in cands
                         if roc_to_ad(p) not in col_years(_c))
            problems.append(
                f"{p} 金標「{g}」{'取自比較欄' if in_cmp else '不在語料'}，本期正解 {vals}")

    gvals = {norm_num(segs[p]) for p in periods if p in segs}
    same_gold = len(gvals) == 1 and None not in gvals
    tvals = {tuple(truth[p]) for p in periods}
    if same_gold and len(tvals) == 2:
        problems.append(
            f"兩期金標同值，但語料本期欄實際為 "
            + "、".join(f"{p}={truth[p]}" for p in periods))

    if problems:
        findings.append(dict(
            dataset=ds, id=q["id"], qtype=q.get("question_type"),
            question=q.get("question", ""), gold=gold,
            defect="D4_same_value_two_period" if same_gold else "D2_wrong_column_period",
            detail="；".join(problems), company_code=code, period="/".join(periods),
            table_name=table, item_name=item, column_header=col,
            correct_by_period={p: truth[p] for p in periods}))


def audit_company_compare(q, corpus: Corpus, findings: list, ds: str):
    """檢查同一季度比較兩家公司的題目。

    程式先分別查出兩家公司的正確數字，再檢查「哪一家較高」的結論。
    財報使用公司代碼，答案使用公司名稱，所以中間會先做代碼與名稱的對照。
    """
    md = q.get("metadata", {})
    codes = md.get("companies") or []
    period = md.get("quarter")
    item = md.get("item_name") or md.get("item_canonical")
    table = md.get("table_name")
    col = md.get("column_header")
    gold = q.get("expected_answer")
    segs = parse_segments(gold)
    if not (codes and period and item):
        return
    ad = roc_to_ad(period)
    qtext = q.get("question", "")
    qtype = q.get("question_type")
    code_repr, period_repr = "/".join(map(str, codes)), period
    # D7：金標來源為「去年同期<表>」，內容為上一年度數字而非所問期間之當期值。
    # 題幹原樣引用該字串不構成有效消歧（指定錯誤來源不會使它變成正確答案）。
    if "去年同期" in str(table) or "去年同期" in str(col):
        findings.append(dict(
            dataset=ds, id=q["id"], qtype=qtype or q.get("question_type"),
            question=qtext, gold=gold, defect="D7_prior_period_source",
            detail=f"金標取自「{table or col}」（上一年度報表），"
                   f"非所問期間之當期值",
            company_code=str(code_repr), period=str(period_repr),
            table_name=table, item_name=item, column_header=col))
        return

    name_of0 = {}
    for c in codes:
        sub = corpus.df[(corpus.df.stock_code == str(c))]
        if len(sub):
            name_of0[str(c)] = sub.iloc[0].company_name

    # 題目明寫欄位標頭 → 欄位無歧義，僅驗證金標與該欄位值一致
    if col and str(col) in qtext:
        problems = []
        for c in codes:
            nm = name_of0.get(str(c), str(c))
            g = segs.get(nm)
            ex = [v for cc, v in corpus.rows(c, period, table, item) if str(cc) == str(col)]
            if g and ex and norm_num(g) not in {norm_num(v) for v in ex}:
                problems.append(f"{nm} 明寫欄位值 {sorted(set(map(str, ex)))} 與金標「{g}」不符")
        if problems:
            findings.append(dict(
                dataset=ds, id=q["id"], qtype=q.get("question_type"),
                question=qtext, gold=gold, defect="D1_gold_not_in_corpus",
                detail="；".join(problems), company_code="/".join(map(str, codes)),
                period=period, table_name=table, item_name=item, column_header=col))
        return

    name_of = {}
    for c in codes:
        sub = corpus.df[(corpus.df.stock_code == str(c))]
        if len(sub):
            name_of[str(c)] = sub.iloc[0].company_name

    problems, truth = [], {}
    for c in codes:
        nm = name_of.get(str(c), str(c))
        hits, cands = corpus.value_for_period(c, period, table, item)
        hits = narrow_by_clause(hits, qtext)
        vals = sorted({str(v) for _c, v in (hits or [])})
        truth[nm] = vals
        g = segs.get(nm)
        if g is None:
            continue
        if vals and norm_num(g) not in {norm_num(v) for v in vals}:
            in_cmp = any(norm_num(g) == norm_num(v) for _c, v in cands
                         if ad not in col_years(_c))
            problems.append(f"{nm} 金標「{g}」{'取自比較欄' if in_cmp else '不在語料'}，"
                            f"本期（{ad}）正解 {vals}")
    # 欄位標頭本身年份錯
    if col and ad and ad not in col_years(col) and col_years(col):
        problems.append(f"metadata.column_header「{col}」非 {period}（{ad}）之本期欄")

    if problems:
        findings.append(dict(
            dataset=ds, id=q["id"], qtype=q.get("question_type"),
            question=q.get("question", ""), gold=gold,
            defect="D2_wrong_column_period", detail="；".join(problems),
            company_code="/".join(map(str, codes)), period=period,
            table_name=table, item_name=item, column_header=col,
            correct_by_company=truth))


def audit_ratio(q, corpus: Corpus, findings: list, ds: str):
    """檢查比率題：原始的分子、分母和最後算出的百分比都要正確。"""
    md = q.get("metadata", {})
    code, period = md.get("company_code"), md.get("quarter")
    num_item, den_item = md.get("numerator_item"), md.get("denominator_item")
    num_raw, den_raw = md.get("numerator_raw"), md.get("denominator_raw")
    ad = roc_to_ad(period)
    problems = {}
    for tag, item, raw in (("分子", num_item, num_raw), ("分母", den_item, den_raw)):
        cands = corpus.rows_any_table(code, period, item)
        hits = [(t, c, v) for t, c, v in cands if ad in col_years(c)]
        vals = {norm_num(v) for _t, _c, v in hits}
        if vals and norm_num(raw) not in vals:
            in_cmp = any(norm_num(raw) == norm_num(v) for _t, c, v in cands
                         if ad not in col_years(c))
            problems[tag] = (f"{tag}「{item}」金標 {raw} "
                             f"{'取自比較欄' if in_cmp else '不在語料'}，"
                             f"本期正解 {sorted({str(v) for _t, _c, v in hits})}")
    # 比率算術一致性
    n, d = norm_num(num_raw), norm_num(den_raw)
    if n and d and float(d) != 0:
        calc = round(float(n) / float(d) * 100, 2)
        if abs(calc - float(q.get("expected_ratio", calc))) > 0.02:
            problems["算術"] = (f"expected_ratio {q.get('expected_ratio')} 與 "
                               f"{num_raw}/{den_raw}*100={calc} 不符")
    if problems:
        findings.append(dict(
            dataset=ds, id=q["id"], qtype="ratio", question=q.get("question", ""),
            gold=q.get("expected_answer"), defect="D2_wrong_column_period",
            detail="；".join(problems.values()), company_code=code, period=period,
            table_name="", item_name=f"{num_item} / {den_item}", column_header=""))


def audit_ratio_cross_company(q, corpus: Corpus, findings: list, ds: str):
    """檢查兩家公司比率比較題。

    不能只看最後一句「A公司比較高」。程式會從頭檢查：
    兩家公司的分子 → 分母 → 百分比 → 最後哪一家比較高。
    其中任何一步錯誤，整題金標就不可靠。
    """
    md = q.get("metadata", {})
    period = md.get("quarter")
    ad = roc_to_ad(period)
    num_item, den_item = md.get("numerator_item"), md.get("denominator_item")
    problems: list[str] = []

    for c in md.get("companies", []):
        code, alias = c.get("company_code"), c.get("alias")
        for tag, item, raw in (("分子", num_item, c.get("numerator_raw")),
                               ("分母", den_item, c.get("denominator_raw"))):
            sub = corpus.df[(corpus.df.stock_code == str(code)) &
                            (corpus.df.period == str(period)) &
                            (corpus.df.item_name.str.startswith(str(item), na=False))]
            cands = [(r.table_name, r.column_header, r.value_raw)
                     for r in sub.itertuples(index=False)]
            hits = [(t, col, v) for t, col, v in cands if ad in col_years(col)]
            vals = {norm_num(v) for _t, _c, v in hits}
            if vals and norm_num(raw) not in vals:
                in_cmp = any(norm_num(raw) == norm_num(v) for _t, col, v in cands
                             if ad not in col_years(col))
                problems.append(f"{alias} {tag}「{item}」金標 {raw} "
                                f"{'取自比較欄' if in_cmp else '不在語料'}")
        n, d = norm_num(c.get("numerator_raw")), norm_num(c.get("denominator_raw"))
        if n and d and float(d) != 0:
            calc = round(float(n) / float(d) * 100, 2)
            if abs(calc - float(c.get("ratio_value", calc))) > 1e-9:
                problems.append(f"{alias} 比率 {c.get('ratio_value')} 與 "
                                f"{c.get('numerator_raw')}/{c.get('denominator_raw')}"
                                f"*100={calc} 不符")

    cs = md.get("companies", [])
    if len(cs) == 2:
        a, b = cs
        if a.get("ratio_value") == b.get("ratio_value"):
            problems.append("兩家比率完全相同，「誰比較高」無唯一解")
        else:
            w = a["alias"] if a["ratio_value"] > b["ratio_value"] else b["alias"]
            if w != q.get("expected_winner"):
                problems.append(f"結論欄 expected_winner={q.get('expected_winner')} "
                                f"與比率大小（應為 {w}）不符")
            want = (f"{a['alias']}: {a['ratio_value']}% ｜ "
                    f"{b['alias']}: {b['ratio_value']}% ｜ 較高: {w}")
            if str(q.get("expected_answer", "")).strip() != want:
                problems.append("expected_answer 字串與各欄位不一致")

    if problems:
        findings.append(dict(
            dataset=ds, id=q["id"], qtype="ratio_cross_company",
            question=q.get("question", ""), gold=q.get("expected_answer"),
            defect="D9_ratio_cross_company", detail="；".join(problems),
            company_code="/".join(str(c.get("company_code")) for c in cs),
            period=period, table_name="",
            item_name=f"{num_item} / {den_item}", column_header=""))



# ─────────────── [P2] 題型／題幹語意稽核（N31 / N33）───────────────
# 來源表關鍵字 → 應有的 question_type（稽核 §27）
_SOURCE_TO_QTYPE = {
    "轉投資大陸地區之事業相關資訊": "mainland_investment_graph",
    "母子公司間業務關係及重要交易往來情形": "related_party_transaction_graph",
    "被投資公司名稱": "investment_graph",
}
# 題幹中無語意的列序號：「的【0】中」「的【7】涉及」（稽核 §33 / N33）
_ROW_INDEX_RE = re.compile(r"的\s*【\s*\d{1,3}\s*】\s*(?:中|涉及|是|，)")


def audit_question_type_consistency(q: dict, findings: list, ds: str) -> None:
    """
    D10：question_type 與 metadata.source_csv 的實際來源表不一致。

    例：arch_test_084 的來源是「轉投資大陸地區之事業相關資訊」，
    卻被標成 related_party_transaction_graph（稽核 §27 / N31）。
    """
    md = q.get("metadata", {}) or {}
    src = str(md.get("source_csv") or md.get("source_fact_file") or "")
    qtype = str(q.get("question_type") or "")
    if not src or not qtype:
        return
    # 只稽核「宣稱自己是某類圖譜題」的題目：一般數值題的來源表是附帶資訊，
    # 其金標來源問題已由 D2／D7 涵蓋，在此重複判定只會產生噪音。
    if "graph" not in qtype:
        return
    for key, expect in _SOURCE_TO_QTYPE.items():
        if key in src and qtype != expect:
            findings.append(dict(
                dataset=ds, id=q.get("id"), qtype=qtype,
                question=q.get("question", ""), gold=q.get("expected_answer"),
                defect="D10_question_type_mismatch",
                detail=f"來源表為「{key}」，question_type 應為 {expect}，"
                       f"實為 {qtype}",
                company_code=md.get("company_code", ""),
                period=md.get("quarter", ""), table_name=key,
                item_name="", column_header=""))
            return


def audit_row_index_in_question(q: dict, findings: list, ds: str) -> None:
    """
    D11：題幹使用原表列序號（「在【0】中」）作為識別鍵。

    列序號沒有會計語意，使用者不可能這樣提問，且同一序號在不同期別指向不同列
    （稽核 §33 / N33）。題目應改用交易人／交易對象／科目等語意主鍵。
    """
    text = str(q.get("question") or "")
    m = _ROW_INDEX_RE.search(text)
    if m:
        findings.append(dict(
            dataset=ds, id=q.get("id"), qtype=q.get("question_type"),
            question=text, gold=q.get("expected_answer"),
            defect="D11_row_index_in_question",
            detail=f"題幹含無語意列序號「{m.group(0).strip()}」，"
                   f"應改用語意主鍵（交易人／交易對象／科目）",
            company_code=(q.get("metadata") or {}).get("company_code", ""),
            period=(q.get("metadata") or {}).get("quarter", ""),
            table_name="", item_name="", column_header=""))


def main():
    """從這裡開始執行整批檢查。

    不加參數：檢查原始題庫，產生「修正前」報告。
    加 `--v3`：檢查修正版題庫，產生「修正後」報告。

    每讀到一題，就先看它是哪一種題目，再交給對應的檢查函式。
    """
    global DATASETS
    v3 = "--v3" in sys.argv
    suffix = "_after" if v3 else "_before"
    if v3:
        DATASETS = [p.name for p in sorted(QDIR.glob("*_v3.json"))]

    corpus = Corpus(FACTS)
    findings: list[dict] = []
    stats = {}

    for name in DATASETS:
        p = QDIR / name
        if not p.exists():
            continue
        data = json.loads(p.read_text(encoding="utf-8"))
        before = len(findings)
        for q in data:
            t = (q.get("question_type") or "").lower()
            # 不論是哪種題目，都先檢查「題型有沒有標錯」及
            # 「題目有沒有使用一般人看不懂的原表列序號」。
            audit_question_type_consistency(q, findings, name)
            audit_row_index_in_question(q, findings, name)
            if "period_compare" in t:
                audit_period_compare(q, corpus, findings, name)
            elif "company_compare" in t:
                audit_company_compare(q, corpus, findings, name)
            elif t == "ratio_cross_company":
                audit_ratio_cross_company(q, corpus, findings, name)
            elif name.startswith("ratio"):
                audit_ratio(q, corpus, findings, name)
            elif "graph" in t or "risk" in t or "supply" in t or "investment" in t \
                    or "related_party" in t:
                if is_corrupt_gold(q.get("expected_answer")):
                    findings.append(dict(
                        dataset=name, id=q["id"], qtype=q.get("question_type"),
                        question=q.get("question", ""), gold=q.get("expected_answer"),
                        defect="D3_corrupt_gold",
                        detail="圖譜題金標為附註代號或整列傾印，無法評分",
                        company_code=q.get("metadata", {}).get("company_code", ""),
                        period=q.get("metadata", {}).get("quarter", ""),
                        table_name="", item_name="", column_header=""))
            else:
                audit_numeric(q, corpus, findings, name)
        stats[name] = dict(total=len(data), findings=len(findings) - before)

    real = [f for f in findings if not f["defect"].startswith("OK_")]
    explicit_ok = [f for f in findings if f["defect"].startswith("OK_")]

    OUTDIR.mkdir(exist_ok=True)
    (OUTDIR / f"dataset_audit{suffix}.json").write_text(
        json.dumps(dict(stats=stats, findings=findings), ensure_ascii=False, indent=2),
        encoding="utf-8")

    lines = ["# 資料集金標稽核報告", "",
             f"稽核對象：{'修正後 `*_v3.json`' if v3 else '原始資料集'}", "",
             f"語料：`__all_company_all_period_numeric_facts.csv`（{len(corpus.df):,} 筆事實）", "",
             "## 各資料集缺陷數", "",
             "| 資料集 | 題數 | 缺陷題數 |", "|---|---:|---:|"]
    for k, v in stats.items():
        n_real = len([f for f in real if f["dataset"] == k])
        lines.append(f"| `{k}` | {v['total']} | {n_real} |")
    lines += ["", f"**合計缺陷 {len(real)} 題**"
                  f"（另有 {len(explicit_ok)} 題題目文字已明寫欄位標頭，判定為非缺陷）", "",
              "## 缺陷類型分佈", "", "| 代碼 | 題數 | 說明 |", "|---|---:|---|"]
    desc = {"D1_gold_not_in_corpus": "金標值在該科目所有欄位中皆不存在",
            "D6_item_name_mismatch": "科目名中英文指向不同科目（語料表頭誤併）",
            "D7_prior_period_source": "金標取自「去年同期」報表，非所問期間之當期值",
            "D9_ratio_cross_company": "跨公司比率題之分子分母／比率算術／孰高結論不自洽",
            "D10_question_type_mismatch": "question_type 與來源表不符（如大陸投資題標成關係人交易）",
            "D11_row_index_in_question": "題幹使用無語意的原表列序號作為識別鍵",
            "D2_wrong_column_period": "金標取自去年同期比較欄（題目未指定欄位）",
            "D3_corrupt_gold": "金標為附註代號／整列傾印，非可評分答案",
            "D4_same_value_two_period": "跨期比較題兩期金標同值，實際兩期不同",
            "D5_ambiguous_row": "同科目同欄位對到多列相異值"}
    for k, c in Counter(f["defect"] for f in real).most_common():
        lines.append(f"| `{k}` | {c} | {desc.get(k, '')} |")

    for dcode in sorted({f["defect"] for f in real}):
        subset = [f for f in real if f["defect"] == dcode]
        lines += ["", f"## {dcode}（{len(subset)} 題）", ""]
        for f in subset:
            lines += [f"**[{f['id']}]** {f['question']}", "",
                      f"- 資料集：`{f['dataset']}`　題型：{f['qtype']}",
                      f"- 現行金標：`{f['gold']}`",
                      f"- 定位：{f['company_code']} / {f['period']} / "
                      f"{f['table_name']} / {f['item_name']} / {f['column_header']}",
                      f"- 診斷：{f['detail']}", ""]

    (OUTDIR / f"dataset_audit{suffix}.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"缺陷 {len(real)} 題（非缺陷 {len(explicit_ok)} 題）")
    for k, c in Counter(f["defect"] for f in real).most_common():
        print(f"  {k}: {c}")
    print(f"→ {OUTDIR/('dataset_audit'+suffix+'.md')}")


if __name__ == "__main__":
    sys.exit(main())
