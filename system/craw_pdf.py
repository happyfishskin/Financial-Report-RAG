# 爬下 pdf 資料

import os
import re
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException


# ==========================================
# 1. 基本設定與下載監控
# ==========================================
def get_company_list(filepath):
    if not os.path.exists(filepath):
        print(f"❌ 錯誤：找不到 {filepath} 檔案！")
        return []

    with open(filepath, "r", encoding="utf-8") as f:
        return [line.strip() for line in f.readlines() if line.strip()]


DOWNLOAD_DIR = os.path.join(os.getcwd(), "financial_reports")

if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)


def wait_for_download_to_finish(download_dir, timeout=120):
    print("   ⏳ 正在監控資料夾等待檔案下載完成...")

    seconds = 0

    while seconds < timeout:
        time.sleep(1)

        files = os.listdir(download_dir)
        crdownloads = [f for f in files if f.endswith(".crdownload")]

        if not crdownloads:
            return True

        seconds += 1

    print("   ⚠️ 等待下載超時！")
    return False


def cleanup_extra_windows(driver, main_window=None):
    """
    關閉多餘視窗，盡量回到主視窗。
    """
    try:
        current_handles = driver.window_handles

        if len(current_handles) == 0:
            return

        if main_window and main_window in current_handles:
            safe_main = main_window
        else:
            safe_main = current_handles[0]

        for handle in current_handles:
            if handle != safe_main:
                try:
                    driver.switch_to.window(handle)
                    driver.close()
                except Exception:
                    pass

        driver.switch_to.window(safe_main)

    except Exception:
        pass


