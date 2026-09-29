#!/usr/bin/env python3
"""单刊 LetPub 查询（诊断 + 落盘）。

用法: python3 letpub_one.py "<期刊名>" <ISSN> [写回的 raw.json] [备用检索键,逗号分隔]
例:   python3 letpub_one.py "INTERNATIONAL JOURNAL OF MOLECULAR SCIENCES" 1661-6596 \
          $WOS_WORKDIR/jmu_aug_cas_raw.json 1422-0067

依次用 [ISSN, 备用键…, 期刊名] 检索；命中则抓详情页分区 block 并写回 raw.json。
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

name, issn = sys.argv[1], sys.argv[2]
out_raw = sys.argv[3] if len(sys.argv) > 3 and not sys.argv[3].startswith("--") else None
extra = sys.argv[4].split(",") if len(sys.argv) > 4 else []
candidates = [issn] + [e for e in extra if e] + [name]
print("检索键顺序:", candidates)

entry = None
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=CHROMIUM, headless=True, args=["--no-sandbox"])
    ctx = b.new_context(user_agent=UA, viewport={"width": 1440, "height": 950})
    page = ctx.new_page()
    for key in candidates:
        page.goto(SEARCH, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(8000)
        box = page.query_selector("input[name='searchissn']") or page.query_selector("input[name='searchname']")
        if not box:
            print(f"[{key}] 无搜索框（限流），等 60s")
            time.sleep(60)
            continue
        use_issn = box.get_attribute("name") == "searchissn" and not re.search(r"[A-Za-z]{4}", key)
        if use_issn:
            box.fill(key)
        else:
            box = page.query_selector("input[name='searchname']") or box
            box.fill(key)
        box.press("Enter")
        page.wait_for_timeout(9000)
        links = page.eval_on_selector_all(
            "a", "els => els.map(e => [e.href, (e.innerText||'').trim()]).filter(s => s[0].includes('journalid'))")
        print(f"[{key}] 命中 journalid 链接 {len(links)} 条" + (f"：{[t[:44] for _, t in links[:5]]}" if links else ""))
        if not links:
            time.sleep(20)
            continue
        best = next(((h, t) for h, t in links if t.upper().strip() == name.upper()), links[0])
        jid = re.search(r"journalid=(\d+)", best[0]).group(1)
        page.goto(f"https://www.letpub.com.cn/index.php?journalid={jid}&page=journalapp&view=detail",
                  wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(7000)
        body = page.inner_text("body")
        m = re.search(r"期刊分区表\s*（\s*([^）]+)）", body)
        if not m:
            print(f"[{key}] 详情页无分区表标题，片段:", body[:240].replace("\n", " | "))
            continue
        entry = {"version": m.group(1).strip(), "block": body[m.end():m.end() + 1500],
                 "jid": jid, "issn": issn, "match": best[1][:60]}
        print(f"[{key}] ✅ {best[1][:60]} | 版本 {entry['version']}")
        print("   block:", entry["block"][:400].replace("\n", " | "))
        break
    b.close()

if entry and out_raw:
    raw = json.load(open(out_raw, encoding="utf-8")) if os.path.exists(out_raw) else {}
    raw[name] = entry
    json.dump(raw, open(out_raw, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"✅ 已写入 {out_raw} [{name}]")
