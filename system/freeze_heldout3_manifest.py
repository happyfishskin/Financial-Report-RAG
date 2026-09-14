#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
第二份 held-out 之預註冊凍結（freeze_heldout3_manifest.py）
==========================================================
第一份 held-out（seed 20260726）之生成判準要求「鑑別子句必須唯一定位一列」，
因此**構造上**不可能含候選不唯一的題目：`measure_relation_ambiguity.py` 量得其
四組候選歧義率 0.0%，那是規則的必然，不是系統的表現。第二份以新種子重抽五組
孿生集，並**新增候選歧義分層**，補上第一份看不見的那一層。

與第一份一樣，先把「量什麼、預測多少、怎麼報」全部寫死並以 SHA256 封存；本檔
獨立於 `freeze_heldout_manifest.py`（不修改它，故第一份之封章不受影響）。

用法
────
    python3 freeze_heldout3_manifest.py            # 凍結
    python3 freeze_heldout3_manifest.py --check    # 驗章
"""
from __future__ import annotations
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
QDIR = ROOT / "questions" / "heldout3"
MANIFEST = ROOT / "results" / "heldout3_prereg_manifest.json"

DATASETS = ["heldout_ambig_rp_40.json"]

SYSTEM_FILES = ["rag_test_system_v14.py", "llm_contract.py",
                "config/system_config.json", "config/company_aliases.json",
                "build_heldout_twins.py", "report_heldout_ambig.py",
                "freeze_heldout3_manifest.py"]

SEED = 20260821

# ══════════════════════════════════════════════════════════════════════
# 預註冊之預測（凍結後不得更動）
# ══════════════════════════════════════════════════════════════════════
PREDICTIONS = {
    "rp_counterparty_ambiguous": {
        "metric": "set_em", "point": 90.0, "interval": [75.0, 98.0],
        "rationale":
            "Fix 19 之關係人分支在公司／期別過濾後，以 party_or_category == 交易人"
            "再篩，列出 amount_summary 之 value_2 去重。金標由同一份邊表以相同鍵"
            "產生，故機制上應高度一致。扣分預期來自 Pattern 4 之 gate："
            "題幹須同時含「關係人」與 gate 字串才進入該分支，若路由層先把題目導向"
            "別的樣板（如公司名恰好命中投資圖譜）則落空。",
    },
    "rp_account_ambiguous": {
        "metric": "set_em", "point": 85.0, "interval": [65.0, 95.0],
        "rationale":
            "較交易對象句型多一層條件：須以正則 `與【Y】之間` 取出交易對象再篩，"
            "才列出 value_4。多一個抽取步驟即多一處失敗點；另「科目」二字之分支"
            "判斷先於「對象」，若題幹同時含兩者會走科目分支——本分層題幹確實同時"
            "含「交易對象」語意（交易人與對象皆出現），故此順序必須正確才不會誤列。",
    },
}
COVERAGE_PREDICTION = {
    "rp_counterparty_ambiguous": {"point": 92.0, "interval": [80.0, 99.0]},
    "rp_account_ambiguous": {"point": 88.0, "interval": [70.0, 97.0]},
}
DISCLOSURE = {
    "blinding": "非盲測",
    "detail": "受測能力 [Fix 19] 係於第二份量測結果公布後才實作；凍結前已對"
              "「交易對象」句型跑過 1 題煙霧測試並通過（世界先進積體電路 113Q2，"
              "n=3，集合相等）。「交易科目」句型於凍結前**未**測試。",
    "implication": "本份預測之證據強度低於第二份。本份不應被當作該能力的獨立"
                   "驗證，而應視為「該修正是否泛化到 40 個未見實例」之檢查。",
}

PRIMARY_HYPOTHESIS = (
    "H_rp：在 Fix 19 之後，關係人列舉題之集合 EM 將顯著高於 0，且兩個子分層"
    "皆落在預測區間內。若「交易對象」子分層高而「交易科目」子分層接近 0，"
    "則問題出在 `與【Y】之間` 之抽取或分支順序，而非列舉能力本身；"
    "若兩者皆接近 0，則 Pattern 4 之 gate 未被觸發，須檢查路由而非樣板。"
)

ANALYSIS_PLAN = {
    "primary_endpoint":
        "兩子分層各自之 set_em（集合相等、順序無關），由 report_heldout_ambig.py 計算。",
    "scoring_rule":
        "以 [｜|;；,，、] 切分系統答案為集合，與 metadata.expected_set 之集合相等"
        "則 set_em=1。**相等，非鬆散包含**：答多或答少皆為 0。同時原樣報告系統之"
        "字串 exact_match，兩者差距即順序／格式造成的低估。",
    "secondary_endpoints":
        "coverage = |預測 ∩ 金標| / |金標|，用以區分「全錯」與「只答出其中一個」；"
        "以及 answer_mode 分布（確認題目確實走到關係軌而非降級）。",
    "no_tuning_rule":
        "凍結後不得因結果而修改 rag_test_system_v14.py 再重跑。若本份數字不如預期"
        "而需再修 Fix 19，須另立第四份，不得就地重測。",
    "reporting_rule":
        "兩子分層數字一律分開報；且**每次引用本份數字時皆須同時陳述 DISCLOSURE "
        "所載之非盲測事實**，不得單獨呈現。",
    "environment_rule":
        "與第一份同組態：什麼旗標都不設（Fix 16/17 全開），vLLM 模型以本 manifest "
        "之 runtime_config 為準。",
}


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()


def entry(p: Path) -> dict:
    return {"path": str(p.relative_to(ROOT)), "sha256": sha256(p),
            "bytes": p.stat().st_size}


def build_manifest() -> dict:
    datasets = {}
    for name in DATASETS:
        p = QDIR / name
        if not p.exists():
            raise SystemExit(f"[中止] 缺少資料集 {p}；請先執行：\n"
                             f"  python3 build_heldout_twins.py --seed {SEED} "
                             f"--ambig --exclude-heldout --outdir questions/heldout2")
        data = json.loads(p.read_text(encoding="utf-8"))
        from collections import Counter
        datasets[name] = {**entry(p), "n_questions": len(data),
                          "question_types": dict(
                              Counter(q.get("question_type") for q in data))}
    system = {f: entry(ROOT / f) for f in SYSTEM_FILES if (ROOT / f).exists()}
    cfg = json.loads((ROOT / "config" / "system_config.json").read_text(encoding="utf-8"))
    return {
        "title": "第二份 held-out（含候選歧義分層）評測預註冊 manifest",
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "project_root": str(ROOT),
        "motivation":
            "第二份之歧義分層涵蓋投資與產業鏈兩樣板；本份補上第三個關係樣板"
            "（關係人交易）之列舉能力，檢驗 Fix 19 是否泛化到未見實例。",
        "generation": {
            "generator": "build_heldout_ambig_rp.py",
            "seed": SEED,
            "command": f"python3 build_heldout_ambig_rp.py --seed {SEED} "
                       f"--outdir questions/heldout3",
            "exclusions": "questions/*.json ＋ questions/heldout/*.json ＋ "
                          "questions/heldout2/*.json（題幹層去重）",
            "gold_semantics": "A 案：全部列出才算對（集合相等、順序無關）",
            "fix19_regression": {
                "claim": "Fix 19 對既有題目零行為變動",
                "basis": "360 道關係軌題目以凍結 intent 重放，L0 可比對 350 題，"
                         "答案逐字相同 350、不同 0",
                "amendment": "heldout2 manifest 之修訂 B3",
            },
        },
        "datasets": datasets,
        "system_under_test": system,
        "runtime_config": {k: cfg.get(k) for k in
                           ("llm_model", "vllm_url", "embed_model",
                            "chroma_collection", "enable_online_graph_traversal")},
        "python": sys.version.split()[0],
        "primary_hypothesis": PRIMARY_HYPOTHESIS,
        "predictions_set_em": PREDICTIONS,
        "predictions_coverage": COVERAGE_PREDICTION,
        "blinding_disclosure": DISCLOSURE,
        "analysis_plan": ANALYSIS_PLAN,
        "execution_commands": [
            "bash run_heldout3_eval.sh          # 一組 rag-query + evaluate",
            "python3 report_heldout_ambig.py    # 歧義分層之集合 EM／覆蓋率",
        ],
        "integrity_rule":
            "分析前先跑 `freeze_heldout3_manifest.py --check`；驗章未過即不得報告數字。",
    }


def check() -> int:
    if not MANIFEST.exists():
        print("✗ 尚未凍結。"); return 1
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    bad = []
    for name, d in m["datasets"].items():
        p = QDIR / name
        if not p.exists() or sha256(p) != d["sha256"]:
            bad.append(f"資料集 {name}")
    for f, d in m["system_under_test"].items():
        p = ROOT / f
        if not p.exists() or sha256(p) != d["sha256"]:
            bad.append(f"系統檔 {f}")
    if bad:
        print("✗ 驗章失敗，凍結後遭更動：")
        for b in bad:
            print("   -", b)
        return 1
    print(f"✓ 驗章通過（凍結於 {m['frozen_at_utc']}）")
    return 0


if __name__ == "__main__":
    if "--check" in sys.argv:
        raise SystemExit(check())
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    man = build_manifest()
    MANIFEST.write_text(json.dumps(man, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    print(f"✓ 已凍結 → {MANIFEST.relative_to(ROOT)}")
    print(f"  種子 {SEED}；資料集 {len(man['datasets'])} 組；"
          f"系統檔 {len(man['system_under_test'])} 個")
    for k, v in PREDICTIONS.items():
        print(f"  預測 {k}: set_em {v['point']}% {v['interval']}")
