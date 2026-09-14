"""爬取櫃買中心半導體產業鏈 D000 各步驟台灣公司，並輸出三個 TXT：

1. tw_semiconductor_supply_chain_companies.txt
   依產業鏈分類輸出公司名稱

2. tw_semiconductor_supply_chain_stock_codes.txt
   依產業鏈分類輸出股票代號 + 公司名稱

3. tw_semiconductor_stock_codes_only.txt
   去重後只輸出股票代號 + 公司名稱

預設只輸出台灣公司：
- 本國上市公司
- 本國上櫃公司
- 本國興櫃公司
- 本國公發公司
- 創櫃公司

若要包含外國上市、外國上櫃、知名外國企業：
python tpex_d000_scraper_with_codes.py --include-foreign
"""

from __future__ import annotations

import argparse
import re
from collections import OrderedDict, defaultdict
from html import unescape
from pathlib import Path
from typing import Any, Dict, List, Tuple

import requests


BASE_URL = "https://ic.tpex.org.tw/introduce.php"
FIRST_STAGE = "IP設計/IC設計代工服務"


TAIWAN_CATEGORIES = {
    "本國上市公司",
    "本國上櫃公司",
    "本國興櫃公司",
    "本國公發公司",
    "創櫃公司",
}


ALL_CATEGORIES = TAIWAN_CATEGORIES | {
    "外國上市公司",
    "外國上櫃公司",
    "外國興櫃公司",
    "外國公發公司",
    "知名外國企業",
}


STAGES: List[Dict[str, Any]] = [
    {
        "level": "上游",
        "stage": "IP設計/IC設計代工服務",
        "substeps": [],
    },
    {
        "level": "上游",
        "stage": "IC設計",
        "substeps": [
            "LED驅動IC",
            "光通訊IC",
            "光源管理IC",
            "消費性IC",
            "記憶體IC",
            "記憶體控制IC",
            "微控制器IC",
            "電源管理IC",
            "磁碟儲存控制器IC",
            "網路通訊IC",
            "輸出入介面IC",
            "平面顯示器控制IC",
            "平面顯示器驅動IC",
            "光儲存控制IC",
            "影像感測IC",
        ],
    },
    {
        "level": "中游",
        "stage": "光罩",
        "substeps": [],
    },
    {
        "level": "中游",
        "stage": "IC/晶圓製造",
        "substeps": [
            "晶圓製造",
            "DRAM製造",
            "其他IC/二極體製造",
        ],
    },
    {
        "level": "中游",
        "stage": "生產製程及檢測設備",
        "substeps": [],
    },
    {
        "level": "中游",
        "stage": "化學品",
        "substeps": [],
    },
    {
        "level": "下游",
        "stage": "生產製程及檢測設備",
        "substeps": [],
    },
    {
        "level": "下游",
        "stage": "基板",
        "substeps": [],
    },
    {
        "level": "下游",
        "stage": "導線架",
        "substeps": [],
    },
    {
        "level": "下游",
        "stage": "IC封裝測試",
        "substeps": [],
    },
    {
        "level": "下游",
        "stage": "IC模組",
        "substeps": [],
    },
    {
        "level": "下游",
        "stage": "IC通路",
        "substeps": [],
    },
]


SupplyChainData = OrderedDict[
    str,
    OrderedDict[
        str,
        OrderedDict[
            str,
            List[Tuple[str, str]],
        ],
    ],
]


def fetch_html(ic_code: str, timeout: int = 30) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    }

    try:
        response = requests.get(
            BASE_URL,
            params={"ic": ic_code},
            headers=headers,
            timeout=timeout,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"無法連到櫃買中心站台：{BASE_URL}，錯誤：{exc}") from exc

    response.encoding = response.apparent_encoding
    return response.text


def clean_text(text: str) -> str:
    text = unescape(text)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def html_to_marked_text(html: str) -> str:
    """把 company_basic.php?stk_code=xxxx 的 a 標籤轉成 [[COMPANY:股票代號:公司名]]。"""

    html = re.sub(r"<!--.*?-->", " ", html, flags=re.S)
    html = re.sub(
        r"<(script|style)[^>]*>.*?</\1>",
        " ",
        html,
        flags=re.I | re.S,
    )

    def replace_anchor(match: re.Match[str]) -> str:
        attrs = match.group(1)
        body = match.group(2)

        name = clean_text(body)
        if not name:
            return " "

        code_match = re.search(
            r"company_basic\.php\?stk_code=([^&\"'#\s>]+)",
            attrs,
            flags=re.I,
        )

        if code_match:
            stock_code = clean_text(code_match.group(1))
            return f" [[COMPANY:{stock_code}:{name}]] "

        return f" {name} "

    html = re.sub(
        r"<a\b([^>]*)>(.*?)</a>",
        replace_anchor,
        html,
        flags=re.I | re.S,
    )

    html = re.sub(r"<br\s*/?>", " ", html, flags=re.I)
    html = re.sub(
        r"</?(div|span|p|li|ul|ol|td|tr|table|h\d|section|article)[^>]*>",
        " ",
        html,
        flags=re.I,
    )
    html = re.sub(r"<[^>]+>", " ", html)

    text = unescape(html).replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)

    # 統一「IP設計 / IC設計代工服務」與「IP設計/IC設計代工服務」。
    text = re.sub(r"\s*/\s*", "/", text)

    return text.strip()


