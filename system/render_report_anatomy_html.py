#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
產生「財報實際長什麼樣」標註圖（MOPS HTML 版）
=================================================
先前版本截自 PDF，但**系統實際消費的是 MOPS 的 HTML 表格**
（`source_kind: html_table` → `*_facts.csv`），PDF 只是前期研究。
以 PDF 當「系統的原始輸入」會與管線敘述對不上，故改截 HTML。

兩者呈現也確實不同，換過來之後標註要跟著改：

    PDF：民國紀年（112年3月31日）、每期另有 % 欄
    HTML：西元日期（2024/3/31）、中英雙語科目名、無 % 欄

其中「表頭是西元、但使用者問的是民國季別（113Q1）」正是 `corpus.roc_to_ad()` /
`roc_to_west_period()` 存在的理由，比 PDF 版的「民國紀年」更貼近系統實況。

作法：以 Playwright 開啟原始 HTML，量出指定列的邊界框後截取兩塊區域——
不重新包裝 HTML，才能保證截到的就是原檔的樣子。

    python3 render_report_anatomy_html.py [--full]
      → slides_assets/fig_report_anatomy_html.png        （簡報用：只有兩塊截圖）
      → slides_assets/fig_report_anatomy_html_full.png   （--full：另附說明文字）
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
SRC = (BASE.parent / "version2" / "reports_html_copy"
       / "2330_台灣積體電路製造股份有限公司" / "2330_113Q1_財報.html")
OUT = BASE / "slides_assets" / "fig_report_anatomy_html.png"
OUT_FULL = BASE / "slides_assets" / "fig_report_anatomy_html_full.png"

# 上半截表頭與流動資產前段；下半以「含括號負數」的列為中心動態決定
# 列數直接決定圖的長寬比：投影片只給得起約 3.5 吋高，若上下兩塊合計超過
# 十餘列，等比縮放後寬度就撐不滿、字也變小。故只取「足以說明問題」的最少列。
BAND_A = (1, 7)                 # 表頭＋資產／流動資產／四列明細
BAND_B_BEFORE, BAND_B_AFTER = 1, 1      # 括號負數列前後各取幾列
SCALE = 2                       # 裝置像素比，投影時才不會糊
PAD = 6                         # 截取範圍上下留白（px）

INK, MUTED = "#1a2332", "#6b7688"
ACCENT, BLUE, GREEN = "#c8553d", "#3478b8", "#2d6a4f"


