#!/usr/bin/env python3
"""月报流程新增步骤①：按学科生成"各学院贡献率"饼图 + 汇总拼图。

Usage:
  python3 college_pies.py <report.csv> <c1.json> <parsed.json> <out_dir> <tag> [--period 2026-06]

- 数据 = 报告中"第一单位=本校"的记录（给 --period 时再限定正式刊期在该期，与简报饼图口径一致）
- 输出 = 每学科一张 3D 饼图 PNG + 一张 _汇总.png（网格拼图，含学科标题与篇数）+ 一张 _数据.csv
"""
import argparse
import csv
import json
import os
import re
import sys
from collections import Counter, OrderedDict

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pie3d import render_pie, FONT  # noqa: E402

COLLEGE_MAP = {
    "Sch Math & Stat": "数学与统计学院",
    "Coll Phys & Informat Engn": "物理与信息工程学院",
    "Sch Phys & Informat Engn": "物理与信息工程学院",
    "Grad Sch Phys & Informat Engn": "物理与信息工程学院",
    "Sch Comp Sci": "计算机学院",
    "Coll Comp Sci": "计算机学院",
    "Coll Comp": "计算机学院",
    "Sch Comp": "计算机学院",
    "Coll Chem Chem Engn & Environm": "化学化工与环境学院",
    "Coll Chem Chem Engn & Environm Sci": "化学化工与环境学院",
    "Coll Chem & Chem Engn & Environm": "化学化工与环境学院",
    "Sch Chem Chem Engn & Environm": "化学化工与环境学院",
    "Key Lab Pollut Monitoring & Control": "化学化工与环境学院",
    "Key Lab Pollut Monitoring & Contr": "化学化工与环境学院",
    "Fujian Prov Univ Key Lab Pollut Monitoring & Contr": "化学化工与环境学院",
    "Fujian Prov Key Lab Modern Analyt Sci & Separat Te": "化学化工与环境学院",
    "Dept Chem & Environm Sci": "化学化工与环境学院",
    "Dept Chem Chem Engn & Environm": "化学化工与环境学院",
    "Fujian Prov Univ": "化学化工与环境学院",
    # 粒计算及其应用福建省重点实验室 / 数据科学与智能应用重点实验室 -> 计算机学院
    # (依据闽南师范大学计算机学院官网"本院简介"：学院拥有"粒计算及其应用"福建省重点实验室)
    "Fujian Key Lab Granular Comp & Applicat": "计算机学院",
    "Key Lab Granular Comp & Applicat": "计算机学院",
    "Key Lab Data Sci & Intelligence Applicat": "计算机学院",
    "Sch Hist & Geog": "历史地理学院",
    "Sch Business": "商学院",
    "Sch Educ & Psychol": "教育与心理学院",
    "Coll Educ & Psychol Sci": "教育与心理学院",
    "Sch Journalism & Commun": "新闻传播学院",
    "Inst Phys Educ": "体育学院",
    "Sch Biol Sci & Biotechnol": "生物科学与技术学院",
    "Engn Technol Ctr Mushroom Ind": "生物科学与技术学院",
    "Biotechnol Res Inst": "生物科学与技术学院",
    "Inst Ecol Planning & Landscape Architecture": "生物科学与技术学院",
    "Fujian Prov Univ Key Lab Fujian & Taiwan Garden Pl": "生物科学与技术学院",
    "Fujian & Taiwan Characterist Fujian Coll & Univ": "生物科学与技术学院",
}
MANUAL_COLLEGE = {
    "MEDLINE:41830277": "化学化工与环境学院",   # 环境科学（1-3月）
    "MEDLINE:42286191": "教育与心理学院",       # 应用心理学研究所 / 认知与人格重点实验室
    "MEDLINE:42277863": "教育与心理学院",       # School of Education and Psychology
    "MEDLINE:42358148": "化学化工与环境学院",   # 生理学报（第一单位为福建师大，仅备查）
}

# 机构可替换：设 COLLEGE_MAP_JSON=<json> 即可覆盖/补充上面的映射（其他高校复用本脚本时用）
# 文件格式: {"college_map": {"WOS 写法": "学院名"}, "manual_college": {"UT": "学院名"}}
_EXTRA_MAP = os.environ.get("COLLEGE_MAP_JSON")
if _EXTRA_MAP and os.path.exists(_EXTRA_MAP):
    _extra = json.load(open(_EXTRA_MAP, encoding="utf-8"))
    COLLEGE_MAP.update(_extra.get("college_map", {}))
    MANUAL_COLLEGE.update(_extra.get("manual_college", {}))
    print(f"[college-map] 已叠加 {_EXTRA_MAP}：college {len(_extra.get('college_map', {}))} 条 / "
          f"manual {len(_extra.get('manual_college', {}))} 条")
PY_ORDER = ["材料科学", "地球科学", "法学", "工程技术", "管理学", "化学", "环境科学与生态学",
            "计算机科学", "教育学", "经济学", "军事学", "农林科学", "人文科学", "社会科学",
            "生物学", "数学", "物理与天体物理", "心理学", "药学", "医学", "艺术学", "综合性期刊"]
OTHERS = "其他（未被2025版分区表收录）"
ADDR_ONLY = "未标注二级单位"


def _norm(t):
    """Normalise a title for matching (CSV round-trips can mangle quotes/spacing)."""
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", (t or "").lower())


