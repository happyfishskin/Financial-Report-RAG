#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多公司財報 RAG 四大模組整合測試系統
=====================================
執行環境：conda activate financial_crawler

模組說明：
  Module 1  (csv2md)       CSV → Markdown 美化轉換（供人工閱讀）
  build-index              從 .md 檔建立本地持久化 Vector DB (ChromaDB)
  Module 2  (gen-dataset)  自動生成測試資料集（Ground Truth QA 對）
  Module 3  (rag-query)    RAG 查詢引擎（向量檢索 + Metadata 硬性過濾 + vLLM Qwen3-4B-AWQ）
  Module 4  (evaluate)     自動評估評分（多指標精準率報告）

快速開始（完整流程）：
  python rag_test_system.py run-all

分步執行：
  python rag_test_system.py csv2md             # 先轉 .md
  python rag_test_system.py build-index        # 建向量索引
  python rag_test_system.py gen-dataset        # 產測試集
  python rag_test_system.py rag-query          # 查詢（需先啟動 vLLM）
  python rag_test_system.py evaluate           # 評分
"""

from __future__ import annotations

import argparse
import difflib
import json
import math
import random
import re
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any

try:
    import torch as _torch
    _CUDA_OK: bool = _torch.cuda.is_available()
except ImportError:
    _torch   = None  # type: ignore[assignment]
    _CUDA_OK = False


def _vram_reset() -> None:
    """Reset PyTorch CUDA peak-memory counter (no-op if CUDA unavailable)."""
    if _CUDA_OK:
        _torch.cuda.reset_peak_memory_stats()


def _vram_peak_mb() -> float | None:
    """Return peak CUDA memory allocated since last reset, in MB; None if unavailable."""
    if not _CUDA_OK:
        return None
    return round(_torch.cuda.max_memory_allocated() / (1024 ** 2), 1)

# ── 必要套件 ──────────────────────────────────────────────────
try:
    import pandas as pd
    from tabulate import tabulate
except ImportError:
    sys.exit("缺少依賴套件，請先執行：conda activate financial_crawler\n"
             "或：pip install pandas tabulate")

# ── 向量 DB / Embedding 套件（Module 3 / build-index 專用）────
try:
    import chromadb
    from sentence_transformers import SentenceTransformer
    _VECTOR_DEPS_OK = True
except ImportError:
    _VECTOR_DEPS_OK = False

# ══════════════════════════════════════════════════════════════
#  路徑常數
# ══════════════════════════════════════════════════════════════

BASE_DIR      = Path(__file__).resolve().parent
REPORTS_ROOT  = BASE_DIR / "reports_csv_output"

# Module 2 用：全量 numeric facts 索引
GLOBAL_NUMERIC_FACTS = REPORTS_ROOT / "__all_company_all_period_numeric_facts.csv"

DEFAULT_DATASET_OUTPUT = BASE_DIR / "multi_company_test_dataset.json"
DEFAULT_RAG_RESULTS    = BASE_DIR / "rag_query_results.json"
DEFAULT_EVAL_REPORT    = BASE_DIR / "rag_evaluation_report.json"

# Vector DB
DEFAULT_VECTOR_DB    = BASE_DIR / "vector_db"
DEFAULT_EMBED_MODEL  = "BAAI/bge-small-zh-v1.5"
_CHROMA_COLLECTION   = "financial_reports_md"

# vLLM
DEFAULT_VLLM_URL  = "http://127.0.0.1:8000/v1"
DEFAULT_LLM_MODEL = "Qwen/Qwen3-4B-AWQ"

# ══════════════════════════════════════════════════════════════
#  問題模板
# ══════════════════════════════════════════════════════════════

QA_QUESTION_TEMPLATE = "請教【{company_name}】在【{column_header}】的【{item_name}】是多少？"
_QA_RE = re.compile(r"請教【(.+?)】在【(.+?)】的【(.+?)】是多少？")

# Type C entity_lookup 問句解析：在【公司】的【table_name】中，被投資公司【entity】的【column_header】是多少？
_ENTITY_QA_RE = re.compile(
    r"在【(.+?)】的【(.+?)】中，(?:在【[^】]*】，)?被投資公司【(.+?)】的【(.+?)】是多少？"
)

# ── 多維度測試資料集生成用常數 ──────────────────────────────────

# Type C：判斷為實體查閱表的 table_name 關鍵字
_ENTITY_TABLE_KEYWORDS = [
    "被投資公司名稱",
    "列入合併財務報表之子公司",
    "母子公司間業務關係",
    "轉投資大陸地區之事業",
]

# GraphRAG 路由觸發關鍵字（item_name 包含以下任一詞時，觸發 GraphRAG 調度）
_GRAPH_ENTITY_KEYWORDS: frozenset[str] = frozenset({
    "被投資公司", "子公司", "大陸投資", "列入合併", "關聯企業", "轉投資",
})

# GraphRAG 啟用開關（True = Layer 2 entity-table lookup 已就緒）
_GRAPH_ENABLED: bool = True

# Microsoft GraphRAG 索引路徑（建置後設定；未建置時 Layer 1 自動跳過）
_GRAPHRAG_INDEX_PATH: Path = BASE_DIR / "graphrag_index"

# 嘗試匯入 Microsoft GraphRAG 套件
try:
    from graphrag.query.structured_search.local_search.search import LocalSearch as _MsLocalSearch  # type: ignore
    _GRAPHRAG_PKG_AVAILABLE: bool = True
except Exception:
    _MsLocalSearch = None  # type: ignore
    _GRAPHRAG_PKG_AVAILABLE: bool = False

# ── 四大編譯圖譜資料夾 ─────────────────────────────────────────
_GRAPH_DIRS: dict[str, Path] = {
    "investment":    BASE_DIR / "investment_graph_output",
    "related_party": BASE_DIR / "related_party_graph_output",
    "supply_chain":  BASE_DIR / "supply_chain_graph_output",
    "risk_event":    BASE_DIR / "risk_event_graph_output",
}

# 全局圖譜 DataFrame（由 _load_all_compiled_graphs() 填充）
GLOBAL_GRAPH_NODES_DF: "pd.DataFrame | None" = None
GLOBAL_GRAPH_EDGES_DF: "pd.DataFrame | None" = None

# Type D：口語詞 → 會計科目映射（問題模板故意不符合 _QA_RE，強制走第二軌）
_COLLOQUIAL_ENTRIES: list[dict] = [
    {
        "template":      "【{company_name}】在【{quarter}】賺了多少錢？",
        "item_keywords": ["本期淨利"],
        "oral_hint":     "賺了多少錢",
    },
    {
        "template":      "【{company_name}】在【{quarter}】的總資產是多少？",
        "item_keywords": ["資產總計"],
        "oral_hint":     "總資產",
    },
    {
        "template":      "【{company_name}】在【{quarter}】的營業額是多少？",
        "item_keywords": ["營業收入合計"],
        "oral_hint":     "營業額",
    },
    {
        "template":      "【{company_name}】在【{quarter}】手上有多少現金？",
        "item_keywords": ["現金及約當現金"],
        "oral_hint":     "現金",
    },
    {
        "template":      "【{company_name}】在【{quarter}】的毛利是多少？",
        "item_keywords": ["營業毛利"],
        "oral_hint":     "毛利",
    },
]

# ══════════════════════════════════════════════════════════════
#  Module 1 需跳過的非報表 CSV
# ══════════════════════════════════════════════════════════════

_M1_SKIP_SUFFIXES = (
    "_facts.csv",
    "_source_table_index.csv",
    "_xbrl_notes.csv",
    "_xbrl_notes_structured.csv",
    "_numeric_facts.csv",
    "_coverage_report.csv",
)
_M1_SKIP_CONTAINS = ("_all_table_facts",)

# ══════════════════════════════════════════════════════════════
#  通用工具
# ══════════════════════════════════════════════════════════════


def iter_quarter_dirs(root: Path):
    """產生所有 (公司目錄, 季度目錄) 組合，跳過以 _ 開頭的目錄。"""
    for company_dir in sorted(root.iterdir()):
        if not company_dir.is_dir() or company_dir.name.startswith("_"):
            continue
        for quarter_dir in sorted(company_dir.iterdir()):
            if quarter_dir.is_dir():
                yield company_dir, quarter_dir


def _should_skip_for_md(name: str) -> bool:
    return (
        any(name.endswith(s) for s in _M1_SKIP_SUFFIXES)
        or any(p in name for p in _M1_SKIP_CONTAINS)
    )


def _print_section(title: str) -> None:
    bar = "─" * 60
    print(f"\n{bar}\n  {title}\n{bar}")


# ══════════════════════════════════════════════════════════════
#  Module 1：原始 CSV → Markdown 美化工具
# ══════════════════════════════════════════════════════════════


def _csv_path_to_markdown(csv_path: Path) -> str | None:
    try:
        df = pd.read_csv(csv_path, encoding="utf-8-sig", dtype=str, keep_default_na=False)
    except Exception:
        return None
    if df.empty or df.shape[1] == 0:
        return None
    return tabulate(df, headers="keys", tablefmt="pipe", showindex=False)


def run_module1_csv_to_markdown(
    root: Path,
    force: bool = False,
    verbose: bool = True,
) -> dict[str, int]:
    """
    Module 1：遍歷所有公司 / 季度目錄，將原始報表 CSV 轉為 .md 檔。

    跳過：_facts.csv、xbrl_notes、source_table_index 等工具 CSV；
          已存在的 .md 檔（除非 force=True）。

    回傳：{converted, skipped, errors}
    """
    converted = skipped = errors = 0

    for company_dir, quarter_dir in iter_quarter_dirs(root):
        company_code = company_dir.name.split("_")[0]
        quarter      = quarter_dir.name
        prefix       = f"{company_code}_{quarter}_"

        for csv_path in sorted(quarter_dir.glob("*.csv")):
            if _should_skip_for_md(csv_path.name):
                skipped += 1
                continue

            md_path = csv_path.with_suffix(".md")
            if md_path.exists() and not force:
                skipped += 1
                continue

            md_body = _csv_path_to_markdown(csv_path)
            if md_body is None:
                if verbose:
                    print(f"  [SKIP-EMPTY] {csv_path.relative_to(root)}")
                errors += 1
                continue

            stem = csv_path.stem
            table_name = stem[len(prefix):] if stem.startswith(prefix) else stem

            header = (
                f"# {company_dir.name}  ｜  {quarter}  ｜  {table_name}\n\n"
                f"> 來源：`{csv_path.name}`\n\n"
            )
            md_path.write_text(header + md_body + "\n", encoding="utf-8")
            converted += 1
            if verbose:
                print(f"  ✓ {csv_path.relative_to(root)}")

    return {"converted": converted, "skipped": skipped, "errors": errors}


# ══════════════════════════════════════════════════════════════
#  Module 2：自動化測試資料集生成器
# ══════════════════════════════════════════════════════════════


def _load_facts_df(root: Path) -> pd.DataFrame:
    """
    載入全量 numeric facts DataFrame。

    優先讀取根目錄預先合併的 __all_company_all_period_numeric_facts.csv；
    若不存在則逐目錄掃描 _facts.csv。
    """
    if GLOBAL_NUMERIC_FACTS.exists():
        print(f"  ▶ 載入全量索引：{GLOBAL_NUMERIC_FACTS.name}")
        df = pd.read_csv(
            GLOBAL_NUMERIC_FACTS,
            encoding="utf-8-sig",
            dtype=str,
            keep_default_na=False,
            usecols=["stock_code", "company_name", "period", "table_name",
                     "item_name", "column_header", "value_raw", "value_number"],
        )
        df = df[df["value_raw"].str.strip() != ""]
        print(f"  ▶ 載入完成：{len(df):,} 筆，{df['company_name'].nunique()} 家公司")
        return df

    print("  ▶ 全量索引不存在，逐目錄掃描 _facts.csv ...")
    records: list[dict] = []
    total_files = 0
    for _, quarter_dir in iter_quarter_dirs(root):
        for facts_path in quarter_dir.glob("*_facts.csv"):
            if any(p in facts_path.name for p in _M1_SKIP_CONTAINS):
                continue
            try:
                tmp = pd.read_csv(
                    facts_path, encoding="utf-8-sig", dtype=str, keep_default_na=False
                )
            except Exception:
                continue
            required = {"company_name", "period", "item_name", "column_header", "value_raw"}
            if not required.issubset(tmp.columns):
                continue
            if "record_type" in tmp.columns:
                tmp = tmp[tmp["record_type"] == "numeric_fact"]
            tmp = tmp[tmp["value_raw"].str.strip() != ""]
            records.extend(tmp.to_dict("records"))
            total_files += 1
            if total_files % 200 == 0:
                print(f"    ... 已掃描 {total_files} 個檔案，{len(records):,} 筆")

    df = pd.DataFrame(records)
    print(f"  ▶ 掃描完成：{len(df):,} 筆")
    return df


def _prep_facts_for_gen(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    將全量 facts df 拆分為三份，供四種題型生成使用：

    Returns:
        std_df   — 排除實體查閱表的標準財報事實（原始，含重複欄位）
        entity_df — 僅實體查閱表（Type C 用）
        deduped  — std_df 按 (company, item, period) 去重，每組保留最能代表「當期」的一筆
                   （優先 column_header 含 'To' 的日期區間欄，如損益表；其次日期點欄，如資產負債表）
    """
    entity_mask = df["table_name"].str.contains(
        "|".join(_ENTITY_TABLE_KEYWORDS), na=False
    )
    entity_df = df[entity_mask].copy()
    std_df    = df[~entity_mask].copy()

    # 去重：每個 (company, item, period) 取「最能代表當期」的一列
    std_df["_has_range"] = std_df["column_header"].str.contains("To", na=False)
    std_df = std_df.sort_values(
        ["stock_code", "company_name", "item_name", "period", "_has_range"],
        ascending=[True, True, True, True, False],
    )
    deduped = std_df.drop_duplicates(
        subset=["stock_code", "company_name", "item_name", "period"], keep="first"
    ).drop(columns=["_has_range"])
    std_df = std_df.drop(columns=["_has_range"])

    return std_df, entity_df, deduped


def _gen_type_a(deduped: pd.DataFrame, n: int, rng: random.Random) -> list[dict]:
    """Type A：跨公司對比型 — 同期同科目，兩家不同公司對比。"""
    # 找每個 (item_name, period) 下有 >= 2 家公司的組合
    candidates: list[dict] = []
    for (item_name, period), grp in deduped.groupby(["item_name", "period"]):
        companies = (
            grp[["stock_code", "company_name", "column_header", "value_raw"]]
            .drop_duplicates("company_name")
            .to_dict("records")
        )
        if len(companies) < 2:
            continue
        candidates.append({"item_name": item_name, "period": period, "companies": companies})

    rng.shuffle(candidates)
    items: list[dict] = []
    for cand in candidates:
        if len(items) >= n:
            break
        pair = rng.sample(cand["companies"], 2)
        ca, cb = pair[0], pair[1]
        col_hdr = ca["column_header"]  # 用第一家的欄位標頭作為問句代表
        question = (
            f"請對比【{ca['company_name']}】與【{cb['company_name']}】"
            f"在【{cand['period']}】的【{cand['item_name']}】"
            f"（{col_hdr}）分別是多少？"
        )
        expected = (
            f"{ca['company_name']}: {ca['value_raw']}"
            f" ｜ {cb['company_name']}: {cb['value_raw']}"
        )
        items.append({
            "question_type":   "cross_company",
            "question":        question,
            "expected_answer": expected,
            "metadata": {
                "question_type":    "cross_company",
                "target_companies": [ca["stock_code"], cb["stock_code"]],
                "company_names":    [ca["company_name"], cb["company_name"]],
                "company_name":     f"{ca['company_name']}×{cb['company_name']}",
                "quarters":         [cand["period"]],
                "quarter":          cand["period"],
                "item_name":        cand["item_name"],
                "column_header":    col_hdr,
            },
        })
    return items


def _gen_type_b(deduped: pd.DataFrame, n: int, rng: random.Random) -> list[dict]:
    """Type B：跨季度趨勢型 — 同公司同科目，橫跨三個連續季度。"""
    # 找每個 (company, item) 下有 >= 3 個不同 period 的組合
    candidates: list[dict] = []
    for (sc, cname, item_name), grp in deduped.groupby(
        ["stock_code", "company_name", "item_name"]
    ):
        period_rows = grp.sort_values("period")[["period", "column_header", "value_raw"]]
        periods = period_rows["period"].tolist()
        if len(periods) < 3:
            continue
        pv = dict(zip(period_rows["period"], period_rows["value_raw"]))
        ph = dict(zip(period_rows["period"], period_rows["column_header"]))
        candidates.append({
            "stock_code":   sc,
            "company_name": cname,
            "item_name":    item_name,
            "periods":      periods,
            "pv":           pv,
            "ph":           ph,
        })

    rng.shuffle(candidates)
    items: list[dict] = []
    for cand in candidates:
        if len(items) >= n:
            break
        periods = cand["periods"]
        # 從可用 period 中取 3 個連續（隨機起點）
        start = rng.randint(0, len(periods) - 3)
        q3 = periods[start : start + 3]
        vals = [cand["pv"].get(p, "N/A") for p in q3]
        question = (
            f"請列出【{cand['company_name']}】在"
            f"【{q3[0]}】、【{q3[1]}】與【{q3[2]}】"
            f"三個季度中，【{cand['item_name']}】的數字變化？"
        )
        expected = " ｜ ".join(f"{p}: {v}" for p, v in zip(q3, vals))
        items.append({
            "question_type":   "cross_quarter",
            "question":        question,
            "expected_answer": expected,
            "metadata": {
                "question_type":    "cross_quarter",
                "target_companies": [cand["stock_code"]],
                "company_name":     cand["company_name"],
                "quarters":         q3,
                "quarter":          None,   # 多季度，Module 3 不加季度過濾
                "item_name":        cand["item_name"],
            },
        })
    return items


def _gen_type_c(entity_df: pd.DataFrame, n: int, rng: random.Random) -> list[dict]:
    """Type C：實體查閱與隱性股權關聯型（GraphRAG 消融實驗對照組）。"""
    key_cols = ["company_name", "period", "item_name", "column_header"]
    c_df = entity_df.drop_duplicates(subset=key_cols)
    # 過濾掉空白 item_name
    c_df = c_df[c_df["item_name"].str.strip() != ""]
    records = c_df.to_dict("records")
    rng.shuffle(records)
    items: list[dict] = []
    for row in records:
        if len(items) >= n:
            break
        company_name  = row.get("company_name", "")
        item_name     = row.get("item_name", "")
        column_header = row.get("column_header", "")
        table_name    = row.get("table_name", "")
        period        = row.get("period", "")
        stock_code    = row.get("stock_code", "")
        value_raw     = row.get("value_raw", "")
        if not all([company_name, item_name, column_header, value_raw]):
            continue
        question = (
            f"在【{company_name}】的【{table_name}】中，"
            f"在【{period}】，"
            f"被投資公司【{item_name}】的【{column_header}】是多少？"
        )
        items.append({
            "question_type":   "entity_lookup",
            "question":        question,
            "expected_answer": value_raw,
            "metadata": {
                "question_type":    "entity_lookup",
                "target_companies": [stock_code],
                "company_name":     company_name,
                "quarters":         [period],
                "quarter":          period,
                "item_name":        item_name,
                "column_header":    column_header,
                "table_name":       table_name,
            },
        })
    return items


def _gen_type_d(deduped: pd.DataFrame, n: int, rng: random.Random) -> list[dict]:
    """Type D：非標準口語化提問（故意不符合 _QA_RE，強制走 ChromaDB 第二軌）。"""
    all_candidates: list[tuple[dict, dict]] = []
    for entry in _COLLOQUIAL_ENTRIES:
        mask = pd.Series(False, index=deduped.index)
        for kw in entry["item_keywords"]:
            mask |= deduped["item_name"].str.contains(kw, na=False)
        sub = deduped[mask]
        for row in sub.to_dict("records"):
            all_candidates.append((entry, row))

    rng.shuffle(all_candidates)
    items: list[dict] = []
    seen: set[tuple] = set()
    for entry, row in all_candidates:
        if len(items) >= n:
            break
        cname  = row.get("company_name", "")
        period = row.get("period", "")
        iname  = row.get("item_name", "")
        key    = (entry["oral_hint"], cname, period)
        if key in seen or not cname or not period:
            continue
        seen.add(key)
        question = entry["template"].format(
            company_name=cname, quarter=period
        )
        items.append({
            "question_type":   "colloquial",
            "question":        question,
            "expected_answer": row.get("value_raw", ""),
            "metadata": {
                "question_type":    "colloquial",
                "target_companies": [row.get("stock_code", "")],
                "company_name":     cname,
                "quarters":         [period],
                "quarter":          period,
                "item_name":        iname,
                "column_header":    row.get("column_header", ""),
                "oral_hint":        entry["oral_hint"],
            },
        })
    return items


