#!/usr/bin/env python3
"""Visit full-record pages for records missing C1 and dump the Addresses section.

Usage: python3 mnnu_missing_addr_generic.py <tag>     # 读 mnnu_<tag>_firstunit_pre.json
Writes: mnnu_<tag>_missing_addr.json
"""
import json
import os
import sys
import time

from playwright.sync_api import sync_playwright

_libs = os.environ.get("WOS_CHROME_LIBS", "")
if _libs:
    os.environ["LD_LIBRARY_PATH"] = _libs + ":" + os.environ.get("LD_LIBRARY_PATH", "")
CHROMIUM = os.environ.get("WOS_CHROMIUM") or os.path.expanduser("~/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
BASE = "https://webofscience.clarivate.cn/wos/woscc/full-record/"
W = os.environ.get("WOS_WORKDIR", os.path.expanduser("~/wos-work"))
tag = sys.argv[1]
# 前缀自适应：支持 <tag>_firstunit_pre.json 与 mnnu_<tag>_firstunit_pre.json 两种命名
PREFIX = tag if os.path.exists(f"{W}/{tag}_firstunit_pre.json") else f"mnnu_{tag}"
uts = json.load(open(f"{W}/{PREFIX}_firstunit_pre.json", encoding="utf-8"))["missing"]
print("prefix:", PREFIX, "| targets:", uts)

out = {}
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=CHROMIUM, headless=True,
                                args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
    ctx = browser.new_context(user_agent=UA, viewport={"width": 1440, "height": 950})
    page = ctx.new_page()
    for ut in uts:
        url = BASE + ut
        seg = ""
        for attempt in range(4):          # 全记录页偶发 500 / SYSTEM ERROR，隔 10s 重试
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(9000)
                body = page.inner_text("body")
            except Exception as e:
                print(f"[ERR {attempt + 1}] {ut}: {e}")
                time.sleep(10)
                continue
            i = body.find("Addresses")
            seg = body[i:i + 1600] if i >= 0 else ""
            if not seg:
                j = body.find("Address")
                seg = body[j:j + 1600] if j >= 0 else body[:1500]
            if seg and "SYSTEM ERROR" not in body[:400] and "HTTP Status 500" not in body[:400]:
                break
            print(f"[retry {attempt + 1}] {ut} 页面异常，10s 后重试")
            time.sleep(10)
        out[ut] = {"url": url, "segment": seg, "title": page.title()}
        print("=" * 100)
        print(ut, "|", page.title()[:80])
        print(seg[:1300])
        time.sleep(2)
    browser.close()

json.dump(out, open(f"{W}/{PREFIX}_missing_addr.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print(f"\nwrote {PREFIX}_missing_addr.json")
