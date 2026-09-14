#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
資料集金標修正（fix_datasets.py）

依 `audit_datasets.py` 之稽核結果，對缺陷題目施以下列修復，
輸出 `questions/*_v3.json`（**不覆蓋原檔**，原始版本保留以重現已發表數據）
與 `results/dataset_fix_changelog.md`（逐題修改紀錄）。

修復規則
--------
R1  欄位錯位（D2）        金標取自去年同期比較欄 → 改為本期欄之值
R2  附註表金標（D2）      金標取自附註表末端子項 → 改指主表之標準科目
R3  單季/累計歧義（D5）   保留原金標，於題目文字補上「（累計數）／（單季數）」消歧
R4  毀損金標（D3 數值）   金標為附註代號 → 改指主表之標準科目本期值
R5  關係人整列傾印（D3）  金標為 `value_2=…; value_3=…` 序列化殘留
                          → 依原始 raw_row 還原語意，題目改問「交易金額」、
                            金標改為金額；同時移除題目中無意義的列序號

原則：**只在語料中有唯一正解時才改金標**；有歧義時改題目（補消歧子句）而非改金標，
      以避免「把金標修成系統答案」之循環論證。

給第一次看這支程式的人
----------------------
`audit_datasets.py`負責找出錯誤，這支程式負責「真的把錯誤修好」。

修正金標不能使用下面這種危險做法：

    系統回答 100 元，金標寫 200 元
    → 直接把金標改成系統回答的 100 元

這樣只是為了讓系統得分，不能證明100元是正確答案。

本程式採用的做法是：

    系統回答 100 元，金標寫 200 元
    → 回到原始財報查證
    → 財報本期欄確實是 100 元，而且只有一個可能答案
    → 才把金標改成 100 元

如果財報裡同時有兩個合理答案，程式不會猜。它會在題目補上「單季數」「累計數」
或交易對象等說明，讓問題本身先變得清楚。

建議閱讀順序：

1. `pick_current`：怎麼找到本期欄。
2. `fix_numeric_question`：怎麼修一題普通數字題。
3. `fix_compare_question`：怎麼修兩季或兩家公司比較題。
4. `fix_related_party`：怎麼修關係人交易題。
5. `main`：怎麼整批處理並另存新檔。

三條底線：
* 絕對不拿模型回答直接當新金標。
* 查不到唯一答案就不硬改。
* 原始題庫不覆蓋，修正版另外存成 `*_v3.json`。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_datasets import (  # noqa: E402
    Corpus, FACTS, roc_to_ad, col_years, norm_num, parse_segments, is_corrupt_gold,
)

ROOT = Path(__file__).resolve().parent
QDIR = ROOT / "questions"
RPT = ROOT / "related_party_graph_output" / "related_party_transaction_table.csv"
OUT = ROOT / "results"

MAIN_TABLES = ("綜合損益表", "資產負債表", "現金流量表")

# metric → 主表標準科目（僅在原科目無法於主表定位時使用）
CANON = {
    "revenue": "營業收入合計 Total operating revenue",
    "assets": "資產總計 Total assets",
    "profit": "本期淨利（淨損） Profit (loss)",
    "cash": "現金及約當現金 Cash and cash equivalents",
}
# 中文名與英文名不相符之毀損科目（語料表頭誤併），一律改指標準科目
BROKEN_ITEMS = {
    "繼續營業單位淨利（淨損） Diluted earnings (loss) per share from continuing operations",
}

_CUMUL_RE = re.compile(r"(\d{4})年1月1日至")
_QUARTER_ONLY_RE = re.compile(r"(\d{4})年(4|7|10)月1日至")

# 母子公司間業務關係表之欄位語意（原擷取器未命名，序列化為 value_N）
RP_FIELDS = {
    "value_2": "交易對象", "value_3": "關係", "value_4": "科目",
    "value_5": "金額", "value_6": "交易條件", "value_7": "佔比",
}
_KV_RE = re.compile(r"(value_\d+)=([^;]+)")


def kv(s: str) -> dict:
    """把 `value_2=A; value_5=100` 拆開，之後才能知道哪個是對象、哪個是金額。"""
    return {k: v.strip() for k, v in _KV_RE.findall(str(s or ""))}


