#!/usr/bin/env python3
"""由 reports_html_copy 的原始 iXBRL 財報，產生四個錯答案例的佐證截圖。

保留 MOPS 原始表格樣式，僅：隱藏英文欄位(.en)、裁到相關列、標記系統答案(紅)
與金標答案(綠)。截圖用 headless Chrome 渲染。
"""

from __future__ import annotations

import copy
import subprocess
import sys
from pathlib import Path

from lxml import etree, html as LH

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "reports_html_copy"
OUT = ROOT / "財報佐證截圖"
OUT.mkdir(exist_ok=True)

ELL = "ELLIPSIS"

CASES = [
    dict(
        name="案例1_錯欄_台灣光罩2338_114Q2",
        title="案例一・錯欄　台灣光罩（2338）114Q2　綜合損益表",
        note="同一列「營業收入合計」有 4 個金額欄：系統取本期欄 1,589,933，"
             "金標指定的是去年同期欄 1,997,876。",
        file="2338_台灣光罩股份有限公司/2338_114Q2_財報.html",
        table=1,
        rows=[0, 1, 2, 3, 4, 5, 6],
        marks={3: {2: "sys", 3: "gold"}},
    ),
    dict(
        name="案例2_聯華電子2303_113Q2",
        title="案例二　聯華電子（2303）113Q2　綜合損益表",
        note="代號 8310「不重分類至損益之項目總額」：系統取 193,901（本期季欄），"
             "金標為 2,688,302（本期累計欄）。",
        file="2303_聯華電子股份有限公司/2303_113Q2_財報.html",
        table=1,
        rows=[0, 1, ELL, 35, 36, 37, 38, 39, 40, 41],
        marks={40: {2: "sys", 4: "gold"}},
    ),
    dict(
        name="案例3_錯對象_穩懋3105_114Q2",
        title="案例三・錯對象／案例四・錯格式　穩懋半導體（3105）114Q2　"
              "母子公司間業務關係及重要交易往來情形",
        note="「其他應付款-關係人」共 3 筆。「江蘇全穩農牧科技」既是第 6 列的"
             "交易人（1,329,341），也是第 8 列的交易往來對象（110,510）—— "
             "須交易人×交易對象×科目三元主鍵齊備才鎖得住唯一一筆。",
        file="3105_穩懋半導體股份有限公司/3105_114Q2_財報.html",
        table=24,
        rows=list(range(12)),
        marks={6: {1: "key", 2: "key", 4: "key", 5: "sys"},
               8: {1: "key", 2: "key", 4: "key", 5: "gold"}},
    ),
]

EXTRA_CSS = """
.en{display:none!important}
.content{background:#fff!important;width:auto!important;height:auto!important;
         float:none!important;overflow:visible!important;display:block!important}
.container{background:#fff!important;width:auto!important}
.nav,.header{display:none!important}
body{background:#fff;margin:0;padding:22px 26px;font-family:"Noto Sans CJK TC",Arial,sans-serif}
.cap{font-size:21px;font-weight:700;color:#0f2f52;margin:0 0 6px}
.note{font-size:15px;color:#444;margin:0 0 16px;line-height:1.6;max-width:1180px}
.src{font-size:12.5px;color:#888;margin-top:14px;font-family:monospace}
.content table{margin:0!important;border-collapse:collapse}
.content table td,.content table th{font-size:14.5px;white-space:nowrap}
td.sys{background:#fdecec!important;color:#c0161d!important;font-weight:700;
       box-shadow:inset 0 0 0 2.5px #c0161d}
td.gold{background:#e7f5ec!important;color:#12723c!important;font-weight:700;
        box-shadow:inset 0 0 0 2.5px #12723c}
td.key{background:#fff6e0!important;box-shadow:inset 0 0 0 1.5px #d8a12a}
tr.ell td{text-align:center!important;color:#999;letter-spacing:5px;background:#fafafa!important}
.lg{display:inline-block;font-size:13px;margin:0 16px 12px 0;padding:3px 10px;border-radius:3px}
.lg.s{background:#fdecec;color:#c0161d;border:2px solid #c0161d}
.lg.g{background:#e7f5ec;color:#12723c;border:2px solid #12723c}
.lg.k{background:#fff6e0;color:#8a6100;border:1.5px solid #d8a12a}
"""