# ==========================================
# 2. 爬蟲主邏輯
# ==========================================
def download_mops_pdf(driver, stock_code, year):
    url = "https://mopsov.twse.com.tw/mops/web/t57sb01_q1"
    main_window = None
    any_item_failed = False

    try:
        main_window = driver.window_handles[0]
        driver.switch_to.window(main_window)
        driver.get(url)

        wait = WebDriverWait(driver, 15)

        # 注入 JS 防禦
        driver.execute_script("""
            window.open = function(url) {
                window.location.href = url;
                return null;
            };

            setInterval(function() {
                let forms = document.getElementsByTagName('form');
                for (let i = 0; i < forms.length; i++) {
                    if (forms[i].target !== '_self') {
                        forms[i].target = '_self';
                    }
                }
            }, 500);
        """)

        # 寫入查詢條件
        input_box = wait.until(
            EC.presence_of_element_located((By.ID, "co_id"))
        )
        driver.execute_script("arguments[0].value = arguments[1];", input_box, stock_code)

        year_box = wait.until(
            EC.presence_of_element_located((By.ID, "year"))
        )
        driver.execute_script("arguments[0].value = arguments[1];", year_box, str(year))

        search_btn = driver.find_element(By.CSS_SELECTOR, "#search_bar1 input[type='button']")
        driver.execute_script("arguments[0].click();", search_btn)

        # 處理防快顯
        try:
            pop_btn = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located(
                    (
                        By.XPATH,
                        "//*[contains(@value, '請點選這裡') or contains(text(), '請點選這裡')]"
                    )
                )
            )
            driver.execute_script("arguments[0].click();", pop_btn)

        except TimeoutException:
            pass

        print("⏳ 等待跨網域跳轉並載入財報清單 第二層...")

        pdf_xpath = "//a[contains(text(), 'AI1.pdf') or contains(@href, 'AI1.pdf')]"

        try:
            wait.until(EC.presence_of_element_located((By.XPATH, pdf_xpath)))
        except TimeoutException:
            print(f"⚠️ 找不到財報檔案連結：{stock_code} - {year}年度")
            return True

        # ==========================================
        # 智慧命名模組 1：自動抓取公司名稱
        # ==========================================
        try:
            page_text = driver.find_element(By.TAG_NAME, "body").text

            match = re.search(r"公司名稱\s*[:：]\s*([^\n]+)", page_text)

            if match:
                raw_name = match.group(1).strip()
                company_name = re.sub(r'[\\/*?:"<>|]', "", raw_name)
            else:
                company_name = str(stock_code)

        except Exception:
            company_name = str(stock_code)

        total_pdfs = len(driver.find_elements(By.XPATH, pdf_xpath))

        if total_pdfs > 0:
            print(f"👉 成功找到 {total_pdfs} 個中文合併財報！準備依序處理...")

            for i in range(total_pdfs):
                current_links = driver.find_elements(By.XPATH, pdf_xpath)

                if i >= len(current_links):
                    continue

                original_file_name = current_links[i].text.strip()

                # ==========================================
                # 智慧命名模組 2：自動判斷季別 Q1~Q4
                # ==========================================
                if "01_" in original_file_name:
                    quarter = "Q1"
                elif "02_" in original_file_name:
                    quarter = "Q2"
                elif "03_" in original_file_name:
                    quarter = "Q3"
                elif "04_" in original_file_name:
                    quarter = "Q4"
                else:
                    quarter = "QX"

                base_target_name = f"{stock_code}_{company_name}_{year}年_{quarter}"
                target_pdf_path = os.path.join(DOWNLOAD_DIR, base_target_name + ".pdf")
                target_zip_path = os.path.join(DOWNLOAD_DIR, base_target_name + ".zip")

                print(f"\n👉 處理中 ({i + 1}/{total_pdfs}): 目標檔案 [{base_target_name}] ...")

                # ==========================================
                # 高速跳過模組：檔案存在則直接略過
                # ==========================================
                if os.path.exists(target_pdf_path) or os.path.exists(target_zip_path):
                    print("   ⏩ 檔案已存在，為節省時間自動跳過下載！")
                    continue

                # 進入實體下載流程
                driver.execute_script("""
                    let forms = document.getElementsByTagName('form');
                    for (let j = 0; j < forms.length; j++) {
                        forms[j].target = '_blank';
                    }
                """)

                old_handles = driver.window_handles
                driver.execute_script("arguments[0].click();", current_links[i])

                try:
                    # 動態等待新視窗彈出
                    WebDriverWait(driver, 10).until(
                        EC.number_of_windows_to_be(len(old_handles) + 1)
                    )

                    driver.switch_to.window(driver.window_handles[-1])

                    print("   ⏳ 進入確認頁，等待伺服器轉檔 最多等待 90 秒...")

                    final_link_xpath = (
                        "//a[contains(translate(@href, 'PDF', 'pdf'), '/pdf/') "
                        "or contains(translate(@href, 'ZIP', 'zip'), '.zip')]"
                    )

                    final_pdf_link = WebDriverWait(driver, 90).until(
                        EC.presence_of_element_located((By.XPATH, final_link_xpath))
                    )

                    pdf_url = final_pdf_link.get_attribute("href")
                    print("   ✅ 取得終極載點網址，執行下載中...")

                    # 紀錄下載前的所有檔案清單
                    files_before = set(os.listdir(DOWNLOAD_DIR))

                    driver.get(pdf_url)

                    # 緩衝，讓 .crdownload 產生
                    time.sleep(3)

                    download_ok = wait_for_download_to_finish(DOWNLOAD_DIR, timeout=120)

                    if not download_ok:
                        print("   ❌ 下載等待失敗，這一筆會標記為失敗。")
                        any_item_failed = True
                        continue

                    # 紀錄下載後的所有檔案清單
                    files_after = set(os.listdir(DOWNLOAD_DIR))

                    # 抓出剛剛下載的新檔案
                    new_files = files_after - files_before

                    # 避免抓到暫存檔
                    new_files = [
                        f for f in new_files
                        if not f.endswith(".crdownload")
                    ]

                    if new_files:
                        downloaded_file = list(new_files)[0]
                        downloaded_filepath = os.path.join(DOWNLOAD_DIR, downloaded_file)

                        # 判斷副檔名並進行重命名
                        if downloaded_file.lower().endswith(".zip"):
                            ext = ".zip"
                        else:
                            ext = ".pdf"

                        final_target_name = base_target_name + ext
                        final_target_path = os.path.join(DOWNLOAD_DIR, final_target_name)

                        os.rename(downloaded_filepath, final_target_path)

                        print(f"   🎉 檔案下載並重命名成功：{final_target_name}")

                    else:
                        print("   ❌ 下載完成，但未能捕捉到新檔案，可能被阻擋或覆蓋。")
                        any_item_failed = True

                except TimeoutException:
                    error_img = f"layer3_error_{stock_code}_{year}_Q{i + 1}.png"
                    driver.save_screenshot(error_img)

                    print(f"   ⚠️ 找不到載點或轉檔超時！已拍下確認頁畫面存證：{error_img}")
                    any_item_failed = True

                except Exception as e:
                    error_img = f"layer3_error_{stock_code}_{year}_Q{i + 1}.png"

                    try:
                        driver.save_screenshot(error_img)
                    except Exception:
                        pass

                    print(f"   ❌ 第三層下載流程發生錯誤：{e}")
                    print(f"   📸 若截圖成功，檔名為：{error_img}")

                    any_item_failed = True

                finally:
                    # 關閉第三層視窗，回到主清單
                    cleanup_extra_windows(driver, main_window)

                    print("   ⏳ 休息 5 秒鐘，避免伺服器超載...")
                    time.sleep(5)

        else:
            print(f"⚠️ 找不到財報檔案連結：{stock_code} - {year}年度")
            return True

        if any_item_failed:
            print(f"⚠️ {stock_code} - {year}年度有部分財報下載失敗。")
            return False

        return True

    except KeyboardInterrupt:
        raise

    except Exception as e:
        print(f"❌ 查詢失敗：{stock_code} - {year}年度。錯誤：{e}")
        return False

    finally:
        cleanup_extra_windows(driver, main_window)


