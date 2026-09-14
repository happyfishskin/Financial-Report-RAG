#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
重拍圖 4-17：關係事實直查之多答案（全列並列）輸出
==================================================
原圖拍的是 Fix 19 之前的行為——候選不唯一時，系統把整列序列化字串原樣傾印，
畫面上是一長串 `value_2=…; value_5=…`，既不是題目所問，也不可讀。附錄 B.7 的
候選歧義分層量測把成因定位到「樣板缺少全列並列分支」，Fix 19 補上之後，同一張
表的同一家公司改為輸出乾淨的多答案清單，故重拍此圖。

刻意沿用原圖的公司（華邦電子）與同一張關係人交易表，使讀者可直接對照前後差異。

前置條件（不符即中止，不將就）：
  · 前端可用，且**該前端行程已載入 Fix 19**（5002 若是改碼前啟動的舊行程，
    會回傳單一數值而非清單，前置檢查會擋下來；另起一個行程即可）
  · 該題答案為 5 個以「｜」分隔的交易對象，answer_mode 為 relation_lookup

    python3 reshoot_fig417_multi_answer.py [--url http://127.0.0.1:5003]
                                           [--out slides_assets/fig417_multi_answer.png]
"""
from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
QUESTION = ("根據關係人交易圖譜，【華邦電子】在【113Q2】揭露的關係人交易中，"
            "交易人【新唐科技公司】有哪些交易對象？請全部列出。")
EXPECT_MODE = "relation_lookup"
EXPECT_ITEMS = 5
# 原圖 5.906 × 4.086 吋 → 比例 1.445；以 1400×969 截圖後縮放不失真
VIEWPORT = (1400, 969)


def arg(flag: str, default):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default


URL = str(arg("--url", "http://127.0.0.1:5003")).rstrip("/")


def precheck() -> dict:
    q = urllib.parse.quote(QUESTION)
    with urllib.request.urlopen(f"{URL}/api/ask?q={q}", timeout=240) as r:
        d = json.loads(r.read().decode("utf-8"))
    ans = str(d.get("answer") or "")
    items = [x.strip() for x in ans.split("｜") if x.strip()]
    print(f"  answer_mode : {d.get('answer_mode')!r}（預期 {EXPECT_MODE!r}）")
    print(f"  答案項數    : {len(items)}（預期 {EXPECT_ITEMS}）")
    print(f"  答案        : {ans[:90]}")
    if len(items) <= 1:
        print("  ⚠ 只回傳單一項：該前端行程很可能是 Fix 19 之前啟動的舊碼，"
              "請以新行程重啟後再拍。")
    return {"ok": d.get("answer_mode") == EXPECT_MODE and len(items) == EXPECT_ITEMS,
            "payload": d, "items": items}


def shoot(out: Path) -> bool:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": VIEWPORT[0],
                                          "height": VIEWPORT[1]},
                                device_scale_factor=2)
        page.goto(URL, wait_until="networkidle")
        page.fill("#q-input", QUESTION)
        page.click("#ask-btn")
        page.wait_for_selector("#result", state="visible", timeout=240_000)
        page.wait_for_function(
            "() => { const b = document.getElementById('route-badge');"
            " return b && b.textContent && b.textContent !== '錯誤'; }",
            timeout=240_000)
        page.wait_for_timeout(2500)
        badge = page.inner_text("#route-badge")
        shown = page.inner_text("#result")
        print(f"  畫面徽章    : {badge}")
        page.screenshot(path=str(out))
        browser.close()
    # 畫面上必須真的看得到多個項目，否則這張圖沒有替換的意義
    return "關係事實直查" in badge and shown.count("｜") >= EXPECT_ITEMS - 1


def main() -> int:
    out = Path(arg("--out", ROOT / "slides_assets" / "fig417_multi_answer.png"))
    out.parent.mkdir(parents=True, exist_ok=True)

    print(f"前置檢查（{URL}）")
    pre = precheck()
    if not pre["ok"]:
        print("✗ 與預期不一致 → 不重拍，保留原圖")
        return 1

    print("\n截圖")
    if not shoot(out):
        print("✗ 畫面未顯示多答案清單或徽章不符，不採用此圖")
        return 2
    print(f"✓ 已輸出 {out}（{out.stat().st_size:,} bytes）")
    print(f"  項目：{' ｜ '.join(pre['items'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