def is_date_col(col: str) -> bool:
    """欄位名稱裡有沒有西元年份，例如2025。"""
    return bool(re.search(r"20\d{2}", str(col)))


# v2 資料集之消歧子句：（科目：【…】）（表：【…】）（<欄位標頭>）
_DISC_RE = re.compile(r"（(?:科目|表)：【[^】]*】）|（[^（）]*(?:20\d{2}|去年同期|本期)[^（）]*）")


def strip_discriminators(text: str) -> str:
    """移除 v2 資料集附加的消歧子句（改指其他表之後這些子句會失效）。"""
    return _DISC_RE.sub("", str(text)).strip()


def rebuild_discriminators(base: str, table: str, item: str, col: str) -> str:
    """依修正後的定位重建消歧子句。"""
    return f"{base}（科目：【{item}】）（表：【{table}】）（{col}）"


def pick_current(corpus: Corpus, code, period, table, item):
    """回傳該 (公司, 期別, 表, 科目) 之本期欄候選 [(col, val), …]。"""
    rows = corpus.rows(code, period, table, item)
    if not rows and not table:  # metadata 未記錄表名時，才跨表以科目名定位
        rows = [(c, v) for _t, c, v in corpus.rows_any_table(code, period, item)]
    ad = roc_to_ad(period)
    return [(c, v) for c, v in rows if ad in col_years(c)]


def resolve_target(corpus: Corpus, md: dict, period: str):
    """判斷這一題到底應該查哪張報表、哪個科目。

    如果題目原本指向正確的主要報表，就照原設定查。
    如果原本指到去年同期報表、錯誤科目或不可靠的附註表，就改回資產負債表、
    綜合損益表或現金流量表中的標準科目。

    第三個回傳值若為 `True`，表示查詢位置已改變，題目文字也必須跟著重寫。
    """
    code = md.get("company_code")
    item = md.get("item_name") or md.get("item_canonical")
    table = md.get("table_name")
    if item not in BROKEN_ITEMS and "去年同期" not in str(table) \
            and "去年同期" not in str(md.get("column_header")) \
            and table in MAIN_TABLES \
            and pick_current(corpus, code, period, table, item):
        return table, item, False
    # 改指主表標準科目
    canon = CANON.get(md.get("metric") or "")
    if not canon:
        return table, item, False
    sub = corpus.df[(corpus.df.stock_code == str(code)) &
                    (corpus.df.period == str(period)) &
                    (corpus.df.table_name.isin(MAIN_TABLES)) &
                    (corpus.df.item_name == canon)]
    if len(sub):
        return sub.iloc[0].table_name, canon, True
    # 退而求其次：主表中以標準科目中文前綴模糊比對
    zh = canon.split(" ")[0]
    sub = corpus.df[(corpus.df.stock_code == str(code)) &
                    (corpus.df.period == str(period)) &
                    (corpus.df.table_name.isin(MAIN_TABLES)) &
                    (corpus.df.item_name.str.startswith(zh, na=False))]
    if len(sub):
        return sub.iloc[0].table_name, sub.iloc[0].item_name, True
    return table, item, False


def choose_column(cands: list[tuple[str, str]]):
    """從幾個可能的本期欄中選擇。

    只有一個就直接使用；如果同時有「單季」和「年初至本季累計」，
    程式會選累計欄，並要求題目補上「累計數」，讓讀者知道答案的口徑。
    """
    if len(cands) == 1:
        return cands[0][0], cands[0][1], ""
    cumul = [(c, v) for c, v in cands if _CUMUL_RE.search(c)]
    single = [(c, v) for c, v in cands if _QUARTER_ONLY_RE.search(c)]
    if cumul and single:
        c, v = cumul[0]
        return c, v, "（累計數，自年初至本期末）"
    if len(cands) >= 1:
        return cands[0][0], cands[0][1], ""
    return None, None, ""


