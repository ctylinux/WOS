#!/usr/bin/env python3
"""Generalised journals.json builder + CAS cache coverage report.

用法: python3 journals_generic.py <prefix>        # 读 <prefix>_parsed.json
写: <prefix>_journals.json / <prefix>_journals_miss.json
"""
import glob
import json
import os
import sys

W = os.environ.get("WOS_WORKDIR", os.path.expanduser("~/wos-work"))
prefix = sys.argv[1]
parsed = json.load(open(f"{W}/{prefix}_parsed.json", encoding="utf-8"))
recs = parsed["records"]

journals = {}
for r in recs:
    so = (r.get("SO") or "").strip()
    if not so:
        print("!! no SO:", r.get("UT"), (r.get("TI") or "")[:60])
        continue
    d = journals.setdefault(so, {"sn": "", "ei": "", "n": 0})
    d["n"] += 1
    if not d["sn"] and r.get("SN"):
        d["sn"] = r["SN"].split()[0].strip()
    if not d["ei"] and r.get("EI"):
        d["ei"] = r["EI"].split()[0].strip()
json.dump(journals, open(f"{W}/{prefix}_journals.json", "w"), ensure_ascii=False, indent=1)
print(f"[{prefix}] 期刊数 {len(journals)} / 正式发表 {len(recs)} 篇")

caches = sorted(set(glob.glob(f"{W}/*cas_raw.json")))
cached = {}
for c in caches:
    try:
        for k, v in json.load(open(c, encoding="utf-8")).items():
            if k not in cached and isinstance(v, dict) and "error" not in v:
                cached[k] = os.path.basename(c)
    except Exception as e:
        print("cache warn", c, e)
print(f"缓存可用期刊 {len(cached)}（来自 {len(caches)} 个缓存文件）")
miss, hit = {}, 0
for n, d in sorted(journals.items()):
    if n in cached:
        hit += 1
    else:
        miss[n] = d
        print(f"  MISS {n[:56]:58s} n={d['n']} issn={d['sn'] or d['ei']}")
json.dump(miss, open(f"{W}/{prefix}_journals_miss.json", "w"), ensure_ascii=False, indent=1)
print(f"[{prefix}] 命中 {hit} / 需抓取 {len(miss)} 刊 -> {(len(miss) + 4) // 5} 批")
