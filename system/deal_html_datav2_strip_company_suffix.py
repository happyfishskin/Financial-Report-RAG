import pandas as pd
import os
import re
import json
import warnings
from pathlib import Path
from bs4 import BeautifulSoup
from bs4 import XMLParsedAsHTMLWarning

# 過濾 BeautifulSoup 對 XBRL/HTML 混合格式的警告
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)


# ============================================================
# 基本設定
# ============================================================
INPUT_FOLDER = "reports_html_copy"       # 上一支爬蟲程式輸出的資料夾
OUTPUT_FOLDER = "reports_csv_output"     # CSV 輸出資料夾

APPEND_XBRL_NOTES_TO_TABLE = True         # True：把 note 說明文字附加回對應表格 CSV
SAVE_XBRL_NOTES_CSV = True                # True：輸出原始 note 整段文字 CSV
SAVE_STRUCTURED_NOTE_CSV = True           # True：輸出保留版面行列結構的 note CSV
SAVE_EACH_NOTE_BLOCK_CSV = False          # False：不輸出 note_001.csv、note_002.csv；全部 note 只放在總表 CSV
STRUCTURED_NOTE_SPLIT_MIN_SPACES = 2      # 連續幾個以上空白視為欄位分隔

# True：xbrl_notes_structured.csv 只保留一欄原始文字 raw_line，不再輸出重複的 col_1 / col_2...
NOTE_STRUCTURED_SINGLE_TEXT_ONLY = True

# note block 分檔過濾設定：
# True：太短、只有公司名、只有單一欄位名稱的 note block 不另存成 note_XXX.csv
# 注意：被過濾掉的內容仍然會保留在 2303_114Q2_xbrl_notes_structured.csv 總表中
FILTER_SHORT_NOTE_BLOCK_CSV = False
MIN_NOTE_BLOCK_CHARS = 20                 # note block 原文總字數少於此值，且行數也很少時，不另存
MIN_NOTE_BLOCK_LINES = 2                  # note block 行數少於此值，且字數也很少時，不另存

# 是否優先用 HTML 畫面標題命名表格，例如：資產負債表、綜合損益表、現金流量表
USE_HTML_TABLE_TITLE_FOR_FILENAME = True

# 單一檔名元件安全長度。中文 UTF-8 一字通常 3 bytes，不能只用字數判斷。
MAX_FILENAME_BYTES = 180
MAX_TITLE_BYTES = 90

# 若不輸出個別 note_XXX.csv，是否自動清除舊的 note_XXX.csv 殘留檔案
CLEAN_OLD_NOTE_BLOCK_CSV = True

# ============================================================
# Long-format Fact 輸出設定
# ============================================================
# True：除了原始寬表 CSV，也額外輸出 long-format facts CSV。
# 範例：
#   2303, 聯華電子, 113Q1, 其他收入, N7130, 股利收入,
#   2024年1月1日至3月31日, 3,929
EXPORT_TABLE_FACTS_CSV = True

# True：同一份 HTML 另外彙整所有表格 facts 成一個總表：
#   <stock>_<period>__all_table_facts.csv
EXPORT_COMBINED_FACTS_CSV = True

# True：所有公司 / 所有季度 / 所有 HTML 的 facts 再合併成一個全域總表：
#   reports_csv_output/__all_company_all_period_facts.csv
EXPORT_GLOBAL_ALL_FACTS_CSV = True
GLOBAL_ALL_FACTS_FILENAME = "__all_company_all_period_facts.csv"

# True：另外輸出優化後 facts 表。
# 優化內容：分離中英文項目名稱、解析欄位期間、標準化表名、補 value_twd / value_ratio、建立 fact_key。
EXPORT_OPTIMIZED_FACTS_CSV = True
OPTIMIZED_FACTS_SUFFIX = "__all_table_facts_optimized"
GLOBAL_OPTIMIZED_FACTS_FILENAME = "__all_company_all_period_facts_optimized.csv"

# True：列印每一張 table 的標題、shape 與是否被跳過，方便追查主表為什麼沒有輸出。
DEBUG_TABLE_SCAN = False

# ============================================================
# RAG-friendly 輸出設定
# ============================================================
# v5 設計原則：
# - 原始表格維持分散 CSV，作為 Parent-Child / DealTable / DealNote 的 source layer。
# - all_table_facts 只保留 numeric_fact，不再塞入所有 source_table_row，避免檔案膨脹與 RAG 檢索污染。
# - 所有原始表是否被處理，改由 source_table_index / coverage_report 檢查，不靠 all_table_facts 承擔全文總表功能。

# False：不要把每張原始 CSV 的每一列塞進 all_table_facts。
# all_table_facts 只放可結構化的 numeric facts。
ENSURE_EVERY_OUTPUT_CSV_IN_ALL_FACTS = False
RAW_ROW_FALLBACK_ONLY_WHEN_NO_NUMERIC_FACTS = True

# True：產生 index / coverage 前，仍會掃描該公司/季度輸出資料夾內既有原始 CSV，
# 讓手動放入或舊版輸出的表也能被記錄在 source_table_index 中。
SCAN_EXISTING_FOLDER_CSVS_INTO_ALL_FACTS = True

# True：輸出一份報告，列出每個 source CSV 是否有 numeric facts。
# 注意：沒有 numeric facts 不是錯誤，代表該表應由 DealTable / DealNote 或原始 CSV 進行 Parent-Child 查找。
EXPORT_ALL_FACTS_COVERAGE_REPORT = True

# True：輸出 source table index，作為 RAG 建庫時的 table source 清單。
EXPORT_SOURCE_TABLE_INDEX_CSV = True

# True：額外輸出 numeric_facts.csv，和 all_table_facts 內容一致，但名稱更明確，方便後續建圖 / 建 Milvus。
EXPORT_NUMERIC_FACTS_ALIAS_CSV = True
NUMERIC_FACTS_SUFFIX = "__numeric_facts"
GLOBAL_NUMERIC_FACTS_FILENAME = "__all_company_all_period_numeric_facts.csv"

# 預設不把衍生檔再次當原始表掃描，避免重複膨脹。
# 衍生檔包含：*_facts.csv、*all_table_facts*.csv、*_coverage_report.csv、*_source_table_index.csv。
INCLUDE_DERIVED_CSVS_WHEN_SCANNING_FOLDER = False

RAW_ROW_COLUMN_HEADER = "__raw_table_row__"

# 財報金額預設單位。公開資訊觀測站財報多數為新台幣仟元，若你的來源不是仟元可改這裡。
DEFAULT_FACT_UNIT = "TWD_1000"

TEST_ONE_COMPANY = False
TEST_STOCK_CODE = "2303"
TEST_PERIODS = []


# ============================================================
# 檔名 / 文字清理
# ============================================================
def clean_filename_name(name):
    """移除 Windows / Linux 檔名不建議或不允許的字元。"""
    name = str(name)
    name = name.replace("\x00", "")
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    name = re.sub(r"\s+", " ", name)
    name = name.strip()

    # Windows 不允許檔名最後是點或空白
    name = name.rstrip(" .")

    return name


def truncate_utf8_bytes(text, max_bytes=MAX_TITLE_BYTES):
    """依 UTF-8 byte 長度截斷，避免中文檔名超過作業系統限制。"""
    text = str(text)
    output = ""

    for ch in text:
        if len((output + ch).encode("utf-8")) > max_bytes:
            break
        output += ch

    return output.strip()


def make_safe_filename_component(text, max_bytes=MAX_TITLE_BYTES, fallback="untitled"):
    """產生安全且短的檔名片段。"""
    text = clean_filename_name(text)
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"_+", "_", text)
    text = text.strip("._- ")

    if not text:
        text = fallback

    text = truncate_utf8_bytes(text, max_bytes=max_bytes)
    return text or fallback


def make_safe_csv_filename(stem, max_bytes=MAX_FILENAME_BYTES):
    """產生安全 CSV 檔名，整個檔名含 .csv 會限制 byte 長度。"""
    stem = make_safe_filename_component(stem, max_bytes=max_bytes - len(".csv".encode("utf-8")))
    return f"{stem}.csv"


def normalize_company_label_name(name):
    """
    將公司名稱轉成輸出用標籤名稱。

    會移除：
    - 股份有限公司及其子公司
    - 股份有限公司及子公司
    - 股份有限公司與子公司
    - 股份有限公司
    - 有限公司及其子公司
    - 有限公司及子公司
    - 有限公司與子公司
    - 有限公司
    - 及其子公司
    - 及子公司
    - 與子公司
    """
    name = clean_filename_name(name)

    remove_suffixes = [
        "股份有限公司及其子公司",
        "股份有限公司及子公司",
        "股份有限公司與子公司",
        "股份有限公司",
        "有限公司及其子公司",
        "有限公司及子公司",
        "有限公司與子公司",
        "有限公司",
        "及其子公司",
        "及子公司",
        "與子公司",
    ]

    changed = True
    while changed:
        changed = False
        for suffix in remove_suffixes:
            if name.endswith(suffix):
                name = name[: -len(suffix)].strip()
                changed = True
                break

    return clean_filename_name(name)


def decode_html_file(html_file_path):
    """讀取公開資訊觀測站下載的 HTML。"""
    with open(html_file_path, "rb") as f:
        content_bytes = f.read()

    for enc in ["utf-8", "utf-8-sig", "big5", "cp950"]:
        try:
            return content_bytes.decode(enc)
        except UnicodeDecodeError:
            continue

    return content_bytes.decode("utf-8", errors="ignore")


# ============================================================
# HTML 畫面標題擷取
# ============================================================
def extract_table_title_from_html_table(table):
    """
    從 HTML table 抓畫面上的中文標題。

    目標範例：
    <span class="zh">資產負債表</span>
    <span class="en" style="display: none;">Balance Sheet</span>
    """
    if table is None:
        return ""

    # 1. 優先抓 table 內第一個 span.zh
    zh_span = table.find("span", class_="zh")
    if zh_span:
        title = zh_span.get_text(" ", strip=True)
        title = re.sub(r"\s+", " ", title).strip()
        if title:
            return title

    # 2. fallback：抓第一列第一個 th / td
    first_row = table.find("tr")
    if first_row:
        first_cell = first_row.find(["th", "td"])
        if first_cell:
            title = first_cell.get_text(" ", strip=True)
            title = re.sub(r"\s+", " ", title).strip()
            if title:
                return title

    return ""


def normalize_table_title_for_filename(title):
    """把 HTML 畫面標題轉成檔名片段。"""
    title = clean_note_text(title)
    title = title.replace("\n", " ")
    title = re.sub(r"\s+", "_", title).strip("_ ")

    return make_safe_filename_component(
        title,
        max_bytes=MAX_TITLE_BYTES,
        fallback="other_table",
    )


# ============================================================
# 公司 / 期間資訊
# ============================================================
def extract_company_info_from_html(html_content, fallback_folder_name):
    """
    從財報 HTML header 抓股票代號與公司名稱。

    目標格式：
    <span class="zh">2330 台灣積體電路製造股份有限公司<br>...</span>
    """
    soup = BeautifulSoup(html_content, "html.parser")
    zh_span = soup.find("span", class_="zh")

    if zh_span:
        text = zh_span.get_text(separator="\n", strip=True)
        lines = [line.strip() for line in text.splitlines() if line.strip()]

        if lines:
            first_line = lines[0]
            match = re.match(r"^(\d{4})\s*(.+)$", first_line)

            if match:
                stock_code = match.group(1)
                company_name = normalize_company_label_name(match.group(2))
                folder_name = f"{stock_code}_{company_name}"
                return stock_code, company_name, folder_name

    fallback_folder_name = clean_filename_name(fallback_folder_name)
    match = re.match(r"^(\d{4})[_\s-]*(.*)$", fallback_folder_name)

    if match:
        stock_code = match.group(1)
        company_name = normalize_company_label_name(match.group(2).strip()) or "Unknown_Company"
        folder_name = f"{stock_code}_{company_name}" if company_name != "Unknown_Company" else fallback_folder_name
        return stock_code, company_name, folder_name

    return "Unknown_Code", "Unknown_Company", fallback_folder_name


def extract_period_from_filename(html_file_path):
    """從檔名抓季度，例如 2330_113Q1_財報.html -> 113Q1。"""
    file_name_only = os.path.basename(html_file_path)
    period_match = re.search(r"(\d{3}Q[1-4])", file_name_only)
    return period_match.group(1) if period_match else "Unknown_Period"


# ============================================================
# 一般 HTML table 解析與修復
# ============================================================
def normalize_table_cell(value):
    """將表格儲存格統一轉成乾淨字串；NaN/None 轉空字串。"""
    if pd.isna(value):
        return ""

    text = str(value).strip()
    if text.lower() in ("nan", "none"):
        return ""

    text = re.sub(r"\s+", " ", text)
    return text


def make_unique_columns(columns):
    """避免 CSV 欄名重複。"""
    seen = {}
    output = []

    for col in columns:
        col = normalize_table_cell(col) or "欄位"

        if col not in seen:
            seen[col] = 1
            output.append(col)
        else:
            seen[col] += 1
            output.append(f"{col}_{seen[col]}")

    return output


