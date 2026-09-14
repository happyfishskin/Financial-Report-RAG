已經幫你把 **vLLM 啟動與管理的相關指令** 完美整合進手冊中。這包含之前跑 `Qwen3-4B-AWQ` 的啟動指令，以及多模型（包含投機解碼草稿模型組合）的配置與顯存清理方法。

你可以直接複製下方最新的文字，覆蓋或存入你的 `README.txt`：

```text
========================================================================
       FinQA 輕量大型語言模型（SLM）自動化評測工作流手冊
========================================================================
本專案用於在單張顯卡（如 NVIDIA RTX A4500）環境下，評測各類輕量化模型
在金融檢索增強生成（Finance RAG）任務下的準確度、格式遵從度與硬體 CP 值。

------------------------------------------------------------------------
一、 推理引擎服務管理（啟動 / 終止 / 清理顯存）
------------------------------------------------------------------------
【核心原則】：vLLM 與 Ollama 皆會常駐顯存。切換模型評測前，必須確保
前一個服務已完全終止，並透過 `nvidia-smi` 確認 VRAM 已完全釋放！

調整 1：vLLM 推理引擎管理
  1. 啟動基礎 Qwen3-4B-AWQ 服務：
    vllm serve Qwen/Qwen3-4B-AWQ \
        --quantization awq \
        --dtype auto \
        --gpu-memory-utilization 0.8 \
        --max-model-len 4096 \
        --enable-prefix-caching \
        --port 8000 \
        --trust-remote-code

  2. 啟動 Qwen3-4B-AWQ + 0.6B 草稿模型（投機解碼/加速組合）：
    vllm serve Qwen/Qwen3-4B-AWQ \
        --quantization awq \
        --dtype auto \
        --gpu-memory-utilization 0.80 \
        --max-model-len 8192 \
        --enable-prefix-caching \
        --port 8000 \
        --trust-remote-code \
        --speculative-config '{"model": "Qwen/Qwen3-0.6B", "num_speculative_tokens": 5, "method": "draft_model"}'

    3. microsoft/Phi-4-mini-instruct
        vllm serve "microsoft/Phi-4-mini-instruct" \
            --port 8000 \
            --gpu-memory-utilization 0.8 \
            --max-model-len 4096 \
            --trust-remote-code

    4. 啟動 FinGPT 微調過的模型 
    VLLM_USE_V1=0 VLLM_VERSION=v0 vllm serve meta-llama/Meta-Llama-3-8B-Instruct     --enable-lora     --lora-modules fingpt_llama3=FinGPT/fingpt-mt_llama3-8b_lora     --max-lora-rank 64     --port 8000     --gpu-memory-utilization 0.88     --max-model-len 4096
        


  4. 如何安全終止 vLLM 服務（釋放 VRAM）：
     vLLM 通常在前景執行，直接在該視窗按下 [Ctrl + C] 即可終止。
     若在背景執行，請執行：
     pkill -f vllm

調整 2：Ollama 推理引擎管理（Linux Systemd）
  1. 停止 Ollama 服務並完全釋放顯存：
     sudo systemctl stop ollama
  
  2. 啟動 Ollama 服務：
     sudo systemctl start ollama

  💡 快速卸載模型（不關閉服務）：
     ollama stop gemma4-12b:latest

------------------------------------------------------------------------
二、 基礎環境檢查
------------------------------------------------------------------------
1. 切換至 Python 虛擬環境：
   source financial_crawler/bin/activate

2. 檢查目前 GPU 顯存剩餘狀態：
   nvidia-smi

------------------------------------------------------------------------
三、 實驗一：FinQA 模型評測標準指令
------------------------------------------------------------------------
為最大化數學計算穩定性、消滅排隊造成的 `(空回覆)` 異常，全面採用
單發理智解碼模式（Top-1 Greedy Decoding, Temperature=0.2）。

1. 評測 Qwen3-4B-AWQ (經由 vLLM 原生引擎)
    python evaluate_finqa.py \
       --defense-base-url "http://127.0.0.1:8000/v1" \
       --defense-model "Qwen/Qwen3-4B-AWQ" \
       --sample-size 50 \
       --top-k 1 \
       --concurrency 1


2. 評測 Gemma-4-12B-QAT (經由 Ollama + 自動重試盾牌)
   python evaluate_finqa.py \
       --defense-base-url "http://127.0.0.1:11434/v1" \
       --defense-model "gemma4-12b:latest" \
       --sample-size 50 \
       --top-k 1 \
       --concurrency 1

3. 評測 Llama-3-8B-Finance-RAG (經由 Ollama 金融微調模型)
   python evaluate_finqa.py \
       --defense-base-url "http://127.0.0.1:11434/v1" \
       --defense-model "QuantFactory/llama3-finance" \
       --sample-size 50 \
       --top-k 1 \
       --concurrency 1

4. 評測 Phi-4-mini-instruct (經由 vLLM 引擎運行 FP16 完全體)
     python evaluate_finqa.py \
         --defense-base-url "http://127.0.0.1:8000/v1" \
         --defense-model "microsoft/Phi-4-mini-instruct" \
         --sample-size 50 \
         --top-k 1 \
         --concurrency 1

------------------------------------------------------------------------
四、 學術核心量化指標說明（論文引用依據）
------------------------------------------------------------------------
* 綜合 CP 值 (Accuracy-per-GB Metric)：
  公式：Accuracy (%) / 實際顯存消耗 (GB)
  理論依據參考 NeurIPS 混合精度量化與離群值保留理論（Tim Dettmers 等人）。
  用以評估模型在硬體資源受限之邊緣端部署時的「硬體投報率 (ROI)」。

* 數據分析發現：
  1. 通用模型（如 Qwen3）自帶強大程式碼與數學 Buff，計算準確度高。
  2. 領域對話微調模型（如 Llama3-Finance）極擅長金融黑話（BERTScore 頂尖）
     且格式遵從度極高（解析失敗率僅 4%），但易遭遇「災難性遺忘」導致
     純硬核數學計算力下滑。此發現可作為後續引入 GraphRAG 增強的完美論證。

========================================================================
                      [ 手冊完結。祝編譯順利，順利畢業！ ]
========================================================================

```