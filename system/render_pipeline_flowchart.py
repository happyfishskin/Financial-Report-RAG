#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
查詢管線流程圖（三軌調度與降級鏈）
====================================
畫出一道問句從進入系統到產出答案所經過的每一個判斷點。

**為何值得單獨畫一張**：系統的行為特徵不在任何單一軌道裡，而在
「先試哪一軌、什麼條件下降級、降級到哪」這條鏈上。既有的
`fig_system_overview` 畫的是元件關係，本圖畫的是**控制流**。

配色與 `render_thesis_figures.py` 一致（直查藍／向量紫／圖譜綠）。

    python3 render_pipeline_flowchart.py
      → slides_assets/fig_pipeline_flow.png
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                     # noqa: E402
from fontTools.ttLib import TTCollection            # noqa: E402
from matplotlib import font_manager                 # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch   # noqa: E402

BASE = Path(__file__).resolve().parent
OUT = BASE / "slides_assets" / "fig_pipeline_flow.png"
FONT_DIR = BASE / ".fonts"
TTC = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"

# 與既有圖表一致的配色
INK, MUTED, FILL = "#1a2332", "#6b7688", "#f4f6f9"
FACT_C, FACT_F = "#3478b8", "#edf5fc"      # 直查軌
VEC_C, VEC_F = "#7357a5", "#f4f0fa"        # 向量軌
GRAPH_C, GRAPH_F = "#2d6a4f", "#eef7f1"    # 圖譜軌
GATE_C, GATE_F = "#c8553d", "#fff6e8"      # 判斷點
DIM_C, DIM_F = "#b0b9c6", "#f7f8fa"


def _font() -> str:
    FONT_DIR.mkdir(exist_ok=True)
    dst = FONT_DIR / "NotoSansCJKtc-Regular.ttf"
    if not dst.exists():
        for f in TTCollection(TTC, lazy=True).fonts:
            if "CJK TC" in (f["name"].getDebugName(4) or "") and "Mono" not in (
                    f["name"].getDebugName(4) or ""):
                f.save(str(dst))
                break
    if dst.exists():
        font_manager.fontManager.addfont(str(dst))
        return font_manager.FontProperties(fname=str(dst)).get_name()
    return "DejaVu Sans"


FAMILY = _font()
plt.rcParams["font.family"] = FAMILY
plt.rcParams["axes.unicode_minus"] = False


def box(ax, x, y, w, h, title, body="", ec=INK, fc="#ffffff", tc=None,
        ts=9.0, bs=7.4, round_r=0.012):
    tc = tc or ec
    ax.add_patch(FancyBboxPatch((x, y), w, h,
                                boxstyle=f"round,pad=0.004,rounding_size={round_r}",
                                fc=fc, ec=ec, lw=1.15, zorder=3))
    if body:
        ax.text(x + w / 2, y + h * 0.66, title, ha="center", va="center",
                fontsize=ts, color=tc, fontweight="bold", zorder=4)
        ax.text(x + w / 2, y + h * 0.28, body, ha="center", va="center",
                fontsize=bs, color=MUTED, zorder=4, linespacing=1.35)
    else:
        ax.text(x + w / 2, y + h / 2, title, ha="center", va="center",
                fontsize=ts, color=tc, fontweight="bold", zorder=4,
                linespacing=1.35)


def arrow(ax, p0, p1, color=INK, style="-", lw=1.1, label="", lpos=0.5,
          ldx=0.0, ldy=0.012, fs=6.8, rad=0.0):
    ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle="-|>", mutation_scale=9,
                                 color=color, lw=lw, linestyle=style,
                                 connectionstyle=f"arc3,rad={rad}", zorder=2,
                                 shrinkA=1.5, shrinkB=2.5))
    if label:
        mx = p0[0] + (p1[0] - p0[0]) * lpos + ldx
        my = p0[1] + (p1[1] - p0[1]) * lpos + ldy
        ax.text(mx, my, label, ha="center", va="center", fontsize=fs,
                color=color, zorder=5,
                bbox=dict(fc="white", ec="none", pad=0.9))