def html_table_to_dataframe(table):
    """
    不依賴 pandas.read_html / html5lib 的簡易 HTML table 解析器。
    支援基本 rowspan / colspan。
    """
    rows = table.find_all("tr")
    grid = []
    rowspan_map = {}

    for r_idx, tr in enumerate(rows):
        cells = tr.find_all(["th", "td"])
        row = []
        c_idx = 0

        while (r_idx, c_idx) in rowspan_map:
            value, remaining = rowspan_map[(r_idx, c_idx)]
            row.append(value)
            if remaining > 1:
                rowspan_map[(r_idx + 1, c_idx)] = (value, remaining - 1)
            del rowspan_map[(r_idx, c_idx)]
            c_idx += 1

        for cell in cells:
            while (r_idx, c_idx) in rowspan_map:
                value, remaining = rowspan_map[(r_idx, c_idx)]
                row.append(value)
                if remaining > 1:
                    rowspan_map[(r_idx + 1, c_idx)] = (value, remaining - 1)
                del rowspan_map[(r_idx, c_idx)]
                c_idx += 1

            text = cell.get_text(" ", strip=True)
            text = re.sub(r"\s+", " ", text)

            try:
                rowspan = int(cell.get("rowspan", 1))
            except ValueError:
                rowspan = 1

            try:
                colspan = int(cell.get("colspan", 1))
            except ValueError:
                colspan = 1

            for offset in range(colspan):
                row.append(text)
                if rowspan > 1:
                    rowspan_map[(r_idx + 1, c_idx + offset)] = (text, rowspan - 1)

            c_idx += colspan

        while (r_idx, c_idx) in rowspan_map:
            value, remaining = rowspan_map[(r_idx, c_idx)]
            row.append(value)
            if remaining > 1:
                rowspan_map[(r_idx + 1, c_idx)] = (value, remaining - 1)
            del rowspan_map[(r_idx, c_idx)]
            c_idx += 1

        if row:
            grid.append(row)

    if not grid:
        return pd.DataFrame()

    max_cols = max(len(row) for row in grid)
    normalized_rows = [row + [""] * (max_cols - len(row)) for row in grid]
    return pd.DataFrame(normalized_rows)


def parse_tables_robust(html_content):
    """
    解析 HTML 表格。

    優先順序：
    1. pandas.read_html + lxml
    2. pandas.read_html 預設模式
    3. BeautifulSoup 自製 table parser
    """
    errors = []

    try:
        return pd.read_html(html_content, flavor="lxml")
    except Exception as e:
        errors.append(f"lxml failed: {e}")

    try:
        return pd.read_html(html_content)
    except Exception as e:
        errors.append(f"pandas default failed: {e}")

    try:
        soup = BeautifulSoup(html_content, "html.parser")
        tables = soup.find_all("table")
        dfs = []

        for table in tables:
            df = html_table_to_dataframe(table)
            if not df.empty:
                dfs.append(df)

        if dfs:
            print("  [Warning] pandas.read_html 失敗，已改用 BeautifulSoup fallback 解析表格")
            return dfs
    except Exception as e:
        errors.append(f"BeautifulSoup fallback failed: {e}")

    raise RuntimeError("無法解析表格；" + " | ".join(errors))


def html_table_node_to_dataframe(table):
    """
    將單一 BeautifulSoup table node 轉成 DataFrame。

    重點：這個函式是「逐一 table 解析」，不再先對整份 HTML 做
    pandas.read_html(html_content)。因此 df 和 html_table 會保持一對一，
    不會發生 pandas 的 dfs index 與 BeautifulSoup 的 table index 錯位。
    """
    if table is None:
        return pd.DataFrame()

    table_html = str(table)

    # 先嘗試 pandas 對「單一 table」解析；失敗再用自製 rowspan / colspan parser。
    for kwargs in ({"flavor": "lxml"}, {}):
        try:
            dfs = pd.read_html(table_html, **kwargs)
            if dfs:
                return dfs[0]
        except Exception:
            pass

    return html_table_to_dataframe(table)


def parse_tables_with_html_nodes(html_content):
    """
    掃描整份 HTML 的所有 <table>，並回傳：
      (table_index, dataframe, original_html_table_node, raw_title)

    這是本版主流程使用的解析方式。它解決舊版問題：
    - 舊版：dfs = pandas.read_html(整份 HTML)
            html_table = soup_tables[table_idx]
            兩者不保證同一張表，導致資產負債表等主表可能沒正確輸出。
    - 新版：每一個 soup table node 直接轉成 df，標題與 df 永遠配對。
    """
    soup = BeautifulSoup(html_content, "html.parser")
    tables = soup.find_all("table")
    table_pairs = []

    for table_idx, table in enumerate(tables):
        raw_title = extract_table_title_from_html_table(table)
        df = html_table_node_to_dataframe(table)

        if df is None or df.empty:
            if DEBUG_TABLE_SCAN:
                print(f"  [Debug][Skip empty node] table_idx={table_idx}, raw_title={raw_title}")
            continue

        table_pairs.append((table_idx, df, table, raw_title))

    return table_pairs


