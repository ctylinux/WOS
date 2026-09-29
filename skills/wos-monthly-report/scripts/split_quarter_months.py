#!/usr/bin/env python3
"""把季度导出（All Databases + 核心合集全记录）按"正式刊期(PD)所属月份"拆成单月文件。

用法: python3 split_quarter_months.py <quarter_prefix> <out_tag> <YYYY-MM> [--dry]

例:   python3 split_quarter_months.py mnnu_q2 m04 2026-04
      → 生成 mnnu_m04_alldb.txt / mnnu_m04_woscc_full.txt（只含 PD 在 2026-04 的记录）

PD 归一化规则与 build_report_excel.norm_date 保持一致（五种写法）。
"""
import os
import re
import sys

W = os.environ.get("WOS_WORKDIR", os.path.expanduser("~/wos-work"))
MON = {'JAN': '01', 'FEB': '02', 'MAR': '03', 'APR': '04', 'MAY': '05', 'JUN': '06',
       'JUL': '07', 'AUG': '08', 'SEP': '09', 'OCT': '10', 'NOV': '11', 'DEC': '12'}


def norm_date(s):
    """与技能 build_report_excel.norm_date 等价（AUG 27 2026 / AUG 2026 / 2026-Aug-27 /
    2026-Aug / 2026 Jun 11 / 2026 Jun / SEP-OCT 2026 / 2026 SEP-OCT）。"""
    s = (s or '').strip()
    if not s:
        return ''
    for pat, fmt in (
        (r'^([A-Za-z]{3})\s+(\d{1,2})\s+(\d{4})$', lambda m: f"{m.group(3)}-{MON.get(m.group(1).upper(), '?')}-{int(m.group(2)):02d}"),
        (r'^([A-Za-z]{3})\s+(\d{4})$', lambda m: f"{m.group(2)}-{MON.get(m.group(1).upper(), '?')}"),
        (r'^(\d{4})-([A-Za-z]{3})-(\d{1,2})$', lambda m: f"{m.group(1)}-{MON.get(m.group(2).upper(), '?')}-{int(m.group(3)):02d}"),
        (r'^(\d{4})-([A-Za-z]{3})$', lambda m: f"{m.group(1)}-{MON.get(m.group(2).upper(), '?')}"),
        (r'^(\d{4})\s+([A-Za-z]{3})\s+(\d{1,2})$', lambda m: f"{m.group(1)}-{MON.get(m.group(2).upper(), '?')}-{int(m.group(3)):02d}"),
        (r'^(\d{4})\s+([A-Za-z]{3})$', lambda m: f"{m.group(1)}-{MON.get(m.group(2).upper(), '?')}"),
        (r'^([A-Za-z]{3})\s*[-/]\s*([A-Za-z]{3})\s+(\d{4})$', lambda m: f"{m.group(3)}-{MON.get(m.group(1).upper(), '?')}"),
        (r'^(\d{4})\s+([A-Za-z]{3})\s*[-/]\s*([A-Za-z]{3})$', lambda m: f"{m.group(1)}-{MON.get(m.group(2).upper(), '?')}"),
    ):
        m = re.match(pat, s)
        if m:
            return fmt(m)
    return s


def read_indexed(path):
    lines = open(path, encoding="utf-8-sig").readlines()
    header = lines[0].rstrip("\n").split("\t")
    idx = {}
    for i, n in enumerate(header):
        if n and n not in idx:
            idx[n] = i
    rows = []
    for line in lines[1:]:
        if not line.strip():
            continue
        c = line.rstrip("\n").split("\t")
        c += [""] * (len(header) - len(c))
        rows.append(c)
    return header, idx, rows


def split_file(src, dst, month, by_ut=None, dry=False):
    header, idx, rows = read_indexed(src)
    ui, pi = idx["UT"], idx["PD"]
    keep = []
    for c in rows:
        if by_ut is not None and c[ui] not in by_ut:
            continue
        if norm_date(c[pi])[:7] == month:
            keep.append(c)
    if not dry:
        with open(dst, "w", encoding="utf-8", newline="") as f:
            f.write("\t".join(header) + "\n")
            for c in keep:
                f.write("\t".join(c) + "\n")
    return len(rows), keep


qprefix, out_tag, month = sys.argv[1], sys.argv[2], sys.argv[3]
dry = "--dry" in sys.argv

na, keep_a = split_file(f"{W}/{qprefix}_alldb.txt", f"{W}/{out_tag}_alldb.txt", month, dry=dry)
print(f"[{out_tag}] alldb: 季度 {na} 条 → PD 在 {month} 的 {len(keep_a)} 条")
uts = {c[0] for c in keep_a}                          # 第一列在季度 alldb 里不是 UT，改用下面按 UT 列取
header, idx, rows = read_indexed(f"{W}/{qprefix}_alldb.txt")
uts = {c[idx["UT"]] for c in keep_a}
nw, keep_w = split_file(f"{W}/{qprefix}_woscc_full.txt", f"{W}/{out_tag}_woscc_full.txt", month,
                        by_ut=uts, dry=dry)
print(f"[{out_tag}] woscc: 季度 {nw} 条 → 命中 {len(keep_w)} 条")
prefixes = {}
for c in keep_a:
    p = c[idx["UT"]].split(":")[0]
    prefixes[p] = prefixes.get(p, 0) + 1
print(f"[{out_tag}] UT 前缀分布: {prefixes}（PPRN/RC 将在建表时剔除）")