def get_detail_region(marked_text: str) -> str:
    """取公司資料區，避免上方圖示文字造成重複解析。"""

    category_pattern = re.compile(
        r"(本國上市公司|本國上櫃公司|本國興櫃公司|本國公發公司|"
        r"外國上市公司|外國上櫃公司|外國興櫃公司|外國公發公司|"
        r"創櫃公司|知名外國企業)\s*\(\d+家\)",
        flags=re.I,
    )

    positions = [m.start() for m in re.finditer(re.escape(FIRST_STAGE), marked_text)]

    if not positions:
        raise RuntimeError(f"找不到公司資料起點：{FIRST_STAGE}")

    start = None

    for pos in reversed(positions):
        window = marked_text[pos : pos + 3000]
        if category_pattern.search(window):
            start = pos
            break

    if start is None:
        start = positions[-1]

    end_candidates = [
        marked_text.find("半導體產業鏈半導體產業鏈上游", start),
        marked_text.find("半導體產業鏈 上游", start),
        marked_text.find("一、上游", start),
        marked_text.find("產業介紹", start),
    ]
    end_candidates = [x for x in end_candidates if x != -1]

    end = min(end_candidates) if end_candidates else len(marked_text)

    return marked_text[start:end].strip()


def make_stage_key(stage: Dict[str, Any]) -> str:
    return f"{stage['level']}::{stage['stage']}"


def build_stage_indexes() -> Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, str], List[str]]:
    stage_by_title: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    substep_parent: Dict[str, str] = {}

    for stage in STAGES:
        stage_by_title[stage["stage"]].append(stage)
        stage_key = make_stage_key(stage)

        for substep in stage["substeps"]:
            substep_parent[substep] = stage_key

    all_titles = set(stage_by_title.keys()) | set(substep_parent.keys())

    # 長標題優先，避免「IP設計/IC設計代工服務」被誤判成「IC設計」。
    sorted_titles = sorted(all_titles, key=len, reverse=True)

    return stage_by_title, substep_parent, sorted_titles


def build_token_regex(titles: List[str]) -> re.Pattern[str]:
    company_pat = r"\[\[COMPANY:(?P<stock_code>[^:\]]+):(?P<company>[^\]]+)\]\]"

    category_pat = (
        r"(?P<category>"
        r"(?:本國|外國)(?:上市|上櫃|興櫃|公發)公司"
        r"|創櫃公司"
        r"|知名外國企業"
        r")\s*\(\d+家\)"
    )

    title_pat = r"(?P<title>" + "|".join(re.escape(t) for t in titles) + r")"

    return re.compile(
        f"{company_pat}|{category_pat}|{title_pat}",
        flags=re.I,
    )


def parse_supply_chain(
    html: str,
    include_foreign: bool = False,
) -> SupplyChainData:
    stage_by_title, _substep_parent, all_titles = build_stage_indexes()
    token_re = build_token_regex(all_titles)

    marked_text = html_to_marked_text(html)
    detail = get_detail_region(marked_text)

    allowed_categories = ALL_CATEGORIES if include_foreign else TAIWAN_CATEGORIES

    stage_seen_count: Dict[str, int] = defaultdict(int)
    stage_by_key = {make_stage_key(stage): stage for stage in STAGES}

    data: SupplyChainData = OrderedDict()
    seen_company: Dict[Tuple[str, str, str, str, str], bool] = {}

    current_stage_key: str | None = None
    current_substep = ""
    current_category: str | None = None

    for match in token_re.finditer(detail):
        title = match.group("title")
        category = match.group("category")
        stock_code = match.group("stock_code")
        company = match.group("company")

        if title:
            if title in stage_by_title:
                candidates = stage_by_title[title]
                idx = stage_seen_count[title]

                # 例如「生產製程及檢測設備」在中游、下游各出現一次。
                # 依照頁面出現順序判斷：第一次為中游，第二次為下游。
                if idx >= len(candidates):
                    idx = len(candidates) - 1

                stage = candidates[idx]
                stage_seen_count[title] += 1

                current_stage_key = make_stage_key(stage)
                current_substep = ""
                current_category = None

                if current_stage_key not in data:
                    data[current_stage_key] = OrderedDict()

                continue

            if current_stage_key:
                current_stage = stage_by_key[current_stage_key]
                if title in current_stage["substeps"]:
                    current_substep = title
                    current_category = None
                    data[current_stage_key].setdefault(current_substep, OrderedDict())
                    continue

        if category:
            current_category = clean_text(category)
            continue

        if company:
            company = clean_text(company)
            stock_code = clean_text(stock_code or "NA")

            if not current_stage_key or not current_category:
                continue

            if current_category not in allowed_categories:
                continue

            subtitle = current_substep or "未分子標題"

            data[current_stage_key].setdefault(subtitle, OrderedDict())
            data[current_stage_key][subtitle].setdefault(current_category, [])

            dedup_key = (
                current_stage_key,
                subtitle,
                current_category,
                stock_code,
                company,
            )

            if dedup_key not in seen_company:
                data[current_stage_key][subtitle][current_category].append(
                    (stock_code, company)
                )
                seen_company[dedup_key] = True

    ordered: SupplyChainData = OrderedDict()

    for stage in STAGES:
        key = make_stage_key(stage)
        if key in data:
            ordered[key] = data[key]

    return ordered