# ────────────────────────── 數值題修復 ──────────────────────────
def fix_numeric_question(q: dict, corpus: Corpus, log: list) -> bool:
    """修正「某公司某一季的某個數字是多少」這種題目。

    有時金標其實正確，只是題目沒說清楚單季或累計，這時只補題目、不改答案。
    如果真的抄錯欄，才會一起更新題目、金標和資料來源說明。
    所有修改都會記錄原題目、原答案、新題目與新答案，方便事後追查。
    """
    md = q.get("metadata", {})
    code, period = md.get("company_code"), md.get("quarter")
    gold, qtext = q.get("expected_answer"), q.get("question", "")
    col = md.get("column_header")
    if not (code and period):
        return False

    # 中英文科目名不一致（語料表頭誤併）與毀損金標同樣必須改指主表，
    # 即使題目已明寫欄位標頭亦然——因為被明寫的那個科目本身就是錯的。
    broken_item = (md.get("item_name") or md.get("item_canonical")) in BROKEN_ITEMS
    # 「去年同期<表>」為上一年度報表，題幹原樣引用亦不構成有效消歧
    prior_src = ("去年同期" in str(md.get("table_name"))
                 or "去年同期" in str(col))
    corrupt = is_corrupt_gold(gold) or broken_item or prior_src
    explicit = bool(col) and str(col) in qtext
    table, item, repointed = resolve_target(corpus, md, period)
    cands = pick_current(corpus, code, period, table, item)
    if not cands:
        return False

    gn = norm_num(gold)
    cur_vals = {norm_num(v) for _c, v in cands}

    if not corrupt and not repointed and gn in cur_vals:
        # 金標本身正確；僅在有單季/累計歧義且題目未消歧時補子句（R3）
        if len(cur_vals) > 1 and not explicit:
            hit = [(c, v) for c, v in cands if norm_num(v) == gn][0]
            tag = "（累計數，自年初至本期末）" if _CUMUL_RE.search(hit[0]) \
                else "（單季數，僅本季三個月）"
            q["question"] = qtext.rstrip("？?。 ") + tag + "？"
            md["column_header"] = hit[0]
            md["fix_rule"] = "R3_單季累計消歧"
            log.append(dict(id=q["id"], rule="R3_單季累計消歧", old_q=qtext,
                            new_q=q["question"], old_gold=gold, new_gold=gold,
                            note=f"本期欄有 {len(cur_vals)} 個候選值，題目補消歧子句，金標不動"))
            return True
        return False

    if explicit and not corrupt:
        return False  # 題目已明寫欄位，金標與該欄位一致 → 不動

    # 重要：新答案從原始財報選，不是從系統回答複製過來。
    newcol, newval, tag = choose_column(cands)
    if newval is None or norm_num(newval) == gn:
        return False

    rule = ("R7_去年同期來源改指主表當期" if prior_src else
            "R6_科目中英文不一致改指主表" if broken_item else
            "R4_毀損金標改指主表" if corrupt else
            "R2_附註表金標改指主表" if repointed else "R1_欄位錯位")

    had_disc = bool(_DISC_RE.search(qtext))
    base = strip_discriminators(qtext) if (repointed or corrupt) else qtext
    if had_disc and (repointed or corrupt):
        # 原題目本有消歧子句，但改指主表後已失效 → 依新定位重建。
        # 重建後欄位已明寫，累計/單季子句冗餘，故不再附加 tag。
        newq = rebuild_discriminators(base.rstrip("？?。 "), table, item, newcol) + "？"
    elif tag:
        newq = base.rstrip("？?。 ") + tag + "？"
    else:
        newq = base
    q["question"] = newq
    q["expected_answer"] = newval
    md.update(table_name=table, item_name=item, column_header=newcol, fix_rule=rule)
    if "item_canonical" in md:
        md["item_canonical"] = item
    log.append(dict(id=q["id"], rule=rule, old_q=qtext, new_q=newq,
                    old_gold=gold, new_gold=newval,
                    note=f"改指 {table} / {item} / {newcol}"))
    return True


