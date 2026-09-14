#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
跨產業金標之獨立驗證：以原始 HTML 的行內 XBRL 標記為準
======================================================
金標取自二維寬表 CSV 的儲存格，與受測系統唯一共用的上游是 HTML→CSV 解析器。
若該解析器把欄位對錯（正是論文檢出的 D2／D4／D7 那類缺陷），金標與系統會一起錯，
EM 就會被墊高——這正是論文貢獻二所描述的污染型態。

MOPS 財報的 HTML 帶有行內 XBRL 標記：

    <ix:nonFraction contextRef="AsOf20250630" ...>870,519,926</ix:nonFraction>

contextRef 由發布端標註，直接說明該數字屬於哪個期間，與本專案的解析邏輯完全無關。
本腳本因此以 contextRef 作為獨立事實來源，逐題核對金標：

    資產負債表／期末餘額   → AsOf20250630
    綜合損益表／單季       → From20250401To20250630
    綜合損益表／累計       → From20250101To20250630
    現金流量表／累計       → From20250101To20250630

判定：
    verified   該科目在該 context 下的值唯一，且與金標相同
    ambiguous  同名科目在該 context 下有多個相異值（跨表重複，本腳本不做表別範圍縮限）
    mismatch   值不同 → 金標或解析器有問題，必須逐題檢查
    not_found  HTML 中找不到該科目或該 context

    python3 verify_cross_industry_gold.py [--gold <檔>]
"""
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_HTML_ROOT = ROOT / "_cross_industry_probe" / "reports_html_copy"
GOLD = ROOT / "questions" / "cross_industry_gold_114Q2.json"
OUT = ROOT / "results" / "cross_industry_gold_verification.json"

# 每個（報表 × 當期欄）可接受的 contextRef；順序即優先序。
# 現金流量表的期初／期末現金餘額是**時點**（instant）事實，發布端以 AsOf 標記，
# 但它們印在期間欄裡——只認 From… 會把這幾列誤判為找不到，故一併接受 AsOf。
CTX = {
    ("資產負債表", "期末餘額"): ("AsOf20250630",),
    ("綜合損益表", "單季"): ("From20250401To20250630",),
    ("綜合損益表", "累計"): ("From20250101To20250630",),
    ("現金流量表", "累計"): ("From20250101To20250630", "AsOf20250630"),
}

_ROW = re.compile(r"<tr\b.*?</tr>", re.S | re.I)
_SPAN = re.compile(r'<span class="(?:zh|en)">(.*?)</span>', re.S)
_NF = re.compile(r'<ix:nonFraction[^>]*contextRef="([^"]+)"[^>]*>(.*?)</ix:nonFraction>',
                 re.S)
_TAG = re.compile(r"<[^>]+>")


def squash(s: str) -> str:
    """比對用：去掉所有空白（含全形空格）與標籤。"""
    return re.sub(r"\s+", "", _TAG.sub("", s)).replace("　", "")


def num(s: str) -> str | None:
    """抽出數值並化為**比較用**的正規形式。

    本函式只服務「金標與 XBRL 是不是同一個數」這個判斷，故以數值等價為準：
    報表寫 17.50、金標寫 17.5 是同一個數，不該判為 mismatch。
    金標本身仍保留報表原寫法（見 generate_cross_industry_gold.canonical）。
    """
    t = _TAG.sub("", s).strip().replace(",", "")
    if not re.fullmatch(r"-?\d+(?:\.\d+)?", t):
        return None
    f = float(t)
    return str(int(f)) if f == int(f) else str(f)


def index_html(path: Path) -> dict[tuple[str, str], set[str]]:
    """(科目正規化文字, contextRef) → 該處出現過的相異數值集合。"""
    html = path.read_text(encoding="utf-8", errors="replace")
    idx: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in _ROW.findall(html):
        facts = _NF.findall(row)
        if not facts:
            continue
        # 科目文字＝該列所有 zh/en span 串接（金額格內無 span，不會混入）
        label = squash("".join(_SPAN.findall(row)))
        if not label:
            continue
        for ctx, raw in facts:
            v = num(raw)
            if v is not None:
                idx[(label, ctx)].add(v)
    return idx


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gold", type=Path, default=GOLD)
    ap.add_argument("--html-root", type=Path, default=DEFAULT_HTML_ROOT)
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args()

    gold = json.loads(a.gold.read_text(encoding="utf-8"))
    caches: dict[str, dict] = {}
    rows, tally = [], defaultdict(int)

    for q in gold:
        m = q["metadata"]
        code = m["company_code"]
        if code not in caches:
            hit = next((p for p in a.html_root.rglob("*.html")
                        if p.parent.name.startswith(code)), None)
            if hit is None:
                raise SystemExit(f"✗ 找不到 {code} 的 HTML")
            caches[code] = index_html(hit)
        idx = caches[code]

        cands = CTX[(m["table_name"], m["column_kind"])]
        ctx, vals = cands[0], set()
        for c in cands:                       # 取第一個有資料的 context
            vals = idx.get((squash(m["item_name"]), c), set())
            if vals:
                ctx = c
                break
        gold_v = num(q["expected_answer"]) or q["expected_answer"]

        if not vals:
            verdict = "not_found"
        elif len(vals) > 1:
            verdict = "verified" if gold_v in vals else "mismatch"
            if verdict == "verified":
                verdict = "ambiguous"          # 值不唯一，證據力較弱
        elif gold_v in vals:
            verdict = "verified"
        else:
            verdict = "mismatch"

        tally[verdict] += 1
        rows.append({"id": q["id"], "verdict": verdict, "context_ref": ctx,
                     "gold": q["expected_answer"], "gold_norm": gold_v, "xbrl_values": sorted(vals)[:4],
                     "item": m["item_name"][:52], "table": m["table_name"]})

    total = len(gold)
    ok = tally["verified"] + tally["ambiguous"]
    print(f"金標 {total} 題，以 HTML 行內 XBRL 之 contextRef 獨立核對：")
    for k in ("verified", "ambiguous", "mismatch", "not_found"):
        print(f"  {k:<10} {tally[k]:>3}  （{tally[k]/total:.1%}）")
    print(f"  一致合計   {ok:>3}  （{ok/total:.1%}）")

    bad = [r for r in rows if r["verdict"] in ("mismatch", "not_found")]
    if bad:
        print("\n需人工檢查：")
        for r in bad[:12]:
            print(f"  [{r['verdict']}] {r['id']} {r['table']} {r['item']}")
            print(f"      金標 {r['gold']}｜XBRL {r['xbrl_values']}")

    a.out.parent.mkdir(exist_ok=True)
    a.out.write_text(json.dumps(
        {"title": "跨產業金標之 XBRL 獨立驗證",
         "why": ("金標取自寬表 CSV，與受測系統共用 HTML→CSV 解析器；"
                 "以發布端標註的 contextRef 核對，可獨立檢出欄位對錯型缺陷。"),
         "context_map": {f"{k[0]}／{k[1]}": list(v) for k, v in CTX.items()},
         "n": total, "tally": dict(tally), "rows": rows},
        ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n→ {a.out}")
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
