# -*- coding: utf-8 -*-
"""
build_all_graphs_merged_all_targets.py

整合版建圖程式：一次整合 investment / related_party / supply_chain / risk_event。

合併來源：
- build_all_graphs.py：原有 investment / related_party / supply_chain 內嵌建圖流程。
- build_all_graphs_deal_fact_risk_event.py：risk_event 風險事件圖譜流程。

新增功能：
- --only 支援 investment / related_party / supply_chain / risk_event。
- --stock-ids / --periods 可傳入 investment / related_party / risk_event。
- --import-neo4j 可把產出的 neo4j_nodes.csv / neo4j_relationships.csv 匯入 Neo4j。
- --clear-neo4j-target 可在匯入前清除本次 target 的舊圖譜。
- --clear-neo4j-all 可在匯入前清除所有 GraphNode 圖譜。

注意：
- related_party 匯入前若要清掉舊的 Q2/Q3 關係圖，建議使用 --clear-neo4j-target。
- risk_event 的 Neo4j 匯入沿用原風險事件 importer，--clear-neo4j-target 會等價啟用 clear-risk-only。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import pandas as pd

_EMBEDDED_SOURCES = {'investment': '# -*- coding: utf-8 -*-\n'
               '"""\n'
               'build_investment_graph_from_reports_csv_v2.py\n'
               '\n'
               '用途：\n'
               '1. 掃描 reports_csv_output 底下「所有公司」。\n'
               '2. 找出每家公司是否有「被投資公司名稱、所在地區...等相關資訊.csv」這類表。\n'
               '3. 將找到的投資關係表建立成圖譜 CSV，供 import_investment_graph_via_neo4j_driver.py 匯入 Neo4j。\n'
               '\n'
               '比前版多的修正：\n'
               '- 不只靠檔名嚴格比對，也會讀 CSV 前幾列判斷是否為投資關係表。\n'
               '- 會輸出 scan_report.csv，列出每家公司/季度有沒有掃到目標表。\n'
               '- 預設掃全部公司、全部季度。\n'
               '\n'
               '執行：\n'
               '    python3 build_investment_graph_from_reports_csv_v2.py\n'
               '"""\n'
               '\n'
               'from __future__ import annotations\n'
               '\n'
               'import csv\n'
               'import json\n'
               'import re\n'
               'import hashlib\n'
               'from dataclasses import dataclass, asdict\n'
               'from pathlib import Path\n'
               'from typing import Dict, List, Optional, Tuple\n'
               '\n'
               'import pandas as pd\n'
               '\n'
               '\n'
               '# ============================================================\n'
               '# 1. 設定區\n'
               '# ============================================================\n'
               'INPUT_DIR = Path("./reports_csv_output")\n'
               'OUTPUT_DIR = Path("./investment_graph_output")\n'
               '\n'
               'ROOT_ID = "investment_network:tw_listed_companies"\n'
               'ROOT_NAME = "台灣上市櫃公司被投資公司關係圖譜"\n'
               '\n'
               'ENCODING_CANDIDATES = ["utf-8-sig", "utf-8", "cp950", "big5"]\n'
               '\n'
               '# 空集合 = 全部公司\n'
               'TEST_STOCK_IDS = set()\n'
               '# 例：只測 2303\n'
               '# TEST_STOCK_IDS = {"2303"}\n'
               '\n'
               '# 空集合 = 全部季度\n'
               'TEST_PERIODS = set()\n'
               '# 例：只測 114Q2\n'
               '# TEST_PERIODS = {"114Q2"}\n'
               '\n'
               'WRITE_HTML_GRAPH = True\n'
               '\n'
               '# 目標表格內容關鍵字。檔名不穩時，會讀 CSV 內容判斷。\n'
               'CONTENT_REQUIRED_KEYWORDS = ["被投資公司", "所在地區"]\n'
               'CONTENT_OPTIONAL_KEYWORDS = ["投資公司", "主要營業項目", "期末持有", "原始投資金額", "本期認列"]\n'
               '\n'
               '# 依公開資訊觀測站常見欄位位置定義\n'
               'POSITIONAL_COLUMNS = [\n'
               '    "investor_name",                  # 投資公司名稱\n'
               '    "investee_name",                  # 被投資公司名稱\n'
               '    "investee_code_or_index",          # 可能為代號 / 索引 / 原表第三欄\n'
               '    "location",                       # 所在地區\n'
               '    "main_business",                  # 主要營業項目\n'
               '    "original_investment_end",         # 原始投資金額：本期期末\n'
               '    "original_investment_prior",       # 原始投資金額：去年年底 / 上期期末\n'
               '    "shares_held",                    # 期末持有股數\n'
               '    "ownership_percent",              # 期末持有比率\n'
               '    "book_value",                     # 期末持有帳面金額\n'
               '    "investment_income_loss",          # 本期認列之投資損益\n'
               '    "note",                           # 備註\n'
               ']\n'
               '\n'
               '\n'
               '# ============================================================\n'
               '# 2. 資料結構\n'
               '# ============================================================\n'
               '@dataclass\n'
               'class InvestmentRecord:\n'
               '    report_stock_id: str\n'
               '    report_company_name: str\n'
               '    report_period: str\n'
               '    report_year: int\n'
               '    report_quarter: int\n'
               '\n'
               '    investor_name: str\n'
               '    investee_name: str\n'
               '    investee_code_or_index: str\n'
               '    location: str\n'
               '    main_business: str\n'
               '\n'
               '    original_investment_end: Optional[float]\n'
               '    original_investment_prior: Optional[float]\n'
               '    shares_held: Optional[float]\n'
               '    ownership_percent: Optional[float]\n'
               '    book_value: Optional[float]\n'
               '    investment_income_loss: Optional[float]\n'
               '    note: str\n'
               '\n'
               '    source_csv: str\n'
               '    source_row_index: int\n'
               '    raw_row_json: str\n'
               '\n'
               '\n'
               '# ============================================================\n'
               '# 3. 基礎工具\n'
               '# ============================================================\n'
               'def clean_text(value) -> str:\n'
               '    if value is None:\n'
               '        return ""\n'
               '    text = str(value)\n'
               '    text = text.replace("\\xa0", " ").replace("\\u3000", " ")\n'
               '    text = text.replace("\\r", " ").replace("\\n", " ")\n'
               '    text = re.sub(r"\\s+", " ", text).strip()\n'
               '    if text.lower() in {"nan", "none"}:\n'
               '        return ""\n'
               '    return text\n'
               '\n'
               '\n'
               'def normalize_for_match(text: str) -> str:\n'
               '    text = clean_text(text)\n'
               '    text = text.replace("…", "").replace("...", "")\n'
               '    text = re.sub(r"[\\s_、，,。．.（）()【】\\[\\]-]+", "", text)\n'
               '    return text\n'
               '\n'
               '\n'
               'def read_csv_with_fallback(path: Path, header=None, nrows=None) -> pd.DataFrame:\n'
               '    last_error = None\n'
               '    for enc in ENCODING_CANDIDATES:\n'
               '        try:\n'
               '            return pd.read_csv(path, encoding=enc, header=header, dtype=str, nrows=nrows).fillna("")\n'
               '        except UnicodeDecodeError as e:\n'
               '            last_error = e\n'
               '            continue\n'
               '    raise UnicodeDecodeError("unknown", b"", 0, 1, '
               'f"無法用這些編碼讀取：{ENCODING_CANDIDATES}。最後錯誤：{last_error}")\n'
               '\n'
               '\n'
               'def clean_number(value) -> Optional[float]:\n'
               '    text = clean_text(value)\n'
               '    if not text or text in {"-", "－", "—", "--"}:\n'
               '        return None\n'
               '    text = text.replace("$", "").replace("＄", "").replace(",", "")\n'
               '    text = text.replace("%", "").replace("％", "").replace(" ", "")\n'
               '    if text.startswith("(") and text.endswith(")"):\n'
               '        text = "-" + text[1:-1]\n'
               '    try:\n'
               '        return float(text)\n'
               '    except ValueError:\n'
               '        return None\n'
               '\n'
               '\n'
               'def number_to_text(value: Optional[float]) -> str:\n'
               '    return "" if value is None else str(value)\n'
               '\n'
               '\n'
               'def safe_id(text: str) -> str:\n'
               '    s = clean_text(text).lower()\n'
               '    s = re.sub(r"\\s+", "_", s)\n'
               '    s = re.sub(r"[^0-9a-zA-Z_\\u4e00-\\u9fff:-]", "_", s)\n'
               '    s = re.sub(r"_+", "_", s).strip("_")\n'
               '    if not s:\n'
               '        s = hashlib.md5(str(text).encode("utf-8")).hexdigest()[:12]\n'
               '    return s\n'
               '\n'
               '\n'
               'def normalize_company_key(name: str) -> str:\n'
               '    s = clean_text(name)\n'
               '    s_upper = s.upper()\n'
               '\n'
               '    suffixes = [\n'
               '        "股份有限公司及其子公司",\n'
               '        "股份有限公司及子公司",\n'
               '        "股份有限公司",\n'
               '        "有限公司",\n'
               '        "(股)公司",\n'
               '        "（股）公司",\n'
               '        "公司",\n'
               '        "CORPORATION",\n'
               '        "CORP.",\n'
               '        "CORP",\n'
               '        "LTD.",\n'
               '        "LTD",\n'
               '        "LIMITED",\n'
               '    ]\n'
               '\n'
               '    for suf in suffixes:\n'
               '        s = s.replace(suf, "")\n'
               '        s_upper = s_upper.replace(suf, "")\n'
               '\n'
               '    if re.search(r"[A-Za-z]", s_upper):\n'
               '        s = s_upper\n'
               '\n'
               '    s = re.sub(r"[\\s\\-_()（）.,，。]", "", s)\n'
               '    return s.strip()\n'
               '\n'
               '\n'
               'def company_node_id(name: str, stock_code: str = "") -> str:\n'
               '    stock_code = clean_text(stock_code)\n'
               '    if re.fullmatch(r"\\d{4}[A-Z]?", stock_code):\n'
               '        return f"company:{stock_code}"\n'
               '    return f"company_name:{safe_id(normalize_company_key(name) or name)}"\n'
               '\n'
               '\n'
               'def country_node_id(location: str) -> str:\n'
               '    return f"location:{safe_id(location or \'未標註\')}"\n'
               '\n'
               '\n'
               'def business_node_id(business: str) -> str:\n'
               '    return f"business:{safe_id(business or \'未標註\')}"\n'
               '\n'
               '\n'
               'def roc_year_to_ad(year: int) -> int:\n'
               '    return year + 1911 if 1 <= year < 1911 else year\n'
               '\n'
               '\n'
               'def parse_period_folder(period_folder: str) -> Tuple[int, int]:\n'
               '    text = str(period_folder).upper()\n'
               '    m = re.search(r"(\\d{3,4})Q([1-4])", text)\n'
               '    if not m:\n'
               '        return 0, 0\n'
               '    return roc_year_to_ad(int(m.group(1))), int(m.group(2))\n'
               '\n'
               '\n'
               'def parse_stock_folder(stock_folder_name: str) -> Tuple[str, str]:\n'
               '    parts = str(stock_folder_name).split("_")\n'
               '    stock_id = parts[0] if len(parts) >= 1 else "Unknown"\n'
               '    company_name = parts[1] if len(parts) >= 2 else f"公司{stock_id}"\n'
               '    return stock_id, company_name\n'
               '\n'
               '\n'
               '# ============================================================\n'
               '# 4. 掃描目標 CSV\n'
               '# ============================================================\n'
               'def is_target_by_filename(path: Path) -> bool:\n'
               '    name = normalize_for_match(path.stem)\n'
               '    return ("被投資公司" in name and ("所在地區" in name or "相關資訊" in name or "投資資訊" in name))\n'
               '\n'
               '\n'
               'def is_target_by_content(path: Path) -> bool:\n'
               '    try:\n'
               '        df = read_csv_with_fallback(path, header=None, nrows=5)\n'
               '    except Exception:\n'
               '        return False\n'
               '\n'
               '    text = normalize_for_match(" ".join(df.astype(str).to_numpy().ravel().tolist()))\n'
               '    required_ok = all(normalize_for_match(k) in text for k in CONTENT_REQUIRED_KEYWORDS)\n'
               '    optional_hits = sum(1 for k in CONTENT_OPTIONAL_KEYWORDS if normalize_for_match(k) in text)\n'
               '    return required_ok and optional_hits >= 1\n'
               '\n'
               '\n'
               'def is_target_investment_csv(path: Path) -> bool:\n'
               '    if path.suffix.lower() != ".csv":\n'
               '        return False\n'
               '    if is_target_by_filename(path):\n'
               '        return True\n'
               '    return is_target_by_content(path)\n'
               '\n'
               '\n'
               'def iter_company_period_dirs(input_dir: Path):\n'
               '    for company_dir in sorted(p for p in input_dir.iterdir() if p.is_dir()):\n'
               '        stock_id = company_dir.name.split("_")[0]\n'
               '\n'
               '        if TEST_STOCK_IDS and stock_id not in TEST_STOCK_IDS:\n'
               '            continue\n'
               '\n'
               '        for period_dir in sorted(p for p in company_dir.iterdir() if p.is_dir()):\n'
               '            if TEST_PERIODS and period_dir.name not in TEST_PERIODS:\n'
               '                continue\n'
               '            yield company_dir, period_dir\n'
               '\n'
               '\n'
               'def scan_target_csv_files(input_dir: Path) -> Tuple[List[Path], List[dict]]:\n'
               '    if not input_dir.exists():\n'
               '        raise FileNotFoundError(f"找不到輸入資料夾：{input_dir.resolve()}")\n'
               '\n'
               '    target_files: List[Path] = []\n'
               '    scan_rows: List[dict] = []\n'
               '\n'
               '    for company_dir, period_dir in iter_company_period_dirs(input_dir):\n'
               '        stock_id, company_name = parse_stock_folder(company_dir.name)\n'
               '        csv_files = sorted(period_dir.glob("*.csv"))\n'
               '\n'
               '        matched = []\n'
               '        for csv_file in csv_files:\n'
               '            if is_target_investment_csv(csv_file):\n'
               '                matched.append(csv_file)\n'
               '                target_files.append(csv_file)\n'
               '\n'
               '        scan_rows.append({\n'
               '            "stock_id": stock_id,\n'
               '            "company_name": company_name,\n'
               '            "period": period_dir.name,\n'
               '            "csv_count": len(csv_files),\n'
               '            "target_count": len(matched),\n'
               '            "target_files": ";".join(p.name for p in matched),\n'
               '        })\n'
               '\n'
               '    return target_files, scan_rows\n'
               '\n'
               '\n'
               '# ============================================================\n'
               '# 5. 投資表解析\n'
               '# ============================================================\n'
               'def looks_like_header_row(values: List[str]) -> bool:\n'
               '    joined = "".join(values)\n'
               '    keywords = ["投資公司名稱", "被投資公司名稱", "所在地區", "主要營業項目", "原始投資金額", "期末持有", "本期認列", "備註"]\n'
               '    return any(k in joined for k in keywords)\n'
               '\n'
               '\n'
               'def make_positional_record(row_values: List[str]) -> Dict[str, str]:\n'
               '    output = {}\n'
               '    for idx, col in enumerate(POSITIONAL_COLUMNS):\n'
               '        output[col] = clean_text(row_values[idx]) if idx < len(row_values) else ""\n'
               '    for idx in range(len(POSITIONAL_COLUMNS), len(row_values)):\n'
               '        output[f"extra_col_{idx + 1}"] = clean_text(row_values[idx])\n'
               '    return output\n'
               '\n'
               '\n'
               'def is_valid_investment_row(row: Dict[str, str]) -> bool:\n'
               '    investor = clean_text(row.get("investor_name", ""))\n'
               '    investee = clean_text(row.get("investee_name", ""))\n'
               '    if not investor and not investee:\n'
               '        return False\n'
               '    joined = investor + investee\n'
               '    if any(k in joined for k in ["投資公司名稱", "被投資公司名稱", "合計", "總計"]):\n'
               '        return False\n'
               '    if not investee:\n'
               '        return False\n'
               '    return True\n'
               '\n'
               '\n'
               'def parse_investment_csv(csv_file: Path) -> List[InvestmentRecord]:\n'
               '    period_folder = csv_file.parent.name\n'
               '    stock_folder = csv_file.parent.parent.name\n'
               '\n'
               '    report_stock_id, report_company_name = parse_stock_folder(stock_folder)\n'
               '    report_year, report_quarter = parse_period_folder(period_folder)\n'
               '\n'
               '    df = read_csv_with_fallback(csv_file, header=None)\n'
               '    records: List[InvestmentRecord] = []\n'
               '\n'
               '    for row_idx, row in df.iterrows():\n'
               '        row_values = [clean_text(v) for v in row.tolist()]\n'
               '        if not any(row_values):\n'
               '            continue\n'
               '        if looks_like_header_row(row_values):\n'
               '            continue\n'
               '\n'
               '        row_dict = make_positional_record(row_values)\n'
               '        if not is_valid_investment_row(row_dict):\n'
               '            continue\n'
               '\n'
               '        records.append(\n'
               '            InvestmentRecord(\n'
               '                report_stock_id=report_stock_id,\n'
               '                report_company_name=report_company_name,\n'
               '                report_period=period_folder,\n'
               '                report_year=report_year,\n'
               '                report_quarter=report_quarter,\n'
               '                investor_name=row_dict.get("investor_name", ""),\n'
               '                investee_name=row_dict.get("investee_name", ""),\n'
               '                investee_code_or_index=row_dict.get("investee_code_or_index", ""),\n'
               '                location=row_dict.get("location", ""),\n'
               '                main_business=row_dict.get("main_business", ""),\n'
               '                original_investment_end=clean_number(row_dict.get("original_investment_end", "")),\n'
               '                original_investment_prior=clean_number(row_dict.get("original_investment_prior", '
               '"")),\n'
               '                shares_held=clean_number(row_dict.get("shares_held", "")),\n'
               '                ownership_percent=clean_number(row_dict.get("ownership_percent", "")),\n'
               '                book_value=clean_number(row_dict.get("book_value", "")),\n'
               '                investment_income_loss=clean_number(row_dict.get("investment_income_loss", "")),\n'
               '                note=row_dict.get("note", ""),\n'
               '                source_csv=str(csv_file),\n'
               '                source_row_index=int(row_idx),\n'
               '                raw_row_json=json.dumps(row_dict, ensure_ascii=False),\n'
               '            )\n'
               '        )\n'
               '\n'
               '    return records\n'
               '\n'
               '\n'
               'def parse_all_investment_tables(input_dir: Path) -> Tuple[List[InvestmentRecord], List[dict]]:\n'
               '    target_files, scan_rows = scan_target_csv_files(input_dir)\n'
               '\n'
               '    print(f"掃描公司/季度組合：{len(scan_rows)}")\n'
               '    print(f"找到目標投資表 CSV：{len(target_files)} 個")\n'
               '\n'
               '    all_records: List[InvestmentRecord] = []\n'
               '\n'
               '    for csv_file in target_files:\n'
               '        try:\n'
               '            records = parse_investment_csv(csv_file)\n'
               '            all_records.extend(records)\n'
               '            print(f"[OK] {csv_file} -> {len(records)} 筆")\n'
               '        except Exception as e:\n'
               '            print(f"[Skip] {csv_file} -> {e}")\n'
               '\n'
               '    return all_records, scan_rows\n'
               '\n'
               '\n'
               '# ============================================================\n'
               '# 6. 建立圖譜\n'
               '# ============================================================\n'
               'def add_node(nodes: Dict[str, dict], node_id: str, label: str, **props) -> None:\n'
               '    if node_id not in nodes:\n'
               '        nodes[node_id] = {"id": node_id, "label": label, **props}\n'
               '        return\n'
               '    for k, v in props.items():\n'
               '        if v in ["", None]:\n'
               '            continue\n'
               '        if k not in nodes[node_id] or nodes[node_id][k] in ["", None, "未標註", "未分類"]:\n'
               '            nodes[node_id][k] = v\n'
               '\n'
               '\n'
               'def add_edge(edges: Dict[Tuple[str, str, str, str], dict], source: str, target: str, edge_type: str, '
               'edge_key: str = "", **props) -> None:\n'
               '    key = (source, target, edge_type, edge_key)\n'
               '    if key not in edges:\n'
               '        edges[key] = {"source": source, "target": target, "type": edge_type, **props}\n'
               '        return\n'
               '\n'
               '    for field in ["source_csv", "source_row_index"]:\n'
               '        if field in props:\n'
               '            old = str(edges[key].get(field, ""))\n'
               '            new = str(props[field])\n'
               '            if new and new not in old.split(";"):\n'
               '                edges[key][field] = f"{old};{new}" if old else new\n'
               '\n'
               '\n'
               'def build_graph(records: List[InvestmentRecord]) -> Tuple[List[dict], List[dict]]:\n'
               '    nodes: Dict[str, dict] = {}\n'
               '    edges: Dict[Tuple[str, str, str, str], dict] = {}\n'
               '\n'
               '    add_node(nodes, ROOT_ID, "InvestmentNetwork", name=ROOT_NAME)\n'
               '\n'
               '    for r in records:\n'
               '        report_company_id = company_node_id(r.report_company_name, r.report_stock_id)\n'
               '\n'
               '        if normalize_company_key(r.investor_name) == normalize_company_key(r.report_company_name):\n'
               '            investor_id = report_company_id\n'
               '        else:\n'
               '            investor_id = company_node_id(r.investor_name)\n'
               '\n'
               '        investee_stock_code = r.investee_code_or_index if re.fullmatch(r"\\d{4}[A-Z]?", '
               'r.investee_code_or_index) else ""\n'
               '        investee_id = company_node_id(r.investee_name, investee_stock_code)\n'
               '\n'
               '        location_id = country_node_id(r.location)\n'
               '        business_id = business_node_id(r.main_business)\n'
               '\n'
               '        add_node(nodes, report_company_id, "Company", name=r.report_company_name, '
               'stock_code=r.report_stock_id, role="report_company")\n'
               '        add_node(nodes, investor_id, "Company", name=r.investor_name, stock_code=r.report_stock_id if '
               'investor_id == report_company_id else "", role="investor")\n'
               '        add_node(nodes, investee_id, "Company", name=r.investee_name, stock_code=investee_stock_code, '
               'role="investee", investee_code_or_index=r.investee_code_or_index)\n'
               '        add_node(nodes, location_id, "Location", name=r.location or "未標註")\n'
               '        add_node(nodes, business_id, "Business", name=r.main_business or "未標註")\n'
               '\n'
               '        add_edge(edges, ROOT_ID, report_company_id, "HAS_REPORT_COMPANY", edge_key=r.report_stock_id, '
               'report_stock_id=r.report_stock_id)\n'
               '\n'
               '        add_edge(\n'
               '            edges,\n'
               '            report_company_id,\n'
               '            investor_id,\n'
               '            "DISCLOSES_INVESTOR",\n'
               '            edge_key=f"{r.report_period}|{investor_id}",\n'
               '            report_period=r.report_period,\n'
               '            report_year=r.report_year,\n'
               '            report_quarter=r.report_quarter,\n'
               '            source_csv=r.source_csv,\n'
               '        )\n'
               '\n'
               '        add_edge(\n'
               '            edges,\n'
               '            investor_id,\n'
               '            investee_id,\n'
               '            "INVESTS_IN",\n'
               '            edge_key=f"{r.report_period}|{r.source_csv}|{r.source_row_index}",\n'
               '            report_stock_id=r.report_stock_id,\n'
               '            report_company_name=r.report_company_name,\n'
               '            report_period=r.report_period,\n'
               '            report_year=r.report_year,\n'
               '            report_quarter=r.report_quarter,\n'
               '            location=r.location,\n'
               '            main_business=r.main_business,\n'
               '            original_investment_end=number_to_text(r.original_investment_end),\n'
               '            original_investment_prior=number_to_text(r.original_investment_prior),\n'
               '            shares_held=number_to_text(r.shares_held),\n'
               '            ownership_percent=number_to_text(r.ownership_percent),\n'
               '            book_value=number_to_text(r.book_value),\n'
               '            investment_income_loss=number_to_text(r.investment_income_loss),\n'
               '            note=r.note,\n'
               '            source_csv=r.source_csv,\n'
               '            source_row_index=r.source_row_index,\n'
               '        )\n'
               '\n'
               '        if r.location:\n'
               '            add_edge(edges, investee_id, location_id, "LOCATED_IN", edge_key=r.location, '
               'location=r.location)\n'
               '\n'
               '        if r.main_business:\n'
               '            add_edge(edges, investee_id, business_id, "HAS_BUSINESS", edge_key=r.main_business, '
               'main_business=r.main_business)\n'
               '\n'
               '    return list(nodes.values()), list(edges.values())\n'
               '\n'
               '\n'
               '# ============================================================\n'
               '# 7. 輸出\n'
               '# ============================================================\n'
               'def write_csv(path: Path, rows: List[dict], fieldnames: List[str]) -> None:\n'
               '    path.parent.mkdir(parents=True, exist_ok=True)\n'
               '    with path.open("w", newline="", encoding="utf-8-sig") as f:\n'
               '        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")\n'
               '        writer.writeheader()\n'
               '        for row in rows:\n'
               '            writer.writerow(row)\n'
               '\n'
               '\n'
               'def write_jsonl(path: Path, rows: List[dict]) -> None:\n'
               '    path.parent.mkdir(parents=True, exist_ok=True)\n'
               '    with path.open("w", encoding="utf-8") as f:\n'
               '        for row in rows:\n'
               '            f.write(json.dumps(row, ensure_ascii=False) + "\\n")\n'
               '\n'
               '\n'
               'def write_outputs(records: List[InvestmentRecord], scan_rows: List[dict], nodes: List[dict], edges: '
               'List[dict]) -> None:\n'
               '    write_csv(OUTPUT_DIR / "scan_report.csv", scan_rows, ["stock_id", "company_name", "period", '
               '"csv_count", "target_count", "target_files"])\n'
               '\n'
               '    write_csv(\n'
               '        OUTPUT_DIR / "company_investment_table.csv",\n'
               '        [asdict(r) for r in records],\n'
               '        [\n'
               '            "report_stock_id", "report_company_name", "report_period", "report_year", '
               '"report_quarter",\n'
               '            "investor_name", "investee_name", "investee_code_or_index", "location", "main_business",\n'
               '            "original_investment_end", "original_investment_prior", "shares_held", '
               '"ownership_percent",\n'
               '            "book_value", "investment_income_loss", "note", "source_csv", "source_row_index", '
               '"raw_row_json",\n'
               '        ],\n'
               '    )\n'
               '\n'
               '    write_csv(\n'
               '        OUTPUT_DIR / "graph_nodes.csv",\n'
               '        nodes,\n'
               '        ["id", "label", "name", "stock_code", "role", "investee_code_or_index"],\n'
               '    )\n'
               '\n'
               '    write_csv(\n'
               '        OUTPUT_DIR / "graph_edges.csv",\n'
               '        edges,\n'
               '        [\n'
               '            "source", "target", "type", "report_stock_id", "report_company_name", "report_period",\n'
               '            "report_year", "report_quarter", "location", "main_business", "original_investment_end",\n'
               '            "original_investment_prior", "shares_held", "ownership_percent", "book_value",\n'
               '            "investment_income_loss", "note", "source_csv", "source_row_index",\n'
               '        ],\n'
               '    )\n'
               '\n'
               '    write_jsonl(OUTPUT_DIR / "graph_nodes.jsonl", nodes)\n'
               '    write_jsonl(OUTPUT_DIR / "graph_edges.jsonl", edges)\n'
               '\n'
               '    # Neo4j CSV\n'
               '    neo_nodes = [\n'
               '        {\n'
               '            "id:ID": n.get("id", ""),\n'
               '            ":LABEL": n.get("label", ""),\n'
               '            "name": n.get("name", ""),\n'
               '            "stock_code": n.get("stock_code", ""),\n'
               '            "role": n.get("role", ""),\n'
               '            "investee_code_or_index": n.get("investee_code_or_index", ""),\n'
               '        }\n'
               '        for n in nodes\n'
               '    ]\n'
               '\n'
               '    neo_edges = [\n'
               '        {\n'
               '            ":START_ID": e.get("source", ""),\n'
               '            ":END_ID": e.get("target", ""),\n'
               '            ":TYPE": e.get("type", ""),\n'
               '            "report_stock_id": e.get("report_stock_id", ""),\n'
               '            "report_company_name": e.get("report_company_name", ""),\n'
               '            "report_period": e.get("report_period", ""),\n'
               '            "report_year": e.get("report_year", ""),\n'
               '            "report_quarter": e.get("report_quarter", ""),\n'
               '            "location": e.get("location", ""),\n'
               '            "main_business": e.get("main_business", ""),\n'
               '            "original_investment_end": e.get("original_investment_end", ""),\n'
               '            "original_investment_prior": e.get("original_investment_prior", ""),\n'
               '            "shares_held": e.get("shares_held", ""),\n'
               '            "ownership_percent": e.get("ownership_percent", ""),\n'
               '            "book_value": e.get("book_value", ""),\n'
               '            "investment_income_loss": e.get("investment_income_loss", ""),\n'
               '            "note": e.get("note", ""),\n'
               '            "source_csv": e.get("source_csv", ""),\n'
               '            "source_row_index": e.get("source_row_index", ""),\n'
               '        }\n'
               '        for e in edges\n'
               '    ]\n'
               '\n'
               '    write_csv(OUTPUT_DIR / "neo4j_nodes.csv", neo_nodes, ["id:ID", ":LABEL", "name", "stock_code", '
               '"role", "investee_code_or_index"])\n'
               '    write_csv(\n'
               '        OUTPUT_DIR / "neo4j_relationships.csv",\n'
               '        neo_edges,\n'
               '        [\n'
               '            ":START_ID", ":END_ID", ":TYPE", "report_stock_id", "report_company_name", '
               '"report_period",\n'
               '            "report_year", "report_quarter", "location", "main_business", "original_investment_end",\n'
               '            "original_investment_prior", "shares_held", "ownership_percent", "book_value",\n'
               '            "investment_income_loss", "note", "source_csv", "source_row_index",\n'
               '        ],\n'
               '    )\n'
               '\n'
               '\n'
               'def try_write_pyvis_html(nodes: List[dict], edges: List[dict]) -> None:\n'
               '    if not WRITE_HTML_GRAPH:\n'
               '        return\n'
               '    try:\n'
               '        from pyvis.network import Network\n'
               '    except Exception:\n'
               '        print("ℹ️ 未安裝 pyvis，略過 HTML 圖譜。若需要可執行：pip install pyvis")\n'
               '        return\n'
               '\n'
               '    color_map = {\n'
               '        "InvestmentNetwork": "#EAECEE",\n'
               '        "Company": "#F9E79F",\n'
               '        "Location": "#AED6F1",\n'
               '        "Business": "#A9DFBF",\n'
               '    }\n'
               '\n'
               '    net = Network(height="900px", width="100%", directed=True, notebook=False)\n'
               '    net.toggle_physics(True)\n'
               '\n'
               '    for n in nodes:\n'
               '        label = n.get("label", "")\n'
               '        display = n.get("name", n.get("id", ""))\n'
               '        if label == "Company" and n.get("stock_code"):\n'
               '            display = f"{n.get(\'stock_code\')} {display}"\n'
               '        title = "<br>".join(f"{k}: {v}" for k, v in n.items() if v not in ["", None])\n'
               '        net.add_node(\n'
               '            n["id"],\n'
               '            label=display,\n'
               '            title=title,\n'
               '            color=color_map.get(label, "#D5DBDB"),\n'
               '            shape="dot" if label == "Company" else "box",\n'
               '        )\n'
               '\n'
               '    for e in edges:\n'
               '        title = "<br>".join(f"{k}: {v}" for k, v in e.items() if v not in ["", None])\n'
               '        net.add_edge(e["source"], e["target"], label=e.get("type", ""), title=title)\n'
               '\n'
               '    net.write_html(str(OUTPUT_DIR / "investment_graph.html"))\n'
               '\n'
               '\n'
               '# ============================================================\n'
               '# 8. 主程式\n'
               '# ============================================================\n'
               'def main() -> None:\n'
               '    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)\n'
               '\n'
               '    records, scan_rows = parse_all_investment_tables(INPUT_DIR)\n'
               '\n'
               '    # 即使沒有 records，也先輸出 scan_report，方便檢查哪些公司沒掃到表。\n'
               '    if not records:\n'
               '        write_csv(OUTPUT_DIR / "scan_report.csv", scan_rows, ["stock_id", "company_name", "period", '
               '"csv_count", "target_count", "target_files"])\n'
               '        print("⚠️ 沒有解析到任何投資關係資料。已輸出 scan_report.csv。")\n'
               '        return\n'
               '\n'
               '    nodes, edges = build_graph(records)\n'
               '    write_outputs(records, scan_rows, nodes, edges)\n'
               '    try_write_pyvis_html(nodes, edges)\n'
               '\n'
               '    report_company_count = len({r.report_stock_id for r in records})\n'
               '    investor_count = len({normalize_company_key(r.investor_name) for r in records})\n'
               '    investee_count = len({normalize_company_key(r.investee_name) for r in records})\n'
               '    companies_with_target = sum(1 for r in scan_rows if int(r["target_count"]) > 0)\n'
               '\n'
               '    print("\\n✅ 被投資公司關係圖譜建立完成")\n'
               '    print(f"輸入資料夾：{INPUT_DIR.resolve()}")\n'
               '    print(f"輸出資料夾：{OUTPUT_DIR.resolve()}")\n'
               '    print(f"公司/季度組合數：{len(scan_rows)}")\n'
               '    print(f"有目標表的公司/季度組合數：{companies_with_target}")\n'
               '    print(f"申報公司數：{report_company_count}")\n'
               '    print(f"投資公司數：{investor_count}")\n'
               '    print(f"被投資公司數：{investee_count}")\n'
               '    print(f"投資關係筆數：{len(records)}")\n'
               '    print(f"節點數：{len(nodes)}")\n'
               '    print(f"關係數：{len(edges)}")\n'
               '    print("\\n主要輸出：")\n'
               '    print(f"- {OUTPUT_DIR / \'scan_report.csv\'}")\n'
               '    print(f"- {OUTPUT_DIR / \'company_investment_table.csv\'}")\n'
               '    print(f"- {OUTPUT_DIR / \'neo4j_nodes.csv\'}")\n'
               '    print(f"- {OUTPUT_DIR / \'neo4j_relationships.csv\'}")\n'
               '    if (OUTPUT_DIR / "investment_graph.html").exists():\n'
               '        print(f"- {OUTPUT_DIR / \'investment_graph.html\'}")\n'
               '\n'
               '\n'
               'if __name__ == "__main__":\n'
               '    main()\n',
 'related_party': '# -*- coding: utf-8 -*-\n'
                  '"""\n'
                  'build_related_party_graph_from_reports_csv_fixed.py\n'
                  '\n'
                  '用途：\n'
                  '    掃描 reports_csv_output 底下所有公司的「關係人名稱及關係.csv」表格，\n'
                  '    將全部公司合併成同一張「關係人圖譜」。\n'
                  '\n'
                  '修正版重點：\n'
                  '    1. 只吃「檔名」明確為關係人名稱及關係的 CSV。\n'
                  '       不再用寬鬆內容比對，避免把「關係人交易」、「營業收入」、「應收帳款」等表誤吃進圖譜。\n'
                  '    2. 解析時只取前兩欄：\n'
                  '       A 欄 = 關係人名稱\n'
                  '       B 欄 = 與合併公司之關係\n'
                  '    3. 會輸出 rejected_files.csv，方便檢查哪些關係人相關表被排除。\n'
                  '\n'
                  '資料來源範例：\n'
                  '    reports_csv_output/\n'
                  '      2408_南亞科技/\n'
                  '        114Q2/\n'
                  '          2408_114Q2_關係人名稱及關係.csv\n'
                  '\n'
                  '輸出：\n'
                  '    related_party_graph_output/\n'
                  '      scan_report.csv\n'
                  '      rejected_files.csv\n'
                  '      related_party_table.csv\n'
                  '      graph_nodes.csv\n'
                  '      graph_edges.csv\n'
                  '      neo4j_nodes.csv\n'
                  '      neo4j_relationships.csv\n'
                  '      related_party_graph.html\n'
                  '\n'
                  '執行：\n'
                  '    python3 build_related_party_graph_from_reports_csv_fixed.py\n'
                  '"""\n'
                  '\n'
                  'from __future__ import annotations\n'
                  '\n'
                  'import csv\n'
                  'import hashlib\n'
                  'import json\n'
                  'import re\n'
                  'from dataclasses import dataclass, asdict\n'
                  'from pathlib import Path\n'
                  'from typing import Dict, List, Tuple\n'
                  '\n'
                  'import pandas as pd\n'
                  '\n'
                  '\n'
                  '# ============================================================\n'
                  '# 1. 設定區\n'
                  '# ============================================================\n'
                  'INPUT_DIR = Path("./reports_csv_output")\n'
                  'OUTPUT_DIR = Path("./related_party_graph_output")\n'
                  '\n'
                  'ROOT_ID = "related_party_network:all_companies"\n'
                  'ROOT_NAME = "全部公司關係人合併圖譜"\n'
                  '\n'
                  'ENCODING_CANDIDATES = ["utf-8-sig", "utf-8", "cp950", "big5"]\n'
                  '\n'
                  '# 空集合 = 全部公司\n'
                  'TEST_STOCK_IDS = set()\n'
                  '# TEST_STOCK_IDS = {"2408"}\n'
                  '\n'
                  '# 空集合 = 全部季度\n'
                  'TEST_PERIODS = set()\n'
                  '# TEST_PERIODS = {"114Q2"}\n'
                  '\n'
                  'WRITE_HTML_GRAPH = True\n'
                  '\n'
                  '# 嚴格目標檔名。避免誤吃：\n'
                  '# - 關係人交易.csv\n'
                  '# - 關係人交易明細.csv\n'
                  '# - 應收帳款與關係人.csv\n'
                  'STRICT_TARGET_PHRASES = [\n'
                  '    "關係人名稱及關係",\n'
                  '    "關係人名稱關係",\n'
                  ']\n'
                  '\n'
                  '# 明確排除的檔名關鍵字\n'
                  'EXCLUDE_FILENAME_KEYWORDS = [\n'
                  '    "關係人交易",\n'
                  '    "重大交易",\n'
                  '    "交易",\n'
                  '    "應收",\n'
                  '    "應付",\n'
                  '    "營業收入",\n'
                  '    "收入",\n'
                  '    "進貨",\n'
                  '    "費用",\n'
                  '    "款項",\n'
                  '    "餘額",\n'
                  '    "明細",\n'
                  ']\n'
                  '\n'
                  '\n'
                  '# ============================================================\n'
                  '# 2. 資料結構\n'
                  '# ============================================================\n'
                  '@dataclass\n'
                  'class RelatedPartyRecord:\n'
                  '    report_stock_id: str\n'
                  '    report_company_name: str\n'
                  '    report_period: str\n'
                  '    report_year: int\n'
                  '    report_quarter: int\n'
                  '\n'
                  '    related_party_name: str\n'
                  '    relationship_desc: str\n'
                  '    relation_category: str\n'
                  '\n'
                  '    source_csv: str\n'
                  '    source_row_index: int\n'
                  '    raw_row_json: str\n'
                  '\n'
                  '\n'
                  '# ============================================================\n'
                  '# 3. 基礎工具\n'
                  '# ============================================================\n'
                  'def clean_text(value) -> str:\n'
                  '    if value is None:\n'
                  '        return ""\n'
                  '\n'
                  '    text = str(value)\n'
                  '    text = text.replace("\\xa0", " ").replace("\\u3000", " ")\n'
                  '    text = text.replace("\\r", " ").replace("\\n", " ")\n'
                  '    text = re.sub(r"\\s+", " ", text).strip()\n'
                  '\n'
                  '    if text.lower() in {"nan", "none"}:\n'
                  '        return ""\n'
                  '\n'
                  '    return text\n'
                  '\n'
                  '\n'
                  'def normalize_for_match(text: str) -> str:\n'
                  '    text = clean_text(text)\n'
                  '    text = text.replace("…", "").replace("...", "")\n'
                  '    text = re.sub(r"[\\s_、，,。．.（）()【】\\[\\]-]+", "", text)\n'
                  '    return text\n'
                  '\n'
                  '\n'
                  'def read_csv_with_fallback(path: Path, header=None, nrows=None) -> pd.DataFrame:\n'
                  '    last_error = None\n'
                  '\n'
                  '    for enc in ENCODING_CANDIDATES:\n'
                  '        try:\n'
                  '            return pd.read_csv(path, encoding=enc, header=header, dtype=str, '
                  'nrows=nrows).fillna("")\n'
                  '        except UnicodeDecodeError as e:\n'
                  '            last_error = e\n'
                  '            continue\n'
                  '\n'
                  '    raise UnicodeDecodeError(\n'
                  '        "unknown", b"", 0, 1,\n'
                  '        f"無法用這些編碼讀取：{ENCODING_CANDIDATES}。最後錯誤：{last_error}"\n'
                  '    )\n'
                  '\n'
                  '\n'
                  'def safe_id(text: str) -> str:\n'
                  '    s = clean_text(text).lower()\n'
                  '    s = re.sub(r"\\s+", "_", s)\n'
                  '    s = re.sub(r"[^0-9a-zA-Z_\\u4e00-\\u9fff:-]", "_", s)\n'
                  '    s = re.sub(r"_+", "_", s).strip("_")\n'
                  '\n'
                  '    if not s:\n'
                  '        s = hashlib.md5(str(text).encode("utf-8")).hexdigest()[:12]\n'
                  '\n'
                  '    return s\n'
                  '\n'
                  '\n'
                  'def normalize_party_key(name: str) -> str:\n'
                  '    """\n'
                  '    關係人名稱正規化。\n'
                  '    用於將不同公司中出現的同一個關係人合併成同一個節點。\n'
                  '    """\n'
                  '    s = clean_text(name)\n'
                  '    s_upper = s.upper()\n'
                  '\n'
                  '    suffixes = [\n'
                  '        "股份有限公司及其子公司",\n'
                  '        "股份有限公司及子公司",\n'
                  '        "股份有限公司",\n'
                  '        "有限公司",\n'
                  '        "(股)公司",\n'
                  '        "（股）公司",\n'
                  '        "公司",\n'
                  '        "CORPORATION",\n'
                  '        "CORP.",\n'
                  '        "CORP",\n'
                  '        "LTD.",\n'
                  '        "LTD",\n'
                  '        "LIMITED",\n'
                  '    ]\n'
                  '\n'
                  '    for suf in suffixes:\n'
                  '        s = s.replace(suf, "")\n'
                  '        s_upper = s_upper.replace(suf, "")\n'
                  '\n'
                  '    if re.search(r"[A-Za-z]", s_upper):\n'
                  '        s = s_upper\n'
                  '\n'
                  '    s = re.sub(r"[\\s\\-_()（）.,，。]", "", s)\n'
                  '    return s.strip()\n'
                  '\n'
                  '\n'
                  'def company_node_id(company_name: str, stock_code: str = "") -> str:\n'
                  '    stock_code = clean_text(stock_code)\n'
                  '\n'
                  '    if re.fullmatch(r"\\d{4}[A-Z]?", stock_code):\n'
                  '        return f"company:{stock_code}"\n'
                  '\n'
                  '    return f"company_name:{safe_id(normalize_party_key(company_name) or company_name)}"\n'
                  '\n'
                  '\n'
                  'def related_party_node_id(name: str) -> str:\n'
                  '    return f"related_party:{safe_id(normalize_party_key(name) or name)}"\n'
                  '\n'
                  '\n'
                  'def relation_type_node_id(relation_category: str) -> str:\n'
                  '    return f"relation_type:{safe_id(relation_category or \'未分類\')}"\n'
                  '\n'
                  '\n'
                  'def roc_year_to_ad(year: int) -> int:\n'
                  '    return year + 1911 if 1 <= year < 1911 else year\n'
                  '\n'
                  '\n'
                  'def parse_period_folder(period_folder: str) -> Tuple[int, int]:\n'
                  '    text = str(period_folder).upper()\n'
                  '    match = re.search(r"(\\d{3,4})Q([1-4])", text)\n'
                  '\n'
                  '    if not match:\n'
                  '        return 0, 0\n'
                  '\n'
                  '    year = roc_year_to_ad(int(match.group(1)))\n'
                  '    quarter = int(match.group(2))\n'
                  '\n'
                  '    return year, quarter\n'
                  '\n'
                  '\n'
                  'def parse_stock_folder(stock_folder_name: str) -> Tuple[str, str]:\n'
                  '    parts = str(stock_folder_name).split("_")\n'
                  '\n'
                  '    stock_id = parts[0] if len(parts) >= 1 else "Unknown"\n'
                  '    company_name = parts[1] if len(parts) >= 2 else f"公司{stock_id}"\n'
                  '\n'
                  '    return stock_id, company_name\n'
                  '\n'
                  '\n'
                  'def classify_relationship(relationship_desc: str) -> str:\n'
                  '    """\n'
                  '    將原始關係文字粗略分類。\n'
                  '    原文仍保留在 relationship_desc 屬性中。\n'
                  '    """\n'
                  '    text = clean_text(relationship_desc)\n'
                  '\n'
                  '    if not text:\n'
                  '        return "未標註"\n'
                  '\n'
                  '    rules = [\n'
                  '        ("母公司", ["母公司", "最終母公司"]),\n'
                  '        ("子公司", ["子公司"]),\n'
                  '        ("關聯企業", ["關聯企業", "採用權益法"]),\n'
                  '        ("合資", ["合資"]),\n'
                  '        ("主要管理階層", ["主要管理階層", "董事", "監察人", "經理人"]),\n'
                  '        ("具重大影響力", ["重大影響"]),\n'
                  '        ("其他關係人", ["其他關係人", "其他關係"]),\n'
                  '        ("實質關係人", ["實質關係"]),\n'
                  '    ]\n'
                  '\n'
                  '    for category, keywords in rules:\n'
                  '        if any(k in text for k in keywords):\n'
                  '            return category\n'
                  '\n'
                  '    return text[:40]\n'
                  '\n'
                  '\n'
                  '# ============================================================\n'
                  '# 4. 掃描目標 CSV\n'
                  '# ============================================================\n'
                  'def is_strict_target_related_party_csv(path: Path) -> Tuple[bool, str]:\n'
                  '    """\n'
                  '    只允許明確檔名為「關係人名稱及關係」的 CSV。\n'
                  '    回傳：\n'
                  '      (是否採用, 原因)\n'
                  '    """\n'
                  '    if path.suffix.lower() != ".csv":\n'
                  '        return False, "not_csv"\n'
                  '\n'
                  '    name_norm = normalize_for_match(path.stem)\n'
                  '\n'
                  '    if any(normalize_for_match(k) in name_norm for k in EXCLUDE_FILENAME_KEYWORDS):\n'
                  '        return False, "excluded_keyword"\n'
                  '\n'
                  '    if any(normalize_for_match(k) in name_norm for k in STRICT_TARGET_PHRASES):\n'
                  '        return True, "strict_filename_match"\n'
                  '\n'
                  '    return False, "not_target_filename"\n'
                  '\n'
                  '\n'
                  'def iter_company_period_dirs(input_dir: Path):\n'
                  '    for company_dir in sorted(p for p in input_dir.iterdir() if p.is_dir()):\n'
                  '        stock_id = company_dir.name.split("_")[0]\n'
                  '\n'
                  '        if TEST_STOCK_IDS and stock_id not in TEST_STOCK_IDS:\n'
                  '            continue\n'
                  '\n'
                  '        for period_dir in sorted(p for p in company_dir.iterdir() if p.is_dir()):\n'
                  '            if TEST_PERIODS and period_dir.name not in TEST_PERIODS:\n'
                  '                continue\n'
                  '            yield company_dir, period_dir\n'
                  '\n'
                  '\n'
                  'def scan_target_csv_files(input_dir: Path) -> Tuple[List[Path], List[dict], List[dict]]:\n'
                  '    if not input_dir.exists():\n'
                  '        raise FileNotFoundError(f"找不到輸入資料夾：{input_dir.resolve()}")\n'
                  '\n'
                  '    target_files: List[Path] = []\n'
                  '    scan_rows: List[dict] = []\n'
                  '    rejected_rows: List[dict] = []\n'
                  '\n'
                  '    for company_dir, period_dir in iter_company_period_dirs(input_dir):\n'
                  '        stock_id, company_name = parse_stock_folder(company_dir.name)\n'
                  '        csv_files = sorted(period_dir.glob("*.csv"))\n'
                  '\n'
                  '        matched = []\n'
                  '        for csv_file in csv_files:\n'
                  '            ok, reason = is_strict_target_related_party_csv(csv_file)\n'
                  '\n'
                  '            if ok:\n'
                  '                matched.append(csv_file)\n'
                  '                target_files.append(csv_file)\n'
                  '            else:\n'
                  '                # 只記錄名稱中含「關係」的被排除檔案，避免 rejected 太大。\n'
                  '                if "關係" in csv_file.name:\n'
                  '                    rejected_rows.append({\n'
                  '                        "stock_id": stock_id,\n'
                  '                        "company_name": company_name,\n'
                  '                        "period": period_dir.name,\n'
                  '                        "csv_file": csv_file.name,\n'
                  '                        "reason": reason,\n'
                  '                    })\n'
                  '\n'
                  '        scan_rows.append({\n'
                  '            "stock_id": stock_id,\n'
                  '            "company_name": company_name,\n'
                  '            "period": period_dir.name,\n'
                  '            "csv_count": len(csv_files),\n'
                  '            "target_count": len(matched),\n'
                  '            "target_files": ";".join(p.name for p in matched),\n'
                  '        })\n'
                  '\n'
                  '    return target_files, scan_rows, rejected_rows\n'
                  '\n'
                  '\n'
                  '# ============================================================\n'
                  '# 5. 關係人表解析\n'
                  '# ============================================================\n'
                  'def looks_like_header_row(values: List[str]) -> bool:\n'
                  '    joined = "".join(values)\n'
                  '    header_keywords = ["關係人名稱", "與合併公司之關係", "與公司之關係"]\n'
                  '    return any(k in joined for k in header_keywords)\n'
                  '\n'
                  '\n'
                  'def is_bad_related_party_name(name: str) -> bool:\n'
                  '    """\n'
                  '    避免把說明列、註解列、表頭列、科目列誤當關係人名稱。\n'
                  '    例如「說明｜註：...」這類 row 只應保留在來源 CSV，不應建立 RelatedParty 節點。\n'
                  '    """\n'
                  '    text = clean_text(name)\n'
                  '    text_norm = normalize_for_match(text)\n'
                  '\n'
                  '    bad_exact = {\n'
                  '        "",\n'
                  '        "項目",\n'
                  '        "名稱",\n'
                  '        "說明",\n'
                  '        "註",\n'
                  '        "註一",\n'
                  '        "註二",\n'
                  '        "附註",\n'
                  '        "備註",\n'
                  '        "其他說明",\n'
                  '        "關係人名稱",\n'
                  '        "與合併公司之關係",\n'
                  '        "與公司之關係",\n'
                  '        "營業收入",\n'
                  '        "應收帳款",\n'
                  '        "應付帳款",\n'
                  '        "進貨",\n'
                  '        "費用",\n'
                  '        "其他收入",\n'
                  '        "合計",\n'
                  '        "總計",\n'
                  '    }\n'
                  '\n'
                  '    bad_exact_norm = {normalize_for_match(x) for x in bad_exact}\n'
                  '    if text in bad_exact or text_norm in bad_exact_norm:\n'
                  '        return True\n'
                  '\n'
                  '    bad_prefixes = [\n'
                  '        "說明",\n'
                  '        "註：",\n'
                  '        "註:",\n'
                  '        "註一",\n'
                  '        "註二",\n'
                  '        "附註",\n'
                  '        "備註",\n'
                  '        "本公司",\n'
                  '        "合併公司",\n'
                  '        "本集團",\n'
                  '        "係指",\n'
                  '    ]\n'
                  '    if any(text.startswith(p) for p in bad_prefixes):\n'
                  '        return True\n'
                  '\n'
                  '    return False\n'
                  '\n'
                  '\n'
                  'def is_note_like_relationship_text(rel: str) -> bool:\n'
                  '    """\n'
                  '    第二欄若是長篇註解，不應拿來當 relationship_desc 建關係。\n'
                  '    正常 relationship_desc 通常是「子公司」「關聯企業」「其他關係人」等短詞。\n'
                  '    """\n'
                  '    rel = clean_text(rel)\n'
                  '    if not rel:\n'
                  '        return True\n'
                  '\n'
                  '    note_prefixes = ["註：", "註:", "註一", "註二", "說明", "附註", "備註"]\n'
                  '    if any(rel.startswith(p) for p in note_prefixes):\n'
                  '        return True\n'
                  '\n'
                  '    # 太長且含敘述性標點，通常是附註，不是關係類型。\n'
                  '    if len(rel) > 80 and any(x in rel for x in ["。", "，", "；", "民國", "請參閱"]):\n'
                  '        return True\n'
                  '\n'
                  '    return False\n'
                  '\n'
                  '\n'
                  'def is_valid_related_party_row(name: str, rel: str) -> bool:\n'
                  '    name = clean_text(name)\n'
                  '    rel = clean_text(rel)\n'
                  '\n'
                  '    if not name:\n'
                  '        return False\n'
                  '\n'
                  '    if looks_like_header_row([name, rel]):\n'
                  '        return False\n'
                  '\n'
                  '    if is_bad_related_party_name(name):\n'
                  '        return False\n'
                  '\n'
                  '    # 第二欄若完全空白或是長篇註解，不能當關係人關係列。\n'
                  '    if is_note_like_relationship_text(rel):\n'
                  '        return False\n'
                  '\n'
                  '    if len(name) > 80:\n'
                  '        return False\n'
                  '\n'
                  '    return True\n'
                  '\n'
                  '\n'
                  'def parse_related_party_csv(csv_file: Path) -> List[RelatedPartyRecord]:\n'
                  '    """\n'
                  '    解析單一「關係人名稱及關係.csv」。\n'
                  '\n'
                  '    只取前兩欄：\n'
                  '      第 1 欄：關係人名稱\n'
                  '      第 2 欄：與合併公司之關係\n'
                  '    """\n'
                  '    period_folder = csv_file.parent.name\n'
                  '    stock_folder = csv_file.parent.parent.name\n'
                  '\n'
                  '    report_stock_id, report_company_name = parse_stock_folder(stock_folder)\n'
                  '    report_year, report_quarter = parse_period_folder(period_folder)\n'
                  '\n'
                  '    df = read_csv_with_fallback(csv_file, header=None)\n'
                  '    records: List[RelatedPartyRecord] = []\n'
                  '\n'
                  '    for row_idx, row in df.iterrows():\n'
                  '        row_values = [clean_text(v) for v in row.tolist()]\n'
                  '\n'
                  '        if not any(row_values):\n'
                  '            continue\n'
                  '\n'
                  '        name = row_values[0] if len(row_values) >= 1 else ""\n'
                  '        rel = row_values[1] if len(row_values) >= 2 else ""\n'
                  '\n'
                  '        if not is_valid_related_party_row(name, rel):\n'
                  '            continue\n'
                  '\n'
                  '        relation_category = classify_relationship(rel)\n'
                  '\n'
                  '        row_dict = {\n'
                  '            "related_party_name": name,\n'
                  '            "relationship_desc": rel,\n'
                  '        }\n'
                  '\n'
                  '        records.append(\n'
                  '            RelatedPartyRecord(\n'
                  '                report_stock_id=report_stock_id,\n'
                  '                report_company_name=report_company_name,\n'
                  '                report_period=period_folder,\n'
                  '                report_year=report_year,\n'
                  '                report_quarter=report_quarter,\n'
                  '                related_party_name=name,\n'
                  '                relationship_desc=rel,\n'
                  '                relation_category=relation_category,\n'
                  '                source_csv=str(csv_file),\n'
                  '                source_row_index=int(row_idx),\n'
                  '                raw_row_json=json.dumps(row_dict, ensure_ascii=False),\n'
                  '            )\n'
                  '        )\n'
                  '\n'
                  '    return records\n'
                  '\n'
                  '\n'
                  'def parse_all_related_party_tables(input_dir: Path) -> Tuple[List[RelatedPartyRecord], List[dict], '
                  'List[dict]]:\n'
                  '    target_files, scan_rows, rejected_rows = scan_target_csv_files(input_dir)\n'
                  '\n'
                  '    print(f"掃描公司/季度組合：{len(scan_rows)}")\n'
                  '    print(f"找到嚴格目標關係人表 CSV：{len(target_files)} 個")\n'
                  '\n'
                  '    all_records: List[RelatedPartyRecord] = []\n'
                  '\n'
                  '    for csv_file in target_files:\n'
                  '        try:\n'
                  '            records = parse_related_party_csv(csv_file)\n'
                  '            all_records.extend(records)\n'
                  '            print(f"[OK] {csv_file} -> {len(records)} 筆")\n'
                  '        except Exception as e:\n'
                  '            print(f"[Skip] {csv_file} -> {e}")\n'
                  '\n'
                  '    return all_records, scan_rows, rejected_rows\n'
                  '\n'
                  '\n'
                  '# ============================================================\n'
                  '# 6. 建立圖譜\n'
                  '# ============================================================\n'
                  'def add_node(nodes: Dict[str, dict], node_id: str, label: str, **props) -> None:\n'
                  '    if node_id not in nodes:\n'
                  '        nodes[node_id] = {"id": node_id, "label": label, **props}\n'
                  '        return\n'
                  '\n'
                  '    for k, v in props.items():\n'
                  '        if v in ["", None]:\n'
                  '            continue\n'
                  '        if k not in nodes[node_id] or nodes[node_id][k] in ["", None, "未標註", "未分類"]:\n'
                  '            nodes[node_id][k] = v\n'
                  '\n'
                  '\n'
                  'def add_edge(\n'
                  '    edges: Dict[Tuple[str, str, str, str], dict],\n'
                  '    source: str,\n'
                  '    target: str,\n'
                  '    edge_type: str,\n'
                  '    edge_key: str = "",\n'
                  '    **props\n'
                  ') -> None:\n'
                  '    key = (source, target, edge_type, edge_key)\n'
                  '\n'
                  '    if key not in edges:\n'
                  '        edges[key] = {"source": source, "target": target, "type": edge_type, **props}\n'
                  '        return\n'
                  '\n'
                  '    for field in ["source_csv", "source_row_index"]:\n'
                  '        if field in props:\n'
                  '            old = str(edges[key].get(field, ""))\n'
                  '            new = str(props[field])\n'
                  '            if new and new not in old.split(";"):\n'
                  '                edges[key][field] = f"{old};{new}" if old else new\n'
                  '\n'
                  '\n'
                  'def build_graph(records: List[RelatedPartyRecord]) -> Tuple[List[dict], List[dict]]:\n'
                  '    nodes: Dict[str, dict] = {}\n'
                  '    edges: Dict[Tuple[str, str, str, str], dict] = {}\n'
                  '\n'
                  '    add_node(nodes, ROOT_ID, "RelatedPartyNetwork", name=ROOT_NAME)\n'
                  '\n'
                  '    for r in records:\n'
                  '        report_company_id = company_node_id(r.report_company_name, r.report_stock_id)\n'
                  '        related_party_id = related_party_node_id(r.related_party_name)\n'
                  '        relation_type_id = relation_type_node_id(r.relation_category)\n'
                  '\n'
                  '        add_node(\n'
                  '            nodes,\n'
                  '            report_company_id,\n'
                  '            "Company",\n'
                  '            name=r.report_company_name,\n'
                  '            stock_code=r.report_stock_id,\n'
                  '            role="report_company",\n'
                  '        )\n'
                  '\n'
                  '        add_node(\n'
                  '            nodes,\n'
                  '            related_party_id,\n'
                  '            "RelatedParty",\n'
                  '            name=r.related_party_name,\n'
                  '            normalized_name=normalize_party_key(r.related_party_name),\n'
                  '        )\n'
                  '\n'
                  '        add_node(\n'
                  '            nodes,\n'
                  '            relation_type_id,\n'
                  '            "RelationType",\n'
                  '            name=r.relation_category,\n'
                  '        )\n'
                  '\n'
                  '        add_edge(\n'
                  '            edges,\n'
                  '            ROOT_ID,\n'
                  '            report_company_id,\n'
                  '            "HAS_REPORT_COMPANY",\n'
                  '            edge_key=r.report_stock_id,\n'
                  '            report_stock_id=r.report_stock_id,\n'
                  '        )\n'
                  '\n'
                  '        add_edge(\n'
                  '            edges,\n'
                  '            report_company_id,\n'
                  '            related_party_id,\n'
                  '            "HAS_RELATED_PARTY",\n'
                  '            edge_key=f"{r.report_period}|{r.source_csv}|{r.source_row_index}",\n'
                  '            report_stock_id=r.report_stock_id,\n'
                  '            report_company_name=r.report_company_name,\n'
                  '            report_period=r.report_period,\n'
                  '            report_year=r.report_year,\n'
                  '            report_quarter=r.report_quarter,\n'
                  '            relationship_desc=r.relationship_desc,\n'
                  '            relation_category=r.relation_category,\n'
                  '            source_csv=r.source_csv,\n'
                  '            source_row_index=r.source_row_index,\n'
                  '        )\n'
                  '\n'
                  '        add_edge(\n'
                  '            edges,\n'
                  '            related_party_id,\n'
                  '            relation_type_id,\n'
                  '            "HAS_RELATION_TYPE",\n'
                  '            edge_key=r.relation_category,\n'
                  '            relation_category=r.relation_category,\n'
                  '        )\n'
                  '\n'
                  '    return list(nodes.values()), list(edges.values())\n'
                  '\n'
                  '\n'
                  '# ============================================================\n'
                  '# 7. 輸出\n'
                  '# ============================================================\n'
                  'def write_csv(path: Path, rows: List[dict], fieldnames: List[str]) -> None:\n'
                  '    path.parent.mkdir(parents=True, exist_ok=True)\n'
                  '\n'
                  '    with path.open("w", newline="", encoding="utf-8-sig") as f:\n'
                  '        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")\n'
                  '        writer.writeheader()\n'
                  '        for row in rows:\n'
                  '            writer.writerow(row)\n'
                  '\n'
                  '\n'
                  'def write_jsonl(path: Path, rows: List[dict]) -> None:\n'
                  '    path.parent.mkdir(parents=True, exist_ok=True)\n'
                  '\n'
                  '    with path.open("w", encoding="utf-8") as f:\n'
                  '        for row in rows:\n'
                  '            f.write(json.dumps(row, ensure_ascii=False) + "\\n")\n'
                  '\n'
                  '\n'
                  'def write_outputs(\n'
                  '    records: List[RelatedPartyRecord],\n'
                  '    scan_rows: List[dict],\n'
                  '    rejected_rows: List[dict],\n'
                  '    nodes: List[dict],\n'
                  '    edges: List[dict],\n'
                  ') -> None:\n'
                  '    write_csv(\n'
                  '        OUTPUT_DIR / "scan_report.csv",\n'
                  '        scan_rows,\n'
                  '        ["stock_id", "company_name", "period", "csv_count", "target_count", "target_files"],\n'
                  '    )\n'
                  '\n'
                  '    write_csv(\n'
                  '        OUTPUT_DIR / "rejected_files.csv",\n'
                  '        rejected_rows,\n'
                  '        ["stock_id", "company_name", "period", "csv_file", "reason"],\n'
                  '    )\n'
                  '\n'
                  '    write_csv(\n'
                  '        OUTPUT_DIR / "related_party_table.csv",\n'
                  '        [asdict(r) for r in records],\n'
                  '        [\n'
                  '            "report_stock_id",\n'
                  '            "report_company_name",\n'
                  '            "report_period",\n'
                  '            "report_year",\n'
                  '            "report_quarter",\n'
                  '            "related_party_name",\n'
                  '            "relationship_desc",\n'
                  '            "relation_category",\n'
                  '            "source_csv",\n'
                  '            "source_row_index",\n'
                  '            "raw_row_json",\n'
                  '        ],\n'
                  '    )\n'
                  '\n'
                  '    write_csv(\n'
                  '        OUTPUT_DIR / "graph_nodes.csv",\n'
                  '        nodes,\n'
                  '        ["id", "label", "name", "stock_code", "role", "normalized_name"],\n'
                  '    )\n'
                  '\n'
                  '    write_csv(\n'
                  '        OUTPUT_DIR / "graph_edges.csv",\n'
                  '        edges,\n'
                  '        [\n'
                  '            "source",\n'
                  '            "target",\n'
                  '            "type",\n'
                  '            "report_stock_id",\n'
                  '            "report_company_name",\n'
                  '            "report_period",\n'
                  '            "report_year",\n'
                  '            "report_quarter",\n'
                  '            "relationship_desc",\n'
                  '            "relation_category",\n'
                  '            "source_csv",\n'
                  '            "source_row_index",\n'
                  '        ],\n'
                  '    )\n'
                  '\n'
                  '    write_jsonl(OUTPUT_DIR / "graph_nodes.jsonl", nodes)\n'
                  '    write_jsonl(OUTPUT_DIR / "graph_edges.jsonl", edges)\n'
                  '\n'
                  '    neo_nodes = [\n'
                  '        {\n'
                  '            "id:ID": n.get("id", ""),\n'
                  '            ":LABEL": n.get("label", ""),\n'
                  '            "name": n.get("name", ""),\n'
                  '            "stock_code": n.get("stock_code", ""),\n'
                  '            "role": n.get("role", ""),\n'
                  '            "normalized_name": n.get("normalized_name", ""),\n'
                  '        }\n'
                  '        for n in nodes\n'
                  '    ]\n'
                  '\n'
                  '    neo_edges = [\n'
                  '        {\n'
                  '            ":START_ID": e.get("source", ""),\n'
                  '            ":END_ID": e.get("target", ""),\n'
                  '            ":TYPE": e.get("type", ""),\n'
                  '            "report_stock_id": e.get("report_stock_id", ""),\n'
                  '            "report_company_name": e.get("report_company_name", ""),\n'
                  '            "report_period": e.get("report_period", ""),\n'
                  '            "report_year": e.get("report_year", ""),\n'
                  '            "report_quarter": e.get("report_quarter", ""),\n'
                  '            "relationship_desc": e.get("relationship_desc", ""),\n'
                  '            "relation_category": e.get("relation_category", ""),\n'
                  '            "source_csv": e.get("source_csv", ""),\n'
                  '            "source_row_index": e.get("source_row_index", ""),\n'
                  '        }\n'
                  '        for e in edges\n'
                  '    ]\n'
                  '\n'
                  '    write_csv(\n'
                  '        OUTPUT_DIR / "neo4j_nodes.csv",\n'
                  '        neo_nodes,\n'
                  '        ["id:ID", ":LABEL", "name", "stock_code", "role", "normalized_name"],\n'
                  '    )\n'
                  '\n'
                  '    write_csv(\n'
                  '        OUTPUT_DIR / "neo4j_relationships.csv",\n'
                  '        neo_edges,\n'
                  '        [\n'
                  '            ":START_ID",\n'
                  '            ":END_ID",\n'
                  '            ":TYPE",\n'
                  '            "report_stock_id",\n'
                  '            "report_company_name",\n'
                  '            "report_period",\n'
                  '            "report_year",\n'
                  '            "report_quarter",\n'
                  '            "relationship_desc",\n'
                  '            "relation_category",\n'
                  '            "source_csv",\n'
                  '            "source_row_index",\n'
                  '        ],\n'
                  '    )\n'
                  '\n'
                  '\n'
                  'def try_write_pyvis_html(nodes: List[dict], edges: List[dict]) -> None:\n'
                  '    if not WRITE_HTML_GRAPH:\n'
                  '        return\n'
                  '\n'
                  '    try:\n'
                  '        from pyvis.network import Network\n'
                  '    except Exception:\n'
                  '        print("ℹ️ 未安裝 pyvis，略過 HTML 圖譜。若需要可執行：pip install pyvis")\n'
                  '        return\n'
                  '\n'
                  '    color_map = {\n'
                  '        "RelatedPartyNetwork": "#EAECEE",\n'
                  '        "Company": "#F9E79F",\n'
                  '        "RelatedParty": "#F5B7B1",\n'
                  '        "RelationType": "#AED6F1",\n'
                  '    }\n'
                  '\n'
                  '    net = Network(height="900px", width="100%", directed=True, notebook=False)\n'
                  '    net.toggle_physics(True)\n'
                  '\n'
                  '    for n in nodes:\n'
                  '        label = n.get("label", "")\n'
                  '        display = n.get("name", n.get("id", ""))\n'
                  '\n'
                  '        if label == "Company" and n.get("stock_code"):\n'
                  '            display = f"{n.get(\'stock_code\')} {display}"\n'
                  '\n'
                  '        title = "<br>".join(f"{k}: {v}" for k, v in n.items() if v not in ["", None])\n'
                  '\n'
                  '        net.add_node(\n'
                  '            n["id"],\n'
                  '            label=display,\n'
                  '            title=title,\n'
                  '            color=color_map.get(label, "#D5DBDB"),\n'
                  '            shape="dot" if label in {"Company", "RelatedParty"} else "box",\n'
                  '        )\n'
                  '\n'
                  '    for e in edges:\n'
                  '        title = "<br>".join(f"{k}: {v}" for k, v in e.items() if v not in ["", None])\n'
                  '        net.add_edge(e["source"], e["target"], label=e.get("type", ""), title=title)\n'
                  '\n'
                  '    net.write_html(str(OUTPUT_DIR / "related_party_graph.html"))\n'
                  '\n'
                  '\n'
                  '# ============================================================\n'
                  '# 8. 主程式\n'
                  '# ============================================================\n'
                  'def main() -> None:\n'
                  '    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)\n'
                  '\n'
                  '    records, scan_rows, rejected_rows = parse_all_related_party_tables(INPUT_DIR)\n'
                  '\n'
                  '    if not records:\n'
                  '        write_csv(\n'
                  '            OUTPUT_DIR / "scan_report.csv",\n'
                  '            scan_rows,\n'
                  '            ["stock_id", "company_name", "period", "csv_count", "target_count", "target_files"],\n'
                  '        )\n'
                  '        write_csv(\n'
                  '            OUTPUT_DIR / "rejected_files.csv",\n'
                  '            rejected_rows,\n'
                  '            ["stock_id", "company_name", "period", "csv_file", "reason"],\n'
                  '        )\n'
                  '        print("⚠️ 沒有解析到任何關係人資料。已輸出 scan_report.csv / rejected_files.csv。")\n'
                  '        return\n'
                  '\n'
                  '    nodes, edges = build_graph(records)\n'
                  '    write_outputs(records, scan_rows, rejected_rows, nodes, edges)\n'
                  '    try_write_pyvis_html(nodes, edges)\n'
                  '\n'
                  '    report_company_count = len({r.report_stock_id for r in records})\n'
                  '    related_party_count = len({normalize_party_key(r.related_party_name) for r in records})\n'
                  '    relation_type_count = len({r.relation_category for r in records})\n'
                  '    companies_with_target = sum(1 for r in scan_rows if int(r["target_count"]) > 0)\n'
                  '\n'
                  '    print("\\n✅ 全部公司關係人圖譜建立完成")\n'
                  '    print(f"輸入資料夾：{INPUT_DIR.resolve()}")\n'
                  '    print(f"輸出資料夾：{OUTPUT_DIR.resolve()}")\n'
                  '    print(f"公司/季度組合數：{len(scan_rows)}")\n'
                  '    print(f"有關係人名稱及關係表的公司/季度組合數：{companies_with_target}")\n'
                  '    print(f"申報公司數：{report_company_count}")\n'
                  '    print(f"關係人數：{related_party_count}")\n'
                  '    print(f"關係類型數：{relation_type_count}")\n'
                  '    print(f"關係筆數：{len(records)}")\n'
                  '    print(f"節點數：{len(nodes)}")\n'
                  '    print(f"關係數：{len(edges)}")\n'
                  '\n'
                  '    print("\\n主要輸出：")\n'
                  '    print(f"- {OUTPUT_DIR / \'scan_report.csv\'}")\n'
                  '    print(f"- {OUTPUT_DIR / \'rejected_files.csv\'}")\n'
                  '    print(f"- {OUTPUT_DIR / \'related_party_table.csv\'}")\n'
                  '    print(f"- {OUTPUT_DIR / \'neo4j_nodes.csv\'}")\n'
                  '    print(f"- {OUTPUT_DIR / \'neo4j_relationships.csv\'}")\n'
                  '    if (OUTPUT_DIR / "related_party_graph.html").exists():\n'
                  '        print(f"- {OUTPUT_DIR / \'related_party_graph.html\'}")\n'
                  '\n'
                  '\n'
                  'if __name__ == "__main__":\n'
                  '    main()\n',
 'supply_chain': '# -*- coding: utf-8 -*-\n'
                 '"""\n'
                 'build_supply_chain_graph.py\n'
                 '\n'
                 '用途：\n'
                 '    將 tw_semiconductor_supply_chain_stock_codes.txt 這種「產業鏈階層文字檔」轉成圖譜資料。\n'
                 '\n'
                 '輸入格式範例：\n'
                 '    [下游] IC通路\n'
                 '    (本國上市公司)\n'
                 '    --- 2308 台達電\n'
                 '    --- 2347 聯強\n'
                 '\n'
                 '輸出：\n'
                 '    supply_chain_graph_output/\n'
                 '      company_table.csv\n'
                 '      graph_nodes.csv\n'
                 '      graph_edges.csv\n'
                 '      neo4j_nodes.csv\n'
                 '      neo4j_relationships.csv\n'
                 '      graph_nodes.jsonl\n'
                 '      graph_edges.jsonl\n'
                 '      import_neo4j.cypher\n'
                 '      supply_chain_graph.html  # 若已安裝 pyvis 才會產生\n'
                 '\n'
                 '執行：\n'
                 '    python build_supply_chain_graph.py\n'
                 '\n'
                 '若檔案位置不同，修改 INPUT_TXT 即可。\n'
                 '"""\n'
                 '\n'
                 'from __future__ import annotations\n'
                 '\n'
                 'import csv\n'
                 'import json\n'
                 'import re\n'
                 'from dataclasses import dataclass, asdict\n'
                 'from pathlib import Path\n'
                 'from typing import Dict, List, Optional, Tuple\n'
                 '\n'
                 '# =========================================================\n'
                 '# 1. 設定區\n'
                 '# =========================================================\n'
                 'INPUT_TXT = Path("./tw_semiconductor_supply_chain_stock_codes.txt")\n'
                 'OUTPUT_DIR = Path("./supply_chain_graph_output")\n'
                 '\n'
                 'ROOT_ID = "industry_chain:tw_semiconductor"\n'
                 'ROOT_NAME = "台灣半導體產業鏈"\n'
                 '\n'
                 'ENCODING_CANDIDATES = ["utf-8-sig", "utf-8", "cp950", "big5"]\n'
                 '\n'
                 '# 允許的階段關鍵字。若你的檔案之後有別的名稱，可加在這裡。\n'
                 'STAGE_KEYWORDS = ["上游", "中游", "下游", "設備", "材料", "通路", "封測", "設計", "製造"]\n'
                 '\n'
                 '# =========================================================\n'
                 '# 2. 資料結構\n'
                 '# =========================================================\n'
                 '@dataclass\n'
                 'class CompanyRecord:\n'
                 '    stock_code: str\n'
                 '    company_name: str\n'
                 '    stage: str\n'
                 '    segment: str\n'
                 '    market: str\n'
                 '    source_line_no: int\n'
                 '    source_line: str\n'
                 '\n'
                 '\n'
                 '# =========================================================\n'
                 '# 3. 基礎工具\n'
                 '# =========================================================\n'
                 'def read_text_with_fallback(path: Path) -> str:\n'
                 '    if not path.exists():\n'
                 '        raise FileNotFoundError(\n'
                 '            f"找不到輸入檔案：{path.resolve()}\\n"\n'
                 '            "請確認 tw_semiconductor_supply_chain_stock_codes.txt 是否與本程式放在同一層，"\n'
                 '            "或修改程式最上方的 INPUT_TXT。"\n'
                 '        )\n'
                 '\n'
                 '    last_error = None\n'
                 '    for enc in ENCODING_CANDIDATES:\n'
                 '        try:\n'
                 '            return path.read_text(encoding=enc)\n'
                 '        except UnicodeDecodeError as e:\n'
                 '            last_error = e\n'
                 '    raise UnicodeDecodeError(\n'
                 '        "unknown", b"", 0, 1,\n'
                 '        f"無法用這些編碼讀取：{ENCODING_CANDIDATES}。最後錯誤：{last_error}"\n'
                 '    )\n'
                 '\n'
                 '\n'
                 'def safe_id(text: str) -> str:\n'
                 '    """產生穩定、可給 Neo4j / CSV 使用的 id。"""\n'
                 '    s = str(text).strip().lower()\n'
                 '    s = re.sub(r"\\s+", "_", s)\n'
                 '    s = re.sub(r"[^0-9a-zA-Z_\\u4e00-\\u9fff:-]", "_", s)\n'
                 '    s = re.sub(r"_+", "_", s).strip("_")\n'
                 '    return s\n'
                 '\n'
                 '\n'
                 'def clean_line(raw: str) -> str:\n'
                 '    """清除樹狀符號與多餘空白，但保留中文、數字與括號。"""\n'
                 '    s = raw.strip()\n'
                 '    s = s.replace("｜", "│")\n'
                 '    s = s.replace("－", "-").replace("—", "-").replace("–", "-")\n'
                 '    s = s.replace("\u3000", " ")\n'
                 '    # 移除常見樹狀圖前綴，例如 ---、├──、└──、│\n'
                 '    s = re.sub(r"^[\\s│├└─\\-\\.\\*•]+", "", s)\n'
                 '    s = re.sub(r"\\s+", " ", s).strip()\n'
                 '    return s\n'
                 '\n'
                 '\n'
                 'def is_market_line(s: str) -> bool:\n'
                 '    return bool(re.match(r"^[（(].*[）)]$", s)) and any(k in s for k in ["公司", "上市", "上櫃", "興櫃", '
                 '"公開發行"])\n'
                 '\n'
                 '\n'
                 'def normalize_market(s: str) -> str:\n'
                 '    return s.strip().strip("()（）").strip()\n'
                 '\n'
                 '\n'
                 'def parse_stage_segment(s: str) -> Optional[Tuple[str, str]]:\n'
                 '    """\n'
                 '    支援：\n'
                 '      [下游] IC通路\n'
                 '      【下游】IC通路\n'
                 '      下游：IC通路\n'
                 '      下游 - IC通路\n'
                 '    """\n'
                 '    patterns = [\n'
                 '        r"^[\\[【](?P<stage>[^\\]】]+)[\\]】]\\s*(?P<segment>.+)$",\n'
                 '        r"^(?P<stage>上游|中游|下游)\\s*[:：\\-]\\s*(?P<segment>.+)$",\n'
                 '    ]\n'
                 '    for pat in patterns:\n'
                 '        m = re.match(pat, s)\n'
                 '        if m:\n'
                 '            stage = m.group("stage").strip()\n'
                 '            segment = m.group("segment").strip()\n'
                 '            if segment:\n'
                 '                return stage, segment\n'
                 '\n'
                 '    # 若是「下游 IC通路」也嘗試解析，但避免誤判公司名稱。\n'
                 '    m = re.match(r"^(?P<stage>上游|中游|下游)\\s+(?P<segment>[^\\d].+)$", s)\n'
                 '    if m:\n'
                 '        return m.group("stage").strip(), m.group("segment").strip()\n'
                 '\n'
                 '    return None\n'
                 '\n'
                 '\n'
                 'def parse_company(s: str) -> Optional[Tuple[str, str]]:\n'
                 '    """\n'
                 '    支援：\n'
                 '      2308 台達電\n'
                 '      2308台達電\n'
                 '      3008 大立光\n'
                 '      8069 元太\n'
                 '    """\n'
                 '    s = s.strip()\n'
                 '    # 避免把標題或日期誤判成公司。\n'
                 '    if any(k in s for k in ["年", "月", "日", "公司代號", "股票代號"]):\n'
                 '        return None\n'
                 '\n'
                 '    m = re.match(r"^(?P<code>\\d{4}[A-Z]?)\\s*(?P<name>[^\\d].+)$", s)\n'
                 '    if not m:\n'
                 '        return None\n'
                 '\n'
                 '    code = m.group("code").strip()\n'
                 '    name = m.group("name").strip()\n'
                 '    name = re.sub(r"^[\\-:：]+", "", name).strip()\n'
                 '\n'
                 '    if not name or len(name) < 1:\n'
                 '        return None\n'
                 '\n'
                 '    # 避免把純說明文字吃進來。\n'
                 '    if len(name) > 40:\n'
                 '        name = name[:40].strip()\n'
                 '\n'
                 '    return code, name\n'
                 '\n'
                 '\n'
                 '# =========================================================\n'
                 '# 4. 解析產業鏈文字檔\n'
                 '# =========================================================\n'
                 'def parse_supply_chain_text(text: str) -> List[CompanyRecord]:\n'
                 '    records: List[CompanyRecord] = []\n'
                 '\n'
                 '    current_stage = "未分類"\n'
                 '    current_segment = "未分類"\n'
                 '    current_market = "未標註"\n'
                 '\n'
                 '    for line_no, raw_line in enumerate(text.splitlines(), start=1):\n'
                 '        s = clean_line(raw_line)\n'
                 '        if not s:\n'
                 '            continue\n'
                 '        if s.startswith("#"):\n'
                 '            continue\n'
                 '\n'
                 '        stage_segment = parse_stage_segment(s)\n'
                 '        if stage_segment:\n'
                 '            current_stage, current_segment = stage_segment\n'
                 '            current_market = "未標註"\n'
                 '            continue\n'
                 '\n'
                 '        if is_market_line(s):\n'
                 '            current_market = normalize_market(s)\n'
                 '            continue\n'
                 '\n'
                 '        company = parse_company(s)\n'
                 '        if company:\n'
                 '            stock_code, company_name = company\n'
                 '            records.append(\n'
                 '                CompanyRecord(\n'
                 '                    stock_code=stock_code,\n'
                 '                    company_name=company_name,\n'
                 '                    stage=current_stage,\n'
                 '                    segment=current_segment,\n'
                 '                    market=current_market,\n'
                 '                    source_line_no=line_no,\n'
                 '                    source_line=raw_line.rstrip("\\n"),\n'
                 '                )\n'
                 '            )\n'
                 '            continue\n'
                 '\n'
                 '    return records\n'
                 '\n'
                 '\n'
                 '# =========================================================\n'
                 '# 5. 建立圖譜 Nodes / Edges\n'
                 '# =========================================================\n'
                 'def add_node(nodes: Dict[str, dict], node_id: str, label: str, **props) -> None:\n'
                 '    if node_id not in nodes:\n'
                 '        nodes[node_id] = {"id": node_id, "label": label, **props}\n'
                 '    else:\n'
                 '        # 合併非空屬性，不覆蓋既有重要資訊。\n'
                 '        for k, v in props.items():\n'
                 '            if k not in nodes[node_id] or nodes[node_id][k] in ["", None, "未標註", "未分類"]:\n'
                 '                nodes[node_id][k] = v\n'
                 '\n'
                 '\n'
                 'def add_edge(edges: Dict[Tuple[str, str, str], dict], source: str, target: str, edge_type: str, '
                 '**props) -> None:\n'
                 '    key = (source, target, edge_type)\n'
                 '    if key not in edges:\n'
                 '        edges[key] = {"source": source, "target": target, "type": edge_type, **props}\n'
                 '    else:\n'
                 '        # 同一條邊出現多次時，累計來源行號。\n'
                 '        if "source_line_no" in props:\n'
                 '            old = str(edges[key].get("source_line_no", ""))\n'
                 '            new = str(props["source_line_no"])\n'
                 '            if new not in old.split(";"):\n'
                 '                edges[key]["source_line_no"] = f"{old};{new}" if old else new\n'
                 '\n'
                 '\n'
                 'def build_graph(records: List[CompanyRecord]) -> Tuple[List[dict], List[dict]]:\n'
                 '    nodes: Dict[str, dict] = {}\n'
                 '    edges: Dict[Tuple[str, str, str], dict] = {}\n'
                 '\n'
                 '    add_node(nodes, ROOT_ID, "IndustryChain", name=ROOT_NAME)\n'
                 '\n'
                 '    for r in records:\n'
                 '        stage_id = f"stage:{safe_id(r.stage)}"\n'
                 '        segment_id = f"segment:{safe_id(r.stage)}:{safe_id(r.segment)}"\n'
                 '        company_id = f"company:{r.stock_code}"\n'
                 '\n'
                 '        add_node(nodes, stage_id, "Stage", name=r.stage, stage=r.stage)\n'
                 '        add_node(nodes, segment_id, "Segment", name=r.segment, stage=r.stage, segment=r.segment)\n'
                 '        add_node(\n'
                 '            nodes,\n'
                 '            company_id,\n'
                 '            "Company",\n'
                 '            name=r.company_name,\n'
                 '            stock_code=r.stock_code,\n'
                 '            market=r.market,\n'
                 '        )\n'
                 '\n'
                 '        add_edge(edges, ROOT_ID, stage_id, "HAS_STAGE")\n'
                 '        add_edge(edges, stage_id, segment_id, "HAS_SEGMENT")\n'
                 '        add_edge(\n'
                 '            edges,\n'
                 '            segment_id,\n'
                 '            company_id,\n'
                 '            "HAS_COMPANY",\n'
                 '            stage=r.stage,\n'
                 '            segment=r.segment,\n'
                 '            market=r.market,\n'
                 '            source_line_no=r.source_line_no,\n'
                 '        )\n'
                 '\n'
                 '    return list(nodes.values()), list(edges.values())\n'
                 '\n'
                 '\n'
                 '# =========================================================\n'
                 '# 6. 輸出工具\n'
                 '# =========================================================\n'
                 'def write_csv(path: Path, rows: List[dict], fieldnames: List[str]) -> None:\n'
                 '    path.parent.mkdir(parents=True, exist_ok=True)\n'
                 '    with path.open("w", newline="", encoding="utf-8-sig") as f:\n'
                 '        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")\n'
                 '        writer.writeheader()\n'
                 '        for row in rows:\n'
                 '            writer.writerow(row)\n'
                 '\n'
                 '\n'
                 'def write_jsonl(path: Path, rows: List[dict]) -> None:\n'
                 '    path.parent.mkdir(parents=True, exist_ok=True)\n'
                 '    with path.open("w", encoding="utf-8") as f:\n'
                 '        for row in rows:\n'
                 '            f.write(json.dumps(row, ensure_ascii=False) + "\\n")\n'
                 '\n'
                 '\n'
                 'def write_company_table(path: Path, records: List[CompanyRecord]) -> None:\n'
                 '    rows = [asdict(r) for r in records]\n'
                 '    write_csv(\n'
                 '        path,\n'
                 '        rows,\n'
                 '        ["stock_code", "company_name", "stage", "segment", "market", "source_line_no", '
                 '"source_line"],\n'
                 '    )\n'
                 '\n'
                 '\n'
                 'def write_neo4j_csv(output_dir: Path, nodes: List[dict], edges: List[dict]) -> None:\n'
                 '    neo_nodes = []\n'
                 '    for n in nodes:\n'
                 '        neo_nodes.append({\n'
                 '            "id:ID": n.get("id", ""),\n'
                 '            ":LABEL": n.get("label", ""),\n'
                 '            "name": n.get("name", ""),\n'
                 '            "stock_code": n.get("stock_code", ""),\n'
                 '            "stage": n.get("stage", ""),\n'
                 '            "segment": n.get("segment", ""),\n'
                 '            "market": n.get("market", ""),\n'
                 '        })\n'
                 '\n'
                 '    neo_edges = []\n'
                 '    for e in edges:\n'
                 '        neo_edges.append({\n'
                 '            ":START_ID": e.get("source", ""),\n'
                 '            ":END_ID": e.get("target", ""),\n'
                 '            ":TYPE": e.get("type", ""),\n'
                 '            "stage": e.get("stage", ""),\n'
                 '            "segment": e.get("segment", ""),\n'
                 '            "market": e.get("market", ""),\n'
                 '            "source_line_no": e.get("source_line_no", ""),\n'
                 '        })\n'
                 '\n'
                 '    write_csv(\n'
                 '        output_dir / "neo4j_nodes.csv",\n'
                 '        neo_nodes,\n'
                 '        ["id:ID", ":LABEL", "name", "stock_code", "stage", "segment", "market"],\n'
                 '    )\n'
                 '    write_csv(\n'
                 '        output_dir / "neo4j_relationships.csv",\n'
                 '        neo_edges,\n'
                 '        [":START_ID", ":END_ID", ":TYPE", "stage", "segment", "market", "source_line_no"],\n'
                 '    )\n'
                 '\n'
                 '\n'
                 'def write_neo4j_cypher(output_dir: Path) -> None:\n'
                 "    cypher = r'''\n"
                 '// 請先把 neo4j_nodes.csv 與 neo4j_relationships.csv 放到 Neo4j import 資料夾。\n'
                 '// Neo4j Browser / cypher-shell 執行：\n'
                 '\n'
                 'CREATE CONSTRAINT company_stock_code IF NOT EXISTS\n'
                 'FOR (c:Company) REQUIRE c.stock_code IS UNIQUE;\n'
                 '\n'
                 'CREATE CONSTRAINT graph_node_id IF NOT EXISTS\n'
                 'FOR (n:GraphNode) REQUIRE n.id IS UNIQUE;\n'
                 '\n'
                 "LOAD CSV WITH HEADERS FROM 'file:///neo4j_nodes.csv' AS row\n"
                 'WITH row\n'
                 'CALL {\n'
                 '  WITH row\n'
                 "  WITH row WHERE row.`:LABEL` = 'IndustryChain'\n"
                 '  MERGE (n:GraphNode:IndustryChain {id: row.`id:ID`})\n'
                 '  SET n.name = row.name\n'
                 '}\n'
                 'CALL {\n'
                 '  WITH row\n'
                 "  WITH row WHERE row.`:LABEL` = 'Stage'\n"
                 '  MERGE (n:GraphNode:Stage {id: row.`id:ID`})\n'
                 '  SET n.name = row.name,\n'
                 '      n.stage = row.stage\n'
                 '}\n'
                 'CALL {\n'
                 '  WITH row\n'
                 "  WITH row WHERE row.`:LABEL` = 'Segment'\n"
                 '  MERGE (n:GraphNode:Segment {id: row.`id:ID`})\n'
                 '  SET n.name = row.name,\n'
                 '      n.stage = row.stage,\n'
                 '      n.segment = row.segment\n'
                 '}\n'
                 'CALL {\n'
                 '  WITH row\n'
                 "  WITH row WHERE row.`:LABEL` = 'Company'\n"
                 '  MERGE (n:GraphNode:Company {id: row.`id:ID`})\n'
                 '  SET n.name = row.name,\n'
                 '      n.stock_code = row.stock_code,\n'
                 '      n.market = row.market\n'
                 '}\n'
                 'RETURN count(*) AS loaded_nodes;\n'
                 '\n'
                 "LOAD CSV WITH HEADERS FROM 'file:///neo4j_relationships.csv' AS row\n"
                 'MATCH (s:GraphNode {id: row.`:START_ID`})\n'
                 'MATCH (t:GraphNode {id: row.`:END_ID`})\n'
                 'CALL apoc.create.relationship(\n'
                 '  s,\n'
                 '  row.`:TYPE`,\n'
                 '  {\n'
                 '    stage: row.stage,\n'
                 '    segment: row.segment,\n'
                 '    market: row.market,\n'
                 '    source_line_no: row.source_line_no\n'
                 '  },\n'
                 '  t\n'
                 ') YIELD rel\n'
                 'RETURN count(rel) AS loaded_relationships;\n'
                 "'''.strip()\n"
                 '\n'
                 '    # 不強制使用 APOC 的版本\n'
                 "    cypher_no_apoc = r'''\n"
                 '// 無 APOC 版本：分三次載入關係。\n'
                 '// 請先把 neo4j_nodes.csv 與 neo4j_relationships.csv 放到 Neo4j import 資料夾。\n'
                 '\n'
                 'CREATE CONSTRAINT graph_node_id IF NOT EXISTS\n'
                 'FOR (n:GraphNode) REQUIRE n.id IS UNIQUE;\n'
                 '\n'
                 "LOAD CSV WITH HEADERS FROM 'file:///neo4j_nodes.csv' AS row\n"
                 'WITH row\n'
                 'CALL {\n'
                 '  WITH row\n'
                 "  WITH row WHERE row.`:LABEL` = 'IndustryChain'\n"
                 '  MERGE (n:GraphNode:IndustryChain {id: row.`id:ID`})\n'
                 '  SET n.name = row.name\n'
                 '}\n'
                 'CALL {\n'
                 '  WITH row\n'
                 "  WITH row WHERE row.`:LABEL` = 'Stage'\n"
                 '  MERGE (n:GraphNode:Stage {id: row.`id:ID`})\n'
                 '  SET n.name = row.name, n.stage = row.stage\n'
                 '}\n'
                 'CALL {\n'
                 '  WITH row\n'
                 "  WITH row WHERE row.`:LABEL` = 'Segment'\n"
                 '  MERGE (n:GraphNode:Segment {id: row.`id:ID`})\n'
                 '  SET n.name = row.name, n.stage = row.stage, n.segment = row.segment\n'
                 '}\n'
                 'CALL {\n'
                 '  WITH row\n'
                 "  WITH row WHERE row.`:LABEL` = 'Company'\n"
                 '  MERGE (n:GraphNode:Company {id: row.`id:ID`})\n'
                 '  SET n.name = row.name, n.stock_code = row.stock_code, n.market = row.market\n'
                 '}\n'
                 'RETURN count(*) AS loaded_nodes;\n'
                 '\n'
                 "LOAD CSV WITH HEADERS FROM 'file:///neo4j_relationships.csv' AS row\n"
                 "WITH row WHERE row.`:TYPE` = 'HAS_STAGE'\n"
                 'MATCH (s:GraphNode {id: row.`:START_ID`})\n'
                 'MATCH (t:GraphNode {id: row.`:END_ID`})\n'
                 'MERGE (s)-[:HAS_STAGE]->(t);\n'
                 '\n'
                 "LOAD CSV WITH HEADERS FROM 'file:///neo4j_relationships.csv' AS row\n"
                 "WITH row WHERE row.`:TYPE` = 'HAS_SEGMENT'\n"
                 'MATCH (s:GraphNode {id: row.`:START_ID`})\n'
                 'MATCH (t:GraphNode {id: row.`:END_ID`})\n'
                 'MERGE (s)-[:HAS_SEGMENT]->(t);\n'
                 '\n'
                 "LOAD CSV WITH HEADERS FROM 'file:///neo4j_relationships.csv' AS row\n"
                 "WITH row WHERE row.`:TYPE` = 'HAS_COMPANY'\n"
                 'MATCH (s:GraphNode {id: row.`:START_ID`})\n'
                 'MATCH (t:GraphNode {id: row.`:END_ID`})\n'
                 'MERGE (s)-[r:HAS_COMPANY]->(t)\n'
                 'SET r.stage = row.stage,\n'
                 '    r.segment = row.segment,\n'
                 '    r.market = row.market,\n'
                 '    r.source_line_no = row.source_line_no;\n'
                 "'''.strip()\n"
                 '\n'
                 '    (output_dir / "import_neo4j_with_apoc.cypher").write_text(cypher + "\\n", encoding="utf-8")\n'
                 '    (output_dir / "import_neo4j_no_apoc.cypher").write_text(cypher_no_apoc + "\\n", '
                 'encoding="utf-8")\n'
                 '\n'
                 '\n'
                 'def try_write_pyvis_html(output_dir: Path, nodes: List[dict], edges: List[dict]) -> None:\n'
                 '    try:\n'
                 '        from pyvis.network import Network\n'
                 '    except Exception:\n'
                 '        print("ℹ️ 未安裝 pyvis，略過 HTML 圖譜。若需要可執行：pip install pyvis")\n'
                 '        return\n'
                 '\n'
                 '    color_map = {\n'
                 '        "IndustryChain": "#EAECEE",\n'
                 '        "Stage": "#AED6F1",\n'
                 '        "Segment": "#A9DFBF",\n'
                 '        "Company": "#F9E79F",\n'
                 '    }\n'
                 '\n'
                 '    net = Network(height="900px", width="100%", directed=True, notebook=False)\n'
                 '    net.toggle_physics(True)\n'
                 '\n'
                 '    for n in nodes:\n'
                 '        label = n.get("label", "")\n'
                 '        title = "<br>".join(f"{k}: {v}" for k, v in n.items() if v not in ["", None])\n'
                 '        display = n.get("name", n.get("id"))\n'
                 '        if label == "Company" and n.get("stock_code"):\n'
                 '            display = f"{n.get(\'stock_code\')} {display}"\n'
                 '        net.add_node(\n'
                 '            n["id"],\n'
                 '            label=display,\n'
                 '            title=title,\n'
                 '            color=color_map.get(label, "#D5DBDB"),\n'
                 '            shape="dot" if label == "Company" else "box",\n'
                 '        )\n'
                 '\n'
                 '    for e in edges:\n'
                 '        net.add_edge(\n'
                 '            e["source"],\n'
                 '            e["target"],\n'
                 '            label=e.get("type", ""),\n'
                 '            title="<br>".join(f"{k}: {v}" for k, v in e.items() if v not in ["", None]),\n'
                 '        )\n'
                 '\n'
                 '    net.write_html(str(output_dir / "supply_chain_graph.html"))\n'
                 '\n'
                 '\n'
                 '# =========================================================\n'
                 '# 7. 主程式\n'
                 '# =========================================================\n'
                 'def main() -> None:\n'
                 '    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)\n'
                 '\n'
                 '    text = read_text_with_fallback(INPUT_TXT)\n'
                 '    records = parse_supply_chain_text(text)\n'
                 '\n'
                 '    if not records:\n'
                 '        print("⚠️ 沒有解析到任何公司資料。")\n'
                 '        print("請確認檔案格式是否類似：")\n'
                 '        print("[下游] IC通路")\n'
                 '        print("(本國上市公司)")\n'
                 '        print("--- 2308 台達電")\n'
                 '        return\n'
                 '\n'
                 '    nodes, edges = build_graph(records)\n'
                 '\n'
                 '    # 一般分析輸出\n'
                 '    write_company_table(OUTPUT_DIR / "company_table.csv", records)\n'
                 '    write_csv(\n'
                 '        OUTPUT_DIR / "graph_nodes.csv",\n'
                 '        nodes,\n'
                 '        ["id", "label", "name", "stock_code", "stage", "segment", "market"],\n'
                 '    )\n'
                 '    write_csv(\n'
                 '        OUTPUT_DIR / "graph_edges.csv",\n'
                 '        edges,\n'
                 '        ["source", "target", "type", "stage", "segment", "market", "source_line_no"],\n'
                 '    )\n'
                 '    write_jsonl(OUTPUT_DIR / "graph_nodes.jsonl", nodes)\n'
                 '    write_jsonl(OUTPUT_DIR / "graph_edges.jsonl", edges)\n'
                 '\n'
                 '    # Neo4j 輸出\n'
                 '    write_neo4j_csv(OUTPUT_DIR, nodes, edges)\n'
                 '    write_neo4j_cypher(OUTPUT_DIR)\n'
                 '\n'
                 '    # HTML 可視化\n'
                 '    try_write_pyvis_html(OUTPUT_DIR, nodes, edges)\n'
                 '\n'
                 '    company_count = len({r.stock_code for r in records})\n'
                 '    stage_count = len({r.stage for r in records})\n'
                 '    segment_count = len({(r.stage, r.segment) for r in records})\n'
                 '\n'
                 '    print("✅ 產業鏈圖譜建立完成")\n'
                 '    print(f"輸入檔案：{INPUT_TXT.resolve()}")\n'
                 '    print(f"輸出資料夾：{OUTPUT_DIR.resolve()}")\n'
                 '    print(f"公司數：{company_count}")\n'
                 '    print(f"階段數：{stage_count}")\n'
                 '    print(f"產業鏈分類數：{segment_count}")\n'
                 '    print(f"節點數：{len(nodes)}")\n'
                 '    print(f"關係數：{len(edges)}")\n'
                 '    print("\\n主要輸出：")\n'
                 '    print(f"- {OUTPUT_DIR / \'company_table.csv\'}")\n'
                 '    print(f"- {OUTPUT_DIR / \'graph_nodes.csv\'}")\n'
                 '    print(f"- {OUTPUT_DIR / \'graph_edges.csv\'}")\n'
                 '    print(f"- {OUTPUT_DIR / \'neo4j_nodes.csv\'}")\n'
                 '    print(f"- {OUTPUT_DIR / \'neo4j_relationships.csv\'}")\n'
                 '    print(f"- {OUTPUT_DIR / \'import_neo4j_no_apoc.cypher\'}")\n'
                 '\n'
                 '\n'
                 'if __name__ == "__main__":\n'
                 '    main()\n'}


