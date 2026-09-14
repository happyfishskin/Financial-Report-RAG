# 實驗總目錄

> 每項實驗列出：目的、題庫、執行腳本、結果檔、關鍵數字、論文位置。
> 數字以論文表格為準，並已逐項回查結果檔。
> 本 repo 的目錄對應開發時名稱：`system/`＝version8、`baseline_pure_rag/`＝version10、`legacy_v12/`＝version7。
> **逐題結果 JSON 與財報資料未收錄於本 repo**；下文列出的 `.json` 結果檔名供對照，Markdown 報表收錄於 [`docs/results/`](results/)。
> 評分一律為正規化後字串完全相同之 Exact Match（EM），除非另註。

## 總覽

| # | 實驗 | 關鍵結果 | 論文 |
|---|---|---|---|
| E01 | 基底模型選型（FinQA 50 題八模型） | Qwen3-4B-AWQ 68.0%（採用）；Gemini 80.0%；FinGPT 54.0% | §4.2 表 4-4 |
| E02 | 檢索策略消融（60 題五配置） | 路由分流 78.3% vs 純向量 6.7% | §4.3 表 4-5 |
| E03 | 圖譜＋向量真並行 | 20.0%（與純關係 21.7% 無顯著差） | §4.3.1 表 4-6 |
| E04 | 外部對照組 Gemini 生成端 | 純向量 6.7%→6.7%；並行 20.0%→16.7% | 附錄四 表 D-1 |
| E05 | 架構測試 100 題增益軌跡 | 12% → 76% → 90% → 100% | §4.4 表 4-8 |
| E06 | 三軌收斂為雙軌之等價性 | 602/602 關係題由 L0 答出，EM 影響 −0 題 | §4.4 表 4-8a |
| E07 | 證據格式受控消融 A／B／C | 15.3%／21.1%／94.2%（n=190） | §4.4.1 表 4-8b～d |
| E08 | 拒答行為針對性實測 | 查無資料 vs 多筆候選兩種成因可區分 | §4.4.1 表 4-8e |
| E09 | 口語化 100 題與純口語 100 題 | 純口語 59% → 100% | §4.5 表 4-9 |
| E10 | 金標機械化稽核與控制變因三欄重測 | 架構 v2：100 / 90 / 97%；D1–D11 | §3.10.1 表 3-11 |
| E11 | 關係題兩組分開報告、自然語句路由 100 題 | 自然路由 43.3% → 100% | §3.13–3.14 表 3-14、3-15 |
| E12 | 關係查詢引擎延遲（Neo4j vs 記憶體） | L0 12ms；圖譜計算佔端到端 0.37% | §4.6 表 4-10 |
| E13 | 前端渲染效能對照 | 首屏 10,173ms → 354ms（28.7×） | §4.7 表 4-11 |
| E14 | 衍生比率：SLM 算術 vs Python 代數 vs Gemini | 58% / 100% / 90% | §4.8 表 4-12、B-7 |
| E15 | 跨公司比率比較 | 字串 EM 22% vs 100% | §4.8.2 表 4-13 |
| E16 | 顯存下限探測 | util 0.23（5.67 GB）EM 0.970 與基準相同 | §4.1 表 4-2、4-3 |
| E17 | Held-out 第一份（五組孿生、預註冊） | 100／92／100／100／100% | 附錄二 表 B-1、B-2 |
| E18 | Held-out 第二份（新種子＋候選歧義分層） | 產業鏈 100%、投資 0%（皆命中預註冊）；Fix 19 後投資 100% | 附錄二 表 B-9～B-11 |
| E19 | Held-out 第三份（關係人列舉，非盲測） | 兩子分層 100% | 附錄二 表 B-11 |
| E20 | 關係軌候選歧義率與收斂分支 | 靜默任選 5.88%，held-out 0.0% | 表 4-14、B-8 |
| E21 | 跨產業可行性與四臂準確率 | 修正 col_hint 後四臂皆 100% | §3.11 表 3-13b、3-13c |
| E22 | 27B 純向量 RAG 對照（baseline_pure_rag） | 13.1% vs 4B＋路由 20.8%（p=0.041） | §4.11、附錄三 4. |
| E23 | 檢索端否證：天花板稽核、bge-m3、BM25、封住軌道一、分層衰減 | 最佳 36.1%，距直查 94.2% 差 58.1pp | §4.11–4.12、附錄三 5. |
| E24 | 2×2 因子：模型規模 × 結構化過濾 | 過濾 +15.4pp（顯著）、規模 +1.5pp（不顯著） | §4.11 |
| E25 | 金標人工抽樣核對、D12、解析層核對、人工複核包 | 24 題抽樣結案 22 正確 2 錯誤 | 附錄五 表 E-1、E-2 |
| E26 | 強健性與分流子集、軌道二拒答診斷、自報定位效度 | 見各報表 | 附錄三 2.–3. |
| E27 | 多跳圖推理壓測 | 30/30 進拓撲層，EM 0.0，19.16 s | 附錄二 表 B-6 |
| E28 | RAG 成本實測（token、延遲） | 證據 token 省 95.7%，總 prompt 只省 1.2% | 口試簡報表八 |

