#!/usr/bin/env python3
"""把本地所有中科院分区缓存合并成一个文件，供 build_report_excel.py --cas 使用。

用法: python3 merge_cas_cache.py [输出路径]   # 默认 $WOS_WORKDIR/mnnu_cas_all.json
优先级：按文件修改时间从新到旧，先到先得；带 error 的条目不覆盖已有成功条目。
"""
import glob
import json
import os
import sys

W = os.environ.get("WOS_WORKDIR", os.path.expanduser("~/wos-work"))
out_path = sys.argv[1] if len(sys.argv) > 1 else f"{W}/mnnu_cas_all.json"

paths = sorted(set(glob.glob(f"{W}/mnnu_*_cas_raw.json") + glob.glob(f"{W}/*cas_raw.json")),
               key=os.path.getmtime, reverse=True)
merged, errored = {}, {}
for p in paths:
    try:
        d = json.load(open(p, encoding="utf-8"))
    except Exception as e:
        print("skip", os.path.basename(p), e)
        continue
    n0 = len(merged)
    for k, v in d.items():
        if not isinstance(v, dict):
            continue
        if "error" in v:
            errored.setdefault(k, []).append(os.path.basename(p))
            continue
        merged.setdefault(k, v)
    print(f"  {os.path.basename(p):28s} 条目 {len(d):4d} → 新增 {len(merged) - n0:4d}")
json.dump(merged, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"[OK] {out_path} 合并后期刊 {len(merged)}（来自 {len(paths)} 个缓存文件）")
still = [k for k in errored if k not in merged]
if still:
    print(f"  ⚠️ 这些刊只存在于 error 条目（需重抓 {len(still)} 个）：{still[:8]}")
