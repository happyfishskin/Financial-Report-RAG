#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════
# A3：五組 held-out 孿生集全量評測
# ═══════════════════════════════════════════════════════════════════════
# 前置條件（缺一不可）：
#   1. questions/heldout/ 下五個孿生集已存在
#   2. verify_heldout.py 三項全過
#   3. freeze_heldout_manifest.py 已凍結，且 --check 驗章通過
#
# 執行環境刻意「什麼旗標都不設」＝最終版系統（Fix 16/17 全開），
# 與論文主結果同一組態，確保 held-out 與 dev 的唯一差異是題目實例。
#
# 每組跑一次 rag-query（需 vLLM）＋一次 evaluate，輸出到 results/heldout/。
# 已有結果者自動略過，可中斷後續跑。
# ═══════════════════════════════════════════════════════════════════════
set -u
PY=${PY:-python3}
cd "$(dirname "$0")"
OUT=results/heldout
mkdir -p "$OUT"

echo "══ 驗章（凍結後不得更動資料集或系統）"
$PY freeze_heldout_manifest.py --project . --check || {
  echo "✗ 驗章失敗，中止評測。"; exit 1; }

run() {   # run <資料集路徑> <輸出標籤>
  local ds="$1" tag="$2"
  local q="$OUT/query_${tag}.json"
  local e="$OUT/eval_${tag}.json"
  if [ -s "$e" ]; then echo "  ✓ 已存在，略過：$tag"; return; fi
  echo "══ [$tag] $ds"
  $PY rag_test_system_v14.py rag-query --dataset "$ds" --output "$q" \
      > "$OUT/log_${tag}.txt" 2>&1 || { echo "  ✗ query 失敗，見 $OUT/log_${tag}.txt"; return; }
  $PY rag_test_system_v14.py evaluate --results "$q" --output "$e" \
      >> "$OUT/log_${tag}.txt" 2>&1 || { echo "  ✗ evaluate 失敗"; return; }
  $PY - "$e" <<'EOF'
import json, sys
a = json.load(open(sys.argv[1]))["summary"]["academic_metrics"]
print(f"  → EM {a['em']:.3f} ｜ P {a['precision']:.3f} ｜ R {a['recall']:.3f} ｜ "
      f"F1 {a['f1']:.3f} ｜ 拒答 {a['refusal_count']}")
EOF
}

run questions/heldout/heldout_arch_100.json       heldout_arch_100
run questions/heldout/heldout_colloq_100.json     heldout_colloq_100
run questions/heldout/heldout_colloq_nat_100.json heldout_colloq_nat_100
run questions/heldout/heldout_graph_cap_30.json   heldout_graph_cap_30
run questions/heldout/heldout_graph_nat_30.json   heldout_graph_nat_30

echo
echo "全部完成 → $OUT"
echo "接著執行：$PY report_heldout.py   # 產生 dev vs held-out 對照表"
