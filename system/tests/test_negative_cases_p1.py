#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Negative Test Cases N05–N36（prompt_audit_issues.txt §七 + §九）
================================================================
承接 `test_negative_cases.py`（P0：N01/N02/N03/N04/N15/N17/N18/N19/N27/N30），
本檔補齊其餘 negative cases，並作為 P1／P2 重構的**驗收規格**。

分組：
  A. 槽位表達力      N05 多科目、N06 多公司×多期間矩陣、N07 缺欄位澄清
  B. 科目正規化      N08 本業獲利→營業利益
  C. 關係人與圖譜    N09 科目精確選擇、N10 值屬性、N24 屬性而非實體、N25 期間限定
  D. 報表口徑        N11 合併/個體、N12 單季/累計
  E. 空值語意        N13 零值、N14 破折號、N26 相近科目不得替代
  F. Context 完整性  N16 首個 chunk 過長不得產生空 context
  G. 比率輸出        N20 公司名 schema、N21 平手、N22 分母為零、N23 括號負數
  H. 輸出格式        N28 JSON 前後夾雜文字、N29 公司名含特殊字元
  I. 資料集稽核      N31 題型錯標、N32 整列傾印金標、N33 無語意列序號
  J. 實驗一致性      N35 自然語言圖譜路由、N36 answer_mode 與實際引擎一致

執行：python3 -m pytest tests/test_negative_cases_p1.py -v
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import llm_contract as C  # noqa: E402


def _vllm_alive() -> bool:
    import urllib.request
    try:
        with urllib.request.urlopen("http://127.0.0.1:8000/v1/models", timeout=3):
            return True
    except Exception:                                             # noqa: BLE001
        return False


needs_vllm = pytest.mark.skipif(not _vllm_alive(), reason="vLLM 服務未啟動")


# ══════════════════════════════════════════════════════════════
# A. 槽位表達力：N05 / N06 / N07
# ══════════════════════════════════════════════════════════════
def test_n05_multi_item_question_keeps_both_items():
    """N05：「營收和營業利益各是多少」須抽出兩個 items，不得只留一個。"""
    slots, violations = C.validate_slots_payload({
        "status": "ok", "intent": "value_lookup",
        "companies_raw": ["台積電"], "periods_raw": ["114Q2"],
        "items_raw": ["營收", "營業利益"],
    })
    assert slots is not None, violations
    assert len(slots["items_raw"]) == 2, "兩個科目都必須保留"


def test_n06_matrix_company_x_period():
    """N06：兩公司 × 兩期間須能表達為矩陣查詢。"""
    slots, _ = C.validate_slots_payload({
        "status": "ok", "intent": "comparison",
        "companies_raw": ["台積電", "聯電"],
        "periods_raw": ["113Q4", "114Q1"],
        "items_raw": ["毛利率"],
    })
    assert slots is not None
    dims = C.comparison_dimensions(slots)
    assert set(dims) == {"company", "period"}, f"應同時跨公司與期間，實得 {dims}"
    assert C.expand_matrix(slots) == [
        ("台積電", "113Q4"), ("台積電", "114Q1"),
        ("聯電", "113Q4"), ("聯電", "114Q1"),
    ]


def test_n07_missing_fields_triggers_clarification():
    """N07：「這家公司今年賺多少？」缺公司與明確期間，須要求澄清而非全庫搜尋。"""
    slots, _ = C.validate_slots_payload({
        "status": "ok", "intent": "value_lookup",
        "companies_raw": [], "periods_raw": [], "items_raw": ["賺多少"],
    })
    assert slots is not None
    assert slots["status"] == "needs_clarification"
    assert set(slots["missing_fields"]) >= {"company", "period"}


def test_n07b_complete_slots_stay_ok():
    """對照組：槽位齊全時不得誤判為需要澄清。"""
    slots, _ = C.validate_slots_payload({
        "status": "ok", "intent": "value_lookup",
        "companies_raw": ["台積電"], "periods_raw": ["114Q2"],
        "items_raw": ["資產總計"],
    })
    assert slots["status"] == "ok" and slots["missing_fields"] == []