def generate_test_dataset(
    root: Path,
    output_path: Path,
    n_samples: int = 50,
    seed: int = 42,
) -> list[dict]:
    """
    Module 2：多維度複合型測試資料集生成器。

    四種題型（各佔 n_samples // 4，餘數補至 Type A）：
      A. cross_company  — 跨公司對比型（測試跨公司污染抗性）
      B. cross_quarter  — 跨季度趨勢型（測試 Header-Loss 抗性）
      C. entity_lookup  — 實體查閱關聯型（GraphRAG 消融對照組）
      D. colloquial     — 口語化提問型（語意泛化，強制走第二軌）

    Type E（multi_hop_graph_reasoning）由 extend_test_dataset.py 手動追加，
    不在此函數生成範圍，最終資料集共 60 題（50 基礎 + 10 Type E）。
    """
    df = _load_facts_df(root)
    if df.empty:
        print("  ERROR：找不到任何 facts 資料！")
        return []

    std_df, entity_df, deduped = _prep_facts_for_gen(df)
    print(f"  ▶ 標準財報事實（去重）：{len(deduped):,} 筆 ｜ 實體查閱：{len(entity_df):,} 筆")

    rng = random.Random(seed)
    n_each = n_samples // 4
    n_a    = n_samples - n_each * 3  # 餘數補至 Type A

    type_a = _gen_type_a(deduped, n_a,    rng)
    type_b = _gen_type_b(deduped, n_each, rng)
    type_c = _gen_type_c(entity_df, n_each, rng)
    type_d = _gen_type_d(deduped, n_each, rng)

    # 若某類型不足，以其他類型補足
    all_items = type_a + type_b + type_c + type_d
    if len(all_items) < n_samples:
        # 補充：從 deduped 抽標準模板題
        used_cols = {"company_name", "period", "item_name", "column_header"}
        extra_pool = deduped.drop_duplicates(
            subset=["company_name", "period", "item_name", "column_header"]
        ).to_dict("records")
        rng.shuffle(extra_pool)
        need = n_samples - len(all_items)
        for fact in extra_pool[:need]:
            all_items.append({
                "question_type":   "template",
                "question": QA_QUESTION_TEMPLATE.format(
                    company_name=fact.get("company_name", ""),
                    column_header=fact.get("column_header", ""),
                    item_name=fact.get("item_name", ""),
                ),
                "expected_answer": fact.get("value_raw", ""),
                "metadata": {
                    "question_type":   "template",
                    "target_companies": [fact.get("stock_code", "")],
                    "company_name":     fact.get("company_name", ""),
                    "quarters":         [fact.get("period", "")],
                    "quarter":          fact.get("period", ""),
                    "item_name":        fact.get("item_name", ""),
                    "column_header":    fact.get("column_header", ""),
                },
            })

    # 重新排序：AABBCCDD... 交叉排列，方便閱讀
    type_order = {"cross_company": 0, "cross_quarter": 1, "entity_lookup": 2, "colloquial": 3, "multi_hop_graph_reasoning": 4, "template": 5}
    all_items.sort(key=lambda x: type_order.get(x.get("question_type", "template"), 5))

    dataset: list[dict] = []
    for idx, item in enumerate(all_items, 1):
        item["id"] = idx
        dataset.append(item)

    counts = defaultdict(int)
    for item in dataset:
        counts[item["question_type"]] += 1
    count_str = " ｜ ".join(f"{k}={v}" for k, v in counts.items())
    print(f"  ▶ 已生成 {len(dataset)} 筆 QA：{count_str}")

    output_path.write_text(
        json.dumps(dataset, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"  ▶ 結果已儲存 → {output_path}")

    print("\n  預覽（各類型首題）：")
    seen_types: set[str] = set()
    for item in dataset:
        qt = item["question_type"]
        if qt not in seen_types:
            seen_types.add(qt)
            print(f"    [{item['id']}|{qt}] Q: {item['question'][:70]}")
            print(f"         A: {item['expected_answer'][:60]}")
            print()

    return dataset


# ══════════════════════════════════════════════════════════════
#  build-index：從 .md 檔建立 ChromaDB 向量索引
# ══════════════════════════════════════════════════════════════


def _require_vector_deps() -> None:
    if not _VECTOR_DEPS_OK:
        sys.exit(
            "缺少向量 DB 套件，請先安裝：\n"
            "  pip install chromadb langchain-text-splitters sentence-transformers\n"
            "或：conda activate financial_crawler"
        )


def _parse_md_path_metadata(md_path: Path, root: Path) -> dict[str, str]:
    """從 .md 檔案路徑解析 Metadata。

    路徑格式：root/2303_聯華電子/113Q1/2303_113Q1_資產負債表.md
    回傳：{"company_code", "company_name", "quarter", "table_name", "source"}
    """
    parts = md_path.relative_to(root).parts
    company_dir_name = parts[0]   # "2303_聯華電子"
    quarter          = parts[1]   # "113Q1"
    filename         = parts[2]   # "2303_113Q1_資產負債表.md"

    company_code = company_dir_name.split("_")[0]
    company_name = "_".join(company_dir_name.split("_")[1:])

    stem   = Path(filename).stem
    prefix = f"{company_code}_{quarter}_"
    table_name = stem[len(prefix):] if stem.startswith(prefix) else stem

    return {
        "company_code": company_code,
        "company_name": company_name,
        "quarter":      quarter,
        "table_name":   table_name,
        "source":       filename,
    }


_SEP_ROW_RE = re.compile(r"^\s*\|[\s|:=-]*\|[\s|:=-]*\|")


def _is_table_separator(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("|") and bool(re.search(r"\|[\s:]*-{3,}", stripped))


def _is_section_header_row(line: str) -> bool:
    """Section header 行：代號欄空白、數值欄全空（純文字小節標題，如「流動資產 Current assets」）。"""
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    if len(cells) < 3:
        return False
    return cells[0] == "" and all(c == "" for c in cells[2:])


def _is_subtotal_row(line: str) -> bool:
    """合計行：代號欄末尾為 XX（如 11XX、15XX、2XXX），代表小計/合計。"""
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    if not cells:
        return False
    return bool(cells[0]) and cells[0].upper().endswith("XX")


def _chunk_md_file(
    content: str,
    chunk_size: int = 1500,
    chunk_overlap: int = 200,
) -> list[str]:
    """
    Row-aware + Section-context 切分策略：
      1. 分離「固定前言」（標題 + 欄位標頭行 + 分隔行）與「資料行」。
      2. 自動依平均行寬決定每個 chunk 含幾行，不做字元切割（不切斷單行）。
      3. 每個 chunk 均以完整前言開頭。
      4. 追蹤最近一個 section header 行，並在新 chunk 開頭重複（保留上下文）。
      5. 不在合計行（代號末尾 XX）之前切分（避免切在小計上方）。
      6. 小表（≤ 15 行）不切分。
      7. 列層級 overlap（row_overlap ≈ 12.5%），取代字元 overlap。
    """
    lines = content.split("\n")
    preamble_lines, col_header_line, sep_line, data_lines = [], None, None, []
    state = "preamble"
    for line in lines:
        stripped = line.strip()
        if state == "preamble":
            if stripped.startswith("|") and not _is_table_separator(line):
                col_header_line = line; state = "await_sep"
            else:
                preamble_lines.append(line)
        elif state == "await_sep":
            if _is_table_separator(line):
                sep_line = line; state = "data"
            else:
                preamble_lines.extend([col_header_line or "", line])
                col_header_line = None; state = "preamble"
        elif state == "data":
            if stripped:
                data_lines.append(line)

    if not data_lines:
        return [content]

    fixed_parts = ["\n".join(preamble_lines).rstrip()]
    if col_header_line: fixed_parts.append(col_header_line)
    if sep_line:        fixed_parts.append(sep_line)
    preamble = "\n".join(fixed_parts) + "\n"

    if len(data_lines) <= 15:
        return [preamble + "\n".join(data_lines)]

    avg_row_len    = sum(len(l) for l in data_lines) / len(data_lines)
    rows_per_chunk = max(10, min(40, int(chunk_size / max(avg_row_len, 1))))
    row_overlap    = max(2, rows_per_chunk // 8)

    chunks, current_section, i = [], None, 0
    while i < len(data_lines):
        batch, j = [], i
        while j < len(data_lines) and len(batch) < rows_per_chunk:
            line = data_lines[j]
            if _is_section_header_row(line):
                current_section = line
            if len(batch) == rows_per_chunk - 1 and j + 1 < len(data_lines):
                if _is_subtotal_row(data_lines[j + 1]):
                    batch.append(line); j += 1
                    batch.append(data_lines[j]); j += 1
                    break
            batch.append(line); j += 1

        header = preamble
        if current_section and (not batch or batch[0] != current_section):
            header = preamble + current_section + "\n"
        chunks.append(header + "\n".join(batch))
        i = max(i + 1, j - row_overlap)

    return chunks if chunks else [content]


class _BGEEmbedder:
    """SentenceTransformer 包裝器，提供批次 Embedding 與查詢 Embedding。"""

    def __init__(self, model_name: str, device: str = "cpu") -> None:
        print(f"  ▶ 載入 Embedding 模型：{model_name}  (device={device})")
        self._model = SentenceTransformer(model_name, device=device)
        self.dimension: int = self._model.get_sentence_embedding_dimension()
        print(f"  ▶ Embedding 維度：{self.dimension}")

    def embed_batch(self, texts: list[str], batch_size: int = 128) -> list[list[float]]:
        vecs = self._model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=False,
            normalize_embeddings=True,
        )
        return vecs.tolist()

    def embed_query(self, text: str) -> list[float]:
        vec = self._model.encode([text], normalize_embeddings=True)
        return vec[0].tolist()


def _build_company_map(root: Path) -> dict[str, str]:
    """回傳 {company_name: company_code} 對應表，從目錄名稱自動建立。"""
    mapping: dict[str, str] = {}
    for company_dir in sorted(root.iterdir()):
        if not company_dir.is_dir() or company_dir.name.startswith("_"):
            continue
        parts = company_dir.name.split("_", 1)
        if len(parts) == 2:
            mapping[parts[1]] = parts[0]
    return mapping


def build_vector_index(
    root: Path,
    db_path: Path = DEFAULT_VECTOR_DB,
    embedding_model: str = DEFAULT_EMBED_MODEL,
    chunk_size: int = 1500,
    chunk_overlap: int = 200,
    force: bool = False,
    device: str = "cpu",
) -> None:
    """
    從所有 Module 1 生成的 .md 檔建立持久化 ChromaDB 向量索引。

    Metadata（每個 chunk 均注入）：
      company_code, company_name, quarter, table_name, source, chunk_index

    若 db_path 已存在且 force=False，直接跳過以節省時間。
    """
    _require_vector_deps()

    if db_path.exists() and not force:
        print(f"  ▶ Vector DB 已存在：{db_path}")
        print(f"     加 --force 可強制重建。")
        return

    if db_path.exists() and force:
        import shutil
        shutil.rmtree(db_path)
        print(f"  ▶ 已清除舊 Vector DB：{db_path}")

    # ── 收集所有 .md 檔案 ─────────────────────────────────────
    md_files: list[Path] = []
    for company_dir, quarter_dir in iter_quarter_dirs(root):
        md_files.extend(sorted(quarter_dir.glob("*.md")))

    if not md_files:
        print("  ERROR：找不到任何 .md 檔案，請先執行 Module 1 (csv2md)！")
        return

    print(f"  ▶ 找到 {len(md_files):,} 個 .md 檔案")

    # ── 初始化 Embedder 與 ChromaDB ───────────────────────────
    embedder   = _BGEEmbedder(embedding_model, device=device)
    client     = chromadb.PersistentClient(path=str(db_path))
    collection = client.get_or_create_collection(
        name=_CHROMA_COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )

    # ── 切分 + Embed + 寫入 ───────────────────────────────────
    UPSERT_BATCH  = 256
    batch_ids:    list[str]  = []
    batch_docs:   list[str]  = []
    batch_metas:  list[dict] = []
    total_chunks  = 0
    split_count   = 0   # 被切成 >1 chunk 的表格數
    single_count  = 0   # 維持單一 chunk 的表格數
    split_log:    list[str] = []   # 記錄被切分的表格，供最後彙整輸出
    t0 = time.time()

    def _flush() -> None:
        nonlocal total_chunks
        if not batch_docs:
            return
        embeds = embedder.embed_batch(batch_docs)
        collection.upsert(
            ids=batch_ids,
            documents=batch_docs,
            metadatas=batch_metas,
            embeddings=embeds,
        )
        total_chunks += len(batch_docs)
        batch_ids.clear(); batch_docs.clear(); batch_metas.clear()

    for fi, md_path in enumerate(md_files):
        try:
            content = md_path.read_text(encoding="utf-8")
        except Exception:
            continue

        meta   = _parse_md_path_metadata(md_path, root)
        chunks = _chunk_md_file(content, chunk_size, chunk_overlap)

        # ── 切分紀錄（Split Annotation）──────────────────────
        n = len(chunks)
        if n > 1:
            split_count += 1
            tag = (f"{meta['company_name']} {meta['quarter']} "
                   f"{meta['table_name']}  → {n} chunks")
            split_log.append(tag)
            # 即時輸出（每隔 50 個切分才列印，避免刷屏；若想全看可改 n > 0）
            if split_count <= 20 or split_count % 50 == 0:
                print(f"    [SPLIT] {tag}")
        else:
            single_count += 1

        for ci, chunk_text in enumerate(chunks):
            doc_id = (
                f"{meta['company_code']}_{meta['quarter']}"
                f"_{meta['table_name'][:30]}_{ci}"
            )
            batch_ids.append(doc_id)
            batch_docs.append(chunk_text)
            batch_metas.append({
                **meta,
                "chunk_index":  ci,
                "total_chunks": n,
            })

            if len(batch_docs) >= UPSERT_BATCH:
                _flush()

        if (fi + 1) % 500 == 0:
            _flush()
            elapsed = time.time() - t0
            print(f"    [{fi+1:,}/{len(md_files):,} 檔]  "
                  f"chunks={total_chunks:,}  split={split_count}  ({elapsed:.0f}s)")

    _flush()
    elapsed = time.time() - t0

    # ── 切分統計彙整 ────────────────────────────────────────
    total_tables = split_count + single_count
    print(f"\n  ── 切分統計（Split Statistics）──")
    print(f"     表格總數        : {total_tables:,}")
    print(f"     完整保留（1 chunk）: {single_count:,}  ({single_count/max(total_tables,1):.1%})")
    print(f"     切分（> 1 chunk）  : {split_count:,}  ({split_count/max(total_tables,1):.1%})")
    if split_log:
        print(f"\n     被切分的表格（前 30 筆）：")
        for entry in split_log[:30]:
            print(f"       {entry}")
        if len(split_log) > 30:
            print(f"       … 共 {len(split_log)} 筆（完整清單見 split_log）")

    print(f"\n  ▶ 建置完成：{total_chunks:,} chunks  {elapsed:.1f}s → {db_path}")
    print(f"     Collection：{_CHROMA_COLLECTION}")


# ══════════════════════════════════════════════════════════════
#  Module 3：RAG 查詢引擎（向量檢索版）
# ══════════════════════════════════════════════════════════════


def _parse_template_question(question: str) -> dict[str, str] | None:
    """從問題模板中解析 company_name / column_header / item_name。"""
    m = _QA_RE.match(question.strip())
    if not m:
        return None
    return {
        "company_name":  m.group(1),
        "column_header": m.group(2),
        "item_name":     m.group(3),
    }


def _resolve_company_code(
    company_name: str,
    company_map: dict[str, str],
) -> str | None:
    """
    將公司名稱解析為公司代碼，支援完全比對與部分比對。

    company_map = {"聯華電子": "2303", "台灣積體電路製造": "2330", ...}
    """
    # 完全比對
    if company_name in company_map:
        return company_map[company_name]
    # 部分比對（問題中的名稱可能是目錄名稱的子字串，或反之）
    for name, code in company_map.items():
        if company_name in name or name in company_name:
            return code
    return None


def _retrieve_from_vectordb(
    question: str,
    collection,
    embedder: _BGEEmbedder,
    company_code: str | None,
    quarter: str | None = None,
    top_k: int = 5,
) -> tuple[list[dict[str, Any]], str]:
    """
    向量檢索核心，自適應多層硬性 Metadata 過濾。

    過濾層級（逐層嘗試，直到命中結果為止）：
      1. company_code + quarter  ($and 雙重過濾，最嚴格，杜絕跨季度時空錯亂)
      2. company_code only       (季度無此 chunk 時的後備，仍保留公司隔離)
      注意：永不回退至無過濾，確保跨公司隔離不被破壞。

    回傳：(hits, filter_level)
      hits         list of dict with keys: content, company_code, company_name,
                   quarter, table_name, source, score
      filter_level "company+quarter" | "company_only" | "no_match"
    """
    query_embedding = embedder.embed_query(question)

    # Build progressive filter candidates — tightest first
    filter_candidates: list[tuple[str, dict | None]] = []
    if company_code and quarter:
        filter_candidates.append((
            "company+quarter",
            {"$and": [
                {"company_code": {"$eq": company_code}},
                {"quarter":      {"$eq": quarter}},
            ]},
        ))
    if company_code:
        filter_candidates.append(("company_only", {"company_code": {"$eq": company_code}}))
    # No fallback to where=None — preserves cross-company isolation

    for level_name, where_filter in filter_candidates:
        try:
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=where_filter,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as exc:
            print(f"\n    [WARN] ChromaDB 查詢失敗（{level_name}）：{exc}")
            continue

        hits: list[dict[str, Any]] = [
            {
                "content":      doc,
                "company_code": meta.get("company_code", ""),
                "company_name": meta.get("company_name", ""),
                "quarter":      meta.get("quarter", ""),
                "table_name":   meta.get("table_name", ""),
                "source":       meta.get("source", ""),
                "score":        round(1.0 - float(dist), 4),
            }
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            )
        ]

        if hits:
            if level_name != "company+quarter":
                print(f"\n    [FALLBACK → {level_name}]", end="", flush=True)
            return hits, level_name

    return [], "no_match"


def _format_context_from_hits(hits: list[dict[str, Any]], max_chars: int = 6000) -> str:
    """
    將向量檢索命中的 Markdown chunks 組合成 LLM 上下文字串。

    限制總長度上限，避免 4B 模型 Context 過長迷失。
    """
    if not hits:
        return "（無相關財報資料）"

    parts: list[str] = []
    total = 0
    for i, h in enumerate(hits, 1):
        header = (
            f"【片段 {i}｜{h['company_name']} {h['quarter']}"
            f" {h['table_name']}｜相似度 {h['score']:.3f}】"
        )
        block = f"{header}\n{h['content']}"
        if total + len(block) > max_chars:
            break
        parts.append(block)
        total += len(block)

    return "\n\n---\n\n".join(parts)


_LLM_SYSTEM_PROMPT = (
    "你是嚴謹的台灣財報問答助手。\n"
    "以下提供的財報資料片段均為 Markdown 格式的表格，請從中找出問題對應的數值。\n"
    "只能使用提供的財報資料回答，不得補造數字、期間或單位。\n"
    "若找到精確數值，直接回答數字（例如：104,217,382），不要加任何解釋。\n"
    "括號負數、百分比、單位均需逐字保留（例如：( 7,439,634 )）。\n"
    "若資料中找不到答案，明確回答「找不到相關資料」。\n"
    "/no_think"
)

# ── LLM 意圖路由器 System Prompt ──────────────────────────────
_ROUTER_SYSTEM_PROMPT = """\
你是專精於台灣繁體中文財報問答的「語意路由與結構化實體抽取」專家。
請分析使用者的財務提問，精確抽取出關鍵實體槽位，並決定最佳的執行路線。
你必須「只」輸出一個合法的 JSON 物件，不得包含任何 Markdown 區塊標籤、不得有任何前後贅詞或推理過程。

欄位說明：
route      : 執行路線，三選一：
             "graph_rag"     — 問題涉及子公司、被投資公司、關係人、大陸投資、轉投資事業、供應鏈、
                               風險事件等需要跨實體多跳推導、或查閱關係明細表時
             "direct_lookup" — 問題提及明確且標準的母公司會計科目（如【資產總計】），語意極度精確時
             "semantic_rag"  — 寬鬆、口語化、非標準科目名稱提問（如「賺了多少錢」、「手上有多少現金」）
query_type : 配合路線的題型：
             graph_rag   → "entity_lookup"（查附註表格實體值）| "multi_hop_graph_reasoning"（多跳圖推理）
             direct_lookup → "single" | "cross_company" | "cross_quarter"
             semantic_rag  → "colloquial"
companies  : 問題中所有公司名稱陣列（若無則填 []）
quarters   : 時間參照陣列，直接抽取【】內的內容（民國季度如 "113Q3" 或日期字串如 "2023年1月1日至9月30日"）（若無則填 []）
table_name : 提及的特定附註表格名稱（如：列入合併財務報表之子公司）；若無則填 null
item_name  : 核心查詢目標；graph_rag 路線填目標實體名稱，其他路線填會計科目名稱
             口語科目需標準化：賺多少錢/賺了多少 → 本期淨利（損）
                               總資產 → 資產總計
                               現金 → 現金及約當現金
                               毛利 → 營業毛利（毛損）
                               營業額 → 營業收入合計

===範例===
問題：在【大聯大控股】的【列入合併財務報表之子公司】中，被投資公司【品佳電子有限公司】的【本期】是多少？
{"route":"graph_rag","query_type":"entity_lookup","companies":["大聯大控股"],"quarters":[],"table_name":"列入合併財務報表之子公司","item_name":"品佳電子有限公司"}

問題：被投資公司品佳電子在大聯大控股的子公司明細表裡面本期損益是多少啊？
{"route":"graph_rag","query_type":"entity_lookup","companies":["大聯大控股"],"quarters":[],"table_name":"子公司明細表","item_name":"品佳電子"}

問題：在【瑞昱半導體】114Q1財報中，其子公司【瑞新投資股份有限公司】對【星瑞半導體股份有限公司】的持股比例為多少？
{"route":"graph_rag","query_type":"multi_hop_graph_reasoning","companies":["瑞昱半導體"],"quarters":["114Q1"],"table_name":"子公司","item_name":"瑞新投資股份有限公司"}

問題：在【瑞昱半導體】114Q1財報的關係人交易中，與【超豐電子工業股份有限公司】的應付帳款本期餘額為多少？
{"route":"graph_rag","query_type":"multi_hop_graph_reasoning","companies":["瑞昱半導體"],"quarters":["114Q1"],"table_name":null,"item_name":"超豐電子工業股份有限公司"}

問題：請教【華邦電子】在【2023年1月1日至9月30日】的【其他利益及損失淨額】是多少？
{"route":"direct_lookup","query_type":"single","companies":["華邦電子"],"quarters":["2023年1月1日至9月30日"],"table_name":null,"item_name":"其他利益及損失淨額"}

問題：請對比【景碩科技】與【祥碩科技】在【113Q3】的【負債及權益總計 Total liabilities and equity】分別是多少？
{"route":"direct_lookup","query_type":"cross_company","companies":["景碩科技","祥碩科技"],"quarters":["113Q3"],"table_name":null,"item_name":"負債及權益總計 Total liabilities and equity"}

問題：請列出【瑞昱半導體】在【113Q3】、【114Q1】與【114Q2】三個季度中，【應付帳款：】的數字變化？
{"route":"direct_lookup","query_type":"cross_quarter","companies":["瑞昱半導體"],"quarters":["113Q3","114Q1","114Q2"],"table_name":null,"item_name":"應付帳款："}

問題：【辛耘企業】在【114Q1】賺了多少錢？
{"route":"semantic_rag","query_type":"colloquial","companies":["辛耘企業"],"quarters":["114Q1"],"table_name":null,"item_name":"本期淨利（損）"}
/no_think"""


def _call_vllm(
    base_url: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 1024,
    timeout: int = 60,
) -> str:
    """呼叫 vLLM OpenAI-compatible API。連線失敗回傳錯誤字串而非拋出例外。"""
    endpoint = f"{base_url.rstrip('/')}/chat/completions"
    payload  = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        "temperature": 0,
        "max_tokens":  max_tokens,
    }
    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type":  "application/json",
            "Authorization": "Bearer EMPTY",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        raw = result["choices"][0]["message"]["content"]
        # strip Qwen3 thinking blocks:
        # 1. closed block <think>...</think> → remove entire block
        # 2. bare tags <think> / </think> without matching pair → remove just the tag
        raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL)
        raw = re.sub(r"</?think>", "", raw)
        return raw.strip()
    except urllib.error.URLError as exc:
        return f"[vLLM 連線失敗：{exc}]"
    except (KeyError, json.JSONDecodeError) as exc:
        return f"[vLLM 回應解析失敗：{exc}]"


