#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fix 16 單筆／多筆實測：關係人交易題並未被限制成只能回一筆
============================================================
委員可能質疑：Fix 16 把「與 X 之間的 Y 交易金額」投影成單一金額，是否等於
把關係人交易題限制成只能回答單一對象？本腳本以實跑回答，量三件事：

  A 三項條件（交易人＋交易對象＋科目）齊備且唯一命中 → Layer 0 投影單一金額，
    零生成、秒級。
  B 少給交易人（僅對象＋科目）→ Layer 0 **不投影也不補齊**，交由後續層處理。
    這點很重要：底層該（對象, 科目）在同公司同期下其實有多列、金額互異，
    若逕自取一列作答就是編造。
  C 問「交易對象有哪些」→ 走圖譜脈絡，回傳完整子圖（多節點多邊），
    前端逐筆呈現，並非單筆。

**已知界線（必須據實陳述）**：C 的生成端輸出在 4B 模型上會因思考預算耗盡而
截斷，未收斂成條列答案；可靠交付面是子圖與證據層，不是 LLM 散文。系統目前
也沒有「請使用者補充鑑別條件」的互動行為，缺條件時是降級而非反問。

    python3 demo_fix16_single_multi.py
      → results/fix16_single_multi.json
"""
from __future__ import annotations

import contextlib
import io
import json
import re
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
V9 = BASE.parent / "version9"
sys.path.insert(0, str(V9))
OUT = BASE / "results" / "fix16_single_multi.json"

CO, QT = "穩懋半導體", "114Q2"
PARTY = "江蘇全穩康源農業發展有限公司"      # 交易人
COUNTER = "江蘇全穩農牧科技有限公司"        # 交易對象
ACCOUNT = "其他應付款-關係人"

CASES = [
    ("single", "三項條件齊備（交易人＋交易對象＋科目）",
     f"根據關係人交易圖譜，【{CO}】在【{QT}】，【{PARTY}】與【{COUNTER}】"
     f"之間的【{ACCOUNT}】交易金額是多少？"),
    ("no_payer", "少給交易人（僅交易對象＋科目）",
     f"根據關係人交易圖譜，【{CO}】在【{QT}】，與【{COUNTER}】"
     f"之間的【{ACCOUNT}】交易金額是多少？"),
    ("multi", "詢問完整交易對象清單",
     f"{CO} {QT} 的關係人交易對象有哪些？"),
]


def underlying_rows(store) -> list[dict]:
    """（交易對象, 科目）在同公司同期下究竟有幾列——三項條件必要性的直接證據。"""
    _, edges = store._frames
    rp = edges[edges["type"].fillna("") == "HAS_RELATED_PARTY_TRANSACTION"]
    rp = rp[rp["report_company_name"].fillna("").str.contains(CO[:2], na=False)]
    rp = rp[rp["report_period"].fillna("") == QT]
    hit = rp[rp["amount_summary"].fillna("").apply(
        lambda s: f"value_2={COUNTER}" in s and f"value_4={ACCOUNT}" in s)]
    out = []
    for _, r in hit.iterrows():
        kv = dict(re.findall(r"(value_\d+)=([^;]*)", str(r["amount_summary"])))
        out.append({"payer": str(r.get("party_or_category") or "").strip(),
                    "amount": kv.get("value_5", "").strip()})
    return out


def main() -> int:
    from finrag.api import RAGSystem                       # noqa: E402

    quiet = io.StringIO()
    with contextlib.redirect_stdout(quiet):
        rag = RAGSystem(verbose=False, base_dir=V9)
    print("系統就緒；開始實跑", flush=True)

    rows = underlying_rows(rag.graphs)
    print(f"底層事實：（對象={COUNTER}, 科目={ACCOUNT}）於 {CO} {QT} 命中 "
          f"{len(rows)} 列")
    for r in rows:
        print(f"    交易人={r['payer'][:30]:<30} 金額={r['amount']}")

    recs = []
    for key, label, q in CASES:
        buf = io.StringIO()
        t0 = time.perf_counter()
        with contextlib.redirect_stdout(buf):
            r = rag.ask(q, with_display=True)
        dt = round(time.perf_counter() - t0, 3)
        g = r.get("graph") or {}
        ans = str(r.get("answer") or "")
        recs.append({
            "key": key, "label": label, "question": q,
            "answer": ans, "answer_len": len(ans),
            "answer_mode": r.get("answer_mode", ""), "latency_sec": dt,
            "subgraph_nodes": len(g.get("nodes") or []),
            "subgraph_edges": len(g.get("edges") or []),
            "related_parties": [n.get("label") for n in (g.get("nodes") or [])
                                if n.get("group") == "RelatedParty"][:12],
            "trace": [l.rstrip() for l in buf.getvalue().split("\n")
                      if l.strip()][-8:],
        })
        print(f"\n[{key}] {label}")
        print(f"    mode={r.get('answer_mode')}｜{dt}s｜"
              f"子圖 {len(g.get('nodes') or [])} 節點 / {len(g.get('edges') or [])} 邊")
        print(f"    答案（{len(ans)} 字）：{ans[:110]}")

    rec = {
        "title": "Fix 16 單筆／多筆實測",
        "why": "回應「Fix 16 是否把關係人交易題限制成只能回一筆」之質疑。",
        "company": CO, "period": QT,
        "counterparty": COUNTER, "account": ACCOUNT,
        "underlying_rows": rows,
        "cases": recs,
        "caveat": ("多筆清單題的生成端輸出在 4B 模型上因思考預算耗盡而截斷，"
                   "未收斂為條列答案；多筆之可靠交付面為子圖與證據層。"
                   "另系統缺條件時為降級處理，並無「反問使用者補充鑑別條件」"
                   "之互動行為。"),
    }
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    print(f"\n→ {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
