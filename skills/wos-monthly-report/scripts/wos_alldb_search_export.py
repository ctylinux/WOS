#!/usr/bin/env python3
"""WOS All Databases: institution (Address) + month range -> export TSV.

Usage:
  python3 wos_alldb_search_export.py "Minnan Normal University" 2026-07-01 2026-07-31 OUT.tsv

Uses IP-direct access (fresh context, no storage_state) — on a campus network this needs
no login. Prints the result count from the page title. Export switches the record range to
1..N (the default 'All records on page' silently caps at the 50-row page size).
NOTE: the All-Databases TSV never carries C1/AB -> affiliations need woscc_full_export.py.
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
WOS_URL = "https://webofscience.clarivate.cn/wos/alldb/basic-search"
REMOVE_COOKIE = ("() => { document.querySelectorAll('#onetrust-consent-sdk, #onetrust-banner-sdk, "
                 ".onetrust-pc-dark-filter').forEach(e => e.remove()); return true; }")


def run(institution, start, end, out_path):
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROMIUM, headless=True,
                                    args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
        ctx = browser.new_context(user_agent=UA, viewport={"width": 1440, "height": 950}, accept_downloads=True)
        page = ctx.new_page()
        page.goto(WOS_URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(12000)
        try:
            page.click("button:has-text('Accept all')", timeout=5000)
            page.wait_for_timeout(1000)
        except Exception:
            pass
        if 'Authentication' in page.title():
            print("[FAIL] 需登录(非IP直连). 先按 institutional-database-access 走 CARSI.")
            browser.close()
            return 1

        # field = Address (All Databases has no Affiliation)
        page.click("button[aria-label^='Select search field']", timeout=20000)
        page.wait_for_timeout(1500)
        got = False
        for el in page.query_selector_all("[role='option'], mat-option, app-select-search-field-option"):
            if (el.inner_text() or '').strip() == 'Address':
                el.click(); got = True; break
        if not got:
            print("[FAIL] 字段下拉无 Address"); browser.close(); return 1
        page.wait_for_timeout(1000)

        sb = page.query_selector("input[aria-label*='Search box']")
        sb.fill(institution)
        page.wait_for_timeout(600)
        print(f"[verify] field={sb.get_attribute('aria-label')!r} query={sb.input_value()!r}")

        # Publication Date custom range (type(), not fill())
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
            print(f"[verify] dates=[{dis[0].input_value()!r},{dis[1].input_value()!r}]")

        sb.press("Enter")
        for _ in range(40):
            page.wait_for_timeout(2000)
            if 'summary' in page.url:
                break
        page.wait_for_timeout(8000)
        title = page.title()
        print(f"[result] {title}")
        m = re.search(r'–\s*(\d+)\s*–', title) or re.search(r'([\d,]+)\s*results? from', page.inner_text('body'))
        total = int(m.group(1).replace(',', '')) if m else 0
        print(f"[result] N={total}")

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
            mf = page.query_selector("input[name='markFrom']"); mt = page.query_selector("input[name='markTo']")
            print(f"[range] {mf.input_value() if mf else '?'}-{mt.input_value() if mt else '?'}")
        except Exception as e:
            print("[warn] range switch:", e)
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
        rows = sum(1 for l in open(out_path, encoding='utf-8-sig').read().split('\n')[1:] if l.strip())
        print(f"[check] 非空记录={rows} (期望 {total})" + ("  ✅" if rows == total else "  ⚠️ 不一致，检查范围是否切 1..N"))
        browser.close()
    return 0


if __name__ == '__main__':
    if len(sys.argv) != 5:
        print(__doc__); sys.exit(2)
    sys.exit(run(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]))
