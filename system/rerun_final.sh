#!/usr/bin/env bash
# 最終重跑：把 A/B/C 三欄補齊到「最終版資料集 × 最終版系統」
#
#   *_after          修正後資料集 ＋ 關閉 Fix 16（DISABLE_FIX16=1）→ 差異純來自資料集
#   *_fix16          修正後資料集 ＋ Fix 16
#   *_regress_fix16  原始資料集   ＋ Fix 16（驗證未使舊資料集退步）
set -u
PY=${PY:-python3}
cd "$(dirname "$0")"
mkdir -p results/rerun

run() {   # run <資料集> <輸出標籤> [DISABLE_FIX16]
  local ds="$1" tag="$2" off="${3:-0}"
  local q="results/rerun/query_${tag}.json"
  local e="results/rerun/eval_${tag}.json"
  if [ -s "$e" ]; then echo "  ✓ 已存在，略過：$tag"; return; fi
  echo "══ [$tag]${off:+ (DISABLE_FIX16=$off)} $ds"
  DISABLE_FIX16="$off" DISABLE_FIX17="$off" $PY rag_test_system_v14.py rag-query --dataset "$ds" --output "$q" \
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

echo "=== B 欄：修正後資料集 ＋ 關閉 Fix 16/17（純資料集效果） ==="
run questions/system_architecture_test_questions_100_v3.json         arch100_orig_after   1
run questions/system_architecture_test_questions_100_v2_v3.json      arch100_v2_after     1
run questions/customer_colloquial_test_questions_100_v3.json         colloq100_orig_after 1
run questions/customer_colloquial_test_questions_100_v2_v3.json      colloq100_v2_after   1
run questions/system_architecture_wrong_questions_dataset_v3.json    wrong24_orig_after   1
run questions/system_architecture_wrong_questions_dataset_v2_v3.json wrong24_v2_after     1

echo "=== C 欄：修正後資料集 ＋ Fix 16 ==="
run questions/system_architecture_test_questions_100_v3.json         arch100_orig_fix16
run questions/system_architecture_test_questions_100_v2_v3.json      arch100_v2_fix16
run questions/customer_colloquial_test_questions_100_v3.json         colloq100_orig_fix16
run questions/customer_colloquial_test_questions_100_v2_v3.json      colloq100_v2_fix16
run questions/system_architecture_wrong_questions_dataset_v3.json    wrong24_orig_fix16
run questions/system_architecture_wrong_questions_dataset_v2_v3.json wrong24_v2_fix16

echo "=== 回歸：原始資料集 ＋ Fix 16 ==="
run questions/system_architecture_test_questions_100.json            arch100_orig_regress_fix16
run questions/system_architecture_test_questions_100_v2.json         arch100_v2_regress_fix16
run questions/customer_colloquial_test_questions_100.json            colloq100_orig_regress_fix16
run questions/customer_colloquial_test_questions_100_v2.json         colloq100_v2_regress_fix16
run questions/system_architecture_wrong_questions_dataset.json       wrong24_orig_regress_fix16
run questions/system_architecture_wrong_questions_dataset_v2.json    wrong24_v2_regress_fix16
run questions/customer_colloquial_natural_100.json                   colloq_nat100_control 1
run questions/customer_colloquial_natural_100.json                   colloq_nat100_fix16

echo "全部完成。"
