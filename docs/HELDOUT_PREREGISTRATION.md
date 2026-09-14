# Held-out 孿生集評測預註冊（Pre-registration）

**凍結時間（UTC）**：2026-07-25T14:33:30+00:00  
**生成器**：`build_heldout_twins.py`（seed = 20260726）  
**驗收報告**：`heldout_verification.json`（SHA256 `d0d5c108a7592544…`）

## 1. 為什麼需要這份文件

論文現有主結果全部量測在「系統曾據以反覆修正」的同一批題目上（Fix 1–17 的每一次
迭代都看過那些題目），因此是**開發集分數**。孿生集把同一批模板與同一套金標方法論
套用到**從未被任何修正看過的題目實例**，用以量化開發集分數與泛化分數的落差。
預註冊的作用是讓「先宣告、後量測」可被第三方驗證：所有資料集與系統檔的 SHA256
在跑第一題之前即已寫死，任何事後更動都會使驗章失敗。

## 2. 受測資料集（凍結）

| 孿生集 | 題數 | dev 對應集 | dev EM | 預測 EM | 預測區間 |
|---|---:|---|---:|---:|---|
| `heldout_arch_100.json` | 100 | `system_architecture_test_questions_100_v4.json` | 97.0% | 88.0% | 80.0–95.0% |
| `heldout_colloq_100.json` | 100 | `customer_colloquial_test_questions_100_v2_v3.json` | 91.0% | 80.0% | 70.0–90.0% |
| `heldout_colloq_nat_100.json` | 100 | `customer_colloquial_natural_100.json` | 100.0% | 92.0% | 85.0–98.0% |
| `heldout_graph_cap_30.json` | 30 | `graph_capability_explicit.json` | 100.0% | 90.0% | 80.0–97.0% |
| `heldout_graph_nat_30.json` | 30 | `graph_routing_natural.json` | 100.0% | 83.0% | 70.0–95.0% |

各組題型組成與 dev 完全相同（逐型題數相等），僅抽樣實例不同：

- **架構測試 100 題**（`heldout_arch_100.json`）：direct_numeric_lookup 30、cross_company_compare 15、cross_period_compare 15、vector_table_retrieval 10、investment_graph 10、related_party_transaction_graph 8、supply_chain_graph 5、risk_event_graph 5、mainland_investment_graph 2
- **口語化 100 題（v2 鑑別版）**（`heldout_colloq_100.json`）：colloquial_single_metric 40、colloquial_company_compare 15、colloquial_period_compare 15、colloquial_investment_question 10、colloquial_related_party_question 10、colloquial_supply_chain_question 5、colloquial_risk_question 5
- **純口語自然 100 題**（`heldout_colloq_nat_100.json`）：colloquial_natural 100
- **圖譜能力題 30 題（固定路由）**（`heldout_graph_cap_30.json`）：investment_graph 10、related_party_transaction_graph 8、supply_chain_graph 5、risk_event_graph 5、mainland_investment_graph 2
- **圖譜自然路由題 30 題**（`heldout_graph_nat_30.json`）：investment_graph 10、related_party_transaction_graph 8、supply_chain_graph 5、risk_event_graph 5、mainland_investment_graph 2

### 預測理由（凍結前寫定）

- **架構測試 100 題** → 88.0%：題幹自帶【】結構化 token 與欄位標頭，col_hint／表鎖等修復屬模板層機制而非個案硬編，遷移性最高；扣分主要預期來自未見過的科目名變體與同名科目跨表並存。
- **口語化 100 題（v2 鑑別版）** → 80.0%：最依賴 Fix 12/13 的口語橋接（別名表、同義詞覆寫路由器）。別名表與同義詞是列舉式知識，對未列舉的口語說法無泛化保證，故預期落差最大。
- **純口語自然 100 題** → 92.0%：題型單一（10 種指標 × 公司 × 季度），金標生成即保證無歧義；公司別名與指標同義詞皆已列舉，主要風險為新期別的欄位型態。
- **圖譜能力題 30 題（固定路由）** → 90.0%：固定走圖譜、題幹保留來源提示與【】token，Layer 0 樣板命中率高；風險為新的鑑別欄位值與實體名稱變體（大小寫、法人後綴）。
- **圖譜自然路由題 30 題** → 83.0%：同時考驗自然路由與 Layer 0 的自然語句雙軌抽取（A1 補強）。該補強是針對 dev 這 30 題逐題除錯而成，最可能過擬合，故預測落差最大、區間最寬。

## 3. 主要假說