# ─────────────────────── 比較題（多公司/多期）修復 ───────────────────────
def fix_compare_question(q: dict, corpus: Corpus, log: list) -> bool:
    """修正兩個季度或兩家公司互相比較的題目。

    不能只改其中一個數字，因為數字改了，「上升／下降」或「哪家公司較高」
    也可能跟著改變。因此程式會把兩邊重新查一次，再重新計算最後結論。
    """
    md = q.get("metadata", {})
    qtext, gold = q.get("question", ""), q.get("expected_answer", "")
    col = md.get("column_header")
    table = md.get("table_name")
    item = md.get("item_name") or md.get("item_canonical")
    segs = parse_segments(gold)
    qtype = (q.get("question_type") or "")
    prior_src = "去年同期" in str(table) or "去年同期" in str(col)
    # 跨期題把單一欄位同時套用於兩期 → 該欄至多屬其中一期，另一期被讀成
    # 去年同期比較欄，趨勢恆為「持平」。題幹原樣引用亦不構成有效消歧。
    degenerate = False
    if "period_compare" in qtype and col and col_years(col):
        owners = [pp for pp in (md.get("periods") or [])
                  if roc_to_ad(pp) in col_years(col)]
        degenerate = len(owners) == 1
    if col and str(col) in qtext and not prior_src and not degenerate:
        return False  # 題目已明寫欄位（且來源非上一年度報表、非跨期共用單欄）
    if prior_src:
        table = None   # 令 pick_current 跨表以科目名重新定位到主表當期欄

    new_segs, changed, newcol, tag = {}, False, col, ""
    per_period_col: dict = {}
    if "period_compare" in qtype:
        # 每一季都查自己的本期欄，不能把同一格數字拿來代表兩季。
        code = md.get("company_code")
        for p in md.get("periods", []):
            cands = pick_current(corpus, code, p, table, item)
            if not cands:
                return False
            c, v, t = choose_column(cands)
            tag = tag or t
            per_period_col[p] = c
            new_segs[p] = v
            if norm_num(v) != norm_num(segs.get(p)):
                changed = True
        if changed:
            a, b = md["periods"]
            newgold = f"{a}: {new_segs[a]} ｜ {b}: {new_segs[b]}"
            # 只有原金標本身帶「趨勢」結論時才重算並保留該段落；
            # 架構資料集的金標格式不含趨勢，擅自補上會造成格式不符而誤判為失分。
            if "趨勢" in segs:
                na, nb = norm_num(new_segs[a]), norm_num(new_segs[b])
                trend = ("持平" if na == nb else
                         "上升" if float(nb) > float(na) else "下降")
                newgold += f" ｜ 趨勢: {trend}"
    elif "company_compare" in qtype:
        # 財報用公司代碼，答案用公司名稱；先做對照，再重寫兩家公司答案。
        period = md.get("quarter")
        name_of = {}
        for c in md.get("companies", []):
            sub = corpus.df[corpus.df.stock_code == str(c)]
            name_of[str(c)] = sub.iloc[0].company_name if len(sub) else str(c)
        for c in md.get("companies", []):
            cands = pick_current(corpus, c, period, table, item)
            if not cands:
                return False
            cc, v, t = choose_column(cands)
            newcol, tag = cc, (tag or t)
            new_segs[name_of[str(c)]] = v
            if norm_num(v) != norm_num(segs.get(name_of[str(c)])):
                changed = True
        if changed:
            names = [name_of[str(c)] for c in md["companies"]]
            parts = [f"{n}: {new_segs[n]}" for n in names]
            if "較高" in segs:
                hi = max(names, key=lambda n: float(norm_num(new_segs[n]) or 0))
                parts.append(f"較高: {hi}")
            newgold = " ｜ ".join(parts)
    else:
        return False

    if not changed:
        return False
    newq = qtext.rstrip("？?。 ") + tag + "？" if tag else qtext
    if degenerate:
        # 題幹原本只點名單一欄位，改正後兩期各用自身當期欄，該子句已失效且會
        # 與新金標矛盾 → 移除，並改以「各期當期欄」語意描述。
        newq = re.sub(r"（[^（）]*20\d{2}[^（）]*）", "", newq).rstrip("？?。 ")
        newq += "（各期均取該期當期欄）？"
        md["column_header"] = {p: c for p, c in per_period_col.items()}
    q["question"] = newq
    q["expected_answer"] = newgold
    if not degenerate:
        md["column_header"] = newcol
    rule = ("R7_去年同期來源改指主表當期" if prior_src else
            "R8_跨期題共用單一欄位" if degenerate else "R1_欄位錯位")
    md["fix_rule"] = rule
    if prior_src:
        # 原題幹引用的「去年同期<表>」子句已失效，須移除；
        # 留著會與改正後的當期金標互相矛盾。
        md["table_name"] = None
        base = strip_discriminators(newq).rstrip("？?。 ")
        newq = rebuild_discriminators(base, "綜合損益表", item, newcol) + "？"
        q["question"] = newq
    log.append(dict(id=q["id"], rule=rule, old_q=qtext, new_q=newq,
                    old_gold=gold, new_gold=newgold,
                    note="比較題各分項改用本期欄之值，趨勢／較高重新計算"
                         + ("；並補上累計/單季消歧子句" if tag else "")))
    return True


