# 程式碼地圖

> 每支程式的一行說明（取自檔頭 docstring）。`system/` 的程式實體上平鋪（腳本以 `ROOT = Path(__file__).parent` 定位專案根，請在 `system/` 內執行），下表為邏輯分組。
> 共 113 支程式。

## system｜核心系統（5）

問答引擎、API、Prompt 契約、評分器、修復群命名

| 檔案 | 用途 |
|---|---|
| [`rag_test_system_v14.py`](../system/rag_test_system_v14.py) | 多公司財報 RAG 四大模組整合測試系統  v14 |
| [`rag_api.py`](../system/rag_api.py) | RAGSystem — 三路混合 RAG 系統統一 API（v15 重構） |
| [`llm_contract.py`](../system/llm_contract.py) | LLM 輸入／輸出契約層（llm_contract.py） |
| [`moverscore_v2.py`](../system/moverscore_v2.py) | MoverScore 語意指標實作（評分器用，取自官方 v2） |
| [`fix_groups.py`](../system/fix_groups.py) | Fix 1–20 的五個修復群——命名的單一事實來源。 |

## system｜資料管線（7）

爬取 MOPS 財報 → 解析寬表與 Fact 索引 → 四大關係圖譜

| 檔案 | 用途 |
|---|---|
| [`crawl_supply_chain.py`](../system/crawl_supply_chain.py) | 爬取櫃買中心半導體產業鏈 D000 各步驟台灣公司，並輸出三個 TXT： |
| [`html_downloadv2.py`](../system/html_downloadv2.py) | 依執行目錄下 companies.txt 的股票代號，自 MOPS 下載指定年季財報 HTML |
| [`craw_pdf.py`](../system/craw_pdf.py) | 爬下 pdf 資料 |
| [`deal_html_datav2_strip_company_suffix.py`](../system/deal_html_datav2_strip_company_suffix.py) | 財報 HTML/iXBRL → 二維寬表 CSV 與長格式 Fact 索引（表格修復、附註抽取、公司名後綴正規化） |
| [`normalize_wide_csv_headers.py`](../system/normalize_wide_csv_headers.py) | 寬表欄名正規化：把現行解析器的巢狀表頭還原為檢索層預期的扁平格式 |
| [`build_all_graphs_merged_all_targets.py`](../system/build_all_graphs_merged_all_targets.py) | 整合建圖：投資／關係人交易／產業鏈／風險事件四大圖譜之節點與邊 CSV，可選匯入 Neo4j |
| [`tw_semiconductor_supply_chain_stock_codes.txt`](../system/tw_semiconductor_supply_chain_stock_codes.txt) | 櫃買中心半導體產業鏈各階段公司代號（crawl_supply_chain.py 產出） |

## system｜端到端評測與統計（5）

資料集重跑、前後比較、雙軌統計合併

| 檔案 | 用途 |
|---|---|
| [`rerun_after_dataset_fix.sh`](../system/rerun_after_dataset_fix.sh) | 資料集修正後之重跑腳本 |
| [`rerun_final.sh`](../system/rerun_final.sh) | 最終重跑：把 A/B/C 三欄補齊到「最終版資料集 × 最終版系統」 |
| [`rerun_with_fix16.sh`](../system/rerun_with_fix16.sh) | Fix 16（關係人交易「對手方＋科目為主鍵、投影金額欄」）之重跑 |
| [`compare_rerun.py`](../system/compare_rerun.py) | 資料集修正前後之重跑結果比較（compare_rerun.py） |
| [`report_dual_track.py`](../system/report_dual_track.py) | 確定性雙軌架構：凍結資料之統計合併與等價性檢核 |

## system｜Held-out 預註冊評測（17）

產生 → 驗收 → 凍結 → 執行 → 報告 → 修訂登錄

