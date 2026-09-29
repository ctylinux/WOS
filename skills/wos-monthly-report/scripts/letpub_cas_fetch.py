#!/usr/bin/env python3
"""Fetch CAS (中科院) partition tables for a journal list from LetPub, with cache + backoff.

Usage:
  python3 letpub_cas_fetch.py JOURNALS.json RAW.json [START] [END] [--cache other_raw.json ...]

JOURNALS.json: {"<JOURNAL NAME>": {"sn": "<ISSN>", "ei": "<eISSN>", "n": <papers>}, ...}
RAW.json     : output, and itself a cache. Per journal it stores {version, block, jid, issn, match}
               (or {error}). --cache adds MORE previously-swept raw JSONs to seed from — journal
               lists repeat heavily across institutions/months, so this skips most queries.

Throttle: LetPub rate-limits by IP; after ~5-9 quick loads the search page comes back with no
input (''no input''). A fresh browser context does NOT clear it — only TIME does. When that
happens: wait 60-120 s, then process only 3-4 journals per run at ~30 s spacing. Results are
written after EVERY journal, so a killed batch resumes where it stopped (pass START/END again).
Parsing lives in the cas-journal-partition skill's scripts/letpub_cas_parse.py.
"""
import json
import os
import re
import sys
import time
from playwright.sync_api import sync_playwright

_libs = os.environ.get("WOS_CHROME_LIBS", "")
if _libs:
    os.environ["LD_LIBRARY_PATH"] = _libs + ":" + os.environ.get("LD_LIBRARY_PATH", "")
CHROMIUM = os.environ.get("WOS_CHROMIUM") or os.path.expanduser("~/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
SEARCH = "https://www.letpub.com.cn/index.php?page=journalapp&view=search"


def fetch_one(ctx, name, issn):
    page = ctx.new_page()
    page.goto(SEARCH, wait_until="domcontentloaded", timeout=50000)
    page.wait_for_timeout(6000)
    inp = page.query_selector("input[name='searchissn']") or page.query_selector("input[name='searchname']")
    if not inp:
        page.close(); return {'error': 'no input'}          # throttle signature
    if inp.get_attribute('name') == 'searchissn':
        inp.fill(issn); inp.press('Enter')
    else:
        inp.type(name, delay=25); inp.press('Enter')
    page.wait_for_timeout(7000)
    links = page.eval_on_selector_all(
        "a", "els => els.map(e => [e.href, (e.innerText||'').trim()]).filter(s => s[0].includes('journalid'))")
    best = next(((h, t) for h, t in links if t.upper().strip() == name.upper()), links[0] if links else None)
    if not best:
        page.close(); return {'error': 'not found'}
    jid = re.search(r'journalid=(\d+)', best[0]).group(1)
    page.goto(f"https://www.letpub.com.cn/index.php?journalid={jid}&page=journalapp&view=detail",
              wait_until="domcontentloaded", timeout=50000)
    page.wait_for_timeout(6000)
    body = page.inner_text('body')
    labels = list(re.finditer(r'期刊分区表\s*（\s*([^）]+?)）', body))
    labels = [m for m in labels if '新锐' not in body[max(0, m.start() - 8):m.start()]]
    cur = next((m for m in labels if '旧' not in m.group(1)), None)
    page.close()
    if cur is None:
        return {'error': 'no cas table', 'jid': jid, 'match': best[1][:60]}
    return {'version': cur.group(1).strip(), 'block': body[cur.end():len(body)],
            'jid': jid, 'issn': issn, 'match': best[1][:60]}


def main():
    argv = [a for a in sys.argv[1:]]
    caches = []
    while '--cache' in argv:
        i = argv.index('--cache'); caches.append(argv[i + 1]); del argv[i:i + 2]
    jpath, raw_path = argv[0], argv[1]
    start = int(argv[2]) if len(argv) > 2 else 0
    end = int(argv[3]) if len(argv) > 3 else 10 ** 9

    journals = json.load(open(jpath, encoding='utf-8'))
    raw = {}
    for cp in [raw_path] + caches:
        if os.path.exists(cp):
            try:
                for k, v in json.load(open(cp, encoding='utf-8')).items():
                    if k not in raw and isinstance(v, dict) and 'error' not in v:
                        raw[k] = v
            except Exception as e:
                print(f"[warn] cache {cp}: {e}")
    items = list(journals.items())[start:end]
    need = [(n, d) for n, d in items if 'error' in raw.get(n, {'error': 'x'})]
    print(f"区间 {start}-{end}: 需抓 {len(need)} / 已缓存 {len(raw)}")

    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROMIUM, headless=True,
                                    args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
        for name, d in need:
            issn = d.get('sn') or d.get('ei') or ''
            res = None
            for attempt in range(3):
                ctx = browser.new_context(user_agent=UA, viewport={"width": 1440, "height": 950})
                try:
                    res = fetch_one(ctx, name, issn)
                except Exception as e:
                    res = {'error': f'exc: {e}'}
                ctx.close()
                if 'error' not in res:
                    break
                print(f"  retry{attempt + 1} {name[:40]}: {res['error']}")
                time.sleep(15 + attempt * 15)
            raw[name] = res
            print(f"{'OK ' if 'error' not in res else 'ERR'} {name[:44]} -> {res.get('version') or res.get('error')}")
            json.dump(raw, open(raw_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
            time.sleep(5)
        browser.close()
    print(f"完成. 累计 {len(raw)}; 仍缺 {sum(1 for v in raw.values() if 'error' in v)}")


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print(__doc__); sys.exit(2)
    main()