# ==========================================
# 3. 程式進入點
# ==========================================
if __name__ == "__main__":
    company_list = get_company_list("companies.txt")
    years = [112, 113, 114]

    if not company_list:
        exit()

    chrome_options = Options()

    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")

    prefs = {
        "download.default_directory": DOWNLOAD_DIR,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "plugins.always_open_pdf_externally": True,
        "safebrowsing.enabled": True,
        "safebrowsing.disable_download_protection": True
    }

    chrome_options.add_experimental_option("prefs", prefs)

    print("啟動 Chrome 瀏覽器中...")

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=chrome_options
    )

    driver.execute_cdp_cmd(
        "Page.setDownloadBehavior",
        {
            "behavior": "allow",
            "downloadPath": DOWNLOAD_DIR
        }
    )

    try:
        for company in company_list:
            for year in years:
                print("\n==========================================")
                print(f"[處理中] 公司代號: {company} | 年度: {year}")
                print("==========================================")

                success = download_mops_pdf(driver, company, year)

                if not success:
                    print(f"   🔁 第一次爬取失敗：{company} - {year}年度")
                    print("   ⏳ 休息 5 秒後重新爬取一次...")

                    time.sleep(5)

                    success = download_mops_pdf(driver, company, year)

                    if not success:
                        print(f"   ❌ 重試後仍失敗，略過：{company} - {year}年度")
                    else:
                        print(f"   ✅ 重試成功：{company} - {year}年度")

                else:
                    print(f"   ✅ 完成：{company} - {year}年度")

                print("   ⏳ 休息 5 秒後處理下一筆...")
                time.sleep(5)

    except KeyboardInterrupt:
        print("\n使用者手動中斷程式。")

    finally:
        print("\n爬蟲結束，關閉瀏覽器。")
        driver.quit()