---

## 第一部分：模型與檢索策略（legacy_v12）

### E01　基底模型選型（FinQA 50 題）

- **目的**：選出在單卡 20 GB 上可部署、數值推理可接受的生成端。
- **設定**：FinQA 50 題，證據為標註者挑出的黃金支撐事實（非檢索），四層數值容差評分——**與本系統 EM 口徑不同，不可直接比較**（表 4-4a）。
- **腳本**：`legacy_v12/evaluate_finqa.py`、`evaluate_finqa_google.py`、`evaluate_finqa_phi.py`；說明 `legacy_v12/readme_finQA.txt`
- **結果檔**：`legacy_v12/results/*_ACC*.json`、`rerun_*.json`
- **結果**：gemini-2.5-flash 80.0%｜**Qwen3-4B-AWQ 68.0%（採用）**｜＋0.6B 投機解碼 68.0%｜Qwen3-8B 64.0%｜gemma4-12b 62.0%｜llama3-8B-finance 56.0%｜fingpt-llama3 54.0%｜phi-4-mini 40.0%。地端模型間差異皆未達顯著。

### E02　檢索策略消融（固定腳本 60 題）

- **目的**：證明單一檢索通道各有盲區，路由分流是前提。
- **題庫**：`legacy_v12/multi_company_test_dataset.json`（A 跨公司 14、B 跨季 12、C 實體 12、D 口語 12、E 圖譜 10）
- **系統**：`legacy_v12/rag_test_system_v12.py`
- **結果檔**（⚠ 檔名陷阱見下）：

  | 配置 | 結果檔 | EM | Hit@5 | 延遲 |
  |---|---|---:|---:|---:|
  | 純 SLM | `legacy_v12/rag_evaluation_v12_llm_only.json` | 1.7% | — | 2.36 s |
  | 純向量 | `system/results/rag_evaluation_v12_vector_only_TRUE.json` | 6.7% | 86.7% | 0.91 s |
  | 純關係直查 | `legacy_v12/rag_evaluation_v12_graph_only.json` | 21.7% | 88.3% | 4.19 s |
  | 圖譜＋向量真並行 | `system/results/rag_evaluation_v12_graph_vector_PARALLEL.json` | 20.0% | 86.7% | 5.52 s |
  | **路由分流** | `legacy_v12/rag_evaluation_v12_full.json` | **78.3%** | 95.0% | 3.37 s |

  ⚠ **version7 同名舊檔不可引用**：`legacy_v12/rag_evaluation_v12_graph_vector.json`（21.7%）是原 `--no-direct` 模式，因降級鏈在圖譜軌回傳後即 return，60 題 `retrieved_count` 全為 0，實為純圖譜之重跑（見 `benchmark_parallel_ablation.py` 檔頭）；`legacy_v12/rag_evaluation_vector_only_v12.json`、`rag_evaluation_v12_v.json` 的 EM 為 78.3%，與路由分流相同，並非純向量結果。論文使用的是 version8 內加註 `_TRUE`／`_PARALLEL` 的檔案（補算緣由見 `system/README.md`「實驗二」）。
- **雙軌重新歸類**：`python3 system/report_dual_track.py`（表 4-5a）

### E03　圖譜＋向量「真並行」