# ============================================================
# 1. 通用設定
# ============================================================
BASE_DIR = Path(__file__).resolve().parent
VALID_TARGETS = ("investment", "related_party", "supply_chain", "risk_event")
DISPLAY_NAMES = {
    "investment": "被投資公司關係圖譜",
    "related_party": "關係人圖譜",
    "supply_chain": "半導體產業鏈圖譜",
    "risk_event": "風險事件圖譜",
}

ENCODING_CANDIDATES = ["utf-8-sig", "utf-8", "cp950", "big5"]


# ============================================================
# 2. Risk Event Ontology
# ============================================================
# 這裡是「風險候選」規則，不代表因果已成立。
# LLM 回答時應說明：這些是財報 evidence 支援的 risk candidates。
DEFAULT_ONTOLOGY = {
    "risk_events": [
        {
            "name": "供應鏈壓力",
            "risk_type": "supply_chain_risk",
            "keywords": ["進貨", "應付帳款", "應付關係人款項", "其他應付款項－關係人", "供應商", "採購"],
            "any_keywords": ["進貨", "應付帳款", "應付關係人款項", "其他應付款項－關係人", "供應商", "採購"],
            "exclude_keywords": ["佔合併總營收或總資產之比率", "%", "％"],
            "evidence_level": "medium",
            "evidence_strength": "medium",
            "description": "成本端、付款端或供應商往來的風險候選；不是直接因果證明。",
        },
        {
            "name": "原料價格上升",
            "risk_type": "raw_material_cost_risk",
            "keywords": ["原料價格", "原材料價格", "材料成本", "採購成本", "營業成本增加", "成本增加", "價格上漲"],
            "any_keywords": ["原料價格", "原材料價格", "材料成本", "採購成本", "營業成本增加", "成本增加", "價格上漲"],
            "exclude_keywords": ["單純進貨", "進貨"],
            "evidence_level": "weak_candidate",
            "evidence_strength": "weak_candidate",
            "description": "需要明確價格或成本上升文字；單純進貨金額不得直接判定為原料價格上升。",
        },
        {
            "name": "過度庫存",
            "risk_type": "inventory_risk",
            "keywords": ["存貨", "庫存", "製成品", "在製品", "原料"],
            "any_keywords": ["存貨", "庫存", "製成品", "在製品", "原料"],
            "exclude_keywords": ["存貨跌價", "備抵存貨跌價"],
            "evidence_level": "medium",
            "evidence_strength": "medium",
            "description": "存貨相關科目可作為庫存風險候選；仍需結合需求或跌價證據才能形成較強結論。",
        },
        {
            "name": "存貨跌價損失",
            "risk_type": "inventory_write_down_risk",
            "keywords": ["存貨跌價", "跌價損失", "備抵存貨跌價", "呆滯"],
            "any_keywords": ["存貨跌價", "跌價損失", "備抵存貨跌價", "呆滯"],
            "exclude_keywords": [],
            "evidence_level": "strong",
            "evidence_strength": "strong",
            "description": "明確存貨跌價或呆滯損失科目。",
        },
        {
            "name": "匯率風險",
            "risk_type": "fx_risk",
            "keywords": ["外幣兌換", "匯率", "匯兌", "外幣"],
            "any_keywords": ["外幣兌換", "匯率", "匯兌", "外幣"],
            "exclude_keywords": [],
            "evidence_level": "strong",
            "evidence_strength": "strong",
            "description": "外幣兌換損益、匯率影響數等明確匯率相關科目。",
        },
        {
            "name": "營收波動候選",
            "risk_type": "revenue_volatility_candidate",
            "keywords": ["營業收入", "銷貨收入", "銷售收入", "客戶合約之收入"],
            "any_keywords": ["營業收入", "銷貨收入", "銷售收入", "客戶合約之收入"],
            "exclude_keywords": ["客戶集中", "主要客戶", "單一客戶"],
            "evidence_level": "weak_candidate",
            "evidence_strength": "weak_candidate",
            "description": "收入科目只能表示營收波動候選；不得直接判定客戶集中。",
        },
        {
            "name": "客戶集中風險",
            "risk_type": "customer_concentration_risk",
            "keywords": ["主要客戶", "單一客戶", "客戶集中", "交易對象", "客戶名稱", "銷貨", "銷售收入", "營業收入", "佔合併總營收"],
            "all_keywords_any_group": [
                ["主要客戶", "單一客戶", "客戶集中", "交易對象", "客戶名稱"],
                ["銷貨", "銷售收入", "營業收入", "佔合併總營收"],
            ],
            "exclude_keywords": [],
            "evidence_level": "strong",
            "evidence_strength": "strong",
            "description": "必須同時有客戶/交易對象或集中度文字，以及收入端交易詞。",
        },
        {
            "name": "營運資金壓力",
            "risk_type": "working_capital_risk",
            "keywords": ["應收帳款", "其他應收款", "應收關係人款項", "應付帳款", "其他應付款", "應付關係人款項"],
            "any_keywords": ["應收帳款", "其他應收款", "應收關係人款項", "應付帳款", "其他應付款", "應付關係人款項"],
            "exclude_keywords": ["佔合併總營收或總資產之比率", "%", "％"],
            "evidence_level": "medium",
            "evidence_strength": "medium",
            "description": "應收/應付等營運資金科目。",
        },
        {
            "name": "需求疲弱",
            "risk_type": "demand_risk",
            "keywords": ["需求減少", "市場需求下降", "客戶需求下降", "營業收入減少", "銷貨減少", "收入減少"],
            "any_keywords": ["需求減少", "市場需求下降", "客戶需求下降", "營業收入減少", "銷貨減少", "收入減少"],
            "exclude_keywords": [],
            "evidence_level": "medium",
            "evidence_strength": "medium",
            "description": "需要明確需求或收入下降文字；單純營業收入科目不等於需求疲弱。",
        },
    ],
    "causal_edges": [
        ["原料價格上升", "供應鏈壓力", "MAY_CAUSE"],
        ["供應鏈壓力", "過度庫存", "MAY_CAUSE"],
        ["需求疲弱", "過度庫存", "MAY_CAUSE"],
        ["過度庫存", "存貨跌價損失", "MAY_CAUSE"],
        ["存貨跌價損失", "毛利率下降", "AFFECTS"],
        ["營收波動候選", "公司價值波動", "AFFECTS"],
        ["匯率風險", "營業外損益波動", "AFFECTS"],
        ["營運資金壓力", "現金流壓力", "AFFECTS"],
        ["客戶集中風險", "營收波動候選", "MAY_CAUSE"],
    ],
}


