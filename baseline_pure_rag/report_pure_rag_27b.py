#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
version10 §9 結果報告：把 27B 純 RAG 的實測結果放進既有對照表
============================================================
輸出兩張表：

表一（規格書 §9 格式）三系統並列：
    既有純向量 RAG（Qwen3-4B）｜27B 純 RAG（本實驗）｜確定性 Fact 直查

表二 逐題配對比較：**同一批 130 題 held-out 數值題**上，
    既有受控消融 A 組（原始 Markdown ＋ 4B ＋ SLM Router ＋ metadata 過濾）
    vs 本實驗（原始 Markdown ＋ 27B ＋ 無路由、無過濾、全庫檢索）
    附 McNemar 精確檢定（配對二項）。

    python3 report_pure_rag_27b.py [--main results/pure_rag_27b_main.json]
"""
from __future__ import annotations

import argparse
import json
from math import comb
from pathlib import Path

ROOT = Path(__file__).resolve().parent
V8   = ROOT.parent / "system"


def load(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def mcnemar(b: int, c: int) -> float:
    """雙尾精確檢定；b＝只有前者對，c＝只有後者對。"""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(comb(n, i) for i in range(k + 1)) / (2 ** n)
    return round(min(1.0, 2 * tail), 6)


def pct(x) -> str:
    return "—" if x is None else f"{x:.1%}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--main", default=str(ROOT / "results" / "pure_rag_27b_main.json"))
    ap.add_argument("--out",  default=str(ROOT / "results" / "pure_rag_27b_report"))
    args = ap.parse_args()

    exp = load(Path(args.main))
    sec = next(s for s in exp["sections"] if s["tag"] == "MAIN")
    cur = sec["overall"]
    env = exp["environment"]

    # ── 既有凍結對照 ────────────────────────────────────────────
    vec = load(V8 / "results" / "rag_evaluation_v12_vector_only_TRUE.json")["summary"]
    vec_row = {
        "em": vec["rates"]["exact_match"],
        "hit5": vec["retrieval_metrics"]["hit_rate@5"],
        "refusal": round(vec["academic_metrics"]["refusal_count"] / vec["total"], 4),
        "n": vec["total"],
    }
    pooled = load(V8 / "results" / "evidence_format_pooled.json")["pooled"]
    fact_row = {
        "em": pooled["groups"]["C_fact_lookup"]["em"],
        "refusal": pooled["groups"]["C_fact_lookup"]["refusal_rate"],
        "n": pooled["n"],
    }

    md = ["# version10 §9 結果報告：27B 純向量 RAG\n"]
    md.append(f"生成模型 `{env['model_file']}`（{env['model_size_gb']} GB，"
              f"SHA256 `{env['model_sha256'][:16] or 'n/a'}…`）｜"
              f"{env['backend']}｜{env['gpu']}｜VRAM 峰值 {env['vram_peak_mib']:,} MiB\n")

    md += ["\n## 表一　系統對照（規格書 §9 格式）\n",
           "| 系統 | 路由／規則 | 證據形式 | 生成模型 | n | EM | Hit@5 | 拒答率 | 平均延遲 |",
           "|---|---|---|---|---:|---:|---:|---:|---:|",
           f"| 純向量 RAG（既有） | 有既有設定 | Markdown | Qwen3-4B | {vec_row['n']} | "
           f"{pct(vec_row['em'])} | {pct(vec_row['hit5'])} | {pct(vec_row['refusal'])} | 0.91s |",
           f"| **27B 純 RAG（本實驗）** | **無** | Top-5 Markdown（全庫、無過濾） | "
           f"Qwen3.8-27B IQ3_XXS | {cur['n']} | **{pct(cur['em'])}** | "
           f"{pct(cur['hit5_strict'])} | {pct(cur['refusal_rate'])} | "
           f"{cur['avg_latency_sec']:.1f}s |",
           f"| 確定性 Fact 直查 | Python 定位 | Fact | 不生成數值 | {fact_row['n']} | "
           f"{pct(fact_row['em'])} | — | {pct(fact_row['refusal'])} | — |",
           "\n註：三列的題組不同（既有純向量為 dev 架構 60 題、Fact 直查為 pooled 190 題），"
           "跨列僅供量級參照；嚴格的同題比較見表二。\n"]

    md += [f"\n每題平均輸入 {cur['avg_prompt_tokens']:.0f} tokens、"
           f"輸出 {cur['avg_completion_tokens']:.0f} tokens；"
           f"數值一致率 {pct(cur['numeric_rate'])}；"
           f"Hit@5（寬鬆，任一金標來源進 Top-5）{pct(cur['hit5_lenient'])}。\n"]

    # ── 表二：同 130 題逐題配對 ─────────────────────────────────
    frozen: dict[str, bool] = {}
    for f in ("evidence_format_ablation_ho_arch.json",
              "evidence_format_ablation_ho_colloq.json"):
        for r in load(V8 / "results" / f)["results"]:
            frozen[r["id"]] = bool(r["groups"]["A_raw_markdown"]["scores"]["exact_match"])

    rows = [r for r in exp["results"] if r["dataset"].startswith("MAIN")]
    paired = [(frozen[r["id"]], bool(r["scores"]["exact_match"]))
              for r in rows if r["id"] in frozen]
    b = sum(1 for a, n in paired if a and not n)      # 只有 4B 對
    c = sum(1 for a, n in paired if n and not a)      # 只有 27B 對
    both = sum(1 for a, n in paired if a and n)
    neither = sum(1 for a, n in paired if not a and not n)
    p = mcnemar(b, c)

    md += ["\n## 表二　同一批 130 題 held-out 數值題之逐題配對\n",
           "| 系統 | 路由／過濾 | 生成模型 | EM |",
           "|---|---|---|---:|",
           f"| 既有受控消融 A 組 | SLM Router ＋ 公司／期別 metadata 硬過濾 | Qwen3-4B | "
           f"{(both + b) / len(paired):.1%}（{both + b}/{len(paired)}） |",
           f"| 本實驗 27B 純 RAG | 無 | Qwen3.8-27B IQ3_XXS | "
           f"{(both + c) / len(paired):.1%}（{both + c}/{len(paired)}） |",
           "",
           f"配對列聯表：兩者皆對 {both}｜僅 4B＋路由對 {b}｜僅 27B 純 RAG 對 {c}｜"
           f"兩者皆錯 {neither}",
           f"McNemar 精確檢定 p = {p}"
           f"（{'顯著' if p < 0.05 else '不顯著'}，α=0.05）\n",
           "此比較有兩個變因同時變動（模型大小、以及是否使用路由與 metadata 過濾），"
           "故只能回答「換上 27B 並拿掉全部規則後，整體是否還站得住」，"
           "不能單獨歸因於模型大小。\n"]

    md += ["\n## 結論界線\n", exp["caveat"], ""]

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    Path(f"{out}.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    Path(f"{out}.json").write_text(json.dumps({
        "table1": {"pure_vector_existing": vec_row, "pure_rag_27b": cur,
                   "fact_lookup": fact_row},
        "table2": {"n": len(paired), "both": both, "only_4b_router": b,
                   "only_27b_pure": c, "neither": neither, "mcnemar_p": p},
        "environment": env,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n".join(md))
    print(f"\n輸出：{out}.md / {out}.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
