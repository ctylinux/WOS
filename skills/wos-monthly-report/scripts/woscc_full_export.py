#!/usr/bin/env python3
"""WOS Core Collection: institution (Affiliation) + month range -> Full Record TSV (has C1).

Usage:
  python3 woscc_full_export.py "Minnan Normal University" 2026-07-01 2026-07-31 OUT.tsv

Why: the All-Databases export carries no C1/AB, so first-affiliation (第一单位) judging needs
this Core-Collection FULL RECORD export, joined to the alldb rows by UT. Affiliation (woscc
only) is disambiguated and misses a few records the raw Address match catches — fill those
from the record pages (/wos/woscc/full-record/<UT>, 'Addresses' -> address 1).
"""
import os
import re
import sys
from playwright.sync_api import sync_playwright

_libs = os.environ.get("WOS_CHROME_LIBS", "")
if _libs:
    os.environ["LD_LIBRARY_PATH"] = _libs + ":" + os.environ.get("LD_LIBRARY_PATH", "")
CHROMIUM = os.environ.get("WOS_CHROMIUM") or os.path.expanduser("~/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
WOSCC = "https://webofscience.clarivate.cn/wos/woscc/basic-search"
REMOVE_COOKIE = ("() => { document.querySelectorAll('#onetrust-consent-sdk, #onetrust-banner-sdk, "
                 ".onetrust-pc-dark-filter').forEach(e => e.remove()); return true; }")


def run(institution, start, end, out_path):
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROMIUM, headless=True,
                                    args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
        ctx = browser.new_context(user_agent=UA, viewport={"width": 1440, "height": 950}, accept_downloads=True)
        page = ctx.new_page()
        page.goto(WOSCC, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(12000)
        try:
            page.click("button:has-text('Accept all')", timeout=5000); page.wait_for_timeout(1000)
        except Exception:
            pass
        if 'Authentication' in page.title():
            print("[FAIL] 需登录(非IP直连)."); browser.close(); return 1

        page.click("button[aria-label^='Select search field']", timeout=20000)
        page.wait_for_timeout(1500)
        got = False
        for el in page.query_selector_all("[role='option'], mat-option, app-select-search-field-option"):
            if (el.inner_text() or '').strip() == 'Affiliation':
                el.click(); got = True; break
        if not got:
            for el in page.query_selector_all("[role='option'], mat-option"):
                if 'Address' in (el.inner_text() or ''):
                    el.click(); got = True; break
        if not got:
            print("[FAIL] 无 Affiliation/Address"); browser.close(); return 1
        page.wait_for_timeout(1000)
        sb = page.query_selector("input[aria-label*='Search box']")
        sb.fill(institution); page.wait_for_timeout(600)
        print(f"[verify] field={sb.get_attribute('aria-label')!r}")

        page.click("button:has-text('Add date range')", timeout=20000)
        page.wait_for_timeout(1200)
        page.click("button:has-text('Publication Date')", timeout=15000)
        page.wait_for_timeout(1500)
        for el in page.query_selector_all("button, [role='option'], [role='menuitem'], mat-option, a, span"):
            if (el.inner_text() or '').strip() == 'Custom':
                el.click(force=True); break
        page.wait_for_timeout(2000)
        dis = page.query_selector_all("input.mat-mdc-input-element:not(.mat-mdc-autocomplete-trigger)")
        if len(dis) >= 2:
            dis[0].click(); dis[0].type(start, delay=40); page.wait_for_timeout(500)
            dis[1].click(); dis[1].type(end, delay=40); page.wait_for_timeout(500)
            dis[1].press("Tab"); page.wait_for_timeout(800)

        sb.press("Enter")
        for _ in range(40):
            page.wait_for_timeout(2000)
            if 'summary' in page.url:
                break
        page.wait_for_timeout(8000)
        print(f"[result] {page.title()}")

        page.evaluate(REMOVE_COOKIE); page.wait_for_timeout(1200)
        for b in page.query_selector_all("button"):
            t = (b.inner_text() or '').strip().lower()
            if 'export' in t and 'refine' not in t:
                b.click(force=True); break
        page.wait_for_timeout(2500)
        for el in page.query_selector_all("[role='menuitem'], [role='option'], mat-option, button"):
            if (el.inner_text() or '').strip() == 'Tab delimited file':
                el.click(force=True); break
        page.wait_for_timeout(6500)
        try:
            page.click("#radio3-input", force=True); page.wait_for_timeout(1000)
            mt = page.query_selector("input[name='markTo']")
            print(f"[range] to={mt.input_value() if mt else '?'}")
        except Exception as e:
            print("[warn] range switch:", e)
        # Record Content -> Full Record (match the button by its CURRENT text, then the option text)
        cb = None
        for b in page.query_selector_all("button"):
            if (b.inner_text() or '').strip() == 'Author, Title, Source':
                cb = b; break
        if cb:
            cb.click(force=True); page.wait_for_timeout(2500)
            for el in page.query_selector_all("[role='option'], [role='menuitem'], mat-option, button, a, span"):
                if (el.inner_text() or '').strip() == 'Full Record':
                    el.click(force=True); print("[OK] Record Content = Full Record"); break
            page.wait_for_timeout(2000)
        btn = None
        for b in page.query_selector_all("[role='dialog'] button, mat-dialog-container button, button"):
            if (b.inner_text() or '').strip() == 'Export':
                btn = b; break
        if not btn:
            print("[FAIL] 无 Export 按钮"); browser.close(); return 1
        with page.expect_download(timeout=180000) as dl:
            btn.click(force=True)
        dl.value.save_as(out_path)
        print(f"[OK] {out_path} ({os.path.getsize(out_path)} bytes)")
        txt = open(out_path, encoding='utf-8-sig').read()
        print("[check] C1 非空行数 =", sum(1 for l in txt.split('\n')[1:] if l.strip()))
        if txt.count('Univ') == 0:
            print("[warn] 导出中无 'Univ' — Record Content 可能仍是 Author,Title,Source")
        browser.close()
    return 0


if __name__ == '__main__':
    if len(sys.argv) != 5:
        print(__doc__); sys.exit(2)
    sys.exit(run(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]))
