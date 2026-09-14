#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Held-out 評測預註冊凍結（freeze_heldout_manifest.py）
======================================================
在**跑任何 held-out 查詢之前**執行，把「要測什麼、用哪一版系統、怎麼算分、
預測是多少、結果怎麼報」全部寫死並以 SHA256 封存。

預註冊（pre-registration）之所以必要
────────────────────────────────────
本論文現有主結果（架構 97.0%／口語 91.0%／純口語 100%／圖譜 100%）全部量測在
系統曾反覆修正的同一批題目上。若 held-out 分數不佳時才回頭改系統或改題目，
held-out 就退化成第二個開發集，失去一般化證據的地位。凍結 manifest 使
「先宣告、後量測」可被第三方驗證：任何事後更動都會使雜湊不符而暴露。

用法
────
    python3 freeze_heldout_manifest.py --project <version8>          # 凍結
    python3 freeze_heldout_manifest.py --project <version8> --check  # 驗章
    ...--outdir DIR / --heldout DIR / --verification FILE            # 路徑覆寫

輸出
────
    results/heldout_prereg_manifest.json   機器可讀（雜湊、預測、分析計畫）
    HELDOUT_PREREGISTRATION.md             人可讀（口試／論文附錄可直接引用）
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def _arg(flag: str, default: str | None = None) -> str | None:
    if flag in sys.argv:
        i = sys.argv.index(flag)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return default


ROOT = Path(_arg("--project", ".")).resolve()
HELDOUT = Path(_arg("--heldout", str(ROOT / "questions" / "heldout"))).resolve()
RESULTS = Path(_arg("--outdir", str(ROOT / "results"))).resolve()
VERIFICATION = Path(_arg("--verification", str(RESULTS / "heldout_verification.json")))
MANIFEST = RESULTS / "heldout_prereg_manifest.json"
MARKDOWN = Path(_arg("--md", str(ROOT / "HELDOUT_PREREGISTRATION.md")))

# ── 孿生對應與 dev 參考分數（皆自既有評測檔讀出，不得手寫）──────────────
TWINS = {
    "heldout_arch_100.json": {
        "dev": "system_architecture_test_questions_100_v4.json",
        "dev_eval": "results/rerun/eval_arch100_v4_v3.json",
        "label": "架構測試 100 題",
    },
    "heldout_colloq_100.json": {
        "dev": "customer_colloquial_test_questions_100_v2_v3.json",
        "dev_eval": "results/rerun/eval_colloq100_v2_fix16.json",
        "label": "口語化 100 題（v2 鑑別版）",
    },
    "heldout_colloq_nat_100.json": {
        "dev": "customer_colloquial_natural_100.json",
        "dev_eval": "results/rerun/eval_colloq_nat100_fix16.json",
        "label": "純口語自然 100 題",
    },
    "heldout_graph_cap_30.json": {
        "dev": "graph_capability_explicit.json",
        "dev_eval": "results/rerun/eval_graphcap_v3.json",
        "label": "圖譜能力題 30 題（固定路由）",
    },
    "heldout_graph_nat_30.json": {
        "dev": "graph_routing_natural.json",
        "dev_eval": "results/rerun/eval_graphnat30_A1.json",
        "label": "圖譜自然路由題 30 題",
    },
}

# ── 受測系統（凍結其雜湊，事後任何修改皆會被驗章抓出）────────────────────
SYSTEM_FILES = [
    "rag_test_system_v14.py",
    "llm_contract.py",
    "config/system_config.json",
    "config/company_aliases.json",
    "build_heldout_twins.py",
    "verify_heldout.py",
    "freeze_heldout_manifest.py",
]

