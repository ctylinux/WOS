#!/usr/bin/env python3
"""列出某机构第一单位=是记录的 C1 二级单位写法与计数（用于建立学院映射）。

用法: python3 dept_inventory.py <prefix> <机构token...>
"""
import os
import json
import re
import sys
from collections import Counter

W = os.environ.get("WOS_WORKDIR", os.path.expanduser("~/wos-work"))
prefix = sys.argv[1]
tokens = [t.upper() for t in sys.argv[2:]]
c1 = json.load(open(f"{W}/{prefix}_c1.json", encoding="utf-8"))
pre = json.load(open(f"{W}/{prefix}_firstunit_pre.json", encoding="utf-8"))
parsed = json.load(open(f"{W}/{prefix}_parsed.json", encoding="utf-8"))
by_ut = {r["UT"]: r for r in parsed["records"]}

yes = set(pre["yes"])
cnt = Counter()
detail = {}
for ut in sorted(yes):
    seg = c1.get(ut, "") or ""
    m = re.match(r"^\[([^\]]*)\]\s*(.*?)(?:\s*;\s*\[|$)", seg)
    raw = m.group(2) if m else "(无C1)"
    # 去掉机构名与邮编/国家尾巴，只留二级单位
    raw2 = re.sub(r",?\s*(\d{6}|Peoples R China|Peoples Republic of China|\d{5}).*$", "", raw).strip(" ,")
    for t in tokens:
        if raw.upper().startswith(t):
            raw2 = re.sub(r"^" + re.escape(t), "", raw2, flags=re.I).strip(" ,")
            break
    parts = [p.strip() for p in raw2.split(",") if p.strip()]
    key = parts[0] if parts else "(空)"
    rest = ", ".join(parts[1:3])
    cnt[key] += 1
    detail.setdefault(key, []).append((ut, rest, (by_ut.get(ut, {}).get("SO") or "")[:28]))
print(f"{prefix}: 第一单位=是 {len(yes)} 篇，二级单位写法 {len(cnt)} 种\n")
for k, n in cnt.most_common():
    print(f"{n:>3} × {k}")
    for ut, rest, so in detail[k][:2]:
        print(f"        {ut} | {rest[:60]} | {so}")
json.dump({k: v for k, v in detail.items()}, open(f"{W}/{prefix}_dept_inventory.json", "w"),
          ensure_ascii=False, indent=1)