# ============================================================
# 3. Basic Helpers
# ============================================================
def clean_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    text = str(value)
    text = text.replace("\xa0", " ").replace("\u3000", " ")
    text = text.replace("\r", " ").replace("\n", " ")
    text = re.sub(r"\s+", " ", text).strip()
    if text.lower() in {"nan", "none", "null"}:
        return ""
    return text


def read_csv_with_fallback(path: Path, **kwargs: Any) -> pd.DataFrame:
    last_error: Optional[Exception] = None
    for enc in ENCODING_CANDIDATES:
        try:
            return pd.read_csv(path, encoding=enc, **kwargs).fillna("")
        except UnicodeDecodeError as exc:
            last_error = exc
            continue
    if last_error:
        raise last_error
    return pd.read_csv(path, **kwargs).fillna("")


def safe_id(text: Any) -> str:
    s = clean_text(text).lower()
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^0-9a-zA-Z_\u4e00-\u9fff:-]", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    if not s:
        s = hashlib.md5(str(text).encode("utf-8")).hexdigest()[:12]
    return s


def clean_number(value: Any) -> Optional[float]:
    text = clean_text(value)
    if not text or text in {"-", "－", "—", "--"}:
        return None
    text = text.replace("$", "").replace("＄", "").replace(",", "")
    text = text.replace("%", "").replace("％", "").replace(" ", "")
    if text.startswith("(") and text.endswith(")"):
        text = "-" + text[1:-1]
    try:
        return float(text)
    except Exception:
        return None