def test_n30_out_of_scope_slot_status():
    """N30：非財報問題須標為 out_of_scope，不得進行 broad vector search。"""
    slots, _ = C.validate_slots_payload({
        "status": "out_of_scope", "intent": "other",
        "companies_raw": [], "periods_raw": [], "items_raw": [],
    })
    assert slots["status"] == "out_of_scope"
    assert C.should_search(slots) is False, "out_of_scope 不得觸發檢索"


# ══════════════════════════════════════════════════════════════
# B. 科目正規化：N08
# ══════════════════════════════════════════════════════════════
def test_n08_operating_income_not_gross_profit():
    """N08：「本業獲利」須正規化為營業利益，不得映射成營業毛利。"""
    import rag_test_system_v14 as v14
    assert v14._ONTOLOGY_REVERSE.get("本業獲利") == "營業利益（損失）"
    assert v14._ONTOLOGY_REVERSE.get("本業獲利") != "營業毛利（毛損）"


# ══════════════════════════════════════════════════════════════
# D. 報表口徑：N11 / N12
# ══════════════════════════════════════════════════════════════
def test_n11_consolidated_vs_standalone_conflict_is_ambiguous():
    """N11：同公司同期同科目同時存在合併與個體報表且題目未指明 → ambiguous。"""
    cands = [
        {"value_raw": "1,000", "basis": "consolidated", "period_kind": "cumulative"},
        {"value_raw": "800", "basis": "standalone", "period_kind": "cumulative"},
    ]
    res = C.resolve_evidence(cands, want_basis=None, want_period_kind="cumulative")
    assert res["status"] == "ambiguous", res


def test_n11b_explicit_basis_resolves():
    """指明口徑時須能唯一選出。"""
    cands = [
        {"value_raw": "1,000", "basis": "consolidated", "period_kind": "cumulative"},
        {"value_raw": "800", "basis": "standalone", "period_kind": "cumulative"},
    ]
    res = C.resolve_evidence(cands, want_basis="standalone",
                             want_period_kind="cumulative")
    assert res["status"] == "ok" and res["value_raw"] == "800"


def test_n12_single_quarter_vs_cumulative():
    """N12：單季與累計並存時須依題目語意選擇，未指明則 ambiguous。"""
    cands = [
        {"value_raw": "100", "basis": "consolidated", "period_kind": "single_quarter"},
        {"value_raw": "300", "basis": "consolidated", "period_kind": "cumulative"},
    ]
    assert C.resolve_evidence(cands, None, "single_quarter")["value_raw"] == "100"
    assert C.resolve_evidence(cands, None, "cumulative")["value_raw"] == "300"
    assert C.resolve_evidence(cands, None, None)["status"] == "ambiguous"


def test_period_kind_detected_from_question():
    """題幹語意須能推出期間口徑（累計數／單季數）。"""
    assert C.detect_period_kind("台積電114Q2營收（累計數，自年初至本期末）？") == "cumulative"
    assert C.detect_period_kind("台積電114Q2單季營收多少？") == "single_quarter"
    assert C.detect_period_kind("台積電114Q2營收多少？") is None


# ══════════════════════════════════════════════════════════════
# E. 空值語意：N13 / N14 / N26
# ══════════════════════════════════════════════════════════════
def test_n13_zero_is_a_valid_value():
    """N13：0 是有效數值，不得當成空值。"""
    assert C.classify_cell_value("0") == "value"
    assert C.classify_cell_value(0) == "value"
    env, _ = C.parse_answer_payload('{"status":"ok","value_raw":"0"}')
    assert env["status"] == "ok" and env["value_raw"] == "0"
    assert C.envelope_to_text(env) == "0"


@pytest.mark.parametrize("dash", ["-", "—", "–", "N/A", "n/a", ""])
def test_n14_dash_is_missing_value_not_zero(dash):
    """N14：- / — / N/A 須為 missing_value，不得自動當成 0。"""
    assert C.classify_cell_value(dash) == "missing_value"
    assert C.classify_cell_value(dash) != "value"