| 檔案 | 用途 |
|---|---|
| [`build_heldout_twins.py`](../system/build_heldout_twins.py) | Held-out 孿生評測集生成器（build_heldout_twins.py） |
| [`build_heldout_ambig_rp.py`](../system/build_heldout_ambig_rp.py) | 關係人列舉分層產生器（第三份 held-out 之候選歧義分層） |
| [`verify_heldout.py`](../system/verify_heldout.py) | Held-out 孿生集驗收（verify_heldout.py） |
| [`verify_heldout2_ambig.py`](../system/verify_heldout2_ambig.py) | 候選歧義分層之獨立驗收（verify_heldout2_ambig.py） |
| [`freeze_heldout_manifest.py`](../system/freeze_heldout_manifest.py) | Held-out 評測預註冊凍結（freeze_heldout_manifest.py） |
| [`freeze_heldout2_manifest.py`](../system/freeze_heldout2_manifest.py) | 第二份 held-out 之預註冊凍結（freeze_heldout2_manifest.py） |
| [`freeze_heldout3_manifest.py`](../system/freeze_heldout3_manifest.py) | 第二份 held-out 之預註冊凍結（freeze_heldout3_manifest.py） |
| [`amend_manifest.py`](../system/amend_manifest.py) | amend_manifest.py — 預註冊 manifest 的「凍結後修訂」登錄 |
| [`amend_heldout2_manifest.py`](../system/amend_heldout2_manifest.py) | amend_heldout2_manifest.py — 第二份 held-out 預註冊 manifest 的凍結後修訂登錄 |
| [`amend_heldout3_manifest.py`](../system/amend_heldout3_manifest.py) | amend_heldout3_manifest.py — 第二份 held-out 預註冊 manifest 的凍結後修訂登錄 |
| [`report_heldout.py`](../system/report_heldout.py) | Held-out vs dev 對照報告（report_heldout.py） |
| [`report_heldout_ambig.py`](../system/report_heldout_ambig.py) | 候選歧義分層（第二份 held-out）之評分與報告。 |
| [`heldout_contamination.py`](../system/heldout_contamination.py) | Held-out 題庫污染偵測與敏感度分析（heldout_contamination.py） |
| [`heldout_limitations.py`](../system/heldout_limitations.py) | Held-out 結果之限制分析（heldout_limitations.py） |
| [`run_heldout_eval.sh`](../system/run_heldout_eval.sh) | ═══════════════════════════════════════════════════════════════════════ |
| [`run_heldout2_eval.sh`](../system/run_heldout2_eval.sh) | ═══════════════════════════════════════════════════════════════════════ |
| [`run_heldout3_eval.sh`](../system/run_heldout3_eval.sh) | 第三份 held-out（關係人列舉分層）評測。與前兩份同組態，什麼旗標都不設。 |

## system｜消融與對照實驗（18）

證據格式、比率算術、外部模型、跨產業、延遲

| 檔案 | 用途 |
|---|---|
| [`benchmark_cross_industry_em.py`](../system/benchmark_cross_industry_em.py) | 跨產業準確率實測（非半導體三家，114Q2，75 題） |
| [`benchmark_cross_industry_feasibility.py`](../system/benchmark_cross_industry_feasibility.py) | 跨產業可行性檢核（只驗管線跑得通，不宣稱準確率） |
| [`benchmark_evidence_format.py`](../system/benchmark_evidence_format.py) | 證據格式受控消融（A／B／C） |
| [`benchmark_gemini_external_baseline.py`](../system/benchmark_gemini_external_baseline.py) | 實驗二補充：外部強模型對照組（Gemini-2.5-flash） |
| [`benchmark_graph_seconds.py`](../system/benchmark_graph_seconds.py) | 圖譜查詢秒數對比測試 |
| [`benchmark_parallel_ablation.py`](../system/benchmark_parallel_ablation.py) | 實驗二補充消融：圖譜 ＋ 向量「真並行」餵入（Graph + Vector True-Parallel Ablation） |
| [`benchmark_ratio_cross_company.py`](../system/benchmark_ratio_cross_company.py) | 跨公司比率比較消融：Pipeline A（LLM 算術）vs Pipeline B（確定性代數） |
| [`benchmark_ratio_gemini.py`](../system/benchmark_ratio_gemini.py) | 比率計算之外部效度對照：Pipeline C（Gemini 算術） |
| [`benchmark_ratio_pipelines.py`](../system/benchmark_ratio_pipelines.py) | 衍生比率指標計算：Pipeline A（LLM 算術）vs Pipeline B（確定性代數） |
| [`benchmark_refusal_probe.py`](../system/benchmark_refusal_probe.py) | 拒答行為之針對性實測（讓「拒答率」成為可解讀的實驗指標） |
| [`benchmark_relation_branch.py`](../system/benchmark_relation_branch.py) | 關係事實直查之候選收斂分支稽核。 |
| [`pool_evidence_format.py`](../system/pool_evidence_format.py) | 證據格式消融：跨題組彙整與統計檢定 |
| [`selfreport_validity.py`](../system/selfreport_validity.py) | A 組自報定位效度：沿用 pool_evidence_format.localized() 之判準， |
| [`report_gemini_external_baseline.py`](../system/report_gemini_external_baseline.py) | 實驗二外部對照組評測報告產生器 |
| [`report_cross_industry_em.py`](../system/report_cross_industry_em.py) | 跨產業準確率：四臂對照彙整 |
| [`verify_cross_industry_gold.py`](../system/verify_cross_industry_gold.py) | 跨產業金標之獨立驗證：以原始 HTML 的行內 XBRL 標記為準 |
| [`trace_ratio_demo.py`](../system/trace_ratio_demo.py) | 口語比率題的內部步驟追蹤（口試備審用實機畫面） |
| [`demo_fix16_single_multi.py`](../system/demo_fix16_single_multi.py) | Fix 16 單筆／多筆實測：關係人交易題並未被限制成只能回一筆 |

