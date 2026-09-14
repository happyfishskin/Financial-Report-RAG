#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
產生「財報實際長什麼樣」標註圖（口試簡報用）
==============================================
簡報目前直接跳到「為什麼一般 RAG 不夠」的失效清單，但**沒有先讓委員看到
財報本身**。抽象地說「表格缺乏階層感」不如把真實那一頁放上去——所有困難
都同時出現在同一張表上，看一眼就懂。

素材取自語料中的真實申報書（台積電 112Q1 合併資產負債表），非示意圖：
  ① 同一列並排三個期別，且每期還各有金額與 % 兩欄 → 一列有六個數字
  ② 民國紀年，且「112年3月31日」是時點、綜合損益表則是期間
  ③ 單位為新台幣仟元，數字本身不帶單位
  ④ 括號表示負數（此即實驗七中前沿模型仍judgement錯誤的那一類）
  ⑤ 階層由縮排表達，扁平化後即失去「合計 vs 明細」的區別

    python3 render_report_anatomy.py
      → slides_assets/fig_report_anatomy.png
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                       # noqa: E402
from fontTools.ttLib import TTCollection              # noqa: E402
from matplotlib import font_manager                   # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle  # noqa: E402
from PIL import Image                                 # noqa: E402

BASE = Path(__file__).resolve().parent
OUT = BASE / "slides_assets" / "fig_report_anatomy.png"
OUT_SLIDE = BASE / "slides_assets" / "fig_report_anatomy_slide.png"
PDF = BASE.parent / "financial_reports" / "2330_台積電_112年_Q1.pdf"
PAGE = 4
FONT_DIR = BASE / ".fonts"
TTC = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"

INK, MUTED = "#1a2332", "#6b7688"
ACCENT, BLUE, GREEN = "#c8553d", "#3478b8", "#2d6a4f"

# 裁切比例（相對整頁）。上半＝表頭與流動資產；下半＝含括號負數的權益列。
CROP_A = (0.03, 0.108, 0.99, 0.30)
CROP_B = (0.03, 0.757, 0.99, 0.800)


def _font() -> str:
    FONT_DIR.mkdir(exist_ok=True)
    dst = FONT_DIR / "NotoSansCJKtc-Regular.ttf"
    if not dst.exists() and Path(TTC).exists():
        for f in TTCollection(TTC, lazy=True).fonts:
            n = f["name"].getDebugName(4) or ""
            if "CJK TC" in n and "Mono" not in n:
                f.save(str(dst))
                break
    if dst.exists():
        font_manager.fontManager.addfont(str(dst))
        return font_manager.FontProperties(fname=str(dst)).get_name()
    return "DejaVu Sans"


plt.rcParams["font.family"] = _font()
plt.rcParams["axes.unicode_minus"] = False