def cells_of(tr):
    return tr.xpath('.//*[local-name()="td" or local-name()="th"]')


def flatten(table):
    """移除 ix:* 包裝標籤，讓 <td> 成為 <tr> 直接子節點（避免瀏覽器 foster parenting）。"""
    tags = {e.tag for e in table.iter() if isinstance(e.tag, str) and ":" in e.tag}
    if tags:
        etree.strip_tags(table, *tags)


def build(case) -> Path:
    path = SRC / case["file"]
    doc = LH.parse(str(path)).getroot()
    style = doc.xpath('//*[local-name()="style"]')
    style_css = "".join(style[0].itertext()) if style else ""

    table = copy.deepcopy(doc.xpath('//*[local-name()="table"]')[case["table"]])
    flatten(table)

    all_rows = table.xpath('.//*[local-name()="tr"]')
    ncol = max(len(cells_of(r)) for r in all_rows)

    keep = []
    for spec in case["rows"]:
        if spec is ELL:
            keep.append(ELL)
        else:
            keep.append(all_rows[spec])

    # 標記系統／金標／主鍵欄位
    for ri, colmap in case["marks"].items():
        cells = cells_of(all_rows[ri])
        for ci, kind in colmap.items():
            cells[ci].set("class", (cells[ci].get("class", "") + " " + kind).strip())

    parent = all_rows[0].getparent()
    for r in all_rows:
        r.getparent().remove(r)
    for spec in keep:
        if spec is ELL:
            tr = etree.SubElement(parent, "tr")
            tr.set("class", "ell")
            td = etree.SubElement(tr, "td")
            td.set("colspan", str(ncol))
            td.text = "⋮　　（中略）　　⋮"
        else:
            parent.append(spec)

    legend = ('<span class="lg s">系統答案</span>'
              '<span class="lg g">金標答案</span>')
    if any("key" in m.values() for m in case["marks"].values()):
        legend += '<span class="lg k">定位所需主鍵欄位</span>'

    html = (f"<!doctype html><html><head><meta charset='utf-8'>"
            f"<style>{style_css}</style><style>{EXTRA_CSS}</style></head><body>"
            f"<div class='cap'>{case['title']}</div>"
            f"<div class='note'>{case['note']}</div>{legend}"
            f"<div class='content'>"
            f"{etree.tostring(table, encoding='unicode', method='html')}</div>"
            f"<div class='src'>來源：reports_html_copy/{case['file']}</div>"
            f"</body></html>")

    tmp = OUT / (case["name"] + ".html")
    tmp.write_text(html, encoding="utf-8")
    return tmp


def shoot(html_path: Path, png_path: Path, width=1750, height=1100) -> None:
    subprocess.run(
        ["google-chrome", "--headless=new", "--disable-gpu", "--hide-scrollbars",
         f"--window-size={width},{height}", "--default-background-color=FFFFFF",
         f"--screenshot={png_path}", f"file://{html_path}"],
        check=True, capture_output=True, timeout=180,
    )
    try:
        from PIL import Image, ImageChops
        im = Image.open(png_path).convert("RGB")
        bg = Image.new("RGB", im.size, (255, 255, 255))
        bbox = ImageChops.difference(im, bg).getbbox()
        if bbox:
            l, t, r, b = bbox
            im.crop((max(0, l - 16), max(0, t - 16),
                     min(im.width, r + 16), min(im.height, b + 16))).save(png_path)
    except Exception as exc:                      # 裁切失敗不影響原圖
        print("  (autocrop skipped:", exc, ")")


def main() -> None:
    for case in CASES:
        html_path = build(case)
        png = OUT / (case["name"] + ".png")
        shoot(html_path, png)
        from PIL import Image
        print(f"  {png.name}  {Image.open(png).size}")
    print("輸出目錄:", OUT)


if __name__ == "__main__":
    main()