## system｜稽核與診斷（17）

金標稽核修復、歧義率、解析層核對、人工複核、強健性

| 檔案 | 用途 |
|---|---|
| [`audit_datasets.py`](../system/audit_datasets.py) | 資料集金標稽核（audit_datasets.py） |
| [`fix_datasets.py`](../system/fix_datasets.py) | 資料集金標修正（fix_datasets.py） |
| [`build_canonical_v4.py`](../system/build_canonical_v4.py) | 建立 canonical 資料集 v4（prompt_audit_issues.txt §26 / §27 / §29） |
| [`audit_pinned_column.py`](../system/audit_pinned_column.py) | D12 稽核：題幹釘住「非當期欄」（audit_pinned_column.py） |
| [`audit_source_table_heterogeneity.py`](../system/audit_source_table_heterogeneity.py) | 原始申報表異質性稽核：為什麼實體資訊需要先編譯成圖譜 |
| [`audit_track_exclusivity.py`](../system/audit_track_exclusivity.py) | 三路互斥性稽核：直查軌與圖譜軌能答對的題目是否重疊 |
| [`measure_relation_ambiguity.py`](../system/measure_relation_ambiguity.py) | 關係事實直查（軌道一 b 分支）之**候選歧義率**量測。 |
| [`parser_provenance_check.py`](../system/parser_provenance_check.py) | 解析層抽樣核對 v2：處理跨公司／跨季度之複合金標。 |
| [`make_gold_verification_sheet.py`](../system/make_gold_verification_sheet.py) | 金標人工抽樣核對清單（make_gold_verification_sheet.py）— B1–B3 |
| [`ingest_gold_verification.py`](../system/ingest_gold_verification.py) | 人工金標核對結果彙整（ingest_gold_verification.py） |
| [`make_targeted_manual_review_packets.py`](../system/make_targeted_manual_review_packets.py) | Produce three targeted human-review packets requested for the oral-defense audit. |
| [`gen_robustness_subset.py`](../system/gen_robustness_subset.py) | 建置「強健性與分流驗證子集」： |
| [`score_robustness_subset.py`](../system/score_robustness_subset.py) | 強健性與分流驗證子集評分（正式版）：分流／拒答／歧義偵測分開報告。 |
| [`track2_diagnosis_probe.py`](../system/track2_diagnosis_probe.py) | 軌道二拒答成因診斷探針（不修改系統，僅離線重問）。 |
| [`analyze_colloq_base_failures.py`](../system/analyze_colloq_base_failures.py) | 口語化基線 100 題（含提示版）失分歸因分析 |
| [`make_graphnat_before_after.py`](../system/make_graphnat_before_after.py) | 產生 Layer 0 自然語句補強之 before/after 對照檔（§3.13 引用來源）。 |
| [`audit_461_readonly_checks.py`](../system/audit_461_readonly_checks.py) | Read-only diagnostics: no model calls, no edits to system/data/results/deck. |

## system｜論文插圖產生（12）

架構圖、流程圖、圖表、實機截圖重拍

