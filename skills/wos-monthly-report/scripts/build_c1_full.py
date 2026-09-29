#!/usr/bin/env python3
"""为缺 C1 的记录合成第一单位地址，生成 <prefix>_c1_full.json（供饼图/信息图判定学院）。

用法: python3 build_c1_full.py <prefix>        # jmu_aug 或 mnnu_aug（自动补 mnnu_ 前缀）
读: <prefix>_c1.json + <prefix>_missing_addr.json + <prefix>_parsed.json
写: <prefix>_c1_full.json
支持两种地址写法：核心合集编号列表（Addresses\n1 ...）与 MEDLINE 无编号列表（取首条）。
"""
import json
import os
import re
import sys

W = os.environ.get("WOS_WORKDIR", os.path.expanduser("~/wos-work"))
tag = sys.argv[1]
PREFIX = tag if os.path.exists(f"{W}/{tag}_c1.json") else f"mnnu_{tag}"
c1 = json.load(open(f"{W}/{PREFIX}_c1.json", encoding="utf-8"))
miss_path = f"{W}/{PREFIX}_missing_addr.json"
miss = json.load(open(miss_path, encoding="utf-8")) if os.path.exists(miss_path) else {}
if not miss:
    print("（无缺失 C1 记录，c1_full = c1 副本）")
parsed = json.load(open(f"{W}/{PREFIX}_parsed.json", encoding="utf-8"))
au = {(r.get("UT") or ""): (r.get("AU") or "").split(";")[0].strip() for r in parsed["records"]}

added = 0
for ut, d in miss.items():
    if ut in c1:
        continue
    seg = d.get("segment") if isinstance(d, dict) else (d or "")
    seg = seg or ""
    # 地址 1：在 "Addresses" 之后找第一行"含机构关键词"的地址行
    # （兼容 "Addresses\n1 Xxx Univ..."、"Addresses\n邮箱\nAddresses\narrow_drop_down\n1 Xxx Univ..."、
    #   MEDLINE 无编号的散文式地址）
    addr1 = ""
    idx = seg.find("Addresses")
    if idx >= 0:
        for line in seg[idx:].split("\n")[1:]:
            t = line.strip()
            if not t:
                continue
            if re.match(r"^(Addresses|E-mail|arrow_drop_down|Categories|Funding|MeSH|Journal information)", t):
                continue
            if re.search(r"Univ|Coll\b|Inst\b|Acad|Hosp|Key Lab|Sch |Ctr \b|Laborator", t):
                addr1 = re.sub(r"^\d+\s+", "", t)          # 去掉编号 "1 "
                break
    if not addr1:
        print(f"  ⚠️ {ut} 未能取到地址1（原文片段：{seg[:70]!r}）")
        continue
    c1[ut] = f"[{au.get(ut, '')}] {addr1}"
    added += 1
    print(f"  + {ut} → {addr1[:100]}")
json.dump(c1, open(f"{W}/{PREFIX}_c1_full.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"[OK] {PREFIX}_c1_full.json 记录 {len(c1)}（新增 {added}）")