- **腳本**：`system/benchmark_parallel_ablation.py`（沿用 v12 檢索元件，輸出以 v12 evaluate 計分）
- **結果**：20.0%，相對純關係直查：圖譜對→並行錯 4 題、圖譜錯→並行對 3 題；McNemar p=1.000。多一條通道不增益，卻付出精確率、延遲與降級率。

### E04　外部對照組（Gemini-2.5-flash 生成端）

- **目的**：排除「換更強的生成模型即可」的解釋。
- **腳本**：`system/benchmark_gemini_external_baseline.py --arm vector|parallel`、`report_gemini_external_baseline.py`（需 `.env` 之 `GEMINI_API_KEY`）
- **結果檔**：`system/results/gemini_external_baseline.{json,md}`、`eval_gemini_{vector,parallel}.json`
- **結果**：純向量 6.7%→6.7%（p=1.000）；並行 20.0%→16.7%（p=0.625）；路由分流相對兩者 p<0.0001。

---

## 第二部分：最終系統主實驗（system）

### E05　架構測試 100 題增益軌跡

- **題庫**：`system/questions/system_architecture_test_questions_100.json`（原始）、`_100_v2.json`（鑑別版）
- **結果檔**：`legacy_v12/rag_evaluation_v12_arch100.json`（12%）→ `legacy_v12/rag_evaluation_v14_full.json`（扁平化，n=100，76%）→ `legacy_v12/test_eval_arch100_orig.json`（90%）→ `test_eval_arch100_v2.json`（100%）；Fix 16 後重跑 `system/results/rerun/eval_arch100_*`
- **結論**：Hit@1 97.65% 時 EM 僅 12%——瓶頸從不在檢索端。殘餘 10 題全為金標隨機列歧義，以消歧子句（v2）解決。

### E06　三軌收斂為雙軌之等價性檢核

- **腳本**：`system/report_dual_track.py`（讀凍結結果重新歸類，**不重跑推論**）；多跳標註 `results/answer_mode_and_multihop.json`
- **結果檔**：`system/results/dual_track_summary.{json,md}`
- **結果**：880 題中軌道一 842 題（95.7%，EM 94.9%）、軌道二 32 題（EM 96.9%）；602 道關係題 100% 由 L0 答出；真正落入線上拓撲層 6 題且 EM 全為 0 → 下架影響 −0 題。

### E07　證據格式受控消融（A 原始 Markdown／B 扁平化 K-V／C Fact 直查）

- **目的**：分離「扁平化」究竟在線上排版還是在離線建索引發揮作用。
- **腳本**：`system/benchmark_evidence_format.py`（三組共用同一批檢索結果，A／B 共用中性提示詞）、`pool_evidence_format.py`（彙整與 McNemar）、`selfreport_validity.py`
- **題庫**：dev 架構數值題 60、held-out 架構數值題 60、held-out 口語數值題 70
- **結果檔**：`system/results/evidence_format_ablation{,_ho_arch,_ho_colloq}.{json,md}`、`evidence_format_pooled.{json,md}`、`selfreport_validity.{json,md}`
- **結果**（n=190）：EM 15.3%／21.1%／**94.2%**；欄位定位率 28.9%／34.7%／98.4%；A vs B p=0.0074；B vs C 差 139 題 p<0.0001。
- **結論**：扁平化真正決定性的一次發生在**離線建索引**，不是線上把表格換排版給模型讀。
- ⚠ 做此類消融時，線上系統提示詞寫死「從 K-V 財報資料列中提取」會偏袒 B 組；已加 `_generate_answer_json(system_prompt=…)` 覆寫。

### E08　拒答行為之針對性實測

- **腳本**：`system/benchmark_refusal_probe.py` → `results/refusal_probe.{json,md}`
- **結果**：「碳權交易收入」→ no_item（候選 0）；聯發科「研究發展費用」→ ambiguous（候選 33）；補上交易對象後唯一命中 658,319。

### E09　口語化泛化

