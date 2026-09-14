#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
跨產業準確率：四臂對照彙整
==========================
把四次實測合併成一份可引用的結果，並把結論的推導寫清楚。

  臂  資料              欄名格式          隔離的變因
  A   非半導體三家      巢狀（現行解析器）  —（原始提問）
  B   半導體三家        巢狀（現行解析器）  產業（與 A 只差產業）
  C   半導體三家        扁平（原始語料）    欄名格式（與 B 只差格式）
  D   非半導體三家      扁平（正規化後）    產業（與 C 只差產業）

A≡B 且 C≡D → 產業無效應；B vs C 差 92 個百分點 → 欄名格式才是變因。

    python3 report_cross_industry_em.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
R = ROOT / "results"
OUT = R / "cross_industry_em_summary"

ARMS = [
    ("A", "跨產業（非半導體三家）", "巢狀（現行解析器）", "cross_industry_em.json",
     "cross_industry_gold_verification.json"),
    ("B", "半導體對照（三家）", "巢狀（現行解析器）", "semi_control_em.json",
     "semi_control_gold_verification.json"),
    ("C", "半導體對照（三家）", "扁平（原始語料）", "semi_oldparse_em.json",
     "semi_oldparse_gold_verification.json"),
    ("D", "跨產業（非半導體三家）", "扁平（欄名正規化後）", "cross_industry_flat_em.json",
     "cross_industry_flat_gold_verification.json"),
]


