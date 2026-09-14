#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
amend_heldout3_manifest.py — 第二份 held-out 預註冊 manifest 的凍結後修訂登錄
=============================================================================
與 `amend_manifest.py` 同一原則：凍結後若受封檔案被更動，且經查證該更動之理由
與證據可具名交代，則以**追加**方式登錄修訂並更新該檔雜湊，使 `--check` 恢復
通過。原始凍結時間、原始雜湊、修訂理由與其界線全部留在 manifest 裡——預註冊的
價值正在於事後無法否認，所以絕不重新凍結覆寫。

用法：
    python3 amend_heldout3_manifest.py --list
    python3 amend_heldout3_manifest.py --apply B1
"""
from __future__ import annotations
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "results" / "heldout3_prereg_manifest.json"

AMENDMENTS: dict[str, dict] = {
    "C1": {
        "id": "C1",
        "date_local": "2026-08-19",
        "file": "report_heldout_ambig.py",
        "summary": "評分器補上關係人兩個子分層的分群依據。**發生於本份量測之前**，"
                   "非依結果調整。",
        "identified_change": {
            "kind": "新增 DIM_TO_STRATUM 與 stratum_of()：關係人之兩個子分層共用同一 "
                    "target_route（graph_rag_related_party），改以 metadata."
                    "listed_dimension 區分；另讓輸出路徑可由 --out 指定。",
            "why": "凍結時漏了這層對照，若不補，40 題會全部落入 unknown 而無法分開報，"
                   "違反本份 analysis_plan 之 reporting_rule（兩子分層一律分開報）。",
            "timing": "凍結於 2026-08-19T08:45:29Z，本修訂在該份 eval 執行**之前**完成，"
                      "故不存在依結果選擇評分方式的空間。",
        },
        "unidentified_change": None,
        "behavioural_evidence": {
            "claim": "不改變任何既有數字。",
            "basis": [
                "第二份之兩個子分層仍走 ROUTE_TO_STRATUM 原路徑，分群結果不變；"
                "以修訂後評分器重算第二份，數字應與 ambig_report.md 完全一致。",
                "set_em／coverage／string_em 之計算式一字未動。",
            ],
            "limits": "僅補分群；若未來出現既不在 DIM_TO_STRATUM 也不在 "
                      "ROUTE_TO_STRATUM 的題目，仍會落入 unknown。",
        },
        "impact_on_results": "第二份數字不變；第三份得以依 analysis_plan 分開報告。",
    },
    "C2": {
        "id": "C2",
        "date_local": "2026-08-19",
        "file": "report_heldout_ambig.py",
        "summary": "修正報表 .md 檔名寫死的缺陷：改為與 --out 之 .json 同名。"
                   "此缺陷曾使 post-hoc 重測的 .md 覆蓋掉預註冊那份 .md。",
        "identified_change": {
            "kind": "輸出改為 out.with_suffix(\".md\")，並把成功訊息改為印實際路徑"
                    "（原本連訊息都是寫死字串，故覆蓋當下沒有被看出來）。",
            "why": "原程式無論 --out 指到哪，.md 一律寫入 <out 的目錄>/ambig_report.md。"
                   "以 --out results/heldout2/ambig_report_posthoc_fix19.json 執行"
                   "post-hoc 重測時，.json 正確分流，.md 卻覆蓋了預註冊的 "
                   "results/heldout2/ambig_report.md。",
        },
        "unidentified_change": None,
        "behavioural_evidence": {
            "claim": "無任何數字遺失；受影響者僅為一個可重生的報表檔。",
            "basis": [
                "原始推論結果 results/heldout2/eval_heldout_ambig_60.json"
                "（Fix 19 前，16:31 產出）未被觸及。",
                "預註冊之 results/heldout2/ambig_report.json 亦未被覆蓋"
                "（post-hoc 走的是另一個 .json 檔名），內容仍為 set_em 50.0%。",
                "已自該原始結果重新產生 ambig_report.md，數字為 investment 0.0%／"
                "supply_chain 100.0%／合計 50.0%，與 .json 一致。",
            ],
            "limits": "覆蓋期間（16:48–16:52）若有人讀過該 .md，會讀到 post-hoc 數字。"
                      "本專案為單人作業且該區間無其他讀者，但仍照實記錄。",
        },
        "impact_on_results": "無。三份報表現已分流為 ambig_report.md（預註冊）、"
                             "ambig_report_posthoc_fix19.md（post-hoc）、"
                             "heldout3/ambig_rp_report.md（第三份）。",
    },
    "C3": {
        "id": "C3",
        "date_local": "2026-08-19",
        "file": "rag_test_system_v14.py",
        "summary": "[Fix 20] 未指定期別之單值題改採「明示預設期別」作答並揭露假設；"
                   "同時修正拒答訊息未指出真正缺漏條件的問題。**post-hoc 系統修改**。",
        "identified_change": {
            "kind": "新增 _FIX20_OFF／_ROC_Q_IN_TEXT_RE／_period_sort_key()／"
                    "_available_periods()；於 ambiguous 拒答分支之前插入預設期別"
                    "分支（僅 query_type=single、路由器未給期別、題幹亦無民國季度、"
                    "且最新期別下之值為唯一時觸發），答案附「未指定期別，預設採最新"
                    "期別 X；本資料涵蓋 A–B」之揭露字串；另把拒答訊息在缺期別時改為"
                    "「條件不足，請指定期別（可選 A–B，共 N 期）」。"
                    "DISABLE_FIX20=1 可關閉。",
            "why": "唯一性閘門把「同一科目跨八季各有不同值」判為候選不唯一而拒答，"
                   "互動使用時對使用者無幫助。處置刻意不是靜默取最新季——那正是本"
                   "研究批評關係軌「逕取原始列序之首筆」的同一種行為；改為採預設並"
                   "在答案內明講假設，系統未替使用者隱瞞任何選擇。比較題（cross_"
                   "company／cross_quarter）**不套用**預設：其結論會因期別而翻轉，"
                   "替使用者選期別等於替他決定結論。",
        },
        "unidentified_change": None,
        "behavioural_evidence": {
            "claim": "對既有題目零行為變動。",
            "basis": [
                "4,492 題凍結評測中觸發 ambiguous 者僅 1 題（ho_arch_016），該題題幹"
                "已寫明【113Q4】，不符 Fix 20 之觸發條件，實測仍拒答且訊息不變。",
                "重跑 heldout2 架構 100（唯一含該拒答題之資料集）：EM 0.990 與凍結值"
                "相同、拒答數 1 相同、**逐題答案不同者 0 題**。",
                "Fix 20 只可能在 ambiguous 拒答分支內觸發，其餘路徑未被觸及。",
            ],
            "limits": "本修改為 post-hoc；且它改變了 §4.9（二）與圖 4-14 所展示的"
                      "行為（該題改為套用預設而非拒答），該圖與段落須另行更新。",
        },
        "impact_on_results": "所有已報 EM 不變。圖 4-14 與 §4.9（二）需改用仍會拒答"
                             "之比較題重拍與改寫。",
    },
}


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load() -> dict:
    if not MANIFEST.exists():
        raise SystemExit("[中止] 尚未凍結 heldout2 manifest。")
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def do_list() -> None:
    m = load()
    ams = m.get("amendments", [])
    print(f"manifest 共 {len(ams)} 筆凍結後修訂"
          f"（原始凍結：{m['frozen_at_utc']}）：")
    for a in ams:
        print(f"  [{a['id']}] {a['date_local']}  {a['file']}")
        print(f"       {a['summary']}")
        print(f"       {a['sha256_before'][:16]}… → {a['sha256_after'][:16]}…")


def do_apply(aid: str) -> None:
    if aid not in AMENDMENTS:
        raise SystemExit(f"[中止] 無此修訂編號：{aid}")
    a = AMENDMENTS[aid]
    m = load()
    f = a["file"]
    ent = m["system_under_test"].get(f)
    if ent is None:
        raise SystemExit(f"[中止] {f} 不在 manifest 的 system_under_test 內。")
    p = ROOT / f
    new_hash = sha256(p)
    if any(x["id"] == aid for x in m.get("amendments", [])):
        print(f"✓ 修訂 {aid} 已登錄（冪等，未重複寫入）")
        return
    # 診斷更正型修訂：不含程式改動，故雜湊本就不變，仍須留下具名紀錄。
    if new_hash == ent["sha256"] and not a.get("diagnosis_only"):
        raise SystemExit(f"[中止] {f} 雜湊未變，無需修訂。"
                         f"（若為純診斷更正，請於該筆加 diagnosis_only=True）")
    rec = {**a, "sha256_before": ent["sha256"], "sha256_after": new_hash,
           "bytes_before": ent["bytes"], "bytes_after": p.stat().st_size,
           "amended_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    m.setdefault("amendments", []).append(rec)
    ent["sha256"], ent["bytes"] = new_hash, p.stat().st_size
    MANIFEST.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✓ 已登錄修訂 {aid}：{f}")
    print(f"   {rec['sha256_before'][:16]}… → {rec['sha256_after'][:16]}…"
          f"（{rec['bytes_before']} → {rec['bytes_after']} bytes）")
    print(f"   原始凍結時間保持不變：{m['frozen_at_utc']}")


if __name__ == "__main__":
    if "--list" in sys.argv:
        do_list()
    elif "--apply" in sys.argv:
        do_apply(sys.argv[sys.argv.index("--apply") + 1])
    else:
        print(__doc__)
