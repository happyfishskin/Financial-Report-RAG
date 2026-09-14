#!/usr/bin/env python3
"""論文用架構圖產生器：把 THESIS.md 內的 mermaid 流程圖轉為可插入 Word 的 PNG。

輸出至 slides_assets/，供 build_thesis_docx.py 依「圖號—圖名置於圖下方」之
學位論文格式規範插入。
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

OUT = Path(__file__).resolve().parent / "slides_assets"
OUT.mkdir(exist_ok=True)
_FONT_DIR = Path(__file__).resolve().parent / ".fonts"


def _ensure_tc_font() -> str:
    """系統 CJK 字型為 .ttc 集合，matplotlib 只註冊第一個 face（JP）。抽出 TC face。"""
    _FONT_DIR.mkdir(exist_ok=True)
    ok = True
    for src, tag in [("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "Regular"),
                     ("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", "Bold")]:
        dst = _FONT_DIR / f"NotoSansCJKtc-{tag}.otf"
        if not dst.exists():
            if not Path(src).exists():
                ok = False
                continue
            from fontTools.ttLib import TTCollection
            for f in TTCollection(src, lazy=True).fonts:
                if "TC" in (f["name"].getDebugName(1) or ""):
                    f.save(str(dst))
                    break
        if dst.exists():
            font_manager.fontManager.addfont(str(dst))
    return "Noto Sans CJK TC" if ok else "Noto Sans CJK JP"


_FAMILY = _ensure_tc_font()
plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["font.sans-serif"] = [_FAMILY, "Noto Sans CJK JP", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

INK = "#1a2332"
MUTED = "#6b7688"
ACCENT = "#c8553d"
GOOD = "#2d6a4f"
BLUE = "#3d6ea5"
FILL = "#f4f6f9"


def _box(ax, x, y, w, h, text, *, fc=FILL, ec=INK, fs=9, bold=False, tc=INK):
    ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h,
                                boxstyle="round,pad=0.012,rounding_size=0.02",
                                fc=fc, ec=ec, lw=1.1, zorder=2))
    ax.text(x, y, text, ha="center", va="center", fontsize=fs, color=tc,
            fontweight="bold" if bold else "normal", zorder=3, linespacing=1.45)


def _diamond(ax, x, y, w, h, text, *, fs=9):
    ax.add_patch(plt.Polygon([(x, y + h / 2), (x + w / 2, y), (x, y - h / 2), (x - w / 2, y)],
                             fc="#fff6e8", ec=ACCENT, lw=1.2, zorder=2))
    ax.text(x, y, text, ha="center", va="center", fontsize=fs, color=INK,
            fontweight="bold", zorder=3)


def _arrow(ax, p0, p1, *, label="", color=MUTED, style="-", fs=8, lo=0.0, dashed=False):
    ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle="-|>", mutation_scale=12,
                                 lw=1.1, color=color, zorder=1,
                                 linestyle="--" if dashed else "-",
                                 connectionstyle="arc3,rad=0"))
    if label:
        mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2 + lo
        ax.text(mx, my, label, ha="center", va="center", fontsize=fs, color=color,
                bbox=dict(fc="white", ec="none", pad=1.2), zorder=4)


_UNIT_PT = [46.8]  # 1 個資料單位等於幾 pt；由 _canvas 依畫布高度更新。


def _canvas(w, h):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis("off")
    fig.patch.set_facecolor("white")
    _UNIT_PT[0] = h * 72.0 / 10.0
    return fig, ax


def _stage(ax, x, y, w, h, head, body, *, fc=FILL, ec=INK, tc=INK,
           hs=7.6, bs=5.4, lh=1.5):
    """階段方塊：粗體標題行 ＋ 小字細節行（細節均取自實際程式碼）。

    標題與內文視為一個整體區塊，在方塊內垂直置中，避免 _stack 拉伸高度後
    文字全部擠在上緣。
    """
    ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h,
                                boxstyle="round,pad=0.012,rounding_size=0.02",
                                fc=fc, ec=ec, lw=1.15, zorder=2))
    nb = (body.count("\n") + 1) if body else 0
    block = (hs * 1.55 + nb * bs * lh) / _UNIT_PT[0]
    top = y + block / 2
    ax.text(x, top, head, ha="center", va="top", fontsize=hs,
            fontweight="bold", color=tc, zorder=3)
    if body:
        ax.text(x, top - hs * 1.55 / _UNIT_PT[0], body, ha="center", va="top",
                fontsize=bs, color=INK, zorder=3, linespacing=lh)


def _stack(ax, x, w, top, bottom, gap, items, *, hs, bs, lh=1.5):
    """在 top→bottom 的縱向空間內，依各方塊行數分配高度並等距排列。

    回傳 [(中心 y, 高度), ...]，供呼叫端自行決定要在哪幾段之間畫箭頭。
    """
    raw = [(hs * 1.55 + len(it["lines"]) * bs * lh) / _UNIT_PT[0] + 0.22
           for it in items]
    k = ((top - bottom) - gap * (len(items) - 1)) / sum(raw)
    out, y = [], top
    for it, h0 in zip(items, raw):
        h = h0 * k
        cy = y - h / 2
        _stage(ax, x, cy, w, h, it["head"], "\n".join(it["lines"]),
               fc=it.get("fc", FILL), ec=it.get("ec", INK), tc=it.get("tc", INK),
               hs=it.get("hs", hs), bs=it.get("bs", bs))
        out.append((cy, h))
        y -= h + gap
    return out


def fig_system_overview(slim: bool = False) -> None:
    """
    圖 3-1：確定性雙軌架構。

    改版重點（前一版是自三軌圖改寫而來，敘事被細節淹沒）：
      · 版面由直式改為橫式（原 0.94 直式在 A4 上佔近 70% 頁高，且與內文欄寬不合）
      · **界線畫出來**：軌道一與軌道二之間標明「以上零 LLM 生成／以下每題 1 次
        LLM 呼叫」——這才是本研究真正的架構分界（§3.5.1、§4.10 之 F2），
        而不是「資料是不是圖」
      · **唯一性判定獨立成節點**，並畫出「不唯一 → 拒答」的分支；前一版把它埋在
        查表方塊的十餘行細節裡，看不出系統會停下來（表 4-8e）
      · 離線兩張事實表以虛線標示「線上只讀取、不重建」，對應 F4：圖譜的價值
        全在離線 ETL

    字級與行長是依**印出來的尺寸**回推的，不是依畫布：本圖在論文中以約 6.2 吋
    寬置入（縮放約 0.6），故畫布上的 10.5 pt 內文印出來只有 6.3 pt。行長因此受
    限於「方塊寬度（單位）× 0.624 吋」——超過就得拆行或縮寫，不能只調字級，
    否則文字會溢出方塊。函式簽章過長者只保留名稱，參數與細節見 §3.5。

    slim=True 產生投影片版（字級放大、行數精簡）。
    """
    fact_c, fact_fill = "#3478b8", "#edf5fc"
    vec_c, vec_fill = "#7357a5", "#f4f0fa"
    graph_c, graph_fill = GOOD, "#eef7f1"
    L = 1 if slim else 0

    def pick(full, brief):
        return [full, brief][L]

    if slim:
        fig, ax = _canvas(13.0, 6.4)
        hs, bs, ts = 10.0, 7.6, 12.5
    else:
        fig, ax = _canvas(10.4, 6.9)
        hs, bs, ts = 13.0, 10.5, 16.5

    # ══ 左：離線建庫 ════════════════════════════════════════════
    ax.add_patch(FancyBboxPatch((0.12, 0.95), 2.72, 8.05,
                                boxstyle="round,pad=0.02,rounding_size=0.05",
                                fc="#fbfcfe", ec="#c9d3e0", lw=1.0, zorder=0))
    ax.text(1.48, 9.32, "離線建庫（只做一次）", ha="center", fontsize=ts,
            fontweight="bold", color=BLUE)

    _stage(ax, 1.48, 8.305, 2.40, 1.15, "① 財報表格",
           pick("MOPS HTML → 二維寬表 CSV\n30 家 × 8 季｜parse_html_report",
                "MOPS HTML → 二維寬表 CSV\n30 家 × 8 季"),
           fc="#ffffff", ec=INK, hs=hs, bs=bs)

    _stage(ax, 1.48, 6.935, 2.40, 1.15, "② 事實表線性化",
           pick("export_table_facts_csv\n每格〔列 × 值欄〕＝ 一筆 Fact",
                "export_table_facts_csv()\n每格 ＝ 一筆 Fact 六元組"),
           fc=fact_fill, ec=fact_c, tc=fact_c, hs=hs, bs=bs)
    _arrow(ax, (1.48, 7.73), (1.48, 7.51), color=fact_c)

    _stage(ax, 1.48, 5.565, 2.40, 1.15, "③a 數值事實表",
           pick("211,263 筆 Fact\nfull_df／deduped_df",
                "211,263 筆 Fact"),
           fc=fact_fill, ec=fact_c, tc=fact_c, hs=hs, bs=bs)
    _arrow(ax, (1.48, 6.36), (1.48, 6.14), color=fact_c)

    _stage(ax, 1.48, 4.02, 2.40, 1.50, "③b 關係事實表",
           pick("1,713 張欄位互異之附註表\n實體解析 ＋ schema 統一\n"
                "32,039 節點／125,167 邊",
                "1,713 張附註表 → 實體解析\n32,039 節點／125,167 邊"),
           fc=graph_fill, ec=graph_c, tc=graph_c, hs=hs, bs=bs)
    _arrow(ax, (1.48, 4.99), (1.48, 4.77), color=graph_c)

    _stage(ax, 1.48, 2.30, 2.40, 1.50, "③c 向量庫",
           pick("row-aware 切塊｜cosine\nbge-small-zh-v1.5\n"
                "ChromaDB 30,887 chunks",
                "row-aware 切塊 → ChromaDB\n30,887 chunks"),
           fc=vec_fill, ec=vec_c, tc=vec_c, hs=hs, bs=bs)
    _arrow(ax, (1.48, 3.27), (1.48, 3.05), color=vec_c)

    ax.text(1.48, 1.22, pick("三張表線上只讀取、不重建\n圖譜價值全在離線 ETL",
                             "線上只讀取、不重建"),
            ha="center", va="center", fontsize=bs * 0.9, color=MUTED,
            linespacing=1.5, zorder=3)

    # ══ 右：線上查詢 ════════════════════════════════════════════
    ax.add_patch(FancyBboxPatch((3.10, 0.95), 6.78, 8.05,
                                boxstyle="round,pad=0.02,rounding_size=0.05",
                                fc="#fffdfb", ec="#e6cfc6", lw=1.0, zorder=0))
    ax.text(6.49, 9.32, "線上查詢（每題）", ha="center", fontsize=ts,
            fontweight="bold", color=ACCENT)

    _stage(ax, 6.49, 8.40, 6.30, 1.10, "① Router 意圖路由",
           pick("_llm_intent_router（Qwen3-4B-AWQ 受限解碼）＋ "
                "_derive_track_deterministic\n"
                "route ∈ {direct_lookup, semantic_rag}；軌道一再依 _relation_query 分支",
                "route ∈ {direct_lookup, semantic_rag}"),
           fc="#fdf3ef", ec=ACCENT, tc=ACCENT, hs=hs, bs=bs)

    # ── 軌道一：確定性直查（虛線群組）──────────────────────────
    # 群組框右緣留 0.5 單位給 Router→軌道二 的走線；初版框寬 6.28 使該線
    # 只能從方塊內部穿過。
    ax.add_patch(FancyBboxPatch((3.55, 4.32), 5.80, 3.50,
                                boxstyle="round,pad=0.02,rounding_size=0.04",
                                fc="#f7fbff", ec=fact_c, lw=1.3, ls="--", zorder=0))
    ax.text(6.45, 7.66, "軌道一　確定性直查　零 LLM 生成・約 12 毫秒",
            ha="center", va="center", fontsize=ts * 0.84, fontweight="bold",
            color=fact_c, zorder=4)

    _stage(ax, 5.00, 6.55, 2.60, 1.50, "②a 數值事實直查",
           pick("槽位正規化 Fix 1/13/14/17\n_direct_lookup_flex\n"
                "科目四段遞進 ＋ 表別防禦",
                "槽位修復（Fix 1/13/14/17）\n_direct_lookup_flex() 四段比對"),
           fc="#ffffff", ec=fact_c, tc=fact_c, hs=hs, bs=bs)
    _stage(ax, 7.90, 6.55, 2.60, 1.50, "②b 關係事實直查",
           pick("_execute_relation_lookup\nL0 預編譯鍵值直答（Fix 16）\n"
                "三元主鍵：人×對象×科目｜L1",
                "L0 鍵值直答（Fix 16 三元主鍵）\nL1 entity_df 實體明細"),
           fc="#ffffff", ec=graph_c, tc=graph_c, hs=hs, bs=bs)
    # Router → 兩個分支：先垂直下引，再走 y=7.45 的橫向匯流排，避開群組標題
    ax.plot([9.15, 9.15], [7.85, 7.45], color=ACCENT, lw=1.1, zorder=1)
    ax.plot([5.00, 9.15], [7.45, 7.45], color=ACCENT, lw=1.1, zorder=1)
    _arrow(ax, (5.00, 7.45), (5.00, 7.30), color=ACCENT)
    _arrow(ax, (7.90, 7.45), (7.90, 7.30), color=ACCENT)

    # 唯一性判定：⟺ 於中文字型缺字（初版渲染為方框），改以文字敘述
    _stage(ax, 6.45, 5.10, 5.50, 1.15, "③ 唯一性判定：候選相異值恰為 1",
           pick("候選集合過濾後取值投影 π_V(K)；|π_V(K)| = 1 才作答\n"
                "不唯一即拒答，不從衝突候選中任選其一",
                "相異值恰為一個才作答；不唯一即拒答"),
           fc="#eef5fc", ec=fact_c, tc=fact_c, hs=hs, bs=bs)
    _arrow(ax, (5.00, 5.80), (5.60, 5.68), color=fact_c)
    _arrow(ax, (7.90, 5.80), (7.30, 5.68), color=fact_c)

    # ── 決定性界線 ─────────────────────────────────────────────
    ax.plot([3.62, 9.78], [4.16, 4.16], color="#b0392b", lw=1.4, ls=(0, (6, 3)),
            zorder=3)
    ax.text(6.49, 4.16, "　以上：程式取出（零生成）　｜　以下：模型生成　",
            ha="center", va="center", fontsize=bs, color="#b0392b",
            fontweight="bold", zorder=4,
            bbox=dict(fc="white", ec="none", pad=1.6))

    # ── 軌道二與結果（左右分開，避免方塊互疊）───────────────────
    _stage(ax, 4.75, 2.70, 2.90, 1.50, "④ 軌道二　語意向量降級軌",
           pick("metadata 硬過濾 → ANN Top-K\n_md_table_to_kv 鍵值展開\n"
                "_generate_answer_json 受限解碼",
                "metadata 硬過濾 → ANN Top-K\n檢索後鍵值展開 → 受限解碼生成"),
           fc=vec_fill, ec=vec_c, tc=vec_c, hs=hs, bs=bs)
    _stage(ax, 8.30, 3.30, 2.80, 1.15, "⑤ 答案",
           pick("value_raw 原值\n可回溯 source_csv, row_index",
                "原值輸出｜可回溯來源列"),
           fc="#f2f7f2", ec=GOOD, tc=GOOD, hs=hs, bs=bs)
    _stage(ax, 8.30, 1.90, 2.80, 1.15, "⑤′ 拒答",
           pick("找不到符合條件的資料\n條件不足，請指定交易對象／欄位",
                "查無資料／條件不足"),
           fc="#f7f8fa", ec=MUTED, tc=MUTED, hs=hs, bs=bs)

    # 軌道一未命中 → 軌道二（跨過決定性界線）
    _arrow(ax, (4.05, 4.32), (4.05, 3.45), color=ACCENT, dashed=True,
           label="未命中\npandas_miss", fs=bs * 0.9, lo=-0.08)
    # 唯一 → 答案（垂直，不經過任何方塊）
    _arrow(ax, (8.30, 4.55), (8.30, 3.88), color=GOOD)
    # 不唯一 → 拒答（走軌道二與結果之間的通道）
    ax.plot([6.55, 6.55], [4.55, 1.90], color=MUTED, lw=1.1, ls="--", zorder=1)
    _arrow(ax, (6.55, 1.90), (6.90, 1.90), color=MUTED, dashed=True)
    ax.text(6.55, 3.15, "不唯一", rotation=90, ha="center", va="center",
            fontsize=bs * 0.9, color=MUTED, zorder=4,
            bbox=dict(fc="#fffdfb", ec="none", pad=1.0))
    # 軌道二 → 答案
    _arrow(ax, (6.20, 2.95), (6.90, 3.20), color=vec_c)
    # Router → 軌道二（口語／非結構化題）：走左緣通道，不穿越軌道一
    ax.plot([3.60, 3.28, 3.28], [7.85, 7.85, 2.70], color=ACCENT, lw=1.1,
            zorder=1)
    _arrow(ax, (3.28, 2.70), (3.30, 2.70), color=ACCENT)
    # 標籤置於通道上緣（緊接 Router 分流處）：y≈5.6 會壓到離線→線上的三條虛線
    # 箭頭，y≈3.7 會壓到軌道一未命中的 pandas_miss 標籤；y≈7.2 是通道上唯一
    # 兩者都不經過的區段。
    ax.text(3.30, 7.20, "semantic_rag\n口語／非結構化題", rotation=90,
            ha="center", va="center", fontsize=bs * 0.85, color=ACCENT, zorder=4,
            linespacing=1.35,
            bbox=dict(fc="#fffdfb", ec="none", pad=1.0))

    # ── 離線 → 線上：只讀取，不重建 ─────────────────────────────
    # 前一版把三條線一路拉進右面板（終點 x≈3.35），與走同一條通道的
    # semantic_rag 垂直線（x=3.28）在 y 區間完全重疊，形成交纏。改為止於
    # 面板左緣的短水平箭頭：三張離線表與線上 ②a／②b／④ 已由 a／b／c 編號
    # 對應，方向足以表意，不需長距離連線。
    for y0, col in ((5.565, fact_c), (4.02, graph_c), (2.30, vec_c)):
        ax.add_patch(FancyArrowPatch((2.70, y0), (3.06, y0),
                                     arrowstyle="-|>", mutation_scale=11,
                                     lw=1.1, color=col, linestyle="--",
                                     connectionstyle="arc3,rad=0", zorder=1))

    ax.text(5.0, 0.42,
            "全題庫 602 道關係題 100% 由離線建好的關係事實表答出，線上圖遍歷貢獻 0 題"
            "（§3.5.1、附錄 B.5）——圖譜留在離線，線上只查表。",
            ha="center", va="center", fontsize=bs * 0.85, color=MUTED, zorder=4)

    fig.tight_layout(pad=0.3)
    name = "fig_system_overview_slide.png" if slim else "fig_system_overview.png"
    fig.savefig(OUT / name, dpi=200, facecolor="white")
    plt.close(fig)


def fig_system_overview_clean(slim: bool = False) -> None:
    """圖 3-1 修正版：如實分開數值唯一值閘門與關係候選處理。

    版面規則：所有標籤水平書寫；連線只走方塊間的保留通道；箭頭端點停在
    方塊邊緣，不從方塊下方穿越。關係軌多候選的現行行為明列為已知限制。
    """
    fact_c, fact_fill = "#3478b8", "#edf5fc"
    vec_c, vec_fill = "#7357a5", "#f4f0fa"
    graph_c, graph_fill = GOOD, "#eef7f1"
    warn_c, warn_fill = "#b0392b", "#fdf1ee"
    L = 1 if slim else 0

    def pick(full, brief):
        return [full, brief][L]

    if slim:
        fig, ax = _canvas(13.0, 6.4)
        hs, bs, ts = 10.5, 8.4, 13.2
    else:
        fig, ax = _canvas(10.4, 6.9)
        hs, bs, ts = 12.4, 9.5, 15.5

    def line(points, color=MUTED, dashed=False, arrow=True, lw=1.1):
        """折線連接；最後一小段另畫箭頭，避免箭頭被方塊遮住。"""
        style = "--" if dashed else "-"
        if len(points) > 2:
            xs, ys = zip(*points[:-1])
            ax.plot(xs, ys, color=color, lw=lw, ls=style, zorder=1)
        if arrow:
            _arrow(ax, points[-2], points[-1], color=color, dashed=dashed)
        else:
            xs, ys = zip(*points)
            ax.plot(xs, ys, color=color, lw=lw, ls=style, zorder=1)

    # ── 區域框 ───────────────────────────────────────────────
    ax.add_patch(FancyBboxPatch((0.10, 0.92), 2.62, 8.08,
                                boxstyle="round,pad=0.02,rounding_size=0.05",
                                fc="#fbfcfe", ec="#c9d3e0", lw=1.0, zorder=0))
    ax.add_patch(FancyBboxPatch((2.94, 0.92), 6.94, 8.08,
                                boxstyle="round,pad=0.02,rounding_size=0.05",
                                fc="#fffdfb", ec="#e6cfc6", lw=1.0, zorder=0))
    ax.text(1.41, 9.35, "離線建庫（只做一次）", ha="center", fontsize=ts,
            fontweight="bold", color=BLUE)
    ax.text(6.42, 9.35, "線上查詢（每題）", ha="center", fontsize=ts,
            fontweight="bold", color=ACCENT)

    # ── 離線建庫 ─────────────────────────────────────────────
    _stage(ax, 1.41, 8.28, 2.25, 1.02, "① 財報表格",
           pick("MOPS HTML → 二維寬表 CSV\n30 家 × 8 季", "MOPS HTML → CSV\n30 家 × 8 季"),
           fc="#ffffff", ec=INK, hs=hs, bs=bs)
    _stage(ax, 1.41, 6.92, 2.25, 1.05, "② 資料解析與正規化",
           pick("表格線性化＋實體解析＋metadata", "線性化＋實體解析"),
           fc=fact_fill, ec=fact_c, tc=fact_c, hs=hs, bs=bs)
    _stage(ax, 1.41, 5.55, 2.25, 1.05, "③a 數值事實表",
           "211,263 筆 Fact", fc=fact_fill, ec=fact_c, tc=fact_c, hs=hs, bs=bs)
    _stage(ax, 1.41, 4.02, 2.25, 1.30, "③b 關係事實表",
           pick("1,713 張附註表經實體解析\n32,039 節點／125,167 邊",
                "1,713 張附註表\n32,039 節點／125,167 邊"),
           fc=graph_fill, ec=graph_c, tc=graph_c, hs=hs, bs=bs)
    _stage(ax, 1.41, 2.40, 2.25, 1.30, "③c 向量索引",
           pick("row-aware 切塊＋metadata\nChromaDB 30,887 chunks",
                "metadata＋向量索引\n30,887 chunks"),
           fc=vec_fill, ec=vec_c, tc=vec_c, hs=hs, bs=bs)
    _arrow(ax, (1.41, 7.77), (1.41, 7.45), color=fact_c)
    # ② 解析完成後分別建立三種索引；右側分支線避免畫成三張表彼此串接。
    _arrow(ax, (1.41, 6.39), (1.41, 6.08), color=fact_c)
    ax.plot([2.54, 2.61, 2.61], [6.92, 6.92, 2.40], color=MUTED,
            lw=1.0, ls="--", zorder=1)
    _arrow(ax, (2.61, 4.02), (2.54, 4.02), color=graph_c, dashed=True)
    _arrow(ax, (2.61, 2.40), (2.54, 2.40), color=vec_c, dashed=True)
    ax.text(1.41, 1.22, "線上只讀取索引，不重建", ha="center", va="center",
            fontsize=bs * 0.92, color=MUTED)

    # 中間交界只放水平文字與短箭頭，不拉跨頁長線。
    ax.text(2.83, 8.15, "索引供線上讀取", ha="center", va="center",
            fontsize=bs * 0.78, color=MUTED)
    _arrow(ax, (2.55, 7.92), (3.02, 7.92), color=MUTED, dashed=True)

    # ── Router ────────────────────────────────────────────────
    _stage(ax, 6.42, 8.45, 5.55, 0.92, "① SLM 初判＋Python 規則覆核",
           pick("Qwen3-4B-AWQ 解析公司、期別、科目與題型\n"
                "route：direct_lookup／semantic_rag",
                "解析問題 → direct_lookup／semantic_rag"),
           fc="#fdf3ef", ec=ACCENT, tc=ACCENT, hs=hs, bs=bs)

    # 軌道一群組
    ax.add_patch(FancyBboxPatch((3.46, 4.18), 5.92, 3.62,
                                boxstyle="round,pad=0.02,rounding_size=0.04",
                                fc="#f7fbff", ec=fact_c, lw=1.25, ls="--", zorder=0))
    ax.text(6.42, 7.63, "軌道一｜確定性查表（答案取值不呼叫 SLM）",
            ha="center", va="center", fontsize=ts * 0.78, fontweight="bold",
            color=fact_c, zorder=4)

    _stage(ax, 4.78, 6.62, 2.45, 1.18, "②a 數值事實直查",
           pick("欄位正規化＋科目四段比對\n讀取 ③a 數值事實表",
                "正規化＋四段比對\n讀取數值事實表"),
           fc="#ffffff", ec=fact_c, tc=fact_c, hs=hs, bs=bs)
    _stage(ax, 7.82, 6.62, 2.45, 1.18, "②b 關係事實直查",
           pick("L0 關係鍵值直答 → L1 明細備援\n讀取 ③b 關係事實表",
                "L0 鍵值直答 → L1 備援\n讀取關係事實表"),
           fc="#ffffff", ec=graph_c, tc=graph_c, hs=hs, bs=bs)

    _stage(ax, 4.78, 4.98, 2.45, 1.18, "③a 數值唯一值閘門",
           pick("相異值 = 1 → 回答\n多值 → 拒答；空值 → 向量軌",
                "唯一 → 回答\n多值拒答；空值降級"),
           fc=fact_fill, ec=fact_c, tc=fact_c, hs=hs, bs=bs)
    _stage(ax, 7.82, 4.98, 2.45, 1.18, "③b L1 明細多候選處理",
           pick("唯一 → 回答；多值＋有期別 → 取首筆\n多值＋無期別 → 全量列示（已知限制）",
                "L1：唯一 → 回答\n多值列示／取首筆（限制）"),
           fc=warn_fill, ec=warn_c, tc=warn_c, hs=hs, bs=bs)

    # Router → 兩個確定性分支：使用上方水平匯流排。
    ax.plot([6.42, 6.42], [7.99, 7.55], color=ACCENT, lw=1.1, zorder=1)
    ax.plot([4.78, 7.82], [7.55, 7.55], color=ACCENT, lw=1.1, zorder=1)
    _arrow(ax, (4.78, 7.55), (4.78, 7.22), color=ACCENT)
    _arrow(ax, (7.82, 7.55), (7.82, 7.22), color=ACCENT)
    ax.text(6.42, 7.88, "direct_lookup", ha="center", va="center",
            fontsize=bs * 0.74, color=ACCENT,
            bbox=dict(fc="#f7fbff", ec="none", pad=1.0), zorder=4)
    _arrow(ax, (4.78, 6.03), (4.78, 5.57), color=fact_c)
    _arrow(ax, (7.82, 6.03), (7.82, 5.57), color=graph_c)

    # ── 決定性／生成界線 ─────────────────────────────────────
    ax.plot([3.48, 9.36], [4.02, 4.02], color=warn_c, lw=1.35, ls=(0, (6, 3)), zorder=1)
    ax.text(6.42, 4.02, "上方：程式取值｜下方：模型生成",
            ha="center", va="center", fontsize=bs * 0.92, color=warn_c,
            fontweight="bold", bbox=dict(fc="white", ec="none", pad=1.2), zorder=4)

    # ── 軌道二、答案與拒答 ───────────────────────────────────
    _stage(ax, 4.72, 2.68, 2.85, 1.40, "④ 軌道二｜語意向量 RAG",
           pick("讀取 ③c：metadata 過濾 → ANN Top-K\n"
                "鍵值展開 → SLM 受限解碼生成",
                "metadata 過濾 → 向量搜尋\nSLM 生成一次"),
           fc=vec_fill, ec=vec_c, tc=vec_c, hs=hs, bs=bs)
    _stage(ax, 8.20, 3.02, 2.25, 1.02, "⑤ 答案＋來源",
           pick("原值／生成答案\n回溯 source_csv、row_index", "回答並保留來源"),
           fc="#f2f7f2", ec=GOOD, tc=GOOD, hs=hs, bs=bs)
    _stage(ax, 8.20, 1.62, 2.25, 1.00, "⑤′ 拒答",
           pick("數值多值、查無資料或條件不足", "多值／查無資料／條件不足"),
           fc="#f7f8fa", ec=MUTED, tc=MUTED, hs=hs, bs=bs)

    # Router → semantic_rag：走右面板最左側的獨立通道；標籤保持水平。
    ax.plot([3.64, 3.20, 3.20], [8.45, 8.45, 2.68], color=vec_c, lw=1.05, zorder=1)
    _arrow(ax, (3.20, 2.68), (3.30, 2.68), color=vec_c)
    ax.text(3.36, 3.72, "semantic_rag", ha="left", va="center",
            fontsize=bs * 0.78, color=vec_c,
            bbox=dict(fc="#fffdfb", ec="none", pad=0.8), zorder=4)

    # 空候選降級：由數值閘門左下繞至向量軌上緣，不穿過任何方塊。
    line([(3.55, 4.98), (3.34, 4.98), (3.34, 3.38), (4.05, 3.38)],
         color=vec_c, dashed=True)
    ax.text(3.45, 4.48, "空候選降級", ha="left", va="center",
            fontsize=bs * 0.75, color=vec_c,
            bbox=dict(fc="#f7fbff", ec="none", pad=0.7), zorder=4)

    # 兩個查表分支的可回答結果在界線上方匯流，再向下接答案。
    ax.plot([4.78, 4.78, 7.82], [4.39, 3.82, 3.82], color=GOOD, lw=1.05, zorder=1)
    ax.plot([7.82, 7.82], [4.39, 3.82], color=GOOD, lw=1.05, zorder=1)
    line([(7.82, 3.82), (9.48, 3.82), (9.48, 3.52), (9.32, 3.52)], color=GOOD)
    ax.text(8.55, 3.94, "可回答", ha="center", va="center",
            fontsize=bs * 0.78, color=GOOD,
            bbox=dict(fc="white", ec="none", pad=0.7), zorder=4)

    # 向量軌 → 答案；是否拒答由受限解碼狀態決定，文字放在箭頭上方。
    _arrow(ax, (6.15, 2.90), (7.07, 3.02), color=vec_c)
    ax.text(6.60, 3.16, "生成／狀態判定", ha="center", va="center",
            fontsize=bs * 0.72, color=vec_c,
            bbox=dict(fc="white", ec="none", pad=0.6), zorder=4)

    # 數值多值 → 拒答：走兩個下方方塊間的通道。
    line([(6.00, 4.98), (6.38, 4.98), (6.38, 1.62), (7.07, 1.62)],
         color=MUTED, dashed=True)
    ax.text(6.50, 2.02, "數值多值", ha="left", va="center",
            fontsize=bs * 0.75, color=MUTED,
            bbox=dict(fc="#fffdfb", ec="none", pad=0.7), zorder=4)

    ax.text(5.0, 0.42,
            "正式關係題由 L0 關係事實表直答；唯一值閘門僅完整適用於數值軌。"
            "L1 明細備援的多候選處理列為已知限制。",
            ha="center", va="center", fontsize=bs * 0.84, color=MUTED, zorder=4)

    fig.tight_layout(pad=0.3)
    name = "fig_system_overview_slide.png" if slim else "fig_system_overview.png"
    fig.savefig(OUT / name, dpi=200, facecolor="white")
    plt.close(fig)


def fig_system_overview_minimal(slim: bool = False) -> None:
    """圖 3-1 極簡排版：上下兩層、三欄對齊，取消跨區長箭頭。"""
    fact_c, fact_fill = "#3478b8", "#edf5fc"
    graph_c, graph_fill = GOOD, "#eef7f1"
    vec_c, vec_fill = "#7357a5", "#f4f0fa"
    warn_c, warn_fill = "#b0392b", "#fdf1ee"
    L = 1 if slim else 0

    def pick(full, brief):
        return [full, brief][L]

    if slim:
        fig, ax = _canvas(13.0, 6.4)
        hs, bs, ts = 10.2, 8.2, 13.0
    else:
        fig, ax = _canvas(10.4, 6.9)
        hs, bs, ts = 12.0, 9.4, 15.2

    # ── 區域底框 ─────────────────────────────────────────────
    ax.add_patch(FancyBboxPatch((0.15, 6.45), 9.70, 2.55,
                                boxstyle="round,pad=0.02,rounding_size=0.05",
                                fc="#fbfcfe", ec="#c9d3e0", lw=1.0, zorder=0))
    ax.add_patch(FancyBboxPatch((0.15, 0.72), 9.70, 5.28,
                                boxstyle="round,pad=0.02,rounding_size=0.05",
                                fc="#fffdfb", ec="#e6cfc6", lw=1.0, zorder=0))
    ax.text(0.42, 8.78, "離線建庫（只做一次）", ha="left", va="center",
            fontsize=ts, fontweight="bold", color=BLUE)
    ax.text(0.42, 5.75, "線上查詢（每題）", ha="left", va="center",
            fontsize=ts, fontweight="bold", color=ACCENT)

    # ── 上層：建庫 ───────────────────────────────────────────
    _stage(ax, 1.15, 7.55, 1.55, 1.05, "① MOPS 財報",
           pick("HTML／CSV\n30 家 × 8 季", "HTML／CSV"),
           fc="#ffffff", ec=INK, hs=hs, bs=bs)
    _stage(ax, 3.12, 7.55, 1.72, 1.05, "② 解析與正規化",
           pick("表格線性化\n實體解析＋metadata", "線性化＋實體解析"),
           fc="#f7f8fa", ec=MUTED, tc=MUTED, hs=hs, bs=bs)
    _stage(ax, 5.25, 7.55, 1.38, 1.05, "③a 數值 Fact",
           "211,263 筆", fc=fact_fill, ec=fact_c, tc=fact_c, hs=hs, bs=bs)
    _stage(ax, 7.00, 7.55, 1.38, 1.05, "③b 關係事實",
           pick("1,713 張附註表\n32,039 節點", "32,039 節點"),
           fc=graph_fill, ec=graph_c, tc=graph_c, hs=hs, bs=bs)
    _stage(ax, 8.75, 7.55, 1.38, 1.05, "③c 向量索引",
           "30,887 chunks", fc=vec_fill, ec=vec_c, tc=vec_c, hs=hs, bs=bs)
    _arrow(ax, (1.93, 7.55), (2.25, 7.55), color=MUTED)
    # 解析後沿上方匯流排分別建立三類索引。
    ax.plot([3.98, 4.28, 4.28, 8.75], [7.55, 7.55, 8.32, 8.32],
            color=MUTED, lw=1.05, zorder=1)
    for x, col in ((5.25, fact_c), (7.00, graph_c), (8.75, vec_c)):
        _arrow(ax, (x, 8.32), (x, 8.08), color=col)
    ax.text(6.50, 8.48, "建立三類索引", ha="center", va="center",
            fontsize=bs * 0.82, color=MUTED)

    # ── 下層：問題與路由 ─────────────────────────────────────
    _stage(ax, 1.15, 4.82, 1.55, 0.92, "① 使用者問題", "繁中財報問句",
           fc="#ffffff", ec=INK, hs=hs, bs=bs)
    _stage(ax, 3.12, 4.82, 1.72, 0.92, "② SLM 初判",
           pick("Python 規則覆核\n公司／期別／科目／題型", "＋Python 規則覆核"),
           fc="#fdf3ef", ec=ACCENT, tc=ACCENT, hs=hs, bs=bs)
    _arrow(ax, (1.93, 4.82), (2.25, 4.82), color=ACCENT)

    # 三條查詢分支與上層三種索引垂直對齊，不再拉跨區資料線。
    _stage(ax, 5.25, 4.82, 1.38, 1.08, "③a 數值直查",
           pick("讀取數值 Fact\n正規化＋四段比對", "讀取 ③a\n正規化＋比對"),
           fc="#ffffff", ec=fact_c, tc=fact_c, hs=hs, bs=bs)
    _stage(ax, 7.00, 4.82, 1.38, 1.08, "③b 關係直查",
           pick("讀取關係事實\nL0 直答 → L1 備援", "讀取 ③b\nL0 → L1"),
           fc="#ffffff", ec=graph_c, tc=graph_c, hs=hs, bs=bs)
    _stage(ax, 8.75, 4.82, 1.38, 1.08, "③c 向量 RAG",
           pick("讀取向量索引\nmetadata → Top-K", "讀取 ③c\nmetadata → Top-K"),
           fc="#ffffff", ec=vec_c, tc=vec_c, hs=hs, bs=bs)

    # Router 上方匯流排：兩個 route 值，再依關係題型分支。
    ax.plot([3.98, 4.28, 4.28, 8.75], [4.82, 4.82, 5.55, 5.55],
            color=ACCENT, lw=1.05, zorder=1)
    for x in (5.25, 7.00, 8.75):
        _arrow(ax, (x, 5.55), (x, 5.36), color=ACCENT)
    ax.text(6.10, 5.68, "direct_lookup", ha="center", va="center",
            fontsize=bs * 0.78, color=ACCENT)
    ax.text(8.75, 5.68, "semantic_rag", ha="center", va="center",
            fontsize=bs * 0.78, color=vec_c)

    # ── 各分支自己的處理結果：只有短直線，沒有交叉線 ───────────
    _stage(ax, 5.25, 2.98, 1.38, 1.42, "④a 唯一值閘門",
           pick("唯一 → 回答\n多值 → 拒答\n空值 → RAG", "唯一回答\n多值拒答\n空值降級"),
           fc=fact_fill, ec=fact_c, tc=fact_c, hs=hs, bs=bs)
    _stage(ax, 7.00, 2.98, 1.38, 1.42, "④b L1 多候選",
           pick("唯一 → 回答\n有期別取首筆\n無期別列示（限制）",
                "唯一回答\n多值列示／取首筆\n（限制）"),
           fc=warn_fill, ec=warn_c, tc=warn_c, hs=hs, bs=bs)
    _stage(ax, 8.75, 2.98, 1.38, 1.42, "④c 生成與狀態",
           pick("鍵值展開\nSLM 生成一次\nok／拒答狀態", "SLM 生成一次\n回答或拒答"),
           fc=vec_fill, ec=vec_c, tc=vec_c, hs=hs, bs=bs)
    for x, col in ((5.25, fact_c), (7.00, graph_c), (8.75, vec_c)):
        _arrow(ax, (x, 4.28), (x, 3.69), color=col)

    # 共同輸出只做摘要，不再把三條箭頭硬匯到同一個小框。
    ax.add_patch(FancyBboxPatch((4.50, 1.12), 4.95, 0.82,
                                boxstyle="round,pad=0.02,rounding_size=0.04",
                                fc="#f2f7f2", ec=GOOD, lw=1.15, zorder=2))
    ax.text(6.98, 1.53,
            pick("⑤ 共同輸出：回答保留來源；拒答回傳原因\n"
                 "正式關係題由 L0 直答，L1 多候選列為已知限制",
                 "⑤ 回答保留來源；拒答回傳原因｜L1 多候選為已知限制"),
            ha="center", va="center", fontsize=bs, color=GOOD,
            fontweight="bold", linespacing=1.35, zorder=3)
    # 三個短箭頭各自落在共同輸出上緣，彼此平行且不交叉。
    for x, col in ((5.25, fact_c), (7.00, graph_c), (8.75, vec_c)):
        _arrow(ax, (x, 2.27), (x, 1.94), color=col)

    ax.text(2.05, 1.55,
            pick("核心界線\n數值：唯一才回答\n關係 L1：多候選仍有限制\n向量：僅在需要時生成",
                 "核心界線\n數值唯一才回答\n關係 L1 多候選為限制"),
            ha="center", va="center", fontsize=bs * 0.90, color=MUTED,
            linespacing=1.4, zorder=3)

    fig.tight_layout(pad=0.3)
    name = "fig_system_overview_slide.png" if slim else "fig_system_overview.png"
    fig.savefig(OUT / name, dpi=200, facecolor="white")
    plt.close(fig)


def fig_fix_positions() -> None:
    """圖 3-3：Fix 1–20 依作用階段分成五個修復群。

    前一版是按**三軌**排的（精確查表軌／自建 KG-RAG 軌／向量語意軌），那是三軌
    時期的產物：三軌已收斂為雙軌，圖裡的「三路檢索」在正文中已不存在。改按
    §3.5.2 的五階段排列，同時解掉另一個問題——同一批 Fix 在論文裡原本有三套
    分法（六道防線、四類、五階段），讀者無從得知哪一套是正典。

    群名取自 fix_groups.py，與表 3-4b、附錄表 E-1 及簡報第 8 頁同一組名字。
    Fix 13、14 跨兩個階段，在所屬的兩群各出現一次；這是作用位置，不是重複計數。

    Fix 19（多候選全列並列）歸群五；Fix 20（明示預設期別）歸群四——後者使群四
    不再是「無編號 Fix」的純判定階段，圖與 fix_groups.py 一併更新。
    """
    from fix_groups import GROUPS

    fig, ax = _canvas(8.4, 5.8)
    hs, bs = 11.0, 9.5
    # 五群配色：一～三是「把候選收斂到可判定」的前段，四是閘門，五是輸出
    palette = {
        "slot":     ("#3478b8", "#edf5fc"),
        "schema":   ("#3478b8", "#edf5fc"),
        "narrow":   ("#3478b8", "#edf5fc"),
        "gate":     ("#b0392b", "#fdf1ee"),
        "assemble": (GOOD, "#eef7f1"),
    }
    body = {
        "slot": "Fix 1 欄位標頭與科目全名｜Fix 5·6 檢索通道守衛｜Fix 17 公司清單與期別\n"
                "Fix 13 口語同義詞｜Fix 14 比率同義詞｜Fix 18 自然語句槽位",
        "schema": "Fix 12 市場簡稱 → 申報全名｜Fix 13 科目本體論最長匹配",
        "narrow": "Fix 11 表名鎖定｜Fix 2 年份感知去重\n"
                  "Fix 7·8·9 申報公司與鑑別子句｜Fix 16 關係三元主鍵",
        "gate": "相異值恰為 1 才作答，不唯一即拒答\n"
                "Fix 20 未給期別之單值題：採最新期別並於答案內揭露（比較題不套用）",
        "assemble": "Fix 3·4 語境補全與樣板直答｜Fix 10 比較與趨勢後綴｜Fix 19 多候選全列並列\n"
                    "Fix 14 Python 除法｜Fix 15 逾時轉可恢復錯誤",
    }

    ax.text(5.0, 9.72, "線上推論管線的五個階段——Fix 1–20 依作用階段分為五個修復群",
            ha="center", va="center", fontsize=hs * 1.05, fontweight="bold",
            color=INK)

    H, tops = 1.20, [8.75, 7.25, 5.75, 4.25, 2.75]   # 方塊高度與各群中心
    for cy, g in zip(tops, GROUPS):
        ec, fc = palette[g.key]
        _stage(ax, 5.0, cy, 8.80, H,
               f"群{g.stage_no}　{g.name}　｜　階段{g.stage_no}　{g.stage}：{g.purpose}",
               body[g.key], fc=fc, ec=ec, tc=ec, hs=hs, bs=bs)

    for a, b in zip(tops, tops[1:]):
        _arrow(ax, (5.0, a - H / 2), (5.0, b + H / 2), color=MUTED)

    # 群四是唯一會讓流程中止的階段，往右拉出拒答分支
    gate_y = tops[[g.key for g in GROUPS].index("gate")]
    ax.plot([9.40, 9.72, 9.72], [gate_y, gate_y, 1.75], color="#b0392b", lw=1.0,
            ls="--", zorder=1)
    ax.text(9.72, 3.00, "不唯一即拒答", rotation=90, ha="center", va="center",
            fontsize=bs * 0.92, color="#b0392b", zorder=4,
            bbox=dict(fc="white", ec="none", pad=1.0))

    ax.text(5.0, 1.15,
            "Fix 13 同時屬群一與群二，Fix 14 同時屬群一與群五——此為作用位置，非重複"
            "計數（對照表 3-10、附錄表 E-1）。Fix 19、20 各只屬一群。",
            ha="center", va="center", fontsize=bs * 0.92, color=MUTED)

    fig.tight_layout(pad=0.3)
    fig.savefig(OUT / "fig_fix_positions.png", dpi=200, facecolor="white")
    plt.close(fig)


def fig_arch_change() -> None:
    """圖 4-3：歷史三軌快照與現行雙軌口徑之架構對照。

    圖上每一項數字均取自評測輸出，非示意：
      * 三軌題數 = 各版 summary.answer_mode_dist
        （version7/rag_evaluation_v12_arch100.json；results/test_eval_arch100_orig.json）
      * col_hint 覆蓋率、科目名截斷題數 = 逐題比對 results[*].router_decision
      * 分流正確率 = 實際 answer_mode 與資料集 metadata.target_route 相符之題數
    """
    fig, ax = _canvas(9.8, 8.8)

    # ── 上欄：原始版本 v12（骨架已具備路由器與三軌）────────────────────────
    ax.add_patch(FancyBboxPatch((0.15, 6.05), 9.7, 3.75,
                                boxstyle="round,pad=0.02,rounding_size=0.05",
                                fc="#fdf6f4", ec="#e0c3ba", lw=1.0, zorder=0))
    ax.text(5.0, 9.58, "原始版本 v12：歷史三軌快照（EM 12.0%）", ha="center",
            fontsize=10.5, fontweight="bold", color=ACCENT)

    _box(ax, 1.15, 8.9, 1.75, 0.55, "使用者問題", fs=8)
    _box(ax, 4.75, 8.9, 4.7, 1.15,
         "LLM 路由器\n"
         "× router_decision 無 col_hint 欄位（0/100）\n"
         "× 科目名遭截斷（13 題）：期初／期末／增減\n三科目同時塌縮為「現金及約當現金」",
         fs=6.8, fc="#ffffff", ec=ACCENT)
    _arrow(ax, (2.05, 8.9), (2.38, 8.9))
    _diamond(ax, 8.8, 8.9, 1.85, 0.8, "歷史三軌分流\n89/100", fs=7.2)
    _arrow(ax, (7.12, 8.9), (7.86, 8.9))

    base_tracks = [
        (1.45, "直查軌　61 題\n× 二維表格未線性化\n依報表季度逕取第 1 欄"),
        (3.65, "圖譜軌　36 題\n× 拓撲未扁平化\n另劫持 8 題向量題"),
        (5.85, "向量軌　1 題\n× 10 題向量題\n僅 1 題進入本軌"),
        (8.05, "no_evidence　2 題\n產業鏈題無可用證據"),
    ]
    ax.plot([1.45, 8.8], [8.15, 8.15], color=MUTED, lw=1.0, zorder=1)
    _arrow(ax, (8.8, 8.5), (8.8, 8.16))
    for x, t in base_tracks:
        _box(ax, x, 7.52, 2.05, 0.95, t, fs=6.6)
        _arrow(ax, (x, 8.15), (x, 8.01))
    _box(ax, 5.0, 6.52, 7.6, 0.6,
         "答案　× 輸出無格式約束（夾帶冗詞／單位）　　"
         "Hit@1 97.65%　EM 12.0%　分流 89/100",
         fs=7.3, bold=True, fc="#fdece7", ec=ACCENT, tc=ACCENT)
    for x, _ in base_tracks:
        _arrow(ax, (x, 7.04), (x, 6.83))

    # ── 兩欄之間：三項技術之介入 ──────────────────────────────────────────
    _arrow(ax, (1.5, 6.05), (1.5, 5.70), color=GOOD)
    ax.text(1.78, 5.88,
            "①結構扁平化 12%→76%　　②確定性修復層 76%→90%",
            ha="left", va="center", fontsize=8.2, color=GOOD, fontweight="bold")

    # ── 下欄：Fix 1–11，以論文現行「確定性／語意」雙軌口徑重新歸類 ────────
    ax.add_patch(FancyBboxPatch((0.15, 0.12), 9.7, 5.5,
                                boxstyle="round,pad=0.02,rounding_size=0.05",
                                fc="#f5f9f6", ec="#bfd6c6", lw=1.0, zorder=0))
    ax.text(5.0, 5.40, "Fix 1–11 系統：現行雙軌口徑（EM 90.0%）", ha="center",
            fontsize=10.5, fontweight="bold", color=GOOD)

    _box(ax, 1.15, 4.78, 1.75, 0.55, "使用者問題", fs=8)
    _box(ax, 3.85, 4.78, 3.0, 0.8,
         "LLM 意圖路由器\nQwen3-4B-AWQ → JSON intent", fs=7.0)
    _box(ax, 7.85, 4.78, 4.0, 1.05,
         "②確定性修復層 Fix 1–11\n"
         "col_hint 正則補回（60/100）\n"
         "以【】內最長 token 還原科目全名・年份感知去重・鎖表",
         fs=6.7, fc="#fdf3ef", ec=ACCENT)
    _arrow(ax, (2.05, 4.78), (2.33, 4.78))
    _arrow(ax, (5.37, 4.78), (5.83, 4.78))

    _diamond(ax, 5.0, 3.72, 2.2, 0.78, "雙軌路由裁決\n100/100", fs=7.2)
    ax.plot([7.85, 7.85], [4.24, 4.05], color=MUTED, lw=1.1, zorder=1)
    ax.plot([7.85, 5.0], [4.05, 4.05], color=MUTED, lw=1.1, zorder=1)
    _arrow(ax, (5.0, 4.05), (5.0, 4.13))

    lanes = [
        (3.15, 4.8,
         "軌道一｜確定性直查　90 題\n"
         "數值事實 60 題：表格線性化為 Fact 六元組，依多重條件唯一取值\n"
         "關係事實 30 題：拓撲預先扁平化為 k=v，以 Python 鍵值匹配"),
        (7.75, 3.5,
         "軌道二｜語意向量　10 題\n"
         "ChromaDB metadata 硬過濾\n"
         "格式約束：規範輸出來源檔與表名"),
    ]
    ax.plot([3.15, 7.75], [3.12, 3.12], color=MUTED, lw=1.0, zorder=1)
    _arrow(ax, (5.0, 3.33), (5.0, 3.13))
    for x, w, t in lanes:
        _box(ax, x, 2.48, w, 1.05, t, fs=6.55)
        _arrow(ax, (x, 3.12), (x, 3.01))

    _box(ax, 5.0, 1.42, 7.9, 0.85,
         "答案　①格式約束：方框內僅輸出數值\n"
         "Hit@1 100%　EM 90.0%（舊金標）／84.0%（修正金標）　分流 100/100　降級歸零",
         fs=7.2, bold=True, fc="#eaf4ee", ec=GOOD, tc=GOOD)
    for x, _, _ in lanes:
        _arrow(ax, (x, 1.95), (x, 1.86))

    _box(ax, 5.0, 0.52, 9.1, 0.62,
         "③鑑別扁平化（資料集端，不改動推論路徑）：金標注入唯一鑑別子句，"
         "一對多歧義收斂為單鍵單值\n"
         "→ v2 資料集：舊金標 100% ／ 修正金標 90.0%；現行口徑為軌道一 90 題、軌道二 10 題\n"
         "（由歷史三軌 60／30／10 重新歸類，未重跑推論；逐題答案與 EM 不變）",
         fs=6.6, fc="#fffdf2", ec="#c9a227")
    _arrow(ax, (5.0, 0.84), (5.0, 0.99), color="#c9a227", dashed=True)

    fig.tight_layout(pad=0.3)
    fig.savefig(OUT / "fig_arch_change.png", dpi=200, facecolor="white")
    fig.savefig(OUT / "fig_arch_change.svg", facecolor="white")
    plt.close(fig)


# ======================================================================================
# 實機截圖裁切：原始截圖為 1600×900 全視窗，左右留白與「範例題按鈕帶」佔去大量面積，
# 縮到 15.5cm 版面寬後內文過小。裁掉無資訊區域可使有效內容放大約 1.45 倍。
# ======================================================================================
SHOTS = {
    # 檔名: (左, 右, 上緣保留至, 按鈕帶結束於, 底部裁切)
    "qa_direct":     dict(x0=250, x1=1350, title_h=58, keep_top=160, chips_end=310, bottom=900),
    "qa_graph":      dict(x0=250, x1=1350, title_h=58, keep_top=160, chips_end=310, bottom=900),
    "qa_vector":     dict(x0=250, x1=1350, title_h=58, keep_top=160, chips_end=310, bottom=580),
    "render_full":   dict(x0=0, x1=1250, keep_top=0, chips_end=0, bottom=900),
    "render_layered": dict(x0=0, x1=1250, keep_top=0, chips_end=0, bottom=900),
}


def crop_screenshots() -> None:
    from PIL import Image

    for name, c in SHOTS.items():
        src = OUT / f"{name}.png"
        if not src.exists():
            print(f"  略過（找不到）{src.name}")
            continue
        im = Image.open(src)
        # 三段裁切：App 標題列內容靠左（自 x=0 起裁）；問題輸入框與其下主體則置中
        # （自 x0 起裁）。若混為一段，靠左裁切會把較寬的問題輸入框右緣切掉。
        w = c["x1"] - c["x0"]
        parts = []
        if c["keep_top"]:
            parts.append(im.crop((0, 0, w, c["title_h"])))
            parts.append(im.crop((c["x0"], c["title_h"], c["x1"], c["keep_top"])))
        parts.append(im.crop((c["x0"], c["chips_end"], c["x1"], c["bottom"])))
        out = Image.new("RGB", (w, sum(p.height for p in parts)))
        y = 0
        for part in parts:
            out.paste(part, (0, y))
            y += part.height
        dst = OUT / f"{name}_fig.png"
        out.save(dst)
        print(f"  裁切 {src.name} {im.size} → {dst.name} {out.size}")


def fig_graph_pipeline() -> None:
    """圖 3-x：財報知識圖譜之離線編譯資料流。

    本研究把圖譜定位在**離線 ETL**——其價值是異質申報表的實體解析與 schema 統一，
    而非圖演算法（見 §3.4 與附錄 B.5）。此圖即畫出該條資料流：從欄位互異的原始表，
    經公司名四級錨定與四類編譯器，壓成單一 (source, type, target, 屬性) schema。

    所有數字皆取自實際編譯結果（`_load_all_compiled_graphs()` 之實測），未取自敘述。
    """
    fig, ax = _canvas(9.2, 6.1)

    W = 9.3
    # ── ① 來源 ────────────────────────────────────────────────
    _stage(ax, 5.0, 9.20, W, 1.25, "① 原始申報表（MOPS HTML → 二維寬表 CSV）",
           "30 家半導體上市公司 × 8 個季度（113Q1–114Q4）\n"
           "其中實體類原始表 1,713 張，表頭寫法 18 種",
           hs=8.2, bs=6.4)

    # ── ② 實體解析 ────────────────────────────────────────────
    _stage(ax, 5.0, 7.30, W, 1.50, "② 實體解析（同一實體在各表寫法不一）",
           "公司名錨定四級漏斗：精確 → 前綴 → 寬鬆包含 → 編輯距離\n"
           "兩套 id 體系 company:{代號} 與 company_name:{名稱} 由錨定函式合併\n"
           "關係人邊在四個來源有四種型別拼法，於此統一",
           hs=8.2, bs=6.4, ec=BLUE)
    _arrow(ax, (5.0, 8.57), (5.0, 8.08))

    # ── ③ 四類編譯器（並列）──────────────────────────────────
    cols = [
        (1.50, "investment", "節點 1,052／邊 8,665", "INVESTS_IN、DISCLOSES_\nINVESTOR、LOCATED_IN、\nHAS_BUSINESS"),
        (3.83, "related_party", "節點 9,743／邊 47,799", "HAS_RELATED_PARTY_\nTRANSACTION、HAS_\nTRANSACTION_ACCOUNT"),
        (6.17, "supply_chain", "節點 355／邊 432", "HAS_STAGE、\nHAS_SEGMENT、\nHAS_COMPANY"),
        (8.50, "risk_event", "節點 20,889／邊 68,271", "EVIDENCES、AFFECTS、\nEXPOSED_TO、HAS_\nFINANCIAL_ITEM"),
    ]
    # 白底 bbox：此標題橫跨四條下行箭頭，不加底色會被箭頭穿過。
    ax.text(5.0, 6.28, "③ 四類圖譜編譯器（各自的來源表與建模規則，見表 3-2）",
            ha="center", va="center", fontsize=8.2, fontweight="bold", color=INK,
            bbox=dict(fc="white", ec="none", pad=2.0), zorder=5)
    for x, name, cnt, types in cols:
        _stage(ax, x, 4.92, 2.24, 1.72, name, cnt + "\n" + types,
               hs=7.4, bs=5.6, ec=MUTED)
        _arrow(ax, (x, 6.55), (x, 5.82))

    # ── ④ 統一 schema ─────────────────────────────────────────
    _stage(ax, 5.0, 2.86, W, 1.45, "④ 統一 schema：單一 (source, type, target, 屬性) 長表",
           "四類編譯結果合併為全域節點與邊 DataFrame\n"
           "32,039 節點 ｜ 125,167 邊 ｜ 合併載入 0.41 秒\n"
           "每條邊保留來源檔與來源列序，答案因此可回溯至原始申報表",
           hs=8.2, bs=6.4, ec=GOOD)
    for x, *_ in cols:
        _arrow(ax, (x, 4.06), (x, 3.62))

    # ── ⑤ 下游 ────────────────────────────────────────────────
    _stage(ax, 3.05, 1.15, 5.2, 1.32, "⑤ 線上：軌道一・關係事實直查",
           "Layer 0 預編譯關係事實直答\n"
           "pandas 鍵值匹配，零 LLM、零圖遍歷\n"
           "約 12 毫秒",
           hs=8.0, bs=6.2, ec=GOOD, fc="#eef5f0")
    _stage(ax, 7.95, 1.15, 3.5, 1.32, "（選用）Neo4j 匯入",
           "neo4j_nodes.csv／\nneo4j_relationships.csv\n僅供視覺化，不在查詢路徑上",
           hs=8.0, bs=6.2, ec=MUTED, fc="#f7f7f7")
    _arrow(ax, (3.05, 2.13), (3.05, 1.84))
    _arrow(ax, (7.95, 2.13), (7.95, 1.84), dashed=True)

    ax.text(5.0, 0.20,
            "圖譜的效益全部來自本圖的離線段（實體解析 ＋ schema 統一）；"
            "線上不執行任何圖遍歷。",
            ha="center", va="center", fontsize=7.0, color=MUTED, style="italic")

    fig.savefig(OUT / "fig_graph_pipeline.png", dpi=300,
                bbox_inches="tight", pad_inches=0.06)
    plt.close(fig)


if __name__ == "__main__":
    fig_system_overview_minimal()            # 論文版：上下兩層、三欄對齊
    fig_system_overview_minimal(slim=True)   # 投影片版：只保留短直線與單一匯流排
    fig_fix_positions()
    fig_arch_change()
    fig_graph_pipeline()
    print("wrote", OUT / "fig_system_overview.png")
    print("wrote", OUT / "fig_system_overview_slide.png")
    print("wrote", OUT / "fig_fix_positions.png")
    print("wrote", OUT / "fig_arch_change.png")
    print("wrote", OUT / "fig_graph_pipeline.png")
    crop_screenshots()