| 檔案 | 用途 |
|---|---|
| [`render_thesis_figures.py`](../system/render_thesis_figures.py) | 論文用架構圖產生器：把 THESIS.md 內的 mermaid 流程圖轉為可插入 Word 的 PNG。 |
| [`render_fact_views_diagram.py`](../system/render_fact_views_diagram.py) | 繪製「數值事實索引之三視圖切分」圖。 |
| [`render_pipeline_flowchart.py`](../system/render_pipeline_flowchart.py) | 查詢管線流程圖（三軌調度與降級鏈） |
| [`render_ratio_screenshot.py`](../system/render_ratio_screenshot.py) | 把「口語比率題」的真實終端輸出渲染成投影片用的畫面圖 |
| [`render_report_anatomy.py`](../system/render_report_anatomy.py) | 產生「財報實際長什麼樣」標註圖（口試簡報用） |
| [`render_report_anatomy_html.py`](../system/render_report_anatomy_html.py) | 產生「財報實際長什麼樣」標註圖（MOPS HTML 版） |
| [`make_defense_charts.py`](../system/make_defense_charts.py) | 口試簡報用圖表產生器：全部數值直接讀取評測結果檔，不硬編。 |
| [`make_case_screenshots.py`](../system/make_case_screenshots.py) | 由 reports_html_copy 的原始 iXBRL 財報，產生四個錯答案例的佐證截圖。 |
| [`reshoot_fig411_relation_lookup.py`](../system/reshoot_fig411_relation_lookup.py) | 重拍圖 4-11：關係事實直查之實際問答畫面 |
| [`reshoot_fig414_insufficient.py`](../system/reshoot_fig414_insufficient.py) | 重拍圖 4-14：條件不足之拒答 |
| [`reshoot_fig416_fallback.py`](../system/reshoot_fig416_fallback.py) | 重拍圖 4-16：查表未命中後降級至向量軌 |
| [`reshoot_fig417_multi_answer.py`](../system/reshoot_fig417_multi_answer.py) | 重拍圖 4-17：關係事實直查之多答案（全列並列）輸出 |

## system｜前端（4）

`rag_frontend/`：問答前端（Flask，port 5002）；`neo4j_graph_demo/`：圖譜渲染效能對照（port 5001）。

| 檔案 | 用途 |
|---|---|
| [`system/rag_frontend/app.py`](../system/rag_frontend/app.py) | 客戶問答前端（確定性雙軌展示）— v15 重構版 |
| [`system/neo4j_graph_demo/app.py`](../system/neo4j_graph_demo/app.py) | ── Neo4j 連線設定 ───────────────────────────────────────────────────────────── |
| [`system/neo4j_graph_demo/questions.py`](../system/neo4j_graph_demo/questions.py) | ── 測試問題庫 ──────────────────────────────────────────────────────────────── |
| [`system/neo4j_graph_demo/run_render_benchmark.py`](../system/neo4j_graph_demo/run_render_benchmark.py) | 無頭瀏覽器自動執行「渲染方式對照實驗」 |

## system｜題庫生成器（8）

| 檔案 | 用途 |
|---|---|
| [`system/questions/generators/generate_arch100_v2.py`](../system/questions/generators/generate_arch100_v2.py) | 100 題架構測試集消歧生成器 |
| [`system/questions/generators/generate_colloquial_natural_100.py`](../system/questions/generators/generate_colloquial_natural_100.py) | 純口語化測試資料集生成器（100 題） |
| [`system/questions/generators/generate_colloquial_v2.py`](../system/questions/generators/generate_colloquial_v2.py) | 口語測試集消歧生成器 |
| [`system/questions/generators/generate_cross_industry_gold.py`](../system/questions/generators/generate_cross_industry_gold.py) | 跨產業金標生成器（非半導體三家，114Q2） |
| [`system/questions/generators/generate_graph_routing_natural_100.py`](../system/questions/generators/generate_graph_routing_natural_100.py) | 自然語句路由大規模評測集生成器（graph_routing_natural_100） |
| [`system/questions/generators/generate_ratio_cross_company.py`](../system/questions/generators/generate_ratio_cross_company.py) | 跨公司比率比較測試資料集生成器（實驗七延伸） |
| [`system/questions/generators/generate_ratio_questions.py`](../system/questions/generators/generate_ratio_questions.py) | 衍生比率指標測試資料集生成器（Fix 14 專用） |
| [`system/questions/generators/generate_wrong_questions_v2.py`](../system/questions/generators/generate_wrong_questions_v2.py) | 修正版錯題資料集生成器 |

## system｜測試（2）

`python3 -m pytest -q tests`（113 項，含 N01–N36 negative cases）