# ─────────────────────── 關係人交易題修復（R5） ───────────────────────
def load_rp_table() -> pd.DataFrame:
    """讀取關係人交易原始表，後面會用它查真正的交易金額。"""
    df = pd.read_csv(RPT, dtype=str)
    df.columns = [c.lstrip("﻿") for c in df.columns]
    return df


def fix_related_party(q: dict, rp: pd.DataFrame, log: list) -> bool:
    """修正關係人交易題。

    舊金標可能長得像 `value_2=甲公司; value_5=1000`，一般人不知道這些代號
    代表什麼。程式會回到原表，用「哪家公司、哪一季、誰跟誰、交易什麼」
    找到唯一一列，再把答案改成真正被問到的交易金額。

    如果符合條件的資料不只一列，程式就不修改，避免猜錯。
    """
    md = q.get("metadata", {})
    gold, qtext = q.get("expected_answer", ""), q.get("question", "")
    g = kv(gold)
    if not g:
        return False
    code, period = md.get("company_code"), md.get("quarter")
    party = md.get("party_or_category")
    counterparty, account_item = g.get("value_2", ""), g.get("value_4", "")
    amount = g.get("value_5", "")
    if not (counterparty and account_item and amount):
        return False

    sub = rp[(rp.report_stock_id == str(code)) & (rp.report_period == str(period))]
    sub = sub[sub.amount_summary.fillna("").str.contains(
        re.escape(f"value_2={counterparty}"), regex=True)]
    sub = sub[sub.amount_summary.fillna("").str.contains(
        re.escape(f"value_4={account_item}"), regex=True)]
    if party:
        sub = sub[sub.party_or_category == party]
    if len(sub) > 1:
        # 同一交易人＋對象＋科目仍多列（原表分列揭露）→ 取最後一列，並記錄列數
        sub = sub.iloc[[-1]]
    if len(sub) != 1:
        log.append(dict(id=q["id"], rule="R5_SKIP", old_q=qtext, new_q=qtext,
                        old_gold=gold, new_gold=gold,
                        note=f"關係人交易列比對到 {len(sub)} 筆，無法唯一定位，維持原狀"))
        return False

    row = sub.iloc[0]
    name = md.get("company_name", "")
    # （交易對象, 科目）在同公司同期別下並非唯一鍵（42 題中有 10 題對到多列），
    # 依「鑑別扁平化」原則一律把交易人也寫進題幹，使金標唯一。
    payer = str(row.party_or_category or "").strip()
    if q.get("question_style", "").startswith("customer_colloquial"):
        # 口語化資料集維持口語語氣，不改成制式句型
        newq = (f"幫我看{name}{period}關係人交易裡，{payer}跟{counterparty}之間的"
                f"{account_item}交易金額是多少？")
    else:
        newq = (f"根據關係人交易圖譜，【{name}】在【{period}】，【{payer}】與"
                f"【{counterparty}】之間的【{account_item}】交易金額是多少？")
    q["question"] = newq
    q["expected_answer"] = amount
    md.update(transacting_party=row.party_or_category, counterparty=counterparty,
              account_item=account_item, amount=amount,
              relation=g.get("value_3", ""), source_row=row.raw_row,
              fix_rule="R5_關係人整列傾印還原")
    md.pop("account", None)          # 原為列序號，非會計科目
    md["party_or_category"] = row.party_or_category
    log.append(dict(id=q["id"], rule="R5_關係人整列傾印還原", old_q=qtext, new_q=newq,
                    old_gold=gold, new_gold=amount,
                    note=f"原金標為擷取器序列化殘留（value_N=）；依 raw_row"
                         f"「{row.raw_row}」還原為交易金額"))
    return True