def _llm_intent_router(
    question: str,
    vllm_url: str,
    llm_model: str,
) -> dict[str, Any]:
    """
    LLM 意圖路由器：送問題給 Qwen3-4B-AWQ，取得純 JSON 路由決策。

    回傳欄位：
      route       : "graph_rag" | "direct_lookup" | "semantic_rag"
      query_type  : "entity_lookup" | "multi_hop_graph_reasoning" |
                    "single" | "cross_company" | "cross_quarter" | "colloquial"
      companies   : list[str]  — 問題中的公司名稱
      quarters    : list[str]  — 民國季度（"113Q3"）或日期字串（"2023年1月1日至9月30日"）
      table_name  : str | None — 附註表格名稱（graph_rag 時常有值，其他路線通常 null）
      item_name   : str        — 目標實體名稱（graph_rag）或核心會計科目（口語已轉換）

    JSON 解析失敗或 vLLM 連線失敗時，回傳預設 semantic_rag fallback。
    """
    _FALLBACK: dict[str, Any] = {
        "route":      "semantic_rag",
        "query_type": "single",
        "companies":  [],
        "quarters":   [],
        "table_name": None,
        "item_name":  "",
        "_router_error": "fallback",
    }

    _VALID_ROUTES = {"direct_lookup", "semantic_rag", "graph_rag"}

    for attempt in range(2):  # retry once on JSON parse error
        raw = _call_vllm(
            vllm_url, llm_model,
            _ROUTER_SYSTEM_PROMPT,
            f"問題：{question} /no_think",
            max_tokens=256,
        )
        if raw.startswith("[vLLM"):
            return {**_FALLBACK, "_router_error": raw[:60]}

        # Extract first JSON object from response (may have preamble text)
        json_match = re.search(r"\{[^{}]*\}", raw, re.DOTALL)
        if not json_match:
            continue
        try:
            intent: dict[str, Any] = json.loads(json_match.group())
        except json.JSONDecodeError:
            continue

        # Validate & normalise
        route = intent.get("route", "")
        if route not in _VALID_ROUTES:
            continue

        companies = intent.get("companies", [])
        if isinstance(companies, str):
            companies = [companies]
        quarters = intent.get("quarters", [])
        if isinstance(quarters, str):
            quarters = [quarters] if quarters else []
        quarters = [q for q in quarters if str(q).strip()]

        raw_table = intent.get("table_name")
        table_name: str | None = str(raw_table).strip() if raw_table and str(raw_table).strip() else None

        return {
            "route":      route,
            "query_type": intent.get("query_type", "single"),
            "companies":  [str(c) for c in companies if c],
            "quarters":   [str(q) for q in quarters],
            "table_name": table_name,
            "item_name":  str(intent.get("item_name", "")),
        }

    return _FALLBACK


def _direct_lookup(
    df: "pd.DataFrame",
    company_name: str,
    item_name: str,
    column_header: str,
    quarter: str | None = None,
) -> str | None:
    """
    精確三欄比對查找（第一軌：直接索引旁路）。

    查找順序：
      1. company_name + item_name + column_header + quarter（4-way，最精確）
      2. 若返回 0 筆，退到 3-way（company_name + item_name + column_header）
         並只在所有命中的 value_raw 完全一致時才回傳（防多值歧義）。

    回傳：value_raw 字串（去除首尾空白）；找不到或歧義時回傳 None。
    """
    base_mask = (
        (df["company_name"]   == company_name) &
        (df["item_name"]      == item_name) &
        (df["column_header"]  == column_header)
    )

    # Try 4-way with quarter first
    if quarter is not None:
        rows = df.loc[base_mask & (df["period"] == quarter), "value_raw"]
        if not rows.empty:
            unique_vals = rows.unique()
            if len(unique_vals) == 1:
                return str(unique_vals[0]).strip()

    # Fall back to 3-way (column_header already encodes the date)
    rows = df.loc[base_mask, "value_raw"]
    if rows.empty:
        return None
    unique_vals = rows.unique()
    return str(unique_vals[0]).strip() if len(unique_vals) == 1 else None


_PERIOD_LABEL_RE = re.compile(r"^\d{3}Q[1-4]$")


# 截斷科目名稱裡的英文尾綴，僅保留前段漢字/符號部分，供模糊比對用
# 例："現金及約當現金 Cash and cash equivalents" → "現金及約當現金"
_EN_SUFFIX_RE = re.compile(r"\s+[A-Za-z(（].*$")


def _fuzzy_item_match(
    item_name: str,
    candidate_items: list[str],
    cutoff: float = 0.7,
) -> str | None:
    """
    對候選科目名稱執行兩段式模糊比對，回傳最佳命中的原始字串；未達閾值則回傳 None。

    Stage A：直接用 difflib.get_close_matches 比對完整字串（命中中文完全一致的情況）。
    Stage B：截斷候選科目的英文尾綴後，用 SequenceMatcher 比對漢字部分
             （應對 "現金及約當現金 Cash and cash equivalents" 這類中英混排欄位名稱）。
    """
    if not item_name or not candidate_items:
        return None

    # Stage A：完整字串
    matches = difflib.get_close_matches(item_name, candidate_items, n=1, cutoff=cutoff)
    if matches:
        return matches[0]

    # Stage B：截斷英文尾綴後比對
    trimmed_name = _EN_SUFFIX_RE.sub("", item_name).strip()
    best_ratio, best_orig = 0.0, None
    for orig in candidate_items:
        trimmed_c = _EN_SUFFIX_RE.sub("", orig).strip()
        if not trimmed_c:
            continue
        ratio = difflib.SequenceMatcher(None, trimmed_name, trimmed_c).ratio()
        if ratio > best_ratio:
            best_ratio, best_orig = ratio, orig
    if best_ratio >= cutoff:
        return best_orig

    return None


# ── 財務本體語意同義詞矩陣（Ontology Alignment Matrix） ──────────────
# 將口語化科目名稱或同義詞統一正規化為 CSV 標準科目名，
# 確保 _direct_lookup_flex 四段比對邏輯始終對準正確的資料欄位。
_FINANCIAL_ONTOLOGY_MATRIX: dict[str, list[str]] = {
    # 正規化目標為 CSV 中實際欄位名稱「本期淨利（淨損）」（不是「本期淨利（損）」）
    "本期淨利（淨損）": [
        "本期淨利（淨損）", "本期淨利（損）", "本期淨利", "本期淨損", "本期損益",
        "賺了多少錢", "賺多少", "獲利", "淨利", "純益", "賺錢",
        "繼續營業單位本期淨利", "繼續營業單位本期淨利（淨損）",
    ],
    "資產總計": [
        "資產總計", "資產總額", "資產合計", "總資產",
        "資產總計 Total assets", "資產規模",
    ],
    "營業收入合計": [
        "營業收入合計", "營業收入", "營業收入淨額", "營業額", "營收",
        "總營收", "收益合計", "賺了多少利潤",
    ],
    "現金及約當現金": [
        "現金及約當現金", "現金", "手頭現金", "手上現金",
        "期末現金及約當現金餘額",
    ],
    "營業毛利（毛損）": [
        "營業毛利", "營業毛利（毛損）", "營業毛利（毛損）淨額",
        "毛利", "毛利總額",
    ],
}

# 反向索引：同義詞 → 標準名稱（加速 O(1) 查詢）
_ONTOLOGY_REVERSE: dict[str, str] = {
    syn: canonical
    for canonical, synonyms in _FINANCIAL_ONTOLOGY_MATRIX.items()
    for syn in synonyms
}


def _direct_lookup_flex(
    full_df: "pd.DataFrame",
    deduped_df: "pd.DataFrame",
    company_name: str,
    item_name: str,
    time_hint: str | None = None,
) -> str | None:
    """
    路由器導向的彈性查表（不需 column_header）。

    time_hint：
      民國季度標籤（如 "113Q3"）→ 比對 deduped_df 的 period 欄（去重後每期唯一值）
      日期字串（如 "2023年1月1日至9月30日"）→ 比對 full_df 的 column_header 欄
      None → 比對 deduped_df，僅在所有期間均為同一數值時才回傳

    優先嘗試 item_name 完全符合，失敗時再改用 str.contains() 子字串搜尋。
    回傳：唯一的 value_raw；有歧義或找不到時回傳 None。
    """
    # ── 語意同義詞正規化：口語科目 → 標準 CSV 欄位名 ──────────────
    item_name = _ONTOLOGY_REVERSE.get(item_name, item_name)

    is_period = time_hint is not None and _PERIOD_LABEL_RE.match(str(time_hint))
    df = deduped_df if (time_hint is None or is_period) else full_df

    # ① company_name 完全符合
    co_mask = (df["company_name"] == company_name)
    if not co_mask.any():
        co_mask = df["company_name"].str.contains(re.escape(company_name), na=False)
    if not co_mask.any():
        return None

    # ② item_name：四段遞進比對
    #   Stage 1：完全符合（最精確）
    item_mask = co_mask & (df["item_name"] == item_name)

    #   Stage 2a：前綴 + 非 CJK 邊界
    #   "現金及約當現金" 可匹配 "現金及約當現金 Cash..."（後接空格）
    #              或 "本期淨利（損）" 中的 "本期淨利"（後接全角括號 U+FF08）
    #   但 *不* 匹配 "現金及約當現金增加（減少）"（後接 CJK 漢字）
    #   ⟹ 解決 str.contains 過度命中導致 unique_vals > 1 的問題
    if not item_mask.any() and item_name:
        prefix_pat = re.escape(item_name) + r"(?:[^一-鿿]|$)"
        item_mask  = co_mask & df["item_name"].str.match(prefix_pat, na=False)

    #   Stage 2b：寬鬆子字串包含（退步，處理 router 名與 CSV 名位置不對稱的情況）
    if not item_mask.any() and item_name:
        item_mask = co_mask & df["item_name"].str.contains(
            re.escape(item_name), na=False, regex=True
        )

    #   Stage 3：difflib 模糊比對（應對細微括號差異或中英混排，cutoff=0.7）
    if not item_mask.any() and item_name:
        co_items  = df.loc[co_mask, "item_name"].dropna().unique().tolist()
        fuzzy_hit = _fuzzy_item_match(item_name, co_items, cutoff=0.7)
        if fuzzy_hit:
            item_mask = co_mask & (df["item_name"] == fuzzy_hit)

    if not item_mask.any():
        return None

    # 【變更 3】表格類型防禦：同名科目跨表混淆修正（DL 通道餘額 vs 流量 Bug）
    # Why: 「現金及約當現金」同時存在於資產負債表（期末餘額）與現金流量表（淨增減數）
    #      若不加表格篩選，unique_vals > 1 導致回傳 None，或錯誤取到流量數當餘額
    # How: 依科目語意匹配正確表格，優先縮窄 item_mask；若無匹配列則保留原 mask（安全降級）
    if "table_name" in df.columns:
        _BS_BALANCE_KW = (
            "現金及約當現金", "總資產", "資產合計", "資產總計",
            "應收帳款", "應收票據", "存貨", "流動資產", "非流動資產",
            "負債合計", "負債總計", "股東權益", "資本公積", "保留盈餘",
            "應付帳款", "應付票據", "短期借款", "長期借款", "權益合計",
            "無形資產", "商譽", "不動產廠房及設備", "使用權資產", "遞延所得稅",
        )
        _CF_FLOW_KW = (
            "現金及約當現金增加", "現金及約當現金減少",
            "期末現金及約當現金", "期初現金及約當現金",
            "營業活動之淨現金", "投資活動之淨現金", "籌資活動之淨現金",
            "本期現金及約當現金淨增", "本期現金及約當現金淨減",
        )
        if any(kw in item_name for kw in _CF_FLOW_KW):
            # 現金流量科目 → 優先限定現金流量表，排除資產負債表期末餘額干擾
            cf_mask = item_mask & df["table_name"].str.contains("現金流量", na=False)
            if cf_mask.any():
                item_mask = cf_mask
        elif any(kw in item_name for kw in _BS_BALANCE_KW):
            # 資產負債表餘額科目 → 優先限定資產負債表，排除現金流量表增減數干擾
            bs_mask = item_mask & df["table_name"].str.contains("資產負債表", na=False)
            if bs_mask.any():
                item_mask = bs_mask

    # ③ 時間過濾（含非Q1損益表單季優先邏輯）
    if time_hint is None:
        final_mask = item_mask
    elif is_period:
        final_mask = item_mask & (df["period"] == time_hint)
        # 非Q1季度：損益表同時並列「單季」（4/7/10月起）與「累計」（1月起）兩欄
        # 若問題屬於損益表科目，優先取單季欄，避免取到年初至今累計數
        quarter_num = int(str(time_hint)[-1])
        _INCOME_STMT_KW = ("淨利", "淨損", "毛利", "毛損", "收入", "損益")
        if quarter_num > 1 and any(kw in item_name for kw in _INCOME_STMT_KW):
            roc_year   = int(str(time_hint)[:3])       # e.g. 113
            western_yr = roc_year + 1911                # e.g. 2024
            start_mo   = (quarter_num - 1) * 3 + 1     # Q2→4  Q3→7  Q4→10
            sq_pat = rf"{western_yr}(?:年|/){start_mo}(?:月|/)"
            # 在 full_df（非 deduped）上找到單季欄的行
            co_full = full_df["company_name"] == company_name
            if not co_full.any():
                co_full = full_df["company_name"].str.contains(
                    re.escape(company_name), na=False)
            im_full = co_full & full_df["item_name"].str.contains(
                re.escape(item_name), na=False, regex=True)
            sq_mask = (im_full
                       & (full_df["period"] == time_hint)
                       & full_df["column_header"].str.contains(
                           sq_pat, na=False, regex=True))
            if sq_mask.any():
                sq_vals = full_df.loc[sq_mask, "value_raw"].dropna().unique()
                if len(sq_vals) == 1:
                    return str(sq_vals[0]).strip()
    else:
        # 日期字串：用前 10 個字元做 column_header 子字串比對（較長字串也能命中）
        date_key = str(time_hint)[:20]
        final_mask = item_mask & df["column_header"].str.contains(
            re.escape(date_key), na=False, regex=True
        )

    rows = df.loc[final_mask, "value_raw"]
    if rows.empty:
        return None
    unique_vals = rows.unique()
    return str(unique_vals[0]).strip() if len(unique_vals) == 1 else None


def _execute_direct_lookup_batch(
    intent: dict[str, Any],
    full_df: "pd.DataFrame",
    deduped_df: "pd.DataFrame",
) -> str | None:
    """
    依據 LLM 路由器意圖執行批次 Pandas 精確查表。

    single       : companies[0] × item_name × quarters[0]（或無季度）
    cross_company: 對每家公司各查一次，組合成 "公司A: 值 ｜ 公司B: 值"
    cross_quarter: 對每個季度各查一次，組合成 "113Q1: 值 ｜ 113Q2: 值 ｜ 113Q3: 值"

    任何子查詢回傳 None → 整批查詢失敗 → 回傳 None（交由 fallback 第二軌處理）。
    """
    qtype     = intent.get("query_type", "single")
    companies = intent.get("companies", [])
    quarters  = intent.get("quarters", [])
    item_name = intent.get("item_name", "")

    if not item_name or not companies:
        return None

    if qtype == "cross_company":
        q = quarters[0] if quarters else None
        parts: list[str] = []
        for cname in companies:
            val = _direct_lookup_flex(full_df, deduped_df, cname, item_name, q)
            if val is None:
                return None
            parts.append(f"{cname}: {val}")
        return " ｜ ".join(parts) if len(parts) >= 2 else None

    elif qtype == "cross_quarter":
        if not quarters:
            return None
        company = companies[0]
        parts = []
        for q in quarters:
            val = _direct_lookup_flex(full_df, deduped_df, company, item_name, q)
            if val is None:
                return None
            parts.append(f"{q}: {val}")
        return " ｜ ".join(parts) if len(parts) >= 2 else None

    else:  # single
        q = quarters[0] if quarters else None
        return _direct_lookup_flex(full_df, deduped_df, companies[0], item_name, q)