H_heldout：五組 held-out 孿生集之 EM 將**全部低於或等於**其 dev 對應集，且五組平均落差落在 5–15 pp。若平均落差 < 5 pp，視為既有修復具跨實例泛化能力；若 > 15 pp，視為既有分數主要來自對開發集的過擬合。任一組 held-out 高於 dev 亦須如實報告（代表 dev 該組偏難或抽樣變異）。

## 4. 分析計畫（凍結）

- **主要指標**：End-to-End EM（rag_test_system_v14.py evaluate 之 academic_metrics.em）
- **次要指標**：precision、recall、f1、refusal_count、BERTScore F1、retrieval hit_rate@5、answer_mode（路由）分布
- **分層報告**：每組另按 question_type 分層報告 EM，用以定位落差來源
- **統計註記**：n=100（三組）與 n=30（兩組）之二項標準誤分別約 ±3–5 pp 與 ±6–9 pp；解讀落差時須同時報告 Wilson 95% 區間，避免把抽樣噪音當成泛化落差。
- **禁止調參**：held-out 結果產生後，**不得**針對其失敗案例修改系統或題目。若因而決定修復，須：(1) 原封不動保留本次 held-out 數字並標為『修復前 held-out』；(2) 以新種子產生第二份孿生集重新量測；(3) 於論文中同時呈現兩次數字。
- **全量報告**：無論結果高低一律全量報告，不得只報表現好的組別；拒答（refusal）計為錯誤，不從分母剔除。
- **執行環境**：五組皆以最終版系統執行，不設任何 DISABLE_FIX* 旗標；vLLM 模型與 system_config.json 內容以本 manifest 之雜湊為準。

## 5. 資料集完整性雜湊

| 檔案 | SHA256 | bytes |
|---|---|---:|
| `heldout_arch_100.json` | `b768563965602070b433e89c348553996e2dc1179c60d9e8cc34750d1b533273` | 74,941 |
| `heldout_colloq_100.json` | `5273ecb2a1d7cbced79a2258fddc018fdb62197845c076ee764e81c78b070469` | 79,971 |
| `heldout_colloq_nat_100.json` | `47f5b5638367f8c70fec383d9a8165dc490d07bd36e16d2e5274c589dee283e8` | 67,396 |
| `heldout_graph_cap_30.json` | `dd2765b08a334f97bdd4a20416c7f7621d7672ebef9a71884ea2c4373cffe4c4` | 23,186 |
| `heldout_graph_nat_30.json` | `0ccf87ab0b77319871b10c466a63200fc07d7545aad0c025fe2fc4083bb22385` | 21,566 |

## 6. 受測系統雜湊

| 檔案 | SHA256 | bytes |
|---|---|---:|
| `rag_test_system_v14.py` | `2fbebf7b38b712e0289e5be9622aad73eb6411174a7f9a9db01759aee456e2f8` | 278,969 |
| `llm_contract.py` | `349e90d1835f60a380a6df92821d34e0450bb3ee6b08fddcc8c4cf6e3de3af12` | 37,201 |
| `config/system_config.json` | `03ef5ca5020d4360f2b600b648498748c826b0d97cbbc25594b99ac1e208194f` | 7,574 |
| `config/company_aliases.json` | `e06a5fcbce06ea0351c8f47af6e34c8b712818bbaa3b900bd0f2c029b8553133` | 916 |
| `build_heldout_twins.py` | `527b4a9c6fc54ad83f07d8327fab46755841bd533702a46c0941addb1dd77adb` | 53,484 |
| `verify_heldout.py` | `c4db28374c46b7cddff92ebed8d93117b3f7ad6e31990092e6d28955a62beca1` | 9,785 |
| `freeze_heldout_manifest.py` | `4186c61bdb8c9d76cc81ac698d00090e0aabf95f07ca4545439da691827d56dd` | 17,350 |

執行環境設定（取自 `system_config.json`）：

```json
{
  "llm_model": "Qwen/Qwen3-4B-AWQ",
  "vllm_url": "http://127.0.0.1:8000/v1",
  "embed_model": "BAAI/bge-small-zh-v1.5",
  "chroma_collection": "financial_reports_md"
}
```

## 7. 執行指令

```bash
bash run_heldout_eval.sh        # 五組各一次 rag-query + evaluate
python3 report_heldout.py       # 產生 dev vs held-out 對照表
```

> 分析前先跑 `freeze_heldout_manifest.py --check`；任一雜湊不符即代表資料集或系統在凍結後被更動，該次 held-out 結果作廢。