def test_n26_nearest_item_must_not_substitute(monkeypatch):
    """N26：片段只有相近科目時須回 not_found，不得用相近科目的數值。"""
    import rag_test_system_v14 as v14
    monkeypatch.setattr(v14, "_call_vllm",
                        lambda *a, **k: '{"status":"not_found","value_raw":""}')
    ans, diag = v14._generate_answer_json("u", "m", "台積電114Q2本業獲利？",
                                          "科目：營業毛利（毛損） ｜ 114Q2：263,385,701")
    assert ans == "找不到相關資料" and diag["status"] == "not_found"


def test_answer_prompt_forbids_nearest_match():
    """提示詞須明文禁止以語意最接近的科目代替（稽核 §4）。"""
    import rag_test_system_v14 as v14
    assert "語意最接近" in v14._LLM_SYSTEM_PROMPT_JSON  # 出現在「嚴禁」語境
    assert "嚴禁" in v14._LLM_SYSTEM_PROMPT_JSON


# ══════════════════════════════════════════════════════════════
# F. Context 完整性：N16
# ══════════════════════════════════════════════════════════════
def test_n16_oversized_first_chunk_still_yields_context():
    """
    N16：第一個 chunk 超過上限時，舊版直接 break 造成 **空 context**，
    程式卻仍認為有檢索命中並送給模型作答（稽核 §17）。
    修正後至少須安全截斷並保留第一個片段。
    """
    import rag_test_system_v14 as v14
    hits = [{"content": "科目：資產總計 ｜ 114Q2：" + "9" * 6000,
             "company_name": "台積電", "quarter": "114Q2",
             "table_name": "資產負債表", "score": 0.9}]
    ctx = v14._format_context_from_hits(hits, max_chars=4000)
    assert ctx.strip(), "有檢索命中時 context 不得為空"
    assert len(ctx) <= 4000 + 200, "須截斷至上限附近"
    assert "資產總計" in ctx, "須保留片段開頭的關鍵內容"


def test_n16b_empty_context_must_not_call_llm(monkeypatch):
    """evidence 為空時不得呼叫答案生成 LLM（稽核 §17 建議）。"""
    import rag_test_system_v14 as v14
    called = {"n": 0}

    def _spy(*a, **k):
        called["n"] += 1
        return '{"status":"ok","value_raw":"999"}'

    monkeypatch.setattr(v14, "_call_vllm", _spy)
    ans, diag = v14._generate_answer_json("u", "m", "Q", "   ")
    assert called["n"] == 0, "空證據不應觸發 LLM 呼叫"
    assert ans == "找不到相關資料" and diag["status"] == "no_evidence"


# ══════════════════════════════════════════════════════════════
# G. 比率輸出：N20 / N21 / N22 / N23
# ══════════════════════════════════════════════════════════════
def test_n20_placeholder_company_names_fail_schema():
    """N20：輸出「公司A／公司B」須被判為公司名 schema 違規，不得靜默對應。"""
    rep = C.validate_ratio_answer("公司A: 12.34% ｜ 公司B: 56.78% ｜ 較高: 公司A",
                                  ["台積電", "聯電"])
    assert rep["schema_valid"] is False
    assert rep["name_exact"] is False
    assert "placeholder" in rep["reason"]


def test_n20b_correct_names_pass():
    rep = C.validate_ratio_answer("台積電: 12.34% ｜ 聯電: 56.78% ｜ 較高: 聯電",
                                  ["台積電", "聯電"])
    assert rep["schema_valid"] and rep["name_exact"]
    assert rep["winner"] == "聯電"


def test_n20c_simplified_chinese_is_name_mismatch_but_mappable():
    """簡體公司名須分開統計：schema/name 不通過，但可依序位對應（稽核 §21）。"""
    rep = C.validate_ratio_answer("力成: 19.15% ｜ 联发科: 49.66% ｜ 較高: 联发科",
                                  ["力成", "聯發科"])
    assert rep["name_exact"] is False
    assert rep["mapping_exact"] is True
    assert rep["winner"] == "聯發科"