def _load_all_compiled_graphs() -> tuple["pd.DataFrame", "pd.DataFrame"]:
    """
    載入四大圖譜事實 CSV，合併為 GLOBAL_GRAPH_NODES_DF / GLOBAL_GRAPH_EDGES_DF。

    各圖譜資料夾：
      investment_graph_output    — 被投資公司 / INVESTS_IN 關係
      related_party_graph_output — 關係人 / HAS_RELATED_PARTY 關係
      supply_chain_graph_output  — 產業鏈上下游位置
      risk_event_graph_output    — 風險事件暴露程度
    """
    global GLOBAL_GRAPH_NODES_DF, GLOBAL_GRAPH_EDGES_DF

    all_nodes: list["pd.DataFrame"] = []
    all_edges: list["pd.DataFrame"] = []
    loaded = []

    for gname, gdir in _GRAPH_DIRS.items():
        n_path = gdir / "graph_nodes.csv"
        e_path = gdir / "graph_edges.csv"
        n_ok = e_ok = False
        try:
            if n_path.exists():
                df = pd.read_csv(n_path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
                df["_graph_source"] = gname
                all_nodes.append(df)
                n_ok = True
        except Exception as exc:
            print(f"    [GKG] {gname} nodes 讀取失敗: {exc}", flush=True)
        try:
            if e_path.exists():
                df = pd.read_csv(e_path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
                df["_graph_source"] = gname
                all_edges.append(df)
                e_ok = True
        except Exception as exc:
            print(f"    [GKG] {gname} edges 讀取失敗: {exc}", flush=True)
        if n_ok and e_ok:
            loaded.append(gname)

    GLOBAL_GRAPH_NODES_DF = pd.concat(all_nodes, ignore_index=True) if all_nodes else pd.DataFrame()
    GLOBAL_GRAPH_EDGES_DF = pd.concat(all_edges, ignore_index=True) if all_edges else pd.DataFrame()

    # ── 數值欄位正規化：去除 ownership_percent 的空格與 % 符號 ──
    if not GLOBAL_GRAPH_EDGES_DF.empty and "ownership_percent" in GLOBAL_GRAPH_EDGES_DF.columns:
        GLOBAL_GRAPH_EDGES_DF["ownership_percent"] = (
            GLOBAL_GRAPH_EDGES_DF["ownership_percent"]
            .str.strip()
            .str.rstrip("%")
            .str.strip()
        )

    total_n = len(GLOBAL_GRAPH_NODES_DF)
    total_e = len(GLOBAL_GRAPH_EDGES_DF)
    print(
        f"  ▶ 圖譜已載入（{', '.join(loaded)}）：{total_n:,} 節點 ｜ {total_e:,} 邊",
        flush=True,
    )
    return GLOBAL_GRAPH_NODES_DF, GLOBAL_GRAPH_EDGES_DF


# ── 圖譜拓撲搜尋輔助函數 ──────────────────────────────────────

def _gkg_anchor_nodes(
    entity_name: str,
    parent_companies: list[str],
    nodes_df: "pd.DataFrame",
) -> list[str]:
    """
    4 級漏斗式實體錨定：在 GLOBAL_GRAPH_NODES_DF 中找出目標實體節點 ID。

    Stage 1 完全符合：nodes_df["name"] 精確比對。
    Stage 2 正則前綴：前 6~8 字元 startswith 比對。
    Stage 3 寬鬆包含：前 4 字元 str.contains，或節點名稱被 entity_name 包含。
    Stage 4 編輯距離：difflib cutoff=0.45 模糊對齊。
    Fallback  父公司：以 intent companies 的 stock_code 或名稱前綴定位。
    """
    if nodes_df is None or nodes_df.empty:
        return []

    hits: list[str] = []

    if entity_name:
        # Stage 1: 完全符合
        exact_mask = nodes_df["name"] == entity_name
        if exact_mask.any():
            return nodes_df.loc[exact_mask, "id"].tolist()[:5]

        # Stage 2: 正則前綴（6~8 字元 startswith，大小寫不敏感）
        for plen in (8, 6):
            if len(entity_name) >= plen:
                prefix = entity_name[:plen]
                m = nodes_df["name"].str.startswith(prefix, na=False)
                if not m.any():
                    # 大小寫不敏感 fallback（英文節點名如 WPG South Asia）
                    m = nodes_df["name"].str.lower().str.startswith(prefix.lower(), na=False)
                if m.any():
                    return nodes_df.loc[m, "id"].tolist()[:5]

        # Stage 3: 寬鬆包含（前 4 字元 case-insensitive contains，或節點名為 entity_name 子串且長度 >= 3）
        short = entity_name[:4]
        loose_mask = (
            nodes_df["name"].str.contains(re.escape(short), na=False, regex=True, case=False) |
            nodes_df["name"].apply(lambda n: bool(n) and len(n) >= 3 and n in entity_name)
        )
        hits = nodes_df.loc[loose_mask, "id"].tolist()
        if hits:
            return list(dict.fromkeys(hits))[:5]

        # Stage 4: 編輯距離 difflib（cutoff=0.45，寬鬆對齊）
        candidate_names = nodes_df["name"].dropna().unique().tolist()
        best = _fuzzy_item_match(entity_name, candidate_names, cutoff=0.45)
        if best:
            mask = nodes_df["name"] == best
            return nodes_df.loc[mask, "id"].tolist()[:5]

    # Fallback：父公司 stock_code / 名稱前綴
    for co in parent_companies:
        co_mask = nodes_df["stock_code"] == co
        if not co_mask.any():
            co_mask = nodes_df["name"].str.contains(re.escape(co[:4]), na=False, regex=True)
        hits.extend(nodes_df.loc[co_mask, "id"].tolist()[:2])

    return list(dict.fromkeys(hits))[:5]


def _gkg_expand_one_hop(
    anchor_ids: list[str],
    edges_df: "pd.DataFrame",
    edge_type_filter: "list[str] | None" = None,
    max_edges: int = 30,   #  這裡硬編碼限制最多隻拿 30 條邊！
) -> "pd.DataFrame":
    """
    一階鄰居擴展：拿錨定 ID 去 edges_df 找所有以它為 source 或 target 的邊。
    edge_type_filter：限定邊的 type 欄位（None = 不限）。
    """
    if edges_df is None or edges_df.empty or not anchor_ids:
        return pd.DataFrame()

    id_set = set(anchor_ids)
    mask = edges_df["source"].isin(id_set) | edges_df["target"].isin(id_set)
    result = edges_df[mask]

    if edge_type_filter:
        result = result[result["type"].isin(edge_type_filter)]

    # 【變更 2a】財務本體論邊權重排序：關鍵結構邊浮頂，防止被 head(max_edges) 截斷
    # Why: 長路徑（如新應材→材料→供應鏈→製造→台積電）的關鍵傳導邊（AFFECTS/MAY_CAUSE）
    #      常位於 edges_df 後段，不排序直接 head() 會優先取到無意義屬性邊
    _PRIORITY_EDGE_TYPES = frozenset(["INVESTS_IN", "AFFECTS", "MAY_CAUSE",
                                       "HAS_RELATED_PARTY_TRANSACTION"])
    if not result.empty and "type" in result.columns:
        result = result.assign(
            _ep=result["type"].apply(lambda t: 0 if t in _PRIORITY_EDGE_TYPES else 1)
        ).sort_values("_ep", kind="stable").drop(columns=["_ep"])

    return result.head(max_edges)


def _gkg_resolve_node_name(node_id: str, nodes_df: "pd.DataFrame") -> str:
    """將 node_id 解析為人類可讀的 name。"""
    if nodes_df is None or nodes_df.empty:
        return node_id
    m = nodes_df[nodes_df["id"] == node_id]
    if not m.empty:
        name = m.iloc[0].get("name", "")
        if name:
            return name
    # 從 id 推斷（去除前綴）
    parts = node_id.split(":", 1)
    return parts[1] if len(parts) > 1 else node_id


def _gkg_build_investment_context(
    hop1_edges: "pd.DataFrame",
    anchor_ids: set[str],
    nodes_df: "pd.DataFrame",
    intent: dict,
) -> list[str]:
    """
    組裝 investment graph 的圖譜脈絡描述。
    重點邊類型：INVESTS_IN、DISCLOSES_INVESTOR
    """
    lines: list[str] = []
    quarters = set(intent.get("quarters") or [])

    invest_edges = hop1_edges[hop1_edges["type"] == "INVESTS_IN"]
    if invest_edges.empty:
        return lines

    lines.append("**【投資關係圖譜 (Investment Graph)】**")
    for _, row in invest_edges.head(20).iterrows():
        src_name = _gkg_resolve_node_name(row.get("source", ""), nodes_df)
        tgt_name = _gkg_resolve_node_name(row.get("target", ""), nodes_df)
        period   = row.get("report_period", "")

        # 期間過濾（intent 有指定季度時）
        if quarters and period and period not in quarters:
            continue

        own_pct  = row.get("ownership_percent", "")
        bv       = row.get("book_value", "")
        inc_loss = row.get("investment_income_loss", "")
        note_val = row.get("note", "")
        loc      = row.get("location", "")
        biz      = row.get("main_business", "")

        parts = []
        if own_pct:
            parts.append(f"持股比率={own_pct}%")
        if bv:
            parts.append(f"帳面金額={bv}")
        if inc_loss:
            parts.append(f"本期損益={note_val or inc_loss}")
        if loc:
            parts.append(f"所在地={loc}")
        if biz:
            parts.append(f"主要業務={biz}")
        if period:
            parts.append(f"期間={period}")

        attr_str = ", ".join(parts)
        lines.append(f"* [{src_name}] --INVESTS_IN--> [{tgt_name}]：{attr_str}")

    return lines


def _gkg_build_related_party_context(
    hop1_edges: "pd.DataFrame",
    anchor_ids: set[str],
    nodes_df: "pd.DataFrame",
    intent: dict,
    priority_parties: list[str] | None = None,
) -> list[str]:
    """組裝 related_party graph 的圖譜脈絡描述。

    priority_parties: 若指定，將包含這些名稱（前2字）的列排到最前面，
                      確保在 head(80) 截斷前能被看到（如 Q60 品佳電子）。
    """
    lines: list[str] = []
    quarters = set(intent.get("quarters") or [])

    rp_edges = hop1_edges[hop1_edges["type"].isin([
        "HAS_RELATED_PARTY_TRANSACTION", "HAS_RELATED_PARTY",
        "RELATED_PARTY_TRANSACTION_WITH", "HAS_TRANSACTION",
    ])]
    if rp_edges.empty:
        return lines

    lines.append("**【關係人圖譜 (Related Party Graph)】**")
    # 先按期間過濾，避免 head(80) 全取到錯誤季度
    if quarters:
        q_filtered = rp_edges[rp_edges["report_period"].isin(quarters)]
        rp_iter = q_filtered if not q_filtered.empty else rp_edges
    else:
        rp_iter = rp_edges

    # 若有 priority_parties，將含指定公司的列浮到最上方，確保不被截斷
    if priority_parties:
        short_names = [p[:2] for p in priority_parties if len(p) >= 2]
        if short_names:
            prio = rp_iter["party_or_category"].apply(
                lambda v: 0 if v and any(s in str(v) for s in short_names) else 1
            )
            rp_iter = rp_iter.assign(_prio=prio).sort_values("_prio").drop(columns=["_prio"])

    seen: set[str] = set()
    for _, row in rp_iter.head(80).iterrows():
        # 使用 party_or_category 作為關係人顯示名稱（target 是 hash ID）
        party   = row.get("party_or_category") or row.get("related_party_name") or ""
        account = row.get("account", "")
        period  = row.get("report_period", "")

        dedup_key = f"{party}|{account}|{period}"
        if dedup_key in seen:
            continue
        seen.add(dedup_key)

        src_name = _gkg_resolve_node_name(row.get("source", ""), nodes_df)
        # 優先用 party_or_category；hash target node 不含可讀名稱
        tgt_name = party or _gkg_resolve_node_name(row.get("target", ""), nodes_df)

        rel_desc = row.get("relationship_desc", "")
        amount   = row.get("amount_summary", "")
        rel_cat  = row.get("relation_category", "")

        parts = []
        if rel_desc or rel_cat:
            parts.append(f"關係={rel_desc or rel_cat}")
        if account:
            parts.append(f"帳目={account}")
        if amount:
            parts.append(f"金額={amount}")
        if period:
            parts.append(f"期間={period}")

        attr_str = ", ".join(parts)
        etype = row.get("type", "HAS_RELATED_PARTY_TRANSACTION")
        lines.append(f"* [{src_name}] --{etype}--> [{tgt_name}]：{attr_str}")

    return lines


def _gkg_build_supply_chain_context(
    hop1_edges: "pd.DataFrame",
    anchor_ids: set[str],
    nodes_df: "pd.DataFrame",
) -> list[str]:
    """組裝 supply_chain graph 的圖譜脈絡描述。"""
    lines: list[str] = []
    sc_edges = hop1_edges[hop1_edges["type"] == "HAS_COMPANY"]
    if sc_edges.empty:
        return lines

    lines.append("**【產業鏈圖譜 (Supply Chain Graph)】**")
    for _, row in sc_edges.head(5).iterrows():
        src_name = _gkg_resolve_node_name(row.get("source", ""), nodes_df)
        tgt_name = _gkg_resolve_node_name(row.get("target", ""), nodes_df)
        stage    = row.get("stage", "")
        segment  = row.get("segment", "")
        market   = row.get("market", "")
        parts = []
        if stage:
            parts.append(f"階段={stage}")
        if segment:
            parts.append(f"細分={segment}")
        if market:
            parts.append(f"市場={market}")
        attr_str = ", ".join(parts)
        edge_type = row.get("type", "")
        lines.append(f"* [{src_name}] --{edge_type}--> [{tgt_name}]：{attr_str}")

    return lines


def _gkg_build_risk_event_context(
    hop1_edges: "pd.DataFrame",
    anchor_ids: set[str],
    nodes_df: "pd.DataFrame",
    intent: dict,
) -> list[str]:
    """組裝 risk_event graph 的圖譜脈絡描述。
    處理邊類型：EXPOSED_TO（公司→風險）、MAY_CAUSE/AFFECTS（風險→風險傳導）
    """
    lines: list[str] = []
    quarters = set(intent.get("quarters") or [])

    risk_edges = hop1_edges[hop1_edges["type"].isin(["EXPOSED_TO", "MAY_CAUSE", "AFFECTS"])]
    if risk_edges.empty:
        return lines

    lines.append("**【風險事件圖譜 (Risk Event Graph)】**")
    seen: set[str] = set()
    for _, row in risk_edges.head(20).iterrows():
        src = row.get("source", "")
        tgt = row.get("target", "")
        etype = row.get("type", "EXPOSED_TO")
        dedup_key = f"{src}|{tgt}|{etype}"
        if dedup_key in seen:
            continue
        seen.add(dedup_key)

        src_name = _gkg_resolve_node_name(src, nodes_df)
        tgt_name = _gkg_resolve_node_name(tgt, nodes_df)
        period   = row.get("period", "")

        if etype == "EXPOSED_TO" and quarters and period:
            period_q = period.replace("-", "").upper()
            if not any(period_q.endswith(q[-2:]) or q in period_q for q in quarters):
                continue

        # matched_keywords 作 OR 鏈：matched_risk 優先，但空字串時 fallback 到 matched_keywords
        matched  = row.get("matched_risk") or row.get("matched_keywords") or ""
        ev_level = row.get("evidence_level", "")

        parts = []
        if matched:
            parts.append(f"匹配科目={matched}")
        if ev_level:
            parts.append(f"強度={ev_level}")
        if period:
            parts.append(f"期間={period}")

        attr_str = ", ".join(parts)
        lines.append(f"* [{src_name}] --{etype}--> [{tgt_name}]：{attr_str}")

    return lines


def _gkg_find_invest_edges_for_entity(
    parent_ids: list[str],
    entity_name: str,
    edges_df: "pd.DataFrame",
    nodes_df: "pd.DataFrame",
    intent: dict,
) -> "pd.DataFrame":
    """
    從父公司的所有 INVESTS_IN 邊中，以 entity_name 模糊比對 target 節點名稱，
    返回最匹配的投資邊（可能跨多期）。
    """
    if not parent_ids or not entity_name:
        return pd.DataFrame()

    quarters = set(intent.get("quarters") or [])
    parent_hop = _gkg_expand_one_hop(parent_ids, edges_df, max_edges=500)
    invest = parent_hop[parent_hop["type"] == "INVESTS_IN"]
    if invest.empty:
        return pd.DataFrame()

    # 建立 target_id → name 映射
    target_ids = invest["target"].unique().tolist()
    id_to_name: dict[str, str] = {
        tid: _gkg_resolve_node_name(tid, nodes_df) for tid in target_ids
    }
    candidate_names = list(id_to_name.values())

    # 精確比對
    best_name = None
    exact_names = [n for n in candidate_names if entity_name in n or n in entity_name]
    if exact_names:
        best_name = exact_names[0]
    else:
        # difflib 模糊（前 6 字元過濾後比對）
        prefix = entity_name[:6]
        pre_filtered = [n for n in candidate_names if prefix in n] or candidate_names
        best_name = _fuzzy_item_match(entity_name, pre_filtered, cutoff=0.45)

    if not best_name:
        return pd.DataFrame()

    best_tid = next((tid for tid, name in id_to_name.items() if name == best_name), None)
    if not best_tid:
        return pd.DataFrame()

    matched = invest[invest["target"] == best_tid]

    # 期間篩選（有指定季度時優先；否則取最新期的非空 note 行）
    if quarters:
        q_matched = matched[matched["report_period"].isin(quarters)]
        if not q_matched.empty:
            return q_matched
    # 按期間降序，取最新
    matched = matched.sort_values("report_period", ascending=False)
    return matched.head(4)  # 最多 4 期


def _graphrag_topology_search(
    intent: dict[str, Any],
    question: str,
    vllm_url: str,
    llm_model: str,
) -> str | None:
    """
    局部圖譜上下文檢索 (Graph Local Context Extraction)。

    雙路徑策略：
      路徑 A（父公司出發）：
        parent_ids → INVESTS_IN/HAS_RELATED_PARTY → 模糊比對 target 名稱 → 取匹配邊
      路徑 B（實體直接錨定）：
        entity_ids → 1-hop 展開 → 取所有相鄰邊（supply_chain、risk_event 常用）

    流程：
      1. 解析問句 / intent → q_company, entity_name, q_col_header
      2. 父公司錨定 + 投資邊模糊搜尋（路徑 A）
      3. 實體直接錨定 → 1-hop 展開（路徑 B）
      4. 合併所有上下文行
      5. LLM 階層推理（Qwen3 生成答案）
    """
    nodes_df = GLOBAL_GRAPH_NODES_DF
    edges_df = GLOBAL_GRAPH_EDGES_DF
    if nodes_df is None or nodes_df.empty or edges_df is None or edges_df.empty:
        return None

    # ── Step 1: 解析問句 ─────────────────────────────────────
    entity_name:  str = ""
    q_company:    str = ""
    q_col_header: str = ""

    m_re = _ENTITY_QA_RE.search(question)
    if m_re:
        q_company    = m_re.group(1)
        entity_name  = m_re.group(3)
        q_col_header = m_re.group(4)
    else:
        entity_name = intent.get("item_name", "")
        companies   = intent.get("companies") or []
        q_company   = companies[0] if companies else ""

    # ── Step 2: 路徑 A — 父公司出發（INVESTS_IN / HAS_RELATED_PARTY）───
    ctx_lines: list[str] = []
    parent_ids = _gkg_anchor_nodes("", [q_company], nodes_df) if q_company else []

    if parent_ids and entity_name:
        # 投資關係
        invest_edges = _gkg_find_invest_edges_for_entity(
            parent_ids, entity_name, edges_df, nodes_df, intent
        )
        if not invest_edges.empty:
            invest_ctx = _gkg_build_investment_context(
                invest_edges, set(parent_ids), nodes_df, intent
            )
            if invest_ctx:
                ctx_lines.extend(invest_ctx)
                ctx_lines.append("")

        # 關係人關係 — 直接全量查詢，不受 max_edges 位置限制
        parent_set_a = set(parent_ids)
        rp_direct_a = edges_df[
            edges_df["type"].isin([
                "HAS_RELATED_PARTY_TRANSACTION", "HAS_RELATED_PARTY",
                "RELATED_PARTY_TRANSACTION_WITH",
            ]) &
            (edges_df["source"].isin(parent_set_a) | edges_df["target"].isin(parent_set_a))
        ]
        # 把 intent["companies"] 中其他公司作為 priority_parties：
        # 優先排到 head(80) 最前面，避免在大型關係人清單中被截斷（如 Q60 品佳電子）
        _extra_cos_a = [c for c in (intent.get("companies") or []) if c != q_company]
        rp_ctx = _gkg_build_related_party_context(
            rp_direct_a, parent_set_a, nodes_df, intent,
            priority_parties=_extra_cos_a or None
        )
        if rp_ctx:
            # 過濾出與 entity_name 或其他公司相關的行（2 字元前綴）
            entity_short = entity_name[:2] if len(entity_name) >= 2 else entity_name
            extra_shorts = [c[:2] for c in _extra_cos_a if len(c) >= 2]
            rp_filtered = [
                ln for ln in rp_ctx
                if not ln.startswith("*")
                or entity_short in ln
                or any(s in ln for s in extra_shorts)
                or ln.startswith("**")
            ]
            if len(rp_filtered) > 1:
                ctx_lines.extend(rp_filtered)
                ctx_lines.append("")

    # ── Step 3: 路徑 B — 實體直接錨定 ────────────────────────
    entity_ids = _gkg_anchor_nodes(entity_name, [], nodes_df) if entity_name else []
    if not entity_ids and q_company:
        # 如果 entity 錨定失敗，用父公司做路徑 B
        entity_ids = parent_ids

    if entity_ids:
        anchor_set = set(entity_ids)

        # 永遠把父公司加入 anchor_set：entity 可能錯定到 meta 節點（如 risk_event_network / industry_chain）
        # 加入 parent_ids 確保 company-level 邊（EXPOSED_TO / HAS_COMPANY）都能被查到
        if parent_ids:
            anchor_set.update(parent_ids)

        # entity_anchor 僅包含原始實體節點（不含 parent_ids）：
        # 用於 INVESTS_IN 查詢，避免把父公司直接持股誤混入孫公司 2-hop 路徑
        entity_anchor: set[str] = set(entity_ids)

        # 多公司錨定擴展：把 intent["companies"] 中其他公司也加入兩個集合
        # （支援 Q58 型「創意電子+聯發科技 共同產業鏈」等跨公司問題）
        extra_cos = [c for c in (intent.get("companies") or []) if c != q_company]
        for _eco in extra_cos:
            _eco_ids = _gkg_anchor_nodes("", [_eco], nodes_df)
            anchor_set.update(_eco_ids)
            entity_anchor.update(_eco_ids)

        # ── 路徑 B：各維度直接全量查詢（繞過 max_edges 位置限制）──────

        # 投資關係 (INVESTS_IN) — 僅用 entity_anchor（子公司節點），捕捉孫公司持股
        # 不用 anchor_set 以避免引入父公司大量直接投資（Q54 瑞新→星瑞 vs 瑞昱直接持股）
        if entity_anchor:
            _inv_b = edges_df[
                (edges_df["type"] == "INVESTS_IN") &
                edges_df["source"].isin(entity_anchor)
            ]
            if not _inv_b.empty:
                inv_ctx_b = _gkg_build_investment_context(_inv_b, entity_anchor, nodes_df, intent)
                if inv_ctx_b:
                    # 不阻擋：Path A 加了父→子投資，Path B 需加子→孫投資（2-hop）
                    ctx_lines.extend(inv_ctx_b)
                    ctx_lines.append("")

        # 供應鏈 (HAS_COMPANY) — 位於 DataFrame 後段（~pos 56466），必須直接查詢
        _sc_b = edges_df[
            (edges_df["type"] == "HAS_COMPANY") &
            (edges_df["target"].isin(anchor_set) | edges_df["source"].isin(anchor_set))
        ]
        if not _sc_b.empty:
            sc_ctx = _gkg_build_supply_chain_context(_sc_b, anchor_set, nodes_df)
            if sc_ctx and not any("產業鏈圖譜" in ln for ln in ctx_lines):
                ctx_lines.extend(sc_ctx)
                ctx_lines.append("")

        # 風險事件 (EXPOSED_TO / MAY_CAUSE / AFFECTS) — 位於 DataFrame 後段
        _re_b = edges_df[
            edges_df["type"].isin(["EXPOSED_TO", "MAY_CAUSE", "AFFECTS"]) &
            (edges_df["source"].isin(anchor_set) | edges_df["target"].isin(anchor_set))
        ]
        if not _re_b.empty:
            re_ctx = _gkg_build_risk_event_context(_re_b, anchor_set, nodes_df, intent)
            if re_ctx and not any("風險事件圖譜" in ln for ln in ctx_lines):
                ctx_lines.extend(re_ctx)
                ctx_lines.append("")

        # 關係人交易 (HAS_RELATED_PARTY_TRANSACTION) — Path B 補充（entity 為申報公司時）
        _rpt_b = edges_df[
            edges_df["type"].isin([
                "HAS_RELATED_PARTY_TRANSACTION", "RELATED_PARTY_TRANSACTION_WITH",
            ]) &
            (edges_df["source"].isin(anchor_set) | edges_df["target"].isin(anchor_set))
        ]
        if not _rpt_b.empty and not any("關係人圖譜" in ln for ln in ctx_lines):
            rp_ctx_b = _gkg_build_related_party_context(_rpt_b, anchor_set, nodes_df, intent)
            if rp_ctx_b:
                ctx_lines.extend(rp_ctx_b)
                ctx_lines.append("")

    if not ctx_lines or all(ln.strip() == "" for ln in ctx_lines):
        ename_short = repr(entity_name[:20])
        print(f"    [GKG] 圖譜脈絡為空（entity={ename_short}, co={q_company!r}），降級",
              flush=True)
        return None

    # 【變更 2b】拓撲優先截斷：確保 INVESTS_IN/AFFECTS/MAY_CAUSE/HAS_RELATED_PARTY_TRANSACTION
    # 關鍵邊行在 80 行門票中優先保留；次要屬性行與純文字描述後排再截斷
    # Why: 舊版直接 [:80] 在 Q58 多公司 140 行案例中，關鍵 INVESTS_IN 邊被大量 EXPOSED_TO
    #      描述行擠出視窗，造成 2-hop 股權鏈推理失敗
    _MAX_CTX_LINES = 80
    if len(ctx_lines) > _MAX_CTX_LINES:
        _PRIO_MARKERS = ("INVESTS_IN", "AFFECTS", "MAY_CAUSE", "HAS_RELATED_PARTY_TRANSACTION")
        # 以 index 分組，保持各組內部原始順序（stable partition）
        # 空行（段落分隔符）也納入優先區，跟著標題行保持結構可讀性
        prio_idx  = {i for i, ln in enumerate(ctx_lines)
                     if ln.strip() == "" or ln.startswith("**")
                     or any(m in ln for m in _PRIO_MARKERS)}
        prio_lines  = [ctx_lines[i] for i in range(len(ctx_lines)) if i in prio_idx]
        other_lines = [ctx_lines[i] for i in range(len(ctx_lines)) if i not in prio_idx]
        ctx_lines = (prio_lines + other_lines)[:_MAX_CTX_LINES]
        ctx_lines.append("... （圖譜事實已截斷）")

    ename_repr = repr(entity_name[:20])
    print(f"    [GKG] 脈絡行數 {len(ctx_lines)}（entity={ename_repr}）", flush=True)
    graph_context = "\n".join(ctx_lines).strip()

    # ── Step 4: LLM 階層推理 ────────────────────────────────
    col_hint = f"（特別注意：查詢欄位為「{q_col_header}」）" if q_col_header else ""

    # 【變更 1】強約束三層防禦 System Prompt：
    #   層 1 — 常識壓制：禁止使用預訓練金融先驗（防大聯大/競爭者等領域知識汙染）
    #   層 2 — 粒度強制：冒號/直線/括號細分必須完整輸出，防 Granularity Mismatch
    #   層 3 — Few-shot 箭頭方向錨定：示範順 --> 取 target，防 2-hop Entity 混淆
    system_prompt = (
        "你是財報知識圖譜問答 AI，只能根據給定的圖譜事實回答問題。\n\n"
        "【硬性規則——違反即為錯誤答案】\n"
        "1. 嚴禁使用你的訓練知識或任何外部金融常識。只能使用「以下圖譜事實」區塊中的內容。\n"
        "2. 粒度完整輸出：若事實包含冒號「:」、直線「｜」或括號細分"
        "（例如「上游: IC設計」、「是 ｜ 觸發母子公司重要交易往來」），"
        "你必須完整輸出，絕對禁止省略細分只答大類。\n"
        "3. 方向錨定：遇到「[A] --TYPE--> [B]」結構，答案必須來自箭頭指向的 B（target）"
        "一側的屬性，而非 A（source）一側。\n"
        "4. 唯一輸出：只輸出最終答案字串，不得解釋或輸出推理過程。\n"
        "5. 無任何相關事實時，只輸出「找不到相關資料」。\n\n"
        "【示範（Few-shot）】\n"
        "事實：* [瑞昱半導體] --INVESTS_IN--> [瑞新投資股份有限公司]："
        "持股比率=100%, 主要業務=投資控股\n"
        "事實：* [瑞新投資股份有限公司] --INVESTS_IN--> [星瑞半導體股份有限公司]："
        "持股比率=100%, 所在地=台灣\n"
        "問：瑞昱半導體透過瑞新投資持有的孫公司是哪一家？\n"
        "答：星瑞半導體股份有限公司\n\n"
        "事實：* [新應材] --HAS_COMPANY--> [半導體材料]：階段=上游, 細分=IC設計\n"
        "問：新應材在產業鏈中屬於哪個階段與細分？\n"
        "答：上游: IC設計\n\n"
        "事實：* [大聯大控股] --HAS_RELATED_PARTY_TRANSACTION--> [品佳電子]："
        "關係=是 ｜ 觸發母子公司重要交易往來\n"
        "問：大聯大控股與品佳電子的關係人交易關係為何？\n"
        "答：是 ｜ 觸發母子公司重要交易往來"
    )
    user_prompt = (
        f"以下是從財務知識圖譜擷取的相關事實：\n\n"
        f"{graph_context}\n\n"
        f"請根據以上圖譜事實，精確回答以下問題{col_hint}：\n{question}\n\n答案：/no_think"
    )

    answer = _call_vllm(vllm_url, llm_model, system_prompt, user_prompt, max_tokens=256)

    if not answer or answer.startswith("[vLLM"):
        print(f"    [GKG] vLLM 無回答，降級", flush=True)
        return None

    print(f"    [GKG] Layer 2a 命中: {answer[:40]}", flush=True)
    return answer


def _graphrag_ms_local_search(
    question: str,
    entity_name: str,
    index_path: Path,
    vllm_url: str,
    llm_model: str,
) -> str | None:
    """
    Layer 1：Microsoft GraphRAG LocalSearch API。
    只在套件已安裝且 index_path 下有 artifacts/*.parquet 時啟用。
    """
    if not _GRAPHRAG_PKG_AVAILABLE:
        return None
    artifacts = index_path / "output" / "artifacts"
    if not (artifacts / "create_final_entities.parquet").exists():
        return None
    try:
        import pandas as pd_local  # noqa: F401

        # 動態建立 LocalSearch 引擎（使用 vLLM OpenAI 相容端點）
        from graphrag.query.llm.oai.chat_openai import ChatOpenAI  # type: ignore
        from graphrag.query.llm.oai.typing import OpenaiApiType  # type: ignore
        from graphrag.query.structured_search.local_search.mixed_context import (  # type: ignore
            LocalSearchMixedContext,
        )

        llm = ChatOpenAI(
            api_base=vllm_url,
            api_key="dummy",
            model=llm_model,
            api_type=OpenaiApiType.OpenAI,
            max_retries=2,
        )

        entities_df    = pd_local.read_parquet(artifacts / "create_final_entities.parquet")
        text_units_df  = pd_local.read_parquet(artifacts / "create_final_text_units.parquet")
        relationships_df = pd_local.read_parquet(artifacts / "create_final_relationships.parquet")
        community_df   = pd_local.read_parquet(artifacts / "create_final_community_reports.parquet")

        context_builder = LocalSearchMixedContext(
            entities=entities_df,
            entity_text_embeddings=None,
            text_units=text_units_df,
            relationships=relationships_df,
            community_reports=community_df,
            text_embedder=None,
        )

        engine = _MsLocalSearch(
            llm=llm,
            context_builder=context_builder,
            token_encoder=None,
        )
        import asyncio
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(engine.asearch(question))
        loop.close()

        answer = result.response if hasattr(result, "response") else str(result)
        return answer if answer and answer.strip() else None
    except Exception as exc:
        print(f"\n    [LOG] GraphRAG Layer 1 例外: {exc}", flush=True)
        return None


def _graphrag_entity_table_lookup(
    question: str,
    intent: dict[str, Any],
    entity_df: "pd.DataFrame",
) -> str | None:
    """
    Layer 2：本地實體明細表直查（entity_df）。
    適用於 Type C「列入合併財務報表之子公司」等 entity table 查詢。

    解析 _ENTITY_QA_RE 取得 table_name、entity_item_name、column_header，
    再從 entity_df 精確查詢。
    """
    if entity_df is None or entity_df.empty:
        return None

    # ── 從問句解析結構 ────────────────────────────────────────
    m = _ENTITY_QA_RE.search(question)
    if m:
        q_company     = m.group(1)   # e.g. "大聯大控股"
        q_table_hint  = m.group(2)   # e.g. "列入合併財務報表之子公司"
        q_entity      = m.group(3)   # e.g. "品佳電子有限公司"
        q_col_header  = m.group(4)   # e.g. "本期"
    else:
        # 回退：從 intent 取已解析欄位
        q_company     = (intent.get("companies") or [""])[0]
        q_table_hint  = ""
        q_entity      = intent.get("item_name", "")
        q_col_header  = ""

    if not q_entity:
        return None

    # ── 找到父公司（直接匹配 entity_df.company_name）───────────
    if q_company:
        co_exact = entity_df["company_name"] == q_company
        if co_exact.any():
            co_mask = co_exact
        else:
            co_mask = entity_df["company_name"].str.contains(
                re.escape(q_company), na=False, regex=True
            )
    else:
        co_mask = pd.Series(True, index=entity_df.index)
    sub = entity_df[co_mask]
    if sub.empty:
        return None

    # ── table_name 過濾 ──────────────────────────────────────
    if q_table_hint:
        tbl_mask = sub["table_name"].str.contains(
            re.escape(q_table_hint[:10]), na=False, regex=True
        )
        if tbl_mask.any():
            sub = sub[tbl_mask]

    # ── entity item_name 精確 / 模糊匹配 ─────────────────────
    exact_mask = sub["item_name"] == q_entity
    if exact_mask.any():
        sub = sub[exact_mask]
    else:
        candidate_items = sub["item_name"].dropna().unique().tolist()
        best = _fuzzy_item_match(q_entity, candidate_items, cutoff=0.65)
        if best:
            sub = sub[sub["item_name"] == best]
        else:
            contains_mask = sub["item_name"].str.contains(
                re.escape(q_entity[:8]), na=False, regex=True
            )
            if contains_mask.any():
                sub = sub[contains_mask]
            else:
                return None

    # ── column_header 過濾 ───────────────────────────────────
    if q_col_header:
        ch_exact = sub["column_header"] == q_col_header
        if ch_exact.any():
            sub = sub[ch_exact]
        else:
            ch_contains = sub["column_header"].str.contains(
                re.escape(q_col_header), na=False, regex=True
            )
            if ch_contains.any():
                sub = sub[ch_contains]

    if sub.empty:
        return None

    # ── 期間過濾（若問句或 intent 含明確季度標籤，精確鎖定單期）────────────
    q_period = (intent.get("quarters") or [None])[0]
    if q_period and _PERIOD_LABEL_RE.match(str(q_period)):
        pm = sub["period"] == q_period
        if pm.any():
            sub = sub[pm]

    # ── 取值：多 facts 選取邏輯 ──────────────────────────────────────
    # 有精確期間過濾時：取首筆有效值（同表首行通常為主要持股 / 主要交易紀錄）
    # 無期間過濾時：全量拼接確保正確值包含在答案字串中
    vals = sub["value_raw"].dropna()
    if vals.empty:
        return None
    unique_vals = vals.unique()
    if len(unique_vals) == 1:
        return str(unique_vals[0]).strip()
    # 多相異值：按原始列順序收集非空值
    cleaned = [str(v).strip() for v in sub["value_raw"]
               if str(v).strip() not in ("", "nan", "None", "NaN")]
    if not cleaned:
        return None
    if len(cleaned) == 1:
        return cleaned[0]
    # 已套用期間過濾 → 取首筆（主要持股或首排交易）；未過濾 → 全量拼接
    if q_period and _PERIOD_LABEL_RE.match(str(q_period)):
        return cleaned[0]
    return " ｜ ".join(dict.fromkeys(cleaned))


def _execute_graph_rag_search(
    intent: dict[str, Any],
    question: str,
    entity_df: "pd.DataFrame | None" = None,
    graph_db_url: str | None = None,
    vllm_url: str = DEFAULT_VLLM_URL,
    llm_model: str = DEFAULT_LLM_MODEL,
) -> str | None:
    """
    FinGraph RAG — 四層降級知識圖譜搜尋。

    Layer 1   Microsoft GraphRAG LocalSearch（需套件 + 已建立索引）
    Layer 2a  圖譜拓撲搜尋（四大編譯圖譜：_graphrag_topology_search）
              entity anchoring → 1-hop expansion → context assembly → vLLM 推理
    Layer 2b  本地實體明細表直查（entity_df；Type C 精確值備援）
    Layer 3   return None → 降級至 ChromaDB 向量搜尋

    觸發條件（由 _rag_query_one 判斷）：
      · route == "graph_rag"（LLM 明確路由）
      · 或 query_type in ("entity_lookup", "multi_hop_graph_reasoning")
      · 或 route != "direct_lookup" 且 item_name 含 _GRAPH_ENTITY_KEYWORDS（兜底）
    """
    entity_short = str(intent.get("item_name", ""))[:30]
    print(
        f"\n    [GKG] GraphRAG 路由"
        f"（type={intent.get('query_type', '?')}, entity={entity_short}）",
        flush=True,
    )

    if not _GRAPH_ENABLED:
        return None

    # ── Layer 1：Microsoft GraphRAG LocalSearch ───────────────
    index_path = Path(graph_db_url) if graph_db_url else _GRAPHRAG_INDEX_PATH
    if _GRAPHRAG_PKG_AVAILABLE and index_path.exists():
        result = _graphrag_ms_local_search(
            question, intent.get("item_name", ""), index_path, vllm_url, llm_model
        )
        if result is not None:
            print(f"    [GKG] Layer 1 (MS GraphRAG) 命中", flush=True)
            return result

    # ── Layer 2 路由策略：
    #   entity_lookup → 先走 entity_df（精確表格值），失敗再走 topology（圖關係）
    #   其他類型（關係語意查詢）→ 先走 topology，再走 entity_df
    query_type = intent.get("query_type", "")

    if query_type == "entity_lookup":
        # ── Layer 2a（優先）：entity_df 精確表格直查 ──────────
        if entity_df is not None and not entity_df.empty:
            result = _graphrag_entity_table_lookup(question, intent, entity_df)
            if result is not None:
                print(f"    [GKG] Layer 2a (entity_df) 命中: {result[:30]}", flush=True)
                return result

        # ── Layer 2b（備援）：圖譜拓撲搜尋 ──────────────────
        if GLOBAL_GRAPH_NODES_DF is not None and not GLOBAL_GRAPH_NODES_DF.empty:
            result = _graphrag_topology_search(intent, question, vllm_url, llm_model)
            if result is not None:
                return result

    else:
        # ── Layer 2a（優先）：圖譜拓撲搜尋（關係語意查詢） ──
        if GLOBAL_GRAPH_NODES_DF is not None and not GLOBAL_GRAPH_NODES_DF.empty:
            result = _graphrag_topology_search(intent, question, vllm_url, llm_model)
            if result is not None:
                return result

        # ── Layer 2b（備援）：entity_df 表格直查 ──────────────
        if entity_df is not None and not entity_df.empty:
            result = _graphrag_entity_table_lookup(question, intent, entity_df)
            if result is not None:
                print(f"    [GKG] Layer 2b (entity_df) 命中: {result[:30]}", flush=True)
                return result

    return None


# ── 向量消融基線：正則提取輔助 ──────────────────────────────────
_VO_BRACKET_RE = re.compile(r"【([^】]+)】")
_VO_QUARTER_RE = re.compile(r"^\d{3}Q[1-4]$")


def _regex_extract_for_vector_only(
    question: str,
    company_map: dict[str, str],
) -> tuple[list[str], list[str]]:
    """
    純正則從問題文本的【...】標記中提取公司代碼與季度列表。
    無需 LLM 意圖路由器，供 vector_only 消融模式使用。

    回傳:
        company_codes  : list[str] — 解析出的公司代碼（可能多家，維持問句順序）
        query_quarters : list[str] — 解析出的所有 ROC 季度標籤（可能多個，Type B 情境）
    """
    tokens = _VO_BRACKET_RE.findall(question)
    company_codes: list[str] = []
    query_quarters: list[str] = []
    seen_codes: set[str] = set()

    for token in tokens:
        t = token.strip()
        if _VO_QUARTER_RE.match(t):
            query_quarters.append(t)
            continue
        code = _resolve_company_code(t, company_map)
        if code and code not in seen_codes:
            company_codes.append(code)
            seen_codes.add(code)

    return company_codes, query_quarters


def _rag_query_one(
    question: str,
    collection,
    embedder: _BGEEmbedder,
    company_map: dict[str, str],
    vllm_url: str,
    llm_model: str,
    top_k: int = 5,
    facts_df: "pd.DataFrame | None" = None,
    deduped_df: "pd.DataFrame | None" = None,
    entity_df: "pd.DataFrame | None" = None,
    vector_only: bool = False,
    llm_only: bool = False,
    graph_only: bool = False,
    no_direct: bool = False,
) -> dict[str, Any]:
    """
    單筆 RAG 查詢（LLM 意圖路由器版）。

    流程：
      Step 1    LLM Intent Router → 解析 route / query_type / companies / quarters / item_name
      Step 1.5  GraphRAG 調度（entity_lookup 或 item_name 含子公司關鍵字）
                _execute_graph_rag_search：未啟用時降級，進入下一步
      Step 2    第一軌 — Pandas 精確查表（route == "direct_lookup"）
                _execute_direct_lookup_batch → single / cross_company / cross_quarter
                三段比對：完全符合 → str.contains → difflib 模糊（cutoff=0.7）
                失敗 → fallback 進入第二軌
      Step 3    第二軌 — ChromaDB 語意向量 + vLLM 生成

    消融實驗旗標：
      vector_only=True  跳過 Step 1/1.5/2，直接進入 Step 3
      llm_only=True     跳過所有檢索，直接送 LLM（無 context）
      graph_only=True   Step 1 路由後，強制走 Step 1.5，命中則回傳；無命中直接 no_evidence
      no_direct=True    強制走 Step 1.5（圖譜），無命中跑 Step 3（VS）；跳過 Step 2（DL）

    answer_mode：
      direct_lookup       精確索引命中（零額外 LLM 呼叫）
      graph_rag_topology  Type E 多跳圖拓撲搜尋命中（四大編譯圖譜）
      graph_rag_local     entity_df 直查命中 or 其他圖譜路徑
      graph_rag           Layer 1 Microsoft GraphRAG LocalSearch 命中
      vector_search       向量檢索 + LLM 生成
      llm_only            純 LLM（消融）
      no_evidence         無命中
    """
    # ── 消融實驗：純 LLM 模式（不提供任何檢索內容）───────────────────
    if llm_only:
        answer = _call_vllm(vllm_url, llm_model, _LLM_SYSTEM_PROMPT,
                            f"問題：{question}\n\n/no_think")
        return {
            "question":         question,
            "answer":           answer,
            "answer_mode":      "llm_only",
            "retrieved_count":  0,
            "sources":          [],
            "retrieved_chunks": [],
            "filter_level":     "llm_only",
            "router_decision":  {"_ablation": "llm_only"},
        }

    # ── 消融實驗：純向量搜尋模式（跳過 LLM 路由 / Pandas 旁路 / GraphRAG）──
    if vector_only:
        # 純正則提取公司代碼與季度列表，不調用 LLM
        company_codes, query_quarters = _regex_extract_for_vector_only(
            question, company_map
        )
        intent: dict[str, Any] = {
            "route":      "semantic_rag",
            "query_type": "single",
            "companies":  company_codes,
            "quarters":   query_quarters,
            "table_name": None,
            "item_name":  "",
            "_ablation":  "vector_only",
        }

        # 按 (公司, 季度) 組合分別查：
        #   Type A cross_company：多公司 × 單季度（或無季度）
        #   Type B cross_quarter：單公司 × 多季度
        #   一般情況：單公司 × 單季度（或無季度）
        all_hits: list[dict[str, Any]] = []
        filter_levels: list[str] = []
        iter_quarters = query_quarters if query_quarters else [None]
        for code in company_codes:
            for q in iter_quarters:
                h, fl = _retrieve_from_vectordb(
                    question, collection, embedder, code, q, top_k
                )
                all_hits.extend(h)
                filter_levels.append(fl)
        # 無法解析公司代碼時，all_hits 為空 → 後續回傳 no_evidence

        # 依 score 降冪排列並去重（防多 (公司×季度) 組合 chunk 重複）
        seen_chunk_ids: set[str] = set()
        unique_hits: list[dict[str, Any]] = []
        for h in sorted(all_hits, key=lambda x: x["score"], reverse=True):
            uid = h.get("source", "") + h["content"][:40]
            if uid not in seen_chunk_ids:
                seen_chunk_ids.add(uid)
                unique_hits.append(h)
        # 上限 = top_k × 公司數 × 季度數（最少 top_k）
        cap = top_k * max(len(company_codes), 1) * max(len(query_quarters), 1)
        all_hits = unique_hits[:cap]

        filter_level = filter_levels[0] if filter_levels else "no_match"

        if not all_hits:
            return {
                "question":          question,
                "answer":            "找不到相關資料",
                "answer_mode":       "no_evidence",
                "retrieved_count":   0,
                "sources":           [],
                "retrieved_chunks":  [],
                "filter_level":      "no_match",
                "router_decision":   intent,
            }

        context     = _format_context_from_hits(all_hits)
        user_prompt = f"問題：{question}\n\n財報資料片段：\n{context}\n\n/no_think"
        answer      = _call_vllm(vllm_url, llm_model, _LLM_SYSTEM_PROMPT, user_prompt)
        return {
            "question":        question,
            "answer":          answer,
            "answer_mode":     "vector_search",
            "retrieved_count": len(all_hits),
            "sources": [
                f"{h['company_name']} {h['quarter']} {h['table_name']} (score={h['score']:.3f})"
                for h in all_hits
            ],
            "retrieved_chunks": [
                {
                    "company_name": h.get("company_name", ""),
                    "quarter":      h.get("quarter", ""),
                    "table_name":   h.get("table_name", ""),
                    "score":        h.get("score", 0.0),
                    "content":      h.get("content", ""),
                }
                for h in all_hits
            ],
            "filter_level":    filter_level,
            "router_decision": intent,
        }

    # ── Step 1：LLM 意圖路由 ─────────────────────────────────────
    intent = _llm_intent_router(question, vllm_url, llm_model)

    # Type C 格式防呆：若問句符合「在【公司】的【表格】中，（在【期間】，）被投資公司【X】的【Y】是多少？」
    # 強制覆蓋 query_type 為 entity_lookup，確保走 graph_rag 路線
    if _ENTITY_QA_RE.match(question):
        intent = {**intent, "query_type": "entity_lookup", "route": "graph_rag"}

    # ── Step 1.5：GraphRAG 實體拓撲路由 ───────────────────────────
    # 觸發條件：route == "graph_rag"（LLM 明確路由）
    #           OR query_type == entity_lookup / multi_hop_graph_reasoning（向下相容）
    #           OR route 非 direct_lookup 且 item_name 含子公司/被投資公司關鍵字（關鍵字兜底）
    # 不對 direct_lookup 路由觸發（避免 "採用權益法認列之關聯企業..." 等長科目名誤觸）
    _is_entity_query = (
        graph_only                              # 消融實驗：強制走圖譜路徑
        or no_direct                            # 消融實驗：圖譜+向量，強制觸發圖譜
        or intent.get("route") == "graph_rag"
        or intent.get("query_type") in ("entity_lookup", "multi_hop_graph_reasoning")
        or (
            intent.get("route") != "direct_lookup"
            and any(kw in intent.get("item_name", "") for kw in _GRAPH_ENTITY_KEYWORDS)
        )
    )
    if _is_entity_query:
        graph_answer = _execute_graph_rag_search(
            intent, question,
            entity_df=entity_df,
            vllm_url=vllm_url,
            llm_model=llm_model,
        )
        if graph_answer is not None:
            if intent.get("query_type") == "multi_hop_graph_reasoning":
                _gmode = "graph_rag_topology"
            elif _GRAPHRAG_PKG_AVAILABLE and _GRAPHRAG_INDEX_PATH.exists():
                _gmode = "graph_rag"
            else:
                _gmode = "graph_rag_local"
            return {
                "question":        question,
                "answer":          graph_answer,
                "answer_mode":     _gmode,
                "retrieved_count": 0,
                "sources":         [],
                "filter_level":    "graph_rag",
                "router_decision": intent,
            }
        # 無命中 → 記錄 fallback 原因，繼續後續流程
        _gfb_reason = "no_index" if not _GRAPHRAG_INDEX_PATH.exists() else "no_match"
        intent = {**intent, "_graph_fallback": _gfb_reason}

    # 消融實驗：純圖譜模式 — 圖譜無命中時直接回傳 no_evidence，不走 DL / VS
    if graph_only:
        return {
            "question":         question,
            "answer":           "找不到相關資料",
            "answer_mode":      "no_evidence",
            "retrieved_count":  0,
            "sources":          [],
            "retrieved_chunks": [],
            "filter_level":     "no_match",
            "router_decision":  {**intent, "_ablation": "graph_only"},
        }

    # ── Step 2：第一軌 — Pandas 精確查表 ──────────────────────────
    # 口語問法（colloquial）同樣先嘗試 Pandas 直接旁路；_direct_lookup_flex 入口會
    # 透過 _ONTOLOGY_REVERSE 將同義詞正規化為標準欄位名，命中則直接回傳，
    # 不命中才繼續進入 Step 3 向量搜尋，避免 LLM 從無關欄位抽錯數字。
    _try_direct = (
        not no_direct                           # 消融實驗：圖譜+向量模式跳過 DL
        and (
            intent["route"] == "direct_lookup"
            or intent.get("query_type") == "colloquial"
        )
    )
    if _try_direct and facts_df is not None and deduped_df is not None:
        direct_answer = _execute_direct_lookup_batch(intent, facts_df, deduped_df)
        if direct_answer is not None:
            return {
                "question":        question,
                "answer":          direct_answer,
                "answer_mode":     "direct_lookup",
                "retrieved_count": 0,
                "sources":         [],
                "filter_level":    "direct_lookup",
                "router_decision": intent,
            }
        # 查無資料 → fallback：記錄原因，進入第二軌
        intent = {**intent, "_fallback_reason": "pandas_miss"}

    # ── Step 3：第二軌 — 語意向量路由 ─────────────────────────────
    companies = intent.get("companies", [])
    quarters  = intent.get("quarters", [])

    # company_code：取 companies[0] 解析（第一家公司）
    company_code: str | None = None
    if companies:
        company_code = _resolve_company_code(companies[0], company_map)

    # query_quarter：唯一季度才加硬性過濾；cross_quarter（多季度）不加，讓 ANN 自由搜尋
    query_quarter: str | None = None
    if len(quarters) == 1:
        q_val = quarters[0]
        # 僅 ROC 季度標籤（113Q3）才能直接對應 ChromaDB metadata 的 quarter 欄
        if _PERIOD_LABEL_RE.match(str(q_val)):
            query_quarter = q_val

    hits, filter_level = _retrieve_from_vectordb(
        question, collection, embedder, company_code, query_quarter, top_k
    )

    if not hits:
        return {
            "question":          question,
            "answer":            "找不到相關資料",
            "answer_mode":       "no_evidence",
            "retrieved_count":   0,
            "sources":           [],
            "retrieved_chunks":  [],
            "filter_level":      "no_match",
            "router_decision":   intent,
        }

    context     = _format_context_from_hits(hits)
    user_prompt = f"問題：{question}\n\n財報資料片段：\n{context}\n\n/no_think"
    answer      = _call_vllm(vllm_url, llm_model, _LLM_SYSTEM_PROMPT, user_prompt)

    return {
        "question":        question,
        "answer":          answer,
        "answer_mode":     "vector_search",
        "retrieved_count": len(hits),
        "sources": [
            f"{h['company_name']} {h['quarter']} {h['table_name']} (score={h['score']:.3f})"
            for h in hits
        ],
        "retrieved_chunks": [
            {
                "company_name": h.get("company_name", ""),
                "quarter":      h.get("quarter", ""),
                "table_name":   h.get("table_name", ""),
                "score":        h.get("score", 0.0),
                "content":      h.get("content", ""),
            }
            for h in hits
        ],
        "filter_level":    filter_level,
        "router_decision": intent,
    }


def _get_gpu_stats() -> list[dict]:
    """
    使用 pynvml 取得所有 GPU 即時使用狀態。
    每張卡回傳：
      gpu_id        — GPU 編號
      util_pct      — 計算核心使用率 (%)
      vram_used_mb  — 已用顯存 (MB)
      vram_total_mb — 總顯存 (MB)
      vram_util_pct — 顯存使用率 (%)
    """
    try:
        import pynvml
        pynvml.nvmlInit()
        stats = []
        for i in range(pynvml.nvmlDeviceGetCount()):
            h    = pynvml.nvmlDeviceGetHandleByIndex(i)
            util = pynvml.nvmlDeviceGetUtilizationRates(h)
            mem  = pynvml.nvmlDeviceGetMemoryInfo(h)
            stats.append({
                "gpu_id":        i,
                "util_pct":      float(util.gpu),
                "vram_used_mb":  round(mem.used   / (1024 ** 2), 1),
                "vram_total_mb": round(mem.total  / (1024 ** 2), 1),
                "vram_util_pct": round(mem.used / mem.total * 100, 1) if mem.total else 0.0,
            })
        return stats
    except Exception:
        return []


def _get_vllm_external_vram_mb() -> float:
    """【終極暴力自適應版】不認 PID 與權限，直接跨所有 GPU 活捉大水箱實質顯存"""
    try:
        import pynvml
        pynvml.nvmlInit()
        device_count = pynvml.nvmlDeviceGetCount()
        
        max_vram_found = 0.0
        
        # 遍歷主機上所有的 GPU 卡 (GPU 0, 1, 2...)
        for i in range(device_count):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            # 直接讀取這張顯卡上「所有進程」配置的總顯存
            # 繞過 psutil 的權限封鎖，直接向 NVIDIA 驅動要數據
            processes = pynvml.nvmlDeviceGetComputeRunningProcesses(handle)
            for p in processes:
                vram_mb = p.usedGpuMemory / (1024 * 1024)
                # 只要顯存大於 2GB (2048MB)，九成九就是我們的 vLLM 常駐水箱
                if vram_mb > 2048.0 and vram_mb > max_vram_found:
                    max_vram_found = vram_mb
                    
        if max_vram_found > 0.0:
            return round(max_vram_found, 2)
            
    except Exception:
        pass
    return 0.0




def run_module3_rag_queries(
    dataset_path: Path,
    root: Path,
    output_path: Path,
    vllm_url: str,
    llm_model: str,
    limit: int = 0,
    db_path: Path = DEFAULT_VECTOR_DB,
    embedding_model: str = DEFAULT_EMBED_MODEL,
    top_k: int = 5,
    embed_device: str = "cpu",
    vector_only: bool = False,
    llm_only: bool = False,
    graph_only: bool = False,
    no_direct: bool = False,
) -> list[dict]:
    """
    Module 3：對測試資料集中的每道問題執行 RAG 查詢，將結果寫入 JSON。

    LLM 意圖路由器三段式流程：
      Step 1  LLM Intent Router（Qwen3）→ 解析意圖 JSON（route / query_type / companies / quarters / table_name / item_name）
      Step 1.5 graph_rag → GraphRAG 四層降級搜尋（entity_lookup / multi_hop_graph_reasoning）
      Step 2  第一軌 direct_lookup → Pandas 精確查表（single / cross_company / cross_quarter）
      Step 3  第二軌 semantic_rag / fallback → ChromaDB ANN + vLLM 生成
    """
    _require_vector_deps()

    if not db_path.exists():
        sys.exit(
            f"  ERROR：Vector DB 不存在 ({db_path})\n"
            f"  請先執行：python rag_test_system.py build-index"
        )

    # ── 載入 ChromaDB ─────────────────────────────────────────
    client     = chromadb.PersistentClient(path=str(db_path))
    collection = client.get_collection(name=_CHROMA_COLLECTION)
    print(f"  ▶ 已載入 Vector DB：{db_path}  "
          f"({collection.count():,} chunks)")

    # ── 載入 Embedder ─────────────────────────────────────────
    embedder    = _BGEEmbedder(embedding_model, device=embed_device)
    company_map = _build_company_map(root)
    print(f"  ▶ 公司對應表：{len(company_map)} 家")

    # ── 載入 facts_df（全量）、deduped_df（去重）、entity_df（子公司明細表）────
    print("  ▶ 載入精確索引 DataFrame ...")
    facts_df = _load_facts_df(root)
    _, entity_df, deduped_df = _prep_facts_for_gen(facts_df)
    print(
        f"  ▶ facts_df：{len(facts_df):,} 筆 ｜ deduped_df：{len(deduped_df):,} 筆 "
        f"｜ entity_df：{len(entity_df):,} 筆"
    )

    # ── 載入四大編譯圖譜（Graph Knowledge Ingestion）──────────
    print("  ▶ 載入四大圖譜事實 ...")
    _load_all_compiled_graphs()

    # ── 載入測試集 ────────────────────────────────────────────
    dataset: list[dict] = json.loads(dataset_path.read_text(encoding="utf-8"))
    if limit:
        dataset = dataset[:limit]

    results:      list[dict]     = []
    mode_counter: dict[str, int] = defaultdict(int)
    _vram_reset()                                    # 會話級本機 CUDA 峰值計數器歸零
    session_vram_peak: float | None = 0.0 if _CUDA_OK else None
    session_vllm_peak: float        = 0.0            # 跨行程 vLLM VRAM 會話最高峰
    session_gpu_util_peak:  float   = 0.0            # GPU 計算使用率會話最高峰 (%)
    session_vram_util_peak: float   = 0.0            # GPU 顯存使用率會話最高峰 (%)
    t0 = time.time()

    for i, item in enumerate(dataset, 1):
        q    = item["question"]
        meta = item.get("metadata", {})
        print(f"  [{i:02d}/{len(dataset)}] {q[:65]}...", end="", flush=True)

        _vram_reset()                                # 單題本機 CUDA 峰值計數器歸零
        q_t0 = time.time()
        result = _rag_query_one(
            q, collection, embedder, company_map,
            vllm_url, llm_model, top_k, facts_df, deduped_df, entity_df,
            vector_only=vector_only,
            llm_only=llm_only,
            graph_only=graph_only,
            no_direct=no_direct,
        )
        result["latency_sec"]  = round(time.time() - q_t0, 2)
        q_vram                 = _vram_peak_mb()
        result["vram_peak_mb"] = q_vram
        if session_vram_peak is not None and q_vram is not None:
            session_vram_peak = max(session_vram_peak, q_vram)
        q_vllm                  = _get_vllm_external_vram_mb()
        result["vllm_vram_mb"]  = q_vllm
        session_vllm_peak       = max(session_vllm_peak, q_vllm)
        # GPU 計算使用率 & 顯存使用率
        gpu_stats = _get_gpu_stats()
        if gpu_stats:
            q_util      = max(g["util_pct"]      for g in gpu_stats)
            q_vram_util = max(g["vram_util_pct"] for g in gpu_stats)
            result["gpu_util_pct"]      = q_util
            result["gpu_vram_util_pct"] = q_vram_util
            result["gpu_vram_used_mb"]  = sum(g["vram_used_mb"]  for g in gpu_stats)
            result["gpu_vram_total_mb"] = sum(g["vram_total_mb"] for g in gpu_stats)
            session_gpu_util_peak  = max(session_gpu_util_peak,  q_util)
            session_vram_util_peak = max(session_vram_util_peak, q_vram_util)
        result["id"]              = item["id"]
        result["expected_answer"] = item["expected_answer"]
        result["metadata"]        = meta
        results.append(result)

        mode         = result["answer_mode"]
        filter_level = result.get("filter_level", "")
        mode_counter[mode] += 1
        rd  = result.get("router_decision", {})
        if mode in ("graph_rag_local", "graph_rag", "graph_rag_topology"):
            rt, qt = "GR", "el"
        else:
            rt = {"direct_lookup": "DL", "semantic_rag": "SR"}.get(rd.get("route", ""), "?")
            qt = {"single": "s", "cross_company": "cc", "cross_quarter": "cq",
                  "colloquial": "col", "entity_lookup": "el"}.get(rd.get("query_type", ""), "?")
        tag = f"{mode}|{rt}+{qt}"
        if filter_level and filter_level not in ("no_match", "direct_lookup", "graph_rag"):
            tag += f"|{filter_level}"
        if "_fallback_reason" in rd:
            tag += f"|fb:{rd['_fallback_reason'][:10]}"
        if "_graph_fallback" in rd:
            gfb = rd["_graph_fallback"]
            tag += f"|gfb:{gfb}" if gfb != "graph_rag_disabled" else "|gfb"
        print(f"  [{tag}]  → {result['answer'][:40]}")

    elapsed = time.time() - t0
    output_path.write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"\n  ▶ 查詢完成（{elapsed:.1f}s）：",
          " ｜ ".join(f"{k}: {v}" for k, v in mode_counter.items()))

    # ── 耗時彙整 ──────────────────────────────────────────────
    all_lat   = [r["latency_sec"] for r in results if "latency_sec" in r]
    avg_total = sum(all_lat) / len(all_lat) if all_lat else 0.0

    _LATENCY_MODES = ("direct_lookup", "graph_rag_topology", "vector_search")
    mode_lats: dict[str, list[float]] = {m: [] for m in _LATENCY_MODES}
    for r in results:
        m = r.get("answer_mode", "")
        if m in mode_lats and "latency_sec" in r:
            mode_lats[m].append(r["latency_sec"])

    print(f"  ▶ 耗時統計：總計 {elapsed:.1f}s ｜ 平均單題 {avg_total:.2f}s")
    for m in _LATENCY_MODES:
        lats = mode_lats[m]
        if lats:
            print(f"      {m}: n={len(lats)} ｜ avg={sum(lats)/len(lats):.2f}s"
                  f" ｜ min={min(lats):.2f}s ｜ max={max(lats):.2f}s")

    # ── VRAM 峰值彙整 ─────────────────────────────────────────
    # vLLM 跨行程外部 VRAM（主要指標）
    vllm_vals = [r["vllm_vram_mb"] for r in results if r.get("vllm_vram_mb") is not None]
    if session_vllm_peak > 0.0:
        avg_vllm = sum(vllm_vals) / len(vllm_vals) if vllm_vals else 0.0
        print(f"  ▶ vLLM VRAM（跨行程）：會話最高 {session_vllm_peak:.1f} MB"
              f" ｜ 平均單題 {avg_vllm:.1f} MB")
        vllm_mode_vrams: dict[str, list[float]] = defaultdict(list)
        for r in results:
            v = r.get("vllm_vram_mb")
            if v is not None:
                vllm_mode_vrams[r.get("answer_mode", "")].append(v)
        for m in _LATENCY_MODES:
            vs = vllm_mode_vrams.get(m, [])
            if vs:
                print(f"      {m}: avg={sum(vs)/len(vs):.1f} MB ｜ max={max(vs):.1f} MB")
    else:
        print("  ▶ vLLM VRAM：0.0 MB（pynvml 未安裝或 vLLM 行程不在 GPU 0）")
    # 本機嵌入模型 CUDA VRAM（次要指標，通常遠小於 vLLM）
    vram_vals = [r["vram_peak_mb"] for r in results if r.get("vram_peak_mb") is not None]
    if _CUDA_OK and vram_vals and any(v > 0 for v in vram_vals):
        avg_vram = sum(vram_vals) / len(vram_vals)
        print(f"  ▶ 本機嵌入 VRAM（torch）：會話最高 {session_vram_peak:.1f} MB"
              f" ｜ 平均 {avg_vram:.1f} MB")

    # GPU 使用率彙整（pynvml）
    util_vals      = [r["gpu_util_pct"]      for r in results if r.get("gpu_util_pct")      is not None]
    vram_util_vals = [r["gpu_vram_util_pct"] for r in results if r.get("gpu_vram_util_pct") is not None]
    if util_vals:
        avg_util      = sum(util_vals)      / len(util_vals)
        avg_vram_util = sum(vram_util_vals) / len(vram_util_vals) if vram_util_vals else 0.0
        last_used  = results[-1].get("gpu_vram_used_mb",  0.0)
        last_total = results[-1].get("gpu_vram_total_mb", 0.0)
        print(f"  ▶ GPU 計算使用率：會話最高 {session_gpu_util_peak:.1f}%"
              f" ｜ 平均 {avg_util:.1f}%")
        print(f"  ▶ GPU 顯存使用率：會話最高 {session_vram_util_peak:.1f}%"
              f" ｜ 平均 {avg_vram_util:.1f}%"
              f" ｜ 現況 {last_used:.0f}/{last_total:.0f} MB")

    print(f"  ▶ 結果已儲存 → {output_path}")
    return results


# ══════════════════════════════════════════════════════════════
#  Module 4：自動評估評分
# ══════════════════════════════════════════════════════════════

# 拒答短語集合（用於 Precision / Recall 的「有效回答」判斷）
_REFUSAL_PHRASES: frozenset[str] = frozenset({
    "找不到相關資料",
    "無法回答",
    "沒有相關資料",
    "不清楚",
    "查無資料",
})


def _normalize(text: str) -> str:
    text = str(text).strip()
    # backup strip: remove any residual <think>...</think> blocks
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    # normalize "100.00 %" → "100.00%" (space before % sign)
    text = re.sub(r"(\d)\s+%", r"\1%", text)
    # collapse all remaining whitespace
    text = re.sub(r"\s+", "", text)
    # remove digit-group commas "1,234,567" → "1234567"
    text = text.replace(",", "")
    return text.lower()


def _extract_numbers(text: str) -> set[str]:
    cleaned = text.replace(",", "").replace("(", "").replace(")", "")
    return set(re.findall(r"\d+(?:\.\d+)?", cleaned))


def _is_refusal(answer: str) -> bool:
    """
    判斷系統回答是否為拒答（無具體數字答案）。

    以下視為拒答：
      · 空字串
      · 以 "[vLLM" 開頭（LLM 服務錯誤訊息）
      · 包含 _REFUSAL_PHRASES 中的任一短語
    """
    ans = str(answer).strip()
    if not ans or ans.startswith("[vLLM"):
        return True
    return any(phrase in ans for phrase in _REFUSAL_PHRASES)


def _compute_repass_flag(item: dict) -> bool:
    """
    RePASS 穩定性框架：判斷本題是否走了降級路由（Fallback）。

    以下情況視為降級：
      1. router_decision._fallback_reason 存在
         → direct_lookup 查表失敗後退至向量搜尋（pandas_miss）
      2. router_decision._graph_fallback 存在
         → GraphRAG 未啟用，降至 ChromaDB 向量搜尋
      3. router_decision._router_error 存在
         → LLM 路由器解析失敗，使用兜底預設值
      4. filter_level == "company_only"
         → ChromaDB $and（公司+季度）過濾無命中，降至公司單獨過濾
    """
    rd = item.get("router_decision", {})
    if rd.get("_fallback_reason") or rd.get("_graph_fallback") or rd.get("_router_error"):
        return True
    return item.get("filter_level") == "company_only"


def _score_one(predicted: str, expected: str) -> dict[str, bool]:
    """
    四指標評分：

    exact_match     正規化後字串完全相同（最嚴格）
    numeric_match   兩邊抽出的數字集合完全一致
    contains_match  expected 的所有數字均出現在 predicted 中
    partial_numeric 至少一個數字相符
    """
    pred_norm = _normalize(predicted)
    exp_norm  = _normalize(expected)

    exact = pred_norm == exp_norm

    pred_nums = _extract_numbers(predicted)
    exp_nums  = _extract_numbers(expected)

    numeric_match   = bool(exp_nums) and pred_nums == exp_nums
    contains_match  = bool(exp_nums) and exp_nums.issubset(pred_nums)
    partial_numeric = bool(exp_nums) and bool(exp_nums & pred_nums)

    return {
        "exact_match":     exact,
        "numeric_match":   numeric_match,
        "contains_match":  contains_match,
        "partial_numeric": partial_numeric,
    }


# ── NLG 指標輔助函數 ──────────────────────────────────────────


def _normalize_nlg(text: str) -> str:
    """NLG 指標輕量正規化：去除 think block、壓縮空白，保留分詞結構。"""
    text = str(text).strip()
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    return re.sub(r"\s+", " ", text).strip()


_JIEBA_INITIALIZED = False

def _tokenize_zh(text: str) -> list[str]:
    """jieba 中文分詞；未安裝時回退逐字符切割。"""
    global _JIEBA_INITIALIZED
    try:
        import logging
        import jieba
        jieba.setLogLevel(logging.WARNING)   # 壓制 "Building prefix dict..." 輸出
        
        # if random.random() < 0.02: 
        #     print(f" \n📢 [DEBUG 斷詞測試] 原文: {text[:15]} -> 分詞結果: {list(jieba.cut(text))[:5]}")
        # return list(jieba.cut(text))

        # 碩論亮點：動態載入繁體大詞庫，確保台灣財報專有名詞不被切碎
        if not _JIEBA_INITIALIZED:
            import os
            if os.path.exists("dict.txt.big"):
                jieba.set_dictionary("dict.txt.big")
            _JIEBA_INITIALIZED = True

        cleaned_text = re.sub(r'(?<=\d),(?=\d)', '', text)  
          
        return list(jieba.cut(text))
    except ImportError:
        return list(text)


def _ngrams(tokens: list[str], n: int) -> "Counter":
    from collections import Counter
    return Counter(tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1))