def shoot():
    """
    截兩塊區域，並**以量測到的儲存格座標**回傳標框位置（相對各截圖的比例）。

    標框若靠目測比例填，換一份報表或改一次裁切範圍就會錯位（實測第一版即框到
    相鄰列）。這裡改為向瀏覽器問實際 bounding box，再換算成比例。
    """
    from playwright.sync_api import sync_playwright

    tmp = Path("/tmp")
    a_png, b_png = tmp / "_mops_a.png", tmp / "_mops_b.png"
    with sync_playwright() as pw:
        br = pw.chromium.launch(headless=True, channel="chrome",
                                args=["--no-sandbox"])
        pg = br.new_page(viewport={"width": 1500, "height": 1200},
                         device_scale_factor=SCALE)
        pg.goto(SRC.resolve().as_uri(), wait_until="load")

        # 以內容定位表格，不靠索引——原檔有 35 張表，順序不保證穩定
        tbl = pg.locator("table").filter(
            has_text="流動資產").filter(has_text="資產總計").first
        rows = tbl.locator("tr")
        n = rows.count()

        # 原檔以 overflow 容器捲動，document.scrollHeight 恆等於視窗高度，
        # 故 full_page 也只截得到一屏。先量表高，再把視窗撐到容得下整張表。
        bx = tbl.bounding_box()
        pg.set_viewport_size({"width": 1500,
                              "height": int(bx["y"] + bx["height"] + 200)})
        pg.wait_for_timeout(200)
        bx = tbl.bounding_box()

        # 找含括號負數的列。有多列時取「括號內數字位數最多」者——首個命中是
        # 「待註銷股本 (14,018)」這種零星小數，不如金額大的列有代表性。
        PAREN = re.compile(r"\(\s*([\d,]+)\s*\)")
        hits = [(max((len(m.replace(",", "")) for m in PAREN.findall(t)), default=0),
                 i, PAREN.findall(t))
                for i, t in ((i, rows.nth(i).inner_text()) for i in range(n))
                if PAREN.search(t)]
        if not hits:
            raise SystemExit("✗ 此表未出現括號負數，無法標註")
        _, neg, neg_vals = max(hits)
        neg_text = max(neg_vals, key=len)
        lo_b = max(0, neg - BAND_B_BEFORE)
        hi_b = min(n - 1, neg + BAND_B_AFTER)
        print(f"  命中表格 {n} 列；括號負數列＝第 {neg} 列（{neg_text}）")

        def shot(lo, hi, out):
            top, bot = rows.nth(lo).bounding_box(), rows.nth(hi).bounding_box()
            box = {"x": bx["x"], "y": top["y"] - PAD, "width": bx["width"],
                   "height": bot["y"] + bot["height"] - top["y"] + PAD * 2}
            pg.screenshot(path=str(out), clip=box)
            print(f"    列 {lo}–{hi} → {out.name}  "
                  f"{int(box['width'])}×{int(box['height'])} css px")
            return box

        def rel(box, el):
            """把元素的頁面座標換算成「相對截圖」的比例。"""
            e = el.bounding_box()
            return ((e["x"] - box["x"]) / box["width"],
                    (e["y"] - box["y"]) / box["height"],
                    (e["x"] + e["width"] - box["x"]) / box["width"],
                    (e["y"] + e["height"] - box["y"]) / box["height"])

        box_a = shot(*BAND_A, a_png)
        hdr = rows.nth(BAND_A[0]).locator("td, th")
        x0, y0, _, y1 = rel(box_a, hdr.nth(2))
        _, _, x1, _ = rel(box_a, hdr.nth(hdr.count() - 1))
        boxes_a = [(x0, y0, x1, y1, ACCENT)]                 # 三個期別表頭
        it0 = rel(box_a, rows.nth(BAND_A[0] + 1).locator("td").nth(1))
        it1 = rel(box_a, rows.nth(BAND_A[1]).locator("td").nth(1))
        boxes_a.append((it0[0], it0[1], it0[2], it1[3], GREEN))   # 科目名／縮排

        box_b = shot(lo_b, hi_b, b_png)
        cells = rows.nth(neg).locator("td")
        c0 = rel(box_b, cells.nth(cells.count() - 2))
        c1 = rel(box_b, cells.nth(cells.count() - 1))
        boxes_b = [(c0[0], c0[1], c1[2], c0[3], ACCENT)]     # 括號負數兩格

        br.close()
    return a_png, b_png, boxes_a, boxes_b, neg_text


def notes(neg_text: str):
    return [
        ("1", "同一列並排三個期別（2024/3/31、2023/12/31、2023/3/31）——"
              "問「資產總計多少」必須先決定取哪一欄", ACCENT),
        ("2", "表頭是西元日期，使用者問的卻是民國季別「113Q1」；"
              "且哪一欄算「本期」隨報表期別而變", BLUE),
        ("3", "階層只用全形空白縮排表達（　流動資產 →　　現金及約當現金），"
              "HTML 本身沒有階層標記——扁平化後「合計」與「明細」長得一樣", GREEN),
        ("4", "英文科目名以 display:none 藏在同一格：畫面看不到，但解析器讀得到"
              "「現金及約當現金　　Cash and cash equivalents」", BLUE),
        ("5", f"括號代表負數：( {neg_text} ) 是 −{neg_text}，"
              "非台灣財報慣例的模型會判成正數（實驗七中前沿模型即敗於此）", ACCENT),
    ]


