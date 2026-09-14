#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
跨產業可行性檢核（只驗管線跑得通，不宣稱準確率）
================================================
§3.11 主張「架構層可跨領域直接複用，僅領域知識層需重建」，但先前只以設定條目數
（224 條）與程式行數（7,212 行）量化，未實際換過產業。本腳本以三家**非半導體**
公司各取單季，逐項記錄五件事：

  1. HTML 是否能下載
  2. 是否能轉成 CSV
  3. 是否能建立 Fact 索引
  4. 是否能完成一筆確定性查詢
  5. 架構程式是否需要修改

**刻意不做**：不建金標、不報 EM、不宣稱跨產業準確率——那需要的樣本數遠超此處
所能負擔，且會把「n 偏小」的弱點請回來（§4.4.1 已示範單組 60 題不足以判定效果）。
本檢核只證明我們實際主張的那一句：換產業時架構層不需要改。

若任一步失敗（含 MOPS 連線失敗），如實記為失敗並在報告中寫明，不換公司湊數。

    python3 benchmark_cross_industry_feasibility.py [--out results/cross_industry_feasibility]
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WORK = ROOT / "_cross_industry_probe"          # 隔離工作區，不污染既有資料
TARGETS = [("2603", "長榮", "航運"),
           ("2317", "鴻海", "電子代工"),
           ("6691", "洋基工程", "機電工程")]
YEAR, SEASON = "114", "2"


def arg(flag: str, default):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default


def step_download(html_dir: Path) -> list[dict]:
    """步驟 1：沿用既有 html_downloadv2.crawl_mops_finance_report，不修改其程式。"""
    sys.path.insert(0, str(ROOT))
    import html_downloadv2 as H

    out = []
    for code, name, industry in TARGETS:
        t0 = time.time()
        try:
            H.crawl_mops_finance_report(stock_code=code, year=YEAR, season=SEASON,
                                        base_folder=str(html_dir))
            err = None
        except Exception as exc:                                  # noqa: BLE001
            err = f"{type(exc).__name__}: {exc}"
        found = list(html_dir.glob(f"{code}_*/*.html"))
        out.append({"code": code, "name": name, "industry": industry,
                    "ok": bool(found), "files": [str(p.relative_to(html_dir)) for p in found],
                    "bytes": sum(p.stat().st_size for p in found),
                    "error": err, "sec": round(time.time() - t0, 1)})
        print(f"  [{'✓' if found else '✗'}] {code} {name}（{industry}）"
              f"｜{len(found)} 檔／{sum(p.stat().st_size for p in found):,} bytes"
              f"{'｜' + err if err else ''}")
        time.sleep(3)
    return out


def step_parse(html_dir: Path, csv_dir: Path) -> dict:
    """步驟 2：以既有解析器轉 CSV。以子行程執行並覆寫其輸入／輸出資料夾常數。"""
    code = (
        "import runpy, sys, types\n"
        "import deal_html_datav2_strip_company_suffix as D\n"
        f"D.INPUT_FOLDER = r'{html_dir}'\n"
        f"D.OUTPUT_FOLDER = r'{csv_dir}'\n"
        "fn = getattr(D, 'main', None) or getattr(D, 'run', None)\n"
        "print('ENTRY:', fn.__name__ if fn else None)\n"
        "fn() if fn else None\n"
    )
    r = subprocess.run([sys.executable, "-c", code], cwd=str(ROOT),
                       capture_output=True, text=True, timeout=900)
    csvs = list(csv_dir.rglob("*.csv"))
    return {"ok": bool(csvs), "n_csv": len(csvs),
            "tables": sorted({p.stem.split("_")[-1] for p in csvs})[:12],
            "returncode": r.returncode,
            "stderr_tail": (r.stderr or "")[-400:]}


