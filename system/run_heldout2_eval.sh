#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════
# 第二份 held-out（新種子 ＋ 候選歧義分層）全量評測
# ═══════════════════════════════════════════════════════════════════════
# 前置條件（缺一不可）：
#   1. questions/heldout2/ 下六個資料集已存在
#   2. freeze_heldout2_manifest.py 已凍結，且 --check 驗章通過
#
# 與第一份同組態：什麼旗標都不設（Fix 16/17 全開）。
# 歧義分層排最前面——它是本份的主要端點，先跑先有數字。
# 已有結果者自動略過，可中斷後續跑。
# ═══════════════════════════════════════════════════════════════════════
set -u
PY=${PY:-python3}
cd "$(dirname "$0")"
OUT=results/heldout2
mkdir -p "$OUT"

echo "══ 驗章（凍結後不得更動資料集或系統）"
$PY freeze_heldout2_manifest.py --check || {
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

run questions/heldout2/heldout_ambig_60.json       heldout_ambig_60
run questions/heldout2/heldout_arch_100.json       heldout2_arch_100
run questions/heldout2/heldout_colloq_100.json     heldout2_colloq_100
run questions/heldout2/heldout_colloq_nat_100.json heldout2_colloq_nat_100
run questions/heldout2/heldout_graph_cap_30.json   heldout2_graph_cap_30
run questions/heldout2/heldout_graph_nat_30.json   heldout2_graph_nat_30

echo
echo "全部完成 → $OUT"
echo "接著執行：$PY report_heldout_ambig.py   # 歧義分層之集合 EM／覆蓋率"
echo "注意：字串 EM 對歧義分層會低估（順序敏感），以集合 EM 為主要端點。"