- **題庫**：`questions/customer_colloquial_test_questions_100{,_v2}.json`（口語化，含提示）、`customer_colloquial_natural_100.json`（純口語、零提示，生成器 `questions/generators/generate_colloquial_natural_100.py`）
- **結果檔**：`results/test_eval_colloq_nat_{base,fix,fix2,final,refactor,fix14}.json`、`colloq_base_failure_attribution.{json,md}`（腳本 `analyze_colloq_base_failures.py`）
- **結果**：純口語 59%（基線）→ 67%（Fix 12 市場別名）→ 92%（Fix 13 原句線索覆蓋）→ 99%（同義詞）→ **100%**（防劫持）。口語化 v2：83%（Fix 16/17 後 91%）。

### E10　金標機械化稽核與控制變因三欄重測

- **目的**：分離「修資料」與「修程式」各自的貢獻。
- **腳本**：`audit_datasets.py`（D1–D11 稽核，只讀）→ `fix_datasets.py`（輸出 `*_v3.json`，原檔不動）→ `rerun_after_dataset_fix.sh`／`rerun_with_fix16.sh`／`rerun_final.sh` → `compare_rerun.py`；`build_canonical_v4.py`（D10/D11）
- **結果檔**：`results/dataset_audit_{before,after}.{json,md}`、`dataset_fix_changelog.{json,md}`、`dataset_fix_impact.md`、`results/rerun/`
- **結果**（A 原始／B 修資料集／C ＋Fix 16/17）：架構 v2 100／90／97%；口語原始 30／51／60%；錯題 24 原始 58.3／45.8／75.0%；純口語對照組 100／—／100%。

### E11　關係題兩組分開報告、自然語句路由 100 題

- **題庫**：`questions/graph_capability_explicit.json`（固定走圖譜）、`graph_routing_natural.json`（30 題）、`graph_routing_natural_100.json`（生成器 `generate_graph_routing_natural_100.py`）
- **結果檔**：`results/graphnat_layer0_before_after.json`（`make_graphnat_before_after.py`）、`graph_routing_natural_100_result.json`、`results/rerun/eval_graphnat*`、`eval_gnat100.json`
- **結果**：能力題 100%；自然路由 E2E 43.3% → 100%；自然語句 100 題七題型 Router 與 E2E 皆 100%。

### E12　關係查詢引擎延遲

- **腳本**：`benchmark_graph_seconds.py`（Neo4j 需 `podman start my-neo4j`，bolt://localhost:7687）→ `results/benchmark_graph_seconds.json`
- **結果**：Neo4j 熱跑 17.5 ms；L0 12.0 ms（30/30 命中）；端到端 3.214 s，圖譜計算佔 0.37%。

### E13　前端渲染效能對照

- **程式**：`neo4j_graph_demo/app.py`（分頁「⏱ 自動對照實驗」）、`neo4j_graph_demo/run_render_benchmark.py`（playwright）
- **結果檔**：`neo4j_graph_demo/render_benchmark_result.json`、`results/render_benchmark_result.json`
- **結果**：首屏可互動 10,173 ms（全圖 2,000 節點）→ 354 ms（分層 30 家），傳輸 1,416.6 KB → 12.5 KB。

### E14　衍生比率：SLM 算術 vs Python 代數 vs 前沿模型

- **腳本**：`benchmark_ratio_pipelines.py`（A／B，檢索完全相同）、`benchmark_ratio_gemini.py`（C）；題庫生成 `questions/generators/generate_ratio_questions.py` → `questions/ratio_questions_50.json`（金標由分子分母直接計算）
- **結果檔**：`results/benchmark_ratio_pipelines.json`、`benchmark_ratio_gemini.json`
- **結果**：EM 58.0%（Qwen3-4B，截斷 12%，86.87 s）／**100%**（Python，0.0215 ms，快 4,036,876×）／90.0%（Gemini，1.629 s）。穩懋 114Q1 營業利益率出現正負號翻轉（真值 −6.06%，SLM 答 6.05%）。

### E15　跨公司比率比較

- **腳本**：`benchmark_ratio_cross_company.py`；題庫 `questions/ratio_cross_company_50.json`（`generate_ratio_cross_company.py`）
- **結果檔**：`results/benchmark_ratio_cross_company.json`、`results/rerun/eval_ratio_xc_e2e*.json`
- **結果**：兩比率皆精確 28% vs 100%；結論（誰高）正確 98% vs 100%；完整字串 EM 22% vs 100%。

