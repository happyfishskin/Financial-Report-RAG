#!/usr/bin/env python3
"""Produce three targeted human-review packets requested for the oral-defense audit.

Outputs (under results/manual_review_20260823):
  01_mops_html_traceback_18.{md,json,csv}
  02_routing_robustness_28.{md,json,csv}
  03_A_localization_audit_25.{md,json,csv}
  README.md

The script only selects and packages evidence.  It does not fill any human
verdict and does not rerun the system.
"""
from __future__ import annotations

import csv
import hashlib
import json
import random
import re
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "results" / "manual_review_20260823"
OUT.mkdir(parents=True, exist_ok=True)
SEED = 20260823

FACTS_PATH = ROOT / "reports_csv_output" / "__all_company_all_period_numeric_facts.csv"
FACTS = pd.read_csv(
    FACTS_PATH, dtype=str, keep_default_na=False, low_memory=False,
    encoding="utf-8-sig",
)
FACTS.columns = [c.lstrip("\ufeff") for c in FACTS.columns]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def abs_s(path: Path | str) -> str:
    return str(Path(path).resolve())


def company_code(name: str) -> str:
    hit = FACTS[FACTS.company_name.eq(str(name))]
    if hit.empty:
        # A few held-out metadata names carry a legal suffix not used by facts.
        hit = FACTS[FACTS.company_name.str.contains(str(name), regex=False)]
    return str(hit.iloc[0].stock_code) if len(hit) else ""


def html_path(code: str, period: str) -> Path | None:
    hits = list((ROOT / "reports_html_copy").glob(f"{code}_*/{code}_{period}_財報.html"))
    return hits[0] if hits else None


def source_path(raw: str, metadata: dict[str, Any]) -> Path | None:
    if not raw:
        return None
    p = ROOT / raw
    if p.exists():
        return p
    code = str(metadata.get("company_code") or company_code(metadata.get("company_name", "")))
    period = str(metadata.get("quarter") or "")
    if code and period:
        matches = list((ROOT / "reports_csv_output").glob(f"{code}_*/{period}/{Path(raw).name}"))
        if matches:
            return matches[0]
    matches = list((ROOT / "reports_csv_output").glob(f"*/*/{Path(raw).name}"))
    return matches[0] if matches else None


def html_targets(metadata: dict[str, Any]) -> list[Path]:
    targets: list[tuple[str, str]] = []
    period = str(metadata.get("quarter") or "")
    if metadata.get("companies") and period:
        targets.extend((str(c), period) for c in metadata["companies"])
    elif metadata.get("periods"):
        code = str(metadata.get("company_code") or company_code(metadata.get("company_name", "")))
        targets.extend((code, str(p)) for p in metadata["periods"])
    else:
        code = str(metadata.get("company_code") or company_code(metadata.get("company_name", "")))
        if code and period:
            targets.append((code, period))
    out: list[Path] = []
    for code, per in targets:
        p = html_path(code, per)
        if p and p not in out:
            out.append(p)
    return out


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            cooked = {}
            for k in fields:
                v = row.get(k, "")
                cooked[k] = json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v
            w.writerow(cooked)


