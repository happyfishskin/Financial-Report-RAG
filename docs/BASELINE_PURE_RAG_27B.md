# 純向量 RAG baseline（27B 大模型）

> 程式在 `baseline_pure_rag/`（開發時目錄名為 version10；文中 version8 即本 repo 的 `system/`）。原始規格書與逐題結果 JSON 未收錄。

規格書：`幫我直接 用傳統的rag 架構 做財報問答系統 模型用Qwen3.docx`

## 實驗目的

檢驗在**不使用** SLM 路由、Python 規則、Fix 1–20、Fact 直查與關係表的情況下，
較大模型搭配傳統向量 RAG 是否能可靠回答繁中財報問題。

研究問題：單靠「向量搜尋 Top-K 證據 ＋ 27B 模型生成」，能否解決財報數字的
**欄位與資料列定位**問題？

## 檔案

| 檔案 | 用途 |
|---|---|
| `benchmark_pure_rag_27b.py` | 純 RAG 主腳本（檢索 → 生成 → 評分） |
| `report_pure_rag_27b.py` | 產生規格書 §9 對照表 ＋ 同題逐題配對（McNemar） |
| `run_pure_rag_27b.sh` | 一鍵執行（含 ollama 啟動與 GGUF 匯入） |
| `models/Modelfile` | Ollama 匯入設定（num_ctx 4096 / temp 0 / seed 42） |
| `results/` | 輸出（`*.json` 全量逐題、`*.md` 報表、`*_checkpoint.json` 續跑點） |

## 為什麼是新腳本，不是改 `benchmark_evidence_format.py`

規格書明確要求。version8 的 `benchmark_evidence_format.py` 每題都會呼叫
`_llm_intent_router()`（SLM Router）與 `_enrich_intent_from_question()`（槽位補全），
再用抽出的公司代號與期別對 ChromaDB 做 **metadata 硬過濾**檢索。那是「有路由的
RAG」，不是純 RAG；沿用它會讓本實驗的前提失效。

本腳本只從既有系統借三樣**不含任何路由知識**的東西，以確保結果可與凍結資料比較：

1. `V._BGEEmbedder` —— 同一顆 `bge-small-zh-v1.5`，CPU 執行
2. `V._score_one` —— 既有 EM／數值一致評分器，逐字不動
3. `V._is_refusal` —— 既有拒答判定

向量庫路徑與 collection 名讀自 version8 的 `config/system_config.json`。

## 流程（規格書 §4）

```
原始使用者問題
  ↓ bge-small-zh-v1.5 向量化（不改寫、不擴充同義詞）
ChromaDB 全庫 Top-K=5 語意搜尋（where=None，無任何 metadata 過濾）
  ↓
原始 Markdown 財報片段（不做 K-V 扁平化）
  ↓
Qwen3.8-27B IQ3_XXS 生成一次（不重試、不二次檢索）
  ↓
既有 EM 評分器
```

## 明確排除（規格書 §5）

SLM Router／意圖 JSON、Python 路由覆核、Fix 1–20、公司別名表、
科目同義詞／比率本體論、metadata 公司／期別／表格硬過濾、
Fact 數值直查與關係事實直查、Python 算術、
查無資料後的第二次檢索／改寫問句／重試、依測試結果調整 Prompt／Top-K／模型設定。

模型只看得到「原始問題 ＋ Top-5 原始 Markdown 證據」。

## 固定設定（規格書 §3，不得依測試結果調整）

| 項目 | 值 |
|---|---|
| 生成模型 | `Qwen3.8-27B-UD-IQ3_XXS.gguf`（unsloth/Qwen3.8-27B-GGUF） |
| SHA256 | `c0b7c3038681ed2e3040456c1dd45f9858b6c2290bed172c70388a94874f3eee` |
| 檔案大小 | 10,934,860,704 bytes（10.93 GB） |
| 推論引擎 | Ollama 0.31.1（本機 GGUF 匯入） |
| Embedding | `BAAI/bge-small-zh-v1.5`，CPU |
| 向量庫 | ChromaDB `financial_reports_md`（30,887 chunks） |
| temperature / seed | 0 / 42 |
| context / 輸出 | 4,096 / 384 tokens |
| Top-K | 5 |

### 證據字元預算的取法