### E16　顯存下限探測

- **結果檔**：`system/results/vram_min/`
- **結果**：`--gpu-memory-utilization 0.23`（整卡 5.67 GB，KV cache 4,112 tokens）可啟動，架構 100 題 EM 0.970，與基準 17.2 GB 配置相同；0.22 以下無法啟動。

---

## 第三部分：泛化與稽核（預註冊 held-out）

### E17　Held-out 第一份（2026-07-25 凍結）

- **目的**：主結果都量在反覆修正過的題目上（開發集分數），以同分布、實例互斥的孿生集先凍結後量測。
- **流程**：`build_heldout_twins.py`（seed 20260726，確定性）→ `verify_heldout.py`（分布／不重疊／D1–D11）→ `freeze_heldout_manifest.py`（SHA256 凍結）→ `run_heldout_eval.sh` → `report_heldout.py`；限制分析 `heldout_contamination.py`、`heldout_limitations.py`；修訂登錄 `amend_manifest.py`（A1–A4）
- **題庫**：`questions/heldout/`（架構 100、口語 100、純口語 100、關係能力 30、關係自然 30）
- **結果檔**：`results/heldout/`、`heldout_vs_dev.{json,md}`、`heldout_prereg_manifest.json`、`heldout_verification.json`、`heldout_contamination.json`、`heldout_limitations.json`、`heldout_frozenrun_20260725/`
- **結果**：dev → held-out：架構 97→100、口語 91→92、純口語 100→100、關係能力 100→100、關係自然 100→100；五組皆高於凍結前預測（88/80/92/90/83%）。
- ⚠ **限制**：孿生集金標規則把「列歧義」層整層排除，架構「97→100」是分層失配而非變強；同層比較才對（詳 `HELDOUT_PREREGISTRATION.md`、表 B-3）。
- ⚠ 口語組 8 題失敗全為比較題路由失效。

### E18　Held-out 第二份（2026-08-19 凍結，seed 20260820）

- **新增**：候選歧義分層 `questions/heldout2/heldout_ambig_60.json`（投資 30＋產業鏈 30），金標「全部列出才算對」（集合 EM）。
- **流程**：`build_heldout_twins.py --seed 20260820 --ambig --exclude-heldout --outdir questions/heldout2` → `verify_heldout2_ambig.py` → `freeze_heldout2_manifest.py` → `run_heldout2_eval.sh` → `report_heldout_ambig.py`；修訂 `amend_heldout2_manifest.py`（B1–B6）
- **結果檔**：`results/heldout2/`（含 `determinism_check.txt`：預設種子重跑與第一份逐位元相同）、`heldout2_prereg_manifest.json`
- **結果**：產業鏈集合 EM 100%（預測 85%）、投資 0%（預測 0%，命中）、覆蓋率 27.1%（預測 30%）；五組孿生 99／91／100／100／100%。字串 EM 對產業鏈只有 13.3%（順序造成低估）→ 此分層必須用集合 EM。
- **Fix 19（post-hoc）**：投資 0% → 100%（`ambig_report_posthoc_fix19.*`），既有 350 題關係題答案逐字相同。

### E19　Held-out 第三份（關係人列舉，seed 20260821）

- **流程**：`build_heldout_ambig_rp.py` → `freeze_heldout3_manifest.py` → `run_heldout3_eval.sh`；修訂 `amend_heldout3_manifest.py`（C1–C3）
- **結果檔**：`results/heldout3/`、`heldout3_prereg_manifest.json`
- **結果**：交易對象、交易科目兩子分層皆 100%。⚠ **非盲測**（能力後寫、凍結前跑過 1 題煙霧測試），引用時須一併陳述。

### E20　關係軌候選歧義率與收斂分支

- **腳本**：`measure_relation_ambiguity.py`（sys.settrace 重放凍結 intent，零 LLM；**釘住 v14 行號**）、`benchmark_relation_branch.py`
- **結果檔**：`results/relation_ambiguity.{json,md}`、`relation_branch_stats.json`
- **結果**：289 題抵達挑列點、靜默任選 17 題（5.88%）、held-out 四組 0.0%；關係人交易（Fix 16 三元主鍵）86 次 0 歧義。

