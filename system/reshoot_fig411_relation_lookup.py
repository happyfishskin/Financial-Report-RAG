#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
重拍圖 4-11：關係事實直查之實際問答畫面
========================================
原圖取自雙軌重構**之前**的建置，畫面路由標籤仍是 `graph_rag`——那是全文已宣告
下架的字面值，出現在「給委員看畫面」的那一節最容易被指著問。前端的標籤對照表
已補上 `relation_lookup`，故重拍後標籤會與正文一致，§4.9 的但書可一併移除。

只重拍這一張：圖 4-10（direct_lookup）與 4-12（vector_search）的標籤本來就正確，
重拍它們不會改善任何東西，只會多兩次「新截圖與論文敘述是否一致」的核對風險。

前置條件（不符即中止，不將就）：
  · 前端於 127.0.0.1:5002 可用、vLLM 可用
  · 該題答案仍為「營運資金壓力」、answer_mode 為 relation_lookup

    python3 reshoot_fig411_relation_lookup.py [--out slides_assets/fig411_relation_lookup.png]
"""
from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
URL = "http://127.0.0.1:5002"
QUESTION = ("根據風險事件圖譜，【旺矽科技】在【114Q4】的財務科目"
            "【其他應付款增加（減少）】被標記為哪一類風險候選？")
EXPECT_ANSWER = "營運資金壓力"
EXPECT_MODE = "relation_lookup"
# 原圖 6.10 × 4.16 吋 → 比例 1.466；以 1400×954 截圖後縮放不失真
VIEWPORT = (1400, 954)


def arg(flag: str, default):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default


def precheck() -> dict:
    q = urllib.parse.quote(QUESTION)
    with urllib.request.urlopen(f"{URL}/api/ask?q={q}", timeout=180) as r:
        d = json.loads(r.read().decode("utf-8"))
    ok = d.get("answer") == EXPECT_ANSWER and d.get("answer_mode") == EXPECT_MODE
    print(f"  答案      : {d.get('answer')!r}（預期 {EXPECT_ANSWER!r}）")
    print(f"  answer_mode: {d.get('answer_mode')!r}（預期 {EXPECT_MODE!r}）")
    print(f"  子圖       : {len((d.get('graph') or {}).get('nodes', []))} 節點／"
          f"{len((d.get('graph') or {}).get('edges', []))} 邊")
    return {"ok": ok, "payload": d}


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
        # 等答案渲染完成：結果區塊出現且路由徽章不再是「錯誤」
        page.wait_for_selector("#result", state="visible", timeout=180_000)
        page.wait_for_function(
            "() => { const b = document.getElementById('route-badge');"
            " return b && b.textContent && b.textContent !== '錯誤'; }",
            timeout=180_000)
        page.wait_for_timeout(2500)          # 讓 vis-network 子圖穩定下來
        badge = page.inner_text("#route-badge")
        print(f"  畫面徽章  : {badge}")
        page.screenshot(path=str(out))
        browser.close()
    return "關係事實直查" in badge


def main() -> int:
    out = Path(arg("--out", ROOT / "slides_assets" / "fig411_relation_lookup.png"))
    out.parent.mkdir(parents=True, exist_ok=True)

    print("前置檢查（答案與論文所述須一致，否則中止不重拍）")
    pre = precheck()
    if not pre["ok"]:
        print("✗ 與論文所述不一致 → 依決策保留原圖與註解，不重拍")
        return 1

    print("\n截圖")
    ok = shoot(out)
    if not ok:
        print("✗ 畫面徽章未顯示「關係事實直查」，不採用此圖")
        return 2
    print(f"✓ 已輸出 {out}（{out.stat().st_size:,} bytes）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