規格書要求模型看到 Top-5 證據，但沒給字元上限。若沿用既有消融 A 組的
4,000 字元，實測只有 2 個片段擠得進 prompt（約 1,300 tokens），4,096 的視窗
大半空著，等於偷偷把 Top-5 變成 Top-2——實測有題目就是因為金標片段被截掉而拒答。

故預算改由 context 視窗反推：`4096 − 384（輸出） − 200（樣板餘裕） = 3,512 tokens`，
本語料實測約 0.43 token/字元，取保守值 0.55 換算得 **6,400 字元**。
每題另記錄 `prompt_tokens`、`chunks_in_context` 與 `ctx_overflow` 供稽核。

## 評測資料（規格書 §7）

| 層級 | 題組 | n |
|---|---|---:|
| 主要評測 | `heldout/heldout_arch_100.json` ＋ `heldout/heldout_colloq_100.json` 的**數值題**（`target_route` 以 `direct_lookup` 開頭） | 60 ＋ 70 = **130** |
| 延伸評測 | `heldout`／`heldout2`／`heldout3` 三批全量，分題型報告 | 360 ＋ 420 ＋ 40 = **820** |

主要評測的 130 題與 `version8/results/evidence_format_ablation_ho_{arch,colloq}.json`
的 held-out 部分**完全同題**，可逐題配對比較。

## 執行

```bash
# 一鍵（自動起 ollama、匯入 GGUF、跑 main 再跑 ext）
./run_pure_rag_27b.sh

# 分開跑；中斷後加 --resume 續跑
python3 benchmark_pure_rag_27b.py --suite main --out results/pure_rag_27b_main
python3 benchmark_pure_rag_27b.py --suite ext  --out results/pure_rag_27b_ext --resume

# 產生 §9 對照表
python3 report_pure_rag_27b.py
```

需 `financial_crawler` conda 環境（chromadb ＋ torch）：
`python3`（conda 環境 financial_crawler）

### GPU 前置條件

27B IQ3_XXS 需約 13 GB VRAM。A4500 只有 20 GB，且既有線上系統的 vLLM
（`vllm serve Qwen/Qwen3-4B-AWQ --gpu-memory-utilization 0.85 --max-model-len 4096
--port 8000`）常駐佔用 18 GB，故跑本實驗前需先停掉 vLLM，跑完再以同一指令還原。
本實驗完全不使用 vLLM，停掉不影響本實驗，只影響既有線上系統。

## 實測結果（2026-09-02，RTX A4500 100% GPU offload）

執行環境：Ollama 0.31.1，27B 全部 11 GB 進 VRAM（`100% GPU`），VRAM 峰值 11,039 MiB /
20,470 MiB，平均延遲 2.3–2.5 s/題。950 題零生成錯誤、零 context 溢位
（最大 prompt 3,237 tokens < 3,712 上限），平均 3.9 個片段進視窗。

### 表一　系統對照（規格書 §9）

| 系統 | 路由／規則 | 證據形式 | 生成模型 | n | EM | Hit@5 | 拒答率 | 平均延遲 |
|---|---|---|---|---:|---:|---:|---:|---:|
| 純向量 RAG（既有） | 有既有設定 | Markdown | Qwen3-4B | 60 | 6.7% | 86.7% | 55.0% | 0.91s |
| **27B 純 RAG（本實驗）** | **無** | Top-5 Markdown（全庫、無過濾） | Qwen3.8-27B IQ3_XXS | 130 | **13.1%** | 21.5% | 80.8% | 2.5s |
| 確定性 Fact 直查 | Python 定位 | Fact | 不生成數值 | 190 | 94.2% | — | 0.0% | — |

延伸評測（n=820，三批 held-out 全量）：EM **6.3%**（52/820）、Hit@5 17.3%、拒答 87.0%。

### 檢索端稽核：低分不是向量庫缺料

`audit_retrieval_ceiling.py`（不呼叫 LLM，純檢索）對主要評測 130 題的 190 個
金標來源逐一檢查：

| 檢查 | 結果 |
|---|---|
| A. 金標 (公司,期別,表名) 是否存在於 collection | **190/190 = 100%**（平均 10.1 個 chunk） |
| B. 全庫語意搜尋的金標名次 | Recall@1 8.4%｜**Recall@5 20.0%**｜@20 35.3%｜@50 42.1%｜@200 46.3% |
| | **連 top-200 都排不進：53.7%（102/190）** |
| C. 同一庫加 company+quarter 硬過濾 | **Recall@5 62.6%**（@1 31.1%、@10 73.2%） |