def _rouge_n_score(pred: str, ref: str, n: int) -> dict[str, float]:
    """計算 ROUGE-N P / R / F1（jieba 分詞）。"""
    pred_tok = _tokenize_zh(_normalize_nlg(pred))
    ref_tok  = _tokenize_zh(_normalize_nlg(ref))
    pred_ng  = _ngrams(pred_tok, n)
    ref_ng   = _ngrams(ref_tok, n)
    overlap  = sum((pred_ng & ref_ng).values())
    prec = overlap / sum(pred_ng.values()) if pred_ng else 0.0
    rec  = overlap / sum(ref_ng.values())  if ref_ng  else 0.0
    f1   = 2 * prec * rec / (prec + rec)   if (prec + rec) > 0 else 0.0
    return {"p": round(prec, 4), "r": round(rec, 4), "f": round(f1, 4)}


_NLG_SAFE_DEFAULT = "找不到相關資料"


def _safe_nlg_text(t: str) -> str:
    """正規化後，防止空字串或 vLLM 錯誤訊息送入神經模型。"""
    t = _normalize_nlg(t)
    if not t.strip() or t.startswith("[vLLM"):
        return _NLG_SAFE_DEFAULT
    return t


def _batch_bert_score(
    preds: list[str], refs: list[str],
) -> "tuple[list[dict[str, float] | None], str]":
    """
    批次計算 BERTScore（lang='zh'）。
    回傳 (scores_list, status)，status: "ok" | "not_installed" | "error"
    """
    try:
        from bert_score import score as _bscore
    except ImportError:
        return [None] * len(preds), "not_installed"

    _preds_safe = [_safe_nlg_text(p) for p in preds]
    _refs_safe  = [_safe_nlg_text(r) for r in refs]

    def _run_bscore(device: str):
        return _bscore(_preds_safe, _refs_safe, lang="zh", verbose=False, device=device)

    try:
        device = "cuda" if _CUDA_OK else "cpu"
        P, R, F = _run_bscore(device)
    except RuntimeError as e:
        if "out of memory" in str(e).lower() and _CUDA_OK:
            print("  ⚠️  [DEBUG] BERTScore CUDA OOM，清快取後改用 CPU 重試 ...", flush=True)
            _torch.cuda.empty_cache()
            try:
                P, R, F = _run_bscore("cpu")
            except Exception as e2:
                print(f"  ❌ [DEBUG] BERTScore CPU 重試失敗: {type(e2).__name__}: {e2}", flush=True)
                return [None] * len(preds), "error"
        else:
            print(f"  ❌ [DEBUG] BERTScore 計算錯誤: {type(e).__name__}: {e}", flush=True)
            return [None] * len(preds), "error"
    except Exception as e:
        print(f"  ❌ [DEBUG] BERTScore 計算錯誤: {type(e).__name__}: {e}", flush=True)
        return [None] * len(preds), "error"

    return [
        {"p": round(p.item(), 4), "r": round(r.item(), 4), "f": round(f.item(), 4)}
        for p, r, f in zip(P, R, F)
    ], "ok"