def write_json(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Packet 1: 18 questions to trace visually to raw MOPS HTML
# ---------------------------------------------------------------------------
def packet_html_traceback() -> list[dict[str, Any]]:
    source = json.loads((ROOT / "results/gold_verification_sheet.json").read_text(encoding="utf-8"))
    # Exclude supply-chain rows because they do not originate in a MOPS HTML table.
    # Retain all high-risk graph/fact semantics and two known prior disagreements.
    selected_no = {1, 2, 3, 4, 5, 6, 7, 8, 11, 12, 13, 14, 15, 16, 17, 18, 23, 24}
    chosen = [x for x in source if int(x["no"]) in selected_no]
    rows: list[dict[str, Any]] = []
    for i, item in enumerate(chosen, 1):
        md = item.get("metadata", {}) or {}
        htmls = html_targets(md)
        raw_source = md.get("source_csv") or md.get("source_fact_file") or md.get("source_md") or ""
        src = source_path(str(raw_source), md)
        terms = [
            md.get("item_name") or md.get("item_canonical"),
            md.get("investor_name"), md.get("investee_name"),
            md.get("transacting_party") or md.get("party_or_category"),
            md.get("counterparty"), md.get("account_item"), item.get("gold"),
        ]
        terms = [str(t) for t in terms if t]
        rows.append({
            "audit_no": i,
            "id": item.get("id"),
            "question_type": item.get("question_type"),
            "dataset": item.get("dataset"),
            "question": item.get("question"),
            "gold": item.get("gold"),
            "system_answer": item.get("system_answer"),
            "company": md.get("company_name", "／".join(map(str, md.get("companies", [])))),
            "period": md.get("quarter", md.get("periods", "")),
            "extracted_source": abs_s(src) if src else "",
            "raw_html": [abs_s(p) for p in htmls],
            "browser_search_terms": terms[:5],
            "check_company_period": "",
            "check_table_row_column": "",
            "check_gold_value_sign_unit": "",
            "human_verdict": "",
            "human_note": "",
        })

    assert len(rows) == 18
    assert all(r["raw_html"] for r in rows), "Every traceback item must resolve to raw HTML"
    write_json(OUT / "01_mops_html_traceback_18.json", rows)
    write_csv(
        OUT / "01_mops_html_traceback_18.csv", rows,
        ["audit_no", "id", "question_type", "dataset", "question", "gold",
         "system_answer", "company", "period", "extracted_source", "raw_html",
         "browser_search_terms", "check_company_period", "check_table_row_column",
         "check_gold_value_sign_unit", "human_verdict", "human_note"],
    )
    L = [
        "# 01｜MOPS 原始 HTML 回溯核對（18 題）\n",
        "> 目的：跳過既有 CSV／Fact，直接目視原始 MOPS HTML。供人工填寫；未預填判定。\n",
        "核對順序：公司／季度 → 表格 → 列與期間欄 → 數值、括號負號、單位 → 金標。\n",
    ]
    for r in rows:
        L += [
            f"## {r['audit_no']:02d}. {r['id']}｜{r['question_type']}",
            f"- 問題：{r['question']}",
            f"- 金標：`{r['gold']}`；系統答案：`{r['system_answer']}`",
            f"- 抽取來源：`{r['extracted_source'] or '—'}`",
            "- 原始 HTML：" + "；".join(f"`{p}`" for p in r["raw_html"]),
            "- 建議頁內搜尋：" + "／".join(f"`{t}`" for t in r["browser_search_terms"]),
            "- [ ] 公司與季度正確　[ ] 表／列／欄正確　[ ] 數值、符號與單位正確",
            "- 人工判定：□正確　□錯誤　□存疑；備註：________________\n",
        ]
    (OUT / "01_mops_html_traceback_18.md").write_text("\n".join(L), encoding="utf-8")
    return rows


# ---------------------------------------------------------------------------
# Packet 2: 28-question routing/refusal robustness subset
# ---------------------------------------------------------------------------
def pick_existing(dataset: str, quotas: dict[str, int]) -> list[dict[str, Any]]:
    p = ROOT / dataset
    data = json.loads(p.read_text(encoding="utf-8"))
    out: list[dict[str, Any]] = []
    used: dict[str, int] = {k: 0 for k in quotas}
    for item in data:
        t = str(item.get("question_type"))
        if t in quotas and used[t] < quotas[t]:
            x = dict(item)
            x["_dataset"] = dataset
            out.append(x)
            used[t] += 1
    assert used == quotas, (dataset, used, quotas)
    return out


def track2_cases() -> list[dict[str, Any]]:
    return [
        {
            "id": "rob_t2_01", "subtype": "會計政策／遵循聲明", "company": "台灣積體電路製造",
            "period": "114Q3", "question": "台積電114Q3合併財務報告依哪一號國際會計準則編製？",
            "gold": "國際會計準則第34號「期中財務報導」。",
            "source": "reports_csv_output/2330_台灣積體電路製造/114Q3/2330_114Q3_重大會計政策之彙總說明.md",
        },
        {
            "id": "rob_t2_02", "subtype": "衡量基礎", "company": "中華精測科技",
            "period": "114Q3", "question": "中華精測114Q3合併財務報告採用什麼編製基礎？",
            "gold": "依歷史成本基礎編製。",
            "source": "reports_csv_output/6510_中華精測科技/114Q3/6510_114Q3_重大會計政策之彙總說明.md",
        },
        {
            "id": "rob_t2_03", "subtype": "合併會計政策", "company": "中華精測科技",
            "period": "114Q3", "question": "中華精測114Q3編製合併財報時，集團內交易、餘額、收益與費損如何處理？",
            "gold": "各個體間之交易、帳戶餘額、收益及費損全數銷除。",
            "source": "reports_csv_output/6510_中華精測科技/114Q3/6510_114Q3_重大會計政策之彙總說明.md",
        },
        {
            "id": "rob_t2_04", "subtype": "會計政策一致性", "company": "創意電子",
            "period": "114Q3", "question": "創意電子114Q3採用的合併報告編製基礎與原則，和113年度相比是否改變？",
            "gold": "與113年度合併財務報告相同。",
            "source": "reports_csv_output/3443_創意電子/114Q3/3443_114Q3_重大會計政策之彙總說明.md",
        },
        {
            "id": "rob_t2_05", "subtype": "衡量基礎", "company": "景碩科技",
            "period": "114Q3", "question": "景碩科技114Q3合併財報除哪一類項目外，以歷史成本為編製基礎？",
            "gold": "除以公允價值衡量之金融工具外，以歷史成本為編製基礎。",
            "source": "reports_csv_output/3189_景碩科技/114Q3/3189_114Q3_重大會計政策之彙總說明.md",
        },
        {
            "id": "rob_t2_06", "subtype": "衡量基礎", "company": "智原科技",
            "period": "114Q3", "question": "智原科技114Q3合併財務報告的衡量基礎為何？",
            "gold": "除以公允價值衡量之金融工具外，以歷史成本為編製基礎。",
            "source": "reports_csv_output/3035_智原科技/114Q3/3035_114Q3_重大會計政策之彙總說明.md",
        },
        {
            "id": "rob_t2_07", "subtype": "會計政策／揭露範圍", "company": "台灣積體電路製造",
            "period": "114Q3", "question": "台積電114Q3期中合併財報是否包含完整年度財報要求的全部IFRS揭露？",
            "gold": "否；未包含整份年度財務報告所規定的所有IFRS會計準則揭露資訊。",
            "source": "reports_csv_output/2330_台灣積體電路製造/114Q3/2330_114Q3_重大會計政策之彙總說明.md",
        },
        {
            "id": "rob_t2_08", "subtype": "關係人交易條件", "company": "台灣積體電路製造",
            "period": "114Q3", "question": "台積電114Q3母子公司間銷貨的價格與收款條件，與一般銷貨相比如何？其他交易如何決定條件？",
            "gold": "銷貨價格與收款條件與一般銷貨無重大差異；其餘交易由雙方協商決定。",
            "source": "reports_csv_output/2330_台灣積體電路製造/114Q3/2330_114Q3_母子公司間業務關係及重要交易往來情形.md",
        },
        {
            "id": "rob_t2_09", "subtype": "關係人交易條件", "company": "中華精測科技",
            "period": "114Q3", "question": "中華精測114Q3與關係人間的交易條件，和非關係人相比如何？",
            "gold": "與非關係人並無重大差異。",
            "source": "reports_csv_output/6510_中華精測科技/114Q3/6510_114Q3_母子公司間業務關係及重要交易往來情形.md",
        },
        {
            "id": "rob_t2_10", "subtype": "關係人交易條件", "company": "創意電子",
            "period": "114Q3", "question": "創意電子114Q3合併個體間交易若無同類交易可循，交易條件如何決定？",
            "gold": "依雙方協議決定。",
            "source": "reports_csv_output/3443_創意電子/114Q3/3443_114Q3_母子公司間業務關係及重要交易往來情形.md",
        },
    ]


def no_answer_cases() -> list[dict[str, Any]]:
    return [
        {"id": "rob_na_01", "company": "台灣積體電路製造", "code": "2330", "period": "114Q3",
         "item": "合約資產－流動", "question": "台積電114Q3的合約資產－流動是多少？"},
        {"id": "rob_na_02", "company": "瑞昱半導體", "code": "2379", "period": "114Q3",
         "item": "應付公司債", "question": "瑞昱半導體114Q3的應付公司債是多少？"},
        {"id": "rob_na_03", "company": "聯發科技", "code": "2454", "period": "114Q4",
         "item": "預付設備款", "question": "聯發科技114Q4的預付設備款是多少？"},
        {"id": "rob_na_04", "company": "中華精測科技", "code": "6510", "period": "114Q2",
         "item": "其他應收款－關係人", "question": "中華精測114Q2的其他應收款－關係人是多少？"},
        {"id": "rob_na_05", "company": "群聯電子", "code": "8299", "period": "114Q2",
         "item": "待出售非流動資產", "question": "群聯電子114Q2的待出售非流動資產是多少？"},
    ]


def packet_routing_robustness() -> list[dict[str, Any]]:
    # 13 frozen-regression items + 10 narrative evidence items + 5 near-miss no-answer items.
    numeric = pick_existing(
        "questions/heldout2/heldout_arch_100.json",
        {"direct_numeric_lookup": 3, "cross_company_compare": 2, "cross_period_compare": 2},
    )
    numeric += pick_existing(
        "questions/heldout2/heldout_colloq_nat_100.json", {"colloquial_natural": 1}
    )
    relation = pick_existing(
        "questions/heldout2/heldout_arch_100.json",
        {"investment_graph": 1, "related_party_transaction_graph": 1,
         "mainland_investment_graph": 1, "supply_chain_graph": 1, "risk_event_graph": 1},
    )
    rows: list[dict[str, Any]] = []
    no = 0
    for item in numeric + relation:
        no += 1
        t = str(item.get("question_type"))
        md = item.get("metadata", {}) or {}
        src = md.get("source_csv") or md.get("source_fact_file") or md.get("source_md") or ""
        rows.append({
            "no": no, "id": item.get("id"), "group": "既有凍結題（回歸）",
            "subtype": t, "question": item.get("question"), "gold": item.get("expected_answer"),
            "expected_route": "relation_lookup" if "graph" in t else "direct_lookup",
            "accepted_routes": ["graph_rag", "relation_lookup"] if "graph" in t else ["direct_lookup"],
            "expected_refusal": False, "source": abs_s(ROOT / item["_dataset"]),
            "evidence_source": abs_s(source_path(str(src), md)) if source_path(str(src), md) else "",
            "system_route": "", "route_correct": "", "system_answer": "",
            "refusal_correct": "", "evidence_grounded": "", "human_note": "",
        })
    for item in track2_cases():
        no += 1
        src = ROOT / item["source"]
        assert src.exists(), src
        code = re.search(r"/(\d{4})_", "/" + item["source"]).group(1)
        hp = html_path(code, item["period"])
        rows.append({
            "no": no, "id": item["id"], "group": "軌道二真實敘述證據",
            "subtype": item["subtype"], "question": item["question"], "gold": item["gold"],
            "expected_route": "semantic_rag", "accepted_routes": ["semantic_rag"],
            "expected_refusal": False, "source": abs_s(src),
            "evidence_source": abs_s(hp) if hp else "",
            "system_route": "", "route_correct": "", "system_answer": "",
            "refusal_correct": "", "evidence_grounded": "", "human_note": "",
        })
    for item in no_answer_cases():
        no += 1
        hp = html_path(item["code"], item["period"])
        assert hp and hp.exists()
        html_absent = item["item"] not in hp.read_text(encoding="utf-8", errors="ignore")
        fact_hit = FACTS[
            FACTS.company_name.eq(item["company"]) & FACTS.period.eq(item["period"])
            & FACTS.item_name.str.contains(item["item"], regex=False)
        ]
        assert html_absent and fact_hit.empty, item
        rows.append({
            "no": no, "id": item["id"], "group": "真公司真季度未揭露近似題",
            "subtype": "no_answer_near_miss", "question": item["question"],
            "gold": "應拒答：該公司該季度未揭露此項目",
            "expected_route": "fact_or_semantic_then_refuse",
            "accepted_routes": ["direct_lookup", "semantic_rag"],
            "expected_refusal": True, "source": abs_s(hp),
            "evidence_source": f"HTML精確詞不存在={html_absent}; numeric facts命中={len(fact_hit)}",
            "system_route": "", "route_correct": "", "system_answer": "",
            "refusal_correct": "", "evidence_grounded": "", "human_note": "",
        })
    assert len(rows) == 28
    write_json(OUT / "02_routing_robustness_28.json", rows)
    fields = ["no", "id", "group", "subtype", "question", "gold", "expected_route",
              "accepted_routes", "expected_refusal", "source", "evidence_source",
              "system_route", "route_correct", "system_answer", "refusal_correct",
              "evidence_grounded", "human_note"]
    write_csv(OUT / "02_routing_robustness_28.csv", rows, fields)
    L = [
        "# 02｜強健性與分流驗證子集（28 題）\n",
        "組成：既有凍結回歸 13＋軌道二真實敘述 10＋未揭露近似題 5。\n",
        "主指標：分流正確率、拒答正確率；輔助：人工有據性（二元）。",
        "\n> 注意：13 題沿用既有 held-out2，只能作回歸，不是新的獨立泛化證據；新增15題須在首次執行前凍結本檔雜湊。\n",
    ]
    for r in rows:
        L += [
            f"## {r['no']:02d}. {r['id']}｜{r['group']}／{r['subtype']}",
            f"- 問題：{r['question']}",
            f"- 預期：{r['gold']}",
            f"- 接受路由：`{r['accepted_routes']}`；預期拒答：`{r['expected_refusal']}`",
            f"- 證據：`{r['source']}`" + (f"；`{r['evidence_source']}`" if r['evidence_source'] else ""),
            "- 實測路由：________　□路由正確　系統答案：________________",
            "- □拒答正確　□答案有據　□答案無據／不足；備註：________________\n",
        ]
    (OUT / "02_routing_robustness_28.md").write_text("\n".join(L), encoding="utf-8")
    return rows


# ---------------------------------------------------------------------------
# Packet 3: 25 A-group self-reported localization cases
# ---------------------------------------------------------------------------
REFUSAL_STATUS = {"not_found", "missing_value", "no_evidence", "llm_error", "schema_invalid"}


def norm(s: str) -> str:
    return re.sub(r"\s+", "", str(s or "")).lower()


def localized(row: dict[str, Any]) -> bool:
    gi, gc = norm(row.get("gold_item")), norm(row.get("gold_column"))
    d = row["groups"]["A_raw_markdown"]
    ri, rc = norm(d.get("reported_item")), norm(d.get("reported_period"))
    ok_i = bool(ri) and (ri in gi or gi in ri)
    ok_c = bool(rc) and (rc in gc or gc in rc)
    return ok_i and ok_c


def select_diverse(pool: list[dict[str, Any]], n: int, rng: random.Random) -> list[dict[str, Any]]:
    rng.shuffle(pool)
    out: list[dict[str, Any]] = []
    # First pass: at least one from each source result where possible.
    used_src: set[str] = set()
    for x in pool:
        if x["_result_file"] not in used_src:
            out.append(x); used_src.add(x["_result_file"])
            if len(out) == n:
                return out
    for x in pool:
        if x not in out:
            out.append(x)
            if len(out) == n:
                break
    return out


def packet_a_localization() -> list[dict[str, Any]]:
    result_files = [
        ROOT / "results/evidence_format_ablation.json",
        ROOT / "results/evidence_format_ablation_ho_arch.json",
        ROOT / "results/evidence_format_ablation_ho_colloq.json",
    ]
    all_rows: list[dict[str, Any]] = []
    dataset_maps: dict[str, dict[str, dict[str, Any]]] = {}
    for p in result_files:
        payload = json.loads(p.read_text(encoding="utf-8"))
        dataset = str(payload["dataset"])
        dp = Path(dataset)
        if not dp.is_absolute():
            dp = ROOT / dp
        items = json.loads(dp.read_text(encoding="utf-8"))
        dataset_maps[dataset] = {str(x.get("id")): x for x in items}
        for row in payload["results"]:
            row = dict(row)
            row["_result_file"] = str(p.relative_to(ROOT))
            row["_dataset"] = dataset
            all_rows.append(row)

    strata: dict[str, list[dict[str, Any]]] = {
        "定位對但值錯": [], "定位對且答案對": [],
        "定位錯但仍作答": [], "拒答或回報歧義": [],
    }
    for row in all_rows:
        d = row["groups"]["A_raw_markdown"]
        em = bool(d["scores"]["exact_match"])
        loc = localized(row)
        refused = str(d.get("status")) in REFUSAL_STATUS or "找不到相關資料" in str(d.get("answer"))
        amb = str(d.get("status")) == "ambiguous"
        if loc and not em:
            strata["定位對但值錯"].append(row)
        elif loc and em:
            strata["定位對且答案對"].append(row)
        elif not loc and not refused and not amb:
            strata["定位錯但仍作答"].append(row)
        elif refused or amb:
            strata["拒答或回報歧義"].append(row)

    quotas = {"定位對但值錯": 10, "定位對且答案對": 5,
              "定位錯但仍作答": 5, "拒答或回報歧義": 5}
    rng = random.Random(SEED)
    chosen: list[tuple[str, dict[str, Any]]] = []
    for label, n in quotas.items():
        picks = select_diverse(list(strata[label]), n, rng)
        assert len(picks) == n, (label, len(picks))
        chosen.extend((label, p) for p in picks)

    rows: list[dict[str, Any]] = []
    for i, (label, row) in enumerate(chosen, 1):
        d = row["groups"]["A_raw_markdown"]
        qrec = dataset_maps[row["_dataset"]].get(str(row.get("id")), {})
        md = qrec.get("metadata", {}) or {}
        src_raw = md.get("source_csv") or md.get("source_md") or ""
        src = source_path(str(src_raw), md)
        raw_html = [abs_s(p) for p in html_targets(md)]
        rows.append({
            "audit_no": i, "stratum": label, "id": row.get("id"),
            "result_file": row["_result_file"], "dataset": row["_dataset"],
            "question": row.get("question"), "gold_answer": row.get("expected_answer"),
            "gold_item": row.get("gold_item"), "gold_period": row.get("gold_column"),
            "A_answer": d.get("answer"), "A_status": d.get("status"),
            "A_reported_item": d.get("reported_item"),
            "A_reported_period": d.get("reported_period"),
            "auto_localized": localized(row), "A_exact_match": bool(d["scores"]["exact_match"]),
            "source_table": abs_s(src) if src else "",
            "raw_html": raw_html,
            "human_item_match": "", "human_period_match": "",
            "human_localized": "", "human_note": "",
        })
    assert len(rows) == 25
    write_json(OUT / "03_A_localization_audit_25.json", rows)
    fields = ["audit_no", "stratum", "id", "result_file", "dataset", "question",
              "gold_answer", "gold_item", "gold_period", "A_answer", "A_status",
              "A_reported_item", "A_reported_period", "auto_localized", "A_exact_match",
              "source_table", "raw_html", "human_item_match", "human_period_match",
              "human_localized", "human_note"]
    write_csv(OUT / "03_A_localization_audit_25.csv", rows, fields)
    L = [
        "# 03｜A 組自報定位人工核對（25 題）\n",
        "分層：定位對但值錯10、定位對且答案對5、定位錯但仍作答5、拒答／歧義5。\n",
        "> 人工只判斷模型自報的科目與期間欄是否真的對應題目金標；不要用最終答案倒推定位。\n",
    ]
    for r in rows:
        L += [
            f"## {r['audit_no']:02d}. {r['id']}｜{r['stratum']}",
            f"- 問題：{r['question']}",
            f"- 金標欄位：科目=`{r['gold_item']}`；期間=`{r['gold_period']}`",
            f"- A自報：科目=`{r['A_reported_item']}`；期間=`{r['A_reported_period']}`",
            f"- A答案／狀態：`{r['A_answer']}`／`{r['A_status']}`；自動定位={r['auto_localized']}；EM={r['A_exact_match']}",
            f"- 來源表：`{r['source_table'] or '題庫metadata未附，依公司／季度回查'}`",
            "- 原始 HTML：" + ("；".join(f"`{p}`" for p in r["raw_html"]) or "—"),
            "- 人工：□科目對 □科目錯　□期間對 □期間錯　最終定位：□對 □錯 □無法判定",
            "- 備註：________________\n",
        ]
    (OUT / "03_A_localization_audit_25.md").write_text("\n".join(L), encoding="utf-8")
    return rows


def main() -> None:
    p1 = packet_html_traceback()
    p2 = packet_routing_robustness()
    p3 = packet_a_localization()
    # Exclude README itself so repeated generation remains deterministic.
    generated = sorted(p for p in OUT.glob("*") if p.name != "README.md")
    readme = f"""# 人工核對工作包（2026-08-23）

## 已抽樣

- `01_mops_html_traceback_18`：{len(p1)} 題，直接回到原始 MOPS HTML。
- `02_routing_robustness_28`：{len(p2)} 題；13 回歸＋10 軌道二＋5 未揭露近似題。
- `03_A_localization_audit_25`：{len(p3)} 題，四種失效分層抽樣。

每份均有 Markdown（閱讀／勾選）、CSV（試算表回填）、JSON（程式統計）。

## 建議執行順序

1. 先人工核准 02 中10題敘述金標，並確認5題未揭露近似題沒有同義揭露。
2. 核准後再將 `02_routing_robustness_28.json` 及目前系統版本計算 SHA256、凍結，才跑新題。
3. 完成 01 的 HTML 目視核對；任何錯誤先修金標，不要先改系統。
4. 盲判 03 的科目／期間定位，再與 `auto_localized` 比較一致率。
5. 02 以分流正確率、拒答正確率為主；只對非拒答題填人工有據性。

## 重要界線

- 02 中13題沿用既有 heldout2，只能作回歸，不能宣稱為新的獨立 held-out。
- 10題軌道二的金標是來源片段摘要，必須由人工回看來源後核准才可評分。
- 5題未揭露近似題已機械確認：原始HTML無精確詞、numeric facts無同名科目；人工仍需確認沒有同義揭露。

## 產物雜湊

"""
    for p in generated:
        if p.is_file():
            readme += f"- `{p.name}`：`{sha256(p)}`\n"
    (OUT / "README.md").write_text(readme, encoding="utf-8")
    print(f"Output: {OUT}")
    print(f"  HTML traceback: {len(p1)}")
    print(f"  Routing robustness: {len(p2)}")
    print(f"  A localization: {len(p3)}")


if __name__ == "__main__":
    main()