def college_of(r, c1, ut_by_title):
    ut = ut_by_title.get(_norm(r["篇名"]), "")
    if ut in MANUAL_COLLEGE:
        return MANUAL_COLLEGE[ut]
    m = re.match(r"^\[([^\]]*)\]\s*(.*?)(?:\s*;\s*\[|$)", c1.get(ut, "") or "")
    if not m:
        return "未识别单位"
    parts = [x.strip() for x in m.group(2).split(",")]
    raw = parts[1] if len(parts) > 1 else parts[0]
    if re.match(r"^\d+\s+\w", raw) or re.match(r"^[A-Z][a-z]+ \d{5}", raw) or re.match(r"^.+\d{5}$", raw):
        return ADDR_ONLY
    if raw in COLLEGE_MAP:
        return COLLEGE_MAP[raw]
    # 不是二级单位的写法（城市名、国家、机构名残留等）→ 归入"未标注二级单位"，不要当成学院
    if not re.search(r"Sch |Coll |Dept |Inst |Key Lab|Ctr |Acad|Lab|Grp|Hosp|Stn|Univ|Bureau", raw):
        return ADDR_ONLY
    return raw


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("c1")
    ap.add_argument("parsed")
    ap.add_argument("outdir")
    ap.add_argument("tag")
    ap.add_argument("--org", default="闽南师范大学")
    ap.add_argument("--period", nargs="+", help="限定正式刊期前缀，如 --period 2026-06")
    a = ap.parse_args()

    rows = list(csv.DictReader(open(a.csv, encoding="utf-8-sig")))
    fu = f"{a.org}是否第一单位"
    sel = [r for r in rows if r.get(fu) == "是"]
    if a.period:
        sel = [r for r in sel if (r.get("正式出版时间") or "")[:7] in a.period]
    c1 = json.load(open(a.c1, encoding="utf-8"))
    ut_by_title = {_norm(r["TI"]): r["UT"] for r in json.load(open(a.parsed, encoding="utf-8"))["records"]}

    groups = OrderedDict()
    for r in sel:
        sj = r.get("中科院大类学科") or OTHERS
        if sj == "未被2025版收录":
            sj = OTHERS
        groups.setdefault(sj, Counter())[college_of(r, c1, ut_by_title)] += 1
    ordered = sorted(groups.items(), key=lambda kv: (1 if kv[0] == OTHERS else 0, -sum(kv[1].values()),
                                                     PY_ORDER.index(kv[0]) if kv[0] in PY_ORDER else 99))
    total = sum(sum(c.values()) for _, c in ordered)
    print(f"[{a.tag}] 纳入 {total} 篇 / {len(ordered)} 个学科")

    os.makedirs(a.outdir, exist_ok=True)
    data_rows = []
    pies = []
    for sj, cols in ordered:
        items = sorted(cols.items(), key=lambda kv: (-kv[1], kv[0]))
        n = sum(cols.values())
        path = os.path.join(a.outdir, f"{a.tag}_{sj}.png")
        render_pie(path, items)
        pies.append((sj, n, path))
        print(f"   {sj}（{n}篇）: " + "；".join(f"{c} {v}篇({100*v/n:.0f}%)" for c, v in items))
        for c, v in items:
            data_rows.append([sj, n, c, v, f"{100*v/n:.1f}%"])
    with open(os.path.join(a.outdir, f"{a.tag}_学院贡献率数据.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["学科", "学科论文数", "第一作者单位（学院）", "论文数", "占该学科比例"])
        w.writerows(data_rows)

    # ---- contact sheet ----
    cols_n = 3
    cell_w, cell_h, title_h = 640, 470, 46
    rows_n = (len(pies) + cols_n - 1) // cols_n
    sheet = Image.new("RGB", (cols_n * cell_w + 40, rows_n * cell_h + 40 + 70), "white")
    d = ImageDraw.Draw(sheet)
    try:
        tf = ImageFont.truetype(FONT, 34)
        sf = ImageFont.truetype(FONT, 26)
        bf = ImageFont.truetype(FONT, 40)
    except Exception:
        tf = sf = bf = ImageFont.load_default()
    d.text((40, 22), f"{a.org} WOS论文月报 · 各学院对学科贡献率（{a.tag}，共{total}篇）", font=bf, fill=(31, 78, 121))
    for i, (sj, n, path) in enumerate(pies):
        cx = 20 + (i % cols_n) * cell_w
        cy = 90 + (i // cols_n) * cell_h
        d.rectangle([cx + 6, cy + 6, cx + cell_w - 6, cy + cell_h - 6], outline=(200, 205, 210), width=2)
        d.text((cx + 22, cy + 14), f"{sj}  {n}篇", font=tf, fill=(31, 78, 121))
        im = Image.open(path).convert("RGB")
        scale = min((cell_w - 44) / im.width, (cell_h - title_h - 24) / im.height)
        im = im.resize((int(im.width * scale), int(im.height * scale)), Image.LANCZOS)
        sheet.paste(im, (cx + (cell_w - im.width) // 2, cy + title_h + 10))
    out_sheet = os.path.join(a.outdir, f"{a.tag}_学科贡献率_汇总.png")
    sheet.save(out_sheet)
    print("[OK]", out_sheet)


if __name__ == "__main__":
    main()