# ══════════════════════════════════════════════════════════════════════
# 預註冊之預測（凍結前可修改，凍結後不得更動）
# ══════════════════════════════════════════════════════════════════════
PREDICTIONS = {
    "heldout_arch_100.json": {
        "point": 88.0, "interval": [80.0, 95.0],
        "rationale": "題幹自帶【】結構化 token 與欄位標頭，col_hint／表鎖等修復"
                     "屬模板層機制而非個案硬編，遷移性最高；扣分主要預期來自"
                     "未見過的科目名變體與同名科目跨表並存。",
    },
    "heldout_colloq_100.json": {
        "point": 80.0, "interval": [70.0, 90.0],
        "rationale": "最依賴 Fix 12/13 的口語橋接（別名表、同義詞覆寫路由器）。"
                     "別名表與同義詞是列舉式知識，對未列舉的口語說法無泛化保證，"
                     "故預期落差最大。",
    },
    "heldout_colloq_nat_100.json": {
        "point": 92.0, "interval": [85.0, 98.0],
        "rationale": "題型單一（10 種指標 × 公司 × 季度），金標生成即保證無歧義；"
                     "公司別名與指標同義詞皆已列舉，主要風險為新期別的欄位型態。",
    },
    "heldout_graph_cap_30.json": {
        "point": 90.0, "interval": [80.0, 97.0],
        "rationale": "固定走圖譜、題幹保留來源提示與【】token，Layer 0 樣板命中率高；"
                     "風險為新的鑑別欄位值與實體名稱變體（大小寫、法人後綴）。",
    },
    "heldout_graph_nat_30.json": {
        "point": 83.0, "interval": [70.0, 95.0],
        "rationale": "同時考驗自然路由與 Layer 0 的自然語句雙軌抽取（A1 補強）。"
                     "該補強是針對 dev 這 30 題逐題除錯而成，最可能過擬合，"
                     "故預測落差最大、區間最寬。",
    },
}

PRIMARY_HYPOTHESIS = (
    "H_heldout：五組 held-out 孿生集之 EM 將**全部低於或等於**其 dev 對應集，"
    "且五組平均落差落在 5–15 pp。"
    "若平均落差 < 5 pp，視為既有修復具跨實例泛化能力；"
    "若 > 15 pp，視為既有分數主要來自對開發集的過擬合。"
    "任一組 held-out 高於 dev 亦須如實報告（代表 dev 該組偏難或抽樣變異）。"
)

ANALYSIS_PLAN = {
    "primary_endpoint": "End-to-End EM（rag_test_system_v14.py evaluate 之 academic_metrics.em）",
    "secondary_endpoints": ["precision", "recall", "f1", "refusal_count",
                            "BERTScore F1", "retrieval hit_rate@5",
                            "answer_mode（路由）分布"],
    "per_type_breakdown": "每組另按 question_type 分層報告 EM，用以定位落差來源",
    "statistical_note": "n=100（三組）與 n=30（兩組）之二項標準誤分別約 ±3–5 pp 與 ±6–9 pp；"
                        "解讀落差時須同時報告 Wilson 95% 區間，避免把抽樣噪音當成泛化落差。",
    "no_tuning_rule": "held-out 結果產生後，**不得**針對其失敗案例修改系統或題目。"
                      "若因而決定修復，須：(1) 原封不動保留本次 held-out 數字並標為"
                      "『修復前 held-out』；(2) 以新種子產生第二份孿生集重新量測；"
                      "(3) 於論文中同時呈現兩次數字。",
    "reporting_rule": "無論結果高低一律全量報告，不得只報表現好的組別；"
                      "拒答（refusal）計為錯誤，不從分母剔除。",
    "environment_rule": "五組皆以最終版系統執行，不設任何 DISABLE_FIX* 旗標；"
                        "vLLM 模型與 system_config.json 內容以本 manifest 之雜湊為準。",
}


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def dev_em(rel: str) -> float | None:
    p = ROOT / rel
    if not p.exists():
        return None
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return round(d["summary"]["academic_metrics"]["em"] * 100, 1)
    except Exception:
        return None


def file_entry(p: Path, rel_to: Path) -> dict:
    return {"path": str(p.relative_to(rel_to)) if p.is_relative_to(rel_to) else str(p),
            "sha256": sha256(p), "bytes": p.stat().st_size}