def main() -> int:
    OUT.parent.mkdir(exist_ok=True)
    fig = plt.figure(figsize=(13.0, 7.3), dpi=230)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_facecolor("white")

    # ── 標題 ────────────────────────────────────────────────
    ax.text(0.035, 0.962, "查詢管線：三軌調度與降級鏈", fontsize=15.5,
            color=INK, fontweight="bold", va="center")
    ax.text(0.035, 0.925,
            "橘框為判斷點，虛線為降級路徑。任一軌未命中即向下一軌降級；"
            "三軌皆無證據時拒答，而非猜測。",
            fontsize=8.2, color=MUTED, va="center")

    # ── 輸入 ────────────────────────────────────────────────
    box(ax, 0.035, 0.845, 0.16, 0.052, "使用者問句", ec=INK, fc=FILL)

    # Step 0.5
    box(ax, 0.235, 0.845, 0.20, 0.052, "Step 0.5　[Fix 6]",
        "問句含「向量檢索」+「找出」？", ec=GATE_C, fc=GATE_F, ts=8.4, bs=7.0)
    arrow(ax, (0.195, 0.871), (0.235, 0.871))

    box(ax, 0.475, 0.845, 0.19, 0.052, "metadata 表格定位直答",
        "零 LLM　answer_mode=vector_search", ec=VEC_C, fc=VEC_F, ts=8.4, bs=6.8)
    arrow(ax, (0.435, 0.871), (0.475, 0.871), color=GATE_C, label="是", ldy=0.016)

    # Step 1 路由
    box(ax, 0.235, 0.745, 0.20, 0.058, "Step 1　意圖路由（LLM）",
        "route / query_type / companies\n"
        "quarters / item_name", ec=INK, fc="#ffffff", ts=8.6, bs=6.9)
    arrow(ax, (0.335, 0.845), (0.335, 0.803), label="否", ldx=0.018, ldy=0)

    ax.text(0.452, 0.774, "→ 注入偵測命中則改用\n   確定性重判（不信 LLM）",
            fontsize=6.8, color=GATE_C, va="center", linespacing=1.5)

    # 反劫持
    box(ax, 0.235, 0.640, 0.20, 0.062, "路由校正",
        "[Fix 5] 明示向量檢索不被劫持\n"
        "[Fix 13/14] 口語數值題防圖譜劫持\n"
        "[Fix 17] 跨公司比較題校正",
        ec=GATE_C, fc=GATE_F, ts=8.4, bs=6.6)
    arrow(ax, (0.335, 0.745), (0.335, 0.702))

    # ── 三軌 ────────────────────────────────────────────────
    y_track = 0.470
    # 圖譜軌
    box(ax, 0.055, y_track, 0.245, 0.135, "圖譜軌　GraphRAG（五層降級）",
        "L0　樣板確定性直答（零 LLM）\n"
        "L1　MS GraphRAG（本研究未啟用）\n"
        "L2a/2b　拓撲搜尋 ⇄ 實體表直查\n"
        "　　　　順序依 query_type 而定",
        ec=GRAPH_C, fc=GRAPH_F, ts=8.6, bs=6.9)
    arrow(ax, (0.262, 0.640), (0.178, 0.605), color=GRAPH_C,
          label="graph_rag", lpos=0.5, ldx=-0.026, ldy=0.014)

    # 直查軌
    box(ax, 0.330, y_track, 0.245, 0.135, "直查軌　Pandas 精確查表",
        "四段科目比對　col_hint 鎖欄\n"
        "表語意防禦（餘額 vs 流量）\n"
        "唯一值閘門：多值即視為未命中\n"
        "[Fix 14] 比率＝兩次查表＋Python 相除",
        ec=FACT_C, fc=FACT_F, ts=8.6, bs=6.9)
    arrow(ax, (0.408, 0.640), (0.452, 0.605), color=FACT_C,
          label="direct_lookup ／ colloquial", lpos=0.5, ldx=0.092, ldy=0.012)

    # 向量軌
    box(ax, 0.605, y_track, 0.245, 0.135, "向量軌　ChromaDB + LLM 生成",
        "逐層硬性過濾：公司+季度 → 僅公司\n"
        "永不回退至無過濾（跨公司隔離）\n"
        "[H1] 表格攤平 K-V　[G4] 指紋去重\n"
        "[P0-4] 受 Schema 強制的 JSON 作答",
        ec=VEC_C, fc=VEC_F, ts=8.6, bs=6.9)

    # 降級鏈（虛線）
    arrow(ax, (0.300, 0.508), (0.330, 0.508), color=MUTED, style="--",
          label="未命中", ldy=0.020, fs=6.4)
    arrow(ax, (0.575, 0.508), (0.605, 0.508), color=MUTED, style="--",
          label="未命中", ldy=0.020, fs=6.4)

    # ── 輸出 ────────────────────────────────────────────────
    box(ax, 0.330, 0.320, 0.245, 0.058, "答案 + answer_mode + router_decision",
        "供評測與前端呈現使用", ec=INK, fc=FILL, ts=8.6, bs=7.0)
    arrow(ax, (0.178, y_track), (0.360, 0.378), color=GRAPH_C, rad=-0.18)
    arrow(ax, (0.452, y_track), (0.452, 0.378), color=FACT_C)
    arrow(ax, (0.728, y_track), (0.548, 0.378), color=VEC_C, rad=0.18)

    box(ax, 0.620, 0.320, 0.185, 0.058, "no_evidence（拒答）",
        "三軌皆未命中 → 不猜", ec=GATE_C, fc=GATE_F, ts=8.6, bs=7.0)
    arrow(ax, (0.800, y_track), (0.735, 0.378), color=MUTED, style="--",
          label="皆未命中", lpos=0.5, ldx=0.052, ldy=0.004, fs=6.4)

    # ── 消融旗標 ────────────────────────────────────────────
    ax.add_patch(FancyBboxPatch((0.875, 0.440), 0.098, 0.195,
                                boxstyle="round,pad=0.006,rounding_size=0.012",
                                fc="#fbfcfe", ec="#c9d3e0", lw=1.0, zorder=1))
    ax.text(0.924, 0.615, "消融旗標", ha="center", fontsize=7.8,
            color=INK, fontweight="bold")
    for i, (t, c) in enumerate([("--vector-only", VEC_C),
                                ("--llm-only", MUTED),
                                ("--graph-only", GRAPH_C),
                                ("--no-direct", FACT_C)]):
        ax.text(0.924, 0.578 - i * 0.030, t, ha="center", fontsize=6.6, color=c)
    ax.text(0.924, 0.455, "各自關掉一軌\n以量測其貢獻", ha="center",
            fontsize=6.2, color=MUTED, linespacing=1.4)

    # ── 底部：確定性 vs LLM ─────────────────────────────────
    ax.add_patch(FancyBboxPatch((0.035, 0.075), 0.930, 0.185,
                                boxstyle="round,pad=0.008,rounding_size=0.010",
                                fc="#fffdfb", ec="#e6cfc6", lw=1.0, zorder=1))
    ax.text(0.055, 0.230, "設計主張：能確定性回答的，就不要交給 LLM",
            fontsize=9.4, color=GATE_C, fontweight="bold", va="center")
    rows = [
        ("圖譜軌 L0 樣板直答", "零 LLM", "毫秒級", GRAPH_C),
        ("直查軌（含比率算術）", "零 LLM", "查表 ~94 ms ／相除 0.022 ms", FACT_C),
        ("向量軌答案生成", "1 次 LLM", "受 JSON Schema 強制", VEC_C),
        ("意圖路由（所有軌共用）", "1 次 LLM", "約 3.3 s，佔端到端 96%", MUTED),
    ]
    for i, (name, llm, note, c) in enumerate(rows):
        y = 0.190 - i * 0.030
        ax.text(0.070, y, "●", fontsize=6.4, color=c, va="center")
        ax.text(0.090, y, name, fontsize=7.4, color=INK, va="center")
        ax.text(0.310, y, llm, fontsize=7.4, color=c, va="center",
                fontweight="bold")
        ax.text(0.395, y, note, fontsize=7.0, color=MUTED, va="center")
    ax.text(0.660, 0.150,
            "同一批 50 題比率，只換算術端：\n"
            "Python 代數 50/50　｜　LLM 算術 29/50\n"
            "把確定性工作交給 LLM，是把可驗證的東西換成不可驗證的。",
            fontsize=7.2, color=INK, va="center", linespacing=1.7)

    fig.savefig(OUT, facecolor="white", dpi=230, bbox_inches="tight",
                pad_inches=0.12)
    plt.close(fig)
    print(f"✓ {OUT}  ({OUT.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