def _run_with_config(csv_dir: Path, snippet: str) -> dict:
    """
    以「只改設定檔」的方式跑一段程式：暫時把 config 的 reports_root 指向探針目錄，
    於子行程執行後還原（try/finally 保證還原）。

    為何不直接傳參數：`_load_facts_df(root)` 的 root 參數對合併索引路徑**不生效**
    ——該路徑取自模組層級常數 GLOBAL_NUMERIC_FACTS，於匯入時由 reports_root 推導。
    這是既有程式的缺陷（參數形同虛設，已記入本檢核之 findings），但不影響本檢核
    要驗證的主張：系統設計的領域切換機制本來就是設定檔外部化，以設定檔測試才公平。
    """
    cfg_path = ROOT / "config" / "system_config.json"
    backup = cfg_path.read_text(encoding="utf-8")
    try:
        cfg = json.loads(backup)
        cfg["reports_root"] = str(csv_dir.relative_to(ROOT))
        cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=1),
                            encoding="utf-8")
        r = subprocess.run([sys.executable, "-c", snippet], cwd=str(ROOT),
                           capture_output=True, text=True, timeout=600)
    finally:
        cfg_path.write_text(backup, encoding="utf-8")
    tail = [ln for ln in (r.stdout or "").splitlines() if ln.startswith("RESULT:")]
    if not tail:
        return {"ok": False, "error": (r.stderr or "")[-400:] or "無 RESULT 輸出"}
    return json.loads(tail[-1][len("RESULT:"):])


def step_index(csv_dir: Path) -> dict:
    """步驟 3：建立 Fact 索引（只改設定檔的 reports_root，不改程式）。"""
    lines = [
        "import json",
        "import rag_test_system_v14 as V",
        "df = V._load_facts_df(V.REPORTS_ROOT)",
        "out = {'ok': len(df) > 0, 'n_facts': int(len(df)),",
        "       'n_companies': int(df['company_name'].nunique()),",
        "       'n_tables': int(df['table_name'].nunique()),",
        "       'companies': sorted(df['company_name'].dropna().unique().tolist())[:6]}",
        "print('RESULT:' + json.dumps(out, ensure_ascii=False))",
    ]
    return _run_with_config(csv_dir, "\n".join(lines))


def step_query(csv_dir: Path) -> dict:
    """
    步驟 4：每家做一筆確定性查詢（同樣只改設定檔）。

    取「資產總計」——跨產業都存在的科目；若改用半導體特有科目，失敗將無法區分
    是管線問題還是本體論缺項。
    """
    targets_literal = repr(json.dumps([[c, n, i] for c, n, i in TARGETS],
                                      ensure_ascii=False))
    lines = [
        "import json",
        "import rag_test_system_v14 as V",
        f"targets = json.loads({targets_literal})",
        f"period = {f'{YEAR}Q{SEASON}'!r}",
        "df = V._load_facts_df(V.REPORTS_ROOT)",
        "_s, _e, ded = V._prep_facts_for_gen(df)",
        "rows = []",
        "for code, name, industry in targets:",
        "    comp = next((c for c in df['company_name'].dropna().unique()",
        "                 if str(c).startswith(name[:2])), name)",
        "    tr = {}",
        "    ans = V._direct_lookup_flex(df, ded, comp, '資產總計', period, trace=tr)",
        "    rows.append({'code': code, 'company': comp, 'industry': industry,",
        "                 'item': '資產總計', 'answer': ans, 'ok': ans is not None,",
        "                 'decision': tr.get('decision'),",
        "                 'matched_item': tr.get('matched_item'),",
        "                 'matched_col': tr.get('matched_col')})",
        "print('RESULT:' + json.dumps({'queries': rows}, ensure_ascii=False))",
    ]
    return _run_with_config(csv_dir, "\n".join(lines))