def fiscal_to_ad_year(value: Any) -> int:
    text = clean_text(value)
    if not text:
        return 0
    m = re.search(r"\d+", text)
    if not m:
        return 0
    y = int(m.group(0))
    return y + 1911 if 1 <= y < 1911 else y


def parse_quarter(value: Any) -> int:
    text = clean_text(value).upper()
    m = re.search(r"Q([1-4])", text)
    if m:
        return int(m.group(1))
    m = re.search(r"([1-4])", text)
    return int(m.group(1)) if m else 0


def parse_period_folder(period: str) -> Tuple[int, int, int]:
    text = clean_text(period).upper()
    m = re.search(r"(\d{3,4})Q([1-4])", text)
    if not m:
        return 0, 0, 0
    fiscal_year = int(m.group(1))
    year = fiscal_year + 1911 if fiscal_year < 1911 else fiscal_year
    quarter = int(m.group(2))
    return fiscal_year, year, quarter


def parse_company_period_from_path(path: Path, reports_dir: Path) -> Tuple[str, str, str, int, int, int]:
    """從 reports_csv_output/<company_folder>/<period>/<file> 推 company / period。"""
    try:
        rel_parts = path.relative_to(reports_dir).parts
    except Exception:
        rel_parts = path.parts

    company_folder = rel_parts[0] if len(rel_parts) >= 1 else ""
    period_folder = rel_parts[1] if len(rel_parts) >= 2 else ""

    stock_id = ""
    company_name = ""
    m = re.match(r"^(?P<code>\d{4}[A-Z]?)[_\s-]*(?P<name>.*)$", company_folder)
    if m:
        stock_id = clean_text(m.group("code"))
        company_name = clean_text(m.group("name"))
    else:
        company_name = clean_text(company_folder)

    fiscal_year, year, quarter = parse_period_folder(period_folder)
    return stock_id, company_name, period_folder, fiscal_year, year, quarter