### E21　跨產業可行性與準確率

- **腳本**：`benchmark_cross_industry_feasibility.py`（五項檢核）、`benchmark_cross_industry_em.py`、`verify_cross_industry_gold.py`（以 iXBRL 標記獨立驗證金標）、`report_cross_industry_em.py`、`pipeline/normalize_wide_csv_headers.py`（D 臂）
- **題庫**：`questions/cross_industry_gold_114Q2.json`、`cross_industry_gold_flat_114Q2.json`、`semi_control_gold_114Q2.json`、`semi_oldparse_gold_114Q2.json`（生成器 `generate_cross_industry_gold.py`）
- **隔離工作區**：`system/_cross_industry_probe/`、`_cross_industry_flat/`、`_semi_control_probe/`、`_semi_oldparse_probe/`
- **結果檔**：`results/cross_industry_*.json`、`semi_*_em.json`
- **結果**：長榮海運、鴻海、洋基工程三家；A（跨產業巢狀欄名）與 B（半導體巢狀）修正前皆 8.0%、修正後 100%；C、D（扁平）皆 100% → **無產業效應**，失效來自 col_hint 以欄名前 12 字元比對之隱性耦合（F6）。

---

## 第四部分：否證實驗（baseline_pure_rag）

### E22　27B 純向量 RAG

- **規格書**：`baseline_pure_rag/幫我直接 用傳統的rag 架構 做財報問答系統 模型用Qwen3.docx`
- **設定**：Qwen3.8-27B-UD-IQ3_XXS（Ollama，temp 0，seed 42，ctx 4096），bge-small-zh-v1.5，ChromaDB 全庫 Top-5、無任何 metadata 過濾，禁用全部路由／Fix／直查。
- **腳本**：`baseline_pure_rag/run_pure_rag_27b.sh`（需先停 vLLM 釋放 VRAM）、`benchmark_pure_rag_27b.py --suite main|ext`、`report_pure_rag_27b.py`
- **結果檔**：`baseline_pure_rag/results/pure_rag_27b_{main,ext,report}.{json,md}`
- **結果**：主要 130 題 EM 13.1%（Hit@5 21.5%、拒答 80.8%）；延伸 820 題 6.3%。同題配對 4B＋路由＋過濾 20.8% vs 27B 純 RAG 13.1%，McNemar p=0.041。寬鬆評分天花板 13.8%，有作答者 EM 68%——失分卡在檢索端。

### E23　檢索端否證

| 子實驗 | 腳本 | 結果檔 | 結果 |
|---|---|---|---|
| 檢索天花板稽核 | `audit_retrieval_ceiling.py` | `retrieval_ceiling_audit.json` | 金標覆蓋 190/190；全庫 Recall@5 20.0%、加公司期別過濾 62.6% |
| bge-m3 嵌入臂 | `benchmark_m3_27b.py`、`_encode_m3.py` | `m3_27b_colloqnat.json` | 純口語 200 題 33.0%（bge-small 4.5%，p=2.6×10⁻¹³） |
| BM25 字面臂 | `benchmark_bm25_27b.py` | `bm25_27b_{main,colloqnat}.json` | 自然語句 14.5%；題幹逐字引用來源者 40.8% |
| 檢索臂召回（五臂：bge-small／bge-m3／BM25／兩種混合） | `eval_retrieval_arms.py`、`eval_arms_natural.py`、`audit_retrieval_arms.py` | `retrieval_arms{,_natural}.json` | 自然口語 200 題表級命中（L2）bge-small 12.5%、bge-m3 74.0%、BM25 15.5%、m3＋BM25 71.0% |
| 封住軌道一 | `benchmark_track1_off.py`、`benchmark_track1_off_27b.py` | `track1_off_embed_ablation.json`、`track1_off_27b.json` | 4B＋bge-small 26.9%、4B＋bge-m3 **36.1%**、27B 27.7% |
| 分層衰減鏈 | `audit_funnel.py` | `funnel_layers.json` | 公司期別 100% → 表名 82.9% → 金標進提示詞 54.3%（全庫 74.3/37.1/37.1%） |

