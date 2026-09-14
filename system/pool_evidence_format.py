#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
證據格式消融：跨題組彙整與統計檢定
==================================
單一題組 n=60 的檢定力不足以判定 A 與 B 的差異（4 題翻轉、0 題退步，
McNemar p=0.125）。本腳本把多個題組彙整後重算，並明確報告：

  · 各組 EM 與 95% Clopper-Pearson 精確區間
  · A vs B、B vs C 之 McNemar 精確檢定（配對設計，優於獨立區間重疊判讀）
  · 逐題翻轉方向（由錯轉對／由對轉錯），用以判斷效果是否單調

題組選擇的原則：**以 held-out 集做獨立重複**（預註冊、從未用於調參），
而非把同一批題目加大——後者只會放大同一份樣本的特性，不構成獨立證據。

    python3 pool_evidence_format.py [--out results/evidence_format_pooled]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from scipy import stats

ROOT = Path(__file__).resolve().parent
GROUPS = ("A_raw_markdown", "B_flattened_kv", "C_fact_lookup")
LABELS = {
    "A_raw_markdown": "A：原始 RAG（Markdown 表格）",
    "B_flattened_kv": "B：扁平化 RAG（同一批檢索結果轉鍵值列）",
    "C_fact_lookup":  "C：Fact 直查（不經 LLM）",
}
SOURCES = [
    ("dev：架構測試 100 之數值題", "results/evidence_format_ablation.json"),
    ("held-out：架構 100 之數值題", "results/evidence_format_ablation_ho_arch.json"),
    ("held-out：口語 100 之數值題", "results/evidence_format_ablation_ho_colloq.json"),
]


def cp_interval(k: int, n: int) -> tuple[float, float]:
    """95% Clopper-Pearson 精確區間（百分比）。"""
    lo = stats.beta.ppf(0.025, k, n - k + 1) if k else 0.0
    hi = stats.beta.ppf(0.975, k + 1, n - k) if k < n else 1.0
    return lo * 100, hi * 100


def em(row: dict, g: str) -> bool:
    return bool(row["groups"][g]["scores"]["exact_match"])


def mcnemar(rows: list[dict], g1: str, g2: str) -> dict:
    """b = 只有 g1 對，c = 只有 g2 對；雙尾精確檢定。"""
    b = sum(1 for r in rows if em(r, g1) and not em(r, g2))
    c = sum(1 for r in rows if not em(r, g1) and em(r, g2))
    p = stats.binomtest(b, b + c, 0.5).pvalue if (b + c) else 1.0
    return {"b": b, "c": c, "n_discordant": b + c, "p_value": round(float(p), 6),
            "significant": bool(p < 0.05)}


REFUSAL_STATUS = {"not_found", "missing_value", "no_evidence", "llm_error",
                  "schema_invalid"}


def _norm(s: str) -> str:
    """比對用正規化：全形空白、空白與大小寫皆不計。"""
    return re.sub(r"\s+", "", str(s or "")).lower()


def localized(row: dict, g: str) -> bool | None:
    """
    欄位定位率：系統實際取值所依據的（科目, 期間欄）是否與金標一致。

    · A／B：取受限解碼信封自報的 item / period（模型宣稱命中的欄位）
    · C　：取唯一性判定時實際命中列的 item_name / column_header

    兩者皆以「金標與自報字串互為包含」判定（模型常只回報科目全名的一部分）。
    金標缺欄位資訊時回傳 None，該題不計入分母——寧可少算，不可用寬鬆判準灌水。
    """
    gi, gc = _norm(row.get("gold_item")), _norm(row.get("gold_column"))
    if not gi or not gc:
        return None
    d = row["groups"][g]
    ri, rc = _norm(d.get("reported_item")), _norm(d.get("reported_period"))
    if not ri and not rc:
        return False
    ok_i = bool(ri) and (ri in gi or gi in ri)
    ok_c = bool(rc) and (rc in gc or gc in rc)
    return ok_i and ok_c