結論：向量庫完整無缺料；失分來自**密集向量檢索排不出正確表格**。同一個庫、同一顆
embedder、同一個問題，只加上 metadata 硬過濾，Recall@5 就從 20.0% → 62.6%（三倍），
證明差異來自「純 RAG 不得使用 metadata 過濾」這個實驗設定本身。

機制解釋：財報表格在向量空間中近乎重複——「台灣光罩 113Q1 現金流量表」與
「台灣光罩 114Q2 財務成本」語意極相近，embedding 分不開**期別**與**表名**這兩個
離散維度，而財報數值的位置恰恰由這兩個維度決定。

附帶結論：加了過濾也只有 62.6%，離 Fact 直查的 94.2% 仍遠，說明本研究的貢獻不是
「加 metadata 過濾」而是確定性查表。

（C 的 62.6% 不可直接與既有系統 Hit@5 86.7% 相比：後者為 dev 60 題、含 query 改寫、
且採分級命中定義。乾淨對比是本稽核內部的 B vs C，同樣 190 個金標來源。）

### EM 是否過嚴？不是

| | MAIN n=130 | EXT n=820 |
|---|---:|---:|
| EM | 17（13.1%） | 52（6.3%） |
| EM=0 但數值一致（忽略格式） | **0** | 1 |
| EM=0 但含任一正確數字 | 1 | 5 |
| **換成最寬鬆評分的天花板** | **13.8%** | 7.0% |
| 拒答 | **105（80.8%）** | 713（87.0%） |
| 有作答者的 EM 率 | **68.0%**（17/25） | 48.6%（52/107） |

MAIN 唯一那題「EM=0 但沾到數字」經檢查是模型真的答錯（金標
`113Q4: 196,308 ｜ 114Q1: 34,951`，模型答 `196,308與413,239`），故實際可救 **0 題**。
低分來自 80.8% 拒答——模型字面輸出「找不到相關資料」，任何評分器（含 LLM judge）
都不可能算對；而拒答是正確行為，因為 Top-5 證據裡確實沒有該數字。
反之，有作答時 EM 達 68%，顯示失分卡在檢索端而非生成端。

### 研究問題的答案：否

1. **換大模型不解決定位問題。** 模型從 4B 放大到 27B，EM 只從 6.7% 到 13.1%，
   離確定性 Fact 直查的 94.2% 仍差約七倍。
2. **瓶頸在檢索端，不在生成端。** 既有系統 Hit@5 86.7% 是**因為有 metadata 硬過濾**；
   拿掉過濾改成全庫檢索後 Hit@5 崩到 21.5%，EM（13.1%）幾乎完全被 Hit@5 卡住。
   典型失敗樣態：問「現金流量表」的某科目，Top-5 全撈成同一家公司的「財務成本」表。
3. **規則的增益大於模型放大。** 同一批 130 題逐題配對：

   | 系統 | 路由／過濾 | 生成模型 | EM |
   |---|---|---|---:|
   | 既有受控消融 A 組 | SLM Router ＋ 公司／期別 metadata 硬過濾 | Qwen3-4B | 20.8%（27/130） |
   | 本實驗 27B 純 RAG | 無 | Qwen3.8-27B IQ3_XXS | 13.1%（17/130） |

   配對列聯表：兩者皆對 12｜僅 4B＋路由對 15｜僅 27B 純 RAG 對 5｜兩者皆錯 98；
   McNemar 精確檢定 **p = 0.041（顯著）**。
   註：此比較同時變動兩個因子（模型大小、有無路由與過濾），只能回答
   「換上 27B 並拿掉全部規則後整體是否站得住」，不能單獨歸因於模型大小。
4. **批次題在純 RAG 架構上做不到。** 跨公司比較與跨期比較全部 **EM 0%**、
   拒答率 83–100%——一次 Top-5 撈不齊兩家公司／兩個期別的來源。
   圖譜題與候選歧義題同樣接近全滅（多數題型 0%）。

## 結論界線（規格書 §10）

本實驗僅評估單一 27B、IQ3_XXS 量化模型在固定純 RAG 設定下的表現；結果不代表
所有大型模型或所有量化設定的能力。若大型模型提升 EM，僅表示其讀表能力較佳；
是否能取代確定性查表，仍須與相同 held-out 題組上的 Fact 直查結果比較。
