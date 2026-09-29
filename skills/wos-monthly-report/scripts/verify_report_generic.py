#!/usr/bin/env python3
"""交付前验证（机构通用）：xlsx 结构、计数自洽、日期归一化、非论文类型、"否"逐条核对。

用法: python3 verify_report_generic.py <prefix> <xlsx> <institution> [是否列名]
"""
import csv
import json
import re
import sys
from collections import Counter

from openpyxl import load_workbook

W = os.environ.get("WOS_WORKDIR", os.path.expanduser("~/wos-work"))
prefix, XLSX, INST = sys.argv[1], sys.argv[2], sys.argv[3]
CSV = XLSX.replace(".xlsx", ".csv")

wb = load_workbook(XLSX)
ws = wb[wb.sheetnames[0]]
header = [c.value for c in ws[1]]
rows = [[c.value for c in r] for r in ws.iter_rows(min_row=2)]
print("sheets:", wb.sheetnames, "| 表头:", " | ".join(str(h) for h in header))
print("数据行数:", len(rows))

i_ut = header.index([h for h in header if "第一单位" in h][0])
i_q = header.index([h for h in header if "大类分区" in h][0])
i_top = header.index("Top期刊")
i_pd, i_da, i_ea = header.index("正式出版时间"), header.index("入库时间"), header.index("EA时间")
print("第一单位:", dict(Counter(r[i_ut] for r in rows)))
print("大类分区:", dict(Counter(r[i_q] for r in rows)))
print("Top期刊:", dict(Counter(r[i_top] for r in rows)))

pat = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$")
bad = [(r[1], r[i_pd], r[i_da], r[i_ea]) for r in rows
       if any(v and not pat.match(str(v).strip()) for v in (r[i_pd], r[i_da], r[i_ea]))]
print("日期格式异常:", len(bad), bad[:4])

parsed = json.load(open(f"{W}/{prefix}_parsed.json", encoding="utf-8"))
print("DT 分布:", dict(Counter(r.get("DT", "") for r in parsed["records"])))
print("剔除:", len(parsed["dropped"]),
      dict(Counter(r["UT"].split(":")[0] for r in parsed["dropped"])))

ut_by_title = {}
for r in parsed["records"]:
    ut_by_title[re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", (r.get("TI") or "").lower())] = r["UT"]
c1 = {k: v for k, v in json.load(open(f"{W}/{prefix}_c1_full.json", encoding="utf-8")).items()}
miss = {}
import os
if os.path.exists(f"{W}/{prefix}_missing_addr.json"):
    miss = json.load(open(f"{W}/{prefix}_missing_addr.json", encoding="utf-8"))
print("\n第一单位=否 的记录与第一作者单位（前 12 条）：")
n = 0
for r in csv.DictReader(open(CSV, encoding="utf-8-sig")):
    if r.get(f"{INST}是否第一单位") == "否":
        n += 1
        ut = ut_by_title.get(re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", (r["篇名"] or "").lower()), "")
        seg = c1.get(ut, "")
        m = re.match(r"^\[[^\]]*\]\s*(.*?)(?:\s*;\s*\[|$)", seg or "")
        src = "C1"
        if not seg:
            s = (miss.get(ut, {}) or {}).get("segment", "")
            src = "全记录页"
            m = re.search(r"Addresses\s*\n(?:\d+\s*)?(.+?)(?:\n|$)", s)
        print(f"   [{'?' if not seg else src}] {ut} -> {(m.group(1) if m else '(未取到)')[:86]}")
print(f"   共 {n} 条")