def refused(row: dict, g: str) -> bool:
    d = row["groups"][g]
    return (str(d.get("status", "")) in REFUSAL_STATUS
            or "找不到相關資料" in str(d.get("answer", "")))


def ambiguous(row: dict, g: str) -> bool:
    d = row["groups"][g]
    return bool(d.get("ambiguous")) or str(d.get("status", "")) == "ambiguous"


def summarize(rows: list[dict]) -> dict:
    n = len(rows)
    out = {"n": n, "groups": {}}
    for g in GROUPS:
        k = sum(1 for r in rows if em(r, g))
        lo, hi = cp_interval(k, n)
        loc = [localized(r, g) for r in rows]
        loc_d = [x for x in loc if x is not None]
        out["groups"][g] = {
            "exact": k, "n": n, "em": round(k / n, 4) if n else 0.0,
            "ci95": [round(lo, 1), round(hi, 1)],
            "localization": {
                "hit": sum(1 for x in loc_d if x), "n": len(loc_d),
                "rate": round(sum(1 for x in loc_d if x) / len(loc_d), 4) if loc_d else None,
            },
            "ambiguity_rate": round(sum(1 for r in rows if ambiguous(r, g)) / n, 4) if n else 0.0,
            "refusal_rate": round(sum(1 for r in rows if refused(r, g)) / n, 4) if n else 0.0,
            # 失效兩段分解：先看有沒有定位到正確的（科目, 期間欄），再看定位對之後
            # 有沒有抄對值。兩者是不同的失效模式，混在 EM 裡看不出來。
            "failure_decomposition": {
                "loc_fail": sum(1 for r in rows if localized(r, g) is False),
                "loc_ok_value_fail": sum(1 for r in rows
                                         if localized(r, g) and not em(r, g)),
                "loc_ok": sum(1 for r in rows if localized(r, g)),
                "value_fail_rate_given_loc": (
                    round(sum(1 for r in rows if localized(r, g) and not em(r, g))
                          / sum(1 for r in rows if localized(r, g)), 4)
                    if sum(1 for r in rows if localized(r, g)) else None),
            },
        }
    out["mcnemar"] = {
        "A_vs_B": mcnemar(rows, "A_raw_markdown", "B_flattened_kv"),
        "B_vs_C": mcnemar(rows, "B_flattened_kv", "C_fact_lookup"),
        "A_vs_C": mcnemar(rows, "A_raw_markdown", "C_fact_lookup"),
    }
    return out


