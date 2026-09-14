import requests
from bs4 import BeautifulSoup
import os
import re
import time
import random


def load_stock_codes(file_path="companies.txt"):
    """
    從 companies.txt 讀取股票代號。
    支援一行一個股票代號，也支援空白、逗號混合。
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"找不到 {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    codes = re.findall(r"\b\d{4}\b", content)

    # 去重複但保留順序
    seen = set()
    stock_codes = []

    for code in codes:
        if code not in seen:
            stock_codes.append(code)
            seen.add(code)

    return stock_codes


def clean_filename_name(name):
    """
    移除 Windows 檔名/資料夾不允許的字元。
    """
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    name = name.strip()
    return name


def decode_html_content(content_bytes):
    """
    嘗試解碼公開資訊觀測站下載下來的 HTML。
    """
    for encoding in ["utf-8", "big5", "cp950"]:
        try:
            return content_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue

    return content_bytes.decode("utf-8", errors="ignore")


def extract_company_name_from_report_html(content_bytes, stock_code):
    """
    從財報 HTML 的 header 欄位抓公司名稱。

    目標格式通常是：
    <span class="zh">
        2330 台灣積體電路製造股份有限公司
        <br>
        2026年第1季合併財務報告
    </span>
    """
    html_text = decode_html_content(content_bytes)
    soup = BeautifulSoup(html_text, "html.parser")

    zh_span = soup.find("span", class_="zh")

    if not zh_span:
        return stock_code

    text = zh_span.get_text(separator="\n", strip=True)

    lines = [line.strip() for line in text.splitlines() if line.strip()]

    if not lines:
        return stock_code

    first_line = lines[0]

    # 例如：2330 台灣積體電路製造股份有限公司
    # 移除開頭股票代號
    company_name = re.sub(rf"^{stock_code}\s*", "", first_line).strip()

    if not company_name:
        company_name = stock_code

    return clean_filename_name(company_name)


def crawl_mops_finance_report(stock_code, year, season, base_folder="reports_html_copy"):
    session = requests.Session()

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Referer": "https://mopsov.twse.com.tw/mops/web/t203sb01"
    }

    search_url = "https://mopsov.twse.com.tw/mops/web/ajax_t203sb01"

    search_payload = {
        "encodeURIComponent": "1",
        "step": "1",
        "firstin": "1",
        "off": "1",
        "co_id": stock_code,
        "year": year,
        "season": ""
    }

    try:
        resp = session.post(
            search_url,
            data=search_payload,
            headers=headers,
            timeout=10
        )
        resp.raise_for_status()
        resp.encoding = "utf-8"

        soup = BeautifulSoup(resp.text, "html.parser")

        target_key = f"{year}Q{season}"
        download_link = None

        rows = soup.find_all("tr")

        for row in rows:
            row_text = row.get_text().replace(" ", "").replace("\n", "")

            if target_key in row_text:
                button = row.find("input", {"value": "下載"})

                if button and button.get("onclick"):
                    match = re.search(
                        r"window\.open\('([^']+)'",
                        button.get("onclick")
                    )

                    if match:
                        download_link = "https://mopsov.twse.com.tw" + match.group(1)
                        break

        if not download_link:
            print(f"  [跳過] {stock_code} 找不到 {target_key} 的下載按鈕")
            return

        file_resp = session.get(
            download_link,
            headers=headers,
            stream=False,
            timeout=30
        )
        file_resp.raise_for_status()

        content_type = file_resp.headers.get("Content-Type", "").lower()
        content_bytes = file_resp.content

        if "pdf" in content_type:
            ext = ".pdf"
            company_name = stock_code
        else:
            ext = ".html"
            company_name = extract_company_name_from_report_html(
                content_bytes=content_bytes,
                stock_code=stock_code
            )

        # 資料夾名稱改成從財報 header 抓到的公司名稱
        # 例如：reports_html_copy/2330_台灣積體電路製造股份有限公司
        company_dir_name = f"{stock_code}_{company_name}"
        download_folder = os.path.join(base_folder, company_dir_name)
        os.makedirs(download_folder, exist_ok=True)

        file_name = f"{stock_code}_{year}Q{season}_財報{ext}"
        file_path = os.path.join(download_folder, file_name)

        with open(file_path, "wb") as f:
            f.write(content_bytes)

        print(f"  [成功] {stock_code} {target_key} 已存檔：{file_path}")

    except Exception as e:
        print(f"  [失敗] {stock_code} {year}Q{season} 出錯：{e}")


if __name__ == "__main__":
    stock_codes = load_stock_codes("companies.txt")

    target_years = ["113", "114"]
    target_seasons = ["1", "2", "3", "4"]

    print("🚀 開始批次爬取財務報表...")
    print(f"共讀取到 {len(stock_codes)} 檔股票：")
    print(stock_codes)

    for stock_code in stock_codes:
        print(f"\n# 正在處理：{stock_code}")

        for year in target_years:
            for season in target_seasons:
                crawl_mops_finance_report(
                    stock_code=stock_code,
                    year=year,
                    season=season
                )

                time.sleep(random.uniform(3, 7))

    print("\n✅ 所有任務執行完畢！")