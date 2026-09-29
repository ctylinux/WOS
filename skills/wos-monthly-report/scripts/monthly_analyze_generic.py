#!/usr/bin/env python3
"""Per-month analyse（机构通用版）: parse alldb (drop PPRN/RC), join woscc C1, judge 第一单位.

用法:
    python3 monthly_analyze_generic.py <prefix> <机构token1> [token2 ...]
例:
    python3 monthly_analyze_generic.py jmu_aug "JIMEI UNIV"
    python3 monthly_analyze_generic.py mnnu_aug "MINNAN NORMAL UNIV" "MINNAN UNIV"

读 <prefix>_alldb.txt / <prefix>_woscc_full.txt
写 <prefix>_parsed.json / <prefix>_c1.json / <prefix>_firstunit_pre.json
"""
import os
import json
import re
import sys
from collections import Counter

W = os.environ.get("WOS_WORKDIR", os.path.expanduser("~/wos-work"))
prefix = sys.argv[1]
tokens = [t.upper() for t in sys.argv[2:]]
assert tokens, "至少要给一个机构名 token（WOS 缩写形式，如 JIMEI UNIV）"


def read_indexed(path):
    lines = open(path, encoding="utf-8-sig").readlines()
    header = lines[0].rstrip("\n").split("\t")
    idx = {}
    for i, n in enumerate(header):
        if n and n not in idx:
            idx[n] = i
    out = []
    for line in lines[1:]:
        if not line.strip():
            continue
        c = line.rstrip("\n").split("\t")
        c += [""] * (len(header) - len(c))
        out.append(c)
    return header, idx, out


h, ai, arows = read_indexed(f"{W}/{prefix}_alldb.txt")
recs = [ {k: c[ai[k]] for k in ("UT", "TI", "AU", "SO", "DI", "PY", "PD", "EA", "DA", "SN", "EI", "DT")}
         for c in arows ]
formal = [r for r in recs if r["UT"].startswith(("WOS:", "MEDLINE:"))]
dropped = [r for r in recs if r not in formal]
print(f"[{prefix}] alldb {len(recs)} -> 正式发表 {len(formal)}，剔除 {len(dropped)} "
      f"({', '.join(sorted({r['UT'].split(':')[0] for r in dropped})) or '无'})")
json.dump({"records": formal, "dropped": dropped}, open(f"{W}/{prefix}_parsed.json", "w"),
          ensure_ascii=False, indent=1)

_, wi, wrows = read_indexed(f"{W}/{prefix}_woscc_full.txt")
c1 = {c[wi["UT"]]: c[wi["C1"]] for c in wrows}
json.dump(c1, open(f"{W}/{prefix}_c1.json", "w"), ensure_ascii=False, indent=1)
print(f"[{prefix}] woscc C1 记录 {len(c1)}")


def first_group(v):
    mm = re.match(r"^\[([^\]]*)\]\s*(.*?)(?:\s*;\s*\[|$)", v or "")
    return (mm.group(1), mm.group(2)) if mm else (None, "")


missing, yes, no = [], [], []
for r in formal:
    ut = r["UT"]
    if ut not in c1:
        missing.append(r)
        continue
    au, aff = first_group(c1[ut])
    (yes if any(t in aff.upper() for t in tokens) else no).append((ut, au, aff))
print(f"[{prefix}] 是 {len(yes)} | 否 {len(no)} | 缺C1 {len(missing)}")
for ut, au, aff in no:
    print(f"     否 {ut} [{au[:30]}] -> {aff[:90]}")
for r in missing:
    print(f"     缺 {r['UT']} {r['SO'][:34]} {r['TI'][:44]}")
json.dump({"missing": [r["UT"] for r in missing], "yes": [u for u, _, _ in yes],
           "no": [u for u, _, _ in no]},
          open(f"{W}/{prefix}_firstunit_pre.json", "w"), ensure_ascii=False, indent=1)