def _batch_mover_score(
    preds: list[str], refs: list[str],
) -> "tuple[list[float | None], str]":
    """
    批次計算 MoverScore（moverscore_v2，mBERT）。
    回傳 (scores_list, status)，status: "ok" | "not_installed" | "error"
    """
    try:
        from moverscore_v2 import get_idf_dict, word_mover_score
    except ImportError:
        return [None] * len(preds), "not_installed"

    _pn = [_safe_nlg_text(p) for p in preds]
    _rn = [_safe_nlg_text(r) for r in refs]

    def _run_mover(use_cuda: bool):
        import os
        if not use_cuda:
            os.environ["MOVERSCORE_DEVICE"] = "cpu"
        idf_ref  = get_idf_dict(_rn)
        idf_pred = get_idf_dict(_pn)
        return word_mover_score(
            _rn, _pn, idf_ref, idf_pred,
            stop_words=[], n_gram=1, remove_subwords=True,
        )

    try:
        scores = _run_mover(use_cuda=_CUDA_OK)
    except RuntimeError as e:
        if "out of memory" in str(e).lower() and _CUDA_OK:
            print("  ⚠️  [DEBUG] MoverScore CUDA OOM，清快取後改用 CPU 重試 ...", flush=True)
            _torch.cuda.empty_cache()
            try:
                scores = _run_mover(use_cuda=False)
            except Exception as e2:
                print(f"  ❌ [DEBUG] MoverScore CPU 重試失敗: {type(e2).__name__}: {e2}", flush=True)
                return [None] * len(preds), "error"
        else:
            print(f"  ❌ [DEBUG] MoverScore 計算錯誤: {type(e).__name__}: {e}", flush=True)
            return [None] * len(preds), "error"
    except Exception as e:
        print(f"  ❌ [DEBUG] MoverScore 計算錯誤: {type(e).__name__}: {e}", flush=True)
        return [None] * len(preds), "error"

    return [round(float(s), 4) for s in scores], "ok"