def test_n21_tie_must_report_equal():
    """N21：兩比率四捨五入後相同 → 須輸出「相同」，不得固定選第二家。"""
    assert C.compare_ratio(12.34, 12.34, "A", "B") == "相同"
    assert C.compare_ratio(12.35, 12.34, "A", "B") == "A"
    assert C.compare_ratio(12.34, 12.35, "A", "B") == "B"


def test_n22_zero_denominator_not_computable():
    """N22：分母為 0 須回 not_computable，不得計算或回 0。"""
    res = C.compute_ratio_safe("1,234", "0")
    assert res["status"] == "not_computable" and res["value"] is None
    res2 = C.compute_ratio_safe("1,234", "—")
    assert res2["status"] == "not_computable"


def test_n23_parenthesised_negative_parsed():
    """N23：括號負數 (1,234) 須解析為 -1234。"""
    assert C.parse_signed_number("(1,234)") == -1234.0
    assert C.parse_signed_number("( 1,234 )") == -1234.0
    assert C.parse_signed_number("1,234") == 1234.0
    res = C.compute_ratio_safe("(1,234)", "10,000")
    assert res["status"] == "ok" and res["value"] == -12.34


# ══════════════════════════════════════════════════════════════
# H. 輸出格式：N28 / N29
# ══════════════════════════════════════════════════════════════
def test_n28_markdown_wrapped_json_recorded_as_violation():
    """N28：JSON 前後夾雜 Markdown／解說時仍須解析，但要記錄 schema violation。"""
    txt = "好的，以下是答案：\n```json\n{\"status\":\"ok\",\"value_raw\":\"123\"}\n```\n希望有幫助！"
    env, violations = C.parse_answer_payload(txt)
    assert env is not None and env["value_raw"] == "123"
    assert any("夾雜" in v or "非純 JSON" in v for v in violations), \
        f"須記錄格式違規，實得 {violations}"


def test_n29_company_name_with_special_chars():
    """N29：含 A、括號、直線的公司名不得被誤認為代稱或分隔符。"""
    rep = C.validate_ratio_answer(
        "台灣光罩(股)公司: 10.00% ｜ AMD Taiwan: 20.00% ｜ 較高: AMD Taiwan",
        ["台灣光罩(股)公司", "AMD Taiwan"])
    assert rep["schema_valid"] and rep["name_exact"]
    assert rep["winner"] == "AMD Taiwan", "含 A 的公司名不得被當成「公司A」代稱"


# ══════════════════════════════════════════════════════════════
# I. 資料集稽核：N31 / N32 / N33
# ══════════════════════════════════════════════════════════════
def test_n31_mainland_investment_mislabelled_as_related_party():
    """N31：來源為大陸投資表卻標成 related_party_transaction_graph → 稽核須失敗。"""
    import audit_datasets as A
    q = {"id": "arch_test_084", "question_type": "related_party_transaction_graph",
         "question": "根據關係人交易圖譜，【群聯電子】在【113Q2】…",
         "expected_answer": "合肥芯鵬技術有限公司",
         "metadata": {"company_code": "8299", "quarter": "113Q2",
                      "source_csv": "reports_csv_output/8299_群聯電子/113Q2/"
                                    "8299_113Q2_轉投資大陸地區之事業相關資訊.csv"}}
    findings: list = []
    A.audit_question_type_consistency(q, findings, "test.json")
    assert findings, "題型與來源表不一致須被檢出"
    assert findings[0]["defect"] == "D10_question_type_mismatch"


def test_n32_serialized_row_gold_flagged():
    """N32：金標含 value_2/value_3 整列傾印 → 稽核失敗。"""
    import audit_datasets as A
    assert A.is_corrupt_gold(
        "FINANCIERE AFG；value_2=X; value_3=子公司對子公司; value_5=238,422")


def test_n33_meaningless_row_index_in_question():
    """N33：題目含無語意列序號（在【0】中）→ 稽核失敗。"""
    import audit_datasets as A
    findings: list = []
    q = {"id": "x", "question_type": "related_party_transaction_graph",
         "question": "根據關係人交易圖譜，【台灣光罩】在【113Q2】的【7】中，…",
         "expected_answer": "2,414", "metadata": {}}
    A.audit_row_index_in_question(q, findings, "test.json")
    assert findings and findings[0]["defect"] == "D11_row_index_in_question"


