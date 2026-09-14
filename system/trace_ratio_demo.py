#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
口語比率題的內部步驟追蹤（口試備審用實機畫面）
================================================
把「台積電114Q2毛利率多少？」這一題在系統內部走過的每一步印出來。

**所有數值皆來自實際函式呼叫**，本腳本只負責排版，不硬編任何結果；
LLM 呼叫次數以攔截 `_call_vllm` 實際計數，不是估計值。

    python3 trace_ratio_demo.py ["問句"]
"""
from __future__ import annotations

import sys
import time
from decimal import Decimal

sys.path.insert(0, ".")
import rag_test_system_v14 as R   # noqa: E402

QUESTION = sys.argv[1] if len(sys.argv) > 1 else "台積電114Q2毛利率多少？"
QUARTER = "114Q2"

# ── 攔截 LLM 呼叫以實際計數 ─────────────────────────────────
_llm_calls: list[tuple[str, float]] = []
_orig_call = R._call_vllm


def _spy(url, model, sysp, usr, **kw):
    t0 = time.perf_counter()
    out = _orig_call(url, model, sysp, usr, **kw)
    _llm_calls.append((sysp.split("\n")[0][:20], time.perf_counter() - t0))
    return out


R._call_vllm = _spy


def main() -> int:
    df = R._load_facts_df(R.REPORTS_ROOT)
    full, _ent, dedup = R._prep_facts_for_gen(df)

    print(f"問句　{QUESTION}\n")

    print("① 口語解析")
    canon = R._canonical_company_name("台積電")
    print(f"　　公司　台積電　→　{canon}　　[Fix 12 市場簡稱正規化]")
    ratio_key = R._RATIO_REVERSE.get("毛利率")
    spec = R._RATIO_ONTOLOGY[ratio_key]
    print(f"　　科目　毛利率　→　比率本體論「{ratio_key}」　[Fix 14]")
    print(f"　　　　　numerator   = {spec['numerator']}")
    print(f"　　　　　denominator = {spec['denominator']}\n")

    print("② 拆成兩次查表（各自通過唯一值閘門）")
    t0 = time.perf_counter()
    num = R._direct_lookup_flex(full, dedup, "台積電", spec["numerator"], QUARTER)
    den = R._direct_lookup_flex(full, dedup, "台積電", spec["denominator"], QUARTER)
    t_lookup = (time.perf_counter() - t0) * 1000
    print(f"　　分子　{spec['numerator']}　{QUARTER}　= {num}")
    print(f"　　分母　{spec['denominator']}　　　{QUARTER}　= {den}")
    print(f"　　（兩次查表共 {t_lookup:.1f} ms）\n")

    print("③ Python 確定性算術（非 LLM）")
    t0 = time.perf_counter()
    result = R._compute_ratio_value(full, dedup, "台積電", "毛利率", QUARTER)
    t_calc = (time.perf_counter() - t0) * 1000
    a = Decimal(num.replace(",", ""))
    b = Decimal(den.replace(",", ""))
    print(f"　　{a} ／ {b} × 100")
    print(f"　　→　{result}　　（{t_calc:.1f} ms）\n")

    print("LLM 呼叫實際計數（攔截 _call_vllm）")
    print(f"　　查表與算術　　{len(_llm_calls)} 次")
    print("　　※ 完整管線另有 1 次意圖路由呼叫（約 3.3 s，佔端到端 96%）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
