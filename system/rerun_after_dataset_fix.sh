#!/usr/bin/env bash
# 資料集修正後之重跑腳本
#
# 對「原始資料集」與「修正後 *_v3 資料集」以**同一份系統**各跑一次，
# 使前後差異只來自資料集本身（已發表數據來自較早的系統版本，直接相比會混淆變因）。
#
# 用法： bash rerun_after_dataset_fix.sh
set -u
PY=${PY:-python3}
cd "$(dirname "$0")"
mkdir -p results/rerun

run() {   # run <資料集> <輸出標籤>
  local ds="$1" tag="$2"
  local q="results/rerun/query_${tag}.json"
  local e="results/rerun/eval_${tag}.json"
  if [ -s "$e" ]; then echo "  ✓ 已存在，略過：$tag"; return; fi
  echo "══ [$tag] $ds"
  $PY rag_test_system_v14.py rag-query --dataset "$ds" --output "$q" \
      > "results/rerun/log_${tag}.txt" 2>&1 || { echo "  ✗ query 失敗，見 log_${tag}.txt"; return; }
  $PY rag_test_system_v14.py evaluate --results "$q" --output "$e" \
      >> "results/rerun/log_${tag}.txt" 2>&1 || { echo "  ✗ evaluate 失敗"; return; }
  $PY - "$e" <<'EOF'
import json,sys
d=json.load(open(sys.argv[1]))
a=d["summary"]["academic_metrics"]
print(f"  → EM {a['em']:.3f} ｜ P {a['precision']:.3f} ｜ R {a['recall']:.3f} ｜ "
      f"F1 {a['f1']:.3f} ｜ 拒答 {a['refusal_count']}")
EOF
}

echo "=== 架構 100 題 ==="
run questions/system_architecture_test_questions_100.json        arch100_orig_before
run questions/system_architecture_test_questions_100_v3.json     arch100_orig_after
run questions/system_architecture_test_questions_100_v2.json     arch100_v2_before
run questions/system_architecture_test_questions_100_v2_v3.json  arch100_v2_after

echo "=== 口語化 100 題 ==="
run questions/customer_colloquial_test_questions_100.json        colloq100_orig_before
run questions/customer_colloquial_test_questions_100_v3.json     colloq100_orig_after
run questions/customer_colloquial_test_questions_100_v2.json     colloq100_v2_before
run questions/customer_colloquial_test_questions_100_v2_v3.json  colloq100_v2_after

echo "=== 錯題回歸集 24 題 ==="
run questions/system_architecture_wrong_questions_dataset.json        wrong24_orig_before
run questions/system_architecture_wrong_questions_dataset_v3.json     wrong24_orig_after
run questions/system_architecture_wrong_questions_dataset_v2.json     wrong24_v2_before
run questions/system_architecture_wrong_questions_dataset_v2_v3.json  wrong24_v2_after

echo "=== 未受影響之對照組（稽核 0 缺陷，僅驗證系統未漂移） ==="
run questions/customer_colloquial_natural_100.json  colloq_nat100_control

echo "全部完成。"