def test_n33b_semantic_question_passes():
    """對照組：已改用語意主鍵的題目不得被誤判。"""
    import audit_datasets as A
    findings: list = []
    q = {"id": "y", "question_type": "related_party_transaction_graph",
         "question": "根據關係人交易圖譜，【台灣光罩】在【113Q2】，【iPro Vision Inc.】"
                     "與【昱嘉科技(股)公司】之間的【銷貨】交易金額是多少？",
         "expected_answer": "2,414", "metadata": {}}
    A.audit_row_index_in_question(q, findings, "test.json")
    assert not findings


# ══════════════════════════════════════════════════════════════
# J. 實驗一致性：N36
# ══════════════════════════════════════════════════════════════
def test_n36_answer_mode_must_match_actual_engine():
    """
    N36：自建 Layer 0 命中不得記為 Microsoft GraphRAG。

    [雙軌重構] MS GraphRAG LocalSearch 已整段移除，故本測試改為驗證
    「該呼叫路徑不存在」＋「answer_mode 宣告仍指向自建引擎」。
    """
    import rag_test_system_v14 as v14
    assert not hasattr(v14, "_graphrag_ms_local_search"), \
        "Microsoft GraphRAG LocalSearch 應已自雙軌架構移除"
    assert not hasattr(v14, "_GRAPHRAG_PKG_AVAILABLE"), \
        "不應再有 MS GraphRAG 套件偵測旗標"
    modes = C.declared_answer_modes()
    assert modes["relation_lookup"] == "pandas_relation_fact_lookup"
    assert "microsoft" not in " ".join(modes.values()).lower(), \
        "不得宣稱使用 Microsoft GraphRAG"


def test_online_graph_traversal_disabled_by_default():
    """
    [雙軌重構] 線上圖遍歷須預設停用——602 道關係題 100% 由 Layer 0 答出，
    線上遍歷在既有題庫中從未貢獻正確答案（附錄 B.5：多跳壓測 0/30）。
    """
    import rag_test_system_v14 as v14
    assert v14._ONLINE_GRAPH_TRAVERSAL is False
    assert v14._GRAPH_LAYER_MODE["l0"] == "relation_lookup"
    assert v14._GRAPH_LAYER_MODE["entity_table"] == "relation_lookup"


@needs_vllm
def test_n35_natural_graph_question_routes_to_relation_branch():
    """
    N35：不含「圖譜」字樣的自然問法仍須進入關係事實直查分支。

    [雙軌重構] 判定條件未變，只是落點由第三軌改為軌道一的關係分支，
    故斷言改為 route=direct_lookup ＋ _relation_query=True。
    """
    import rag_test_system_v14 as v14
    q = "群聯電子113Q2投資的大陸事業中，哪一家主要從事電子產品軟硬體研發？"
    intent = v14._llm_intent_router(q, v14.DEFAULT_VLLM_URL, v14.DEFAULT_LLM_MODEL)
    assert intent["route"] == "direct_lookup", f"實得 {intent['route']}"
    assert intent.get("_relation_query") is True, "應判為關係事實題"


def test_derive_track_relation_branch_offline():
    """[雙軌重構] 確定性路由（不需 vLLM）：關係語意 → 軌道一之關係分支。"""
    import rag_test_system_v14 as v14
    cases = [
        ("群聯電子113Q2投資的大陸事業中，哪一家主要從事研發？", True),
        ("台達電114Q1，甲公司與乙公司之間的營業收入交易金額是多少？", True),
        ("請查詢【台積電】在【114Q2】的【資產總計】（2025年6月30日）是多少？", False),
        ("辛耘企業114Q1賺了多少錢？", False),
    ]
    for q, want_rel in cases:
        route, is_rel = v14._derive_track_deterministic(q, {"route": "semantic_rag"})
        assert route == "direct_lookup", f"{q} → {route}"
        assert is_rel is want_rel, f"{q} → relation={is_rel}，預期 {want_rel}"

    # 明示向量檢索 → 軌道二
    r, rel = v14._derive_track_deterministic("請從向量檢索找出台積電的資產負債表", {})
    assert (r, rel) == ("semantic_rag", False)