def main() -> int:
    out_stem = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv \
        else ROOT / "results" / "evidence_format_pooled"

    per: list[tuple[str, dict, list[dict]]] = []
    pooled: list[dict] = []
    for label, rel in SOURCES:
        p = ROOT / rel
        if not p.exists():
            print(f"  ⚠ 略過（尚未產生）：{rel}")
            continue
        rows = json.loads(p.read_text(encoding="utf-8"))["results"]
        per.append((label, summarize(rows), rows))
        pooled.extend(rows)
        print(f"  ✓ {label}：n={len(rows)}")

    if not pooled:
        print("✗ 沒有任何題組結果可彙整")
        return 2
    total = summarize(pooled)

    L = ["# 證據格式消融：跨題組彙整與統計檢定\n",
         "> held-out 兩組為預註冊集、從未用於調參，構成對 dev 結果的獨立重複。\n",
         "## 一、逐題組\n",
         "| 題組 | n | A EM（95% CI） | B EM（95% CI） | C EM（95% CI） | A vs B（McNemar） |",
         "|---|---:|---:|---:|---:|---|"]
    for label, s, _ in per:
        g = s["groups"]
        m = s["mcnemar"]["A_vs_B"]
        cells = [f"{g[k]['em']:.1%}〔{g[k]['ci95'][0]}, {g[k]['ci95'][1]}〕" for k in GROUPS]
        L.append(f"| {label} | {s['n']} | " + " | ".join(cells) +
                 f" | b={m['b']} c={m['c']}, p={m['p_value']:.4f}"
                 f"{'（顯著）' if m['significant'] else '（未達顯著）'} |")

    g, m = total["groups"], total["mcnemar"]
    L += ["", "## 二、彙整（四項指標）\n",
          f"合計 **n={total['n']}**\n",
          "| 組別 | EM | 95% CI | 欄位定位率 | 候選歧義率 | 拒答率 |",
          "|---|---:|---|---:|---:|---:|"]
    for k in GROUPS:
        q = g[k]
        lc = q["localization"]
        lcs = f"{lc['rate']:.1%}（{lc['hit']}/{lc['n']}）" if lc["rate"] is not None else "—"
        L.append(f"| {LABELS[k]} | {q['em']:.1%}（{q['exact']}/{q['n']}） |"
                 f" 〔{q['ci95'][0]}, {q['ci95'][1]}〕 | {lcs} |"
                 f" {q['ambiguity_rate']:.1%} | {q['refusal_rate']:.1%} |")
    L += ["", "## 三、失效之兩段分解\n",
          "| 組別 | 定位失敗 | 定位成功 | 其中取值仍失敗 | 定位成功下的取值失敗率 |",
          "|---|---:|---:|---:|---:|"]
    for k in GROUPS:
        d = g[k]["failure_decomposition"]
        rate = f"{d['value_fail_rate_given_loc']:.1%}" if d["value_fail_rate_given_loc"] is not None else "—"
        L.append(f"| {LABELS[k]} | {d['loc_fail']} | {d['loc_ok']} | "
                 f"{d['loc_ok_value_fail']} | {rate} |")
    L += ["", "指標定義：**欄位定位率**＝實際取值所依據的（科目, 期間欄）與金標一致之比率"
          "（A／B 取受限解碼信封之自報欄位，C 取唯一性判定時命中列之欄位）；"
          "**候選歧義率**＝候選集合相異值 >1（C）或信封回報 ambiguous（A／B）之比率；"
          "**拒答率**＝回報 not_found／missing_value／無證據或輸出拒答短語之比率。"]
    L += ["", "### McNemar 配對精確檢定\n",
          "| 對照 | 只有前者對 | 只有後者對 | p | 判定 |", "|---|---:|---:|---:|---|"]
    for key, name in (("A_vs_B", "A vs B（證據格式）"),
                      ("B_vs_C", "B vs C（模型讀 vs 程式取值）"),
                      ("A_vs_C", "A vs C")):
        x = m[key]
        L.append(f"| {name} | {x['b']} | {x['c']} | {x['p_value']:.4f} | "
                 f"{'**顯著**' if x['significant'] else '未達顯著'} |")

    ab, bc = m["A_vs_B"], m["B_vs_C"]
    mono = "完全單調" if ab["b"] == 0 else "不完全單調"
    conj = "且" if ab["significant"] else "但"
    verdict = (f"達統計顯著（p={ab['p_value']:.4f}）" if ab["significant"]
               else f"**未達統計顯著**（p={ab['p_value']:.4f}）")
    L += ["", "### 讀法\n",
          f"- A→B 的翻轉為 **{ab['c']} 題由錯轉對、{ab['b']} 題由對轉錯**："
          f"方向{mono}，{conj}於 n={total['n']} 下{verdict}。",
          f"- B→C 的差距為 {bc['c']} 題，"
          f"{'達統計顯著' if bc['significant'] else '未達顯著'}"
          f"（p={bc['p_value']:.4g}），量級遠大於證據格式所能解釋的範圍。"]

    Path(f"{out_stem}.json").write_text(
        json.dumps({"per_dataset": [{"label": l, **s} for l, s, _ in per],
                    "pooled": total}, ensure_ascii=False, indent=2), encoding="utf-8")
    Path(f"{out_stem}.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n" + "\n".join(L))
    print(f"\n輸出：{out_stem}.json / .md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
