#!/usr/bin/env python3
"""
口語化基線 100 題（含提示版）失分歸因分析

背景
────
`results/test_eval_colloq_base.json` 之 EM 為 16%，84 題未精確命中。本腳本以
211,263 筆數值事實表反查「系統答案」與「金標」各自的來源列，將失分歸類，
以區分「系統真的答錯」與「金標本身不可靠」。

分類（互斥，依序判定）
──────────────────────
  F1 格式差異     數值全數正確，僅字串格式不同（如分隔符、缺少「趨勢:」尾綴）。
                  判定：評測器 numeric_match=True 而 exact_match=False。
  （文字型答案：圖譜題之金標本身為實體名稱／產業鏈分類／風險標籤，改以語意
     包含關係判定，歸入 F1／F6／F8，不套用數值比對。）
  F3 金標可疑     金標取自附註表或損益表末端零星子項（其他營業收入淨額、非控制
                  權益等），而系統答案取自該問題應對應之主要報表主科目。
                  此類系統實際答對，EM=0 係資料集生成瑕疵。
  F4 欄位錯位     系統與金標同公司同期同表同科目，僅 column_header 不同
                  （本期 vs 去年同期、單季 vs 累計）。屬 §1.2 失效類型 2。
  F5 科目歧義     口語詞可合理對應多個主要報表科目（「現金」可指資產負債表期末
                  餘額或現金流量表期末餘額；「獲利」可指稅前/稅後/母公司業主），
                  金標任選其一。系統答案亦落在主要報表之合理科目上。
  F6 部分正確     複合題（跨公司/跨季度）中部分數值正確。
  F7 拒答         系統回答「找不到相關資料」等。
  F8 真失效       以上皆非：系統取到與問題語意無關之科目，或答案無法在該公司
                  該期任何事實列中定位。

輸出
────
  results/colloq_base_failure_attribution.json   逐題歸因（含反查證據）
  results/colloq_base_failure_attribution.md     可讀對照表（口試備查用）

用法
────
    conda activate financial_crawler
    python3 analyze_colloq_base_failures.py
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

_V7 = Path(__file__).resolve().parent.parent / "legacy_v12"
FACTS = _V7 / "reports_csv_output" / "__all_company_all_period_numeric_facts.csv"
EVAL = Path("results/test_eval_colloq_base.json")
OUT_JSON = Path("results/colloq_base_failure_attribution.json")
OUT_MD = Path("results/colloq_base_failure_attribution.md")

_MAIN_TABLES = ("資產負債表", "綜合損益表", "現金流量表", "權益變動表")

# 附註／明細類表格（金標落於此處而問題問公司整體指標 → 高度可疑）
_NOTE_KW = (
    "母子公司間業務關係", "關係人", "轉投資", "大陸地區", "重要交易往來",
    "背書保證", "資金貸與", "衍生工具", "取得或處分", "子公司",
)
# 損益表末端零星子項／權益歸屬子項（非「獲利」「營收」之主科目）
_MINOR_ITEM_KW = (
    "其他營業收入", "非控制權益", "其他綜合損益",
    "基本每股盈餘", "稀釋每股盈餘", "每股盈餘",
)
# 「母公司業主（淨利／損）」為「淨利」之合理解讀（歸屬母公司業主之淨利），
# 與「本期淨利」並存屬語意歧義而非金標錯誤，故不列入上表。
_REFUSAL = ("找不到相關資料", "無法回答", "沒有相關資料", "不清楚", "查無資料")


def _norm_num(s) -> str | None:
    t = str(s).replace(",", "").replace(" ", "").strip()
    neg = t.startswith("(") and t.endswith(")")
    t = t.strip("()")
    if not re.fullmatch(r"-?\d+(?:\.\d+)?", t):
        return None
    return ("-" if neg else "") + t.lstrip("-") if neg else t


def _nums(s) -> set[str]:
    c = str(s).replace(",", "").replace("(", "").replace(")", "")
    return set(re.findall(r"\d+(?:\.\d+)?", c))


_SEP_RE = re.compile(r"[；;：:、｜|,，/\s]+")
_TAG_RE = re.compile(r"【([^】]+)】")
_STAGE_RE = re.compile(r"(上游|中游|下游)\s*[:：]\s*([^\s｜|、，,]+)")


def _norm_text(s) -> str:
    """移除分隔符、括號標記與空白，供文字答案的包含關係比對。"""
    t = str(s)
    t = t.replace("【", "").replace("】", "").replace("「", "").replace("」", "")
    return _SEP_RE.sub("", t)


def _text_tokens(gold) -> list[str]:
    """將文字金標依分隔符拆為關鍵詞（各自去除空白）。"""
    return [x for x in (_SEP_RE.sub("", p) for p in re.split(r"[；;、,]", str(gold))) if x]


def _count_extra_candidates(ans, gold_tokens, gold_raw="") -> int:
    """
    計算輸出中除金標外，另列出幾個同類候選（風險標籤或產業鏈階段）。

    比對基準同時納入「逐詞」與「整串」兩種形式：產業鏈金標「下游；IC通路」的
    分隔符與階段標記形式相同，拆詞後為 {下游, IC通路}，無法對上輸出中串接的
    「下游IC通路」，故須一併以整串正規化形式比對。
    """
    tags = set(_TAG_RE.findall(str(ans)))
    stages = {f"{a}{b}" for a, b in _STAGE_RE.findall(str(ans))}
    cands = tags | stages
    if not cands:
        return 0
    gset = {_SEP_RE.sub("", g) for g in gold_tokens}
    if gold_raw:
        gset.add(_norm_text(gold_raw))
    return sum(1 for c in cands if _SEP_RE.sub("", c) not in gset)


_PERIOD_RE = re.compile(r"^(\d{3})Q([1-4])$")


def _roc_to_ad_year(period: str) -> int | None:
    """民國季度標籤（113Q2）→ 該期別所屬西元年（2024）。"""
    m = _PERIOD_RE.match(str(period).strip())
    return int(m.group(1)) + 1911 if m else None


def _col_years(col: str) -> set[int]:
    """自欄位標頭抽出其中出現的西元年份。"""
    return {int(y) for y in re.findall(r"(20\d{2})", str(col))}


_SEG_SPLIT_RE = re.compile(r"[｜|]")
_KV_RE = re.compile(r"^\s*([^:：]+)[:：]\s*(.+?)\s*$")
# 趨勢/較高等結論性尾綴，不參與數值比對
_CONCLUSION_KEYS = ("較高", "趨勢", "差額", "差多少")


def _parse_segments(text: str) -> dict[str, str]:
    """
    解析複合式答案「公司A: 值 ｜ 公司B: 值 ｜ 較高: 公司A」為 {鍵: 值}。
    非 key:value 形式的片段以序號為鍵保留，供後續判定。
    """
    out: dict[str, str] = {}
    for i, seg in enumerate(_SEG_SPLIT_RE.split(str(text))):
        seg = seg.strip()
        if not seg:
            continue
        m = _KV_RE.match(seg)
        if m:
            out[m.group(1).strip()] = m.group(2).strip()
        else:
            out[f"_seg{i}"] = seg
    return out


def _is_corrupt_gold_value(v: str) -> bool:
    """金標值應為數字，卻是附註代號（如 D1、A2）等非數值字串。"""
    t = str(v).strip()
    if _norm_num(t) is not None:
        return False
    return bool(re.fullmatch(r"[A-Za-z]\d{1,2}", t))


def _is_refusal(a) -> bool:
    a = str(a).strip()
    return (not a) or a.startswith("[vLLM") or any(p in a for p in _REFUSAL)


def _is_note_table(t) -> bool:
    t = str(t)
    if any(t.strip().startswith(m) for m in _MAIN_TABLES):
        return False
    return any(k in t for k in _NOTE_KW) or t.strip() == "營業收入"


def _is_minor_item(i) -> bool:
    return any(k in str(i) for k in _MINOR_ITEM_KW)


def main() -> None:
    print("載入數值事實表 ...", flush=True)
    df = pd.read_csv(
        FACTS,
        usecols=["company_name", "period", "table_name", "item_name",
                 "column_header", "value_raw"],
        dtype=str, low_memory=False,
    )
    df["_v"] = df["value_raw"].map(_norm_num)
    print(f"  {len(df):,} 筆事實")

    items = json.loads(EVAL.read_text(encoding="utf-8"))["results"]
    fails = [x for x in items if not x["scores"]["exact_match"]]
    print(f"  未 EM 命中：{len(fails)}/{len(items)}\n")

    idx = {k: g for k, g in df.groupby(["company_name", "period"], sort=False)}

    out: list[dict] = []
    for it in fails:
        meta = it.get("metadata", {}) or {}
        sc = it["scores"]
        co, qtr = meta.get("company_name", ""), meta.get("quarter", "")
        g_tbl = meta.get("table_name", "") or ""
        g_item = meta.get("item_name", "") or ""
        ans, gold = str(it.get("answer", "")), str(it.get("expected_answer", ""))
        rd = it.get("router_decision", {}) or {}

        rec = {
            "id": it.get("id"), "question": it.get("question"),
            "company": co, "quarter": qtr,
            "system_answer": ans, "gold_answer": gold,
            "router_item": rd.get("item_name"),
            "gold_table": g_tbl, "gold_item": g_item,
            "gold_column": meta.get("column_header", ""),
            "numeric_match": sc.get("numeric_match"),
            "contains_match": sc.get("contains_match"),
        }

        # ── F1 格式差異 ────────────────────────────────────────
        if sc.get("numeric_match"):
            rec.update(category="F1_格式差異",
                       reason="數值集合與金標完全相同，僅字串格式不同")
            out.append(rec); continue

        # ── F7 拒答 ────────────────────────────────────────────
        if _is_refusal(ans):
            rec.update(category="F7_拒答", reason="系統回答找不到相關資料")
            out.append(rec); continue

        # ── 複合式答案（跨公司對比／跨季度趨勢）──────────────────
        # 格式為「鍵: 值 ｜ 鍵: 值 ｜ 較高/趨勢: X」，須逐段比對而非整串解析。
        g_segs = _parse_segments(gold)
        if len(g_segs) >= 2 and any(_KV_RE.match(x.strip())
                                    for x in _SEG_SPLIT_RE.split(gold) if x.strip()):
            a_segs = _parse_segments(ans)
            num_keys = [k for k in g_segs
                        if not any(c in k for c in _CONCLUSION_KEYS)]
            # 跨季度題之金標系統性錯欄偵測：
            # 兩個期別分屬不同民國年度（如 113Q4 vs 114Q4），金標值卻完全相同，
            # 表示後一年度取到了報表中的「去年同期比較欄」而非當期欄，
            # 導致趨勢結論一律被判為「持平」。
            pkeys = [k for k in num_keys if _PERIOD_RE.match(k.strip())]
            if len(pkeys) == 2:
                yrs = {_roc_to_ad_year(k) for k in pkeys}
                vals = {_norm_num(g_segs[k]) for k in pkeys}
                if len(yrs) == 2 and len(vals) == 1 and None not in vals:
                    rec.update(category="F3_金標可疑", reason=(
                        f"跨會計年度之兩期別（{pkeys[0]}／{pkeys[1]}）金標值完全相同"
                        f"（皆為 {g_segs[pkeys[0]]}），為後一年度取到去年同期比較欄所致；"
                        "趨勢結論因此恆為「持平」，無法作為評分基準"))
                    out.append(rec); continue

            corrupt = [k for k in num_keys if _is_corrupt_gold_value(g_segs[k])]
            if corrupt:
                rec.update(category="F2_金標毀損", reason=(
                    f"金標中 {len(corrupt)} 個欄位為附註代號而非數值"
                    f"（如 {corrupt[0]}: {g_segs[corrupt[0]]}），無法作為評分基準"))
                out.append(rec); continue
            hit = sum(1 for k in num_keys
                      if k in a_segs and _norm_num(a_segs[k]) is not None
                      and _norm_num(a_segs[k]) == _norm_num(g_segs[k]))
            if hit and hit == len(num_keys):
                rec.update(category="F1_格式差異", reason=(
                    f"複合題 {hit}/{len(num_keys)} 個數值全部正確，"
                    "僅結論尾綴（較高/趨勢）或分隔格式不同"))
            elif hit:
                rec.update(category="F6_部分正確", reason=(
                    f"複合題 {hit}/{len(num_keys)} 個數值正確"))
            else:
                miss = [k for k in num_keys if k not in a_segs
                        or _norm_num(a_segs.get(k, "")) != _norm_num(g_segs[k])]
                rec.update(category="F8_真失效", reason=(
                    f"複合題 0/{len(num_keys)} 個數值正確"
                    f"（不符欄位：{miss[:2]}）"))
            out.append(rec); continue

        # ── 單值金標毀損 ────────────────────────────────────────
        if _is_corrupt_gold_value(gold):
            rec.update(category="F2_金標毀損", reason=(
                f"金標「{gold.strip()}」為附註代號而非數值，無法作為評分基準"))
            out.append(rec); continue

        # ── 文字型答案（圖譜題：實體名稱／產業鏈分類／風險標記）──────
        # 此類金標本身即為文字而非數值，須以語意包含關係判定，不可套用數值比對。
        if not _nums(gold):
            gt = _text_tokens(gold)
            sa = _norm_text(ans)
            if gt and all(t in sa for t in gt):
                extra = _count_extra_candidates(ans, gt, gold)
                if extra == 0:
                    rec.update(category="F1_格式差異", reason=(
                        "文字答案語意與金標一致，僅分隔符/贅詞不同"
                        f"（金標「{gold[:24]}」）"))
                else:
                    rec.update(category="F6_部分正確", reason=(
                        f"正解已包含於輸出，但另夾雜 {extra} 個未經篩選的候選項"))
            else:
                miss = [t for t in gt if t not in sa]
                rec.update(category="F8_真失效", reason=(
                    f"文字答案未涵蓋金標關鍵詞 {miss[:2]}"
                    f"（金標「{gold[:24]}」）"))
            out.append(rec); continue

        grp = idx.get((co, qtr))
        av = _norm_num(ans)
        a_rows = grp[grp["_v"] == av] if (grp is not None and av) else None

        if a_rows is not None and not a_rows.empty:
            rec["system_value_locations"] = [
                {"table": r["table_name"], "item": r["item_name"],
                 "col": r["column_header"]}
                for _, r in a_rows.head(5).iterrows()
            ]

        # ── F4 欄位錯位 ────────────────────────────────────────
        if grp is not None and av and a_rows is not None and not a_rows.empty:
            gv = _norm_num(gold)
            if gv:
                key = g_item.strip()
                a_same = a_rows[
                    a_rows["table_name"].astype(str).str.contains(re.escape(g_tbl[:6]), na=False)
                    & (a_rows["item_name"].astype(str).str.strip() == key)]
                g_rows = grp[grp["_v"] == gv]
                g_same = g_rows[
                    g_rows["table_name"].astype(str).str.contains(re.escape(g_tbl[:6]), na=False)
                    & (g_rows["item_name"].astype(str).str.strip() == key)]
                if not a_same.empty and not g_same.empty:
                    a_col = str(a_same.iloc[0]["column_header"])
                    g_col = str(g_same.iloc[0]["column_header"])
                    cur = _roc_to_ad_year(qtr)
                    a_yrs, g_yrs = _col_years(a_col), _col_years(g_col)
                    # 系統落在該期別當年、金標落在更早年份 → 金標取了「去年同期
                    # 比較欄」，而問題問的是當期，系統實為正確。
                    if (cur and a_yrs and g_yrs
                            and cur in a_yrs and cur not in g_yrs
                            and max(g_yrs) < cur):
                        rec.update(category="F3_金標可疑", reason=(
                            f"金標取自去年同期比較欄「{g_col}」，而問題所問期別 {qtr} "
                            f"對應西元 {cur} 年；系統取當期欄「{a_col}」，實為正確"))
                    else:
                        rec.update(category="F4_欄位錯位", reason=(
                            f"同表同科目、欄位不同（同屬當期年度，單季 vs 累計）："
                            f"系統取「{a_col}」，金標為「{g_col}」"))
                    out.append(rec); continue

        # ── F3 金標可疑 ────────────────────────────────────────
        if _is_note_table(g_tbl) or _is_minor_item(g_item):
            main_hit = None
            if a_rows is not None and not a_rows.empty:
                m = a_rows[a_rows["table_name"].astype(str).str.startswith(_MAIN_TABLES)]
                if not m.empty:
                    main_hit = m.iloc[0]
            if main_hit is not None:
                why = ("金標取自附註表" if _is_note_table(g_tbl)
                       else "金標為損益表/權益末端子項")
                rec.update(category="F3_金標可疑", reason=(
                    f"{why}「{(g_tbl if _is_note_table(g_tbl) else g_item)[:22]}」；"
                    f"系統答案取自主要報表 {main_hit['table_name']}／"
                    f"{str(main_hit['item_name'])[:22]}"))
                out.append(rec); continue

        # ── F5 科目歧義 ────────────────────────────────────────
        if (a_rows is not None and not a_rows.empty
                and str(g_tbl).startswith(_MAIN_TABLES)):
            m = a_rows[a_rows["table_name"].astype(str).str.startswith(_MAIN_TABLES)]
            if not m.empty:
                rec.update(category="F5_科目歧義", reason=(
                    f"口語詞可對應多個主表科目：系統取 {m.iloc[0]['table_name']}／"
                    f"{str(m.iloc[0]['item_name'])[:22]}；"
                    f"金標為 {g_tbl}／{g_item[:22]}"))
                out.append(rec); continue

        # ── F6 部分正確 ────────────────────────────────────────
        if sc.get("contains_match") or sc.get("partial_numeric"):
            rec.update(category="F6_部分正確",
                       reason="複合題中部分數值與金標相符")
            out.append(rec); continue

        # ── F8 真失效 ──────────────────────────────────────────
        loc = rec.get("system_value_locations")
        rec.update(category="F8_真失效", reason=(
            f"系統取到語意無關之科目：{loc[0]['table']}／{loc[0]['item'][:22]}"
            if loc else "系統答案無法在該公司該期任何事實列中定位"))
        out.append(rec)

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    ORDER = ["F1_格式差異", "F2_金標毀損", "F3_金標可疑", "F4_欄位錯位",
             "F5_科目歧義", "F6_部分正確", "F7_拒答", "F8_真失效"]
    cnt = Counter(r["category"] for r in out)
    total = len(out)

    print("═" * 70)
    print(f"  口語化基線 100 題 失分歸因（{total} 題未 EM 命中）")
    print("═" * 70)
    for k in ORDER:
        n = cnt.get(k, 0)
        if n:
            print(f"  {k:14} {n:>3} 題 ({n/total*100:5.1f}%)  {'█'*max(1,int(n/total*38))}")
    print("─" * 70)
    gold_side = sum(cnt.get(k, 0) for k in ("F1_格式差異", "F2_金標毀損",
                                            "F3_金標可疑", "F5_科目歧義"))
    sys_side = sum(cnt.get(k, 0) for k in ("F4_欄位錯位", "F6_部分正確",
                                           "F7_拒答", "F8_真失效"))
    print(f"  金標/格式面（非系統檢索錯誤）：{gold_side:>3} 題 ({gold_side/total*100:.1f}%)")
    print(f"  系統面（確為系統失分）      ：{sys_side:>3} 題 ({sys_side/total*100:.1f}%)")

    # ── Markdown 對照表 ────────────────────────────────────
    lines = ["# 口語化基線 100 題：失分逐題歸因",
             "",
             f"資料來源：`results/test_eval_colloq_base.json`（EM 16%，{total} 題未命中）。",
             "反查依據：`__all_company_all_period_numeric_facts.csv`（211,263 筆事實）。",
             "分析腳本：`analyze_colloq_base_failures.py`。",
             "", "## 歸因摘要", "",
             "| 類別 | 題數 | 佔比 | 說明 |", "|---|---|---|---|"]
    desc = {
        "F1_格式差異": "數值/語意全對，僅字串格式或贅詞不同",
        "F2_金標毀損": "金標為附註代號而非數值，無法評分",
        "F3_金標可疑": "金標取自附註表／末端子項，系統答案取自主表主科目",
        "F4_欄位錯位": "同表同科目，欄位（本期/去年同期、單季/累計）取錯",
        "F5_科目歧義": "口語詞可合理對應多個主表科目，金標任選其一",
        "F6_部分正確": "複合題部分數值正確，或正解夾雜其他候選項",
        "F7_拒答": "系統回答找不到相關資料",
        "F8_真失效": "取到語意無關之科目或無法定位",
    }
    for k in ORDER:
        n = cnt.get(k, 0)
        if n:
            lines.append(f"| {k} | {n} | {n/total*100:.1f}% | {desc[k]} |")
    lines += ["", f"**金標/格式面合計 {gold_side} 題（{gold_side/total*100:.1f}%）**"
                  f"；**系統面合計 {sys_side} 題（{sys_side/total*100:.1f}%）**。", ""]
    for k in ORDER:
        rs = [r for r in out if r["category"] == k]
        if not rs:
            continue
        lines += [f"## {k}（{len(rs)} 題）", ""]
        for r in rs:
            lines += [f"**[{r['id']}]** {r['question']}", "",
                      f"- 系統：`{r['system_answer'][:70]}`",
                      f"- 金標：`{r['gold_answer'][:70]}`",
                      f"- 金標出處：{r['gold_table']} ／ {r['gold_item'][:40]}",
                      f"- 判定理由：{r['reason']}", ""]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n  → {OUT_JSON}\n  → {OUT_MD}")


if __name__ == "__main__":
    main()
