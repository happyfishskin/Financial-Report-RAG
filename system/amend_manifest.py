#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
amend_manifest.py — 預註冊 manifest 的「凍結後修訂」登錄
=========================================================
用途：當某個受封印的檔案在凍結後被更動，且經查證該更動**不影響行為**時，
以本腳本登錄一筆具名修訂並更新該檔雜湊，使 `--check` 能恢復通過。

**為何不直接重新凍結**：重跑 `freeze_heldout_manifest.py` 會刷新
`frozen_at_utc` 與全部雜湊，等於抹掉「曾經被改過」這件事。預註冊的價值
正在於事後無法否認，所以修訂必須是**追加**而非覆寫：原始凍結時間、
原始雜湊、修訂理由與證據強度全部留在 manifest 裡。

用法：
    python3 amend_manifest.py --list        # 列出既有修訂
    python3 amend_manifest.py --apply A1    # 套用指定修訂（冪等）
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "results" / "heldout_prereg_manifest.json"

# ── 修訂登錄簿 ────────────────────────────────────────────────
# 每筆修訂都必須寫明：改了什麼、證據是什麼、證據的**界線**在哪裡。
# 「查不出來的部分」要照實記，不得因為結論是「無影響」就略過不提。
AMENDMENTS: dict[str, dict] = {
    "A1": {
        "id": "A1",
        "date_local": "2026-07-30",
        "file": "rag_test_system_v14.py",
        "detected_at_local": "2026-07-30 17:05",
        "file_mtime_local": "2026-07-30 00:33",
        "size_before": 278969,
        "size_after": 279309,
        "lines_before": 5991,
        "lines_after": 5994,
        "summary": "凍結後檔案遭外部編輯（非 Claude Code 工具寫入）；經查證為註解層級改動，未變更任何可執行邏輯。",
        "identified_change": {
            "kind": "新增純註解 3 行",
            "location": "現行檔第 2175–2177 行，位於 _COL_HINT_RE 定義之前、"
                        "[Fix 1] 正則保底提取的說明區塊末端",
            "bytes": 292,
            "lines": [
                "# 原問句: 請幫我查【台積電】【2023年第一季】的【營業收入（2023年第一季）】是多少？",
                "#  ├─ 抓取到的欄位標頭 (Column Hint): ['2023年第一季']",
                "#  └─ 【】內的 Tokens: ['台積電', '2023年第一季', '營業收入（2023年第一季）']",
            ],
            "how_identified": "自工作階段轉錄檔取出 2026-07-25T17:48Z（凍結後、改動前）"
                              "的 _direct_lookup_flex 完整傾印，與現行檔 difflib 比對；"
                              "移除此 3 行後行數回復為 5,991（與凍結版相同）。",
        },
        "unidentified_change": {
            "bytes": 48,
            "lines": 0,
            "status": "未定位",
            "note": "移除已識別的 3 行後仍比凍結版多 48 位元組，且行數已相同，"
                    "推定為某一行的就地修改。經使用者裁示停止追查，故此部分"
                    "**沒有**逐位元證據，不得聲稱『已完整比對』。",
        },
        "behavioural_evidence": {
            "claim": "在已評測的題目分布上，改動前後行為一致。",
            "basis": [
                "version9 對照測試以 v8 函式為 oracle：同一套測試在【凍結版 v8】"
                "（2026-07-29 執行，當時驗章通過）與【現行 v8】（2026-07-30 執行）"
                "各通過一次，兩次結果相同。",
                "涵蓋範圍：直查 1,131 組真實探針（_direct_lookup_flex / "
                "_compute_ratio_value / _lookup_value_or_ratio）、"
                "路由 1,756 題全量（_derive_route_deterministic / "
                "_enrich_intent_from_question）、事實表三份 DataFrame 逐格比對。",
                "已識別的 3 行為註解，Python 直譯器不產生任何位元組碼。",
            ],
            "limits": "此為行為證據而非逐位元證明；未涵蓋上述測試未觸及的程式路徑"
                      "（向量軌、評分模組、CLI）。48 位元組的未定位改動亦可能落在其中。",
        },
        "impact_on_results": "held-out 五組評測結果於凍結版產出，本修訂不重跑、不改動任何"
                             "既有 eval_*.json；後續若重跑，須以本修訂後的雜湊為準並註明。",
    },
    "A4": {
        "id": "A4",
        "date_local": "2026-08-19",
        "file": "build_heldout_twins.py",
        "summary": "為建立第二份 held-out（新種子＋候選歧義分層）而擴充產生器："
                   "種子參數化、新增兩個歧義分層生成器、新增排除第一份 held-out 之"
                   "旗標。第一份之五組輸出**逐位元不變**。",
        "identified_change": {
            "kind": "(a) SEED 由常數改為 _arg(\"--seed\", \"20260726\")，預設值同原常數；"
                    "(b) 新增 gen_investment_ambiguous()、gen_supply_chain_ambiguous()、"
                    "build_ambig()，僅在 --ambig 時執行，且使用獨立 RNG"
                    "（random.Random(SEED ^ AMBIG_SALT)），不消耗主 rng 之抽樣序列；"
                    "(c) Exclusions.__init__ 新增 extra_dirs 參數（預設 None），"
                    "僅在 --exclude-heldout 時傳入 questions/heldout。",
            "location": "SEED 定義處、Exclusions.__init__、build() 之 sets 組裝處，"
                        "及新增於 build() 之前的三個函式",
            "why": "第一份 held-out 之生成判準要求「鑑別子句必須唯一定位一列」"
                   "（本檔開頭第 3 條），構造上排除了候選不唯一的題目。"
                   "measure_relation_ambiguity.py 量得第一份四組候選歧義率 0.0%，"
                   "係該規則之必然結果，不可作為系統表現之證據；故需第二份補上該層。",
            "new_value": "新增資料集 heldout_ambig_60.json（investment_ambiguous 30 ＋ "
                         "supply_chain_ambiguous 30），輸出至 questions/heldout2/。",
        },
        "unidentified_change": None,
        "behavioural_evidence": {
            "claim": "對第一份 held-out 之五組輸出零影響。",
            "basis": [
                "以最終版產生器、預設種子、不加任何新旗標重跑至暫存目錄，"
                "與 questions/heldout/ 之五個檔案逐位元比對（cmp）：五份全數相同。",
                "證據檔：results/heldout2/determinism_check.txt（含時間戳與逐檔結果）。",
                "第一份 manifest 中五個資料集之 SHA256 未變（本次未觸碰題目檔）。",
                "兩份 held-out 題幹交集為 0（390 vs 330 題幹鍵）。",
            ],
            "limits": "僅證明預設種子路徑之輸出不變；--seed / --ambig / "
                      "--exclude-heldout 三條新路徑為新增功能，無舊行為可資比對，"
                      "其正確性由 verify_heldout.py 三檢與 verify_heldout2_ambig.py "
                      "四檢承擔。",
        },
        "impact_on_results": "第一份 held-out 之全部已報數字不變。第二份自有預註冊"
                             "（results/heldout2_prereg_manifest.json）與獨立封章。",
    },
    "A3": {
        "id": "A3",
        "date_local": "2026-08-01",
        "file": "rag_test_system_v14.py",
        "summary": "answer_mode 標註修正：改由實際命中的圖譜層決定，而非路由器的題型分類。"
                   "EM 逐題不變，answer_mode 分布改變。",
        "identified_change": {
            "kind": "為 _execute_graph_rag_search() 增加 trace 出參，"
                    "並新增 _GRAPH_LAYER_MODE 對照表；_rag_query_one() 依實際命中層標註",
            "location": "_execute_graph_rag_search()、_rag_query_one() 之圖譜軌回傳處",
            "why": "舊版以 intent['query_type'] == 'multi_hop_graph_reasoning' 推斷 "
                   "answer_mode，只反映路由器如何分類問題，與實際走了哪一層無關。"
                   "實測全題庫 602 道圖譜題全數由 Layer 0 樣板直答（零 LLM、零遍歷）"
                   "攔下，卻被標成 graph_rag_topology，使該分布看似證明了多跳能力。",
            "new_value": "graph_rag_l0（Layer 0 直答）為新增取值；"
                         "graph_rag_topology 自此僅代表真正執行過拓撲遍歷。",
        },
        "unidentified_change": None,
        "behavioural_evidence": {
            "claim": "答案內容完全不變，僅標籤改變。",
            "basis": [
                "held-out 五組 360 題以修正後系統重跑，與修正前逐題比對："
                "EM 不同 0 題、答案字串不同 0 題、answer_mode 不同 124 題。",
                "分布變化：graph_rag_topology 112 → 6，新增 graph_rag_l0 120，"
                "graph_rag_local 14 → 0；direct_lookup 223 與 vector_search 11 不變。",
                "version9 對照測試同步修改並通過。",
            ],
            "limits": "answer_mode 分布本身改變，任何引用該分布的圖表與敘述須重新產生；"
                      "EM／P／R／F1 不受影響。",
        },
        "impact_on_results": "EM 相關之全部結論不變。舊 eval_*.json 保留於 "
                             "results/heldout/；修正後產出見 version9/results_v9/。",
    },
    "A2": {
        "id": "A2",
        "date_local": "2026-07-30",
        "file": "freeze_heldout_manifest.py",
        "summary": "驗章工具本身的修訂：`do_check()` 於通過時一併列出所有凍結後修訂與"
                   "其未定位部分，避免 ✓ 掩蓋掉『曾被改過』。",
        "identified_change": {
            "kind": "do_check() 新增修訂揭示輸出",
            "location": "do_check() 回傳 0 之前",
            "note": "純輸出，不改變回傳碼與比對邏輯。",
        },
        "unidentified_change": None,
        "behavioural_evidence": {
            "claim": "驗章判準未變，僅增加輸出。",
            "basis": ["比對邏輯（資料集與系統檔雜湊）與回傳碼皆未修改。"],
            "limits": "無。",
        },
        "impact_on_results": "不影響任何評測數字。",
    },
}


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def do_list(man: dict) -> int:
    ams = man.get("amendments") or []
    if not ams:
        print("manifest 尚無任何凍結後修訂。")
        return 0
    print(f"manifest 共 {len(ams)} 筆凍結後修訂（原始凍結：{man['frozen_at_utc']}）：")
    for a in ams:
        print(f"  [{a['id']}] {a['date_local']}  {a['file']}")
        print(f"       {a['summary']}")
        print(f"       {a['sha256_before'][:16]}… → {a['sha256_after'][:16]}…")
    return 0


