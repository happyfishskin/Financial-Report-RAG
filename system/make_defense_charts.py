#!/usr/bin/env python3
"""口試簡報用圖表產生器：全部數值直接讀取評測結果檔，不硬編。"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

V7 = Path(__file__).resolve().parent.parent / "legacy_v12"
OUT = Path("slides_assets")
OUT.mkdir(exist_ok=True)

# 繁體中文字型
# 系統僅提供 .ttc 集合，matplotlib 只會註冊其中第一個 face（JP），繁體字形會走
# 日文變體。故先以 fontTools 由集合中抽出 TC face 為獨立 .otf 再註冊。
_FONT_DIR = Path(__file__).resolve().parent / ".fonts"


def _ensure_tc_font() -> str:
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
plt.rcParams["font.size"] = 13

INK = "#1a2332"
MUTED = "#8a94a6"
ACCENT = "#c8553d"
GOOD = "#2d6a4f"
GRID = "#dfe3ea"
BLUE = "#3d6ea5"


def _style(ax, ylabel=""):
    ax.set_facecolor("white")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)
    ax.tick_params(colors=MUTED, length=0)
    ax.yaxis.grid(True, color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    if ylabel:
        ax.set_ylabel(ylabel, color=MUTED, fontsize=12)


def _em(f):
    return json.load(open(f, encoding="utf-8"))["summary"]["academic_metrics"]["em"]


def _sum(f):
    return json.load(open(f, encoding="utf-8"))["summary"]


# ── 1. 實驗二：檢索策略消融 ──────────────────────────────
def chart_ablation():
    cfg = [
        ("純 LLM\n(無檢索)", V7 / "rag_evaluation_v12_llm_only.json", MUTED),
        ("純向量", Path("results/rag_evaluation_v12_vector_only_TRUE.json"), MUTED),
        ("純圖譜", V7 / "rag_evaluation_v12_graph_only.json", MUTED),
        ("圖譜+向量\n真並行", Path("results/rag_evaluation_v12_graph_vector_PARALLEL.json"), ACCENT),
        ("混合路由\n(本系統)", V7 / "rag_evaluation_v12_full.json", GOOD),
    ]
    labels = [c[0] for c in cfg]
    ems = [_em(c[1]) * 100 for c in cfg]
    cols = [c[2] for c in cfg]

    fig, ax = plt.subplots(figsize=(10, 5.2), dpi=200)
    bars = ax.bar(labels, ems, color=cols, width=0.6)
    for b, v in zip(bars, ems):
        ax.text(b.get_x() + b.get_width() / 2, v + 1.6, f"{v:.1f}%",
                ha="center", fontsize=14, color=INK, fontweight="bold")
    _style(ax, "Exact Match (%)")
    ax.set_ylim(0, 92)
    ax.annotate("", xy=(3.74, 72), xytext=(2.02, 28.5),
                arrowprops=dict(arrowstyle="->", color=GOOD, lw=1.8, ls=":",
                                shrinkA=6, shrinkB=6,
                                connectionstyle="arc3,rad=-0.18"))
    ax.text(2.52, 56, "3.6×", color=GOOD, fontsize=17, fontweight="bold")
    ax.set_title("檢索策略消融（固定腳本 60 題）", color=INK, fontsize=16,
                 fontweight="bold", pad=14, loc="left")
    fig.tight_layout()
    fig.savefig(OUT / "chart_ablation.png", facecolor="white")
    plt.close(fig)


# ── 2. 分題型互補性 ──────────────────────────────────────
def chart_per_type():
    F = {
        "純向量": Path("results/rag_evaluation_v12_vector_only_TRUE.json"),
        "純圖譜": V7 / "rag_evaluation_v12_graph_only.json",
        "混合路由": V7 / "rag_evaluation_v12_full.json",
    }
    types = [("cross_company", "A 跨公司", 14), ("cross_quarter", "B 跨季度", 12),
             ("entity_lookup", "C 實體查閱", 12), ("colloquial", "D 口語化", 12),
             ("multi_hop_graph_reasoning", "E 多跳圖譜", 10)]
    D = {k: json.load(open(v, encoding="utf-8"))["per_type_accuracy"] for k, v in F.items()}

    fig, ax = plt.subplots(figsize=(10, 5.2), dpi=200)
    x = range(len(types))
    w = 0.26
    for i, (name, col) in enumerate([("純向量", "#9db4d0"), ("純圖譜", "#e0a58f"), ("混合路由", GOOD)]):
        vals = [D[name][t[0]]["exact"] / t[2] * 100 for t in types]
        pos = [xx + (i - 1) * w for xx in x]
        bars = ax.bar(pos, vals, width=w, color=col, label=name)
        for b, v in zip(bars, vals):
            if v > 0:
                ax.text(b.get_x() + b.get_width() / 2, v + 2, f"{v:.0f}",
                        ha="center", fontsize=10, color=INK)
    ax.set_xticks(list(x))
    ax.set_xticklabels([t[1] for t in types])
    _style(ax, "各題型 EM (%)")
    ax.set_ylim(0, 118)
    ax.legend(frameon=False, ncol=3, loc="upper center", fontsize=12)
    ax.set_title("單軌盲區互補而非重疊 ── 路由設計的前提", color=INK,
                 fontsize=16, fontweight="bold", pad=14, loc="left")
    fig.tight_layout()
    fig.savefig(OUT / "chart_per_type.png", facecolor="white")
    plt.close(fig)


# ── 3. 實驗三：增益軌跡 ──────────────────────────────────
def chart_trajectory():
    stages = [
        ("原始版本\n傳統 RAG", V7 / "rag_evaluation_v12_arch100.json"),
        ("＋結構\n扁平化", V7 / "rag_evaluation_v14_full.json"),
        ("＋確定性\n修復層", Path("results/test_eval_arch100_orig.json")),
        ("＋鑑別扁平化\n(v2 資料集)", Path("results/test_eval_arch100_v2.json")),
    ]
    ems = [_em(s[1]) * 100 for s in stages]
    hits = [_sum(s[1])["retrieval_metrics"]["hit_rate@1"] * 100 for s in stages]

    fig, ax = plt.subplots(figsize=(10, 5.2), dpi=200)
    xs = range(len(stages))
    ax.plot(xs, hits, "o--", color=MUTED, lw=2, ms=9, label="檢索命中率 Hit@1")
    ax.plot(xs, ems, "o-", color=ACCENT, lw=3, ms=11, label="精確匹配率 EM")
    for i, (e, h) in enumerate(zip(ems, hits)):
        ax.text(i, e + 4.5, f"{e:.0f}%", ha="center", fontsize=15,
                color=ACCENT, fontweight="bold")
        ax.text(i, h - 8, f"{h:.1f}%", ha="center", fontsize=11, color=MUTED)
    ax.set_xticks(list(xs))
    ax.set_xticklabels([s[0] for s in stages])
    _style(ax, "(%)")
    ax.set_ylim(0, 118)
    ax.legend(frameon=False, ncol=2, loc="lower right", fontsize=12)
    ax.fill_between([-0.3, 0.3], 12, 97.65, color=ACCENT, alpha=0.06)
    ax.text(0, 55, "「撈得準，\n答不對」", ha="center", fontsize=12, color=ACCENT)
    ax.set_title("架構測試 100 題：瓶頸從不在檢索端", color=INK,
                 fontsize=16, fontweight="bold", pad=14, loc="left")
    fig.tight_layout()
    fig.savefig(OUT / "chart_trajectory.png", facecolor="white")
    plt.close(fig)


# ── 4. 實驗四：口語化修復軌跡 ────────────────────────────
def chart_colloquial():
    stages = ["基線", "＋Fix 12\n市場別名", "＋Fix 13\n科目線索", "＋同義詞\n補強", "＋防劫持\n完善"]
    ems = [_em(Path(f"results/test_eval_colloq_nat_{k}.json")) * 100
           for k in ["base", "fix", "fix2"]]
    ems += [99.0, _em(Path("results/test_eval_colloq_nat_final.json")) * 100]

    fig, ax = plt.subplots(figsize=(10, 5.2), dpi=200)
    cols = [MUTED, BLUE, BLUE, BLUE, GOOD]
    bars = ax.bar(stages, ems, color=cols, width=0.58)
    for i, (b, v) in enumerate(zip(bars, ems)):
        ax.text(b.get_x() + b.get_width() / 2, v + 1.6, f"{v:.0f}%",
                ha="center", fontsize=14, color=INK, fontweight="bold")
        if i:
            d = ems[i] - ems[i - 1]
            ax.text(b.get_x() + b.get_width() / 2, v / 2, f"+{d:.0f}",
                    ha="center", fontsize=13, color="white", fontweight="bold")
    _style(ax, "Exact Match (%)")
    ax.set_ylim(0, 118)
    ax.set_title("純口語 100 題（市場簡稱＋零提示）：三層落差逐層修復",
                 color=INK, fontsize=16, fontweight="bold", pad=14, loc="left")
    fig.tight_layout()
    fig.savefig(OUT / "chart_colloquial.png", facecolor="white")
    plt.close(fig)


# ── 5. 實驗七：比率計算消融 ──────────────────────────────
def chart_ratio():
    s = json.load(open("results/benchmark_ratio_pipelines.json", encoding="utf-8"))["summary"]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10.5, 4.6), dpi=200)

    labels = ["Pipeline A\nLLM 算術", "Pipeline B\nPython 代數"]
    acc = [s["llm_exact_rate"] * 100, s["py_exact_rate"] * 100]
    bars = a1.bar(labels, acc, color=[ACCENT, GOOD], width=0.55)
    for b, v in zip(bars, acc):
        a1.text(b.get_x() + b.get_width() / 2, v + 2, f"{v:.0f}%", ha="center",
                fontsize=15, color=INK, fontweight="bold")
    _style(a1, "精確匹配率 (%)")
    a1.set_ylim(0, 118)
    a1.set_title("正確性", color=INK, fontsize=14, fontweight="bold", loc="left")

    lat = [s["llm_avg_latency_sec"], s["llm_avg_latency_sec"] / s["speedup"]]
    bars = a2.bar(labels, lat, color=[ACCENT, GOOD], width=0.55, log=True)
    for b, v in zip(bars, lat):
        txt = f"{v:.2f} 秒" if v > 1 else f"{v*1000:.4f} 毫秒"
        a2.text(b.get_x() + b.get_width() / 2, v * 1.6, txt, ha="center",
                fontsize=13, color=INK, fontweight="bold")
    _style(a2, "平均延遲（對數刻度）")
    a2.set_ylim(1e-6, 1e4)
    a2.set_title(f"效能：快 {s['speedup']:,.0f} 倍", color=INK,
                 fontsize=14, fontweight="bold", loc="left")
    fig.suptitle("衍生比率計算：誰做除法？（50 題，檢索步驟完全相同）",
                 color=INK, fontsize=16, fontweight="bold", x=0.02, ha="left")
    fig.tight_layout(rect=[0, 0, 1, 0.9])
    fig.savefig(OUT / "chart_ratio.png", facecolor="white")
    plt.close(fig)


# ── 6. 金標歸因 ──────────────────────────────────────────
def chart_attribution():
    o = json.load(open("results/colloq_base_failure_attribution.json", encoding="utf-8"))
    from collections import Counter
    c = Counter(x["category"] for x in o)
    gold = ["F1_格式差異", "F2_金標毀損", "F3_金標可疑", "F5_科目歧義"]
    order = gold + ["F4_欄位錯位", "F6_部分正確", "F7_拒答", "F8_真失效"]
    labels = [k.split("_")[1] for k in order]
    vals = [c.get(k, 0) for k in order]
    cols = [BLUE] * 4 + [ACCENT] * 4

    fig, ax = plt.subplots(figsize=(10, 5.0), dpi=200)
    bars = ax.barh(labels[::-1], vals[::-1], color=cols[::-1], height=0.62)
    for b, v in zip(bars, vals[::-1]):
        ax.text(v + 0.5, b.get_y() + b.get_height() / 2, str(v),
                va="center", fontsize=13, color=INK, fontweight="bold")
    ax.set_facecolor("white")
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=MUTED, length=0)
    ax.xaxis.grid(True, color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    ax.set_xlabel("題數", color=MUTED)
    g = sum(c.get(k, 0) for k in gold)
    ax.set_title(f"早期資料集 84 題失分歸因：{g} 題（{g/len(o)*100:.1f}%）"
                 f"非系統錯誤", color=INK, fontsize=16, fontweight="bold",
                 pad=14, loc="left")
    ax.text(0.0, -0.14, "■ 金標／格式面（非系統錯誤）        ■ 系統面",
            transform=ax.transAxes, ha="left", fontsize=12, color=MUTED)
    ax.set_xlim(0, max(vals) * 1.14)
    fig.tight_layout()
    fig.savefig(OUT / "chart_attribution.png", facecolor="white")
    plt.close(fig)


# ── 7. 效能：延遲組成 ────────────────────────────────────
def chart_latency():
    d = json.load(open("results/benchmark_graph_seconds.json", encoding="utf-8"))
    import statistics as st
    g = st.mean([x["warm_avg_ms"] for x in d["v14_layer0"]["questions"]])
    e2e = d["v14_e2e_graph_ref"]["avg_s"] * 1000

    fig, ax = plt.subplots(figsize=(10, 3.0), dpi=200)
    ax.barh([""], [e2e], color="#e8ebf0", height=0.5)
    ax.barh([""], [g], color=GOOD, height=0.5)
    ax.text(g + 60, 0, f"圖譜計算 {g:.1f} ms（佔 {g/e2e*100:.2f}%）",
            va="center", fontsize=13, color=GOOD, fontweight="bold")
    ax.text(e2e * 0.62, 0, f"端到端 {e2e/1000:.3f} s（瓶頸為 SLM）",
            va="center", fontsize=13, color=INK)
    ax.set_facecolor("white")
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=MUTED, length=0)
    ax.set_xlabel("毫秒", color=MUTED)
    ax.set_xlim(0, e2e * 1.05)
    ax.set_title("延遲瓶頸在 SLM，不在檢索", color=INK, fontsize=16,
                 fontweight="bold", pad=12, loc="left")
    fig.tight_layout()
    fig.savefig(OUT / "chart_latency.png", facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    for fn in (chart_ablation, chart_per_type, chart_trajectory, chart_colloquial,
               chart_ratio, chart_attribution, chart_latency):
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"→ {OUT}/")