| 檔案 | 用途 |
|---|---|
| [`system/tests/test_negative_cases.py`](../system/tests/test_negative_cases.py) | Negative Test Cases（對應 prompt_audit_issues.txt §七） |
| [`system/tests/test_negative_cases_p1.py`](../system/tests/test_negative_cases_p1.py) | Negative Test Cases N05–N36（prompt_audit_issues.txt §七 + §九） |

## baseline_pure_rag｜27B 純向量 RAG 與否證實驗（14）

| 檔案 | 用途 |
|---|---|
| [`baseline_pure_rag/_encode_m3.py`](../baseline_pure_rag/_encode_m3.py) | 以 BAAI/bge-m3 對語料 chunk 預先編碼並快取（檢索臂實驗用） |
| [`baseline_pure_rag/audit_funnel.py`](../baseline_pure_rag/audit_funnel.py) | 分層衰減鏈（三層漏斗）：在**線上管線**上量測，非以金標模擬 |
| [`baseline_pure_rag/audit_retrieval_arms.py`](../baseline_pure_rag/audit_retrieval_arms.py) | 檢索臂消融：換更強的嵌入模型或加上字面檢索，能否補上「表級鑑別」？ |
| [`baseline_pure_rag/audit_retrieval_ceiling.py`](../baseline_pure_rag/audit_retrieval_ceiling.py) | 檢索端稽核：低分到底是「向量庫沒有這筆資料」還是「純語意排序排不上來」？ |
| [`baseline_pure_rag/benchmark_bm25_27b.py`](../baseline_pure_rag/benchmark_bm25_27b.py) | 補測：把檢索端由稠密向量換成 BM25，其餘一切不變，量端到端 EM |
| [`baseline_pure_rag/benchmark_m3_27b.py`](../baseline_pure_rag/benchmark_m3_27b.py) | 補測：把檢索端由稠密向量換成 BM25，其餘一切不變，量端到端 EM |
| [`baseline_pure_rag/benchmark_pure_rag_27b.py`](../baseline_pure_rag/benchmark_pure_rag_27b.py) | 純向量 RAG baseline（27B 大模型）— version10 規格書實作 |
| [`baseline_pure_rag/benchmark_purerag_4b.py`](../baseline_pure_rag/benchmark_purerag_4b.py) | 補上 2×2 之第四格：純 RAG（無過濾、無規則）× 生成端 4B，題組同為 held-out 130 題 |
| [`baseline_pure_rag/benchmark_track1_off.py`](../baseline_pure_rag/benchmark_track1_off.py) | 軌道一封住 × 嵌入模型消融（2×2 的缺角） |
| [`baseline_pure_rag/benchmark_track1_off_27b.py`](../baseline_pure_rag/benchmark_track1_off_27b.py) | 補上設計矩陣缺角：軌道一封住 × 生成端 4B vs 27B（過濾已生效之條件下） |
| [`baseline_pure_rag/eval_arms_natural.py`](../baseline_pure_rag/eval_arms_natural.py) | BM25 的優勢是不是題目措辭給的？——自然口語題對照 |
| [`baseline_pure_rag/eval_retrieval_arms.py`](../baseline_pure_rag/eval_retrieval_arms.py) | 五條檢索臂在同一批 130 題上的第②③層命中率（無任何 metadata 過濾）。 |
| [`baseline_pure_rag/report_pure_rag_27b.py`](../baseline_pure_rag/report_pure_rag_27b.py) | version10 §9 結果報告：把 27B 純 RAG 的實測結果放進既有對照表 |
| [`baseline_pure_rag/run_pure_rag_27b.sh`](../baseline_pure_rag/run_pure_rag_27b.sh) | ═══════════════════════════════════════════════════════════════════ |

## legacy_v12｜前期系統（4）

實驗一（FinQA 基底模型選型）與實驗二（60 題檢索消融）所用程式。

| 檔案 | 用途 |
|---|---|
| [`legacy_v12/evaluate_finqa.py`](../legacy_v12/evaluate_finqa.py) | FinQA 評測腳本 |
| [`legacy_v12/evaluate_finqa_google.py`](../legacy_v12/evaluate_finqa_google.py) | FinQA 評測腳本 — Google Gemini 版 |
| [`legacy_v12/evaluate_finqa_phi.py`](../legacy_v12/evaluate_finqa_phi.py) | FinQA 評測腳本 |
| [`legacy_v12/rag_test_system_v12.py`](../legacy_v12/rag_test_system_v12.py) | 多公司財報 RAG 四大模組整合測試系統 |