# ── 檢索品質評估工具函數（Hit Rate / NDCG / MRR）────────────────────────────

_RETRIEVAL_K_VALUES: tuple[int, ...] = (1, 3, 5)


def _build_virtual_ranked_list(result: dict, metadata: dict) -> list[dict]:
    """
    將三軌查詢結果轉換為統一的虛擬排名清單（Virtual Ranked List, VRL）。

    軌道映射：
      DL  (direct_lookup)          → 1 個 rank-1 item，公司+季度+表格取自 metadata
      GR  (graph_rag / topology / local) → 1 個 rank-1 item，取自 router_decision
      VS  (vector_search)          → top-K chunks，按 ChromaDB 相似度排序
      NE  (no_evidence)            → 空清單

    為何需要 VRL：
      直接套標準 IR 公式需要一個排名清單；DL/GR 軌道雖無「chunks」，
      但其確定性命中等同於 rank-1 精確召回，統一建模可跨軌道計算 NDCG。
    """
    mode = result.get("answer_mode", "no_evidence")
    meta = metadata or {}
    co   = meta.get("company_name", "")
    qtr  = meta.get("quarter", "")
    tbl  = meta.get("table_name", "") or ""

    if mode == "no_evidence":
        return []

    if mode == "direct_lookup":
        return [{"rank": 1, "track": "DL",
                 "company_name": co, "quarter": qtr, "table_name": tbl, "score": 1.0}]

    if mode in ("graph_rag", "graph_rag_topology", "graph_rag_local"):
        rd  = result.get("router_decision", {})
        cos = rd.get("companies") or [co]
        qs  = rd.get("quarters")  or [qtr]
        return [{"rank": 1, "track": "GR",
                 "company_name": cos[0] if cos else co,
                 "quarter":      qs[0]  if qs  else qtr,
                 "table_name":   rd.get("table_name") or tbl,
                 "score": 1.0}]

    # vector_search：retrieved_chunks 已按 score 降序
    chunks = result.get("retrieved_chunks", [])
    return [
        {"rank": i + 1, "track": "VS",
         "company_name": c.get("company_name", ""),
         "quarter":      c.get("quarter",      ""),
         "table_name":   c.get("table_name",   ""),
         "score":        c.get("score", 0.0)}
        for i, c in enumerate(chunks)
    ]


def _relevance_grade(item: dict, gold_co: str, gold_qtr: str, gold_tbl: str) -> int:
    """
    計算 VRL 項目對於金標準（gold）的相關等級。

    Grade 2 — 公司 + 季度 + 表格前綴三者均符合（精確黃金命中，Graded = 高度相關）
    Grade 1 — 公司 + 季度符合，表格層級不完全對應（相關但不精確）
    Grade 0 — 公司不符合（完全無關）

    表格比對使用前 4 字前綴匹配（「資產負債表」→「資產負」），
    容許 CSV 表格名稱與意圖 table_name 的細微差異。
    """
    c_hit = bool(gold_co) and (
        gold_co in item["company_name"] or item["company_name"] in gold_co
    )
    if not c_hit:
        return 0
    q_hit = not gold_qtr or item["quarter"] == gold_qtr
    t_hit = not gold_tbl or gold_tbl[:4] in item.get("table_name", "")
    if q_hit and t_hit:
        return 2
    if q_hit:
        return 1
    return 0


def _dcg_at_k(rel_list: list[int], k: int) -> float:
    """Discounted Cumulative Gain @K（log base 2，rank 從 1 起算）。"""
    return sum(
        rel / math.log2(rank + 1)
        for rank, rel in enumerate(rel_list[:k], start=1)
        if rel > 0
    )


def _ndcg_at_k(rel_list: list[int], k: int) -> float:
    """Normalised DCG@K。IDCG = 0（無任何相關項目）時回傳 0.0。"""
    idcg = _dcg_at_k(sorted(rel_list, reverse=True), k)
    return round(_dcg_at_k(rel_list, k) / idcg, 4) if idcg > 0 else 0.0


def run_module4_evaluate(
    results_path: Path,
    output_path: Path,
    show_answers: bool = True,
) -> dict[str, Any]:
    """
    Module 4：讀取 RAG 查詢結果，計算多維度評分，輸出評測報告。

    基礎指標：
      exact_match     正規化後字串完全一致（EM，最嚴格）
      numeric_match   數字集合完全一致
      contains_match  正確數字皆出現在答案中
      partial_numeric 至少一個數字正確

    學術指標（Academic Metrics）：
      EM (Exact Match)   全量題目的 exact_match 平均（0~1）
      Precision          有效回答中的正確率（EM=1 / 非拒答非 no_evidence）
      Recall             全量中系統給出有效回答的比例（非拒答非 no_evidence / 全量）
      F1-Score           Precision 與 Recall 的調和平均數

    RePASS 穩定性指標：
      is_fallback（per-question）  是否為降級路由（pandas_miss / graph_disabled / company_only 等）
      fallback_em_rate             降級題目的 EM 準確率
      stable_em_rate               非降級題目的 EM 準確率
      stability_delta              兩者差距（穩定路由品質優勢）
    """
    results: list[dict] = json.loads(results_path.read_text(encoding="utf-8"))
    total = len(results)

    # ── 基礎評分 ──────────────────────────────────────────────
    metric_keys = ("exact_match", "numeric_match", "contains_match", "partial_numeric")
    counts: dict[str, int] = {k: 0 for k in metric_keys}
    scored_results: list[dict] = []

    for item in results:
        pred        = item.get("answer", "")
        ref         = item.get("expected_answer", "")
        scores      = _score_one(pred, ref)
        scores["rouge_1"] = _rouge_n_score(pred, ref, 1)
        scores["rouge_2"] = _rouge_n_score(pred, ref, 2)
        scores["rouge_3"] = _rouge_n_score(pred, ref, 3)
        is_fallback = _compute_repass_flag(item)
        for k in metric_keys:
            if scores[k]:
                counts[k] += 1
        scored_results.append({**item, "scores": scores, "is_fallback": is_fallback})

    rates = {k: round(counts[k] / total, 4) if total else 0.0 for k in metric_keys}

    # ── NLG 批次指標（BERTScore + MoverScore）────────────────
    print("  ▶ 計算 BERTScore ...", flush=True)
    _preds = [it.get("answer", "")          for it in results]
    _refs  = [it.get("expected_answer", "") for it in results]
    _bs, _bs_status = _batch_bert_score(_preds, _refs)
    # 暴力即時攔截：第一線數值驗證
    _bs_raw_valid = [v for v in _bs if v is not None]
    if _bs_raw_valid:
        _bs_f1_raw = sum(v["f"] for v in _bs_raw_valid) / len(_bs_raw_valid)
        print(f"  [DEBUG] BERTScore F1 即時攔截: {_bs_f1_raw:.4f}"
              f"  (有效={len(_bs_raw_valid)}/{len(_bs)})", flush=True)
    else:
        print(f"  [DEBUG] BERTScore 全為 None  status={_bs_status}", flush=True)

    print("  ▶ 計算 MoverScore ...", flush=True)
    _ms, _ms_status = _batch_mover_score(_preds, _refs)
    # 暴力即時攔截：第一線數值驗證
    _ms_raw_valid = [v for v in _ms if v is not None]
    if _ms_raw_valid:
        _ms_avg_raw = sum(_ms_raw_valid) / len(_ms_raw_valid)
        print(f"  [DEBUG] MoverScore avg 即時攔截: {_ms_avg_raw:.4f}"
              f"  (有效={len(_ms_raw_valid)}/{len(_ms)})", flush=True)
    else:
        print(f"  [DEBUG] MoverScore 全為 None  status={_ms_status}", flush=True)

    for i, it in enumerate(scored_results):
        it["scores"]["bert_score"]  = _bs[i]
        it["scores"]["mover_score"] = _ms[i]

    def _rouge_avg(n: int, sub: str) -> float | None:
        vals = [it["scores"][f"rouge_{n}"][sub] for it in scored_results]
        return round(sum(vals) / len(vals), 4) if vals else None

    _bs_valid = [it["scores"]["bert_score"]  for it in scored_results if it["scores"].get("bert_score")]
    _ms_valid = [it["scores"]["mover_score"] for it in scored_results if it["scores"].get("mover_score") is not None]

    nlg_metrics: dict[str, Any] = {
        "rouge_1":    {"avg_p": _rouge_avg(1, "p"), "avg_r": _rouge_avg(1, "r"), "avg_f": _rouge_avg(1, "f")},
        "rouge_2":    {"avg_p": _rouge_avg(2, "p"), "avg_r": _rouge_avg(2, "r"), "avg_f": _rouge_avg(2, "f")},
        "rouge_3":    {"avg_p": _rouge_avg(3, "p"), "avg_r": _rouge_avg(3, "r"), "avg_f": _rouge_avg(3, "f")},
        "bert_score": {
            "avg_p": round(sum(s["p"] for s in _bs_valid) / len(_bs_valid), 4),
            "avg_r": round(sum(s["r"] for s in _bs_valid) / len(_bs_valid), 4),
            "avg_f": round(sum(s["f"] for s in _bs_valid) / len(_bs_valid), 4),
        } if _bs_valid else None,
        "mover_score": {
            "avg": round(sum(_ms_valid) / len(_ms_valid), 4),
        } if _ms_valid else None,
    }

    # ── 答案模式分布 ──────────────────────────────────────────
    mode_dist: dict[str, int] = defaultdict(int)
    for item in results:
        mode_dist[item.get("answer_mode", "unknown")] += 1

    # ── 學術指標：Precision / Recall / F1 ────────────────────
    # 「有效回答」= answer_mode != no_evidence 且非拒答短語
    answered_items = [
        it for it in scored_results
        if it["answer_mode"] != "no_evidence"
        and not _is_refusal(it.get("answer", ""))
    ]
    answered_count    = len(answered_items)
    precision_correct = sum(1 for it in answered_items if it["scores"]["exact_match"])

    precision: float = round(precision_correct / answered_count, 4) if answered_count else 0.0
    recall:    float = round(answered_count / total, 4) if total else 0.0
    f1:        float = (
        round(2 * precision * recall / (precision + recall), 4)
        if (precision + recall) > 0 else 0.0
    )

    academic_metrics: dict[str, Any] = {
        "em":             rates["exact_match"],
        "precision":      precision,
        "recall":         recall,
        "f1":             f1,
        "answered_count": answered_count,
        "refusal_count":  total - answered_count,
        "precision_note": "EM=1 / 有效回答（非 no_evidence、非拒答）",
        "recall_note":    "有效回答 / 全量題數",
    }

    # ── RePASS 穩定性分析 ──────────────────────────────────────
    fallback_items = [it for it in scored_results if it["is_fallback"]]
    stable_items   = [it for it in scored_results if not it["is_fallback"]]
    fb_n, st_n     = len(fallback_items), len(stable_items)
    fb_em = sum(1 for it in fallback_items if it["scores"]["exact_match"])
    st_em = sum(1 for it in stable_items   if it["scores"]["exact_match"])

    fb_em_rate = round(fb_em / fb_n, 4) if fb_n else 0.0
    st_em_rate = round(st_em / st_n, 4) if st_n else 0.0

    repass_stability: dict[str, Any] = {
        "fallback_count":   fb_n,
        "stable_count":     st_n,
        "fallback_em":      fb_em,
        "stable_em":        st_em,
        "fallback_em_rate": fb_em_rate,
        "stable_em_rate":   st_em_rate,
        "stability_delta":  round(st_em_rate - fb_em_rate, 4),
        "flag_definition":  (
            "is_fallback=True 觸發條件："
            "_fallback_reason(pandas_miss) | _graph_fallback | _router_error | filter_level=company_only"
        ),
    }

    # ── 檢索品質指標：Hit Rate@K / NDCG@K / MRR ─────────────────
    # 適用全三軌：
    #   DL  → 虛擬 rank-1（精確查表命中即 Grade 2）
    #   GR  → 虛擬 rank-1（圖譜推理命中即 Grade 1-2）
    #   VS  → top-K ChromaDB chunks（Grade 由公司+季度+表格匹配度決定）
    #   NE  → 空清單（不貢獻任何 hit / NDCG 分數）
    hit_counts: dict[int, int]   = {k: 0 for k in _RETRIEVAL_K_VALUES}
    ndcg_sums:  dict[int, float] = {k: 0.0 for k in _RETRIEVAL_K_VALUES}
    mrr_sum:    float            = 0.0
    ret_total:  int              = 0

    for item in scored_results:
        meta    = item.get("metadata", {})
        g_co    = meta.get("company_name", "")
        g_qtr   = str(meta.get("quarter", "") or "")
        g_tbl   = str(meta.get("table_name", "") or "")
        if not g_co:
            continue  # 無金標準公司名，無法判斷相關性，跳過

        vrl      = _build_virtual_ranked_list(item, meta)
        rel_list = [_relevance_grade(v, g_co, g_qtr, g_tbl) for v in vrl]

        ret_total += 1

        # Hit Rate@K：rel >= 1 即算命中（公司+季度匹配即可）
        for k in _RETRIEVAL_K_VALUES:
            if any(r >= 1 for r in rel_list[:k]):
                hit_counts[k] += 1

        # NDCG@K
        for k in _RETRIEVAL_K_VALUES:
            ndcg_sums[k] += _ndcg_at_k(rel_list, k)

        # MRR（Mean Reciprocal Rank）
        for i, r in enumerate(rel_list):
            if r >= 1:
                mrr_sum += 1.0 / (i + 1)
                break

        # 存回 per-question 檢索指標（供 JSON 報告與逐題比對區塊使用）
        item["retrieval"] = {
            "vrl_size":   len(vrl),
            "track":      vrl[0]["track"] if vrl else "NE",
            "rel_labels": rel_list,
            "hit@1":      any(r >= 1 for r in rel_list[:1]),
            "hit@3":      any(r >= 1 for r in rel_list[:3]),
            "hit@5":      any(r >= 1 for r in rel_list[:5]),
            "ndcg@1":     _ndcg_at_k(rel_list, 1),
            "ndcg@3":     _ndcg_at_k(rel_list, 3),
            "ndcg@5":     _ndcg_at_k(rel_list, 5),
            "rr":         next((1.0 / (i + 1) for i, r in enumerate(rel_list) if r >= 1), 0.0),
        }

    _n_ret = ret_total or 1
    retrieval_metrics: dict[str, Any] = {
        **{f"hit_rate@{k}": round(hit_counts[k] / _n_ret, 4) for k in _RETRIEVAL_K_VALUES},
        **{f"ndcg@{k}":     round(ndcg_sums[k]  / _n_ret, 4) for k in _RETRIEVAL_K_VALUES},
        "mrr":            round(mrr_sum / _n_ret, 4),
        "retrieval_total": ret_total,
        "grade_def": "2=公司+季度+表格, 1=公司+季度, 0=無關",
        "vrl_def": "DL/GR=virtual rank-1; VS=top-K ChromaDB chunks by score",
    }

    # ── 逐公司統計 ────────────────────────────────────────────
    per_company: dict[str, dict] = defaultdict(lambda: {"total": 0, "exact": 0})
    for item in scored_results:
        cname = item.get("metadata", {}).get("company_name", "unknown")
        per_company[cname]["total"] += 1
        if item["scores"]["exact_match"]:
            per_company[cname]["exact"] += 1

    company_accuracy = {
        cname: {
            "total":      v["total"],
            "exact":      v["exact"],
            "exact_rate": round(v["exact"] / v["total"], 4) if v["total"] else 0.0,
        }
        for cname, v in sorted(per_company.items())
    }

    # ── 逐題型統計 ────────────────────────────────────────────
    per_type: dict[str, dict] = defaultdict(
        lambda: {"total": 0, "exact": 0, "contains": 0, "answered": 0, "fallback": 0}
    )
    for item in scored_results:
        meta  = item.get("metadata", {})
        qtype = meta.get("question_type") or item.get("question_type", "template")
        per_type[qtype]["total"] += 1
        if item["scores"]["exact_match"]:
            per_type[qtype]["exact"] += 1
        if item["scores"]["contains_match"]:
            per_type[qtype]["contains"] += 1
        if not _is_refusal(item.get("answer", "")) and item["answer_mode"] != "no_evidence":
            per_type[qtype]["answered"] += 1
        if item["is_fallback"]:
            per_type[qtype]["fallback"] += 1

    _TYPE_ORDER = ["cross_company", "cross_quarter", "entity_lookup", "colloquial", "multi_hop_graph_reasoning", "template"]
    type_accuracy = {
        qtype: {
            "total":         v["total"],
            "exact":         v["exact"],
            "contains":      v["contains"],
            "answered":      v["answered"],
            "fallback":      v["fallback"],
            "exact_rate":    round(v["exact"]    / v["total"], 4) if v["total"] else 0.0,
            "contains_rate": round(v["contains"] / v["total"], 4) if v["total"] else 0.0,
            "recall_rate":   round(v["answered"] / v["total"], 4) if v["total"] else 0.0,
            "fallback_rate": round(v["fallback"] / v["total"], 4) if v["total"] else 0.0,
        }
        for qtype, v in sorted(
            per_type.items(),
            key=lambda x: _TYPE_ORDER.index(x[0]) if x[0] in _TYPE_ORDER else 99,
        )
    }

    # ── 硬體效能剖析（Latency + VRAM）────────────────────────
    _vram_all     = [r.get("vram_peak_mb") for r in results if r.get("vram_peak_mb") is not None]
    _vllm_all     = [r.get("vllm_vram_mb") for r in results if r.get("vllm_vram_mb") is not None]
    _lat_all      = [r.get("latency_sec")  for r in results if r.get("latency_sec")  is not None]
    _mode_vram:  dict[str, list[float]] = defaultdict(list)
    _mode_vllm:  dict[str, list[float]] = defaultdict(list)
    _mode_lat:   dict[str, list[float]] = defaultdict(list)
    for r in results:
        m = r.get("answer_mode", "")
        if r.get("vram_peak_mb") is not None:
            _mode_vram[m].append(r["vram_peak_mb"])
        if r.get("vllm_vram_mb") is not None:
            _mode_vllm[m].append(r["vllm_vram_mb"])
        if r.get("latency_sec") is not None:
            _mode_lat[m].append(r["latency_sec"])
    _all_modes = sorted(set(list(_mode_lat.keys()) + list(_mode_vllm.keys()) + list(_mode_vram.keys())))
    hardware_profile: dict[str, Any] = {
        "cuda_available":              _CUDA_OK,
        "vllm_vram_session_peak_mb":   round(max(_vllm_all), 1)                     if _vllm_all else None,
        "vllm_vram_avg_mb":            round(sum(_vllm_all) / len(_vllm_all), 1)    if _vllm_all else None,
        "embedder_vram_session_peak_mb": round(max(_vram_all), 1)                   if _vram_all else None,
        "embedder_vram_avg_mb":        round(sum(_vram_all) / len(_vram_all), 1)    if _vram_all else None,
        "latency_total_sec":           round(sum(_lat_all), 1)                      if _lat_all  else None,
        "latency_avg_sec":             round(sum(_lat_all) / len(_lat_all), 2)      if _lat_all  else None,
        "latency_min_sec":             round(min(_lat_all), 2)                      if _lat_all  else None,
        "latency_max_sec":             round(max(_lat_all), 2)                      if _lat_all  else None,
        "per_mode": {
            m: {
                "n":                  len(_mode_lat.get(m, [])) or len(_mode_vllm.get(m, [])),
                "avg_lat_sec":        round(sum(_mode_lat[m])  / len(_mode_lat[m]),  2) if _mode_lat.get(m)  else None,
                "max_lat_sec":        round(max(_mode_lat[m]),                        2) if _mode_lat.get(m)  else None,
                "avg_vllm_vram_mb":   round(sum(_mode_vllm[m]) / len(_mode_vllm[m]), 1) if _mode_vllm.get(m) else None,
                "max_vllm_vram_mb":   round(max(_mode_vllm[m]),                       1) if _mode_vllm.get(m) else None,
                "avg_embedder_vram_mb": round(sum(_mode_vram[m]) / len(_mode_vram[m]), 1) if _mode_vram.get(m) else None,
            }
            for m in _all_modes
        },
    }

    # ── 組裝報告 ──────────────────────────────────────────────
    report: dict[str, Any] = {
        "summary": {
            "total":              total,
            "answer_mode_dist":   dict(mode_dist),
            "counts":             counts,
            "rates":              rates,
            "academic_metrics":   academic_metrics,
            "nlg_metrics":        nlg_metrics,
            "retrieval_metrics":  retrieval_metrics,
            "repass_stability":   repass_stability,
            "hardware_profile":   hardware_profile,
        },
        "per_type_accuracy":    type_accuracy,
        "per_company_accuracy": company_accuracy,
        "results":              scored_results,
    }

    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # ── 終端輸出 ──────────────────────────────────────────────
    SEP  = "═" * 55
    SEP2 = "─" * 55
    print(f"\n{SEP}")
    print(f"  評測結果彙整  （共 {total} 題）")
    print(SEP)

    metric_labels = {
        "exact_match":     "完全正確      (EM / exact)",
        "numeric_match":   "數字完全一致  (numeric)",
        "contains_match":  "數字包含正確  (contains)",
        "partial_numeric": "部分數字正確  (partial)",
    }
    for k in metric_keys:
        rate  = rates[k]
        bar_s = "█" * int(rate * 25) + "░" * (25 - int(rate * 25))
        print(f"  {metric_labels[k]:<30}: {rate:6.1%}  {bar_s}  ({counts[k]}/{total})")

    print(f"\n  答案模式：", " ｜ ".join(f"{k}={v}" for k, v in mode_dist.items()))

    # ── 學術指標區塊 ─────────────────────────────────────────
    print(f"\n{SEP2}")
    print(f"  學術指標（Academic Metrics）")
    print(SEP2)
    _bar25 = lambda r: "█" * int(r * 25) + "░" * (25 - int(r * 25))
    print(f"  EM   (Exact Match)             : {rates['exact_match']:6.1%}  "
          f"{_bar25(rates['exact_match'])}  ({counts['exact_match']}/{total})")
    print(f"  P    (Precision, 有答案中精確率): {precision:6.1%}  "
          f"{_bar25(precision)}  ({precision_correct}/{answered_count})")
    print(f"  R    (Recall, 回答覆蓋率)       : {recall:6.1%}  "
          f"{_bar25(recall)}  ({answered_count}/{total})")
    print(f"  F1   (調和平均)                 : {f1:6.1%}  {_bar25(f1)}")
    print(f"\n  ┌ Precision 分母：有效回答 {answered_count} 題"
          f"（排除 no_evidence {mode_dist.get('no_evidence',0)} 題"
          f" + 拒答 {total - answered_count - mode_dist.get('no_evidence',0)} 題）")
    print(f"  └ Recall 分母：全量 {total} 題")

    # ── NLG 生成品質指標區塊 ─────────────────────────────────
    print(f"\n{SEP2}")
    print(f"  NLG 生成品質指標（中文分詞 jieba）")
    print(SEP2)
    for rn in (1, 2, 3):
        rm = nlg_metrics[f"rouge_{rn}"]
        if rm["avg_f"] is not None:
            bar = _bar25(rm["avg_f"])
            print(f"  ROUGE-{rn}  F1={rm['avg_f']:.4f}  {bar}  "
                  f"(P={rm['avg_p']:.4f}  R={rm['avg_r']:.4f})")
    bm = nlg_metrics.get("bert_score")
    if bm:
        print(f"  BERTScore F1={bm['avg_f']:.4f}  {_bar25(bm['avg_f'])}  "
              f"(P={bm['avg_p']:.4f}  R={bm['avg_r']:.4f})")
    elif _bs_status == "not_installed":
        print("  BERTScore : — （bert_score 未安裝，執行 pip install bert-score）")
    else:
        print("  BERTScore : 計算失敗（請查看上文 [DEBUG] 報錯訊息）")
    mm = nlg_metrics.get("mover_score")
    if mm:
        print(f"  MoverScore avg={mm['avg']:.4f}  {_bar25(mm['avg'])}")
    elif _ms_status == "not_installed":
        print("  MoverScore: — （moverscore_v2 未安裝，執行 pip install moverscore_v2）")
    else:
        print("  MoverScore: 計算失敗（請查看上文 [DEBUG] 報錯訊息）")

    # ── 檢索品質指標區塊（IR Metrics）────────────────────────
    print(f"\n{SEP2}")
    print(f"  檢索品質指標（Information Retrieval Metrics）")
    print(SEP2)
    rm = retrieval_metrics
    # Hit Rate@K 長條圖
    for k in _RETRIEVAL_K_VALUES:
        hr = rm[f"hit_rate@{k}"]
        print(f"  Hit Rate@{k}   : {hr:6.1%}  {_bar25(hr)}"
              f"  ({hit_counts[k]}/{ret_total})")
    print()
    # NDCG@K 長條圖
    for k in _RETRIEVAL_K_VALUES:
        nd = rm[f"ndcg@{k}"]
        print(f"  NDCG@{k}       : {nd:6.4f}  {_bar25(nd)}")
    print()
    print(f"  MRR           : {rm['mrr']:6.4f}  {_bar25(rm['mrr'])}")
    print(f"\n  ┌ VRL 定義：DL/GR 軌道 = 虛擬 rank-1；VS 軌道 = top-K ChromaDB chunks")
    print(f"  ├ 相關等級：Grade 2=公司+季度+表格全符，Grade 1=公司+季度符")
    print(f"  └ 評估總題數（有金標準公司名）= {ret_total} 題")

    # ── RePASS 穩定性分析區塊 ────────────────────────────────
    print(f"\n{SEP2}")
    print(f"  RePASS 穩定性分析（降級路由影響）")
    print(SEP2)
    delta_sign = "+" if repass_stability["stability_delta"] >= 0 else ""
    print(f"  穩定路由（非降級） {st_n:2d} 題  EM = {st_em_rate:5.1%}  ({st_em}/{st_n})")
    print(f"  降級路由（fallback） {fb_n:2d} 題  EM = {fb_em_rate:5.1%}  ({fb_em}/{fb_n})")
    print(f"  穩定性差距 Δ                      "
          f"{delta_sign}{repass_stability['stability_delta']:.1%}")
    print(f"\n  降級原因包括：pandas_miss（查表失敗回退向量）、"
          f"company_only（季度過濾無命中回退）、graph_rag_disabled")

    # ── 逐題型 ───────────────────────────────────────────────
    _TYPE_LABELS = {
        "cross_company":             "A-跨公司對比",
        "cross_quarter":             "B-跨季度趨勢",
        "entity_lookup":             "C-實體查閱",
        "colloquial":                "D-口語化提問",
        "multi_hop_graph_reasoning": "E-多跳圖譜推理",
        "template":                  "標準模板",
    }
    print(f"\n  逐題型 exact / recall / fallback_rate：")
    for qtype, acc in type_accuracy.items():
        label = _TYPE_LABELS.get(qtype, qtype)
        print(
            f"    {label:<14}  EM={acc['exact_rate']:5.1%}"
            f"  R={acc['recall_rate']:5.1%}"
            f"  FB={acc['fallback_rate']:5.1%}"
            f"  ({acc['exact']}/{acc['total']})"
        )

    # ── 逐公司 ───────────────────────────────────────────────
    print(f"\n  逐公司 exact_match：")
    for cname, acc in company_accuracy.items():
        print(f"    {cname:<15}  {acc['exact_rate']:5.1%}  ({acc['exact']}/{acc['total']})")

    # ── 硬體效能剖析（Latency + VRAM）───────────────────────
    hp = hardware_profile
    print(f"\n{SEP2}")
    print(f"  硬體效能剖析（Edge-AI Operational Efficiency）")
    print(SEP2)
    if hp.get("latency_total_sec") is not None:
        print(f"  回答時間 總計         : {hp['latency_total_sec']:>8.1f} s")
        print(f"  單題 Latency 平均     : {hp['latency_avg_sec']:>8.2f} s"
              f"  (min={hp['latency_min_sec']:.2f}s  max={hp['latency_max_sec']:.2f}s)")
    if hp.get("vllm_vram_session_peak_mb") is not None:
        print(f"  vLLM VRAM 會話最高峰值: {hp['vllm_vram_session_peak_mb']:>8.1f} MB"
              f"  (avg={hp['vllm_vram_avg_mb']:.1f} MB)")
    else:
        print("  vLLM VRAM             : 0.0 MB（pynvml 未安裝或行程未找到）")
    if hp["cuda_available"] and hp.get("embedder_vram_session_peak_mb"):
        print(f"  嵌入模型 VRAM 峰值    : {hp['embedder_vram_session_peak_mb']:>8.1f} MB"
              f"  (avg={hp['embedder_vram_avg_mb']:.1f} MB)")
    if hp.get("per_mode"):
        print(f"\n  {'通道':<28}  {'avg_lat':>8}  {'max_lat':>8}  {'avg_vLLM':>10}  {'max_vLLM':>10}")
        for m, mv in hp["per_mode"].items():
            lat_avg  = f"{mv['avg_lat_sec']:.2f}s"      if mv.get("avg_lat_sec")      is not None else "   —   "
            lat_max  = f"{mv['max_lat_sec']:.2f}s"      if mv.get("max_lat_sec")      is not None else "   —   "
            vv_avg   = f"{mv['avg_vllm_vram_mb']:.1f}MB" if mv.get("avg_vllm_vram_mb") is not None else "    —    "
            vv_max   = f"{mv['max_vllm_vram_mb']:.1f}MB" if mv.get("max_vllm_vram_mb") is not None else "    —    "
            print(f"    {m:<26}  {lat_avg:>8}  {lat_max:>8}  {vv_avg:>10}  {vv_max:>10}  (n={mv['n']})")

    # ── 逐題答案比對 ──────────────────────────────────────────
    if show_answers:
        _TYPE_SHORT = {
            "cross_company":             "A-跨公司",
            "cross_quarter":             "B-跨季度",
            "entity_lookup":             "C-實體查閱",
            "colloquial":                "D-口語化",
            "multi_hop_graph_reasoning": "E-多跳推理",
            "template":                  "標準模板",
        }
        _MODE_SHORT = {
            "direct_lookup":      "DL",
            "vector_search":      "VS",
            "no_evidence":        "NE",
            "graph_rag_local":    "GRL",
            "graph_rag_topology": "GRT",
            "graph_rag":          "GR",
            "llm_only":           "LLM",
        }

        def _trunc(s: str, n: int = 65) -> str:
            return (s[:n] + "…") if len(s) > n else s

        print(f"\n{SEP}")
        print(f"  逐題答案比對  （✓=EM正確  ✗=錯誤  —=no_evidence）")
        print(SEP)
        for it in scored_results:
            idx    = str(it.get("id", "?")).rjust(2)
            meta   = it.get("metadata", {})
            qtype  = meta.get("question_type") or it.get("question_type", "template")
            mode   = it.get("answer_mode", "")
            em_ok  = it["scores"]["exact_match"]
            pred   = it.get("answer", "")
            ref    = it.get("expected_answer", "")
            q      = it.get("question", "")

            mark   = "✓" if em_ok else ("—" if mode == "no_evidence" else "✗")
            tlabel = _TYPE_SHORT.get(qtype, qtype)
            mlabel = _MODE_SHORT.get(mode, mode)

            # 檢索命中標記
            _ret   = it.get("retrieval", {})
            h1_mk  = "H1✓" if _ret.get("hit@1") else "H1✗"
            h5_mk  = "H5✓" if _ret.get("hit@5") else "H5✗"
            nd5    = _ret.get("ndcg@5", 0.0)
            ret_tag = f"{h1_mk} {h5_mk} N@5={nd5:.2f}" if _ret else ""

            print(f"  [{idx}] {mark}  {tlabel:<10}  ({mlabel})  {ret_tag}")
            print(f"        Q : {_trunc(q, 72)}")
            print(f"        期 : {_trunc(ref)}")
            if not em_ok:
                pred_lines = [l for l in pred.splitlines() if l.strip()]
                if not pred_lines:
                    pred_lines = [pred]
                print(f"        答 : {_trunc(pred_lines[0])}")
                for pl in pred_lines[1:4]:
                    print(f"            {_trunc(pl)}")
                if len(pred_lines) > 4:
                    print(f"            … (共 {len(pred_lines)} 行)")
            chunks = it.get("retrieved_chunks", [])
            if chunks:
                for ci, ch in enumerate(chunks, 1):
                    hdr = (f"{ch.get('company_name','')} {ch.get('quarter','')} "
                           f"{ch.get('table_name','')}  score={ch.get('score',0):.3f}")
                    print(f"        ↳ 片段{ci} {hdr}")
                    content_lines = ch.get("content", "").splitlines()
                    for line in content_lines[:10]:
                        if line.strip():
                            print(f"             {_trunc(line, 68)}")
                    if len(content_lines) > 10:
                        print(f"             … (共 {len(content_lines)} 行)")
            print(f"        {'─' * 50}")

    print(f"\n{SEP}")
    print(f"  完整報告 → {output_path}")
    print(SEP)
    return report