def build_manifest() -> dict:
    ver = json.loads(VERIFICATION.read_text(encoding="utf-8"))
    if not ver.get("all_checks_passed"):
        sys.exit("[ABORT] verify_heldout.py 未全數通過，不得凍結。")

    cfg = {}
    cfgp = ROOT / "config" / "system_config.json"
    if cfgp.exists():
        c = json.loads(cfgp.read_text(encoding="utf-8"))
        cfg = {k: c.get(k) for k in ("llm_model", "vllm_url", "embed_model",
                                     "chroma_collection")}

    datasets = {}
    for twin, meta in TWINS.items():
        tp = HELDOUT / twin
        data = json.loads(tp.read_text(encoding="utf-8"))
        devp = ROOT / "questions" / meta["dev"]
        datasets[twin] = {
            "label": meta["label"],
            "n": len(data),
            "question_types": dict(Counter(q["question_type"] for q in data)),
            "file": file_entry(tp, HELDOUT.parent.parent),
            "dev_counterpart": {
                "file": meta["dev"],
                "sha256": sha256(devp) if devp.exists() else None,
                "eval_json": meta["dev_eval"],
                "dev_em_pct": dev_em(meta["dev_eval"]),
            },
            "prediction_em_pct": PREDICTIONS[twin],
        }

    system = {}
    for name in SYSTEM_FILES:
        for base in (ROOT, HELDOUT.parent.parent, Path(__file__).resolve().parent):
            p = base / name
            if p.exists():
                system[name] = {"sha256": sha256(p), "bytes": p.stat().st_size}
                break
        else:
            system[name] = None

    try:
        py = subprocess.run([sys.executable, "-V"], capture_output=True,
                            text=True).stdout.strip()
    except Exception:
        py = sys.version.split()[0]

    return {
        "title": "Held-out 孿生集評測預註冊 manifest",
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "project_root": str(ROOT),
        "generation": {
            "generator": "build_heldout_twins.py",
            "seed": 20260726,
            "design": "同分布、同金標方法論、題目實例與全部 dev 題庫互斥",
        },
        "verification": {
            "report": str(VERIFICATION),
            "sha256": sha256(VERIFICATION),
            "all_checks_passed": True,
            "checks": ["題型分布與 dev 完全相同",
                       "題幹與語意主鍵與 23 個 dev 題庫零重疊",
                       "audit_datasets.py D1–D11 零金標缺陷"],
        },
        "datasets": datasets,
        "system_under_test": system,
        "runtime_config": cfg,
        "python": py,
        "primary_hypothesis": PRIMARY_HYPOTHESIS,
        "analysis_plan": ANALYSIS_PLAN,
        "execution_commands": [
            f"bash run_heldout_eval.sh        # 五組各一次 rag-query + evaluate",
            f"python3 report_heldout.py       # 產生 dev vs held-out 對照表",
        ],
        "integrity_rule": "分析前先跑 `freeze_heldout_manifest.py --check`；"
                          "任一雜湊不符即代表資料集或系統在凍結後被更動，"
                          "該次 held-out 結果作廢。",
    }


def do_check(man: dict) -> int:
    bad = []
    for twin, d in man["datasets"].items():
        p = HELDOUT / twin
        if not p.exists() or sha256(p) != d["file"]["sha256"]:
            bad.append(f"資料集 {twin}")
    for name, ent in man["system_under_test"].items():
        if ent is None:
            continue
        for base in (ROOT, HELDOUT.parent.parent, Path(__file__).resolve().parent):
            p = base / name
            if p.exists():
                if sha256(p) != ent["sha256"]:
                    bad.append(f"系統檔 {name}")
                break
        else:
            bad.append(f"系統檔 {name}（遺失）")
    if bad:
        print("✗ 驗章失敗，凍結後遭更動：")
        for b in bad:
            print("   -", b)
        return 1
    print(f"✓ 驗章通過（凍結於 {man['frozen_at_utc']}）："
          f"{len(man['datasets'])} 個資料集、"
          f"{sum(1 for v in man['system_under_test'].values() if v)} 個系統檔雜湊相符。")
    # 驗章比對的可能是**修訂後**的雜湊。若不在此揭示，「曾經被改過」這件事
    # 會隨著 ✓ 一起被忽略，預註冊的不可否認性就形同虛設。
    for a in man.get("amendments") or []:
        print(f"  ⚠ 含凍結後修訂 [{a['id']}] {a['date_local']} {a['file']}："
              f"{a['summary']}")
        u = a.get("unidentified_change") or {}
        if u.get("status") == "未定位":
            print(f"     其中 {u['bytes']} 位元組未定位——引用本次 held-out 數字時"
                  f"須一併說明此界線。")
    return 0


