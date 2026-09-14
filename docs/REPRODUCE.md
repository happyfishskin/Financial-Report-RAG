# 環境與重跑

## 環境

| 項目 | 開發時規格 |
|---|---|
| GPU | NVIDIA RTX A4500 20 GB（Router 服務下限實測 5.67 GB） |
| Python | 3.10；套件版本鎖定見 `requirements.txt`（torch 2.9.1、chromadb 1.5.9、sentence-transformers 5.2.0、vllm 0.16.0） |
| LLM | vLLM 服務 `Qwen/Qwen3-4B-AWQ`；27B 對照用 Ollama 0.31.1 載入 `Qwen3.8-27B-UD-IQ3_XXS.gguf`（SHA256 見 `baseline_pure_rag/models/model_sha256.txt`） |
| 嵌入 | `BAAI/bge-small-zh-v1.5`（CPU）；對照 `BAAI/bge-m3` |
| 選用 | Neo4j（延遲基準、圖譜前端）、Playwright＋Chromium（渲染基準、截圖）、Noto Sans CJK TC 字型放 `system/.fonts/`（插圖） |

```bash
pip install -r requirements.txt
vllm serve Qwen/Qwen3-4B-AWQ --gpu-memory-utilization 0.85 --max-model-len 4096 --port 8000
export NEO4J_PASSWORD=...        # 只有 Neo4j 相關實驗需要
echo 'GEMINI_API_KEY=...' > system/.env   # 只有 Gemini 對照需要
```

## 1. 建立資料（約 3 GB，全部在 `system/` 下執行）

```bash
cd system
python3 crawl_supply_chain.py                     # 櫃買中心產業鏈公司清單（研究樣本來源）
python3 html_downloadv2.py                        # 依 companies.txt（30 家）自 MOPS 下載財報 HTML → reports_html_copy/
python3 deal_html_datav2_strip_company_suffix.py  # → reports_csv_output/（211,263 筆數值事實）
python3 build_all_graphs_merged_all_targets.py    # → 四個 *_graph_output/（--import-neo4j 可匯入 Neo4j）
python3 rag_test_system_v14.py build-index        # → vector_db/（30,887 chunks）
```

`html_downloadv2.py` 會下載程式內指定的年度與季度。MOPS 上的申報可能已更新，重爬的數值不保證與論文逐位元組相同。

`legacy_v12/` 的程式讀取同目錄下的 `reports_csv_output`、`vector_db`，可用 symlink 指向 `system/` 的資料：

```bash
cd legacy_v12 && ln -s ../system/reports_csv_output . && ln -s ../system/vector_db .
```

## 2. 使用與自我檢查

```bash
cd system
python3 -m pytest -q tests                        # 113 項
python3 rag_api.py "台積電114Q2營收多少？"
cd rag_frontend && python3 app.py                 # http://localhost:5002
cd ../neo4j_graph_demo && python3 app.py          # http://localhost:5001
```

換產業或換模型只改 `system/config/system_config.json`。修復層可用環境變數關閉：
`DISABLE_FIX16`、`DISABLE_FIX17`、`DISABLE_FIX19`、`DISABLE_FIX20`、`DISABLE_P1_ROUTING`。

## 3. 端到端評測

```bash
cd system
mkdir -p out
python3 rag_test_system_v14.py rag-query --dataset questions/heldout2/heldout_colloq_nat_100.json --output out/q.json
python3 rag_test_system_v14.py evaluate  --results out/q.json --output out/e.json   # EM／P／R／F1／BERTScore／MoverScore／ROUGE
```

## 4. 各實驗

實驗編號對應 [EXPERIMENTS.md](EXPERIMENTS.md)。多數腳本預設寫入 `results/`；不存在時會自動建立或需加 `--out`。

| 實驗 | 指令 |
|---|---|
| E01 FinQA 基底模型選型 | `cd legacy_v12 && python3 evaluate_finqa.py`（依 `readme_finQA.txt` 啟動各模型） |
| E02 60 題檢索消融 | `cd legacy_v12 && python3 rag_test_system_v12.py rag-query --dataset multi_company_test_dataset.json [--vector-only｜--llm-only｜--graph-only]` → `evaluate` |
| E03 真並行 | `cd system && python3 benchmark_parallel_ablation.py --output out/par.json` |
| E04 Gemini 生成端 | `python3 benchmark_gemini_external_baseline.py --arm vector｜parallel` |
| E07 證據格式 A／B／C | `python3 benchmark_evidence_format.py --dataset <題庫> --out out/ef` → `python3 pool_evidence_format.py` |
| E08 拒答探針 | `python3 benchmark_refusal_probe.py --out out/refusal` |
| E10 金標稽核與三欄重測 | `python3 audit_datasets.py` → `python3 fix_datasets.py` → `python3 audit_datasets.py --v3` → `bash rerun_final.sh` → `python3 compare_rerun.py` |
| E12 關係查詢延遲 | `python3 benchmark_graph_seconds.py`（需 Neo4j） |
| E13 前端渲染 | `cd neo4j_graph_demo && python3 run_render_benchmark.py --rounds 3 --expands 3`（需先啟動 app.py） |
| E14／E15 比率 | `python3 benchmark_ratio_pipelines.py`、`benchmark_ratio_gemini.py`、`benchmark_ratio_cross_company.py` |
| E17–E19 預註冊 held-out | `python3 build_heldout_twins.py --report` → `verify_heldout.py` → `freeze_heldout_manifest.py` → `bash run_heldout_eval.sh` → `report_heldout.py`（第二、三份為 `*2*`／`*3*` 版本） |
| E20 關係歧義率 | `python3 measure_relation_ambiguity.py`、`benchmark_relation_branch.py` |
| E21 跨產業四臂 | `python3 benchmark_cross_industry_feasibility.py` → `verify_cross_industry_gold.py` → `benchmark_cross_industry_em.py` → `report_cross_industry_em.py` |
| E22–E24 27B 純 RAG 與否證 | `cd baseline_pure_rag && ./run_pure_rag_27b.sh`（需停 vLLM 釋放 VRAM）；`audit_retrieval_ceiling.py`、`benchmark_m3_27b.py`、`benchmark_bm25_27b.py`、`benchmark_track1_off*.py`、`benchmark_purerag_4b.py`、`audit_funnel.py` |
| E26 強健性子集 | `python3 gen_robustness_subset.py` → 評測 → `score_robustness_subset.py`；`track2_diagnosis_probe.py` |
| E27 多跳壓測 | 設 `config/system_config.json` 之 `enable_online_graph_traversal: true`，評測 `questions/multihop_2hop_30.json` |

注意事項：
- 預註冊驗章（`freeze_*_manifest.py --check`）比對 `results/` 內的 manifest 與結果檔。這些凍結檔未收錄於本 repo，所以驗章要在完整封存版上執行。
- `measure_relation_ambiguity.py` 以行號追蹤 `rag_test_system_v14.py` 的挑列點。修改 v14 後須重新核對行號。