# ══════════════════════════════════════════════════════════════
# K. [P2 補強] Layer 0 自然語句樣板（無【】依賴）
# ══════════════════════════════════════════════════════════════
@pytest.mark.parametrize("q,label,want", [
    ("投資了哪一家所在地為香港的被投資公司？", "所在地為", "香港"),
    ("主要業務為配管工程及電器承裝的被投資公司", "主要業務為", "配管工程及電器承裝"),
    ("主要業務為電子產品軟硬件的研發、生產的被投資公司是哪一家？",
     "主要業務為", "電子產品軟硬件的研發、生產"),
    ("帳面價值為2,051,269的被投資公司", "帳面價值為", "2,051,269"),
    ("主要業務為【資訊軟體服務業】的被投資公司", "主要業務為", "資訊軟體服務業"),
])
def test_disc_value_extracted_without_brackets(q, label, want):
    """鑑別子句在無【】時仍須抽出（含逗號數字與含「的」的業務描述）。"""
    import rag_test_system_v14 as v14
    assert v14._extract_disc_value(q, label) == want


def test_disc_value_prefers_bracket_form():
    """【】形式優先於自然形式。"""
    import rag_test_system_v14 as v14
    q = "主要業務為【A】而非自然形式B的被投資公司"
    assert v14._extract_disc_value(q, "主要業務為") == "A"


@needs_vllm
def test_layer0_natural_investment_disambiguation():
    """
    自然問法（無【】）的投資題須由 Layer 0 確定性直答並選對被投資公司，
    不落到拓撲搜尋（LLM 生成）而選錯近似實體。
    """
    import json
    import rag_test_system_v14 as v14
    v14._load_all_compiled_graphs()
    cm = v14._build_company_map(v14.REPORTS_ROOT)
    d = json.load(open(ROOT / "questions/graph_routing_natural.json", encoding="utf-8"))
    q = next(x for x in d if x["id"] == "graph_nat_073")   # 所在地為香港
    md = q["metadata"]
    intent = {"route": "direct_lookup", "query_type": "entity_lookup",
              "companies": [md.get("company_name", "")],
              "quarters": [md.get("quarter", "")],
              "item_name": md.get("main_business", ""), "table_name": None}
    a = v14._gkg_pattern_direct_answer(q["question"], intent, cm)
    assert a is not None, "自然問法應由 Layer 0 命中，而非落到 LLM"
    assert a.strip() == q["expected_answer"].strip()


# ══════════════════════════════════════════════════════════════
# L. [P2 補強] 風險多標籤集合比對 + 科目定位修正（graph_nat_096）
# ══════════════════════════════════════════════════════════════
def test_risk_label_set_order_insensitive():
    """同一組風險標籤不同順序須判為相等（集合比對）。"""
    import rag_test_system_v14 as v14
    assert v14._score_one("供應鏈壓力;營運資金壓力",
                          "營運資金壓力;供應鏈壓力")["exact_match"]
    assert v14._score_one("營運資金壓力", "營運資金壓力")["exact_match"]


def test_risk_label_set_is_equality_not_loose_inclusion():
    """
    集合比對必須是**相等**而非鬆散包含——多輸出一個標籤不得判為對，
    否則會掩蓋 Layer 0 科目定位過寬（graph_nat_096 之成因）的 bug。
    """
    import rag_test_system_v14 as v14
    assert not v14._score_one("供應鏈壓力;營運資金壓力",
                              "營運資金壓力")["exact_match"]
    assert not v14._score_one("營運資金壓力", "匯率風險")["exact_match"]


def test_set_comparison_does_not_affect_numeric_answers():
    """非風險題（數值）不得受集合比對影響。"""
    import rag_test_system_v14 as v14
    assert v14._score_one("104,217,382", "104,217,382")["exact_match"]
    assert not v14._score_one("104,217,382", "104,217,383")["exact_match"]


