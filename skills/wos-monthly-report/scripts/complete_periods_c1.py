#!/usr/bin/env python3
"""为所有期次补齐 c1_full.json：先确保 firstunit_pre / missing_addr 存在，再合成 c1_full。

用法: python3 complete_periods_c1.py [prefix ...]     # 默认处理全部门户期次
"""
import os
import subprocess
import sys

W = os.environ.get("WOS_WORKDIR", os.path.expanduser("~/wos-work"))
PY = "python3"
DEFAULT = ["mnnu_q1", "mnnu_q2", "mnnu_m01", "mnnu_m02", "mnnu_m03",
           "mnnu_jun", "mnnu_jul", "mnnu_aug"]
prefixes = sys.argv[1:] or DEFAULT


def run(desc, cmd, tail=2):
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=W)
    out = ((r.stdout or "") + (r.stderr or "")).strip().split("\n")
    print(f"  {desc}: " + " / ".join(x.strip() for x in out[-tail:] if x.strip())[:170])
    return out


for pre in prefixes:
    print("=" * 62)
    print(pre)
    if not os.path.exists(f"{W}/{pre}_firstunit_pre.json"):
        run("解析", [PY, f"{W}/monthly_analyze_generic.py", pre,
                     "MINNAN NORMAL UNIV", "ZHANGZHOU NORMAL UNIV"], 3)
    if not os.path.exists(f"{W}/{pre}_missing_addr.json"):
        run("补录全记录页", [PY, f"{W}/mnnu_missing_addr_generic.py", pre], 3)
    run("合成 c1_full", [PY, f"{W}/build_c1_full.py", pre], 4)