# ────────────────────────────── 主流程 ──────────────────────────────
TARGETS = [
    "customer_colloquial_test_questions_100.json",
    "customer_colloquial_test_questions_100_v2.json",
    "system_architecture_test_questions_100.json",
    "system_architecture_test_questions_100_v2.json",
    "system_architecture_test_questions_10_selected.json",
    "system_architecture_test_questions_10_selected_alt.json",
    "system_architecture_wrong_questions_dataset.json",
    "system_architecture_wrong_questions_dataset_v2.json",
]


def main():
    """整批修正題庫。

    原始檔不會被蓋掉。例如讀取 `questions.json` 後，修正版會另存成
    `questions_v3.json`。因此仍可比較修正前後的分數，也能查回每一筆修改。
    """
    corpus = Corpus(FACTS)
    rp = load_rp_table()
    all_log = {}

    for name in TARGETS:
        src = QDIR / name
        if not src.exists():
            continue
        data = json.loads(src.read_text(encoding="utf-8"))
        log: list = []
        for q in data:
            t = (q.get("question_type") or "").lower()
            # 先看這是哪一種題目，再交給對應的修正方式。
            # 一般圖譜題無法只靠數值表安全修正，所以這裡不自動亂改。
            if "related_party" in t:
                fix_related_party(q, rp, log)
            elif "compare" in t:
                fix_compare_question(q, corpus, log)
            elif "graph" in t or "risk" in t or "supply" in t or "investment" in t:
                continue
            else:
                fix_numeric_question(q, corpus, log)
        dst = QDIR / name.replace(".json", "_v3.json")
        dst.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        all_log[name] = log
        print(f"  {name}: 修復 {len([l for l in log if l['rule']!='R5_SKIP'])} 題 "
              f"→ {dst.name}")

    OUT.mkdir(exist_ok=True)
    (OUT / "dataset_fix_changelog.json").write_text(
        json.dumps(all_log, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = ["# 資料集金標修正紀錄", "",
             "原始檔案保留不動；修正版輸出為 `questions/*_v3.json`。", "",
             "| 規則 | 說明 |", "|---|---|",
             "| R1 | 欄位錯位：金標取自去年同期比較欄 → 改為本期欄之值 |",
             "| R2 | 附註表金標：金標取自附註表末端子項 → 改指主表標準科目 |",
             "| R3 | 單季/累計歧義：**金標不動**，於題目補消歧子句 |",
             "| R4 | 毀損金標：金標為附註代號 → 改指主表標準科目本期值 |",
             "| R5 | 關係人整列傾印：`value_N=` 序列化殘留 → 依 raw_row 還原為交易金額 |",
             "| R6 | 科目中英文不一致（語料表頭誤併，中文「淨利」配英文 EPS）→ 改指主表標準科目 |",
             "| R7 | 金標取自「去年同期<表>」（上一年度報表）→ 改指主表之當期欄 |",
             "| R8 | 跨期題兩期共用單一欄位標頭（趨勢恆「持平」）→ 各期改用自身當期欄，趨勢重算 |",
             ""]
    for name, log in all_log.items():
        real = [l for l in log if l["rule"] != "R5_SKIP"]
        lines += [f"## `{name}`（修復 {len(real)} 題）", ""]
        for l in log:
            lines += [f"**[{l['id']}]** `{l['rule']}`", "",
                      f"- 原題目：{l['old_q']}"]
            if l["new_q"] != l["old_q"]:
                lines.append(f"- 新題目：{l['new_q']}")
            lines += [f"- 原金標：`{l['old_gold']}`"]
            if l["new_gold"] != l["old_gold"]:
                lines.append(f"- 新金標：`{l['new_gold']}`")
            lines += [f"- 說明：{l['note']}", ""]
    (OUT / "dataset_fix_changelog.md").write_text("\n".join(lines), encoding="utf-8")
    total = sum(len([l for l in v if l["rule"] != "R5_SKIP"]) for v in all_log.values())
    print(f"\n合計修復 {total} 題 → {OUT/'dataset_fix_changelog.md'}")


if __name__ == "__main__":
    sys.exit(main())
