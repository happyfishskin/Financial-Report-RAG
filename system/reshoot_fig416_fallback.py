#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
重拍圖 4-16：查表未命中後降級至向量軌
======================================
原圖問的是「台積電114Q2的存貨明細表主要揭露什麼內容？」，有兩個問題：

  1. **該表不存在**。台積電 114Q2 的附註表為薪酬、其他收入、員工福利、應收帳齡、
     進貨、財務成本等，並無「存貨明細表」。檢索因此退而抓到資產負債表與現金流量表。
  2. **答案是無關的裸數字**（304,193,716）。軌道二的答案契約為數值導向，開放式的
     「揭露什麼內容」必然得不到敘述性答案——凍結評測中 7 筆降級題的答案**全部**
     是裸數字，可佐證此非個案。

一張要證明「降級鏈生效」的圖，卻同時展示了問到不存在的表、檢索錯表、答非所問，
反而削弱該節論點。改以同樣走降級路徑、但表確實存在且答案可回查原始 CSV 的題目。

新題之路徑（實測）：
  router route=direct_lookup、_graph_fallback=no_match → 查表未命中 → 降級軌道二
  → metadata 硬過濾至 company+quarter → ANN 首位命中正確的「主要管理階層薪酬」表
  → 取出 1,400,324（與 reports_csv_output/2330_…/114Q2/2330_114Q2_主要管理階層薪酬.csv
    之「短期員工福利／本期」欄一致）

前置條件（不符即中止，不將就）：
  · 前端可用；answer_mode 須為 vector_search（真的降級），答案須為 1,400,324
  · ANN 首位片段之表名須為「主要管理階層薪酬」（證明降級後檢索確實定位到正確的表）

    python3 reshoot_fig416_fallback.py [--url http://127.0.0.1:5003]
                                       [--out slides_assets/fig416_fallback.png]
"""
from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
QUESTION = "台積電114Q2的主要管理階層薪酬中，短期員工福利是多少？"
EXPECT_MODE = "vector_search"
EXPECT_ANSWER = "1,400,324"
EXPECT_TOP_TABLE = "主要管理階層薪酬"
# 原圖 6.102 × 2.860 吋 → 比例 2.133；以 1600×750 截圖後裁切至該比例
VIEWPORT = (1600, 1100)


def arg(flag: str, default):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default


URL = str(arg("--url", "http://127.0.0.1:5003")).rstrip("/")


def precheck() -> dict:
    q = urllib.parse.quote(QUESTION)
    with urllib.request.urlopen(f"{URL}/api/ask?q={q}", timeout=300) as r:
        d = json.loads(r.read().decode("utf-8"))
    frs = d.get("fragments") or []
    top = str((frs[0] if frs else {}).get("table_name", ""))
    rt = (d.get("router") or {})
    print(f"  answer_mode : {d.get('answer_mode')!r}（預期 {EXPECT_MODE!r}）")
    print(f"  router route: {rt.get('route')!r}／圖譜 {rt.get('_graph_fallback')!r}")
    print(f"  filter_level: {d.get('filter_level')!r}")
    print(f"  答案        : {d.get('answer')!r}（預期 {EXPECT_ANSWER!r}）")
    print(f"  ANN 首位表名: {top!r}（預期 {EXPECT_TOP_TABLE!r}）")
    ok = (d.get("answer_mode") == EXPECT_MODE
          and str(d.get("answer")).strip() == EXPECT_ANSWER
          and top == EXPECT_TOP_TABLE)
    return {"ok": ok, "payload": d}


def shoot(out: Path) -> bool:
    from playwright.sync_api import sync_playwright
    from PIL import Image

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": VIEWPORT[0],
                                          "height": VIEWPORT[1]},
                                device_scale_factor=2)
        page.goto(URL, wait_until="networkidle")
        page.fill("#q-input", QUESTION)
        page.click("#ask-btn")
        page.wait_for_selector("#result", state="visible", timeout=300_000)
        page.wait_for_function(
            "() => { const b = document.getElementById('route-badge');"
            " return b && b.textContent && b.textContent !== '錯誤'; }",
            timeout=300_000)
        page.wait_for_timeout(2000)
        badge = page.inner_text("#route-badge")
        print(f"  畫面徽章    : {badge}")
        page.screenshot(path=str(out))
        browser.close()

    # 裁至原圖比例（2.133），保留題目、通道指示器、徽章、答案與首筆片段
    im = Image.open(out)
    h = int(im.width / 2.133)
    im.crop((0, 0, im.width, min(h, im.height))).save(out)
    print(f"  裁切後      : {Image.open(out).size}")
    return "向量" in badge or "生成" in badge


def main() -> int:
    out = Path(arg("--out", ROOT / "slides_assets" / "fig416_fallback.png"))
    out.parent.mkdir(parents=True, exist_ok=True)

    print(f"前置檢查（{URL}）")
    pre = precheck()
    if not pre["ok"]:
        print("✗ 與預期不一致 → 不重拍，保留原圖")
        return 1

    print("\n截圖")
    if not shoot(out):
        print("✗ 畫面徽章不符，不採用此圖")
        return 2
    print(f"✓ 已輸出 {out}（{out.stat().st_size:,} bytes）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