def save_companies_to_txt(
    data: SupplyChainData,
    output_path: Path,
) -> None:
    lines: List[str] = []

    for stage_key, subtitle_map in data.items():
        level, stage = stage_key.split("::", 1)
        lines.append(f"[{level}] {stage}")

        for subtitle, category_map in subtitle_map.items():
            if subtitle != "未分子標題":
                lines.append(f"  <子標題> {subtitle}")

            for category, companies in category_map.items():
                lines.append(f"  ({category})")

                for _stock_code, company in companies:
                    lines.append(f"  - {company}")

        lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def save_stock_codes_to_txt(
    data: SupplyChainData,
    output_path: Path,
) -> None:
    """輸出保留產業鏈分類的股票代號 TXT。"""

    lines: List[str] = []

    for stage_key, subtitle_map in data.items():
        level, stage = stage_key.split("::", 1)
        lines.append(f"[{level}] {stage}")

        for subtitle, category_map in subtitle_map.items():
            if subtitle != "未分子標題":
                lines.append(f"  <子標題> {subtitle}")

            for category, companies in category_map.items():
                lines.append(f"  ({category})")

                for stock_code, company in companies:
                    lines.append(f"  - {stock_code} {company}")

        lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def save_stock_codes_only_to_txt(
    data: SupplyChainData,
    output_path: Path,
) -> None:
    """輸出去重後的純股票代號 TXT。"""

    rows: List[Tuple[str, str]] = []
    seen = set()

    for subtitle_map in data.values():
        for category_map in subtitle_map.values():
            for companies in category_map.values():
                for stock_code, company in companies:
                    if not stock_code or stock_code == "NA":
                        continue

                    key = (stock_code, company)
                    if key not in seen:
                        rows.append((stock_code, company))
                        seen.add(key)

    rows.sort(key=lambda x: x[0])

    lines = [f"{stock_code} {company}" for stock_code, company in rows]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def count_companies(data: SupplyChainData) -> int:
    total = 0

    for subtitle_map in data.values():
        for category_map in subtitle_map.values():
            for companies in category_map.values():
                total += len(companies)

    return total


def main() -> None:
    parser = argparse.ArgumentParser(
        description="抓取櫃買中心半導體產業鏈 D000 公司清單與股票代號"
    )

    parser.add_argument(
        "--ic",
        default="D000",
        help="產業代碼，半導體請使用 D000",
    )

    parser.add_argument(
        "--output",
        default="tw_semiconductor_supply_chain_companies.txt",
        help="公司清單 TXT 輸出檔名",
    )

    parser.add_argument(
        "--code-output",
        default="tw_semiconductor_supply_chain_stock_codes.txt",
        help="分類股票代號 TXT 輸出檔名",
    )

    parser.add_argument(
        "--codes-only-output",
        default="tw_semiconductor_stock_codes_only.txt",
        help="純股票代號 TXT 輸出檔名",
    )

    parser.add_argument(
        "--include-foreign",
        action="store_true",
        help="包含外國上市公司、外國上櫃公司、知名外國企業",
    )

    args = parser.parse_args()

    if args.ic != "D000":
        raise ValueError("目前此腳本只針對半導體產業鏈 D000 設計，請使用 --ic D000")

    html = fetch_html(args.ic)
    data = parse_supply_chain(html, include_foreign=args.include_foreign)

    if not data:
        raise RuntimeError("沒有解析到任何公司資料，請檢查網頁結構是否已變更。")

    company_output_path = Path(args.output)
    code_output_path = Path(args.code_output)
    codes_only_output_path = Path(args.codes_only_output)

    # save_companies_to_txt(data, company_output_path)
    save_stock_codes_to_txt(data, code_output_path)
    save_stock_codes_only_to_txt(data, codes_only_output_path)

    print(f"完成：共 {len(data)} 個步驟，{count_companies(data)} 筆公司資料")
    # print(f"公司清單已輸出：{company_output_path}")
    print(f"分類股票代號已輸出：{code_output_path}")
    print(f"純股票代號清單已輸出：{codes_only_output_path}")


if __name__ == "__main__":
    main()