#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════
# version10：純向量 RAG baseline（27B）全量評測
#
# 前置條件：GPU 需有 ≥13GB 可用 VRAM，故必須先停掉佔用 GPU 的 vLLM（Qwen3-4B）。
#   停止： pkill -f "vllm serve Qwen/Qwen3-4B-AWQ"
#   還原： cd ../system && \
#          vllm serve Qwen/Qwen3-4B-AWQ --gpu-memory-utilization 0.85 \
#                     --max-model-len 4096 --port 8000
# 本實驗完全不使用 vLLM／SLM Router，停掉不影響本實驗，只影響既有線上系統。
# ═══════════════════════════════════════════════════════════════════
set -euo pipefail
cd "$(dirname "$0")"

PY=${PY:-python3}
MODEL=qwen3.8-27b-iq3xxs

command -v ollama >/dev/null || { echo "✗ 找不到 ollama"; exit 1; }
curl -sf -m 5 http://127.0.0.1:11434/api/version >/dev/null || {
    echo "→ 啟動 ollama serve"; nohup ollama serve > models/ollama_serve.log 2>&1 &
    sleep 5; }
ollama list | grep -q "$MODEL" || {
    echo "→ 匯入 GGUF"; (cd models && ollama create "$MODEL" -f Modelfile); }

FREE=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits | head -1)
if [ "$FREE" -lt 12000 ]; then
    echo "⚠ 可用 VRAM 僅 ${FREE} MiB（<12000）；27B 將大量落在 CPU，速度不可用。"
    echo "  請先停掉 vLLM：pkill -f 'vllm serve Qwen/Qwen3-4B-AWQ'"
    [ "${FORCE:-0}" = "1" ] || exit 1
fi

# 主要評測（n=130）→ 再跑延伸評測（n=820）；--resume 可中斷續跑
$PY benchmark_pure_rag_27b.py --suite main --model "$MODEL" \
    --out results/pure_rag_27b_main  "$@" 2>&1 | tee results/run_main.log
$PY benchmark_pure_rag_27b.py --suite ext  --model "$MODEL" \
    --out results/pure_rag_27b_ext   "$@" 2>&1 | tee results/run_ext.log

echo "完成：results/pure_rag_27b_main.md 與 results/pure_rag_27b_ext.md"
