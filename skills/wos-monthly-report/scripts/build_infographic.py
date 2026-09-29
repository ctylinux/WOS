#!/usr/bin/env python3
"""月报流程新增步骤②：把月报结果生成"手绘思维导图"式信息图（HTML -> PNG）。

Usage:
  python3 build_infographic.py <report.csv> <c1.json> <parsed.json> <tag> <out.png> [--org 闽南师范大学]

数据全部取自月报本身（不新增口径）：原始条数、剔除数、正式发表、第一单位分布、
分区结构、Top期刊、学科×学院贡献率、第一作者非本校的合作单位。
风格：手绘纸张底纹 + 手写中文字体（ZCOOL KuaiLe / Ma Shan Zheng）+ 瓦楞手绘连线。
"""
import argparse
import csv
import json
import os
import re
import sys
from collections import Counter, OrderedDict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from college_pies import COLLEGE_MAP, MANUAL_COLLEGE, college_of, _norm, PY_ORDER, OTHERS  # noqa: E402

BIG = "'Ma Shan Zheng', 'ZCOOL KuaiLe', 'WenQuanYi Zen Hei', sans-serif"
HAND = "'ZCOOL KuaiLe', 'WenQuanYi Zen Hei', sans-serif"
BODY = "'WenQuanYi Zen Hei', 'ZCOOL KuaiLe', sans-serif"
PIE_COLORS = ["#0E9BD3", "#E57030", "#4CA52C", "#FFC000", "#A5A5A5", "#7030A0"]


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def collect(csv_path, c1_path, parsed_path, org):
    rows = list(csv.DictReader(open(csv_path, encoding="utf-8-sig")))
    c1 = json.load(open(c1_path, encoding="utf-8"))
    parsed = json.load(open(parsed_path, encoding="utf-8"))
    ut_by_norm = {_norm(r["TI"]): r["UT"] for r in parsed["records"]}
    fu = f"{org}是否第一单位"
    yes = [r for r in rows if r.get(fu) == "是"]
    no = [r for r in rows if r.get(fu) == "否"]

    groups = OrderedDict()
    for r in yes:
        sj = r.get("中科院大类学科") or OTHERS
        if sj == "未被2025版收录":
            sj = OTHERS
        groups.setdefault(sj, Counter())[college_of(r, c1, ut_by_norm)] += 1
    ordered = sorted(groups.items(), key=lambda kv: (1 if kv[0] == OTHERS else 0, -sum(kv[1].values()),
                                                     PY_ORDER.index(kv[0]) if kv[0] in PY_ORDER else 99))

    subj_rows = []
    for sj, cols in ordered:
        n = sum(cols.values())
        items = sorted(cols.items(), key=lambda kv: (-kv[1], kv[0]))
        subj_rows.append((sj, n, items))

    def inst_of(r):
        ut = ut_by_norm.get(_norm(r.get("篇名", "")), "")
        m = re.match(r"^\[([^\]]*)\]\s*(.*?)(?:\s*;\s*\[|$)", c1.get(ut, "") or "")
        return m.group(2).split(",")[0].strip() if m else "(缺C1)"

    partners = Counter(inst_of(r) for r in no)
    return {
        "csv": rows, "yes": yes, "no": no, "subj": subj_rows, "partners": partners,
        "raw": len(rows) + int(parsed.get("_dropped", 0)) if False else None,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv"); ap.add_argument("c1"); ap.add_argument("parsed")
    ap.add_argument("tag"); ap.add_argument("out_png")
    ap.add_argument("--org", default="闽南师范大学")
    ap.add_argument("--org-en", default="Minnan Normal Univ", help="WOS 检索字段值（用于⑤数据口径卡）")
    ap.add_argument("--raw", type=int, help="原始检索条数（默认=正式发表+剔除数）")
    ap.add_argument("--dropped", type=int, default=0, help="剔除的预印本/RC 条数")
    ap.add_argument("--outdir", default=".")
    a = ap.parse_args()

    d = collect(a.csv, a.c1, a.parsed, a.org)
    rows, yes, no = d["csv"], d["yes"], d["no"]
    formal = len(rows)
    raw = a.raw if a.raw else formal + a.dropped
    big = Counter((r.get("大类分区") or "未收录") for r in rows)
    top = sum(1 for r in rows if r.get("Top期刊") == "是")
    journals = len({r.get("期刊来源") for r in rows})
    fu_pct = 100.0 * len(yes) / formal if formal else 0

    # ---------- 学科分布卡片 ----------
    subj_html = []
    for sj, n, items in d["subj"]:
        segs = "".join(
            f"<span class='seg' style='width:{100*v/n:.2f}%;background:{PIE_COLORS[i % len(PIE_COLORS)]}'></span>"
            for i, (c, v) in enumerate(items))
        legend = " · ".join(f"{c} {100*v/n:.0f}%" for c, v in items[:3])
        subj_html.append(
            f"<div class='subj'><div class='subj-hd'><b>{esc(sj)}</b><i>{n}篇</i></div>"
            f"<div class='bar'>{segs}</div><div class='lg'>{esc(legend)}</div></div>")

    big_html = "".join(
        f"<div class='bigrow'><span class='bigtag'>{esc(k)}</span>"
        f"<span class='bigbar'><i style='width:{100*v/formal:.1f}%;background:"
        f"{'#0E9BD3' if k.startswith('1') else '#E57030' if k.startswith('2') else '#4CA52C' if k.startswith('3') else '#FFC000' if k.startswith('4') else '#A5A5A5'}'></i></span>"
        f"<b>{v}篇</b><s>{100*v/formal:.0f}%</s></div>"
        for k, v in sorted(big.items(), key=lambda kv: (kv[0] == "未收录", kv[0])))

    partners = "、".join(f"{k} {v}篇" for k, v in d["partners"].most_common(5)) or "无"

    partners_rows = "".join(
        f"<div class='pr'><span>{esc(k)}</span><b>{v}篇</b></div>"
        for k, v in d["partners"].most_common(5)) or "<div class='pr'>无</div>"

    html = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><style>
  * {{ box-sizing: border-box; }}
  body {{ margin:0; width:1600px; height:1520px; font-family:{BODY}; color:#2b2b2b; background:#fdfaf3;
    background-image: radial-gradient(#d9d2c0 1.1px, transparent 1.1px), radial-gradient(#e6e0d0 1px, transparent 1px);
    background-size: 26px 26px, 26px 26px; background-position: 0 0, 13px 13px; }}
  .title {{ position:absolute; left:56px; top:18px; font-family:{BIG}; font-size:46px; letter-spacing:2px; }}
  .sub {{ position:absolute; left:62px; top:78px; font-family:{BODY}; font-size:19px; color:#7a6a52; }}
  .card {{ position:absolute; background:#fffdf6; border:3px solid #2b2b2b; border-radius:16px 22px 18px 24px;
    box-shadow: 6px 7px 0 rgba(43,43,43,.16); padding:16px 18px; }}
  .card h3 {{ margin:0 0 10px; font-family:{HAND}; font-size:26px; letter-spacing:1px; }}
  .card h3 em {{ font-style:normal; font-size:18px; color:#8a7a60; margin-left:8px; }}
  .row {{ font-size:21px; line-height:1.66; }}
  .row b {{ font-size:24px; }}
  .k {{ color:#8a7a60; }}
  .hub {{ position:absolute; left:560px; top:54px; width:480px; height:300px; background:#fffdf6;
    border:4px solid #2b2b2b; border-radius:50% 46% 52% 48% / 46% 52% 46% 54%;
    box-shadow: 8px 9px 0 rgba(43,43,43,.18); text-align:center; padding-top:40px; }}
  .hub .t {{ font-family:{BIG}; font-size:27px; color:#7a6a52; }}
  .hub .n {{ font-family:{BIG}; font-size:60px; line-height:1.05; color:#0E9BD3;
    display:flex; justify-content:center; align-items:baseline; gap:8px; }}
  .hub .n span {{ font-size:34px; color:#2b2b2b; }}
  .hub .n2 {{ font-size:20px; margin-top:8px; }}
  .hub .h {{ font-size:18px; color:#8a7a60; margin-top:8px; }}
  .subj {{ margin:0 0 7px; }}
  .subj-hd {{ display:flex; justify-content:space-between; font-size:20px; }}
  .subj-hd i {{ font-style:normal; color:#8a7a60; }}
  .bar {{ display:flex; height:14px; border:2px solid #2b2b2b; border-radius:8px; overflow:hidden; margin:3px 0 2px; }}
  .seg {{ display:block; height:100%; }}
  .lg {{ font-size:15px; color:#7a6a52; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
  .grid {{ display:grid; grid-template-columns:1fr 1fr; gap:6px 30px; }}
  .bigrow {{ display:flex; align-items:center; gap:8px; font-size:19px; margin:9px 0; }}
  .bigtag {{ width:88px; }}
  .bigbar {{ flex:1; height:14px; border:2px solid #2b2b2b; border-radius:7px; overflow:hidden; background:#fff; }}
  .bigbar i {{ display:block; height:100%; }}
  .bigrow b {{ width:54px; text-align:right; white-space:nowrap; }}
  .bigrow s {{ text-decoration:none; width:50px; text-align:right; color:#8a7a60; font-size:17px; }}
  .pr {{ display:flex; justify-content:space-between; gap:10px; font-size:16px; line-height:1.5; }}
  .pr span {{ white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
  .pr b {{ white-space:nowrap; }} 
  .doodle {{ position:absolute; font-family:{HAND}; color:#c0392b; font-size:21px; }}
  .foot {{ position:absolute; left:56px; bottom:16px; font-size:16px; color:#7a6a52; }}
  .stamp {{ position:absolute; right:60px; bottom:14px; font-family:{HAND}; font-size:20px; color:#b03a2e;
    border:3px dashed #b03a2e; border-radius:12px; padding:6px 14px; transform:rotate(-3deg); }}
</style></head><body>
  <div class="title">{esc(a.org)} WOS 论文月报</div>
  <div class="sub">{esc(a.tag)}　·　手绘思维导图</div>

  <div class="hub">
    <div class="t">正式发表</div>
    <div class="n">{formal}<span> 篇</span></div>
    <div class="n2">本校为第一单位 <b style="color:#4CA52C">{len(yes)}</b> 篇 · 合作/挂名 {len(no)} 篇</div>
    <div class="h">原始检索 {raw} 条 · 剔除非期刊 {a.dropped} 条</div>
  </div>

  <svg width="1600" height="1520" style="position:absolute;left:0;top:0;pointer-events:none">
    <g fill="none" stroke="#2b2b2b" stroke-width="3.4" stroke-linecap="round">
      <path d="M566 170 C 480 168, 420 175, 350 190"/><path d="M570 178 C 486 178, 426 184, 356 199" opacity=".42"/>
      <path d="M1034 170 C 1120 168, 1180 175, 1250 190"/><path d="M1030 178 C 1114 178, 1174 184, 1244 199" opacity=".42"/>
      <path d="M566 250 C 480 260, 420 290, 350 330"/><path d="M570 258 C 486 268, 426 296, 356 338" opacity=".42"/>
      <path d="M1034 250 C 1120 260, 1180 290, 1250 330"/><path d="M1030 258 C 1114 268, 1174 296, 1244 338" opacity=".42"/>
      <path d="M566 330 C 480 400, 420 480, 350 560"/><path d="M570 338 C 486 406, 426 486, 356 568" opacity=".42"/>
      <path d="M800 356 C 800 560, 800 720, 800 892"/><path d="M808 356 C 808 560, 808 720, 808 892" opacity=".42"/>
    </g>
  </svg>

  <div class="card" style="left:50px;top:100px;width:380px;height:230px">
    <h3>① 论文规模</h3>
    <div class="row">
      <div><span class="k">原始检索</span> <b>{raw}</b> 条</div>
      <div><span class="k">剔除非期刊</span> {a.dropped} 条</div>
      <div><span class="k">正式发表</span> <b>{formal}</b> 篇</div>
      <div><span class="k">第一单位=本校</span> <b>{len(yes)}</b> 篇（{fu_pct:.0f}%）</div>
    </div>
  </div>

  <div class="card" style="left:1170px;top:100px;width:380px;height:330px">
    <h3>② 分区结构<em>2025升级版</em></h3>
    <div class="row">{big_html}</div>
  </div>

  <div class="card" style="left:50px;top:370px;width:380px;height:280px">
    <h3>③ 主要合作单位</h3>
    <div class="row" style="font-size:18px">
      <div class="k" style="margin-bottom:6px">非第一单位 {len(no)} 篇的第一作者单位</div>
      {partners_rows}
    </div>
  </div>

  <div class="card" style="left:1170px;top:470px;width:380px;height:200px">
    <h3>④ 高影响力</h3>
    <div class="row">
      <div><span class="k">Top 期刊</span> <b>{top}</b> 篇（{100*top/formal:.0f}%）</div>
      <div><span class="k">1区</span> {big.get('1区', 0)} 篇 · <span class="k">2区</span> {big.get('2区', 0)} 篇</div>
      <div><span class="k">来源期刊</span> {journals} 种</div>
    </div>
  </div>

  <div class="card" style="left:50px;top:650px;width:380px;height:230px">
    <h3>⑤ 数据口径</h3>
    <div class="row" style="font-size:17px;line-height:1.66">
      <div>检索：WOS 所有数据库</div>
      <div>字段：Address = "{esc(a.org_en)}"</div>
      <div>时间：Publication Date {esc(a.tag)}</div>
      <div>分区：中科院 2025年3月升级版</div>
      <div>第一单位：C1 地址第一组</div>
      <div>日期已归一化为 YYYY-MM-DD</div>
    </div>
  </div>

  <div class="card" style="left:50px;top:900px;width:1500px;height:540px">
    <h3>⑥ 学科分布与学院贡献率<em>{len(yes)} 篇（本校第一单位）</em></h3>
    <div class="grid">{''.join(subj_html)}</div>
  </div>

  <div class="foot">数据来源：Web of Science · 分区：中科院文献情报中心期刊分区表（2025年3月升级版）· 因 WOS 实时更新，数据为不完全统计，仅供参考</div>
  <div class="stamp">{esc(a.org)} · 科研月报</div>
</body></html>"""

    os.makedirs(a.outdir, exist_ok=True)
    html_path = os.path.join(a.outdir, f"{a.tag}_手绘信息图.html")
    open(html_path, "w", encoding="utf-8").write(html)

    # ---- render ----
    _libs = os.environ.get("WOS_CHROME_LIBS", "")
if _libs:
    os.environ["LD_LIBRARY_PATH"] = _libs + ":" + os.environ.get("LD_LIBRARY_PATH", "")
    CHROMIUM = os.environ.get("WOS_CHROMIUM") or os.path.expanduser("~/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome")
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROMIUM, headless=True, args=["--no-sandbox"])
        ctx = b.new_context(viewport={"width": 1600, "height": 1520}, device_scale_factor=2)
        pg = ctx.new_page()
        pg.goto("file://" + os.path.abspath(html_path), wait_until="load")
        pg.wait_for_timeout(1200)
        pg.screenshot(path=a.out_png, full_page=True)
        b.close()
    print("[OK]", a.out_png, os.path.getsize(a.out_png))
    print("[OK]", html_path)


if __name__ == "__main__":
    main()