def step_code_changes() -> dict:
    """
    步驟 5：架構程式是否需要修改。

    本檢核全程只呼叫既有函式（crawl_mops_finance_report、解析器的 main、
    _load_facts_df、_prep_facts_for_gen、_direct_lookup_flex），未修改任何一行；
    唯一提供的外部輸入是資料夾路徑與公司代號。以 git 工作區是否乾淨佐證。
    """
    r = subprocess.run(["git", "status", "--porcelain",
                        "rag_test_system_v14.py", "llm_contract.py",
                        "html_downloadv2.py",
                        "deal_html_datav2_strip_company_suffix.py"],
                       cwd=str(ROOT), capture_output=True, text=True)
    dirty = [ln for ln in (r.stdout or "").splitlines() if ln.strip()]
    return {
        "ok": not dirty,
        "dirty_files": dirty,
        "note": ("四支核心程式（爬蟲、解析器、檢索系統、契約層）在本檢核期間未被"
                 "修改；切換資料來源的方式是暫時改寫 config/system_config.json 的 "
                 "reports_root，即系統原本設計的領域切換機制。")
        if not dirty else f"檢核期間有 {len(dirty)} 支核心程式被改動",
        # 檢核過程中發現、但不影響上述結論的既有缺陷，一併記錄以免被遺忘
        "findings": [
            "_load_facts_df(root) 的 root 參數對合併索引路徑不生效——該路徑取自"
            "模組層級常數 GLOBAL_NUMERIC_FACTS，於匯入時由 reports_root 推導。"
            "參數形同虛設，易誤導呼叫端（本檢核初次執行即因此讀到原半導體索引）。"
            "屬 API 一致性缺陷，不影響設定檔驅動之領域切換。",
        ],
    }


def main() -> int:
    out_stem = Path(arg("--out", ROOT / "results" / "cross_industry_feasibility"))
    html_dir = WORK / "reports_html_copy"
    csv_dir = WORK / "reports_csv_output"
    if "--clean" in sys.argv and WORK.exists():
        shutil.rmtree(WORK)
    html_dir.mkdir(parents=True, exist_ok=True)
    csv_dir.mkdir(parents=True, exist_ok=True)

    print(f"目標：{'、'.join(f'{c} {n}（{i}）' for c, n, i in TARGETS)}｜{YEAR}Q{SEASON}")
    print(f"工作區（隔離，不影響既有資料）：{WORK}\n")

    print("步驟 1／HTML 下載")
    dl = step_download(html_dir)

    print("\n步驟 2／解析為 CSV")
    parse = step_parse(html_dir, csv_dir)
    print(f"  [{'✓' if parse['ok'] else '✗'}] 產出 {parse['n_csv']} 個 CSV"
          f"｜表名樣本 {parse['tables'][:6]}")
    if not parse["ok"] and parse["stderr_tail"]:
        print("  stderr:", parse["stderr_tail"][-200:])

    print("\n步驟 3／建立 Fact 索引")
    idx = step_index(csv_dir)
    print(f"  [{'✓' if idx['ok'] else '✗'}] {idx['n_facts']:,} 筆 Fact"
          f"｜{idx['n_companies']} 家公司｜表名 {idx['n_tables']} 種")

    print("\n步驟 4／確定性查詢（每家一筆「資產總計」）")
    q = step_query(csv_dir)
    for r in q.get("queries", []):
        print(f"  [{'✓' if r['ok'] else '✗'}] {r['company']}：{r['answer']}"
              f"｜命中欄位 {str(r['matched_col'])[:26]}｜{r['decision']}")

    print("\n步驟 5／架構程式是否需要修改")
    mods = step_code_changes()
    print(f"  {'✓ 零行修改' if mods['ok'] else '✗ 需要修改'}：{mods['note']}")

    result = {
        "title": "跨產業可行性檢核（非半導體三家，單季）",
        "scope": "只驗管線可執行性與架構層是否需修改；不建金標、不報 EM、"
                 "不宣稱跨產業準確率。",
        "targets": [{"code": c, "name": n, "industry": i} for c, n, i in TARGETS],
        "period": f"{YEAR}Q{SEASON}",
        "checks": {
            "1_html_download": dl,
            "2_parse_to_csv": parse,
            "3_build_fact_index": idx,
            "4_deterministic_query": q,
            "5_architecture_code_changes": mods,
        },
        "all_pass": (all(d["ok"] for d in dl) and parse["ok"] and idx["ok"]
                     and all(r["ok"] for r in q.get("queries", []))
                     and mods["ok"]),
    }
    Path(f"{out_stem}.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n（階段性）輸出：{out_stem}.json")
    return 0 if all(d["ok"] for d in dl) and parse["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
