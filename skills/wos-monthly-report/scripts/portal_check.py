#!/usr/bin/env python3
"""核对门户：期次标签、各期指标卡数字、下载项数量，并截图。"""
import os
import re
import sys

from playwright.sync_api import sync_playwright

_libs = os.environ.get("WOS_CHROME_LIBS", "")
if _libs:
    os.environ["LD_LIBRARY_PATH"] = _libs + ":" + os.environ.get("LD_LIBRARY_PATH", "")
CHROMIUM = os.environ.get("WOS_CHROMIUM") or os.path.expanduser("~/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome")
URL = "http://localhost:8080/portal/"
OUT = sys.argv[1] if len(sys.argv) > 1 else "/tmp/portal_check.png"
WATCH = sys.argv[2:] or ["4月", "5月", "8月"]

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=CHROMIUM, headless=True, args=["--no-sandbox"])
    pg = b.new_page(viewport={"width": 1440, "height": 2200}, device_scale_factor=1)
    pg.goto(URL, wait_until="load", timeout=60000)
    pg.wait_for_timeout(2500)
    body = pg.inner_text("body")
    print("模板残留检查:", "❌ 发现 ${" if "${" in body else "✅ 无")
    tabs = pg.eval_on_selector_all(
        "[data-tab], .tab, .tabs button, .tabs a, nav button",
        "els => els.map(e => (e.innerText||'').trim()).filter(Boolean)")
    print("期次数:", len(tabs))
    for t in tabs:
        print("   -", t[:40])
    for label in WATCH:
        try:
            pg.click(f"text={label}", timeout=4000)
            pg.wait_for_timeout(900)
            kpi = pg.eval_on_selector_all(".kpi, .card .n, .kpi b", "els => els.map(e => (e.innerText||'').trim())")
            print(f"[{label}] 指标片段: {kpi[:8]}")
        except Exception as e:
            print(f"[{label}] 点击失败: {str(e)[:70]}")
    dl = pg.eval_on_selector_all("a.dl", "els => els.map(e => (e.innerText||'').split('\\n')[0])")
    print("交付物下载项:", len(dl))
    for d in dl:
        print("   ·", d[:46])
    pg.screenshot(path=OUT, full_page=True)
    print("[OK]", OUT)
    b.close()