所有結果檔在 `baseline_pure_rag/results/`。**結論**：四條路徑最佳 36.1%，距確定性直查 94.2% 差 58.1pp，F1／F3 未被推翻；但嵌入模型確為未探索的改善空間，應列為限制。

### E24　2×2 因子：模型規模 × 結構化過濾（同 130 題）

| | 無過濾（純 RAG） | 過濾生效（封住軌道一） |
|---|---:|---:|
| **4B** | 11.5%（`pure_rag_4b_main.json`，`benchmark_purerag_4b.py`） | 26.9%（`track1_off_embed_ablation.json` A 臂） |
| **27B** | 13.1%（`pure_rag_27b_main.json`） | 27.7%（`track1_off_27b.json`） |

模型規模主效果 +1.5pp（p=0.625）／+0.8pp（p=1.000）不顯著；過濾主效果 +15.4pp（p=3.6×10⁻⁵）／+14.6pp（p=6.6×10⁻⁵）顯著；無交互作用。

---

## 第五部分：人工核對、強健性與其他

### E25　金標人工核對與解析層核對

- `make_gold_verification_sheet.py` → 人工填寫（`system/gold`，CSV 檔）→ `ingest_gold_verification.py` → `results/gold_verification_{sheet,result}.*`：24 題抽樣，補齊證據後正確 22、錯誤 2、存疑 0（表 E-1）。
- `audit_pinned_column.py` → `results/pinned_column_audit.json`：D12「題幹釘住非當期欄」（表 E-2）。
- `parser_provenance_check.py` → `results/parser_provenance_check.{json,md}`：以獨立解析器自 MOPS HTML 取值與金標逐分量比對。
- `make_targeted_manual_review_packets.py` → `results/manual_review_20260823/`：口試前三份針對性人工複核包。
- `audit_source_table_heterogeneity.py` → `results/source_table_heterogeneity.json`（表 3-7）；`audit_track_exclusivity.py` → `results/track_exclusivity.json`（表 3-5）。

### E26　強健性與分流子集、軌道二診斷

- `gen_robustness_subset.py` → `questions/robustness_routing_subset.json` → `score_robustness_subset.py` → `results/robustness_routing_{query,report}.*`
- `track2_diagnosis_probe.py` → `results/track2_diagnosis_probe.{json,md}`：敘述題 10 題因 JSON Schema 契約全數拒答，換敘述型契約後 9 題作答成功（F6）。

### E27　多跳圖推理壓測

- 題庫 `questions/multihop_2hop_30.json`；設 `config/system_config.json` 的 `enable_online_graph_traversal: true` 可重現。
- 結果：30/30 進拓撲層、EM 0.0、平均 19.16 s；28 題送入模型的脈絡不含答案（F4）。

### E28　RAG 成本實測

- 以 vLLM `/tokenize` 量得：傳統向量 RAG 每題證據 1,160 tokens；軌道一 0；加權 50 tokens（省 95.7%）；但 Router 系統提示獨佔 1,519 tokens，總 prompt 只省 1.2%。延遲 99% 在 Router 那次呼叫（direct_lookup 中位數 3.62 s，取值 12 ms）。
- 口試講法：「LLM 由讀資料降級為讀問題」——省的是幻覺與稽核成本，**不是** token 或速度。
- 出處：開發期間以 vLLM `/tokenize` 實測之紀錄；無獨立結果檔。

---

## 系統修復層 Fix 1–20（五個修復群）

單一事實來源：`system/fix_groups.py`；完整規則表見論文表 F-1、`system/TECHNICAL_REPORT.md` §4。
開關：`DISABLE_FIX16`、`DISABLE_FIX17`、`DISABLE_FIX19`、`DISABLE_FIX20` 環境變數。

| 修復群 | 對應管線階段 | Fix |
|---|---|---|
| 一、槽位補全 | 語意候選產生 | 1、5、6、13、14、17、18 |
| 二、體系對映 | 槽位正規化 | 12、13 |
| 三、候選收斂 | 候選集合過濾 | 2、7、8、9、11、16 |
| 四、唯一性閘門 | 唯一性判定 | 20 |
| 五、組裝與降級 | 回答或降級 | 3、4、10、14、15、19 |

（Fix 13、14 跨兩階段，為執行位置而非重複計數。）
