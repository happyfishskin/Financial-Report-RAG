#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
重拍圖 4-14：條件不足之拒答
============================
原圖用「台積電的資產總計是多少？」示範未指定期別時的拒答。[Fix 20] 之後該題改為
套用明示預設期別作答，原圖因此失效，須換用仍會拒答的題目。

改用跨公司比較題「請比較台積電與聯電的資產總計」。Fix 20 **刻意不套用於比較題**：
比較題的結論（較高／趨勢）會因期別而翻轉，替使用者選期別等於替他決定結論，風險
高於單值題；故此類仍要求明確指定期別，正好是「寧缺勿猜」未被放寬的那一半。

順帶修掉原圖的一個缺陷：舊訊息一律回「條件不足，請指定交易對象／欄位」，但此處
缺的是期別，與交易對象無關。新訊息會指出真正缺的條件並列出可選範圍。

前置條件（不符即中止）：
  · answer_mode 為 no_evidence、filter_level 為 ambiguous
  · 訊息須為新版「請指定期別」字樣（舊碼會回舊訊息，代表前端行程未載入 Fix 20）

    python3 reshoot_fig414_insufficient.py [--url http://127.0.0.1:5003]
                                           [--out slides_assets/fig414_insufficient.png]
"""
from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
QUESTION = "請比較台積電與聯電的資產總計"
EXPECT_MODE = "no_evidence"
EXPECT_FILTER = "ambiguous"
EXPECT_IN_ANSWER = "請指定期別"
# 原圖 6.102 × 1.289 吋 → 比例 4.734
VIEWPORT = (1600, 1100)
RATIO = 4.734


def arg(flag: str, default):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default


URL = str(arg("--url", "http://127.0.0.1:5003")).rstrip("/")


def precheck() -> bool:
    q = urllib.parse.quote(QUESTION)
    with urllib.request.urlopen(f"{URL}/api/ask?q={q}", timeout=300) as r:
        d = json.loads(r.read().decode("utf-8"))
    a = str(d.get("answer") or "")
    print(f"  answer_mode : {d.get('answer_mode')!r}（預期 {EXPECT_MODE!r}）")
    print(f"  filter_level: {d.get('filter_level')!r}（預期 {EXPECT_FILTER!r}）")
    print(f"  答案        : {a}")
    if EXPECT_IN_ANSWER not in a:
        print("  ⚠ 訊息仍為舊版 → 該前端行程未載入 Fix 20，請以新行程重啟。")
    return (d.get("answer_mode") == EXPECT_MODE
            and d.get("filter_level") == EXPECT_FILTER
            and EXPECT_IN_ANSWER in a)


def shoot(out: Path) -> bool:
    from playwright.sync_api import sync_playwright
    from PIL import Image

    with sync_playwright() as pw:
        b = pw.chromium.launch()
        page = b.new_page(viewport={"width": VIEWPORT[0], "height": VIEWPORT[1]},
                          device_scale_factor=2)
        page.goto(URL, wait_until="networkidle")
        # 範例題按鈕（#examples）在圖上是純噪音，且會把題目與答案推遠；截圖前先隱藏。
        page.eval_on_selector("#examples", "el => el.style.display = 'none'")
        page.fill("#q-input", QUESTION)
        page.click("#ask-btn")
        page.wait_for_selector("#result", state="visible", timeout=300_000)
        page.wait_for_timeout(2000)
        shown = page.inner_text("#result")
        box_q = page.locator("#q-input").first.bounding_box()
        box_r = page.locator("#result").first.bounding_box()
        page.screenshot(path=str(out))
        b.close()

    # 依元素座標裁出「題目 → 拒答訊息」這一帶（device_scale_factor=2）
    top = max(0, int((box_q["y"] - 22) * 2))
    bot = int((box_r["y"] + box_r["height"] + 22) * 2)
    im = Image.open(out)
    im.crop((0, top, im.width, min(bot, im.height))).save(out)
    print(f"  裁切後      : {Image.open(out).size}")
    return EXPECT_IN_ANSWER in shown


def main() -> int:
    out = Path(arg("--out", ROOT / "slides_assets" / "fig414_insufficient.png"))
    out.parent.mkdir(parents=True, exist_ok=True)
    print(f"前置檢查（{URL}）")
    if not precheck():
        print("✗ 與預期不一致 → 不重拍，保留原圖")
        return 1
    print("\n截圖")
    if not shoot(out):
        print("✗ 畫面未顯示新版拒答訊息，不採用")
        return 2
    print(f"✓ 已輸出 {out}（{out.stat().st_size:,} bytes）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
