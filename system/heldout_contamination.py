#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Held-out 題庫污染偵測與敏感度分析（heldout_contamination.py）
================================================================
由 B1–B3 人工抽樣清單發現：部分**投資題**的「投資方／被投資公司／鑑別值」
被填入 CSV 欄位名（record_type / source_kind / row_text），而非真實實體名。
成因為 `build_heldout_twins.gen_investment` 以 `_gkg_resolve_node_name` 解析
節點名時，撈到圖譜編譯殘留的表頭列。

此類題目**在語意上不可回答**，但金標與系統輸出同源於該筆損壞資料，
兩者字串相同 → EM=1，形成**假性通過**：既拉高分子，也讓有效樣本數虛增。

本腳本：① 偵測受污染題目；② 在排除它們的乾淨子集上重算 EM 與
95% Clopper-Pearson 精確區間；③ 把結果附加到 results/heldout_vs_dev.md。

**不修改任何已凍結檔案**（改動會使 freeze_heldout_manifest.py --check 失效）。
修正應於第二份孿生集（新種子）為之。

用法：python3 heldout_contamination.py [--project DIR]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

def _arg(f,d):
    return sys.argv[sys.argv.index(f)+1] if f in sys.argv and sys.argv.index(f)+1<len(sys.argv) else d

ROOT = Path(_arg("--project", ".")).resolve()
REPORT = ROOT / "results" / "heldout_vs_dev.md"
OUT = ROOT / "results" / "heldout_contamination.json"

# 財報事實 CSV 的欄位名——出現在實體欄位即代表圖譜編譯殘留
COLUMN_TOKENS = re.compile(
    r"^(record_type|source_kind|row_text|row_json|include_reason|value_number|"
    r"value_type|fiscal_year|source_csv|stock_code|company_name|item_name|"
    r"column_header|value_raw|period|table_name|code|unit|year|quarter|"
    r"source_all_facts_csv|fact_text|row_index)$")

SETS = [("heldout_arch_100", "架構測試 100 題"),
        ("heldout_colloq_100", "口語化 100 題"),
        ("heldout_colloq_nat_100", "純口語自然 100 題"),
        ("heldout_graph_cap_30", "圖譜能力題 30 題"),
        ("heldout_graph_nat_30", "圖譜自然路由題 30 題")]


def contaminated(q: dict) -> list[str]:
    md = q.get("metadata", {}) or {}
    vals = [md.get("investor_name"), md.get("investee_name"), md.get("counterparty"),
            md.get("transacting_party"), md.get("main_business"),
            str(q.get("expected_answer", ""))]
    d = md.get("discriminator")
    if isinstance(d, dict):
        vals.append(str(d.get("value", "")))
    return sorted({str(v).strip() for v in vals
                   if v and COLUMN_TOKENS.match(str(v).strip())})


def clopper_pearson(k: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    from scipy.stats import beta
    lo = 0.0 if k == 0 else float(beta.ppf(alpha / 2, k, n - k + 1))
    hi = 1.0 if k == n else float(beta.ppf(1 - alpha / 2, k + 1, n - k))
    return lo * 100, hi * 100


def main() -> int:
    rows = []
    for tag, label in SETS:
        qp = ROOT / "questions" / "heldout" / f"{tag}.json"
        ep = ROOT / "results" / "heldout" / f"eval_{tag}.json"
        if not (qp.exists() and ep.exists()):
            continue
        qs = {str(q["id"]): q for q in json.loads(qp.read_text(encoding="utf-8"))}
        ev = json.loads(ep.read_text(encoding="utf-8"))
        bad_ids, n, k, cn, ck = [], 0, 0, 0, 0
        for r in ev["results"]:
            q = qs.get(str(r["id"]), {})
            e = int(bool((r.get("scores") or {}).get("exact_match")))
            n += 1; k += e
            tok = contaminated(q)
            if tok:
                bad_ids.append({"id": r["id"], "tokens": tok, "em": e})
            else:
                cn += 1; ck += e
        lo, hi = clopper_pearson(ck, cn) if cn else (0.0, 0.0)
        rows.append({"tag": tag, "label": label, "n": n, "em": k,
                     "em_pct": round(k / n * 100, 1),
                     "contaminated": len(bad_ids), "contaminated_ids": bad_ids,
                     "clean_n": cn, "clean_em": ck,
                     "clean_em_pct": round(ck / cn * 100, 1) if cn else None,
                     "clean_ci95": [round(lo, 1), round(hi, 1)]})

    # dev 題庫是否也有同樣問題
    dev_hits = {}
    for p in sorted((ROOT / "questions").glob("*.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            continue
        ids = [q.get("id") for q in data if contaminated(q)]
        if ids:
            dev_hits[p.name] = ids

    OUT.write_text(json.dumps({"heldout": rows, "dev_datasets": dev_hits},
                              ensure_ascii=False, indent=2), encoding="utf-8")

    L = ["", "---", "",
         "## 限制：題庫污染與假性通過（由 heldout_contamination.py 產生）", "",
         "B1–B3 人工抽樣核對發現，部分**投資題**的「投資方／被投資公司／鑑別值」",
         "被填入 CSV 欄位名（`record_type` / `source_kind` / `row_text`）而非真實實體，",
         "成因為孿生集生成器解析圖譜節點名時撈到編譯殘留的表頭列。",
         "此類題目語意上不可回答，但金標與系統輸出同源於該筆損壞資料，字串相同 → **EM=1**，",
         "形成**假性通過**：既拉高分子，也使有效樣本數虛增。", "",
         "| 資料集 | 原始 EM | 受污染題數 | 乾淨子集 EM | 95% CI（Clopper-Pearson） |",
         "|---|---:|---:|---:|---|"]
    for r in rows:
        L.append(f"| {r['label']} | {r['em']}/{r['n']} = {r['em_pct']}% | "
                 f"{r['contaminated']} | {r['clean_em']}/{r['clean_n']} = "
                 f"{r['clean_em_pct']}% | [{r['clean_ci95'][0]}, {r['clean_ci95'][1]}] |")
    L += ["",
          "**判讀**：乾淨子集的 EM 與原始值幾乎相同，故**結論方向不變**；",
          "但圖譜兩組各有 5/30（16.7%）題目無效，有效樣本數下降使信賴區間變寬，",
          "因此不應以「30/30 滿分」作為圖譜引擎能力的陳述，應改述為",
          "「25 題有效題全數正確，95% CI [86.3, 100.0]」。", ""]
    if dev_hits:
        L += ["**dev 題庫亦受影響**（同一生成器缺陷，非本次新增）：", ""]
        for k2, v in dev_hits.items():
            L.append(f"- `{k2}`：{len(v)} 題（{', '.join(map(str, v[:5]))}）")
        L.append("")
    L += ["**處置（依 manifest 禁止調參條款）**：不修改已凍結之孿生集與系統檔，",
          "以保全 `freeze_heldout_manifest.py --check` 的稽核效力。修正應於",
          "第二份孿生集（新種子）為之：`gen_investment` 須在解析節點名後排除",
          "欄位名 token，並於 `verify_heldout.py` 增設「實體名不得為語料欄位名」檢查。", ""]

    with REPORT.open("a", encoding="utf-8") as f:
        f.write("\n".join(L))
    print("\n".join(L[3:]))
    print(f"\n→ 已附加至 {REPORT}")
    print(f"→ {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
