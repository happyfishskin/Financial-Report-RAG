#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把「口語比率題」的真實終端輸出渲染成投影片用的畫面圖
======================================================
用於口試簡報備審頁「口語算數題實機執行」。

**圖上每一行文字都取自實際執行的輸出**（`rag_api.py` 與 `trace_ratio_demo.py`
的 stdout），本腳本只負責上色與排版，不代為產生任何數值。

    python3 render_ratio_screenshot.py            # → slides_assets/qa_ratio_terminal.png
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                    # noqa: E402
from fontTools.ttLib import TTCollection           # noqa: E402
from matplotlib import font_manager                # noqa: E402

BASE = Path(__file__).resolve().parent
OUT = BASE / "slides_assets" / "qa_ratio_terminal.png"
FONT_DIR = BASE / ".fonts"
TTC = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
MONO_FAMILY = "Noto Sans Mono CJK TC"

# 終端配色（深色，與簡報既有實機畫面一致）
BG = "#12161c"
FG = "#d6dae0"
DIM = "#7f8994"
PROMPT = "#5fb3f0"
OK = "#5fd6a0"
WARN = "#e8c46a"
KEY = "#f0a6c8"


def _ensure_mono_font() -> str:
    """從 Noto CJK 的 ttc 抽出 Mono TC 子字型並註冊給 matplotlib。"""
    FONT_DIR.mkdir(exist_ok=True)
    dst = FONT_DIR / "NotoSansMonoCJKtc-Regular.ttf"
    if not dst.exists():
        for f in TTCollection(TTC, lazy=True).fonts:
            name = f["name"].getDebugName(4) or ""
            if "Mono CJK TC" in name:
                f.save(str(dst))
                break
    if dst.exists():
        font_manager.fontManager.addfont(str(dst))
        return font_manager.FontProperties(fname=str(dst)).get_name()
    return "DejaVu Sans Mono"


FAMILY = _ensure_mono_font()

# ── 畫面內容：(文字, 顏色) ──────────────────────────────────
# 全部逐字取自實際 stdout；註解標示來源指令。
LINES: list[tuple[str, str]] = [
    ('$ python3 rag_api.py "台積電114Q2毛利率多少？"', PROMPT),
    ("[RAGSystem] 就緒（3.6s）：211,263 facts ｜ 32,039 圖譜節點 ｜ 30,887 向量 chunks", DIM),
    ("", FG),
    ("Q: 台積電114Q2毛利率多少？", FG),
    ("A: 58.62%", OK),
    ("   路由=direct_lookup ｜ 耗時=3.389s", DIM),
    ("", FG),
    ("$ python3 trace_ratio_demo.py          # 展開內部步驟", PROMPT),
    ("", FG),
    ("① 口語解析", KEY),
    ("    公司  台積電  →  台灣積體電路製造        [Fix 12 市場簡稱正規化]", FG),
    ("    科目  毛利率  →  比率本體論「毛利率」    [Fix 14]", FG),
    ("          numerator   = 營業毛利（毛損）", DIM),
    ("          denominator = 營業收入合計", DIM),
    ("", FG),
    ("② 拆成兩次查表（各自通過唯一值閘門）", KEY),
    ("    分子  營業毛利（毛損）  114Q2 = 547,369,238", FG),
    ("    分母  營業收入合計      114Q2 = 933,791,869", FG),
    ("", FG),
    ("③ Python 確定性算術（非 LLM）", KEY),
    ("    547369238 ／ 933791869 × 100", FG),
    ("    →  58.62%", OK),
    ("", FG),
    ("LLM 呼叫實際計數（攔截 _call_vllm）", KEY),
    ("    查表與算術   0 次", OK),
    ("    意圖路由     1 次   3.273s   ← 佔端到端 96%", WARN),
]


def main() -> int:
    OUT.parent.mkdir(exist_ok=True)
    # 版面比例對齊投影片左欄的圖框（7.20 x 4.91 in）
    fig = plt.figure(figsize=(7.20, 4.91), dpi=260)
    fig.patch.set_facecolor(BG)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor(BG)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    # 視窗標題列
    ax.add_patch(plt.Rectangle((0, 0.945), 1, 0.055, color="#1c2229", zorder=1))
    for i, c in enumerate(("#ff5f57", "#febc2e", "#28c840")):
        ax.add_patch(plt.Circle((0.022 + i * 0.024, 0.9725), 0.0075,
                                color=c, zorder=2))
    ax.text(0.5, 0.9725, "financial_crawler — rag_api.py", color=DIM,
            fontsize=6.2, family=FAMILY, ha="center", va="center", zorder=2)

    y = 0.905
    for text, color in LINES:
        if text:
            ax.text(0.022, y, text, color=color, fontsize=6.35,
                    family=FAMILY, ha="left", va="top", zorder=2)
        y -= 0.0345

    fig.savefig(OUT, facecolor=BG, dpi=260)
    plt.close(fig)
    print(f"✓ {OUT}  ({OUT.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
