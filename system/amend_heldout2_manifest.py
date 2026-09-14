#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
amend_heldout2_manifest.py — 第二份 held-out 預註冊 manifest 的凍結後修訂登錄
=============================================================================
與 `amend_manifest.py` 同一原則：凍結後若受封檔案被更動，且經查證該更動之理由
與證據可具名交代，則以**追加**方式登錄修訂並更新該檔雜湊，使 `--check` 恢復
通過。原始凍結時間、原始雜湊、修訂理由與其界線全部留在 manifest 裡——預註冊的
價值正在於事後無法否認，所以絕不重新凍結覆寫。

用法：
    python3 amend_heldout2_manifest.py --list
    python3 amend_heldout2_manifest.py --apply B1
"""
from __future__ import annotations
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "results" / "heldout2_prereg_manifest.json"

AMENDMENTS: dict[str, dict] = {
    "B1": {
        "id": "B1",
        "date_local": "2026-08-19",
        "file": "report_heldout_ambig.py",
        "summary": "凍結之評分規則字元集自相矛盾，會把金標元素拆碎；改為只以各題"
                   "metadata 宣告之 set_delimiter（｜）切分，並同時報告原規則數字。",
        "identified_change": {
            "kind": "SPLIT_RE 由 [｜|;；,，、] 改為 [｜|]；新增 SPLIT_RE_FROZEN 保留"
                    "原字元集，逐題同時計算 set_em 與 set_em_frozen_rule 兩欄。"
                    "另：子分層改以 metadata.target_route 分群（eval 紀錄不含"
                    "question_type 欄，原程式據此分群會全部落入空字串）。",
            "location": "SPLIT_RE 定義、to_set()、rows 組裝、agg() 與兩處輸出",
            "why": "產業鏈子分層之金標元素形如「中游；生產製程及檢測設備」，"
                   "「；」是**元素內部**的 stage／segment 分隔符。凍結之 analysis_plan "
                   "誤把「；」列入集合切分字元集，會將每個元素拆成兩片，量到的是"
                   "碎片相等而非集合相等。同一份 metadata 已明確宣告 "
                   "set_delimiter=\"｜\"，故原規則與資料自身的宣告直接衝突。",
            "detected_by": "集合 EM(0.0%) 低於字串 EM(6.7%) — 集合比對是字串相等的"
                           "鬆弛，數學上不可能更低，該矛盾即為規則有誤之訊號。",
        },
        "unidentified_change": None,
        "behavioural_evidence": {
            "claim": "本修訂只改評分器，未觸碰受測系統與資料集。",
            "basis": [
                "rag_test_system_v14.py 與 questions/heldout2/*.json 之 SHA256 未變"
                "（本次未寫入任一檔）。",
                "eval_heldout_ambig_60.json 為修訂前既已產出之原始推論結果，"
                "本修訂不重跑推論，僅重算分數。",
                "原規則之數字以 set_em_frozen_rule 欄保留並一併報告，未被抹除。",
            ],
            "limits": "修訂發生於已看見原規則數字之後。故 set_em 之絕對值雖仍取自"
                      "未經調整的推論結果，但『規則於見數後修改』這件事本身必須"
                      "隨數字一併揭露；預註冊之預測值（產業鏈 85%／投資 0%）不得"
                      "因本修訂而更動。",
        },
        "impact_on_results": "推論結果不變；分數重算。兩種規則之數字並列於 "
                             "results/heldout2/ambig_report.md。",
    },
    "B2": {
        "id": "B2",
        "diagnosis_only": True,
        "date_local": "2026-08-19",
        "file": "report_heldout_ambig.py",
        "summary": "更正 B1 對成因的診斷：真正造成「集合 EM 低於字串 EM」的是**比對"
                   "不對稱**，不是字元集本身。字元集仍應改正，但兩種規則的數字相同。",
        "identified_change": {
            "kind": "本筆為診斷更正，不含新的程式改動（程式狀態同 B1 套用後）。",
            "why": "B1 敘述停在「字元集含「；」會把元素拆碎」。實測顯示：若把同一個"
                   "字元集**對稱地**套用到金標與系統答案兩側，碎片集合仍會相等，"
                   "原規則同樣得到 supply_chain 100.0%／investment 0.0%。原程式之所以"
                   "得出不可能的 0.0%，是因為它把切碎後的系統答案拿去和**未切碎的** "
                   "metadata.expected_set 比對——一側是「中游；生產製程及檢測設備」，"
                   "另一側是「中游」「生產製程及檢測設備」，必然不相等。",
            "correct_diagnosis": "asymmetric comparison（gold 取自 expected_set，"
                                 "pred 取自切分後字串），而非 delimiter 選擇本身。",
        },
        "unidentified_change": None,
        "behavioural_evidence": {
            "claim": "兩種切分規則在對稱比對下給出相同數字，故本次修訂未改變結論。",
            "basis": [
                "報表同時輸出 set_em 與 set_em_frozen_rule 兩欄，實測皆為 "
                "supply_chain 100.0%、investment 0.0%、合計 50.0%。",
                "此一致性即為「修訂未影響結論」之直接證據。",
            ],
            "limits": "僅就本資料集之實例成立；若未來金標元素含「｜」以外的分隔符，"
                      "兩規則仍可能分歧，屆時應以 metadata.set_delimiter 為準。",
        },
        "impact_on_results": "數字不變（兩規則一致）。B1 之程式改動維持有效，"
                             "本筆僅更正 manifest 中對成因的記載。",
    },
    "B3": {
        "id": "B3",
        "date_local": "2026-08-19",
        "file": "rag_test_system_v14.py",
        "summary": "[Fix 19] 為投資關係與關係人交易樣板補上「全部列出」時的全列並列"
                   "分支。**post-hoc 系統修改**：發生於本份預註冊量測完成之後。",
        "identified_change": {
            "kind": "新增 _FIX19_OFF / _LISTALL_RE / _listall_requested()；"
                    "投資樣板於 `tgt = inv.iloc[-1][\"target\"]` 之前插入全列分支；"
                    "關係人 Pattern 4 之 gate 加入 _listall_requested()，並於"
                    "公司／期別過濾後插入交易對象（value_2）與交易科目（value_4）"
                    "之列舉分支。DISABLE_FIX19=1 可關閉以重現修正前行為。",
            "why": "本份預註冊量測顯示：同一「請全部列出」語意下，產業鏈樣板"
                   "（已有 Fix 9 全列分支）集合 EM 100.0%，投資樣板 0.0%、覆蓋率"
                   "27.1%（≈1/候選數）。差異純由樣板有無全列分支造成，與檢索無關。",
            "gate": "沿用 Fix 9 之字串「全部列出」／「全部的」。全題庫僅 4 題含該"
                    "字串且皆為產業鏈題（不含「關係人」三字），故新分支對既有題目"
                    "不可能被觸發。",
        },
        "unidentified_change": None,
        "behavioural_evidence": {
            "claim": "對既有題目零行為變動。",
            "basis": [
                "以凍結之 router_decision 重放十一份結果檔中全部 360 道關係軌題目："
                "L0 有答出並可比對者 350 題，答案字串**逐字相同 350、不同 0**。",
                "gate 字串在既有題庫僅出現 4 次，且均為 supply_chain（原就走 Fix 9）。",
            ],
            "limits": "此回歸只覆蓋關係軌（L0）之答案字串；數值軌與向量軌未重跑"
                      "（Fix 19 未觸及該等路徑之程式碼）。另：本修改為 post-hoc，"
                      "修正後之歧義分層數字**不得取代**預註冊之量測，須並列呈現"
                      "並標明 post-hoc。",
        },
        "impact_on_results": "預註冊之 investment 0.0%／supply_chain 100.0% 維持不變"
                             "並繼續作為主要結果；修正後數字另行標示為 post-hoc。",
    },
    "B4": {
        "id": "B4",
        "date_local": "2026-08-19",
        "file": "report_heldout_ambig.py",
        "summary": "評分器新增關係人子分層之分群依據（供第三份使用）；對本份之分群"
                   "與數字皆無影響。同一變動於第三份 manifest 登錄為 C1。",
        "identified_change": {
            "kind": "新增 DIM_TO_STRATUM 與 stratum_of()；輸出路徑改為可由 --out 指定。",
            "why": "第三份（關係人列舉分層）之兩個子分層共用同一 target_route，"
                   "需以 listed_dimension 區分才能依 analysis_plan 分開報告。",
        },
        "unidentified_change": None,
        "behavioural_evidence": {
            "claim": "本份數字一字不變。",
            "basis": [
                "以修訂後評分器重算本份：investment 0.0%／supply_chain 100.0%／"
                "合計 50.0%、覆蓋率 27.1%／100.0%／63.5%——與修訂前逐欄相同。",
                "本份兩子分層之 target_route 仍走 ROUTE_TO_STRATUM 原路徑。",
            ],
            "limits": "無。計算式未動，僅新增一條在本份不會被命中的分群規則。",
        },
        "impact_on_results": "無。",
    },
    "B5": {
        "id": "B5",
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
    "B6": {
        "id": "B6",
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
