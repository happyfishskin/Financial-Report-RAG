#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
無頭瀏覽器自動執行「渲染方式對照實驗」
=======================================
前置：Neo4j 容器已啟動（podman start my-neo4j）、Flask app 在 5001 埠
（本腳本會自行啟動/關閉 Flask 子行程）。

用法：
  python3 run_render_benchmark.py [--rounds 3] [--expands 3]

輸出：render_benchmark_result.json ＋ console 摘要表
"""

import argparse
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent
URL = "http://127.0.0.1:5001"


def wait_http(url: str, timeout_s: float = 30) -> bool:
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        try:
            with urllib.request.urlopen(url, timeout=2):
                return True
        except Exception:
            time.sleep(0.5)
    return False


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--expands", type=int, default=3)
    args = ap.parse_args()

    flask_proc = None
    if not wait_http(f"{URL}/api/health", timeout_s=2):
        print("▶ 啟動 Flask app（port 5001）…")
        flask_proc = subprocess.Popen(
            [sys.executable, str(BASE / "app.py")],
            cwd=BASE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if not wait_http(f"{URL}/api/health", timeout_s=30):
            print("✗ Flask 啟動失敗"); sys.exit(1)

    from playwright.sync_api import sync_playwright

    try:
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(headless=True)
            except Exception:
                browser = p.chromium.launch(headless=True, channel="chrome")
            page = browser.new_page(viewport={"width": 1600, "height": 1000})
            page.goto(URL, wait_until="networkidle")

            page.click('button[data-tab="bench"]')
            page.fill("#bench-rounds", str(args.rounds))
            page.fill("#bench-expands", str(args.expands))
            print(f"▶ 執行對照實驗：{args.rounds} 回合 × 展開 {args.expands} 家…")
            t0 = time.time()
            page.click("#bench-run-btn")

            page.wait_for_function(
                "window.__BENCH_RESULT !== null",
                timeout=15 * 60 * 1000, polling=1000)
            result = page.evaluate("window.__BENCH_RESULT")
            print(f"▶ 實驗完成（{time.time()-t0:.0f} s）")
            browser.close()
    finally:
        if flask_proc:
            flask_proc.terminate()

    out = BASE / "render_benchmark_result.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")

    c = result["summary"]["control"]
    e = result["summary"]["experiment"]
    n_exp = len(result["experiment"][0]["expands"])
    print()
    print("═" * 68)
    print(f"  前端渲染對照結果（{result['rounds']} 回合平均）")
    print("═" * 68)
    print(f"  {'指標':<22}{'控制組·全圖一次':>16}{'實驗組·分層首屏':>16}{'單次點擊展開':>12}")
    rows = [
        ("後端查詢 (ms)",  c["query_ms"],       e["init_query_ms"],    e.get("expand_query_ms")),
        ("資料下載 (ms)",  c["download_ms"],    e["init_download_ms"], e.get("expand_download_ms")),
        ("傳輸量 (KB)",    c["bytes"] / 1024,   e["init_bytes"] / 1024, e["expand_bytes"] / 1024),
        ("前端渲染 (ms)",  c["render_ms"],      e["init_render_ms"],   e["expand_render_ms"]),
        ("可互動時間 (ms)", c["ttfi_ms"],       e["init_ttfi_ms"],     e["expand_click_ms"]),
    ]
    for name, cv, ev, xv in rows:
        print(f"  {name:<24}{cv:>14.1f}{ev:>16.1f}" + (f"{xv:>14.1f}" if xv is not None else f"{'—':>14}"))
    print(f"  {'節點 / 邊':<24}{str(c['nodes'])+' / '+str(c['edges']):>14}"
          f"{str(e['init_nodes'])+' / 0':>16}"
          f"{'展開後 '+str(e['final_nodes'])+' / '+str(e['final_edges']):>14}")
    sp = result["summary"]["first_view_speedup"]
    print(f"\n  ▶ 首屏可互動時間：實驗組是控制組的 1/{sp:.1f}（快 {sp:.1f} 倍）")
    print(f"  已輸出 {out.name}")


if __name__ == "__main__":
    main()
