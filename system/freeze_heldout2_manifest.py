#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
第二份 held-out 之預註冊凍結（freeze_heldout2_manifest.py）
==========================================================
第一份 held-out（seed 20260726）之生成判準要求「鑑別子句必須唯一定位一列」，
因此**構造上**不可能含候選不唯一的題目：`measure_relation_ambiguity.py` 量得其
四組候選歧義率 0.0%，那是規則的必然，不是系統的表現。第二份以新種子重抽五組
孿生集，並**新增候選歧義分層**，補上第一份看不見的那一層。

與第一份一樣，先把「量什麼、預測多少、怎麼報」全部寫死並以 SHA256 封存；本檔
獨立於 `freeze_heldout_manifest.py`（不修改它，故第一份之封章不受影響）。

用法
────
    python3 freeze_heldout2_manifest.py            # 凍結
    python3 freeze_heldout2_manifest.py --check    # 驗章
"""
from __future__ import annotations
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
QDIR = ROOT / "questions" / "heldout2"
MANIFEST = ROOT / "results" / "heldout2_prereg_manifest.json"

DATASETS = ["heldout_ambig_60.json", "heldout_arch_100.json",
            "heldout_colloq_100.json", "heldout_colloq_nat_100.json",
            "heldout_graph_cap_30.json", "heldout_graph_nat_30.json"]

SYSTEM_FILES = ["rag_test_system_v14.py", "llm_contract.py",
                "config/system_config.json", "config/company_aliases.json",
                "build_heldout_twins.py", "report_heldout_ambig.py",
                "freeze_heldout2_manifest.py"]

SEED = 20260820

# ══════════════════════════════════════════════════════════════════════
# 預註冊之預測（凍結後不得更動）
# ══════════════════════════════════════════════════════════════════════
PREDICTIONS = {
    "supply_chain_ambiguous": {
        "metric": "set_em", "point": 85.0, "interval": [70.0, 95.0],
        "rationale":
            "系統**已有**全列並列分支（`_gkg_pattern_direct_answer` 之 Fix 9，"
            "gate 為題幹含「全部列出」），本分層題幹皆明寫「請全部列出」，故機制上"
            "應可命中。扣分預期來自三處而非核心能力：(a) 公司名須以 Company 節點"
            "名最長比對錨定，簡稱／全名不一致者會落空；(b) 系統之 combos 取自邊表"
            "列序，若同一 (stage, segment) 在邊表有變體拼法會多出元素；(c) 金標取自"
            "`company_table.csv`，與邊表若有極少數不同步即失配。",
    },
    "investment_ambiguous": {
        "metric": "set_em", "point": 0.0, "interval": [0.0, 5.0],
        "rationale":
            "系統**沒有**對應的全列分支：投資關係樣板在多候選時執行 "
            "`tgt = inv.iloc[-1][\"target\"]`，只回傳單一被投資公司。題幹雖明寫"
            "「請全部列出」，該字串在投資樣板中不被檢查（Fix 9 的 gate 只在產業鏈"
            "分支）。故集合 EM 預測為 0；非零只可能來自恰好只有兩家且答案被串接的"
            "邊界情形。**覆蓋率**另行預測為 25–35%（≈ 1 / 平均候選數）。",
    },
}
COVERAGE_PREDICTION = {
    "supply_chain_ambiguous": {"point": 88.0, "interval": [75.0, 97.0]},
    "investment_ambiguous": {"point": 30.0, "interval": [20.0, 40.0]},
}

PRIMARY_HYPOTHESIS = (
    "H_ambig：在候選不唯一且題幹明示「請全部列出」的實例上，系統之集合 EM 將"
    "**依樣板是否具備全列並列分支而兩極化**——產業鏈分層（有分支）顯著高於投資"
    "分層（無分支），且投資分層之集合 EM 接近 0、覆蓋率接近 1/候選數。若投資分層"
    "集合 EM 顯著大於 0，則本研究對「關係軌在多候選時靜默任選一列」之描述有誤，"
    "須修正 §軌道一之敘述；若產業鏈分層亦接近 0，則問題不在樣板有無分支，而在"
    "「全部列出」之 gate 或公司錨定，須另行歸因。"
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
        "凍結後不得因結果而修改 rag_test_system_v14.py 再重跑。若決定補上投資樣板"
        "之全列並列分支，須以**修正前後兩組數字並列**呈現，且修正後之數字標明為"
        "post-hoc，不得取代預註冊之量測。",
    "reporting_rule":
        "兩子分層數字一律分開報，不得只報合計；第一份 held-out 之 0.0% 歧義率須"
        "同時說明其為生成規則之必然，不得作為系統表現之證據。",
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


def determinism_evidence() -> dict:
    """第一份之產生器已被修改（加 --seed / --ambig / --exclude-heldout）。
    證據：以預設種子、不加任何新旗標重跑，輸出與凍結之五份**逐位元相同**。"""
    return {
        "claim": "build_heldout_twins.py 之修改對第一份 held-out 無行為影響",
        "method": "python3 build_heldout_twins.py --outdir <tmp> 後與 "
                  "questions/heldout/*.json 逐位元比對（cmp）",
        "result_file": "results/heldout2/determinism_check.txt",
        "limitation": "僅證明預設種子路徑不變；新旗標路徑本身為新增功能，"
                      "無舊行為可比對。",
    }


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
            "第一份 held-out 之生成判準要求鑑別子句唯一定位一列，故候選歧義率 0.0% "
            "為構造必然而非系統表現（見 results/relation_ambiguity.md）。第二份新種子"
            "重抽，並新增候選歧義分層補上該層。",
        "generation": {
            "generator": "build_heldout_twins.py",
            "seed": SEED,
            "command": f"python3 build_heldout_twins.py --seed {SEED} --ambig "
                       f"--exclude-heldout --outdir questions/heldout2",
            "exclusions": "questions/*.json（dev 全題庫）＋ questions/heldout/*.json"
                          "（第一份 held-out）——兩份 held-out 實例互斥",
            "gold_semantics": "A 案：全部列出才算對（集合相等、順序無關）",
            "determinism_evidence": determinism_evidence(),
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
        "analysis_plan": ANALYSIS_PLAN,
        "execution_commands": [
            "bash run_heldout2_eval.sh          # 六組各一次 rag-query + evaluate",
            "python3 report_heldout_ambig.py    # 歧義分層之集合 EM／覆蓋率",
        ],
        "integrity_rule":
            "分析前先跑 `freeze_heldout2_manifest.py --check`；驗章未過即不得報告數字。",
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
