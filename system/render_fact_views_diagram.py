#!/usr/bin/env python3
"""繪製「數值事實索引之三視圖切分」圖。"""
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


ROOT = Path(__file__).resolve().parent
OUT_PNG = ROOT / "slides_assets" / "fig_fact_three_views.png"
OUT_SVG = ROOT / "slides_assets" / "fig_fact_three_views.svg"

INK = "#172033"
MUTED = "#58677F"
SOURCE = "#354A6B"
FULL = "#3274A1"
DEDUP = "#D97732"
ENTITY = "#2E7D5B"
DIRECT = "#C64B3A"
BG = "#F5F7FA"
LINE = "#B9C2CF"


def box(ax, x, y, w, h, *, edge, title, body, fill="#FFFFFF",
        title_size=17, body_size=12.5):
    patch = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.035,rounding_size=0.10",
        linewidth=1.8, edgecolor=edge, facecolor=fill,
    )
    ax.add_patch(patch)
    ax.add_patch(FancyBboxPatch(
        (x, y + h - 0.12), w, 0.12,
        boxstyle="round,pad=0.0,rounding_size=0.06",
        linewidth=0, facecolor=edge,
    ))
    ax.text(x + 0.24, y + h - 0.38, title, ha="left", va="top",
            fontsize=title_size, fontweight="bold", color=edge)
    ax.text(x + 0.24, y + h - 0.94, body, ha="left", va="top",
            fontsize=body_size, color=INK, linespacing=1.55)
    return patch


def arrow(ax, start, end, *, color=LINE, width=1.8, mutation=14):
    ax.add_patch(FancyArrowPatch(
        start, end, arrowstyle="-|>", mutation_scale=mutation,
        linewidth=width, color=color, connectionstyle="arc3,rad=0",
    ))


def main():
    # 明確註冊系統中文字型，避免不同 Python 環境的字型快取尚未收錄 CJK 字型。
    font_manager.fontManager.addfont("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")
    font_manager.fontManager.addfont("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc")
    plt.rcParams.update({
        # TTC 檔在 Matplotlib 中以集合內第一個家族名稱（JP）註冊，字形仍完整支援繁中。
        "font.family": "Noto Sans CJK JP",
        "axes.unicode_minus": False,
    })
    fig, ax = plt.subplots(figsize=(16, 9), dpi=160)
    fig.patch.set_facecolor("white")
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 9)
    ax.axis("off")

    ax.text(0.55, 8.62, "數值事實索引的三視圖切分與通道用途",
            fontsize=27, fontweight="bold", color=INK, va="center")
    ax.plot([0.55, 3.35], [8.29, 8.29], color=DIRECT, linewidth=4)

    source = FancyBboxPatch(
        (4.05, 7.17), 7.9, 0.78,
        boxstyle="round,pad=0.04,rounding_size=0.12",
        linewidth=0, facecolor=SOURCE,
    )
    ax.add_patch(source)
    ax.text(8.0, 7.56, "211,263 筆 Fact 全量數值事實索引",
            ha="center", va="center", fontsize=18, color="white", fontweight="bold")
    ax.text(8.0, 6.86, "系統啟動時一次載入記憶體，再依用途建立不同篩選視角",
            ha="center", va="center", fontsize=13, color=MUTED)

    arrow(ax, (8.0, 7.17), (8.0, 6.47), color=SOURCE, width=2.2)
    ax.plot([2.8, 13.2], [6.28, 6.28], color=LINE, linewidth=1.8)
    for cx in (2.8, 8.0, 13.2):
        arrow(ax, (cx, 6.28), (cx, 5.92), width=1.8)

    box(
        ax, 0.4, 3.18, 4.8, 2.75, edge=FULL,
        title="① 全量視圖",
        body=("保留全部原始欄位與不同年份數值\n"
              "以完整欄標頭進行四鍵定位\n"
              "公司 × 期別 × 科目 × 欄標頭"),
    )
    box(
        ax, 5.6, 3.18, 4.8, 2.75, edge=DEDUP,
        title="② 當期去重視圖",
        body=("先排除實體名錄類資料表\n"
              "依股票代號、公司、科目與期別分組\n"
              "優先：日期區間 → 日期點 → 較新年份"),
    )
    box(
        ax, 10.8, 3.18, 4.8, 2.75, edge=ENTITY,
        title="③ 實體視圖",
        body=("依資料表名稱與實體關鍵詞篩選\n"
              "被投資公司、子公司、關係企業\n"
              "母子公司關係與大陸投資等明細"),
    )

    # 全量與去重視圖共同流向精確查表軌。
    arrow(ax, (2.8, 3.18), (4.3, 2.12), color=FULL, width=2.0)
    arrow(ax, (8.0, 3.18), (6.8, 2.12), color=DEDUP, width=2.0)
    direct = FancyBboxPatch(
        (2.15, 1.10), 6.8, 0.98,
        boxstyle="round,pad=0.04,rounding_size=0.12",
        linewidth=1.8, edgecolor=DIRECT, facecolor="#FFF5F2",
    )
    ax.add_patch(direct)
    ax.text(5.55, 1.72, "精確查表軌　direct_lookup", ha="center", va="center",
            fontsize=17, color=DIRECT, fontweight="bold")
    ax.text(5.55, 1.36, "完整欄位定位｜跨公司、跨季度及一般期間查詢",
            ha="center", va="center", fontsize=11.5, color=INK)

    arrow(ax, (13.2, 3.18), (13.2, 2.12), color=ENTITY, width=2.0)
    graph = FancyBboxPatch(
        (10.35, 1.10), 5.25, 0.98,
        boxstyle="round,pad=0.04,rounding_size=0.12",
        linewidth=1.8, edgecolor=ENTITY, facecolor="#F1FAF6",
    )
    ax.add_patch(graph)
    ax.text(12.98, 1.72, "圖譜軌　graph_rag L2b", ha="center", va="center",
            fontsize=17, color=ENTITY, fontweight="bold")
    ax.text(12.98, 1.36, "實體明細表直接查詢",
            ha="center", va="center", fontsize=11.5, color=INK)

    ax.text(8.0, 0.48,
            "三個視圖不是三份重複資料，而是同一份 Fact 索引的不同篩選與去重結果。",
            ha="center", va="center", fontsize=13.5, color=MUTED, fontweight="bold")

    fig.savefig(OUT_PNG, bbox_inches="tight", pad_inches=0.18, facecolor="white")
    fig.savefig(OUT_SVG, bbox_inches="tight", pad_inches=0.18, facecolor="white")
    print(OUT_PNG)
    print(OUT_SVG)


if __name__ == "__main__":
    main()