def do_apply(man: dict, key: str) -> int:
    spec = AMENDMENTS.get(key)
    if spec is None:
        print(f"✗ 未知的修訂代號：{key}（可用：{', '.join(AMENDMENTS)}）")
        return 2

    name = spec["file"]
    entry = man["system_under_test"].get(name)
    if entry is None:
        print(f"✗ manifest 未收錄系統檔 {name}")
        return 2

    path = ROOT / name
    if not path.exists():
        print(f"✗ 找不到檔案 {path}")
        return 2
    now = sha256(path)

    ams = man.setdefault("amendments", [])
    if any(a["id"] == key for a in ams):
        if entry["sha256"] == now:
            print(f"✓ 修訂 {key} 已套用且雜湊相符，無需變更（冪等）。")
            return 0
        print(f"✗ 修訂 {key} 已登錄，但 {name} 的雜湊又變了"
              f"（登錄後 {entry['sha256'][:16]}… ≠ 現行 {now[:16]}…）。\n"
              f"   這是**新的一次**凍結後更動，請新增另一筆修訂，不要覆寫 {key}。")
        return 1

    before_sha, before_bytes = entry["sha256"], entry.get("bytes")
    if before_sha == now:
        print(f"✓ {name} 雜湊與 manifest 相符，無需修訂。")
        return 0

    record = dict(spec)
    record["sha256_before"] = before_sha
    record["sha256_after"] = now
    record["bytes_before"] = before_bytes
    record["bytes_after"] = path.stat().st_size
    record["applied_at_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    ams.append(record)

    entry["sha256"] = now
    entry["bytes"] = path.stat().st_size
    entry["amended_by"] = key

    man["integrity_rule"] = (
        man["integrity_rule"].split("｜")[0].rstrip()
        + "｜本 manifest 含凍結後修訂（見 `amendments`）：驗章所比對的是修訂後雜湊，"
          "引用 held-out 數字時必須一併引用修訂記錄。"
    )

    MANIFEST.write_text(json.dumps(man, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    print(f"✓ 已登錄修訂 {key}：{name}")
    print(f"   {before_sha[:16]}… → {now[:16]}…（{before_bytes} → {path.stat().st_size} bytes）")
    print(f"   原始凍結時間保持不變：{man['frozen_at_utc']}")
    return 0


def do_record_replication(man: dict, key: str) -> int:
    """
    以「凍結版產出 vs 修訂後重跑」的逐題比對結果補強某筆修訂的證據。

    數字由本函式**現場重算**而非手動填寫——修訂記錄是論文要引用的東西，
    手打的數字無法被後人重新驗證。注意：本函式只會新增 `end_to_end_replication`
    欄位，不會修改 `unidentified_change`——未定位就是未定位，實測收斂了它的
    影響範圍，並不等於把它找出來了。
    """
    ams = man.get("amendments") or []
    rec = next((a for a in ams if a["id"] == key), None)
    if rec is None:
        print(f"✗ manifest 無修訂 {key}")
        return 2

    frozen_dir = ROOT / "results" / "heldout_frozenrun_20260725"
    new_dir = ROOT / "results" / "heldout"
    if not frozen_dir.exists():
        print(f"✗ 找不到凍結版產出目錄 {frozen_dir}")
        return 2

    def per(d):
        for k in ("details", "results", "items", "per_question"):
            if k in d:
                return {x.get("id") or x.get("question_id"): x for x in d[k]}
        return {}

    def em(x):
        for k in ("em", "exact_match", "is_em"):
            if k in x:
                return x[k]
        return (x.get("scores") or {}).get("em")

    groups, tot, d_em, d_mode = {}, 0, 0, 0
    for p in sorted(new_dir.glob("eval_*.json")):
        q = frozen_dir / p.name
        if not q.exists():
            continue
        pn, po = per(json.loads(p.read_text("utf-8"))), per(json.loads(q.read_text("utf-8")))
        ids = set(pn) & set(po)
        a = sum(1 for i in ids if em(po[i]) != em(pn[i]))
        b = sum(1 for i in ids if po[i].get("answer_mode") != pn[i].get("answer_mode"))
        groups[p.stem] = {"n": len(ids), "em_diff": a, "answer_mode_diff": b}
        tot += len(ids); d_em += a; d_mode += b

    if not groups:
        print("✗ 沒有可比對的 eval_*.json")
        return 2

    rec["end_to_end_replication"] = {
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "design": "凍結版系統產出的 held-out 結果全數保留於 "
                  "results/heldout_frozenrun_20260725/，修訂後以相同資料集、相同 "
                  "runtime_config 重跑一次，兩次結果逐題比對。",
        "questions_compared": tot,
        "em_mismatches": d_em,
        "answer_mode_mismatches": d_mode,
        "per_group": groups,
        "interpretation": (
            "端到端逐題一致，涵蓋直查／向量／圖譜三軌與評分模組——"
            "即 behavioural_evidence.limits 原先指出的未涵蓋範圍。"
            if d_em == 0 and d_mode == 0 else
            "存在不一致，修訂不得視為行為中性，須逐題檢視。"),
        "does_not_imply": "本結果收斂了未定位改動的影響範圍，但**不等於**已定位該改動；"
                          "unidentified_change 的狀態維持『未定位』。",
    }
    MANIFEST.write_text(json.dumps(man, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    print(f"✓ 已記錄 {key} 的端到端複現證據：{tot} 題，"
          f"EM 不同 {d_em} 題、answer_mode 不同 {d_mode} 題")
    return 0


def main() -> int:
    man = load()
    if "--list" in sys.argv:
        return do_list(man)
    if "--record-replication" in sys.argv:
        i = sys.argv.index("--record-replication")
        return do_record_replication(man, sys.argv[i + 1] if i + 1 < len(sys.argv) else "A1")
    if "--apply" in sys.argv:
        i = sys.argv.index("--apply")
        if i + 1 >= len(sys.argv):
            print("✗ --apply 需要修訂代號")
            return 2
        return do_apply(man, sys.argv[i + 1])
    print(__doc__)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