@needs_vllm
def test_graph_nat_096_single_label_via_chinese_item():
    """
    graph_nat_096：router 只抽到英文科目名時，Layer 0 須改用問句中文科目
    定位，得到單一正確風險標籤，而非因英文短前綴匹配多科目而多標籤。
    """
    import json
    import rag_test_system_v14 as v14
    v14._load_all_compiled_graphs()
    cm = v14._build_company_map(v14.REPORTS_ROOT)
    q = next(x for x in json.load(
        open(ROOT / "questions/graph_routing_natural.json", encoding="utf-8"))
        if x["id"] == "graph_nat_096")
    intent = {"route": "direct_lookup", "query_type": "multi_hop_graph_reasoning",
              "companies": ["旺矽科技"], "quarters": ["114Q4"],
              "item_name": "Increase (decrease) in other payable",
              "table_name": "風險事件明細表"}
    a = v14._gkg_pattern_direct_answer(q["question"], intent, cm)
    assert a == q["expected_answer"], f"實得 {a!r}"


@pytest.mark.parametrize("dataset", [
    "questions/system_architecture_test_questions_100_v4.json",
    "questions/graph_routing_natural_100.json",
])
def test_dual_track_routing_matches_frozen_target_route(dataset):
    """
    [雙軌重構] 路由等價性回歸：確定性路由對凍結題庫的分流，須與資料集的
    `metadata.target_route` 完全一致。

    這是「凍結資料可直接沿用」的技術前提——若分流變了，逐題結果就不再可比。
    映射：target_route 前綴 graph_rag* → 軌道一之關係分支、direct_lookup* →
    軌道一之數值分支、其餘 → 軌道二。
    """
    import json
    import rag_test_system_v14 as v14

    path = ROOT / dataset
    if not path.exists():
        pytest.skip(f"找不到 {dataset}")
    ds = json.loads(path.read_text(encoding="utf-8"))
    items = ds if isinstance(ds, list) else ds.get("questions", [])
    assert items, "資料集為空"

    bad = []
    for it in items:
        tr = str(it.get("metadata", {}).get("target_route", ""))
        want = ("relation" if tr.startswith("graph_rag") else
                "numeric" if tr.startswith("direct_lookup") else "vector")
        route, rel = v14._derive_track_deterministic(
            it["question"], {"route": "semantic_rag", "query_type": "single"})
        assert route in v14._contract.ROUTE_VALUES
        got = ("vector" if route == "semantic_rag" else
               "relation" if rel else "numeric")
        if got != want:
            bad.append((it.get("id"), want, got))
    assert not bad, f"{len(bad)}/{len(items)} 題分流與凍結目標不符：{bad[:5]}"


# ══════════════════════════════════════════════════════════════
# L. 拒答行為：唯一性判定的兩種失敗成因必須可區分
# ══════════════════════════════════════════════════════════════
def _facts():
    import rag_test_system_v14 as v14
    facts = v14._load_facts_df(v14.REPORTS_ROOT)
    _std, _ent, ded = v14._prep_facts_for_gen(facts)
    return v14, facts, ded


def test_refusal_no_data_returns_specific_message():
    """
    候選集合為空 → 「找不到符合條件的資料」。

    公司與期別皆合法，只有科目不存在，故失敗必然發生在科目過濾；
    若此測試失敗，代表拒答路徑或訊息對照表被改動，§4.4.1 的拒答率即不可解讀。
    """
    v14, facts, ded = _facts()
    intent = {"route": "direct_lookup", "query_type": "single",
              "companies": ["台灣積體電路製造"], "quarters": ["114Q2"],
              "item_name": "碳權交易收入"}
    traces = []
    ans = v14._execute_direct_lookup_batch(intent, facts, ded, traces=traces)
    assert ans is None, f"不存在的科目不應有答案，實得 {ans!r}"
    assert traces and traces[0]["decision"] in ("no_item", "no_candidate")
    assert v14._REFUSAL_MESSAGES[traces[0]["decision"]] == "找不到符合條件的資料"


