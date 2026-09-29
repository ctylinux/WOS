#!/usr/bin/env python3
"""把门户打包成可直接上传静态托管的自包含目录（含交付物文件，链接改写为相对路径）。

用法：
    python3 pack_portal.py https://example.com/portal/   # 指定发布地址（页面与二维码按此地址重建）
    python3 pack_portal.py                               # 只打包，地址沿用当前 portal/index.html

输出：portal_publish/  —— 把该目录里的内容上传即可，入口为 index.html。
"""
import os
import re
import shutil
import subprocess
import sys

W = os.environ.get("WOS_WORKDIR", os.path.expanduser("~/wos-work"))
SRC = f"{W}/portal"
OUT = f"{W}/portal_publish"
URL = sys.argv[1] if len(sys.argv) > 1 else None

# 1) 指定了发布地址：先重建页面与二维码（地址在页面上与二维码里都随之更新）
if URL:
    env = dict(os.environ, PORTAL_URL=URL)
    subprocess.run([sys.executable, f"{W}/build_portal.py"], env=env, check=True)

html = open(f"{SRC}/index.html", encoding="utf-8").read()

# 2) 收集 ../ 形式的交付物链接，复制进 downloads/ 并改写链接
names = sorted(set(re.findall(r'href="\.\./([^"]+)"', html)))
missing = []
for name in names:
    src = os.path.join(W, name)
    dst = os.path.join(OUT, "downloads", name)
    if os.path.isfile(src):
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
    else:
        missing.append(name)
html = html.replace('href="../', 'href="downloads/')

# 3) 落地页面与二维码
os.makedirs(OUT, exist_ok=True)
open(f"{OUT}/index.html", "w", encoding="utf-8").write(html)
for extra in ("qr.png", "访问说明.txt"):
    p = os.path.join(SRC, extra)
    if os.path.exists(p):
        shutil.copy2(p, os.path.join(OUT, extra))

# 4) 自检 + 报告
assert 'href="../' not in html, "仍有 ../ 链接未改写"
files = [os.path.join(dp, f) for dp, _, fs in os.walk(OUT) for f in fs]
total = sum(os.path.getsize(f) for f in files)
print(f"[OK] {OUT}  文件 {len(files)} 个，共 {total / 1048576:.1f} MB")
print(f"     入口 index.html；交付物 {len(names) - len(missing)}/{len(names)} 个已放入 downloads/")
if missing:
    print("     ⚠️ 源文件缺失（发布后这些链接会 404）：")
    for m in missing:
        print("       -", m)
print("     自检通过：页面无 ../ 残留链接")