def crops() -> tuple[Image.Image, Image.Image]:
    if not PDF.exists():
        sys.exit(f"✗ 找不到原始申報書 {PDF}")
    with tempfile.TemporaryDirectory() as td:
        stem = Path(td) / "pg"
        subprocess.run(["pdftoppm", "-f", str(PAGE), "-l", str(PAGE), "-r", "200",
                        "-png", str(PDF), str(stem)], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        png = next(iter(sorted(Path(td).glob("pg*.png"))), None)
        if png is None:
            sys.exit("✗ pdftoppm 未產生影像")
        im = Image.open(png).convert("RGB")
        w, h = im.size
        box = lambda c: im.crop((int(w * c[0]), int(h * c[1]),
                                 int(w * c[2]), int(h * c[3])))
        return box(CROP_A), box(CROP_B)


def label(ax, x, y, n, txt, color):
    """圓形編號＋說明文字，統一置於圖面右側或下方留白處。"""
    ax.add_patch(plt.Circle((x, y), 0.011, color=color, zorder=6,
                            transform=ax.transAxes, clip_on=False))
    ax.text(x, y, n, transform=ax.transAxes, ha="center", va="center",
            fontsize=8, color="white", fontweight="bold", zorder=7, clip_on=False)
    ax.text(x + 0.018, y, txt, transform=ax.transAxes, ha="left", va="center",
            fontsize=9.5, color=INK, zorder=7, clip_on=False)


def box_on(ax, im, x0, y0, x1, y1, color):
    """在裁切圖上框出要指的位置（座標為該裁切圖的比例）。"""
    w, h = im.size
    ax.add_patch(Rectangle((x0 * w, y0 * h), (x1 - x0) * w, (y1 - y0) * h,
                           fill=False, edgecolor=color, lw=1.8, zorder=5))


def main() -> int:
    a, b = crops()
    if "--slide" in sys.argv:
        return render_slide(a, b)
    # 影像維持原比例，若軸框比例不符會在軸內留白。故先由裁切圖長寬比反推所需
    # 軸高，再據此定出整張圖的高度——否則兩塊節錄之間會出現一大片空白。
    FW, LEFT, CW = 13.2, 0.035, 0.93
    inner = FW * CW
    ha, hb = inner * a.size[1] / a.size[0], inner * b.size[1] / b.size[0]
    head, gap, notes_h, pad = 0.62, 0.16, 5 * 0.30 + 0.34, 0.18
    FH = head + ha + gap + hb + notes_h + pad

    fig = plt.figure(figsize=(FW, FH), dpi=200)
    fig.patch.set_facecolor("white")
    y = lambda inch: inch / FH                       # 英吋 → 圖面比例

    fig.text(LEFT, 1 - y(0.26), "真實申報書：台積電 112Q1 合併資產負債表（節錄）",
             fontsize=15, color=INK, fontweight="bold")
    fig.text(LEFT, 1 - y(0.50),
             "所有困難同時出現在同一張表上——這是系統要處理的原始輸入，不是示意圖。",
             fontsize=10.5, color=MUTED)

    top_a = 1 - y(head) - y(ha)
    axa = fig.add_axes([LEFT, top_a, CW, y(ha)])
    axa.imshow(a)
    axa.axis("off")
    box_on(axa, a, 0.435, 0.10, 0.99, 0.33, ACCENT)      # 三期表頭
    box_on(axa, a, 0.855, 0.00, 0.99, 0.09, BLUE)        # 單位
    box_on(axa, a, 0.115, 0.30, 0.30, 0.99, GREEN)       # 階層縮排

    top_b = top_a - y(gap) - y(hb)
    axb = fig.add_axes([LEFT, top_b, CW, y(hb)])
    axb.imshow(b)
    axb.axis("off")
    box_on(axb, b, 0.435, 0.42, 0.62, 0.72, ACCENT)      # 括號負數

    notes = [
        ("1", "同一列並排三個期別，每期又各有「金額」與「%」兩欄——"
              "一列其實有六個數字，問「資產總計多少」必須先決定取哪一欄", ACCENT),
        ("2", "民國紀年（112 年 3 月 31 日）；資產負債表是時點、"
              "綜合損益表是期間，兩者的「本期」意義不同", BLUE),
        ("3", "單位為新台幣仟元，寫在表外——數字本身不帶單位", BLUE),
        ("4", "階層以縮排表達：「流動資產合計」與其下明細在扁平化後長得一樣", GREEN),
        ("5", "括號代表負數：( 24,269,263 ) 是 −24,269,263，"
              "非台灣財報慣例的模型會判成正數（實驗七中前沿模型即敗於此）", ACCENT),
    ]
    y0 = top_b - y(0.34)
    for i, (n, t, c) in enumerate(notes):
        yi = y0 - y(i * 0.30)
        fig.patches.append(plt.Circle((0.048, yi), y(0.075), color=c,
                                      transform=fig.transFigure, zorder=6))
        fig.text(0.048, yi, n, ha="center", va="center", fontsize=8.5,
                 color="white", fontweight="bold", zorder=7)
        fig.text(0.068, yi, t, ha="left", va="center", fontsize=10, color=INK)

    OUT.parent.mkdir(exist_ok=True)
    fig.savefig(OUT, dpi=200, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    print(f"✓ {OUT.relative_to(BASE)}  ({OUT.stat().st_size:,} bytes)")
    return 0


def render_slide(a, b) -> int:
    """
    簡報用變體：只放兩塊裁切與標框，不含標題與說明。

    投影片高度有限，若把 5 條說明也畫進圖裡，整張圖會變高變窄，等比縮放後
    表格本身反而看不清——而委員要看的正是那張表。故說明改由投影片文字承載，
    圖只負責「把真實表格放到最大」。
    """
    FW, LEFT, CW = 13.2, 0.02, 0.96
    inner = FW * CW
    ha, hb = inner * a.size[1] / a.size[0], inner * b.size[1] / b.size[0]
    gap, pad = 0.14, 0.10
    FH = ha + gap + hb + pad * 2

    fig = plt.figure(figsize=(FW, FH), dpi=200)
    fig.patch.set_facecolor("white")
    y = lambda inch: inch / FH

    top_a = 1 - y(pad) - y(ha)
    axa = fig.add_axes([LEFT, top_a, CW, y(ha)])
    axa.imshow(a)
    axa.axis("off")
    box_on(axa, a, 0.435, 0.10, 0.99, 0.33, ACCENT)
    box_on(axa, a, 0.855, 0.00, 0.99, 0.09, BLUE)
    box_on(axa, a, 0.115, 0.30, 0.30, 0.99, GREEN)

    top_b = top_a - y(gap) - y(hb)
    axb = fig.add_axes([LEFT, top_b, CW, y(hb)])
    axb.imshow(b)
    axb.axis("off")
    box_on(axb, b, 0.435, 0.42, 0.62, 0.72, ACCENT)

    OUT_SLIDE.parent.mkdir(exist_ok=True)
    fig.savefig(OUT_SLIDE, dpi=200, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    print(f"✓ {OUT_SLIDE.relative_to(BASE)}  ({OUT_SLIDE.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