def load_ontology(path: Optional[Path] = None) -> dict:
    """讀取風險事件 ontology。

    預設使用程式內建 DEFAULT_ONTOLOGY，避免專案目錄中舊的
    risk_event_ontology.json 覆蓋嚴格規則。只有明確傳入有效 JSON 路徑時
    才使用外部 ontology。
    """
    if path is not None and str(path).strip() and path.exists() and path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return DEFAULT_ONTOLOGY


def _matched_keywords_for_rule(text: str, rule: dict) -> List[str]:
    kws: List[str] = []
    for kw in rule.get("any_keywords", []) or rule.get("keywords", []):
        if kw and kw in text:
            kws.append(kw)
    for group in rule.get("all_keywords_any_group", []) or []:
        for kw in group:
            if kw and kw in text:
                kws.append(kw)
    return sorted(set(kws))


def match_rule(text: str, rule: dict) -> bool:
    """支援 any_keywords 與 all_keywords_any_group 的風險規則比對。

    若規則有 all_keywords_any_group，代表「每一組至少命中一個」的嚴格條件，
    例如客戶集中風險必須同時有「客戶/交易對象」與「收入端交易詞」。
    這類規則不可退回 keywords 的寬鬆 OR 比對。
    """
    text = clean_text(text)
    for kw in rule.get("exclude_keywords", []) or []:
        if kw and kw in text:
            return False

    groups = rule.get("all_keywords_any_group", []) or []
    if groups:
        return all(any(kw and kw in text for kw in group) for group in groups)

    any_keywords = rule.get("any_keywords", None)
    if any_keywords is None:
        any_keywords = rule.get("keywords", [])
    if any_keywords:
        return any(kw and kw in text for kw in any_keywords)

    return False