def to_markdown(man: dict) -> str:
    L: list[str] = []
    A = L.append
    A("# Held-out 孿生集評測預註冊（Pre-registration）\n")
    A(f"**凍結時間（UTC）**：{man['frozen_at_utc']}  ")
    A(f"**生成器**：`{man['generation']['generator']}`（seed = "
      f"{man['generation']['seed']}）  ")
    A(f"**驗收報告**：`{Path(man['verification']['report']).name}`"
      f"（SHA256 `{man['verification']['sha256'][:16]}…`）\n")

    A("## 1. 為什麼需要這份文件\n")
    A("論文現有主結果全部量測在「系統曾據以反覆修正」的同一批題目上（Fix 1–17 的每一次")
    A("迭代都看過那些題目），因此是**開發集分數**。孿生集把同一批模板與同一套金標方法論")
    A("套用到**從未被任何修正看過的題目實例**，用以量化開發集分數與泛化分數的落差。")
    A("預註冊的作用是讓「先宣告、後量測」可被第三方驗證：所有資料集與系統檔的 SHA256")
    A("在跑第一題之前即已寫死，任何事後更動都會使驗章失敗。\n")

    A("## 2. 受測資料集（凍結）\n")
    A("| 孿生集 | 題數 | dev 對應集 | dev EM | 預測 EM | 預測區間 |")
    A("|---|---:|---|---:|---:|---|")
    for twin, d in man["datasets"].items():
        dv = d["dev_counterpart"]["dev_em_pct"]
        pr = d["prediction_em_pct"]
        A(f"| `{twin}` | {d['n']} | `{d['dev_counterpart']['file']}` | "
          f"{dv if dv is not None else '—'}% | {pr['point']}% | "
          f"{pr['interval'][0]}–{pr['interval'][1]}% |")
    A("")
    A("各組題型組成與 dev 完全相同（逐型題數相等），僅抽樣實例不同：\n")
    for twin, d in man["datasets"].items():
        types = "、".join(f"{k} {v}" for k, v in d["question_types"].items())
        A(f"- **{d['label']}**（`{twin}`）：{types}")
    A("")
    A("### 預測理由（凍結前寫定）\n")
    for twin, d in man["datasets"].items():
        A(f"- **{d['label']}** → {d['prediction_em_pct']['point']}%："
          f"{d['prediction_em_pct']['rationale']}")
    A("")

    A("## 3. 主要假說\n")
    A(man["primary_hypothesis"] + "\n")

    A("## 4. 分析計畫（凍結）\n")
    ap = man["analysis_plan"]
    A(f"- **主要指標**：{ap['primary_endpoint']}")
    A(f"- **次要指標**：{'、'.join(ap['secondary_endpoints'])}")
    A(f"- **分層報告**：{ap['per_type_breakdown']}")
    A(f"- **統計註記**：{ap['statistical_note']}")
    A(f"- **禁止調參**：{ap['no_tuning_rule']}")
    A(f"- **全量報告**：{ap['reporting_rule']}")
    A(f"- **執行環境**：{ap['environment_rule']}\n")

    A("## 5. 資料集完整性雜湊\n")
    A("| 檔案 | SHA256 | bytes |")
    A("|---|---|---:|")
    for twin, d in man["datasets"].items():
        A(f"| `{twin}` | `{d['file']['sha256']}` | {d['file']['bytes']:,} |")
    A("")
    A("## 6. 受測系統雜湊\n")
    A("| 檔案 | SHA256 | bytes |")
    A("|---|---|---:|")
    for name, ent in man["system_under_test"].items():
        if ent:
            A(f"| `{name}` | `{ent['sha256']}` | {ent['bytes']:,} |")
        else:
            A(f"| `{name}` | （未找到） | — |")
    A("")
    if man.get("runtime_config"):
        A("執行環境設定（取自 `system_config.json`）：\n")
        A("```json")
        A(json.dumps(man["runtime_config"], ensure_ascii=False, indent=2))
        A("```\n")

    A("## 7. 執行指令\n")
    A("```bash")
    for c in man["execution_commands"]:
        A(c)
    A("```\n")
    A(f"> {man['integrity_rule']}\n")
    return "\n".join(L)


def main() -> int:
    if "--check" in sys.argv:
        if not MANIFEST.exists():
            sys.exit(f"[ABORT] 找不到 manifest：{MANIFEST}")
        return do_check(json.loads(MANIFEST.read_text(encoding="utf-8")))

    man = build_manifest()
    RESULTS.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(man, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    MARKDOWN.parent.mkdir(parents=True, exist_ok=True)
    MARKDOWN.write_text(to_markdown(man), encoding="utf-8")

    print(f"✓ 已凍結：{man['frozen_at_utc']}")
    for twin, d in man["datasets"].items():
        dv = d["dev_counterpart"]["dev_em_pct"]
        print(f"  {twin:30} n={d['n']:>3}  dev EM "
              f"{dv if dv is not None else '—'}%  → 預測 "
              f"{d['prediction_em_pct']['point']}%")
    print(f"\n→ {MANIFEST}")
    print(f"→ {MARKDOWN}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