def compose(a_png, b_png, boxes_a, boxes_b, neg_text, full: bool) -> Path:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from fontTools.ttLib import TTCollection
    from matplotlib import font_manager
    from matplotlib.patches import Rectangle
    from PIL import Image

    fd = BASE / ".fonts"
    fd.mkdir(exist_ok=True)
    dst = fd / "NotoSansCJKtc-Regular.ttf"
    ttc = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
    if not dst.exists() and Path(ttc).exists():
        for f in TTCollection(ttc, lazy=True).fonts:
            nm = f["name"].getDebugName(4) or ""
            if "CJK TC" in nm and "Mono" not in nm:
                f.save(str(dst))
                break
    if dst.exists():
        font_manager.fontManager.addfont(str(dst))
        plt.rcParams["font.family"] = font_manager.FontProperties(
            fname=str(dst)).get_name()
    plt.rcParams["axes.unicode_minus"] = False

    a, b = Image.open(a_png), Image.open(b_png)
    FW, LEFT, CW = 13.2, (0.035 if full else 0.02), (0.93 if full else 0.96)
    inner = FW * CW
    ha, hb = inner * a.size[1] / a.size[0], inner * b.size[1] / b.size[0]
    head = 0.62 if full else 0.10
    NOTES = notes(neg_text)
    notes_h = (len(NOTES) * 0.30 + 0.34) if full else 0.10
    gap, pad = 0.16, 0.10
    FH = head + ha + gap + hb + notes_h + pad

    fig = plt.figure(figsize=(FW, FH), dpi=200)
    fig.patch.set_facecolor("white")
    y = lambda inch: inch / FH

    if full:
        fig.text(LEFT, 1 - y(0.26),
                 "真實 MOPS 申報 HTML：台積電 113Q1 合併資產負債表（節錄）",
                 fontsize=15, color=INK, fontweight="bold")
        fig.text(LEFT, 1 - y(0.50),
                 "這是系統實際消費的原始輸入（HTML 表格 → CSV），不是示意圖。",
                 fontsize=10.5, color=MUTED)

    def put(im, top, boxes):
        ax = fig.add_axes([LEFT, top, CW, y(inner * im.size[1] / im.size[0])])
        ax.imshow(im)
        ax.axis("off")
        w, h = im.size
        for x0, y0, x1, y1, c in boxes:
            ax.add_patch(Rectangle((x0 * w, y0 * h), (x1 - x0) * w, (y1 - y0) * h,
                                   fill=False, edgecolor=c, lw=1.8, zorder=5))
        return ax

    top_a = 1 - y(head) - y(ha)
    put(a, top_a, boxes_a)
    top_b = top_a - y(gap) - y(hb)
    put(b, top_b, boxes_b)

    if full:
        y0 = top_b - y(0.34)
        for i, (n, t, c) in enumerate(NOTES):
            yi = y0 - y(i * 0.30)
            fig.patches.append(plt.Circle((0.048, yi), y(0.075), color=c,
                                          transform=fig.transFigure, zorder=6))
            fig.text(0.048, yi, n, ha="center", va="center", fontsize=8.5,
                     color="white", fontweight="bold", zorder=7)
            fig.text(0.068, yi, t, ha="left", va="center", fontsize=10, color=INK)

    out = OUT_FULL if full else OUT
    out.parent.mkdir(exist_ok=True)
    fig.savefig(out, dpi=200, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    print(f"✓ {out.relative_to(BASE)}  ({out.stat().st_size:,} bytes)")
    return out


def main() -> int:
    if not SRC.exists():
        print(f"✗ 找不到原始 MOPS HTML：{SRC}")
        return 2
    a, b, ba, bb, neg = shoot()
    compose(a, b, ba, bb, neg, full="--full" in sys.argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