def match_risk_events(text: str, ontology: dict) -> List[dict]:
    """文字型 evidence 的保守風險比對。"""
    text = clean_text(text)
    matched = []
    for rule in ontology.get("risk_events", []):
        if not match_rule(text, rule):
            continue
        ev2 = dict(rule)
        ev2["matched_keywords"] = _matched_keywords_for_rule(text, rule)
        ev2["evidence_level"] = rule.get("evidence_level") or rule.get("evidence_strength") or "weak_candidate"
        matched.append(ev2)
    return matched



def parse_numeric_value_for_filter(value: str):
    s = str(value or "").strip()
    if not s or s.lower() in {"nan", "none", "null", "-", "－"}:
        return None

    neg = s.startswith("(") and s.endswith(")")
    s = s.replace(",", "").replace(" ", "")
    s = s.replace("(", "").replace(")", "")
    s = s.replace("%", "").replace("％", "")

    s = re.sub(r"[^\d.\-]", "", s)
    if not s:
        return None

    try:
        v = float(s)
    except Exception:
        return None

    return -v if neg else v


def is_noise_fact(row: dict) -> bool:
    column_header = str(row.get("column_header", ""))
    value_raw = str(row.get("value_raw", ""))
    item_name = str(row.get("item_name", ""))

    # 排除比率欄位，避免 0.00% 變成主要風險證據
    if "比率" in column_header or "%" in value_raw or "％" in value_raw:
        return True

    # 空值、null、dash 排除
    v_text = value_raw.replace(",", "").replace("(", "").replace(")", "").strip()
    if v_text.lower() in {"", "null", "nan", "none", "-", "－"}:
        return True

    # 排除數值為 0 的 fact
    v_num = parse_numeric_value_for_filter(value_raw)
    if v_num is not None and abs(v_num) < 1e-12:
        return True

    return False


def match_risk_events_from_fact(row: pd.Series, ontology: dict) -> List[dict]:
    """針對 deal_html all_table_facts 的 row 做更嚴格的風險比對。"""
    if is_noise_fact(row):
        return []

    text = fact_text_for_matching(row)
    matched: List[dict] = []
    item_name = clean_text(row.get("item_name", ""))

    for rule in ontology.get("risk_events", []):
        if not match_rule(text, rule):
            continue

        evidence_level = rule.get("evidence_level") or rule.get("evidence_strength") or "weak_candidate"

        # 合計列通常比具體交易對象弱一階。
        if item_name == "合計":
            if evidence_level == "strong":
                evidence_level = "medium"
            elif evidence_level == "medium":
                evidence_level = "weak_candidate"

        ev2 = dict(rule)
        ev2["matched_keywords"] = _matched_keywords_for_rule(text, rule)
        ev2["evidence_level"] = evidence_level
        matched.append(ev2)

    return matched


def company_node_id(stock_id: str, company_name: str) -> str:
    stock_id = clean_text(stock_id)
    if re.fullmatch(r"\d{4}[A-Z]?", stock_id):
        return f"company:{stock_id}"
    return f"company:{safe_id(company_name or stock_id or 'unknown')}"


def risk_node_id(name: str) -> str:
    return f"risk_event:{safe_id(name)}"


def evidence_node_id(evidence_id: str) -> str:
    return f"risk_evidence:{safe_id(evidence_id)}"


def financial_item_node_id(code: str, name: str) -> str:
    code = clean_text(code)
    name = clean_text(name)
    if code:
        return f"financial_item:{safe_id(code)}"
    return f"financial_item:{safe_id(name or 'unknown')}"


def add_node(nodes: Dict[str, dict], node_id: str, label: str, **props: Any) -> None:
    if node_id not in nodes:
        nodes[node_id] = {"id": node_id, "label": label, **props}
        return
    for key, value in props.items():
        if value not in ["", None] and nodes[node_id].get(key) in ["", None]:
            nodes[node_id][key] = value


def add_edge(edges: Dict[Tuple[str, str, str, str], dict], source: str, target: str, edge_type: str, edge_key: str = "", **props: Any) -> None:
    key = (source, target, edge_type, edge_key)
    if key not in edges:
        edges[key] = {"source": source, "target": target, "type": edge_type, **props}
        return
    for k, v in props.items():
        if v not in ["", None] and k not in edges[key]:
            edges[key][k] = v


def normalize_filter_values(values: Optional[str]) -> set[str]:
    if not values:
        return set()
    return {clean_text(x) for x in re.split(r"[,;\s]+", values) if clean_text(x)}


# ============================================================
# 4. Risk Event Evidence Extraction from deal_html facts
# ============================================================
def fact_text_for_matching(row: pd.Series) -> str:
    return " ".join([
        clean_text(row.get("company_name", "")),
        clean_text(row.get("period", "")),
        clean_text(row.get("table_name", "")),
        clean_text(row.get("code", "")),
        clean_text(row.get("item_name", "")),
        clean_text(row.get("column_header", "")),
        clean_text(row.get("value_raw", "")),
        clean_text(row.get("fact_text", "")),
    ])


def iter_deal_fact_evidence(
    reports_dir: Path,
    ontology: dict,
    stock_filter: Optional[set[str]] = None,
    period_filter: Optional[set[str]] = None,
) -> Iterable[dict]:
    """只讀 deal_html_datav2 產出的 *_all_table_facts.csv；不讀每張表的 *__facts.csv。"""
    if not reports_dir.exists():
        print(f"⚠️ 找不到 reports_csv_output，略過：{reports_dir}")
        return []

    fact_files = sorted(reports_dir.rglob("*_all_table_facts.csv"))
    if not fact_files:
        print(f"⚠️ 找不到 *_all_table_facts.csv，請先執行 deal_html_datav2_strip_company_suffix*.py 產生總表：{reports_dir}")
        return []

    for fact_path in fact_files:
        path_stock_id, path_company_name, path_period, path_fiscal_year, path_year, path_quarter = parse_company_period_from_path(fact_path, reports_dir)

        if stock_filter and path_stock_id and path_stock_id not in stock_filter:
            continue
        if period_filter and path_period and path_period not in period_filter:
            continue

        try:
            df = read_csv_with_fallback(fact_path, dtype=str)
        except Exception as exc:
            print(f"⚠️ 讀取失敗，略過：{fact_path} | {exc}")
            continue

        required_cols = {"table_name", "item_name", "value_raw"}
        missing = required_cols - set(df.columns)
        if missing:
            print(f"⚠️ 不是 all_table_facts 格式，略過：{fact_path} | missing={sorted(missing)}")
            continue

        for idx, row in df.iterrows():
            stock_id = clean_text(row.get("stock_code", "")) or clean_text(row.get("stock_id", "")) or path_stock_id
            company_name = clean_text(row.get("company_name", "")) or path_company_name
            period = clean_text(row.get("period", "")) or path_period

            _, year, quarter = parse_period_folder(period)
            if not year:
                year = fiscal_to_ad_year(row.get("year", "")) or path_year
            if not quarter:
                quarter = parse_quarter(row.get("quarter", "")) or path_quarter
            fiscal_year = fiscal_to_ad_year(row.get("fiscal_year", ""))
            if fiscal_year > 1911:
                fiscal_year -= 1911
            fiscal_year = fiscal_year or path_fiscal_year
            period_key = f"{year}Q{quarter}" if year and quarter else period

            match_text = fact_text_for_matching(row)
            events = match_risk_events_from_fact(row, ontology)
            if not events:
                continue

            fact_text = clean_text(row.get("fact_text", "")) or match_text
            evidence_id = f"dealfact:{stock_id}:{period}:{safe_id(fact_path.as_posix())}:{idx}"

            yield {
                "evidence_id": evidence_id,
                "evidence_source_type": "deal_html_fact",
                "stock_id": stock_id,
                "company_name": company_name,
                "period": period_key,
                "raw_period": period,
                "fiscal_year": fiscal_year,
                "year": year,
                "quarter": quarter,
                "table_name": clean_text(row.get("table_name", "")),
                "code": clean_text(row.get("code", "")),
                "item_name": clean_text(row.get("item_name", "")),
                "column_header": clean_text(row.get("column_header", "")),
                "value_raw": clean_text(row.get("value_raw", "")),
                "value_number": clean_number(row.get("value_number", "")),
                "value_type": clean_text(row.get("value_type", "")),
                "unit": clean_text(row.get("unit", "")),
                "source_file": clean_text(row.get("source_csv", "")) or fact_path.as_posix(),
                "source_fact_file": fact_path.as_posix(),
                "source_row_index": int(idx),
                "source_pdf": "",
                "page": "",
                "text": fact_text,
                "match_text": match_text,
                "events": events,
            }


# Optional: PDF clean financial CSV evidence, off by default.
def iter_financial_evidence(financial_csv: Path, ontology: dict, stock_filter: Optional[set[str]] = None) -> Iterable[dict]:
    if not financial_csv.exists():
        print(f"⚠️ 找不到 financial CSV，略過：{financial_csv}")
        return []

    df = read_csv_with_fallback(financial_csv, dtype=str)
    for idx, row in df.iterrows():
        stock_id = clean_text(row.get("company_code", ""))
        if stock_filter and stock_id and stock_id not in stock_filter:
            continue
        company_name = clean_text(row.get("company_name", "")) or clean_text(row.get("company", ""))
        year = fiscal_to_ad_year(row.get("fiscal_year", ""))
        quarter = parse_quarter(row.get("quarter", ""))
        period = f"{year}Q{quarter}" if year and quarter else ""
        item_name = clean_text(row.get("item_name", ""))
        code = clean_text(row.get("item_code", ""))
        column_header = clean_text(row.get("column_header", ""))
        value_raw = clean_text(row.get("value_raw", ""))
        source_pdf = clean_text(row.get("source_pdf", ""))
        source_file = clean_text(row.get("source_csv", ""))
        page = clean_text(row.get("page", ""))
        row_context = clean_text(row.get("row_context", ""))

        evidence_text = " ".join([company_name, stock_id, period, code, item_name, row_context, column_header, value_raw, source_pdf, f"page:{page}"])
        events = match_risk_events(evidence_text, ontology)
        if not events:
            continue

        yield {
            "evidence_id": f"financial:{stock_id}:{period}:{idx}",
            "evidence_source_type": "financial_statement",
            "stock_id": stock_id,
            "company_name": company_name,
            "period": period,
            "raw_period": period,
            "fiscal_year": clean_text(row.get("fiscal_year", "")),
            "year": year,
            "quarter": quarter,
            "table_name": clean_text(row.get("source_table_id", "")),
            "code": code,
            "item_name": item_name,
            "column_header": column_header,
            "value_raw": value_raw,
            "value_number": clean_number(row.get("value", "")),
            "value_type": clean_text(row.get("value_type", "")),
            "unit": clean_text(row.get("unit", "")),
            "source_file": source_file,
            "source_fact_file": "",
            "source_row_index": int(idx),
            "source_pdf": source_pdf,
            "page": page,
            "text": evidence_text,
            "match_text": evidence_text,
            "events": events,
        }


# ============================================================
# 5. Risk Event Graph Build / Output
# ============================================================
def build_risk_graph(evidence_rows: List[dict], ontology: dict) -> Tuple[List[dict], List[dict]]:
    nodes: Dict[str, dict] = {}
    edges: Dict[Tuple[str, str, str, str], dict] = {}

    root_id = "risk_event_network:financial_risks"
    add_node(nodes, root_id, "RiskEventNetwork", name="財報風險事件圖譜", source="deal_html_all_table_facts")

    # RiskEvent nodes and ontology edges.
    for ev in ontology.get("risk_events", []):
        rid = risk_node_id(ev.get("name", ""))
        add_node(
            nodes,
            rid,
            "RiskEvent",
            name=ev.get("name", ""),
            risk_type=ev.get("risk_type", ""),
            evidence_strength=ev.get("evidence_strength", "candidate"),
            keywords=";".join(ev.get("keywords", [])),
        )
        add_edge(edges, root_id, rid, "HAS_RISK_EVENT", edge_key=rid)

    for src, dst, rel_type in ontology.get("causal_edges", []):
        src_id = risk_node_id(src)
        dst_id = risk_node_id(dst)
        add_node(nodes, src_id, "RiskEvent", name=src)
        target_label = "FinancialImpact" if rel_type == "AFFECTS" else "RiskEvent"
        add_node(nodes, dst_id, target_label, name=dst)
        add_edge(edges, src_id, dst_id, rel_type, edge_key=f"{src}->{dst}:{rel_type}")

    # Evidence nodes and evidence links.
    for evd in evidence_rows:
        stock_id = clean_text(evd.get("stock_id", ""))
        company_name = clean_text(evd.get("company_name", ""))
        company_id = company_node_id(stock_id, company_name)
        evidence_id = evidence_node_id(evd["evidence_id"])
        period = clean_text(evd.get("period", ""))
        period_id = f"report_period:{safe_id(period or 'unknown')}"
        item_name = clean_text(evd.get("item_name", ""))
        item_code = clean_text(evd.get("code", ""))
        item_id = financial_item_node_id(item_code, item_name or evd.get("table_name", "unknown"))

        add_node(nodes, company_id, "Company", name=company_name, stock_code=stock_id)
        add_node(nodes, period_id, "ReportPeriod", name=period, year=evd.get("year", ""), quarter=evd.get("quarter", ""), raw_period=evd.get("raw_period", ""))
        add_node(nodes, item_id, "FinancialItem", name=item_name or evd.get("table_name", ""), code=item_code, table_name=evd.get("table_name", ""))
        evd_risk_levels = sorted({clean_text(r.get("evidence_level", "weak_candidate")) for r in evd.get("events", []) if clean_text(r.get("evidence_level", ""))})
        evd_matched_keywords = sorted({kw for r in evd.get("events", []) for kw in r.get("matched_keywords", [])})
        evidence_display_name = "｜".join([
            clean_text(evd.get("item_name", "")) or clean_text(evd.get("table_name", "")) or "RiskEvidence",
            clean_text(evd.get("value_raw", "")),
            clean_text(evd.get("table_name", "")),
        ]).strip("｜") or evd["evidence_id"]

        add_node(
            nodes,
            evidence_id,
            "RiskEvidence",
            name=evidence_display_name[:120],
            evidence_id=evd["evidence_id"],
            evidence_levels=";".join(evd_risk_levels),
            matched_keywords=";".join(evd_matched_keywords),
            evidence_source_type=evd.get("evidence_source_type", ""),
            stock_id=stock_id,
            company_name=company_name,
            period=period,
            raw_period=evd.get("raw_period", ""),
            table_name=evd.get("table_name", ""),
            code=item_code,
            item_name=item_name,
            column_header=evd.get("column_header", ""),
            value_raw=evd.get("value_raw", ""),
            value_number="" if evd.get("value_number") is None else evd.get("value_number"),
            value_type=evd.get("value_type", ""),
            unit=evd.get("unit", ""),
            source_file=evd.get("source_file", ""),
            source_fact_file=evd.get("source_fact_file", ""),
            source_row_index=evd.get("source_row_index", ""),
            source_pdf=evd.get("source_pdf", ""),
            page=evd.get("page", ""),
            text=evd.get("text", ""),
        )

        add_edge(edges, company_id, period_id, "HAS_PERIOD", edge_key=f"{stock_id}:{period}", year=evd.get("year", ""), quarter=evd.get("quarter", ""))
        add_edge(edges, company_id, evidence_id, "HAS_RISK_EVIDENCE", edge_key=evd["evidence_id"], period=period, source_file=evd.get("source_file", ""))
        add_edge(edges, company_id, item_id, "HAS_FINANCIAL_ITEM", edge_key=f"{stock_id}:{period}:{item_id}", period=period, item_name=item_name)
        add_edge(edges, evidence_id, item_id, "HAS_FINANCIAL_ITEM", edge_key=evd["evidence_id"], item_name=item_name, value_raw=evd.get("value_raw", ""))

        for risk in evd.get("events", []):
            risk_id = risk_node_id(risk.get("name", ""))
            matched_keywords = ";".join(risk.get("matched_keywords", []))
            add_node(nodes, risk_id, "RiskEvent", name=risk.get("name", ""), risk_type=risk.get("risk_type", ""), keywords=";".join(risk.get("keywords", [])))
            add_edge(edges, evidence_id, risk_id, "EVIDENCES", edge_key=f"{evd['evidence_id']}->{risk_id}", matched_risk=risk.get("name", ""), matched_keywords=matched_keywords, evidence_level=risk.get("evidence_level", "weak_candidate"), period=period)
            add_edge(edges, company_id, risk_id, "EXPOSED_TO", edge_key=f"{stock_id}:{period}:{risk_id}", period=period, evidence_id=evd["evidence_id"], matched_keywords=matched_keywords, evidence_level=risk.get("evidence_level", "weak_candidate"))

    return list(nodes.values()), list(edges.values())


def collect_fieldnames(rows: List[dict], preferred: Optional[List[str]] = None) -> List[str]:
    fields = list(preferred or [])
    for row in rows:
        for key in row.keys():
            if key not in fields:
                fields.append(key)
    return fields