# ══════════════════════════════════════════════════════════════
#  CLI 入口
# ══════════════════════════════════════════════════════════════


def _add_root_arg(p: argparse.ArgumentParser) -> None:
    p.add_argument("--root", type=Path, default=REPORTS_ROOT,
                   help=f"reports_csv_output 根目錄 (default: {REPORTS_ROOT})")


def _add_vector_args(p: argparse.ArgumentParser) -> None:
    """向量 DB / Embedding 共用參數。"""
    p.add_argument("--db",    type=Path, default=DEFAULT_VECTOR_DB,
                   help=f"Vector DB 路徑 (default: {DEFAULT_VECTOR_DB.name})")
    p.add_argument("--embedding-model", default=DEFAULT_EMBED_MODEL,
                   help=f"Embedding 模型 (default: {DEFAULT_EMBED_MODEL})")
    p.add_argument("--embed-device", default="cpu",
                   help="Embedding 運算裝置：cpu / cuda (default: cpu)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rag_test_system.py",
        description="多公司財報 RAG 四大模組整合測試系統",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "完整流程：\n"
            "  python rag_test_system.py run-all\n\n"
            "分步執行：\n"
            "  python rag_test_system.py csv2md\n"
            "  python rag_test_system.py build-index\n"
            "  python rag_test_system.py gen-dataset\n"
            "  python rag_test_system.py rag-query\n"
            "  python rag_test_system.py evaluate\n"
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # ── Module 1：csv2md ───────────────────────────────────────
    p1 = sub.add_parser("csv2md", help="[Module 1] 原始 CSV → Markdown 美化轉換")
    _add_root_arg(p1)
    p1.add_argument("--force", action="store_true", help="覆蓋已存在的 .md 檔案")
    p1.add_argument("--quiet", action="store_true", help="不印每個檔案的轉換訊息")

    # ── build-index ────────────────────────────────────────────
    bi = sub.add_parser("build-index",
                        help="從所有 .md 檔建立持久化 ChromaDB 向量索引")
    _add_root_arg(bi)
    _add_vector_args(bi)
    bi.add_argument("--chunk-size",    type=int, default=1500,
                    help="每個 chunk 的最大字元數 (default: 1500)")
    bi.add_argument("--chunk-overlap", type=int, default=200,
                    help="chunk 重疊字元數 (default: 200)")
    bi.add_argument("--force", action="store_true",
                    help="強制重建，忽略已存在的 Vector DB")

    # ── Module 2：gen-dataset ──────────────────────────────────
    p2 = sub.add_parser("gen-dataset", help="[Module 2] 自動生成 QA 測試資料集")
    _add_root_arg(p2)
    p2.add_argument("--output",  type=Path, default=DEFAULT_DATASET_OUTPUT)
    p2.add_argument("--samples", type=int,  default=50,
                    help="生成 A~D 基礎題數，四種題型均勻分布（default: 50；Type E 由 extend_test_dataset.py 追加）")
    p2.add_argument("--seed",    type=int,  default=42)

    # ── Module 3：rag-query ────────────────────────────────────
    p3 = sub.add_parser("rag-query",
                        help="[Module 3] 向量檢索 + vLLM 回答測試集")
    _add_root_arg(p3)
    _add_vector_args(p3)
    p3.add_argument("--dataset", type=Path, default=DEFAULT_DATASET_OUTPUT)
    p3.add_argument("--output",  type=Path, default=DEFAULT_RAG_RESULTS)
    p3.add_argument("--vllm-url",  default=DEFAULT_VLLM_URL)
    p3.add_argument("--llm-model", default=DEFAULT_LLM_MODEL)
    p3.add_argument("--top-k",   type=int, default=5,
                    help="每次查詢取回的 chunks 數量 (default: 5)")
    p3.add_argument("--limit",   type=int, default=0,
                    help="限制查詢筆數，0 = 全部（default: 0）")
    p3.add_argument("--vector-only", action="store_true",
                    help="消融實驗：跳過 LLM 路由器、GraphRAG、精確查表，純向量搜尋")
    p3.add_argument("--llm-only", action="store_true",
                    help="消融實驗：純 LLM 回答，不提供任何檢索內容（零 context baseline）")
    p3.add_argument("--graph-only", action="store_true",
                    help="消融實驗：只走圖譜路徑（GRT/GRL），不走 DL/VS")
    p3.add_argument("--no-direct", action="store_true",
                    help="消融實驗：圖譜+向量，強制走圖譜，無命中跑 VS，跳過 DL")

    # ── Module 4：evaluate ────────────────────────────────────
    p4 = sub.add_parser("evaluate", help="[Module 4] 評估 RAG 查詢結果")
    p4.add_argument("--results", type=Path, default=DEFAULT_RAG_RESULTS)
    p4.add_argument("--output",  type=Path, default=DEFAULT_EVAL_REPORT)
    p4.add_argument("--no-show-answers", action="store_true",
                    help="關閉逐題答案比對輸出（預設：顯示）")

    # ── run-all ────────────────────────────────────────────────
    ra = sub.add_parser("run-all", help="依序執行全部流程（M1 → build-index → M2 → M3 → M4）")
    _add_root_arg(ra)
    _add_vector_args(ra)
    ra.add_argument("--chunk-size",    type=int, default=1500)
    ra.add_argument("--chunk-overlap", type=int, default=200)
    ra.add_argument("--samples",  type=int, default=50,
                    help="生成 A~D 基礎題數（default: 50；Type E 由 extend_test_dataset.py 追加）")
    ra.add_argument("--seed",     type=int, default=42)
    ra.add_argument("--vllm-url",   default=DEFAULT_VLLM_URL)
    ra.add_argument("--llm-model",  default=DEFAULT_LLM_MODEL)
    ra.add_argument("--top-k",    type=int, default=5)
    ra.add_argument("--limit",    type=int, default=0)
    ra.add_argument("--vector-only", action="store_true",
                    help="消融實驗：Module 3 純向量搜尋，跳過路由器與精確查表")
    ra.add_argument("--force-md",    action="store_true",
                    help="Module 1：覆蓋已存在的 .md 檔案")
    ra.add_argument("--skip-md",     action="store_true",
                    help="跳過 Module 1（.md 已存在時可省時）")
    ra.add_argument("--force-index", action="store_true",
                    help="強制重建 Vector DB")
    ra.add_argument("--skip-index",  action="store_true",
                    help="跳過 build-index（Vector DB 已存在時可省時）")

    return parser


def main() -> None:
    parser = build_parser()
    args   = parser.parse_args()

    # ── Module 1 ──────────────────────────────────────────────
    if args.command == "csv2md":
        _print_section("Module 1：CSV → Markdown 美化轉換")
        r = run_module1_csv_to_markdown(
            args.root, force=args.force, verbose=not args.quiet
        )
        print(f"\n  完成：{r['converted']} 檔轉換 ｜ {r['skipped']} 跳過 ｜ {r['errors']} 錯誤")

    # ── build-index ───────────────────────────────────────────
    elif args.command == "build-index":
        _print_section("build-index：建立 ChromaDB 向量索引")
        build_vector_index(
            root=args.root,
            db_path=args.db,
            embedding_model=args.embedding_model,
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
            force=args.force,
            device=args.embed_device,
        )

    # ── Module 2 ──────────────────────────────────────────────
    elif args.command == "gen-dataset":
        _print_section("Module 2：測試資料集生成")
        generate_test_dataset(args.root, args.output, args.samples, args.seed)

    # ── Module 3 ──────────────────────────────────────────────
    elif args.command == "rag-query":
        _print_section("Module 3：RAG 查詢引擎（向量檢索）")
        if not args.dataset.exists():
            sys.exit(f"  ERROR：找不到測試資料集 {args.dataset}\n"
                     f"  請先執行：python rag_test_system.py gen-dataset")
        run_module3_rag_queries(
            dataset_path=args.dataset,
            root=args.root,
            output_path=args.output,
            vllm_url=args.vllm_url,
            llm_model=args.llm_model,
            limit=args.limit,
            db_path=args.db,
            embedding_model=args.embedding_model,
            top_k=args.top_k,
            embed_device=args.embed_device,
            vector_only=args.vector_only,
            llm_only=args.llm_only,
            graph_only=args.graph_only,
            no_direct=args.no_direct,
        )

    # ── Module 4 ──────────────────────────────────────────────
    elif args.command == "evaluate":
        _print_section("Module 4：自動評估評分")
        if not args.results.exists():
            sys.exit(f"  ERROR：找不到查詢結果 {args.results}\n"
                     f"  請先執行：python rag_test_system.py rag-query")
        run_module4_evaluate(
            args.results, args.output,
            show_answers=not args.no_show_answers,
        )

    # ── run-all ───────────────────────────────────────────────
    elif args.command == "run-all":
        dataset_path = DEFAULT_DATASET_OUTPUT
        results_path = DEFAULT_RAG_RESULTS
        eval_path    = DEFAULT_EVAL_REPORT

        if not args.skip_md:
            _print_section("Module 1：CSV → Markdown 美化轉換")
            r = run_module1_csv_to_markdown(
                args.root, force=args.force_md, verbose=False
            )
            print(f"\n  完成：{r['converted']} 檔轉換 ｜ {r['skipped']} 跳過 ｜ {r['errors']} 錯誤")
        else:
            print("\n  [Module 1] 已跳過（--skip-md）")

        if not args.skip_index:
            _print_section("build-index：建立 ChromaDB 向量索引")
            build_vector_index(
                root=args.root,
                db_path=args.db,
                embedding_model=args.embedding_model,
                chunk_size=args.chunk_size,
                chunk_overlap=args.chunk_overlap,
                force=args.force_index,
                device=args.embed_device,
            )
        else:
            print("\n  [build-index] 已跳過（--skip-index）")

        _print_section("Module 2：測試資料集生成")
        generate_test_dataset(args.root, dataset_path, args.samples, args.seed)

        _print_section("Module 3：RAG 查詢引擎（向量檢索）")
        run_module3_rag_queries(
            dataset_path=dataset_path,
            root=args.root,
            output_path=results_path,
            vllm_url=args.vllm_url,
            llm_model=args.llm_model,
            limit=args.limit,
            db_path=args.db,
            embedding_model=args.embedding_model,
            top_k=args.top_k,
            embed_device=args.embed_device,
            vector_only=args.vector_only,
        )

        _print_section("Module 4：自動評估評分")
        run_module4_evaluate(results_path, eval_path)


if __name__ == "__main__":
    main()