def test_refusal_ambiguous_returns_specific_message():
    """
    候選不唯一 → 「條件不足，請指定交易對象／欄位」。

    聯發科技 113Q1「研究發展費用」於母子公司間交易表中按交易對象分列數十筆，
    四鍵齊備後仍不唯一——此時缺的是題目條件，不是證據，故不得任選其一作答。
    """
    v14, facts, ded = _facts()
    trace = {}
    ans = v14._direct_lookup_flex(facts, ded, "聯發科技", "研究發展費用",
                                  "113Q1", col_hint="金額", trace=trace)
    assert ans is None, f"候選不唯一時必須拒答，實得 {ans!r}"
    assert trace["decision"] == "ambiguous"
    assert trace["n_unique"] > 1, "此案例應有多個相異候選值"
    assert v14._REFUSAL_MESSAGES["ambiguous"] == "條件不足，請指定交易對象／欄位"


def test_refusal_resolved_when_condition_supplied():
    """
    對照組：同題補上交易對象後應答出唯一值——證明拒答源於條件不足，
    而非系統答不出這類題目（否則「寧缺勿猜」只是答不出來的託辭）。
    """
    import rag_test_system_v14 as v14
    v14._load_all_compiled_graphs()
    cm = v14._build_company_map(v14.REPORTS_ROOT)
    q = ("根據關係人交易圖譜，【聯發科技】在【113Q1】，【聯發科技(股)公司】與"
         "【MediaTek Bangalore Private Limited】之間的【研究發展費用】交易金額是多少？")
    intent = {"route": "direct_lookup", "query_type": "entity_lookup",
              "_relation_query": True, "companies": ["聯發科技"],
              "quarters": ["113Q1"], "table_name": None,
              "item_name": "MediaTek Bangalore Private Limited"}
    assert v14._gkg_pattern_direct_answer(q, intent, cm) == "658,319"


def test_refusal_messages_are_recognised_as_refusals():
    """兩則拒答訊息都必須被評分器認定為拒答，否則 Precision／Recall 口徑會錯。"""
    import rag_test_system_v14 as v14
    for msg in v14._REFUSAL_MESSAGES.values():
        assert v14._is_refusal(msg), f"{msg!r} 未被認定為拒答"


def test_col_hint_key_is_position_independent():
    """欄位鎖定鍵不得依賴字首位置。

    解析器對多層表頭輸出「資產負債表Balance Sheet_2025年6月30日2025/6/30」；
    舊作法取前 12 字元會拿到「資產負債表Balance」——同表每欄皆同，鎖定失效，
    唯一性判定誤判為 ambiguous 而拒答（四臂對照實測 EM 100.0% → 8.0%）。
    """
    import rag_test_system_v14 as v14
    nested = "資產負債表Balance Sheet_2025年6月30日2025/6/30"
    flat = "2025年6月30日 2025/6/30"
    assert v14._col_hint_key(nested) == "2025年6月30日"
    assert v14._col_hint_key(flat) == "2025年6月30日"
    # 兩種格式必須推出同一個鍵，否則同一題會因語料格式而有不同結果
    assert v14._col_hint_key(nested) == v14._col_hint_key(flat)


def test_col_hint_key_separates_quarter_from_cumulative():
    """單季與累計欄的當期日期區間不同，鍵必須保留「至」區間才分得開。"""
    import rag_test_system_v14 as v14
    q = v14._col_hint_key("綜合損益表_2025年4月1日至6月30日2025/4/1To6/30")
    c = v14._col_hint_key("綜合損益表_2025年1月1日至6月30日2025/1/1To6/30")
    assert q == "2025年4月1日至6月30日"
    assert c == "2025年1月1日至6月30日"
    assert q != c


def test_col_hint_key_falls_back_to_legacy_behaviour_when_no_date():
    """標頭不含日期時，必須與修正前的 col_hint[:12] 逐字相同。

    這是本次修正得以安全套用於凍結資料的前提：只有含日期的標頭改變比對鍵，
    其餘一律沿用舊行為，故既有實驗結果不會位移（回放 160 題 0 差異）。
    """
    import rag_test_system_v14 as v14
    for h in ("主要管理階層薪酬_本期", "本期", "", "期末餘額",
              "很長的欄位標頭沒有任何日期資訊在裡面"):
        assert v14._col_hint_key(h) == h[:12], h


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
