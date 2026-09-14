#!/usr/bin/env bash
# 第三份 held-out（關係人列舉分層）評測。與前兩份同組態，什麼旗標都不設。
set -u
PY=${PY:-python3}
cd "$(dirname "$0")"
OUT=results/heldout3; mkdir -p "$OUT"
echo "══ 驗章"
$PY freeze_heldout3_manifest.py --check || { echo "✗ 驗章失敗，中止。"; exit 1; }
ds=questions/heldout3/heldout_ambig_rp_40.json
$PY rag_test_system_v14.py rag-query --dataset "$ds" --output "$OUT/query_rp40.json" \
    > "$OUT/log_rp40.txt" 2>&1 || { echo "✗ query 失敗"; exit 1; }
$PY rag_test_system_v14.py evaluate --results "$OUT/query_rp40.json" \
    --output "$OUT/eval_heldout_ambig_rp_40.json" >> "$OUT/log_rp40.txt" 2>&1 \
    || { echo "✗ evaluate 失敗"; exit 1; }
$PY report_heldout_ambig.py --eval results/heldout3/eval_heldout_ambig_rp_40.json \
    --out results/heldout3/ambig_rp_report.json
