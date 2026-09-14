#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
關係人列舉分層產生器（第三份 held-out 之候選歧義分層）
=======================================================
第二份 held-out 的歧義分層涵蓋「投資關係」與「產業鏈階段」兩個樣板。本檔補上
第三個關係樣板——**關係人交易**——的列舉題，兩個子分層：

  rp_counterparty_ambiguous  「交易人【X】有哪些交易對象？請全部列出。」
                             同一（公司, 期別, 交易人）揭露 ≥2 個交易對象
  rp_account_ambiguous       「【X】與【Y】之間有哪些交易科目？請全部列出。」
                             同一（公司, 期別, 交易人, 交易對象）揭露 ≥2 個科目

金標語意沿用 A 案：全部列出才算對（集合相等、順序無關）。

**為何另立一檔而不改 build_heldout_twins.py**：後者已被 heldout2 之預註冊
manifest 封印，改它會破章並需再登錄一次修訂。本檔為新增檔案，不觸碰任何受封檔。

用法：
    python3 build_heldout_ambig_rp.py [--seed 20260821] [--outdir questions/heldout3]
"""
from __future__ import annotations
import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

KV_RE = re.compile(r"(value_\d+)=([^;]+)")
SPEC = {"rp_counterparty_ambiguous": 20, "rp_account_ambiguous": 20}


def _arg(flag: str, default: str) -> str:
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default


SEED = int(_arg("--seed", "20260821"))
OUTDIR = ROOT / _arg("--outdir", "questions/heldout3")


def norm_q(t: str) -> str:
    return re.sub(r"\s+", "", str(t)).strip()


def existing_question_texts() -> set:
    """dev 全題庫 ＋ 第一、二份 held-out 之題幹，用於去重。"""
    out = set()
    for d in (ROOT / "questions", ROOT / "questions" / "heldout",
              ROOT / "questions" / "heldout2"):
        if not d.exists():
            continue
        for p in sorted(d.glob("*.json")):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            if isinstance(data, list):
                out |= {norm_q(q.get("question", "")) for q in data}
    return out


def main() -> None:
    import rag_test_system_v14 as v14   # noqa: E402
    print("▶ 載入關係事實表 …")
    v14._load_all_compiled_graphs()
    e = v14.GLOBAL_GRAPH_EDGES_DF
    rp = e[e["type"].fillna("") == "HAS_RELATED_PARTY_TRANSACTION"].copy()
    kvs = [dict(KV_RE.findall(str(v or ""))) for v in rp["amount_summary"].tolist()]
    rp["_v2"] = [d.get("value_2", "").strip() for d in kvs]
    rp["_v4"] = [d.get("value_4", "").strip() for d in kvs]
    rp = rp[(rp["_v2"] != "") & (rp["_v4"] != "")]
    rp = rp[rp["report_company_name"].fillna("").ne("")
            & rp["report_period"].fillna("").ne("")
            & rp["party_or_category"].fillna("").ne("")]
    print(f"  可用關係人交易列：{len(rp):,}")

    seen = existing_question_texts()
    print(f"  既有題幹（dev＋held-out 一二份）：{len(seen):,}")
    rng = random.Random(SEED)
    out: list[dict] = []

    # ── 子分層 1：交易對象列舉 ────────────────────────────────────
    g1 = list(rp.groupby(["report_company_name", "report_period",
                          "party_or_category"]))
    rng.shuffle(g1)
    used_payer: set = set()
    for (co, per, payer), d in g1:
        if sum(1 for q in out
               if q["question_type"] == "rp_counterparty_ambiguous") >= \
                SPEC["rp_counterparty_ambiguous"]:
            break
        vals = list(dict.fromkeys(d["_v2"].tolist()))
        if len(vals) < 2 or (co, per, payer) in used_payer:
            continue
        q = (f"根據關係人交易圖譜，【{co}】在【{per}】揭露的關係人交易中，"
             f"交易人【{payer}】有哪些交易對象？請全部列出。")
        if norm_q(q) in seen:
            continue
        used_payer.add((co, per, payer))
        seen.add(norm_q(q))
        gold = sorted(vals)
        out.append({
            "question_type": "rp_counterparty_ambiguous", "question": q,
            "expected_answer": " ｜ ".join(gold),
            "metadata": {"target_route": "graph_rag_related_party",
                         "company_name": co, "quarter": per, "payer": payer,
                         "answer_semantics": "set", "set_delimiter": "｜",
                         "expected_set": gold, "n_candidates": len(gold),
                         "listed_dimension": "交易對象(value_2)"},
        })

    # ── 子分層 2：交易科目列舉 ────────────────────────────────────
    g2 = list(rp.groupby(["report_company_name", "report_period",
                          "party_or_category", "_v2"]))
    rng.shuffle(g2)
    for (co, per, payer, cp), d in g2:
        if sum(1 for q in out
               if q["question_type"] == "rp_account_ambiguous") >= \
                SPEC["rp_account_ambiguous"]:
            break
        vals = list(dict.fromkeys(d["_v4"].tolist()))
        if len(vals) < 2:
            continue
        q = (f"根據關係人交易圖譜，【{co}】在【{per}】揭露的關係人交易中，"
             f"交易人【{payer}】與【{cp}】之間有哪些交易科目？請全部列出。")
        if norm_q(q) in seen:
            continue
        seen.add(norm_q(q))
        gold = sorted(vals)
        out.append({
            "question_type": "rp_account_ambiguous", "question": q,
            "expected_answer": " ｜ ".join(gold),
            "metadata": {"target_route": "graph_rag_related_party",
                         "company_name": co, "quarter": per, "payer": payer,
                         "counterparty": cp,
                         "answer_semantics": "set", "set_delimiter": "｜",
                         "expected_set": gold, "n_candidates": len(gold),
                         "listed_dimension": "交易科目(value_4)"},
        })

    order = list(SPEC)
    out.sort(key=lambda q: order.index(q["question_type"]))
    for i, q in enumerate(out, 1):
        q["id"] = f"ho3_rp_{i:03d}"
        q["metadata"]["heldout_stratum"] = "candidate_ambiguity_related_party"
        q["metadata"]["gold_semantics"] = "A：全部列出才算對（集合相等、順序無關）"

    from collections import Counter
    c = Counter(q["question_type"] for q in out)
    ok = dict(c) == SPEC
    print(f"\n{'✓' if ok else '✗'} 產出 {len(out)} 題")
    for k, v in c.items():
        print(f"      {k:<30} {v}")
    if not ok:
        print("[WARN] 未達目標題數——可抽樣池可能被去重耗盡。")

    OUTDIR.mkdir(parents=True, exist_ok=True)
    p = OUTDIR / "heldout_ambig_rp_40.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n→ 已寫入 {p}")


if __name__ == "__main__":
    main()