def main() -> int:
    arms = []
    for tag, data, fmt, em_f, ver_f in ARMS:
        d = json.loads((R / em_f).read_text(encoding="utf-8"))
        v = json.loads((R / ver_f).read_text(encoding="utf-8"))
        pre = json.loads((R / "_beforefix" / em_f).read_text(encoding="utf-8"))
        fd = d["failure_decomposition"]
        arms.append({
            "arm": tag, "data": data, "header_format": fmt,
            "n": d["n"], "em": d["em"], "em_count": d["em_count"],
            "em_ci95_wilson": d["em_ci95_wilson"],
            "refused": d["refused"], "refusal_rate": d["refusal_rate"],
            "localization_rate": fd["localization_rate"],
            "decision_dist": d["decision_dist"],
            "gold_xbrl_verified": f"{v['tally'].get('verified', 0)}/{v['n']}",
            "em_before_fix": pre["em"], "refused_before_fix": pre["refused"],
            "source": em_f,
        })

    a, b, c, dd = arms
    res = {
        "title": "跨產業準確率四臂對照（114Q2，每臂 75 題數值直查）",
        "question": "架構層換到非半導體產業後，取值準確率是否等同半導體？",
        "gold_design": {
            "source": "原始二維寬表 CSV 儲存格，不經事實索引（避免評測集與受測系統同源）",
            "independent_check": "逐題以原始 HTML 行內 XBRL 之 contextRef 核對，四組皆 75/75 一致",
            "sampling": "固定亂數種子分層隨機抽樣；不因系統拒答而換題",
        },
        "scope": ("僅測軌道一之確定性取值：直接呼叫 _lookup_value_or_ratio，"
                  "題幹已給表名與欄位標頭，**不含 LLM 意圖路由**。"
                  "故不可與含路由、關係題與口語題的整體 EM 97.0% 直接相比。"),
        "arms": arms,
        # 推導一律以**修正前**數字進行——那是診斷所依據的證據；
        # 修正後四臂皆 100%，差值全為 0，會把診斷過程抹平。
        "findings": {
            "industry_effect_nested": {
                "compare": "A vs B（修正前）",
                "delta_pp": round((a["em_before_fix"] - b["em_before_fix"]) * 100, 1),
                "note": "巢狀格式下，跨產業與半導體完全相同（同為 6/75、同 61 題拒答）",
            },
            "industry_effect_flat": {
                "compare": "D vs C（修正前）",
                "delta_pp": round((dd["em_before_fix"] - c["em_before_fix"]) * 100, 1),
                "note": "扁平格式下，兩者同為 75/75",
            },
            "format_effect": {
                "compare": "B vs C（修正前）",
                "delta_pp": round((c["em_before_fix"] - b["em_before_fix"]) * 100, 1),
                "note": ("同一批公司、同一批題目，只換欄名格式即由 8.0% 變為 100.0%——"
                         "這才是變因"),
            },
            "root_cause": {
                "where": "rag_test_system_v14.py:2207",
                "code": "_ch_key = re.escape(str(col_hint)[:12])",
                "why": ("col_hint 只取前 12 字元。扁平格式下前 12 字元是具鑑別力的日期；"
                        "巢狀格式下卻是表名前綴（如「資產負債表Balance」），該表每欄皆同，"
                        "鎖定失效 → 候選退回多個年份欄 → 唯一性判定判為 ambiguous → 拒答。"),
                "evidence": ("巢狀臂的判定分佈為 ambiguous 61；扁平臂為 hit_col_hint 75。"),
                "impact": ("這是檢索層對解析器輸出格式的隱性耦合，"
                           "與「架構層零行修改即可換領域」的主張直接相關："
                           "換領域確實不必改程式，但**解析器輸出格式改變時會**。"),
                "suggested_fix": ("col_hint 比對不應依賴字首位置——"
                                  "改以日期樣式抽取後比對，或比對欄名尾段。"),
            },
        },
        "fix": {
            "where": "rag_test_system_v14.py：新增 _col_hint_key()，取代 col_hint[:12]",
            "what": ("欄位鎖定改以標頭中的日期（含「至」區間）為比對鍵，"
                     "不再依賴字首固定長度；標頭不含日期時退回原有行為。"),
            "effect": "A、B 兩臂由 8.0% 升至 100.0%，拒答 61 → 0；C、D 兩臂維持 100.0%。",
            "regression": ("以既有半導體題庫（架構 100 v2／v1、口語 100 v2 共 160 題）"
                           "回放確定性查表路徑，修正前後逐題答案與判定完全一致（0 題差異），"
                           "故凍結實驗數據不受影響。"),
        },
        "conclusion": ("在欄名格式相容的前提下，非半導體三家（航運、電子代工、機電工程）"
                       "之確定性取值為 75/75，與半導體對照組完全相同，未觀察到產業效應；"
                       "格式不相容時兩者亦同樣崩解至 6/75。故先前「架構層零行修改」之主張"
                       "在**產業**維度上成立，但需補充**解析器輸出格式**這一前提。"),
        "caveats": [
            "每臂僅 75 題、單一季度（114Q2）、每產業一家公司，樣本小。",
            "題型限於三大報表的數值直查，且題幹已消歧；不涵蓋關係題、口語題與跨期比較。",
            "未經 LLM 意圖路由，量測的是檢索層而非端到端。",
            "100% 不應外推為系統整體準確率；它是「槽位齊備時取值層的正確率」。",
        ],
    }
    Path(f"{OUT}.json").write_text(json.dumps(res, ensure_ascii=False, indent=2),
                                   encoding="utf-8")

    lines = [f"# {res['title']}", "", f"**問題**：{res['question']}", "",
             "| 臂 | 資料 | 欄名格式 | n | EM（修正前） | EM（修正後） | 拒答 前→後 | 金標 XBRL 核對 |",
             "|---|---|---|---|---|---|---|---|"]
    for x in arms:
        lines.append(f"| {x['arm']} | {x['data']} | {x['header_format']} | {x['n']} | "
                     f"{x['em_before_fix']:.1%} | **{x['em']:.1%}** | "
                     f"{x['refused_before_fix']} → {x['refused']} | "
                     f"{x['gold_xbrl_verified']} |")
    f = res["findings"]
    lines += ["", "## 推導", "",
              f"- **A vs B（產業，修正前）**：{f['industry_effect_nested']['delta_pp']:+.1f} pp"
              f"——{f['industry_effect_nested']['note']}",
              f"- **D vs C（產業，修正前）**：{f['industry_effect_flat']['delta_pp']:+.1f} pp"
              f"——{f['industry_effect_flat']['note']}",
              f"- **B vs C（格式，修正前）**：{f['format_effect']['delta_pp']:+.1f} pp"
              f"——{f['format_effect']['note']}", "",
              "## 根因", "",
              f"`{f['root_cause']['where']}`：`{f['root_cause']['code']}`", "",
              f"{f['root_cause']['why']}", "",
              f"證據：{f['root_cause']['evidence']}", "",
              f"影響：{f['root_cause']['impact']}", "",
              f"建議修正：{f['root_cause']['suggested_fix']}", "",
              "## 修正", "",
              f"- 位置：{res['fix']['where']}", f"- 作法：{res['fix']['what']}",
              f"- 效果：{res['fix']['effect']}", f"- 回歸：{res['fix']['regression']}", "",
              "## 結論", "", res["conclusion"], "", "## 界線", ""]
    lines += [f"- {c}" for c in res["caveats"]]
    Path(f"{OUT}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("\n".join(lines[:12]))
    print(f"\n→ {OUT}.json / {OUT}.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