def columns_are_messy(df):
    """判斷欄位是否疑似被 colspan / rowspan 展開壞掉。"""
    columns = [normalize_table_cell(col) for col in df.columns]
    if not columns:
        return False

    base_columns = [re.sub(r"\.\d+$", "", col) for col in columns]
    unique_base_count = len(set(base_columns))

    if unique_base_count <= max(2, len(columns) // 4):
        return True

    duplicate_style_count = sum(1 for col in columns if re.search(r"\.\d+$", col))
    if duplicate_style_count >= max(2, len(columns) // 3):
        return True

    if all(re.fullmatch(r"\d+", col) for col in columns):
        return True

    return False


def detect_header_row_for_layout(df, max_scan_rows=10):
    """在前幾列中尋找最可能的真正欄名列。"""
    header_keywords = [
        "代號", "會計項目", "項目", "名稱", "關係人", "關係人類別",
        "帳列項目", "本期", "去年同期", "累計", "年度", "月", "日",
        "金額", "取得價款", "期末", "期初", "流動", "非流動",
        "交易標的", "交易股數", "交易金額", "交易對象",
    ]

    values = df.fillna("").astype(str)
    best_candidate = None
    scan_rows = min(max_scan_rows, len(values))

    for row_idx in range(scan_rows):
        row_values = [normalize_table_cell(x) for x in values.iloc[row_idx].tolist()]
        non_empty_values = [x for x in row_values if x]

        if len(non_empty_values) < 2:
            continue

        unique_values = set(non_empty_values)
        keyword_hits = sum(
            1 for keyword in header_keywords
            if any(keyword in value for value in non_empty_values)
        )
        joined = "".join(non_empty_values)

        score = 0
        score += len(non_empty_values)
        score += len(unique_values) * 0.5
        score += keyword_hits * 5

        if any(key in joined for key in ["本期", "去年同期", "累計", "會計項目", "代號", "名稱"]):
            score += 10

        if len(unique_values) <= 1:
            score -= 20

        last_non_empty_col = max(
            (col_idx for col_idx, value in enumerate(row_values) if value),
            default=-1
        )

        candidate = {
            "score": score,
            "row_idx": row_idx,
            "last_non_empty_col": last_non_empty_col,
            "keyword_hits": keyword_hits,
        }

        if best_candidate is None or candidate["score"] > best_candidate["score"]:
            best_candidate = candidate

    return best_candidate


def remove_redundant_layout_rows(df):
    """
    只移除全空列與重複 header row。
    不移除「說明」「備註」「附註」，避免刪到有效資訊。
    """
    if df.empty:
        return df

    column_names = [normalize_table_cell(col) for col in df.columns]
    keep_mask = []

    for _, row in df.iterrows():
        values = [normalize_table_cell(x) for x in row.tolist()]
        non_empty_values = [x for x in values if x]

        drop_row = False
        if not non_empty_values:
            drop_row = True
        elif non_empty_values == column_names[:len(non_empty_values)]:
            drop_row = True

        keep_mask.append(not drop_row)

    return df.loc[keep_mask].reset_index(drop=True)


def fix_total_row_expanded_cells(df):
    """修正合計列被合併儲存格展開成「合計, 合計」的情形。"""
    if df.empty or df.shape[1] < 2:
        return df

    total_words = {"合計", "總計", "小計"}
    df = df.copy()

    for idx in df.index:
        first_value = normalize_table_cell(df.iat[idx, 0])
        second_value = normalize_table_cell(df.iat[idx, 1])

        if first_value in total_words and first_value == second_value:
            df.iat[idx, 1] = ""

    return df


def repair_mops_table_layout(df):
    """修復公開資訊觀測站 HTML 表格常見的 colspan / rowspan 解析錯亂問題。"""
    if df is None or df.empty:
        return df

    df = df.copy()
    df = df.dropna(how="all", axis=0).dropna(how="all", axis=1)

    if df.empty:
        return df

    candidate = detect_header_row_for_layout(df)

    if candidate:
        header_row_idx = candidate["row_idx"]
        last_non_empty_col = candidate["last_non_empty_col"]
        keyword_hits = candidate["keyword_hits"]

        should_repair = (
            columns_are_messy(df)
            or (
                last_non_empty_col + 1 < df.shape[1]
                and keyword_hits >= 1
            )
        )

        if should_repair and last_non_empty_col >= 1:
            keep_cols = list(range(last_non_empty_col + 1))
            header_values = []

            for col_idx in keep_cols:
                header = normalize_table_cell(df.iloc[header_row_idx, col_idx])

                if not header:
                    parts = []
                    for row_idx in range(header_row_idx + 1):
                        value = normalize_table_cell(df.iloc[row_idx, col_idx])
                        if value and value not in parts:
                            parts.append(value)
                    header = "_".join(parts) if parts else f"欄位{col_idx + 1}"

                header_values.append(header)

            header_values = make_unique_columns(header_values)
            df = df.iloc[header_row_idx + 1:, keep_cols].copy()
            df.columns = header_values
            df = df.reset_index(drop=True)

    df = df.replace(r"^\s*$", pd.NA, regex=True)
    df = df.dropna(how="all", axis=0).dropna(how="all", axis=1)
    df = remove_redundant_layout_rows(df)
    df = fix_total_row_expanded_cells(df)
    df = df.dropna(how="all", axis=0).dropna(how="all", axis=1)

    return df.reset_index(drop=True)


def clean_table(df):
    """
    清理表格：
    1. 移除全空的行或列
    2. 將 MultiIndex 欄位攤平成一般欄位
    3. 修復公開資訊觀測站 HTML 合併儲存格造成的格式錯亂
    4. 移除完全重複的行
    """
    df = df.dropna(how="all", axis=0).dropna(how="all", axis=1)

    if isinstance(df.columns, pd.MultiIndex):
        new_columns = []
        for col in df.columns:
            col_items = [normalize_table_cell(x) for x in col if normalize_table_cell(x)]
            new_columns.append("_".join(col_items) if col_items else "欄位")
        df.columns = make_unique_columns(new_columns)
    else:
        df.columns = make_unique_columns([normalize_table_cell(col) for col in df.columns])

    df = repair_mops_table_layout(df)

    if df.empty:
        return df

    return df.drop_duplicates()


# ============================================================
# Long-format Fact 輸出：把寬表轉成「一個數值一列」
# ============================================================

def parse_number_for_fact(value):
    """將 3,929 / (3,929) / 3.5% 轉成數值；不可轉換時回傳 None。"""
    s = normalize_table_cell(value)
    if not s or s in {"-", "－", "$", "nan", "None", "無", "不適用"}:
        return None

    is_percent = "%" in s or "％" in s
    is_negative = s.startswith("(") and s.endswith(")")

    s2 = s.replace(",", "").replace(" ", "")
    s2 = s2.replace("（", "(").replace("）", ")")
    s2 = s2.replace("(", "").replace(")", "")
    s2 = s2.replace("％", "%").replace("%", "")

    # 保留數字、小數點與負號；若剩下不是數字，表示不是純金額/比例。
    s2 = re.sub(r"[^0-9.\-]", "", s2)
    if not s2 or s2 in {"-", ".", "-."}:
        return None

    try:
        num = float(s2)
    except Exception:
        return None

    if is_negative and num > 0:
        num = -num
    return num


def detect_value_type_and_unit(value_raw, column_header=""):
    """判斷數值是金額或百分比。"""
    v = normalize_table_cell(value_raw)
    c = normalize_table_cell(column_header)
    if "%" in v or "％" in v or "比率" in c or "比例" in c:
        return "percent", "Percentage"
    return "amount", DEFAULT_FACT_UNIT


def normalize_column_for_fact_detection(col_name):
    """
    將 pandas / HTML 解析後的欄名轉成較適合判斷語意的版本。

    公開資訊觀測站主表常見問題：
    - pandas 解析 MultiIndex 後，欄名會變成「資產負債表_代號」或「資產負債表_會計項目」。
    - 舊版 infer_code_and_item() 只認 exact match 的「代號」「會計項目」，因此資產負債表的
      1100 / 現金及約當現金等列無法轉成 facts，最後不會進 all_table_facts。
    
    這個函式不改原始輸出欄名，只用於判斷欄位角色。
    """
    c = normalize_table_cell(col_name)
    if not c:
        return ""

    # 移除 pandas 解析空白欄時產生的 Unnamed 資訊。
    c = re.sub(r"Unnamed:\s*\d+(_level_\d+)?", "", c, flags=re.I)

    # 移除常見主表標題前綴，避免「資產負債表_代號」無法被辨識。
    title_words = [
        "資產負債表", "Balance Sheet",
        "綜合損益表", "Statements of Comprehensive Income", "Statement of Comprehensive Income",
        "損益表", "Income Statement",
        "權益變動表", "Statements of Changes in Equity", "Statement of Changes in Equity",
        "現金流量表", "Statements of Cash Flows", "Statement of Cash Flows",
    ]
    for word in title_words:
        c = c.replace(word, "")

    c = c.replace("_", " ")
    c = re.sub(r"\s+", " ", c).strip(" _-")
    return c


def column_contains_any(col_name, keywords):
    """判斷欄名是否包含任一關鍵字；會同時檢查原始欄名與語意清理後欄名。"""
    raw = normalize_table_cell(col_name)
    clean = normalize_column_for_fact_detection(col_name)
    raw_lower = raw.lower()
    clean_lower = clean.lower()
    for keyword in keywords:
        k = str(keyword).lower()
        if k and (k in raw_lower or k in clean_lower):
            return True
    return False


def is_account_code_like(value):
    """
    判斷是否像財報科目代號。

    舊版只接受 A1234 這種代號，但主表常用純數字代號，例如 1100、1170、3110。
    這會導致資產負債表 / 綜合損益表 / 權益變動表無法擷取 item_name。
    """
    s = normalize_table_cell(value)
    if not s:
        return False
    s = s.replace(",", "").replace(" ", "")
    return bool(re.fullmatch(r"[A-Z]?\d{3,}[A-Z]?", s, flags=re.I))


def is_non_value_column_for_fact(col_name):
    """判斷欄位是否較像描述欄，而不是數值欄。"""
    c = normalize_column_for_fact_detection(col_name)
    if not c:
        return False

    non_value_exact = {
        "代號", "會計項目", "項目", "名稱", "說明", "備註", "附註",
        "關係人", "關係人名稱", "關係人類別", "關係", "交易人名稱",
        "交易往來對象", "交易對象", "帳列項目", "科目", "編號",
        "公司名稱", "被投資公司名稱", "所在地區", "主要營業項目",
    }
    if c in non_value_exact:
        return True

    # 對付「資產負債表_會計項目」「代號 Code」這類欄名。
    non_value_keywords = [
        "代號", "會計項目", "項目", "名稱", "說明", "備註", "附註",
        "關係人", "交易對象", "帳列項目", "科目", "編號",
        "公司名稱", "所在地區", "主要營業項目",
    ]
    return any(k in c for k in non_value_keywords)


def is_value_column_for_fact(col_name):
    """
    判斷欄位是否適合作為 fact 的 value 欄位。
    例如：2024年1月1日至3月31日、本期、去年同期、金額、餘額、比率。
    """
    raw = normalize_table_cell(col_name)
    c = normalize_column_for_fact_detection(col_name)
    if not raw and not c:
        return False

    # 先排除描述欄；這一點對主表非常重要，否則「會計項目」可能被誤判。
    if is_non_value_column_for_fact(col_name):
        return False

    # 期間欄：2024年1月1日至3月31日、2024年3月31日、113年3月31日等。
    if re.search(r"\d{2,4}年\d{1,2}月\d{1,2}日", raw) or re.search(r"\d{2,4}年\d{1,2}月\d{1,2}日", c):
        return True

    # 英文/斜線日期欄：2024/3/31、2024/1/1To3/31。
    if re.search(r"\d{4}/\d{1,2}/\d{1,2}", raw) or re.search(r"\d{4}/\d{1,2}/\d{1,2}", c):
        return True

    # 常見數值欄。
    value_keywords = [
        "本期", "去年同期", "上期", "前期", "期末", "期初",
        "金額", "餘額", "帳面金額", "取得價款", "交易金額",
        "股數", "比率", "比例", "百分比", "累計", "合計",
        "amount", "balance", "ratio", "shares",
    ]
    if any(k.lower() in raw.lower() or k.lower() in c.lower() for k in value_keywords):
        return True

    return False


def pick_column_by_keywords(columns, keywords):
    """從欄名清單中挑出最像指定角色的欄位。"""
    exact_matches = []
    contains_matches = []
    for col in columns:
        raw = normalize_table_cell(col)
        clean = normalize_column_for_fact_detection(col)
        for keyword in keywords:
            k = str(keyword)
            if clean == k or raw == k:
                exact_matches.append(col)
            elif k and (k in clean or k in raw):
                contains_matches.append(col)

    if exact_matches:
        return exact_matches[0]

    if contains_matches:
        # 優先選欄名較短者，通常比較接近真正的代號/會計項目欄。
        return sorted(contains_matches, key=lambda x: len(normalize_table_cell(x)))[0]

    return None


def infer_code_and_item(row, columns):
    """從一列中抽出代號與會計項目；強化主表純數字科目代號的支援。"""
    code = ""
    item_name = ""

    # 1) 先用語意欄名找。支援「資產負債表_代號」「資產負債表_會計項目」。
    code_col = pick_column_by_keywords(columns, ["代號", "科目代號", "會計項目代號", "code"])
    item_col = pick_column_by_keywords(columns, ["會計項目", "帳列項目", "項目", "科目", "名稱", "item_name", "item"])

    if code_col is not None:
        code = normalize_table_cell(row.get(code_col, ""))

    if item_col is not None:
        item_name = normalize_table_cell(row.get(item_col, ""))

    # 2) fallback：找出非數值欄，通常是 [代號, 會計項目]。
    if not item_name:
        descriptor_cols = [col for col in columns if not is_value_column_for_fact(col)]
        if not descriptor_cols:
            descriptor_cols = list(columns[: min(3, len(columns))])

        descriptor_values = [normalize_table_cell(row.get(col, "")) for col in descriptor_cols]

        # 主表最常見：第一欄純數字代號、第二欄會計項目。
        if len(descriptor_values) >= 2:
            first, second = descriptor_values[0], descriptor_values[1]
            if is_account_code_like(first) and second:
                code = code or first
                item_name = second
            elif not first and second and parse_number_for_fact(second) is None:
                item_name = second
            elif first and parse_number_for_fact(first) is None:
                item_name = first

        # 再保險：從描述欄中挑第一個非代號、非純數值的文字。
        if not item_name:
            for value in descriptor_values:
                if not value:
                    continue
                if is_account_code_like(value):
                    code = code or value
                    continue
                if parse_number_for_fact(value) is None:
                    item_name = value
                    break

    # 3) 如果 code 欄沒有抓到，但描述欄第一欄像代號，補起來。
    if not code:
        for col in columns[: min(3, len(columns))]:
            value = normalize_table_cell(row.get(col, ""))
            if is_account_code_like(value):
                code = value
                break

    return code, item_name


def build_fact_sentence(company_name, period, table_name, item_name, column_header, value_raw, code):
    """建立人可讀的 fact 文字，例如：聯華電子113Q1 其他收入 股利收入 ...。"""
    pieces = [
        normalize_table_cell(company_name),
        normalize_table_cell(period),
        normalize_table_cell(table_name),
        normalize_table_cell(item_name),
        normalize_table_cell(column_header),
    ]
    base = " ".join([x for x in pieces if x])
    amount = normalize_table_cell(value_raw)
    code_s = normalize_table_cell(code)
    if amount:
        base += f" 金額{amount}"
    if code_s:
        base += f" 代號{code_s}"
    return base.strip()


def export_table_facts_csv(
    df,
    output_dir,
    stock_code,
    company_name,
    period,
    table_name,
    source_csv_filename,
):
    """
    將原本寬表額外輸出成 long-format facts CSV。

    輸出檔：<stock>_<period>_<table_name>__facts.csv
    每列代表一個數值事實：
      公司 + 期間 + 表格 + 代號 + 項目 + 欄位期間 + 金額
    """
    if not EXPORT_TABLE_FACTS_CSV:
        return None
    if df is None or df.empty:
        return None

    columns = list(df.columns)
    rows = []

    fiscal_year = ""
    ad_year = ""
    quarter = ""
    if re.match(r"^\d{3}Q[1-4]$", str(period)):
        fiscal_year = int(str(period)[:3])
        ad_year = fiscal_year + 1911
        quarter = int(str(period)[-1])

    for row_idx, row in df.iterrows():
        code, item_name = infer_code_and_item(row, columns)
        if not item_name:
            continue

        # 跳過說明列、合計空列等不適合轉 fact 的列。
        if item_name in {"說明", "備註", "附註"}:
            continue

        for col in columns:
            col_s = normalize_table_cell(col)
            if not is_value_column_for_fact(col_s):
                continue

            value_raw = normalize_table_cell(row.get(col, ""))
            value_number = parse_number_for_fact(value_raw)
            if value_number is None:
                continue

            value_type, unit = detect_value_type_and_unit(value_raw, col_s)
            fact_sentence = build_fact_sentence(
                company_name=company_name,
                period=period,
                table_name=table_name,
                item_name=item_name,
                column_header=col_s,
                value_raw=value_raw,
                code=code,
            )

            rows.append({
                "record_type": "numeric_fact",
                "source_kind": "html_table",
                "include_reason": "numeric_value_detected",
                "row_text": "",
                "row_json": "",
                "stock_code": stock_code,
                "company_name": company_name,
                "period": period,
                "fiscal_year": fiscal_year,
                "year": ad_year,
                "quarter": quarter,
                "table_name": table_name,
                "code": code,
                "item_name": item_name,
                "column_header": col_s,
                "value_raw": value_raw,
                "value_number": value_number,
                "value_type": value_type,
                "unit": unit,
                "source_csv": source_csv_filename,
                "row_index": int(row_idx),
                "fact_text": fact_sentence,
            })

    if not rows:
        return None

    facts_df = pd.DataFrame(rows)
    facts_filename = make_safe_csv_filename(
        f"{stock_code}_{period}_{table_name}__facts",
        max_bytes=MAX_FILENAME_BYTES,
    )
    facts_path = Path(output_dir) / facts_filename
    facts_df.to_csv(facts_path, index=False, encoding="utf-8-sig")
    print(f"  [Fact] 已輸出 long-format facts：{facts_filename}，共 {len(facts_df)} 筆")
    return facts_df


# ============================================================
# 表格分類
# ============================================================
def identify_table_name(df):
    """根據表格內容關鍵字辨識財報類型。HTML 標題不存在時才會 fallback 到這裡。"""
    content = df.to_string(index=False)
    content_clean = content.replace(" ", "").replace("\n", "")

    related_note_map = {
        "acquisition_of_investments_equity_method": ["取得採用權益法之投資"],
        "acquisition_of_other_assets": ["取得其他資產"],
        "disposal_of_other_assets": ["處分其他資產"],
        "loans_to_related_parties": ["關係人放款"],
        "endorsements_guarantees": ["背書保證"],
        "related_party_acquisition": ["取得價款", "關係人類別/名稱", "帳列項目"],
    }

    for table_name, keywords in related_note_map.items():
        if all(keyword in content_clean for keyword in keywords):
            return table_name

    if (
        ("資產" in content_clean)
        and ("負債" in content_clean)
        and ("權益" in content_clean)
        and ("流動資產" in content_clean or "非流動資產" in content_clean)
    ):
        return "balance_sheet"

    if (
        ("營業收入" in content_clean or "收入" in content_clean)
        and ("營業利益" in content_clean or "營業損益" in content_clean)
        and ("每股盈餘" in content_clean or "本期淨利" in content_clean or "本期損益" in content_clean)
    ):
        return "income_statement"

    if (
        ("營業活動" in content_clean)
        and ("投資活動" in content_clean)
        and ("籌資活動" in content_clean or "融資活動" in content_clean)
    ):
        return "cash_flow"

    if (
        ("期初餘額" in content_clean)
        and ("期末餘額" in content_clean)
        and ("權益" in content_clean or "股本" in content_clean)
    ):
        return "equity_movement"

    keywords_map = {
        "audit_report": ["會計師查核報告", "會計師核閱報告"],
        "related_party_transactions": ["關係人交易", "關係人名稱", "應收關係人", "應付關係人"],
        "segment_info": ["部門資訊", "營運部門", "應報導部門"],
        "inventory": ["存貨", "原料", "製成品", "在製品"],
        "receivables": ["應收帳款", "備抵損失", "應收票據"],
        "payables": ["應付帳款", "應付票據"],
        "property_plant_equipment": ["不動產廠房及設備", "累計折舊"],
        "intangible_assets": ["無形資產", "商譽"],
        "financial_assets": ["金融資產", "透過損益按公允價值衡量", "透過其他綜合損益按公允價值衡量"],
        "revenue_detail": ["客戶合約之收入", "收入認列"],
        "eps_detail": ["每股盈餘", "基本每股盈餘", "稀釋每股盈餘"],
    }

    for table_name, keywords in keywords_map.items():
        for keyword in keywords:
            if keyword in content_clean:
                return table_name

    return "other_table"


# ============================================================
# XBRL / iXBRL note 解析：保留架構
# ============================================================
def clean_note_text(text):
    """清理 note 文字，但保留換行。"""
    if text is None:
        return ""

    text = str(text)
    text = text.replace("\xa0", " ")
    text = text.replace("\u3000", " ")

    lines = []
    for line in text.splitlines():
        line = re.sub(r"[ \t]+", " ", line).strip()
        if line:
            lines.append(line)

    return "\n".join(lines).strip()


def clean_note_text_keep_layout(text):
    """清理 note 文字，但保留 <pre> 的換行與縮排。"""
    if text is None:
        return ""

    text = str(text)
    text = text.replace("\xa0", " ")
    text = text.replace("\u3000", " ")
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    lines = []
    for line in text.split("\n"):
        line = line.rstrip()
        if line.strip():
            lines.append(line)

    return "\n".join(lines)


def unique_keep_order(items):
    """去重複但保留原始順序。"""
    seen = set()
    output = []

    for item in items:
        item_clean = clean_note_text(item)
        if not item_clean:
            continue
        if item_clean not in seen:
            output.append(item_clean)
            seen.add(item_clean)

    return output


def is_ix_nonumeric_tag(tag):
    """判斷是否為 ix:nonumeric / nonumeric 類型標籤。"""
    if tag is None or not getattr(tag, "name", None):
        return False

    tag_name = tag.name.lower()
    return tag_name == "ix:nonumeric" or tag_name == "nonumeric" or tag_name.endswith(":nonumeric")


def get_raw_note_text_from_tag(tag):
    """從 note tag 取得原始文字，不額外插入分隔符。"""
    if tag is None:
        return ""
    return clean_note_text_keep_layout(tag.get_text())


def extract_note_texts_from_node(node):
    """從節點抓取一般 note 文字。"""
    if node is None:
        return []

    note_texts = []

    pre_notes = node.find_all(
        "pre",
        class_=lambda value: value and "note" in str(value).split()
    )

    if pre_notes:
        for tag in pre_notes:
            note_texts.append(tag.get_text("\n", strip=True))
        return unique_keep_order(note_texts)

    ix_notes = node.find_all(is_ix_nonumeric_tag)
    for tag in ix_notes:
        note_texts.append(tag.get_text("\n", strip=True))

    return unique_keep_order(note_texts)


def extract_note_texts_near_table(table):
    """抓取表格內與表格附近的 XBRL 說明文字。"""
    if table is None:
        return []

    note_texts = []
    note_texts.extend(extract_note_texts_from_node(table))

    sibling = table.next_sibling
    scanned = 0

    while sibling is not None and scanned < 20:
        scanned += 1
        sibling_name = getattr(sibling, "name", None)

        if sibling_name == "table":
            break

        if getattr(sibling, "find_all", None):
            note_texts.extend(extract_note_texts_from_node(sibling))

        sibling = sibling.next_sibling

    return unique_keep_order(note_texts)


def append_note_rows_to_df(df, note_texts):
    """將 XBRL 說明文字附加到對應表格 CSV 的最後。"""
    if df is None or df.empty or not note_texts:
        return df

    df = df.copy()
    existing_text = "\n".join(df.fillna("").astype(str).to_numpy().ravel().tolist())

    columns = list(df.columns)
    if not columns:
        return df

    label_col = columns[0]
    text_col = columns[1] if len(columns) >= 2 else columns[0]

    new_rows = []

    for note_text in note_texts:
        note_text = clean_note_text(note_text)

        if not note_text:
            continue

        for line in note_text.splitlines():
            line = clean_note_text(line)

            if not line:
                continue

            if line in existing_text:
                continue

            row = {col: "" for col in columns}
            row[label_col] = "說明"

            if text_col == label_col:
                row[text_col] = f"說明 {line}"
            else:
                row[text_col] = line

            new_rows.append(row)

    if not new_rows:
        return df

    note_df = pd.DataFrame(new_rows, columns=columns)
    return pd.concat([df, note_df], ignore_index=True)


def split_visual_line_to_columns(line, min_spaces=2):
    """
    將 <pre> 的一行依「連續多個空白」切成欄位。
    同時會保留 raw_line，所以即使切欄不完美，也能回溯原始版面。
    """
    line = line.rstrip()
    if not line.strip():
        return []

    pattern = r"[ \t]{" + str(min_spaces) + r",}"
    parts = [part.strip() for part in re.split(pattern, line) if part.strip()]

    if not parts:
        parts = [line.strip()]

    return parts


def parse_note_text_to_structured_rows(note_text, note_index, source, table_index):
    """
    將一段 <pre class="note"> 文字轉為一行一列的結構化資料。

    欄位：
    - note_index
    - source
    - table_index
    - line_no
    - indent_level
    - raw_line
    - col_1, col_2, ...
    """
    note_text = clean_note_text_keep_layout(note_text)
    rows = []

    if not note_text:
        return rows

    for line_no, raw_line in enumerate(note_text.split("\n"), start=1):
        if not raw_line.strip():
            continue

        indent_level = len(raw_line) - len(raw_line.lstrip(" "))
        cols = split_visual_line_to_columns(raw_line, min_spaces=STRUCTURED_NOTE_SPLIT_MIN_SPACES)

        row = {
            "note_index": note_index,
            "source": source,
            "table_index": table_index,
            "line_no": line_no,
            "indent_level": indent_level,
            "raw_line": raw_line,
        }

        for col_idx, value in enumerate(cols, start=1):
            row[f"col_{col_idx}"] = value

        rows.append(row)

    return rows


def build_single_text_structured_note_records(note_records):
    """
    將 structured note records 轉成單一文字欄位版本。

    原本欄位：
    - raw_line
    - col_1
    - col_2
    - ...

    問題：
    - 多數情況 raw_line 與 col_1 完全相同，CSV 會重複兩欄資訊。

    新輸出欄位：
    - note_index
    - source
    - table_index
    - line_no
    - indent_level
    - raw_line

    說明：
    - raw_line 保留原始文字與空白版面，是最完整的一欄。
    - col_1 / col_2 / col_3 不輸出，避免重複與欄位混亂。
    """
    output = []

    for row in note_records:
        raw_line = str(row.get("raw_line", "")).rstrip()

        # 若 raw_line 不存在，才 fallback 到 col_1，避免空白
        if not raw_line:
            raw_line = str(row.get("col_1", "")).rstrip()

        output.append({
            "note_index": row.get("note_index", ""),
            "source": row.get("source", ""),
            "table_index": row.get("table_index", ""),
            "line_no": row.get("line_no", ""),
            "indent_level": row.get("indent_level", ""),
            "raw_line": raw_line,
        })

    return output


def extract_all_xbrl_note_records(html_content):
    """從整份 HTML 中抽出所有 XBRL / iXBRL 說明文字，另存成獨立 CSV。"""
    soup = BeautifulSoup(html_content, "html.parser")
    tables = soup.find_all("table")

    records = []
    seen = set()
    note_index = 1

    for table_index, table in enumerate(tables, start=1):
        note_texts = extract_note_texts_near_table(table)

        for note_text in note_texts:
            note_text = clean_note_text(note_text)
            if not note_text or note_text in seen:
                continue

            records.append({
                "note_index": note_index,
                "source": "table_or_near_table",
                "table_index": table_index,
                "note_text": note_text,
            })
            seen.add(note_text)
            note_index += 1

    all_notes = []
    pre_notes = soup.find_all(
        "pre",
        class_=lambda value: value and "note" in str(value).split()
    )

    if pre_notes:
        for tag in pre_notes:
            all_notes.append(tag.get_text("\n", strip=True))
    else:
        for tag in soup.find_all(is_ix_nonumeric_tag):
            all_notes.append(tag.get_text("\n", strip=True))

    for note_text in all_notes:
        note_text = clean_note_text(note_text)
        if not note_text or note_text in seen:
            continue

        records.append({
            "note_index": note_index,
            "source": "global_note",
            "table_index": "",
            "note_text": note_text,
        })
        seen.add(note_text)
        note_index += 1

    return records


def extract_structured_note_records(html_content):
    """
    掃描整份 HTML，把所有 <pre class="note"> / <ix:nonumeric>
    轉成保留行列架構的 structured CSV records。
    """
    soup = BeautifulSoup(html_content, "html.parser")
    tables = soup.find_all("table")

    records = []
    seen_texts = set()
    note_index = 1

    for table_index, table in enumerate(tables, start=1):
        pre_notes = table.find_all(
            "pre",
            class_=lambda value: value and "note" in str(value).split()
        )

        if pre_notes:
            for tag in pre_notes:
                raw_text = get_raw_note_text_from_tag(tag)

                if not raw_text or raw_text in seen_texts:
                    continue

                rows = parse_note_text_to_structured_rows(
                    note_text=raw_text,
                    note_index=note_index,
                    source="table_pre_note",
                    table_index=table_index,
                )
                records.extend(rows)
                seen_texts.add(raw_text)
                note_index += 1
            continue

        ix_notes = table.find_all(is_ix_nonumeric_tag)
        for tag in ix_notes:
            raw_text = get_raw_note_text_from_tag(tag)

            if not raw_text or raw_text in seen_texts:
                continue

            rows = parse_note_text_to_structured_rows(
                note_text=raw_text,
                note_index=note_index,
                source="table_ix_nonumeric",
                table_index=table_index,
            )
            records.extend(rows)
            seen_texts.add(raw_text)
            note_index += 1

    # 補抓不在 table 內的 pre.note
    all_pre_notes = soup.find_all(
        "pre",
        class_=lambda value: value and "note" in str(value).split()
    )

    for tag in all_pre_notes:
        raw_text = get_raw_note_text_from_tag(tag)

        if not raw_text or raw_text in seen_texts:
            continue

        rows = parse_note_text_to_structured_rows(
            note_text=raw_text,
            note_index=note_index,
            source="global_pre_note",
            table_index="",
        )
        records.extend(rows)
        seen_texts.add(raw_text)
        note_index += 1

    return records


def infer_short_note_block_title(note_rows):
    """
    從 note block 推測短標題，只存到 CSV 欄位，不直接拿完整文字當檔名。
    避免「其他事項-提及其他會計師之核閱 ...」整段內文塞進檔名。
    """
    for row in note_rows[:8]:
        value = str(row.get("col_1", "")).strip()
        raw_line = str(row.get("raw_line", "")).strip()
        text = clean_note_text(value or raw_line)

        if not text:
            continue

        # 句子太長或含大量標點，通常是說明內文，不適合作檔名標題。
        if len(text) > 35:
            continue
        if re.search(r"[，。；;,.]", text):
            continue

        return text

    return ""


def add_note_block_title_to_rows(rows):
    """將推測出的短 note title 寫進每列資料，方便在 CSV 中查閱。"""
    title = infer_short_note_block_title(rows)
    for row in rows:
        row["note_block_title"] = title
    return rows


def get_note_block_full_text(rows):
    """
    合併 note block 的原始文字。
    優先使用 raw_line，因為 raw_line 保留原始版面文字。
    """
    lines = []

    for row in rows:
        raw_line = str(row.get("raw_line", "")).strip()
        if raw_line:
            lines.append(raw_line)

    return "\n".join(lines).strip()


def should_save_note_block(rows):
    """
    判斷這個 note block 是否值得單獨另存成 note_XXX.csv。

    過濾目標：
    - 只有一行公司名稱，例如 ECP VITA PTE. LTD.
    - 只有單一欄位名稱或短詞
    - XBRL/iXBRL 裡被切成獨立 note 的零碎文字

    注意：
    - 此函數只影響「每個 note block 另存 CSV」。
    - 不會影響 xbrl_notes.csv 與 xbrl_notes_structured.csv 總表。
    """
    if not FILTER_SHORT_NOTE_BLOCK_CSV:
        return True

    if not rows:
        return False

    full_text = get_note_block_full_text(rows)
    compact_text = re.sub(r"\s+", "", full_text)

    line_count = len([
        str(row.get("raw_line", "")).strip()
        for row in rows
        if str(row.get("raw_line", "")).strip()
    ])

    # 條件 1：單行且總文字太短，通常只是公司名稱或欄位值
    if line_count <= 1 and len(compact_text) < MIN_NOTE_BLOCK_CHARS:
        return False

    # 條件 2：行數很少且總文字很短，也不單獨輸出
    if line_count < MIN_NOTE_BLOCK_LINES and len(compact_text) < MIN_NOTE_BLOCK_CHARS:
        return False

    # 條件 3：只有英文字母、數字、空白、符號，且很短，多半是公司名稱或英文欄位
    if (
        line_count <= 1
        and len(compact_text) < 40
        and re.fullmatch(r"[A-Za-z0-9 .,&'()\-/]+", full_text)
    ):
        return False

    return True


def save_each_structured_note_block(note_records, output_dir, stock_code, period):
    """
    把每個 note block 各自輸出成一個 CSV。

    重要：
    - 檔名只用 note index，不再用 note 內文當檔名。
    - 完整內容保留在 CSV 的 raw_line / col_x 欄位。
    - 短標題另存 note_block_title 欄位，不放進檔名。
    """
    if not note_records:
        return 0

    by_note_index = {}
    for row in note_records:
        note_index = row.get("note_index")
        by_note_index.setdefault(note_index, []).append(row)

    saved_count = 0

    for note_index, rows in by_note_index.items():
        if not should_save_note_block(rows):
            continue

        rows = add_note_block_title_to_rows(rows)

        filename = make_safe_csv_filename(
            f"{stock_code}_{period}_note_{int(note_index):03d}",
            max_bytes=MAX_FILENAME_BYTES,
        )
        save_path = output_dir / filename

        pd.DataFrame(rows).to_csv(save_path, index=False, encoding="utf-8-sig")
        saved_count += 1

    return saved_count



def cleanup_old_note_block_csv(output_dir, stock_code, period):
    """
    清除舊版輸出的個別 note block CSV，例如：
    2303_114Q2_note_001.csv
    2303_114Q2_note_075.csv

    不會刪除：
    - 2303_114Q2_xbrl_notes.csv
    - 2303_114Q2_xbrl_notes_structured.csv
    """
    if not CLEAN_OLD_NOTE_BLOCK_CSV:
        return 0

    output_dir = Path(output_dir)
    pattern = f"{stock_code}_{period}_note_*.csv"

    deleted_count = 0

    for file_path in output_dir.glob(pattern):
        expected_pattern = rf"{re.escape(stock_code)}_{re.escape(period)}_note_\d{{3}}\.csv"
        if re.fullmatch(expected_pattern, file_path.name):
            file_path.unlink()
            deleted_count += 1

    return deleted_count



# ============================================================
# Facts 優化輸出：讓 all_table_facts 更適合查詢、比對、RAG / LLM 使用
# ============================================================
def split_table_name_and_instance(table_name):
    """拆出表名與同名表序號，例如 其他收入_2 -> (其他收入, 2)。"""
    table_name = normalize_table_cell(table_name)
    m = re.match(r"^(.*)_(\d+)$", table_name)
    if m and m.group(1):
        return m.group(1), int(m.group(2))
    return table_name, 1


def standardize_table_name(table_name):
    """將英文 fallback 或相近表名標準化成穩定中文名稱。"""
    table_base, _ = split_table_name_and_instance(table_name)
    s = normalize_table_cell(table_base)
    compact = s.replace(" ", "").lower()

    mappings = [
        ("資產負債表", ["資產負債表", "balancesheet", "balance_sheet"]),
        ("綜合損益表", ["綜合損益表", "損益表", "incomestatement", "income_statement"]),
        ("權益變動表", ["權益變動表", "權益變動", "equitymovement", "equity_movement"]),
        ("現金流量表", ["現金流量表", "cashflow", "cash_flow"]),
    ]
    for canonical, keys in mappings:
        if any(k.replace(" ", "").lower() in compact for k in keys):
            return canonical
    return s


def classify_table_group(table_name):
    """粗分類 facts 來源，方便後續篩選主表與附註表。"""
    canonical = standardize_table_name(table_name)
    if canonical in {"資產負債表", "綜合損益表", "權益變動表", "現金流量表"}:
        return "main_statement"

    s = normalize_table_cell(table_name)
    related_keywords = ["關係人", "背書保證", "母子公司", "子公司", "大陸地區", "被投資公司"]
    if any(k in s for k in related_keywords):
        return "note_related_party_or_investment"

    note_keywords = ["收入", "成本", "利益", "損失", "應收", "財務成本", "明細", "帳齡", "薪酬", "所得稅"]
    if any(k in s for k in note_keywords):
        return "note_detail"

    return "other"


def split_zh_en_text(text):
    """
    把常見的「中文 English」欄位拆成中文與英文兩欄。
    若沒有中文，保留在中文欄，避免把公司英文名稱誤判成英文說明。
    """
    s = normalize_table_cell(text)
    if not s:
        return "", ""

    has_cjk = bool(re.search(r"[\u4e00-\u9fff]", s))
    has_ascii_word = bool(re.search(r"[A-Za-z]", s))
    if not (has_cjk and has_ascii_word):
        return s, ""

    # 從第一個英文詞開始切；常見於「折舊費用 Depreciation expense」。
    candidates = list(re.finditer(r"\s+[A-Za-z][A-Za-z0-9 ,;:/().&%\-]*$", s))
    if candidates:
        m = candidates[-1]
        zh = s[:m.start()].strip()
        en = s[m.start():].strip()
        if zh and en:
            return zh, en

    # fallback：找第一個英文大段落。
    m = re.search(r"[A-Za-z][A-Za-z0-9 ,;:/().&%\-]*$", s)
    if m:
        zh = s[:m.start()].strip()
        en = s[m.start():].strip()
        if zh and en:
            return zh, en

    return s, ""


def clean_column_header_label(column_header):
    """清除欄名中重複英文日期，例如 2024年1月1日至6月30日 2024/1/1To6/30。"""
    s = normalize_table_cell(column_header)
    s = re.sub(r"\s+\d{4}/\d{1,2}/\d{1,2}\s*To\s*\d{1,2}/\d{1,2}$", "", s, flags=re.I)
    s = re.sub(r"\s+\d{4}/\d{1,2}/\d{1,2}\s*To\s*\d{4}/\d{1,2}/\d{1,2}$", "", s, flags=re.I)
    s = re.sub(r"\s+\d{4}/\d{1,2}/\d{1,2}$", "", s, flags=re.I)
    return s.strip()


def convert_year_to_ad(year_text):
    """民國年或西元年轉西元年。"""
    try:
        y = int(str(year_text))
    except Exception:
        return ""
    if 1 <= y < 1000:
        return y + 1911
    return y


def parse_date_parts_to_iso(year_text, month_text, day_text):
    """將年月日文字轉 YYYY-MM-DD；失敗時回空字串。"""
    y = convert_year_to_ad(year_text)
    if not y:
        return ""
    try:
        m = int(month_text)
        d = int(day_text)
        return f"{int(y):04d}-{m:02d}-{d:02d}"
    except Exception:
        return ""


def parse_column_period(column_header, report_year="", report_quarter=""):
    """
    解析 column_header 的期間資訊。

    輸出欄位：
    - column_header_clean
    - period_kind: duration / instant / relative / unknown
    - period_role: current / prior / current_ytd / prior_ytd / current_end / current_beginning / unknown
    - period_start_date / period_end_date
    """
    original = normalize_table_cell(column_header)
    clean = clean_column_header_label(original)

    result = {
        "column_header_clean": clean,
        "period_kind": "unknown",
        "period_role": "unknown",
        "period_start_date": "",
        "period_end_date": "",
    }

    # 例：2024年1月1日至6月30日、113年1月1日至6月30日、2024年1月1日至2024年6月30日
    duration_pattern = (
        r"(?P<y1>\d{2,4})年(?P<m1>\d{1,2})月(?P<d1>\d{1,2})日"
        r"(?:至|到|~|～|-|－)"
        r"(?:(?P<y2>\d{2,4})年)?(?P<m2>\d{1,2})月(?P<d2>\d{1,2})日"
    )
    m = re.search(duration_pattern, clean)
    if m:
        y1 = m.group("y1")
        y2 = m.group("y2") or y1
        start_date = parse_date_parts_to_iso(y1, m.group("m1"), m.group("d1"))
        end_date = parse_date_parts_to_iso(y2, m.group("m2"), m.group("d2"))
        result["period_kind"] = "duration"
        result["period_start_date"] = start_date
        result["period_end_date"] = end_date
        try:
            y_end = int(end_date[:4]) if end_date else None
            if report_year and y_end == int(report_year):
                result["period_role"] = "current"
            elif report_year and y_end == int(report_year) - 1:
                result["period_role"] = "prior"
        except Exception:
            pass
        return result

    # 例：2024年6月30日、113年6月30日
    instant_pattern = r"(?P<y>\d{2,4})年(?P<m>\d{1,2})月(?P<d>\d{1,2})日"
    m = re.search(instant_pattern, clean)
    if m:
        end_date = parse_date_parts_to_iso(m.group("y"), m.group("m"), m.group("d"))
        result["period_kind"] = "instant"
        result["period_end_date"] = end_date
        try:
            y_end = int(end_date[:4]) if end_date else None
            if report_year and y_end == int(report_year):
                result["period_role"] = "current"
            elif report_year and y_end == int(report_year) - 1:
                result["period_role"] = "prior"
        except Exception:
            pass
        return result

    # 相對期間欄位。
    relative_map = [
        ("去年同期累計", "prior_ytd"),
        ("本期累計", "current_ytd"),
        ("去年同期", "prior"),
        ("本期期末", "current_end"),
        ("本期期初", "current_beginning"),
        ("期末", "current_end"),
        ("期初", "current_beginning"),
        ("本期", "current"),
        ("上期", "prior"),
        ("前期", "prior"),
    ]
    for key, role in relative_map:
        if key in clean:
            result["period_kind"] = "relative"
            result["period_role"] = role
            return result

    return result


def parse_report_period_meta(period):
    """從 113Q2 解析民國年、西元年、季度。"""
    period_s = normalize_table_cell(period)
    m = re.match(r"^(\d{3})Q([1-4])$", period_s)
    if not m:
        return "", "", ""
    fiscal_year = int(m.group(1))
    year = fiscal_year + 1911
    quarter = int(m.group(2))
    return fiscal_year, year, quarter


def build_optimized_fact_text(row):
    """建立較乾淨、適合檢索/RAG 的文字。"""
    company = normalize_table_cell(row.get("company_name", ""))
    period = normalize_table_cell(row.get("period", ""))
    table_name = normalize_table_cell(row.get("table_name_canonical", row.get("table_name", "")))
    code = normalize_table_cell(row.get("code", ""))
    item = normalize_table_cell(row.get("item_name_zh", row.get("item_name", "")))
    header = normalize_table_cell(row.get("column_header_clean", row.get("column_header", "")))
    value_raw = normalize_table_cell(row.get("value_raw", ""))
    unit = normalize_table_cell(row.get("unit", ""))

    pieces = [company, period, table_name, item, header]
    text = " ".join([p for p in pieces if p])
    if value_raw:
        text += f" 數值{value_raw}"
    if unit:
        text += f" 單位{unit}"
    if code:
        text += f" 代號{code}"
    return text.strip()


def make_fact_key(row):
    """建立穩定 fact key，利於去重與資料庫 upsert。"""
    import hashlib
    keys = [
        row.get("stock_code", ""),
        row.get("period", ""),
        row.get("table_name_canonical", row.get("table_name", "")),
        row.get("table_instance", ""),
        row.get("code", ""),
        row.get("item_name_zh", row.get("item_name", "")),
        row.get("column_header_clean", row.get("column_header", "")),
        row.get("value_raw", ""),
        row.get("source_csv", ""),
        row.get("row_index", ""),
    ]
    raw = "|".join(normalize_table_cell(x) for x in keys)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def optimize_facts_dataframe(facts_df):
    """
    將原始 all_table_facts 轉成優化欄位版。

    不刪除原始欄位，避免資料遺失；只新增標準化/解析後欄位並調整欄位順序。
    """
    if facts_df is None or facts_df.empty:
        return facts_df

    df = facts_df.copy()

    # 確保必要欄位存在，避免外部 CSV 少欄時失敗。
    required_cols = [
        "stock_code", "company_name", "period", "fiscal_year", "year", "quarter",
        "table_name", "code", "item_name", "column_header", "value_raw", "value_number",
        "value_type", "unit", "source_csv", "row_index", "fact_text",
    ]
    for col in required_cols:
        if col not in df.columns:
            df[col] = ""

    # 字串欄位清理。
    for col in ["company_name", "period", "table_name", "code", "item_name", "column_header", "value_raw", "value_type", "unit", "source_csv", "fact_text"]:
        df[col] = df[col].map(normalize_table_cell)

    # 報告期間 meta 補齊。
    meta = df["period"].map(parse_report_period_meta)
    df["report_fiscal_year"] = [x[0] for x in meta]
    df["report_year"] = [x[1] for x in meta]
    df["report_quarter"] = [x[2] for x in meta]

    # 表格名稱標準化與分類。
    table_split = df["table_name"].map(split_table_name_and_instance)
    df["table_name_base"] = [x[0] for x in table_split]
    df["table_instance"] = [x[1] for x in table_split]
    df["table_name_canonical"] = df["table_name"].map(standardize_table_name)
    df["table_group"] = df["table_name"].map(classify_table_group)
    df["is_main_statement"] = df["table_group"].eq("main_statement")

    # 項目中英文拆分。
    item_split = df["item_name"].map(split_zh_en_text)
    df["item_name_zh"] = [x[0] for x in item_split]
    df["item_name_en"] = [x[1] for x in item_split]

    # 欄位期間解析。
    period_records = []
    for _, row in df.iterrows():
        report_year = row.get("report_year", "")
        report_quarter = row.get("report_quarter", "")
        period_records.append(parse_column_period(row.get("column_header", ""), report_year, report_quarter))
    period_df = pd.DataFrame(period_records)
    for col in period_df.columns:
        df[col] = period_df[col]

    # 金額比例標準化。
    df["value_number"] = pd.to_numeric(df["value_number"], errors="coerce")
    df["value_scale"] = df["unit"].map(lambda u: 1000 if normalize_table_cell(u) == "TWD_1000" else 1)
    df["value_twd"] = df.apply(
        lambda r: r["value_number"] * r["value_scale"] if normalize_table_cell(r.get("value_type", "")) == "amount" and pd.notna(r["value_number"]) else "",
        axis=1,
    )
    df["value_ratio"] = df.apply(
        lambda r: r["value_number"] / 100 if normalize_table_cell(r.get("value_type", "")) == "percent" and pd.notna(r["value_number"]) else "",
        axis=1,
    )
    df["value_sign"] = df["value_number"].map(lambda x: "negative" if pd.notna(x) and x < 0 else ("positive" if pd.notna(x) and x > 0 else ("zero" if pd.notna(x) else "")))

    # 品質旗標。
    df["has_code"] = df["code"].ne("")
    df["period_parse_status"] = df["period_kind"].map(lambda x: "parsed" if x in {"duration", "instant", "relative"} else "unparsed")
    dup_subset = ["stock_code", "period", "table_name_canonical", "code", "item_name_zh", "column_header_clean", "value_number", "source_csv"]
    df["duplicate_rank"] = df.groupby(dup_subset, dropna=False).cumcount() + 1
    df["is_duplicate_fact"] = df["duplicate_rank"].gt(1)

    # 穩定 key 與乾淨 fact_text。
    df["fact_key"] = df.apply(make_fact_key, axis=1)
    df["fact_text_clean"] = df.apply(build_optimized_fact_text, axis=1)

    preferred_order = [
        "fact_key",
        "stock_code", "company_name", "period", "report_fiscal_year", "report_year", "report_quarter",
        "table_group", "is_main_statement", "table_name_canonical", "table_name_base", "table_instance", "table_name",
        "code", "has_code", "item_name_zh", "item_name_en", "item_name",
        "column_header_clean", "period_kind", "period_role", "period_start_date", "period_end_date", "column_header",
        "value_raw", "value_number", "value_type", "unit", "value_scale", "value_twd", "value_ratio", "value_sign",
        "period_parse_status", "duplicate_rank", "is_duplicate_fact",
        "source_csv", "row_index", "fact_text_clean", "fact_text",
    ]
    remaining = [col for col in df.columns if col not in preferred_order]
    return df[preferred_order + remaining]


def save_optimized_facts_csv(facts_df, output_path):
    """輸出優化後 facts CSV；若關閉 EXPORT_OPTIMIZED_FACTS_CSV 則不輸出。"""
    if not EXPORT_OPTIMIZED_FACTS_CSV:
        return None, None
    if facts_df is None or facts_df.empty:
        return None, None
    optimized_df = optimize_facts_dataframe(facts_df)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    optimized_df.to_csv(output_path, index=False, encoding="utf-8-sig")
    return optimized_df, str(output_path)


def optimize_existing_facts_csv(input_csv_path, output_csv_path=None):
    """
    對已經存在的 all_table_facts CSV 另做優化輸出。
    可直接用來處理舊版產出的檔案。
    """
    input_csv_path = Path(input_csv_path)
    df = pd.read_csv(input_csv_path, encoding="utf-8-sig")
    optimized_df = optimize_facts_dataframe(df)
    if output_csv_path is None:
        output_csv_path = input_csv_path.with_name(input_csv_path.stem + "_optimized.csv")
    output_csv_path = Path(output_csv_path)
    optimized_df.to_csv(output_csv_path, index=False, encoding="utf-8-sig")
    print(f"[Optimize] 已輸出優化 facts：{output_csv_path}，共 {len(optimized_df)} 筆")
    return str(output_csv_path)



# ============================================================
# all_table_facts 完整納入輔助函式
# ============================================================
def dataframe_row_to_text(row, columns):
    """把一列資料壓成可檢索文字；空欄位會略過。"""
    pieces = []
    for col in columns:
        col_s = normalize_table_cell(col)
        value_s = normalize_table_cell(row.get(col, ""))
        if not value_s:
            continue
        if col_s:
            pieces.append(f"{col_s}: {value_s}")
        else:
            pieces.append(value_s)
    return " | ".join(pieces).strip()


def dataframe_row_to_json(row, columns):
    """把一列資料保留成 JSON 字串，避免 raw row 補進 all_table_facts 後無法回溯原始欄位。"""
    record = {}
    for col in columns:
        col_s = normalize_table_cell(col) or "欄位"
        value_s = normalize_table_cell(row.get(col, ""))
        if value_s:
            record[col_s] = value_s
    return json.dumps(record, ensure_ascii=False)


def infer_text_item_name_from_row(row, columns, row_text):
    """raw row 沒有標準會計項目欄時，從列內容挑一個短文字當 item_name。"""
    code, item_name = infer_code_and_item(row, columns)
    if item_name:
        return code, item_name

    for col in columns:
        value = normalize_table_cell(row.get(col, ""))
        if not value:
            continue
        if is_account_code_like(value):
            code = code or value
            continue
        # 避免把純數字金額當 item_name。
        if parse_number_for_fact(value) is None:
            return code, value[:300]

    return code, row_text[:300]


def build_raw_table_row_facts_df(
    df,
    stock_code,
    company_name,
    period,
    table_name,
    source_csv_filename,
    source_kind="html_table",
    include_reason="no_numeric_facts_for_source_csv",
):
    """
    將無法轉成 numeric facts 的原始 CSV 表格列，補成 all_table_facts 可收納的文字紀錄。

    目的：all_table_facts 不再只包含「可解析數字」的表，會讓資料夾內每張原始表都至少可在總表中被找到。
    """
    if df is None or df.empty:
        return None

    columns = list(df.columns)
    fiscal_year, ad_year, quarter = parse_report_period_meta(period)
    rows = []

    for row_idx, row in df.iterrows():
        row_text = dataframe_row_to_text(row, columns)
        if not row_text:
            continue

        code, item_name = infer_text_item_name_from_row(row, columns, row_text)
        row_json = dataframe_row_to_json(row, columns)

        fact_sentence = " ".join([
            x for x in [
                normalize_table_cell(company_name),
                normalize_table_cell(period),
                normalize_table_cell(table_name),
                normalize_table_cell(item_name),
                row_text,
            ] if x
        ]).strip()

        rows.append({
            "record_type": "source_table_row",
            "source_kind": source_kind,
            "include_reason": include_reason,
            "row_text": row_text,
            "row_json": row_json,
            "stock_code": stock_code,
            "company_name": company_name,
            "period": period,
            "fiscal_year": fiscal_year,
            "year": ad_year,
            "quarter": quarter,
            "table_name": table_name,
            "code": code,
            "item_name": item_name,
            "column_header": RAW_ROW_COLUMN_HEADER,
            "value_raw": "",
            "value_number": "",
            "value_type": "text",
            "unit": "",
            "source_csv": source_csv_filename,
            "row_index": int(row_idx),
            "fact_text": fact_sentence,
        })

    if not rows:
        return None
    return pd.DataFrame(rows)


def register_output_csv(output_csv_registry, df, table_name, filename, source_kind):
    """記錄本次輸出的原始 CSV，之後用來保證 all_table_facts 覆蓋所有表。"""
    if df is None:
        return
    output_csv_registry.append({
        "df": df.copy(),
        "table_name": table_name,
        "source_csv": filename,
        "source_kind": source_kind,
    })


def append_missing_output_csvs_as_raw_facts(
    all_fact_frames,
    output_csv_registry,
    stock_code,
    company_name,
    period,
):
    """
    將沒有 numeric facts 的來源 CSV 補成 raw row facts。

    注意：這裡補的是「本次程式產生的原始 CSV」，不包含 *_facts.csv、all_table_facts.csv、optimized.csv 這些衍生檔。
    """
    if not ENSURE_EVERY_OUTPUT_CSV_IN_ALL_FACTS:
        return all_fact_frames

    frames = list(all_fact_frames or [])
    represented_sources = set()
    for frame in frames:
        if frame is None or frame.empty or "source_csv" not in frame.columns:
            continue
        represented_sources.update(frame["source_csv"].dropna().astype(str).tolist())

    added_sources = []
    for entry in output_csv_registry:
        source_csv = str(entry.get("source_csv", ""))
        if not source_csv:
            continue

        # 預設只補完全沒有 numeric facts 的表，避免同一張表在總表中重複膨脹。
        if RAW_ROW_FALLBACK_ONLY_WHEN_NO_NUMERIC_FACTS and source_csv in represented_sources:
            continue

        raw_df = build_raw_table_row_facts_df(
            df=entry.get("df"),
            stock_code=stock_code,
            company_name=company_name,
            period=period,
            table_name=entry.get("table_name", ""),
            source_csv_filename=source_csv,
            source_kind=entry.get("source_kind", "output_csv"),
            include_reason="source_csv_had_no_numeric_facts",
        )
        if raw_df is not None and not raw_df.empty:
            frames.append(raw_df)
            represented_sources.add(source_csv)
            added_sources.append(source_csv)

    if added_sources:
        print(f"  [Fact] 已補入沒有 numeric facts 的原始 CSV：{len(added_sources)} 個")
        for source in added_sources[:20]:
            print(f"    - {source}")
        if len(added_sources) > 20:
            print(f"    ... 另有 {len(added_sources) - 20} 個")


    return frames


def is_original_csv_for_all_facts_scan(filename):
    """
    判斷資料夾掃描時，哪些 CSV 要被視為「原始表」。

    預設排除衍生檔，避免 all_table_facts 把自己的輸出或 *_facts.csv 再吃回去造成重複膨脹。
    會保留：一般寬表 CSV、xbrl_notes.csv、xbrl_notes_structured.csv、note_XXX.csv。
    """
    name = str(filename)
    lower = name.lower()

    if not lower.endswith(".csv"):
        return False

    if INCLUDE_DERIVED_CSVS_WHEN_SCANNING_FOLDER:
        return True

    derived_patterns = [
        "all_table_facts",
        "coverage_report",
        "source_table_index",
        "numeric_facts",
        "__all_company_all_period_facts",
        "__all_company_all_period_numeric_facts",
    ]
    if any(pattern in lower for pattern in derived_patterns):
        return False

    # 個別 long-format facts 是原始寬表的衍生物，預設不再當原始 source CSV 掃描。
    if lower.endswith("_facts.csv"):
        return False

    return True


def infer_table_name_from_csv_filename(filename, stock_code, period):
    """從 CSV 檔名反推出 table_name。"""
    stem = Path(str(filename)).stem
    prefixes = [
        f"{stock_code}_{period}_",
        f"{stock_code}_{period}__",
        f"{stock_code}_{period}",
    ]

    table_name = stem
    for prefix in prefixes:
        if table_name.startswith(prefix):
            table_name = table_name[len(prefix):]
            break

    table_name = table_name.strip("_ ")
    return table_name or stem


def read_csv_with_encoding_fallback(csv_path):
    """讀取 CSV，支援 utf-8-sig / utf-8 / big5 / cp950。"""
    csv_path = Path(csv_path)
    errors = []

    for enc in ["utf-8-sig", "utf-8", "big5", "cp950"]:
        try:
            return pd.read_csv(csv_path, encoding=enc, dtype=str, keep_default_na=False)
        except Exception as e:
            errors.append(f"{enc}: {e}")

    raise RuntimeError(f"無法讀取 CSV：{csv_path}；" + " | ".join(errors[-2:]))


def append_existing_folder_csvs_to_registry(
    output_csv_registry,
    output_dir,
    stock_code,
    period,
):
    """
    掃描該公司/季度輸出資料夾內的既有 CSV，把尚未登錄的原始表補進 registry。

    v3 的 registry 只包含「本次解析流程有記錄到的 CSV」。若資料夾內已有舊檔、手動放入的 CSV，
    或某些流程漏登錄，all_table_facts 就不會覆蓋到它們。v4 在輸出總表前追加一次資料夾掃描。
    """
    if not SCAN_EXISTING_FOLDER_CSVS_INTO_ALL_FACTS:
        return output_csv_registry

    output_dir = Path(output_dir)
    if not output_dir.exists():
        return output_csv_registry

    registry = list(output_csv_registry or [])
    registered_sources = {str(entry.get("source_csv", "")) for entry in registry if entry.get("source_csv")}

    added = []
    skipped_read_error = []

    for csv_path in sorted(output_dir.glob("*.csv")):
        filename = csv_path.name

        if not is_original_csv_for_all_facts_scan(filename):
            continue

        if filename in registered_sources:
            continue

        try:
            df = read_csv_with_encoding_fallback(csv_path)
        except Exception as e:
            skipped_read_error.append((filename, str(e)))
            continue

        table_name = infer_table_name_from_csv_filename(filename, stock_code, period)
        register_output_csv(
            output_csv_registry=registry,
            df=df,
            table_name=table_name,
            filename=filename,
            source_kind="folder_scan_existing_csv",
        )
        registered_sources.add(filename)
        added.append(filename)

    if added:
        print(f"  [Folder Scan] 已把資料夾內未登錄的原始 CSV 補進 source registry：{len(added)} 個")
        for name in added[:30]:
            print(f"    - {name}")
        if len(added) > 30:
            print(f"    ... 另有 {len(added) - 30} 個")

    if skipped_read_error:
        print(f"  [Warning][Folder Scan] 有 {len(skipped_read_error)} 個 CSV 讀取失敗，未補進 source registry")
        for name, err in skipped_read_error[:10]:
            print(f"    - {name}: {err}")

    return registry


def build_all_facts_coverage_dataframe(all_facts_df, output_csv_registry):
    """
    建立 RAG-friendly source coverage 表。

    v5 的語意：
    - all_table_facts 只存 numeric_fact。
    - 沒有進 all_table_facts 不代表漏資料；代表該來源表沒有可解析的數值 fact，
      但原始 CSV 仍然保留，後續應以 DealTable / DealNote / Parent-Child 方式處理。
    """
    registry_by_source = {}
    for entry in output_csv_registry or []:
        source = str(entry.get("source_csv", ""))
        if not source:
            continue
        if source not in registry_by_source:
            df = entry.get("df")
            registry_by_source[source] = {
                "source_csv": source,
                "table_name": entry.get("table_name", ""),
                "source_kind": entry.get("source_kind", ""),
                "source_row_count": len(df) if isinstance(df, pd.DataFrame) else "",
            }

    actual_counts = {}
    record_types = {}
    numeric_counts = {}
    if all_facts_df is not None and not all_facts_df.empty and "source_csv" in all_facts_df.columns:
        temp = all_facts_df.copy()
        temp["source_csv"] = temp["source_csv"].fillna("").astype(str)
        actual_counts = temp.groupby("source_csv").size().to_dict()
        if "record_type" in temp.columns:
            record_types = (
                temp.groupby("source_csv")["record_type"]
                .apply(lambda s: ",".join(sorted(set(str(x) for x in s.dropna() if str(x)))))
                .to_dict()
            )
            numeric_temp = temp[temp["record_type"].astype(str).eq("numeric_fact")]
        else:
            numeric_temp = temp
        if not numeric_temp.empty:
            numeric_counts = numeric_temp.groupby("source_csv").size().to_dict()

    rows = []
    for source, meta in sorted(registry_by_source.items()):
        numeric_rows = int(numeric_counts.get(source, 0))
        has_numeric = numeric_rows > 0
        source_kind = str(meta.get("source_kind", ""))
        if source_kind in {"xbrl_notes", "xbrl_notes_structured"}:
            rag_chunk_type = "DealNoteStructured" if source_kind == "xbrl_notes_structured" else "DealNote"
        else:
            rag_chunk_type = "DealTable"

        rows.append({
            "source_csv": source,
            "table_name": meta.get("table_name", ""),
            "source_kind": source_kind,
            "source_row_count": meta.get("source_row_count", ""),
            "numeric_fact_rows": numeric_rows,
            "has_numeric_facts": has_numeric,
            "rows_in_all_table_facts": int(actual_counts.get(source, 0)),
            "record_types_in_all_table_facts": record_types.get(source, ""),
            "raw_csv_preserved": True,
            "recommended_rag_chunk_type": rag_chunk_type,
            "ingest_note": "numeric facts in all_table_facts" if has_numeric else "no numeric fact; use original CSV as parent/child source",
        })

    return pd.DataFrame(rows)


def save_source_table_index(output_dir, stock_code, period, all_facts_df, output_csv_registry):
    """輸出 source table index，供 RAG 建庫流程掃描原始表格來源。"""
    if not EXPORT_SOURCE_TABLE_INDEX_CSV:
        return ""

    index_df = build_all_facts_coverage_dataframe(all_facts_df, output_csv_registry)
    if index_df.empty:
        return ""

    filename = make_safe_csv_filename(
        f"{stock_code}_{period}__source_table_index",
        max_bytes=MAX_FILENAME_BYTES,
    )
    save_path = Path(output_dir) / filename
    index_df.to_csv(save_path, index=False, encoding="utf-8-sig")

    total_sources = len(index_df)
    with_numeric = int(index_df["has_numeric_facts"].astype(bool).sum())
    without_numeric = total_sources - with_numeric
    print(
        f"  [Source Index] 已輸出來源表索引：{filename}；"
        f"原始 CSV {total_sources} 個，其中 {with_numeric} 個有 numeric facts，{without_numeric} 個保留為原始表來源"
    )
    return str(save_path)


def save_all_facts_coverage_report(output_dir, stock_code, period, all_facts_df, output_csv_registry):
    """
    輸出 all_table_facts coverage report。

    v5 中 coverage 的目的不是強制所有 CSV 都進 all_table_facts，
    而是記錄哪些來源 CSV 產生 numeric_fact，哪些只保留為原始表 / note 來源。
    """
    if not EXPORT_ALL_FACTS_COVERAGE_REPORT:
        return ""

    coverage_df = build_all_facts_coverage_dataframe(all_facts_df, output_csv_registry)
    if coverage_df.empty:
        return ""

    filename = make_safe_csv_filename(
        f"{stock_code}_{period}__all_table_facts_coverage_report",
        max_bytes=MAX_FILENAME_BYTES,
    )
    save_path = Path(output_dir) / filename
    coverage_df.to_csv(save_path, index=False, encoding="utf-8-sig")

    total_sources = len(coverage_df)
    with_numeric = int(coverage_df["has_numeric_facts"].astype(bool).sum())
    without_numeric = total_sources - with_numeric
    print(
        f"  [Coverage] 已輸出 coverage report：{filename}；"
        f"all_table_facts 採 fact-only 模式，{with_numeric}/{total_sources} 個來源 CSV 有 numeric facts，"
        f"其餘 {without_numeric} 個保留為原始 CSV 供 Parent-Child RAG 使用"
    )

    return str(save_path)


def report_all_output_csv_coverage(all_facts_df, output_csv_registry):
    """列印 fact-only all_table_facts 的來源概況。"""
    coverage_df = build_all_facts_coverage_dataframe(all_facts_df, output_csv_registry)
    if coverage_df.empty:
        print("  [Warning][Fact] 沒有可檢查的來源 CSV registry")
        return

    total_sources = len(coverage_df)
    with_numeric = int(coverage_df["has_numeric_facts"].astype(bool).sum())
    without_numeric = total_sources - with_numeric
    print(
        f"  [Check][Fact] all_table_facts 為 fact-only：來源 CSV 共 {total_sources} 個，"
        f"其中 {with_numeric} 個產生 numeric facts，{without_numeric} 個只保留原始 CSV / note source"
    )


# ============================================================
# 主解析流程
# ============================================================
def get_output_table_name(df, html_table):
    """
    取得輸出表格名稱。

    修正點：
    - 只有在原始 HTML 真的抓到 table_title 時，才用 HTML 標題命名。
    - 如果 table_title 是空字串，不可讓 normalize_table_title_for_filename()
      自動回傳 other_table，否則會吃掉 identify_table_name(df) 的 fallback。
    """
    if USE_HTML_TABLE_TITLE_FOR_FILENAME:
        table_title = extract_table_title_from_html_table(html_table)
        table_title = clean_note_text(table_title).replace("\n", " ").strip()

        if table_title:
            table_title_name = normalize_table_title_for_filename(table_title)
            if table_title_name:
                return table_title_name

    return identify_table_name(df)


def update_main_table_check(expected_main_tables, table_name):
    """記錄四大主表是否有成功輸出。"""
    table_name = normalize_table_cell(table_name)

    aliases = {
        "資產負債表": ["資產負債表", "balance_sheet"],
        "綜合損益表": ["綜合損益表", "損益表", "income_statement"],
        "權益變動表": ["權益變動表", "equity_movement"],
        "現金流量表": ["現金流量表", "cash_flow"],
    }

    for canonical_name, keywords in aliases.items():
        if any(keyword in table_name for keyword in keywords):
            expected_main_tables[canonical_name] = True


def save_global_all_facts(results, output_root=OUTPUT_FOLDER):
    """
    將所有 HTML 產生的 <stock>_<period>__all_table_facts.csv
    合併成全域總表。
    """
    if not EXPORT_GLOBAL_ALL_FACTS_CSV:
        return None

    fact_paths = []
    for result in results:
        if not result or result.get("status") != "success":
            continue
        path = result.get("combined_facts_path")
        if path and Path(path).exists():
            fact_paths.append(Path(path))

    if not fact_paths:
        print("[Global Fact] 沒有可合併的 all_table_facts CSV")
        return None

    frames = []
    for path in fact_paths:
        try:
            df = pd.read_csv(path, encoding="utf-8-sig")
            if not df.empty:
                df["source_all_facts_csv"] = str(path)
                frames.append(df)
        except Exception as e:
            print(f"[Global Fact][Warning] 讀取失敗：{path}；原因：{e}")

    if not frames:
        print("[Global Fact] all_table_facts CSV 皆為空，未輸出全域總表")
        return None

    global_df = pd.concat(frames, ignore_index=True)
    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    global_path = output_root / GLOBAL_ALL_FACTS_FILENAME
    global_df.to_csv(global_path, index=False, encoding="utf-8-sig")

    print(f"[Global Fact] 已輸出全域 fact-only facts 總表：{global_path}，共 {len(global_df)} 筆")

    if EXPORT_NUMERIC_FACTS_ALIAS_CSV:
        global_numeric_path = output_root / GLOBAL_NUMERIC_FACTS_FILENAME
        global_df.to_csv(global_numeric_path, index=False, encoding="utf-8-sig")
        print(f"[Global Fact] 已另存全域 numeric facts alias：{global_numeric_path}")

    if EXPORT_OPTIMIZED_FACTS_CSV:
        global_optimized_path = output_root / GLOBAL_OPTIMIZED_FACTS_FILENAME
        optimized_df, optimized_path = save_optimized_facts_csv(global_df, global_optimized_path)
        if optimized_path:
            print(f"[Global Fact] 已輸出優化全域 facts：{optimized_path}，共 {len(optimized_df)} 筆")

    return str(global_path)


def parse_html_report(html_file_path, output_root=OUTPUT_FOLDER):
    """解析單一 HTML 財報，並輸出 CSV。"""
    html_file_path = Path(html_file_path)
    print(f"正在處理: {html_file_path}")

    parent_folder_name = html_file_path.parent.name
    period = extract_period_from_filename(str(html_file_path))

    html_content = decode_html_file(str(html_file_path))

    stock_code, company_name, company_folder_name = extract_company_info_from_html(
        html_content=html_content,
        fallback_folder_name=parent_folder_name,
    )

    output_dir = Path(output_root) / company_folder_name / period
    output_dir.mkdir(parents=True, exist_ok=True)

    # 現在只輸出 note 總表；先清除舊版留下的 note_XXX.csv，避免資料夾看起來還有分檔
    if not SAVE_EACH_NOTE_BLOCK_CSV:
        deleted_note_blocks = cleanup_old_note_block_csv(output_dir, stock_code, period)
        if deleted_note_blocks:
            print(f"  [Clean] 已清除舊的 note block CSV：{deleted_note_blocks} 個")

    try:
        table_pairs = parse_tables_with_html_nodes(html_content)
    except Exception as e:
        print(f"  [Error] 無法解析表格: {e}")
        return {
            "file": str(html_file_path),
            "status": "failed",
            "reason": str(e),
            "saved_tables": 0,
        }

    if not table_pairs:
        print("  [Error] HTML 中沒有解析到任何 table")
        return {
            "file": str(html_file_path),
            "status": "failed",
            "reason": "no table parsed",
            "saved_tables": 0,
        }

    saved_counts = {}
    saved_total = 0
    all_fact_frames = []
    output_csv_registry = []
    combined_facts_path = ""
    optimized_combined_facts_path = ""

    expected_main_tables = {
        "資產負債表": False,
        "綜合損益表": False,
        "權益變動表": False,
        "現金流量表": False,
    }

    for table_idx, df, html_table, raw_title in table_pairs:
        if DEBUG_TABLE_SCAN:
            print("=" * 100)
            print(f"[Before Clean] table_idx={table_idx}")
            print(f"[Before Clean] raw_title={raw_title}")
            print(f"[Before Clean] shape={df.shape}")

        if df.shape[0] < 3 or df.shape[1] < 2:
            if DEBUG_TABLE_SCAN:
                print("[Skip] 原始表格列數或欄數太小")
            continue

        df = clean_table(df)

        if DEBUG_TABLE_SCAN:
            print(f"[After Clean] shape={df.shape}")
            try:
                print(df.head(8).to_string())
            except Exception:
                pass

        if df.shape[0] < 1 or df.shape[1] < 1:
            if DEBUG_TABLE_SCAN:
                print("[Skip] clean_table 後變成空表")
            continue

        table_name = get_output_table_name(df, html_table)
        update_main_table_check(expected_main_tables, table_name)

        if DEBUG_TABLE_SCAN:
            print(f"[Save] table_name={table_name}")
            print("=" * 100)

        # 把 <pre class="note"> / <ix:nonumeric> 說明文字附加回對應表格
        if APPEND_XBRL_NOTES_TO_TABLE and html_table is not None:
            note_texts = extract_note_texts_near_table(html_table)
            df = append_note_rows_to_df(df, note_texts)

        saved_counts[table_name] = saved_counts.get(table_name, 0) + 1
        count = saved_counts[table_name]
        suffix = f"_{count}" if count > 1 else ""

        filename = make_safe_csv_filename(
            f"{stock_code}_{period}_{table_name}{suffix}",
            max_bytes=MAX_FILENAME_BYTES,
        )
        save_path = output_dir / filename
        df.to_csv(save_path, index=False, encoding="utf-8-sig")
        register_output_csv(
            output_csv_registry=output_csv_registry,
            df=df,
            table_name=f"{table_name}{suffix}",
            filename=filename,
            source_kind="html_table",
        )

        facts_df = export_table_facts_csv(
            df=df,
            output_dir=output_dir,
            stock_code=stock_code,
            company_name=company_name,
            period=period,
            table_name=f"{table_name}{suffix}",
            source_csv_filename=filename,
        )
        if facts_df is not None and not facts_df.empty:
            all_fact_frames.append(facts_df)
        else:
            # 主表有輸出成寬表，但沒有轉出 facts 時，要明確警告；
            # 舊版資產負債表缺在 all_table_facts，就是這裡沒有 rows。
            if any(k in normalize_table_cell(table_name) for k in ["資產負債表", "綜合損益表", "權益變動表", "現金流量表"]):
                print(f"  [Warning][Fact] {table_name}{suffix} 已輸出寬表 CSV，但沒有產生 long-format facts；請開啟 DEBUG_TABLE_SCAN 檢查欄名與前幾列。")

        saved_total += 1

    # all_table_facts 會在 note CSV 也輸出並登錄後統一產生，確保資料夾內本次輸出的所有原始表都可進總表。

    # 另存 XBRL/iXBRL note 原始文字
    if SAVE_XBRL_NOTES_CSV:
        note_records = extract_all_xbrl_note_records(html_content)

        if note_records:
            notes_filename = make_safe_csv_filename(
                f"{stock_code}_{period}_xbrl_notes",
                max_bytes=MAX_FILENAME_BYTES,
            )
            notes_save_path = output_dir / notes_filename
            notes_df = pd.DataFrame(note_records)
            notes_df.to_csv(notes_save_path, index=False, encoding="utf-8-sig")
            register_output_csv(
                output_csv_registry=output_csv_registry,
                df=notes_df,
                table_name="xbrl_notes",
                filename=notes_filename,
                source_kind="xbrl_notes",
            )
            print(f"  [Note] 已輸出 XBRL 說明文字：{notes_filename}")

    # 另存保留行列結構的 note CSV
    if SAVE_STRUCTURED_NOTE_CSV:
        structured_note_records = extract_structured_note_records(html_content)

        if structured_note_records:
            structured_filename = make_safe_csv_filename(
                f"{stock_code}_{period}_xbrl_notes_structured",
                max_bytes=MAX_FILENAME_BYTES,
            )
            structured_save_path = output_dir / structured_filename
            if NOTE_STRUCTURED_SINGLE_TEXT_ONLY:
                structured_output_records = build_single_text_structured_note_records(structured_note_records)
            else:
                structured_output_records = structured_note_records

            structured_df = pd.DataFrame(structured_output_records)
            structured_df.to_csv(
                structured_save_path,
                index=False,
                encoding="utf-8-sig",
            )
            register_output_csv(
                output_csv_registry=output_csv_registry,
                df=structured_df,
                table_name="xbrl_notes_structured",
                filename=structured_filename,
                source_kind="xbrl_notes_structured",
            )

            block_count = 0
            if SAVE_EACH_NOTE_BLOCK_CSV:
                block_count = save_each_structured_note_block(
                    note_records=structured_note_records,
                    output_dir=output_dir,
                    stock_code=stock_code,
                    period=period,
                )
                print(f"  [Note] 已輸出結構化說明：{structured_filename}，另存 {block_count} 個 note block CSV")
            else:
                print(f"  [Note] 已輸出單欄結構化說明總表：{structured_filename}；未輸出個別 note_XXX.csv")

    # v5：輸出總表前，先掃描輸出資料夾內所有既有原始 CSV，建立完整 source registry。
    # 注意：掃描結果只進 source_table_index / coverage_report，不會把 raw rows 塞進 all_table_facts。
    if SCAN_EXISTING_FOLDER_CSVS_INTO_ALL_FACTS:
        output_csv_registry = append_existing_folder_csvs_to_registry(
            output_csv_registry=output_csv_registry,
            output_dir=output_dir,
            stock_code=stock_code,
            period=period,
        )

    # v5：all_table_facts 採 fact-only 模式，只合併 numeric_fact。
    # 原始表格全文維持分散 CSV，後續由 RAG 建庫流程讀取 source_table_index 進行 Parent-Child ingestion。
    all_facts_df = pd.DataFrame()
    if EXPORT_COMBINED_FACTS_CSV and all_fact_frames:
        all_facts_df = pd.concat(all_fact_frames, ignore_index=True)
        if "record_type" in all_facts_df.columns:
            all_facts_df = all_facts_df[all_facts_df["record_type"].astype(str).eq("numeric_fact")].reset_index(drop=True)

    if EXPORT_COMBINED_FACTS_CSV and not all_facts_df.empty:
        all_facts_filename = make_safe_csv_filename(
            f"{stock_code}_{period}__all_table_facts",
            max_bytes=MAX_FILENAME_BYTES,
        )
        all_facts_path = output_dir / all_facts_filename
        all_facts_df.to_csv(all_facts_path, index=False, encoding="utf-8-sig")
        combined_facts_path = str(all_facts_path)
        print(f"  [Fact] 已輸出 fact-only all_table_facts：{all_facts_filename}，共 {len(all_facts_df)} 筆 numeric facts")

        if EXPORT_NUMERIC_FACTS_ALIAS_CSV:
            numeric_facts_filename = make_safe_csv_filename(
                f"{stock_code}_{period}{NUMERIC_FACTS_SUFFIX}",
                max_bytes=MAX_FILENAME_BYTES,
            )
            numeric_facts_path = output_dir / numeric_facts_filename
            all_facts_df.to_csv(numeric_facts_path, index=False, encoding="utf-8-sig")
            print(f"  [Fact] 已另存 numeric facts alias：{numeric_facts_filename}")

        # 檢查四大主表是否有 numeric facts。沒有 numeric facts 不代表原始表遺失；
        # 例如權益變動表可能以複雜版面保留在原始 CSV 中，供 DealTable / Parent-Child RAG 使用。
        fact_table_names = all_facts_df.get("table_name", pd.Series(dtype=str)).astype(str)
        missing_numeric_main_tables = []
        fact_aliases = {
            "資產負債表": ["資產負債表", "balance_sheet"],
            "綜合損益表": ["綜合損益表", "損益表", "income_statement"],
            "權益變動表": ["權益變動表", "equity_movement"],
            "現金流量表": ["現金流量表", "cash_flow"],
        }
        for canonical_name, aliases in fact_aliases.items():
            if not any(fact_table_names.str.contains(alias, regex=False, na=False).any() for alias in aliases):
                missing_numeric_main_tables.append(canonical_name)
        if missing_numeric_main_tables:
            print(f"  [Info][Fact] 以下主表沒有 numeric facts，但若寬表 CSV 有輸出，仍會保留為原始表來源：{missing_numeric_main_tables}")
        else:
            print("  [Check][Fact] 四大主表都有 numeric facts")

        if EXPORT_OPTIMIZED_FACTS_CSV:
            optimized_facts_filename = make_safe_csv_filename(
                f"{stock_code}_{period}{OPTIMIZED_FACTS_SUFFIX}",
                max_bytes=MAX_FILENAME_BYTES,
            )
            optimized_facts_path = output_dir / optimized_facts_filename
            optimized_facts_df, optimized_path = save_optimized_facts_csv(all_facts_df, optimized_facts_path)
            if optimized_path:
                optimized_combined_facts_path = optimized_path
                print(f"  [Fact] 已輸出優化 fact-only facts：{optimized_facts_filename}，共 {len(optimized_facts_df)} 筆")
    else:
        print("  [Warning][Fact] 沒有任何 numeric facts 可輸出 all_table_facts；原始 CSV 仍會保留並登錄到 source index")

    # v5：source_table_index / coverage_report 不依賴 all_table_facts 是否覆蓋所有來源表。
    # 它負責告訴 RAG 建庫流程：哪些表該讀原始 CSV，哪些表已有 numeric facts。
    report_all_output_csv_coverage(all_facts_df, output_csv_registry)
    save_source_table_index(
        output_dir=output_dir,
        stock_code=stock_code,
        period=period,
        all_facts_df=all_facts_df,
        output_csv_registry=output_csv_registry,
    )
    save_all_facts_coverage_report(
        output_dir=output_dir,
        stock_code=stock_code,
        period=period,
        all_facts_df=all_facts_df,
        output_csv_registry=output_csv_registry,
    )

    missing_tables = [name for name, found in expected_main_tables.items() if not found]
    if missing_tables:
        print(f"  [Warning] 以下主表沒有輸出：{missing_tables}")
    else:
        print("  [Check] 四大主表都有輸出")

    print(f"  [完成] {company_folder_name}/{period}，輸出 {saved_total} 個表格 CSV")

    return {
        "file": str(html_file_path),
        "status": "success",
        "stock_code": stock_code,
        "company_name": company_name,
        "period": period,
        "saved_tables": saved_total,
        "combined_facts_path": combined_facts_path,
        "optimized_combined_facts_path": optimized_combined_facts_path,
    }

def find_html_files(input_root=INPUT_FOLDER):
    """
    掃描上一支爬蟲程式輸出的 HTML。

    預期資料夾：
    reports_html_copy/
    ├── 2330_台灣積體電路製造/
    │   ├── 2330_113Q1_財報.html
    │   └── 2330_113Q2_財報.html
    └── 2303_聯華電子/
        └── 2303_114Q2_財報.html

    若 TEST_ONE_COMPANY = True：
    只處理 TEST_STOCK_CODE 開頭的資料夾與檔案。
    """
    input_root = Path(input_root)

    if not input_root.exists():
        print(f"[Error] 找不到輸入資料夾：{input_root}")
        return []

    if TEST_ONE_COMPANY:
        candidate_files = []

        for company_dir in input_root.glob(f"{TEST_STOCK_CODE}_*"):
            if company_dir.is_dir():
                candidate_files.extend(company_dir.glob("*.html"))

        code_only_dir = input_root / TEST_STOCK_CODE
        if code_only_dir.exists() and code_only_dir.is_dir():
            candidate_files.extend(code_only_dir.glob("*.html"))

        html_files = sorted(set(candidate_files))
    else:
        html_files = sorted(input_root.rglob("*.html"))

    # 可選：只跑指定季度
    if TEST_PERIODS:
        period_set = set(TEST_PERIODS)
        filtered_files = []

        for html_file in html_files:
            period = extract_period_from_filename(str(html_file))
            if period in period_set:
                filtered_files.append(html_file)

        html_files = filtered_files

    return html_files


def main():
    html_files = find_html_files(INPUT_FOLDER)

    if not html_files:
        print("找不到 HTML 檔案！")
        print(f"請確認上一支爬蟲程式是否已輸出到：./{INPUT_FOLDER}/股票資料夾/*.html")
        return

    print("開始解析財報 HTML...")
    print(f"輸入資料夾：{INPUT_FOLDER}")
    print(f"輸出資料夾：{OUTPUT_FOLDER}")

    if TEST_ONE_COMPANY:
        print(f"測試模式：只處理股票代號 {TEST_STOCK_CODE}")
        if TEST_PERIODS:
            print(f"限定季度：{TEST_PERIODS}")
        else:
            print("限定季度：全部季度")
    else:
        print("測試模式：關閉，處理全部公司")

    print(f"共找到 {len(html_files)} 個 HTML 檔案")

    results = []

    for html_file in html_files:
        result = parse_html_report(html_file_path=html_file, output_root=OUTPUT_FOLDER)
        results.append(result)

    global_facts_path = save_global_all_facts(results, output_root=OUTPUT_FOLDER)

    success_count = sum(1 for r in results if r and r.get("status") == "success")
    failed_count = sum(1 for r in results if r and r.get("status") == "failed")
    total_csv = sum(r.get("saved_tables", 0) for r in results if r)

    print("\n全部處理完成")
    print(f"成功 HTML 數：{success_count}")
    print(f"失敗 HTML 數：{failed_count}")
    print(f"輸出一般表格 CSV 總數：{total_csv}")
    if global_facts_path:
        print(f"全域 facts 總表：{global_facts_path}")



if __name__ == "__main__":
    main()
