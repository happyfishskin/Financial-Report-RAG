#!/usr/bin/env bash
# Fix 16（關係人交易「對手方＋科目為主鍵、投影金額欄」）之重跑
#
# 跑兩組：
#   *_fix16   修正後資料集 ＋ Fix 16 系統
#   *_regress 原始資料集   ＋ Fix 16 系統（驗證 Fix 16 未使舊資料集退步）
set -u
PY=${PY:-python3}
cd "$(dirname "$0")"
mkdir -p results/rerun

run() {
  local ds="$1" tag="$2"
  local q="results/rerun/query_${tag}.json"
  local e="results/rerun/eval_${tag}.json"
  if [ -s "$e" ]; then echo "  ✓ 已存在，略過：$tag"; return; fi
  echo "══ [$tag] $ds"
  $PY rag_test_system_v14.py rag-query --dataset "$ds" --output "$q" \
      > "results/rerun/log_${tag}.txt" 2>&1 || { echo "  ✗ query 失敗"; return; }
  $PY rag_test_system_v14.py evaluate --results "$q" --output "$e" \
      >> "results/rerun/log_${tag}.txt" 2>&1 || { echo "  ✗ evaluate 失敗"; return; }
  $PY - "$e" <<'EOF'
import json,sys
a=json.load(open(sys.argv[1]))["summary"]["academic_metrics"]
print(f"  → EM {a['em']:.3f} ｜ P {a['precision']:.3f} ｜ R {a['recall']:.3f} ｜ "
      f"F1 {a['f1']:.3f} ｜ 拒答 {a['refusal_count']}")
EOF
}

echo "=== 修正後資料集 ＋ Fix 16 ==="
run questions/system_architecture_test_questions_100_v3.json         arch100_orig_fix16
run questions/system_architecture_test_questions_100_v2_v3.json      arch100_v2_fix16
run questions/customer_colloquial_test_questions_100_v3.json         colloq100_orig_fix16
run questions/customer_colloquial_test_questions_100_v2_v3.json      colloq100_v2_fix16
run questions/system_architecture_wrong_questions_dataset_v3.json    wrong24_orig_fix16
run questions/system_architecture_wrong_questions_dataset_v2_v3.json wrong24_v2_fix16

echo "=== 原始資料集 ＋ Fix 16（回歸驗證，應與 *_before 相同） ==="
run questions/system_architecture_test_questions_100_v2.json         arch100_v2_regress_fix16
run questions/customer_colloquial_test_questions_100_v2.json         colloq100_v2_regress_fix16
run questions/system_architecture_wrong_questions_dataset_v2.json    wrong24_v2_regress_fix16
run questions/customer_colloquial_natural_100.json                   colloq_nat100_fix16

echo "全部完成。"