def write_csv(path: Path, rows: List[dict], fieldnames: Optional[List[str]] = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = fieldnames or collect_fieldnames(rows)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_jsonl(path: Path, rows: List[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def flatten_evidence_row(evd: dict) -> dict:
    out = {k: v for k, v in evd.items() if k != "events"}
    out["matched_risks"] = ";".join(clean_text(r.get("name", "")) for r in evd.get("events", []))
    out["matched_risk_levels"] = ";".join(
        f"{clean_text(r.get('name', ''))}:{clean_text(r.get('evidence_level', 'weak_candidate'))}"
        for r in evd.get("events", [])
    )
    out["matched_keywords"] = ";".join(sorted({kw for r in evd.get("events", []) for kw in r.get("matched_keywords", [])}))
    return out


def write_risk_outputs(output_dir: Path, evidence_rows: List[dict], nodes: List[dict], edges: List[dict]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "risk_evidence_table.csv", [flatten_evidence_row(r) for r in evidence_rows])
    write_csv(output_dir / "graph_nodes.csv", nodes)
    write_csv(output_dir / "graph_edges.csv", edges)
    write_jsonl(output_dir / "graph_nodes.jsonl", nodes)
    write_jsonl(output_dir / "graph_edges.jsonl", edges)

    neo_nodes = []
    for n in nodes:
        row = {"id:ID": n.get("id", ""), ":LABEL": n.get("label", "")}
        row.update({k: v for k, v in n.items() if k not in {"id", "label"}})
        neo_nodes.append(row)

    neo_edges = []
    for e in edges:
        row = {":START_ID": e.get("source", ""), ":END_ID": e.get("target", ""), ":TYPE": e.get("type", "")}
        row.update({k: v for k, v in e.items() if k not in {"source", "target", "type"}})
        neo_edges.append(row)

    write_csv(output_dir / "neo4j_nodes.csv", neo_nodes)
    write_csv(output_dir / "neo4j_relationships.csv", neo_edges)


def try_write_risk_pyvis_html(output_dir: Path, nodes: List[dict], edges: List[dict], no_html: bool = False) -> None:
    if no_html:
        return
    try:
        from pyvis.network import Network
    except Exception:
        print("ℹ️ 未安裝 pyvis，略過 HTML 圖譜。若需要可執行：pip install pyvis")
        return

    color_map = {
        "RiskEventNetwork": "#EAECEE",
        "Company": "#F9E79F",
        "ReportPeriod": "#D6EAF8",
        "RiskEvidence": "#FADBD8",
        "RiskEvent": "#F5B7B1",
        "FinancialItem": "#A9DFBF",
        "FinancialImpact": "#D7BDE2",
    }
    net = Network(height="900px", width="100%", directed=True, notebook=False)
    net.toggle_physics(True)

    for n in nodes:
        label = n.get("label", "")
        display = n.get("name", n.get("id", ""))
        if label == "Company" and n.get("stock_code"):
            display = f"{n.get('stock_code')} {display}"
        title = "<br>".join(f"{k}: {v}" for k, v in n.items() if v not in ["", None])
        net.add_node(n["id"], label=display, title=title, color=color_map.get(label, "#D5DBDB"), shape="dot" if label == "Company" else "box")

    for e in edges:
        title = "<br>".join(f"{k}: {v}" for k, v in e.items() if v not in ["", None])
        net.add_edge(e["source"], e["target"], label=e.get("type", ""), title=title)

    net.write_html(str(output_dir / "risk_event_graph.html"))


# ============================================================
# 6. Optional Neo4j import
# ============================================================
ALLOWED_LABELS = {
    "GraphNode",
    "RiskEventNetwork",
    "Company",
    "ReportPeriod",
    "RiskEvidence",
    "RiskEvent",
    "FinancialItem",
    "FinancialImpact",
}
ALLOWED_REL_TYPES = {
    "HAS_RISK_EVENT",
    "MAY_CAUSE",
    "AFFECTS",
    "HAS_PERIOD",
    "HAS_RISK_EVIDENCE",
    "HAS_FINANCIAL_ITEM",
    "EVIDENCES",
    "EXPOSED_TO",
}


def sanitize_symbol(s: str, allowed: set[str], fallback: str) -> str:
    s = clean_text(s)
    if s in allowed:
        return s
    return fallback


def import_to_neo4j(nodes: List[dict], edges: List[dict], clear_risk_only: bool = False) -> None:
    try:
        from neo4j import GraphDatabase
    except Exception as exc:
        raise RuntimeError("未安裝 neo4j 套件，請先 pip install neo4j，或不要加 --import-neo4j") from exc

    uri = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "password")
    database = os.getenv("NEO4J_DATABASE", "neo4j")

    driver = GraphDatabase.driver(uri, auth=(user, password))

    def create_constraints(tx):
        tx.run("""
        CREATE CONSTRAINT graph_node_id_unique IF NOT EXISTS
        FOR (n:GraphNode)
        REQUIRE n.id IS UNIQUE
        """)

    def clear(tx):
        tx.run("""
        MATCH (n)
        WHERE any(l IN labels(n) WHERE l IN [
            "RiskEventNetwork", "RiskEvent", "RiskEvidence", "FinancialItem", "FinancialImpact", "ReportPeriod"
        ])
        DETACH DELETE n
        """)

    def upsert_node(tx, row: dict):
        node_id = clean_text(row.get("id", ""))
        if not node_id:
            return
        label = sanitize_symbol(row.get("label", ""), ALLOWED_LABELS, "GraphNode")
        props = {k: clean_text(v) for k, v in row.items() if k not in {"id", "label"} and clean_text(v)}
        props["id"] = node_id
        cypher = f"""
        MERGE (n:GraphNode:`{label}` {{id: $id}})
        SET n += $props
        """
        tx.run(cypher, id=node_id, props=props)

    def upsert_edge(tx, row: dict):
        source = clean_text(row.get("source", ""))
        target = clean_text(row.get("target", ""))
        if not source or not target:
            return
        rel_type = sanitize_symbol(row.get("type", ""), ALLOWED_REL_TYPES, "RELATED_TO")
        raw_key = "|".join([source, target, rel_type, clean_text(row.get("edge_key", ""))])
        edge_key = hashlib.md5(raw_key.encode("utf-8")).hexdigest()
        props = {k: clean_text(v) for k, v in row.items() if k not in {"source", "target", "type"} and clean_text(v)}
        props["edge_key"] = edge_key
        cypher = f"""
        MATCH (a:GraphNode {{id: $source}})
        MATCH (b:GraphNode {{id: $target}})
        MERGE (a)-[r:`{rel_type}` {{edge_key: $edge_key}}]->(b)
        SET r += $props
        """
        tx.run(cypher, source=source, target=target, edge_key=edge_key, props=props)

    with driver.session(database=database) as session:
        session.execute_write(create_constraints)
        if clear_risk_only:
            session.execute_write(clear)
        for n in nodes:
            session.execute_write(upsert_node, n)
        for e in edges:
            session.execute_write(upsert_edge, e)

    driver.close()
    print("✅ 已匯入 Neo4j")
    print(f"Neo4j: {uri} database={database}")


# ============================================================
# 7. Run targets
# ============================================================
def run_risk_event(args: argparse.Namespace) -> None:
    reports_dir = Path(args.reports_dir)
    ontology_path = Path(args.risk_ontology) if args.risk_ontology else None
    output_dir = Path(args.risk_output_dir)

    stock_filter = normalize_filter_values(args.stock_ids)
    period_filter = normalize_filter_values(args.periods)

    ontology = load_ontology(ontology_path)
    evidence_rows: List[dict] = []
    evidence_rows.extend(iter_deal_fact_evidence(reports_dir, ontology, stock_filter=stock_filter, period_filter=period_filter) or [])

    if args.include_financial:
        evidence_rows.extend(iter_financial_evidence(Path(args.financial_csv), ontology, stock_filter=stock_filter) or [])

    nodes, edges = build_risk_graph(evidence_rows, ontology)
    write_risk_outputs(output_dir, evidence_rows, nodes, edges)
    try_write_risk_pyvis_html(output_dir, nodes, edges, no_html=args.no_html)

    if args.import_neo4j:
        import_to_neo4j(nodes, edges, clear_risk_only=args.clear_risk_only)

    company_count = len({r.get("stock_id", "") for r in evidence_rows if r.get("stock_id")})
    risk_count = len({risk.get("name", "") for r in evidence_rows for risk in r.get("events", [])})

    print("\n✅ 風險事件圖譜建立完成")
    print(f"來源：deal_html all_table_facts")
    print(f"reports_csv_output：{reports_dir.resolve()}")
    
    if ontology_path is not None and ontology_path.exists():
        print(f"ontology：{ontology_path.resolve()} (外部檔)")
    else:
        print("ontology：使用內建 DEFAULT_ONTOLOGY（未讀取外部 risk_event_ontology.json）")
    print(f"輸出資料夾：{output_dir.resolve()}")
    print(f"公司數：{company_count}")
    print(f"風險事件種類數：{risk_count}")
    print(f"風險 evidence 筆數：{len(evidence_rows)}")
    print(f"節點數：{len(nodes)}")
    print(f"關係數：{len(edges)}")
    print("\n主要輸出：")
    print(f"- {output_dir / 'risk_evidence_table.csv'}")
    print(f"- {output_dir / 'neo4j_nodes.csv'}")
    print(f"- {output_dir / 'neo4j_relationships.csv'}")
    if (output_dir / "risk_event_graph.html").exists():
        print(f"- {output_dir / 'risk_event_graph.html'}")




# ============================================================
# 8. Unified runner / CLI / Neo4j import
# ============================================================
_DISPLAY_NAMES = {
    "investment": "被投資公司關係圖譜",
    "related_party": "關係人圖譜",
    "supply_chain": "半導體產業鏈圖譜",
    "risk_event": "風險事件圖譜",
}
_VALID_TARGETS = ("investment", "related_party", "supply_chain", "risk_event")

_TARGET_OUTPUT_DIRS = {
    "investment": Path("./investment_graph_output"),
    "related_party": Path("./related_party_graph_output"),
    "supply_chain": Path("./supply_chain_graph_output"),
    "risk_event": Path("./risk_event_graph_output"),
}

_ALLOWED_LABEL_RE = re.compile(r"^[A-Za-z_][0-9A-Za-z_]*$")
_ALLOWED_REL_RE = re.compile(r"^[A-Za-z_][0-9A-Za-z_]*$")


def _clean_symbol(value: Any, fallback: str) -> str:
    s = str(value or "").strip()
    if not s:
        return fallback
    s = re.sub(r"[^0-9A-Za-z_]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    if not s or not re.match(r"^[A-Za-z_]", s):
        return fallback
    return s


def _csv_value(value: Any) -> str:
    if value is None:
        return ""
    s = str(value).strip()
    if s.lower() in {"nan", "none", "null"}:
        return ""
    return s


def load_embedded_module(name: str) -> Dict[str, object]:
    if name not in _EMBEDDED_SOURCES:
        raise ValueError(f"未知的建圖目標：{name}")

    module_name = f"_embedded_{name}_builder"
    module = ModuleType(module_name)
    module.__file__ = f"<embedded {name} builder>"

    # dataclasses 在處理 postponed annotations 時會查 sys.modules[__module__]。
    sys.modules[module_name] = module
    exec(compile(_EMBEDDED_SOURCES[name], module.__file__, "exec"), module.__dict__)
    return module.__dict__


def configure_module(ns: Dict[str, object], name: str, args: argparse.Namespace) -> None:
    """覆蓋原始 script 的全域設定，讓各建圖流程可由同一個 CLI 控制。"""
    if name in {"investment", "related_party"}:
        ns["INPUT_DIR"] = Path(args.reports_dir)
    elif name == "supply_chain":
        ns["INPUT_TXT"] = Path(args.supply_chain_txt)

    # 原始 investment / related_party 內部以 TEST_STOCK_IDS / TEST_PERIODS 控制篩選。
    if name in {"investment", "related_party"}:
        if "TEST_STOCK_IDS" in ns:
            ns["TEST_STOCK_IDS"] = normalize_filter_values(args.stock_ids)
        if "TEST_PERIODS" in ns:
            ns["TEST_PERIODS"] = normalize_filter_values(args.periods)

    if args.no_html and "WRITE_HTML_GRAPH" in ns:
        ns["WRITE_HTML_GRAPH"] = False


def _output_dir_for_embedded(ns: Dict[str, object], name: str) -> Path:
    raw = ns.get("OUTPUT_DIR")
    if raw:
        try:
            return Path(raw)
        except Exception:
            pass
    return _TARGET_OUTPUT_DIRS[name]


def _neo4j_driver(args: argparse.Namespace):
    try:
        from neo4j import GraphDatabase
    except Exception as exc:
        raise RuntimeError("未安裝 neo4j 套件，請先 pip install neo4j，或不要加 --import-neo4j") from exc

    uri = args.neo4j_uri or os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687")
    user = args.neo4j_user or os.getenv("NEO4J_USER", "neo4j")
    password = args.neo4j_password or os.getenv("NEO4J_PASSWORD", "password")
    return GraphDatabase.driver(uri, auth=(user, password))


def _neo4j_database(args: argparse.Namespace) -> str:
    return args.neo4j_database or os.getenv("NEO4J_DATABASE", "neo4j")


def _apply_neo4j_env(args: argparse.Namespace) -> None:
    if args.neo4j_uri:
        os.environ["NEO4J_URI"] = args.neo4j_uri
    if args.neo4j_user:
        os.environ["NEO4J_USER"] = args.neo4j_user
    if args.neo4j_password:
        os.environ["NEO4J_PASSWORD"] = args.neo4j_password
    if args.neo4j_database:
        os.environ["NEO4J_DATABASE"] = args.neo4j_database


def _create_neo4j_constraint(tx) -> None:
    tx.run("""
    CREATE CONSTRAINT graph_node_id_unique IF NOT EXISTS
    FOR (n:GraphNode)
    REQUIRE n.id IS UNIQUE
    """)


def _clear_neo4j_all(args: argparse.Namespace) -> None:
    driver = _neo4j_driver(args)
    database = _neo4j_database(args)
    with driver.session(database=database) as session:
        session.execute_write(lambda tx: tx.run("MATCH (n:GraphNode) DETACH DELETE n"))
    driver.close()
    print("✅ 已清除 Neo4j 內所有 GraphNode 圖譜")


def _clear_neo4j_target(args: argparse.Namespace, target: str) -> None:
    driver = _neo4j_driver(args)
    database = _neo4j_database(args)

    cypher_by_target = {
        "related_party": """
            MATCH ()-[r:HAS_RELATED_PARTY|HAS_RELATION_TYPE|HAS_RELATED_PARTY_TRANSACTION|HAS_TRANSACTION_ACCOUNT|HAS_TRANSACTION_PARTY|RELATED_PARTY_TRANSACTION_WITH|HAS_RELATED_PARTY_ACCOUNT]->()
            DELETE r;
            MATCH (n:GraphNode)
            WHERE n:RelatedParty OR n:RelationType OR n:RelatedPartyNetwork OR n:RelatedPartyTransaction OR n:RelatedPartyAccount
            DETACH DELETE n;
        """,
        "investment": """
            MATCH ()-[r:DISCLOSES_INVESTOR|INVESTS_IN|LOCATED_IN|HAS_BUSINESS]->()
            DELETE r;
            MATCH (n:GraphNode)
            WHERE n:InvestmentNetwork OR n:Location OR n:Business
            DETACH DELETE n;
        """,
        "supply_chain": """
            MATCH ()-[r:HAS_STAGE|HAS_SEGMENT|HAS_COMPANY]->()
            DELETE r;
            MATCH (n:GraphNode)
            WHERE n:IndustryChain OR n:Stage OR n:Segment
            DETACH DELETE n;
        """,
        "risk_event": """
            MATCH (n:GraphNode)
            WHERE n:RiskEventNetwork OR n:RiskEvent OR n:RiskEvidence OR n:FinancialItem OR n:FinancialImpact OR n:ReportPeriod
            DETACH DELETE n;
        """,
    }
    cypher = cypher_by_target.get(target)
    if not cypher:
        driver.close()
        raise ValueError(f"未知清除目標：{target}")

    with driver.session(database=database) as session:
        for stmt in [s.strip() for s in cypher.split(";") if s.strip()]:
            session.execute_write(lambda tx, q=stmt: tx.run(q))
    driver.close()
    print(f"✅ 已清除 Neo4j 舊 {target} 圖譜；Company 節點保留")


def _read_csv_dicts(path: Path) -> List[dict]:
    if not path.exists():
        raise FileNotFoundError(f"找不到 Neo4j CSV：{path}")
    rows: List[dict] = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({k: _csv_value(v) for k, v in row.items()})
    return rows


def _upsert_node_tx(tx, row: dict) -> None:
    node_id = _csv_value(row.get("id:ID") or row.get("id"))
    if not node_id:
        return
    raw_label = _csv_value(row.get(":LABEL") or row.get("label") or "GraphNode")
    # 支援 CSV 中可能的多 label，但全部做 symbol 清洗。
    labels = [_clean_symbol(x, "GraphNode") for x in re.split(r"[;:|,\s]+", raw_label) if _csv_value(x)]
    if "GraphNode" not in labels:
        labels.insert(0, "GraphNode")
    label_clause = ":".join(f"`{x}`" for x in labels)
    props = {k: v for k, v in row.items() if k not in {"id:ID", "id", ":LABEL", "label"} and _csv_value(v)}
    props["id"] = node_id
    tx.run(f"MERGE (n:{label_clause} {{id: $id}}) SET n += $props", id=node_id, props=props)


def _upsert_rel_tx(tx, row: dict) -> None:
    source = _csv_value(row.get(":START_ID") or row.get("source"))
    target = _csv_value(row.get(":END_ID") or row.get("target"))
    rel_type = _clean_symbol(row.get(":TYPE") or row.get("type"), "RELATED_TO")
    if not source or not target:
        return
    props = {k: v for k, v in row.items() if k not in {":START_ID", ":END_ID", ":TYPE", "source", "target", "type"} and _csv_value(v)}
    raw_key = "|".join([source, target, rel_type, json.dumps(props, sort_keys=True, ensure_ascii=False)])
    props["edge_key"] = hashlib.md5(raw_key.encode("utf-8")).hexdigest()
    tx.run(
        f"""
        MATCH (a:GraphNode {{id: $source}})
        MATCH (b:GraphNode {{id: $target}})
        MERGE (a)-[r:`{rel_type}` {{edge_key: $edge_key}}]->(b)
        SET r += $props
        """,
        source=source,
        target=target,
        edge_key=props["edge_key"],
        props=props,
    )



# ============================================================
# Related-party transaction evidence augmentation
# ============================================================
# 關係人圖譜檔案白名單。
# 2026-06-07 依使用者最新要求：related_party 只使用以下五類表：
#   1. 關係人名稱及關係.csv                      -> 原 related_party parser 掃描
#   2. 母子公司間業務關係及重要交易往來情形.csv  -> transaction augmentation 掃描
#   3. 轉投資大陸地區之事業相關資訊.csv          -> transaction augmentation 掃描
#   4. 應付關係人款項.csv                        -> transaction augmentation 掃描
#   5. 應收關係人款項.csv                        -> transaction augmentation 掃描
#
# 注意：這裡只吃原始表格 CSV，不吃 *_facts.csv / *_all_table_facts.csv / *_numeric_facts.csv。
RELATED_PARTY_TRANSACTION_FILE_KEYWORDS = [
    "母子公司間業務關係及重要交易往來情形", "母子公司間業務關係", "重要交易往來情形",
    "轉投資大陸地區之事業相關資訊", "轉投資大陸地區", "大陸地區之事業相關資訊",
    "應付關係人款項",
    "應收關係人款項",
]

# 關係人主檔「關係人名稱及關係.csv」由原 related_party parser 掃描，
# 不進入交易增補 parser，避免重複產生 transaction 節點。
# *_facts.csv 等衍生表一律排除，確保只吃使用者指定的原始 CSV。
RELATED_PARTY_TRANSACTION_EXCLUDE_FILE_KEYWORDS = [
    "關係人名稱及關係", "關係人名稱關係",
    "_facts", "facts", "all_table_facts", "numeric_facts", "coverage_report", "optimized",
    "source_table_index", "xbrl_notes", "xbrl_note", "Independent_Auditors", "會計師查核",
    "應收款項之備抵損失變動資訊", "應收款項之帳齡分析",
]

RELATED_PARTY_CATEGORY_WORDS = {
    "母公司", "子公司", "關聯企業", "關係企業", "合資", "主要管理階層", "具重大影響力",
    "其他關係人", "其他關係企業", "實質關係人", "關係人", "關聯公司",
}

AMOUNT_FIELD_HINTS = [
    "本期", "去年同期", "本期累計", "去年同期累計", "期末餘額", "期初餘額", "金額",
    "帳面金額", "取得價款", "處分價款", "付款金額", "收款金額", "交易金額",
    "value", "amount", "餘額", "合計",
]


def _rt_clean_text(value: Any) -> str:
    if value is None:
        return ""
    s = str(value).replace("\xa0", " ").replace("\u3000", " ")
    s = s.replace("\r", " ").replace("\n", " ")
    s = re.sub(r"\s+", " ", s).strip()
    if s.lower() in {"nan", "none", "null"}:
        return ""
    return s


def _rt_norm(text: Any) -> str:
    s = _rt_clean_text(text)
    s = s.replace("…", "").replace("...", "")
    return re.sub(r"[\s_、，,。．.（）()【】\[\]\\/\-]+", "", s)


def _rt_safe_id(text: Any) -> str:
    s = _rt_clean_text(text).lower()
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^0-9a-zA-Z_\u4e00-\u9fff:-]", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    if not s:
        s = hashlib.md5(str(text).encode("utf-8")).hexdigest()[:12]
    return s


def _rt_normalize_party_key(name: str) -> str:
    s = _rt_clean_text(name)
    s_upper = s.upper()
    suffixes = [
        "股份有限公司及其子公司", "股份有限公司及子公司", "股份有限公司", "有限公司",
        "(股)公司", "（股）公司", "公司", "CORPORATION", "CORP.", "CORP",
        "LTD.", "LTD", "LIMITED",
    ]
    for suf in suffixes:
        s = s.replace(suf, "")
        s_upper = s_upper.replace(suf, "")
    if re.search(r"[A-Za-z]", s_upper):
        s = s_upper
    return re.sub(r"[\s\-_()（）.,，。]", "", s).strip()


def _rt_related_party_node_id(name: str) -> str:
    return f"related_party:{_rt_safe_id(_rt_normalize_party_key(name) or name)}"


def _rt_relation_type_node_id(category: str) -> str:
    return f"relation_type:{_rt_safe_id(category or '未分類')}"


def _rt_company_node_id(stock_id: str, company_name: str = "") -> str:
    stock_id = _rt_clean_text(stock_id)
    if re.fullmatch(r"\d{4}[A-Z]?", stock_id):
        return f"company:{stock_id}"
    return f"company_name:{_rt_safe_id(_rt_normalize_party_key(company_name) or company_name or stock_id)}"


def _rt_account_node_id(account: str) -> str:
    return f"related_party_account:{_rt_safe_id(account or '未分類科目')}"


def _rt_transaction_node_id(*parts: Any) -> str:
    raw = "|".join(_rt_clean_text(x) for x in parts)
    return f"related_party_txn:{hashlib.md5(raw.encode('utf-8')).hexdigest()}"


def _rt_parse_company_period_from_path(path: Path, reports_dir: Path) -> Tuple[str, str, str, int, int]:
    try:
        rel_parts = path.relative_to(reports_dir).parts
    except Exception:
        rel_parts = path.parts
    company_folder = rel_parts[0] if len(rel_parts) >= 1 else ""
    period_folder = rel_parts[1] if len(rel_parts) >= 2 else ""
    stock_id = ""
    company_name = ""
    m = re.match(r"^(?P<code>\d{4}[A-Z]?)[_\s-]*(?P<name>.*)$", company_folder)
    if m:
        stock_id = _rt_clean_text(m.group("code"))
        company_name = _rt_clean_text(m.group("name"))
    else:
        company_name = _rt_clean_text(company_folder)
    year = 0
    quarter = 0
    pm = re.search(r"(\d{3,4})Q([1-4])", period_folder.upper())
    if pm:
        y = int(pm.group(1))
        year = y + 1911 if y < 1911 else y
        quarter = int(pm.group(2))
    return stock_id, company_name, period_folder, year, quarter


def _rt_is_related_party_transaction_file(path: Path) -> bool:
    if path.suffix.lower() != ".csv":
        return False

    # 用 stem 判斷，避免 .csv 副檔名干擾；同時保留 *_facts.csv。
    # 但排除 all_table_facts / numeric_facts / index / coverage 類彙整檔。
    name_norm = _rt_norm(path.stem)
    if any(_rt_norm(k) in name_norm for k in RELATED_PARTY_TRANSACTION_EXCLUDE_FILE_KEYWORDS):
        return False

    return any(_rt_norm(k) in name_norm for k in RELATED_PARTY_TRANSACTION_FILE_KEYWORDS)


def _rt_infer_account_from_filename(path: Path) -> str:
    stem = path.stem
    stem = re.sub(r"^\d{4}[A-Z]?_\d{3,4}Q[1-4]_", "", stem, flags=re.I)
    stem = re.sub(r"_facts$|_numeric_facts$", "", stem)
    stem = _rt_clean_text(stem)
    mapping = [
        ("母子公司間業務關係及重要交易往來情形", ["母子公司間業務關係及重要交易往來情形", "母子公司間業務關係", "重要交易往來情形"]),
        ("轉投資大陸地區之事業相關資訊", ["轉投資大陸地區之事業相關資訊", "轉投資大陸地區", "大陸地區之事業相關資訊"]),
        ("應付關係人款項", ["應付關係人款項"]),
        ("應收關係人款項", ["應收關係人款項"]),
    ]
    norm = _rt_norm(stem)
    for canonical, aliases in mapping:
        if any(_rt_norm(a) in norm for a in aliases):
            return canonical
    return stem or "關係人交易"


def _rt_read_csv_table(path: Path) -> List[List[str]]:
    last_error: Optional[Exception] = None
    for enc in ["utf-8-sig", "utf-8", "cp950", "big5"]:
        try:
            rows: List[List[str]] = []
            with path.open("r", encoding=enc, newline="") as f:
                reader = csv.reader(f)
                for row in reader:
                    rows.append([_rt_clean_text(x) for x in row])
            return rows
        except UnicodeDecodeError as exc:
            last_error = exc
            continue
    if last_error:
        raise last_error
    return []


def _rt_looks_like_header(row: List[str]) -> bool:
    text = " ".join(row)
    header_hits = ["帳列項目", "關係人類別", "關係人名稱", "本期", "去年同期", "期末餘額", "金額", "項目"]
    return sum(1 for k in header_hits if k in text) >= 2


def _rt_parse_key_value_text(text: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    if "=" not in text:
        return out
    parts = re.split(r"\s*[|｜;；]\s*", text)
    for part in parts:
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        k = _rt_clean_text(k)
        v = _rt_clean_text(v)
        if k:
            out[k] = v
    return out


def _rt_is_numeric_like(value: str) -> bool:
    s = _rt_clean_text(value)
    if not s or s in {"-", "－", "—", "--"}:
        return False
    s2 = s.replace(",", "").replace("%", "").replace("％", "").strip()
    if s2.startswith("(") and s2.endswith(")"):
        s2 = "-" + s2[1:-1]
    return bool(re.fullmatch(r"-?\d+(?:\.\d+)?", s2))


def _rt_first_number(value: str) -> str:
    s = _rt_clean_text(value)
    m = re.search(r"\(?-?\d[\d,]*(?:\.\d+)?\)?", s)
    return m.group(0) if m else ""


def _rt_is_note_or_bad_name(value: str) -> bool:
    s = _rt_clean_text(value)
    if not s:
        return True
    if s in {"說明", "註", "註一", "註二", "附註", "備註", "項目", "名稱", "合計", "總計"}:
        return True
    if s.startswith(("註：", "註:", "註一：", "註二：", "說明：", "備註：", "附註：")):
        return True
    return False


def _rt_classify_category(value: str) -> str:
    s = _rt_clean_text(value)
    if not s:
        return ""
    rules = [
        ("母公司", ["母公司", "最終母公司"]),
        ("子公司", ["子公司"]),
        ("關聯企業", ["關聯企業", "關係企業", "關聯公司", "採用權益法"]),
        ("合資", ["合資"]),
        ("主要管理階層", ["主要管理階層", "董事", "監察人", "經理人"]),
        ("具重大影響力", ["重大影響"]),
        ("其他關係人", ["其他關係人", "其他關係", "其他關係企業"]),
        ("實質關係人", ["實質關係"]),
    ]
    for category, kws in rules:
        if any(k in s for k in kws):
            return category
    if s in RELATED_PARTY_CATEGORY_WORDS:
        return s
    return ""


def _rt_build_row_mapping(row: List[str], header: Optional[List[str]], account_from_file: str) -> Dict[str, str]:
    joined = " | ".join(x for x in row if x)
    kv = _rt_parse_key_value_text(joined)
    if kv:
        return kv

    out: Dict[str, str] = {}
    if header:
        for i, h in enumerate(header):
            h = _rt_clean_text(h) or f"col_{i}"
            if i < len(row):
                out[h] = _rt_clean_text(row[i])
        return out

    values = [_rt_clean_text(x) for x in row]
    values = values + [""] * max(0, 4 - len(values))
    first, second = values[0], values[1]

    # 若第一欄看起來是類別/名稱，第二欄就是金額，則科目採檔名。
    if first and (_rt_classify_category(first) or _rt_is_numeric_like(second)):
        out["帳列項目"] = account_from_file
        out["關係人類別/名稱"] = first
        for i, v in enumerate(values[1:], start=1):
            out[f"value_{i}"] = v
    else:
        out["帳列項目"] = first or account_from_file
        out["關係人類別/名稱"] = second
        for i, v in enumerate(values[2:], start=2):
            out[f"value_{i}"] = v
    return out


def _rt_pick_field(mapping: Dict[str, str], candidates: Sequence[str]) -> str:
    norm_map = {_rt_norm(k): v for k, v in mapping.items()}
    for cand in candidates:
        v = norm_map.get(_rt_norm(cand), "")
        if _rt_clean_text(v):
            return _rt_clean_text(v)
    # fuzzy contains
    for k, v in mapping.items():
        kn = _rt_norm(k)
        for cand in candidates:
            if _rt_norm(cand) and _rt_norm(cand) in kn and _rt_clean_text(v):
                return _rt_clean_text(v)
    return ""


def _rt_amount_summary(mapping: Dict[str, str]) -> Tuple[str, str]:
    parts: List[str] = []
    first_number = ""
    for k, v in mapping.items():
        k2 = _rt_clean_text(k)
        v2 = _rt_clean_text(v)
        if not v2:
            continue
        if k2 in {"帳列項目", "關係人類別/名稱", "關係人名稱", "關係人類別", "項目", "名稱"}:
            continue
        is_amount_key = any(h in k2 for h in AMOUNT_FIELD_HINTS) or k2.startswith("value_") or k2.startswith("col_")
        if is_amount_key and (_rt_is_numeric_like(v2) or v2 not in {"", "-", "－"}):
            # 避免把長篇註解塞進金額摘要。
            if len(v2) > 120 and not _rt_is_numeric_like(v2):
                continue
            parts.append(f"{k2}={v2}")
            if not first_number:
                first_number = _rt_first_number(v2)
    return "; ".join(parts[:12]), first_number


def augment_related_party_transactions(args: argparse.Namespace, output_dir: Path) -> None:
    """把關係人交易表也併入 related_party 圖譜輸出。

    原 related_party builder 只吃「關係人名稱及關係.csv」，本函式額外只掃描使用者指定的
    母子公司間業務關係及重要交易往來情形、轉投資大陸地區之事業相關資訊、
    應收關係人款項、應付關係人款項四類原始 CSV，建立：
      Company -[:HAS_RELATED_PARTY_TRANSACTION]-> RelatedPartyTransaction
      RelatedPartyTransaction -[:HAS_TRANSACTION_ACCOUNT]-> RelatedPartyAccount
      RelatedPartyTransaction -[:HAS_RELATION_TYPE]-> RelationType
      RelatedPartyTransaction -[:HAS_TRANSACTION_PARTY]-> RelatedParty  （若列中有具體名稱）
    """
    reports_dir = Path(args.reports_dir)
    stock_filter = normalize_filter_values(args.stock_ids)
    period_filter = normalize_filter_values(args.periods)
    if not reports_dir.exists():
        print(f"⚠️ related_party transaction augmentation 略過，找不到 reports-dir：{reports_dir}")
        return

    node_csv = output_dir / "neo4j_nodes.csv"
    rel_csv = output_dir / "neo4j_relationships.csv"
    graph_node_csv = output_dir / "graph_nodes.csv"
    graph_edge_csv = output_dir / "graph_edges.csv"
    txn_table_csv = output_dir / "related_party_transaction_table.csv"

    nodes = _read_csv_dicts(node_csv) if node_csv.exists() else []
    rels = _read_csv_dicts(rel_csv) if rel_csv.exists() else []
    graph_nodes = _read_csv_dicts(graph_node_csv) if graph_node_csv.exists() else []
    graph_edges = _read_csv_dicts(graph_edge_csv) if graph_edge_csv.exists() else []

    node_ids = {r.get("id:ID") or r.get("id") for r in nodes}
    rel_keys = set()
    txn_rows: List[dict] = []

    def add_node_row(node_id: str, label: str, **props: Any) -> None:
        if not node_id or node_id in node_ids:
            return
        node_ids.add(node_id)
        common = {"id:ID": node_id, ":LABEL": label}
        common.update({k: _rt_clean_text(v) for k, v in props.items() if _rt_clean_text(v)})
        nodes.append(common)
        g = {"id": node_id, "label": label}
        g.update({k: _rt_clean_text(v) for k, v in props.items() if _rt_clean_text(v)})
        graph_nodes.append(g)

    def add_rel_row(source: str, target: str, rel_type: str, **props: Any) -> None:
        if not source or not target:
            return
        key = (source, target, rel_type, _rt_clean_text(props.get("edge_key", "")), json.dumps(props, sort_keys=True, ensure_ascii=False))
        if key in rel_keys:
            return
        rel_keys.add(key)
        row = {":START_ID": source, ":END_ID": target, ":TYPE": rel_type}
        row.update({k: _rt_clean_text(v) for k, v in props.items() if _rt_clean_text(v)})
        rels.append(row)
        g = {"source": source, "target": target, "type": rel_type}
        g.update({k: _rt_clean_text(v) for k, v in props.items() if _rt_clean_text(v)})
        graph_edges.append(g)

    files = sorted(p for p in reports_dir.rglob("*.csv") if _rt_is_related_party_transaction_file(p))
    print(f"\n[TXN-SCAN] 指定關係人交易原始 CSV 候選：{len(files)} 個")
    scanned = 0
    created_txn = 0

    for csv_file in files:
        stock_id, company_name, period, year, quarter = _rt_parse_company_period_from_path(csv_file, reports_dir)
        if stock_filter and stock_id not in stock_filter:
            continue
        if period_filter and period not in period_filter:
            continue
        scanned += 1
        account_from_file = _rt_infer_account_from_filename(csv_file)
        try:
            rows = _rt_read_csv_table(csv_file)
        except Exception as exc:
            print(f"⚠️ 關係人交易表讀取失敗，略過：{csv_file} | {exc}")
            continue

        header: Optional[List[str]] = None
        data_start = 0
        for i, row in enumerate(rows[:6]):
            if _rt_looks_like_header(row):
                header = [_rt_clean_text(x) for x in row]
                data_start = i + 1
                break

        company_id = _rt_company_node_id(stock_id, company_name)
        add_node_row(company_id, "Company", name=company_name, stock_code=stock_id, role="report_company")
        file_txn_count = 0

        for row_idx, row in enumerate(rows[data_start:], start=data_start):
            if not any(_rt_clean_text(x) for x in row):
                continue
            if _rt_looks_like_header(row):
                continue
            if row and _rt_is_note_or_bad_name(row[0]):
                continue

            mapping = _rt_build_row_mapping(row, header, account_from_file)
            account = _rt_pick_field(mapping, ["帳列項目", "項目", "科目", "item_name", "table_name"]) or account_from_file
            party_value = _rt_pick_field(mapping, ["關係人類別/名稱", "關係人名稱", "關係人類別", "交易對象", "名稱", "對象"])
            if _rt_is_note_or_bad_name(account) and not account_from_file:
                continue
            if _rt_is_note_or_bad_name(party_value):
                continue

            category = _rt_classify_category(party_value)
            related_party_name = "" if category else party_value
            if not category and not related_party_name:
                # 沒有任何關係人類別或名稱，不併入 related_party graph。
                continue

            amount_summary, value_number = _rt_amount_summary(mapping)
            if not amount_summary and not value_number:
                # 沒有金額/餘額資訊，通常不是交易 evidence row。
                continue

            relation_category = category or "未標註"
            txn_id = _rt_transaction_node_id(stock_id, period, csv_file.as_posix(), row_idx, account, party_value, amount_summary)
            account_id = _rt_account_node_id(account)
            relation_type_id = _rt_relation_type_node_id(relation_category)

            add_node_row(
                txn_id,
                "RelatedPartyTransaction",
                name=f"{period} {account} {party_value}"[:120],
                report_stock_id=stock_id,
                report_company_name=company_name,
                report_period=period,
                report_year=year,
                report_quarter=quarter,
                account=account,
                relation_category=relation_category,
                related_party_name=related_party_name,
                party_or_category=party_value,
                amount_summary=amount_summary,
                value_number=value_number,
                source_csv=str(csv_file),
                source_row_index=row_idx,
            )
            add_node_row(account_id, "RelatedPartyAccount", name=account)
            add_node_row(relation_type_id, "RelationType", name=relation_category)

            edge_common = dict(
                report_stock_id=stock_id,
                report_company_name=company_name,
                report_period=period,
                report_year=year,
                report_quarter=quarter,
                account=account,
                relation_category=relation_category,
                related_party_name=related_party_name,
                party_or_category=party_value,
                amount_summary=amount_summary,
                value_number=value_number,
                source_csv=str(csv_file),
                source_row_index=row_idx,
            )
            add_rel_row(company_id, txn_id, "HAS_RELATED_PARTY_TRANSACTION", edge_key=f"{period}|{csv_file}|{row_idx}", **edge_common)
            add_rel_row(txn_id, account_id, "HAS_TRANSACTION_ACCOUNT", edge_key=f"{txn_id}|account", account=account)
            add_rel_row(txn_id, relation_type_id, "HAS_RELATION_TYPE", edge_key=f"{txn_id}|relation_type", relation_category=relation_category)
            add_rel_row(company_id, account_id, "HAS_RELATED_PARTY_ACCOUNT", edge_key=f"{stock_id}|{period}|{account}", report_period=period, report_year=year, report_quarter=quarter, account=account)

            if related_party_name:
                rp_id = _rt_related_party_node_id(related_party_name)
                add_node_row(rp_id, "RelatedParty", name=related_party_name, normalized_name=_rt_normalize_party_key(related_party_name))
                add_rel_row(txn_id, rp_id, "HAS_TRANSACTION_PARTY", edge_key=f"{txn_id}|party", related_party_name=related_party_name)
                add_rel_row(company_id, rp_id, "RELATED_PARTY_TRANSACTION_WITH", edge_key=f"{period}|{csv_file}|{row_idx}|{rp_id}", **edge_common)

            txn_rows.append({
                "report_stock_id": stock_id,
                "report_company_name": company_name,
                "report_period": period,
                "report_year": year,
                "report_quarter": quarter,
                "account": account,
                "party_or_category": party_value,
                "relation_category": relation_category,
                "related_party_name": related_party_name,
                "amount_summary": amount_summary,
                "value_number": value_number,
                "source_csv": str(csv_file),
                "source_row_index": row_idx,
                "raw_row": " | ".join(row),
            })
            created_txn += 1
            file_txn_count += 1

        print(f"[TXN] {csv_file} -> {file_txn_count} 筆")

    _write_csv_dicts(node_csv, nodes)
    _write_csv_dicts(rel_csv, rels)
    _write_csv_dicts(graph_node_csv, graph_nodes)
    _write_csv_dicts(graph_edge_csv, graph_edges)
    _write_csv_dicts(txn_table_csv, txn_rows)

    print("\n✅ 已併入關係人交易表到 related_party 圖譜")
    print(f"掃描交易檔案數：{scanned}")
    print(f"新增交易 evidence 筆數：{created_txn}")
    print(f"輸出：{txn_table_csv}")


def _write_csv_dicts(path: Path, rows: List[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: List[str] = []
    for row in rows:
        for k in row.keys():
            if k not in fieldnames:
                fieldnames.append(k)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

def import_neo4j_csv_output(args: argparse.Namespace, target: str, output_dir: Path) -> None:
    nodes_csv = output_dir / "neo4j_nodes.csv"
    rels_csv = output_dir / "neo4j_relationships.csv"
    nodes = _read_csv_dicts(nodes_csv)
    rels = _read_csv_dicts(rels_csv)

    # Neo4j 清除動作統一放在 run_target()/main() 的建圖前執行。
    # 這裡只負責匯入本 target 已輸出的 neo4j_nodes.csv / neo4j_relationships.csv，
    # 避免多 target 執行時每匯入一個 target 就把前一個 target 清掉。
    driver = _neo4j_driver(args)
    database = _neo4j_database(args)
    with driver.session(database=database) as session:
        session.execute_write(_create_neo4j_constraint)
        for row in nodes:
            session.execute_write(_upsert_node_tx, row)
        for row in rels:
            session.execute_write(_upsert_rel_tx, row)
    driver.close()

    print(f"✅ 已匯入 Neo4j：{target}")
    print(f"nodes: {nodes_csv} ({len(nodes)} rows)")
    print(f"relationships: {rels_csv} ({len(rels)} rows)")


def run_embedded_target(name: str, args: argparse.Namespace) -> None:
    ns = load_embedded_module(name)
    configure_module(ns, name, args)

    main_func = ns.get("main")
    if not callable(main_func):
        raise RuntimeError(f"{name} 沒有可執行的 main()")

    main_func()
    output_dir = _output_dir_for_embedded(ns, name)

    if name == "related_party" and not getattr(args, "no_related_party_transactions", False):
        augment_related_party_transactions(args, output_dir)

    if args.import_neo4j:
        import_neo4j_csv_output(args, name, output_dir)


def run_target(name: str, args: argparse.Namespace) -> None:
    print("\n" + "=" * 72)
    print(f"開始建立：{_DISPLAY_NAMES[name]}")
    print("=" * 72)

    # target-level 清除要在建圖/匯入前做，log 順序才直覺。
    # clear-neo4j-all 則由 main() 在所有 target 開始前只做一次。
    if args.import_neo4j and args.clear_neo4j_target:
        _apply_neo4j_env(args)
        if name == "risk_event":
            _clear_neo4j_target(args, "risk_event")
        else:
            _clear_neo4j_target(args, name)

    if name == "risk_event":
        _apply_neo4j_env(args)
        # 若已在上面清除 target，就不要再讓 risk_event 原始 importer 清一次。
        old_clear_risk = getattr(args, "clear_risk_only", False)
        if args.clear_neo4j_target:
            args.clear_risk_only = False
        try:
            run_risk_event(args)
        finally:
            args.clear_risk_only = old_clear_risk
        return

    run_embedded_target(name, args)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="一次建立 investment / related_party / supply_chain / risk_event 四種圖譜輸出，並可選擇匯入 Neo4j。"
    )
    parser.add_argument(
        "--only",
        nargs="+",
        choices=_VALID_TARGETS,
        default=list(_VALID_TARGETS),
        help="只執行指定圖譜。預設四種都執行。",
    )
    parser.add_argument("--reports-dir", default="./reports_csv_output", help="investment / related_party / risk_event 使用的 reports_csv_output 資料夾。")
    parser.add_argument("--supply-chain-txt", default="./tw_semiconductor_supply_chain_stock_codes.txt", help="supply_chain 使用的產業鏈文字檔。")
    parser.add_argument("--stock-ids", default="", help="只處理指定股票代號，可用逗號或空白分隔，例如 2303 或 5347,2303。")
    parser.add_argument("--periods", default="", help="只處理指定期間，例如 114Q3 或 113Q2,114Q3。")
    parser.add_argument("--no-html", action="store_true", help="關閉 pyvis HTML 圖輸出。CSV / JSONL 仍會照常輸出。")
    parser.add_argument("--no-related-party-transactions", action="store_true", help="related_party 只建立關係人名稱及關係，不額外併入指定的母子公司間業務、轉投資大陸、應收/應付關係人款項交易表。")

    # risk_event options
    parser.add_argument("--financial-csv", default="./graph_rag_final_output/final_cleaned_data_all_companies.csv", help="risk_event 可選：PDF clean 財報總表。只有加 --include-financial 才會使用。")
    parser.add_argument("--include-financial", action="store_true", help="risk_event 額外納入 PDF clean financial CSV。預設只用 deal_html all_table_facts。")
    parser.add_argument("--risk-ontology", default="", help="risk_event 外部風險事件本體 JSON；預設空字串表示使用內建嚴格 DEFAULT_ONTOLOGY。")
    parser.add_argument("--risk-output-dir", default="./risk_event_graph_output", help="risk_event 輸出資料夾。")

    # Neo4j options
    parser.add_argument("--import-neo4j", action="store_true", help="建完後直接匯入 Neo4j。")
    parser.add_argument("--clear-neo4j-target", action="store_true", help="建圖/匯入前清除本次 target 的舊圖譜；保留共用 Company 節點。")
    parser.add_argument("--clear-neo4j-all", action="store_true", help="所有 target 建圖/匯入前清除所有 GraphNode 圖譜；請只在完整重建時使用。")
    parser.add_argument("--clear-risk-only", action="store_true", help="risk_event 專用：匯入前清除舊風險事件節點；不刪一般 Company 節點。")
    parser.add_argument("--neo4j-uri", default="", help="Neo4j URI；預設讀 NEO4J_URI 或 bolt://127.0.0.1:7687。")
    parser.add_argument("--neo4j-user", default="", help="Neo4j user；預設讀 NEO4J_USER 或 neo4j。")
    parser.add_argument("--neo4j-password", default="", help="Neo4j password；預設讀 NEO4J_PASSWORD 或 password。")
    parser.add_argument("--neo4j-database", default="", help="Neo4j database；預設讀 NEO4J_DATABASE 或 neo4j。")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    failures = []

    # 全域清除必須在所有 target 開始前只做一次。
    # 舊版是在每個 target 產出 CSV 後、匯入前才清，log 會看起來像「後面才清除」；
    # 多 target 同跑時還可能把前一個剛匯入的 target 刪掉。
    if args.import_neo4j and args.clear_neo4j_all:
        _apply_neo4j_env(args)
        _clear_neo4j_all(args)

    for name in args.only:
        try:
            run_target(name, args)
        except Exception as exc:
            failures.append((name, exc))
            print(f"\n❌ {_DISPLAY_NAMES[name]} 建立失敗：{exc}")

    print("\n" + "=" * 72)
    if failures:
        print("部分圖譜建立失敗：")
        for name, exc in failures:
            print(f"- {_DISPLAY_NAMES[name]}：{exc}")
        raise SystemExit(1)

    print("✅ 全部指定圖譜建立完成")
    print("主要輸出資料夾：")
    for name in _VALID_TARGETS:
        if name in args.only:
            print(f"- {_TARGET_OUTPUT_DIRS[name]}/")


if __name__ == "__main__":
    main()
