#!/usr/bin/env python3
"""Render a .docx to a full-page PNG preview (mammoth → HTML → Playwright screenshot).

Usage: python3 render_docx_preview.py <in.docx> <out.png>
"""
import base64
import os
import sys

import mammoth
from playwright.sync_api import sync_playwright

src, out = sys.argv[1], sys.argv[2]
_libs = os.environ.get("WOS_CHROME_LIBS", "")
if _libs:
    os.environ["LD_LIBRARY_PATH"] = _libs + ":" + os.environ.get("LD_LIBRARY_PATH", "")
CHROMIUM = os.environ.get("WOS_CHROMIUM") or os.path.expanduser("~/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome")


def convert_image(image):
    with image.open() as f:
        data = base64.b64encode(f.read()).decode("ascii")
    return {"src": f"data:{image.content_type};base64,{data}"}


with open(src, "rb") as f:
    result = mammoth.convert_to_html(f, convert_image=mammoth.images.img_element(convert_image))
html = f"""<!doctype html><html><head><meta charset="utf-8">
<style>body{{margin:0;padding:24px;background:#fff;font-family:"Microsoft YaHei",sans-serif;width:1000px}}
table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #444;padding:2px 6px;font-size:13px}}
img{{max-width:290px}}</style></head><body>{result.value}</body></html>"""
tmp = "/tmp/brief_preview.html"
open(tmp, "w", encoding="utf-8").write(html)

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=CHROMIUM, headless=True, args=["--no-sandbox"])
    pg = b.new_page(viewport={"width": 1000, "height": 1400}, device_scale_factor=2)
    pg.goto("file://" + tmp)
    pg.wait_for_timeout(800)
    pg.screenshot(path=out, full_page=True)
    b.close()
print("[OK]", out, os.path.getsize(out))
