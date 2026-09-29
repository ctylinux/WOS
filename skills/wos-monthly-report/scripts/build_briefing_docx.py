#!/usr/bin/env python3
"""Build the 带图简报 docx (user's established format) from a monthly/quarterly report CSV.

The format replicates the July 2026 简报 exactly: title + subtitle, then a 3-column table
(学科名称 | 论文数量 | one 3D pie per subject group, vertically merged) with a yellow header
row, and a 附注 paragraph. Fonts: 宋体/Arial 9pt in the table, 14pt title, Microsoft YaHei UI
8.5pt 附注 (colour 110101).

COUNTING RULE (reverse-engineered from the user's own July file and verified to match its
总计 12): 第一单位 = the institution AND 正式刊期 (PD) falling inside the统计期. Papers whose
WOS PD sits in a later month (early access) are NOT counted, and neither are year-only PDs.

    python3 build_briefing_docx.py --csv 闽南师范大学_2026年1-3月_WOS论文_含中科院分区.csv \\
        --period 2026-01 2026-03 --org 闽南师范大学 --title "闽南师范大学2026年1-3月份(第一单位)WOS收录论文统计" \\
        --out "2026年1-3月闽南师范大学Web of Science收录论文简报（带图）.docx" \\
        --c1 mnnu_q1_c1.json --parsed mnnu_q1_parsed.json

COLLEGE_MAP translates the WOS English unit in C1 into the Chinese college name; it is
institution-specific and MUST be verified (see the skill's 阶段 8 notes) — unknown units fall
back to the raw English string, which is visible in the chart so it can be corrected later.
"""
import argparse
import csv
import json
import os
import re
import sys
from collections import Counter, OrderedDict

from docx import Document
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor, Twips

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pie3d import render_pie  # noqa: E402

# Verified for 闽南师范大学 (July briefing labels + 校内研究所一览表:
# 生态规划与景观设计研究所 and 闽台特色园林植物重点实验室 both sit in 生物科学与技术学院)
COLLEGE_MAP = {
    "Sch Math & Stat": "数学与统计学院",
    "Coll Phys & Informat Engn": "物理与信息工程学院",
    "Sch Phys & Informat Engn": "物理与信息工程学院",
    "Grad Sch Phys & Informat Engn": "物理与信息工程学院",
    "Sch Comp Sci": "计算机学院",
    "Coll Comp Sci": "计算机学院",
    "Sch Comp": "计算机学院",
    "Coll Chem Chem Engn & Environm": "化学化工与环境学院",
    "Key Lab Pollut Monitoring & Control": "化学化工与环境学院",
    "Sch Hist & Geog": "历史地理学院",
    "Sch Business": "商学院",
    "Sch Educ & Psychol": "教育与心理学院",
    "Coll Educ & Psychol Sci": "教育与心理学院",
    "Engn Technol Ctr Mushroom Ind": "生物科学与技术学院",
    "Biotechnol Res Inst": "生物科学与技术学院",
    "Inst Ecol Planning & Landscape Architecture": "生物科学与技术学院",
    "Fujian Prov Univ Key Lab Fujian & Taiwan Garden Pl": "生物科学与技术学院",
    "Fujian & Taiwan Characterist Fujian Coll & Univ": "生物科学与技术学院",
}

# pinyin order of CAS 大类学科 — the user's table orders groups by 篇数 desc then pinyin asc
PY_ORDER = ["材料科学", "地球科学", "法学", "工程技术", "管理学", "化学", "环境科学与生态学",
            "计算机科学", "教育学", "经济学", "军事学", "农林科学", "人文科学", "社会科学",
            "生物学", "数学", "物理与天体物理", "心理学", "药学", "医学", "艺术学", "综合性期刊"]
OTHERS = "其他（未被2025版分区表收录）"


def set_font(run, size, ascii_font, ea_font, color=None, bold=False):
    run.font.size = Pt(size)
    run.font.name = ascii_font
    run.font.bold = bold
    rpr = run._element.get_or_add_rPr()
    rf = rpr.find(qn('w:rFonts'))
    if rf is None:
        rf = OxmlElement('w:rFonts')
        rpr.append(rf)
    rf.set(qn('w:ascii'), ascii_font)
    rf.set(qn('w:hAnsi'), ascii_font)
    rf.set(qn('w:eastAsia'), ea_font)
    rf.set(qn('w:hint'), 'eastAsia')
    if color:
        run.font.color.rgb = color


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--csv', required=True)
    ap.add_argument('--period', nargs='+', required=True, help='YYYY-MM prefixes counted as 正式刊期')
    ap.add_argument('--org', required=True)
    ap.add_argument('--title', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--c1', help='C1 json {UT: "[Author] Inst, College, ..."} for the pie colleges')
    ap.add_argument('--parsed', help='parsed json with the records (篇名 -> UT)')
    ap.add_argument('--manual-college', help='json {UT: "中文学院"} for records without C1')
    ap.add_argument('--note-extra', default='')
    a = ap.parse_args()

    rows = list(csv.DictReader(open(a.csv, encoding='utf-8-sig')))
    fu_col = f'{a.org}是否第一单位'
    sel = [r for r in rows if r.get(fu_col) == '是' and (r.get('正式出版时间') or '')[:7] in a.period]
    print(f"简报口径: {len(sel)} 篇 (第一单位=是 共 {sum(1 for r in rows if r.get(fu_col) == '是')} 篇)")

    c1 = json.load(open(a.c1, encoding='utf-8')) if a.c1 else {}
    ut_by_title = {}
    if a.parsed:
        ut_by_title = {r['TI']: r['UT'] for r in json.load(open(a.parsed, encoding='utf-8'))['records']}
    manual_college = json.load(open(a.manual_college, encoding='utf-8')) if a.manual_college else {}

    def college_of(ut):
        if ut in manual_college:
            return manual_college[ut]
        m = re.match(r'^\[([^\]]*)\]\s*(.*?)(?:\s*;\s*\[|$)', c1.get(ut, '') or '')
        if not m:
            return '未识别单位'
        parts = [x.strip() for x in m.group(2).split(',')]
        return COLLEGE_MAP.get(parts[1] if len(parts) > 1 else parts[0],
                               parts[1] if len(parts) > 1 else parts[0])

    groups = OrderedDict()
    for r in sel:
        subj = r.get('中科院大类学科') or OTHERS
        if subj == '未被2025版收录':
            subj = OTHERS
        g = groups.setdefault(subj, {'rows': Counter(), 'colleges': Counter(), 'n': 0})
        g['n'] += 1
        g['rows'][(r.get('大类分区') or '—') + ('TOP' if r.get('Top期刊') == '是' else '')] += 1
        g['colleges'][college_of(ut_by_title.get(r.get('篇名', ''), ''))] += 1
    ordered = sorted(groups.items(),
                     key=lambda kv: (1 if kv[0] == OTHERS else 0, -kv[1]['n'],
                                     PY_ORDER.index(kv[0]) if kv[0] in PY_ORDER else 99))
    total = sum(g['n'] for _, g in ordered)
    print('学科顺序:', [(k, g['n']) for k, g in ordered], '总计', total)

    pie_dir = '/tmp/brief_pies'
    os.makedirs(pie_dir, exist_ok=True)
    pies = {}
    for name, g in ordered:
        items = sorted(g['colleges'].items(), key=lambda kv: (-kv[1], kv[0]))
        print(f'  pie {name}: {items}')
        pies[name] = render_pie(f"{pie_dir}/{abs(hash(name)) % 100000}.png", items)

    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Twips(11906), Twips(16838)
    sec.left_margin = sec.right_margin = Twips(1800)
    sec.top_margin = sec.bottom_margin = Twips(1440)
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_font(p.add_run(a.title), 14, 'Times New Roman', '宋体')
    p2 = doc.add_paragraph(); p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_font(p2.add_run('（按照2025年升级版中科院期刊分区表）'), 11, 'Times New Roman', '宋体')
    doc.add_paragraph()

    tbl = doc.add_table(rows=0, cols=3)
    tbl.style = 'Table Grid'
    tbl.autofit = False
    widths = [Twips(2900), Twips(1150), Twips(4256)]

    def style_cell(cell, text=None, fill=None):
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        if fill:
            shd = OxmlElement('w:shd')
            shd.set(qn('w:val'), 'clear'); shd.set(qn('w:color'), '000000'); shd.set(qn('w:fill'), fill)
            cell._tc.get_or_add_tcPr().append(shd)
        para = cell.paragraphs[0]
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        para.paragraph_format.space_before = Pt(0)
        para.paragraph_format.space_after = Pt(0)
        if text is not None:
            set_font(para.add_run(str(text)), 9, 'Arial', '宋体', RGBColor(0x33, 0x33, 0x33))

    def add_row(cells_text, fill=None):
        row = tbl.add_row()
        for cell, txt in zip(row.cells, cells_text):
            style_cell(cell, txt, fill)

    add_row(['学科名称', '论文数量', ''], fill='FFFF00')

    def qkey(q):
        if q == '—':
            return (99, 0)
        m = re.match(r'(\d)区(TOP)?', q)
        return (int(m.group(1)), 0 if m.group(2) else 1)

    for name, g in ordered:
        first = len(tbl.rows)
        for q in sorted(g['rows'], key=qkey):
            add_row([f'{name}{q}' if q != '—' else name, g['rows'][q], ''])
        add_row(['其他汇总' if name == OTHERS else f'{name}汇总', g['n'], ''])
        last = len(tbl.rows) - 1
        mc = tbl.cell(first, 2).merge(tbl.cell(last, 2))
        mc.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        mp = mc.paragraphs[0]
        mp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        mp.paragraph_format.space_before = Pt(0)
        mp.paragraph_format.space_after = Pt(0)
        mp.add_run().add_picture(pies[name], width=Inches(2.48))
    add_row(['总计', total, ''])
    for row in tbl.rows:
        for cell, wd in zip(row.cells, widths):
            try:
                cell.width = wd
            except Exception:
                pass

    period_txt = a.period[0][:4] + '年' + a.period[0][5:].lstrip('0') + '-' + \
        a.period[-1][5:].lstrip('0') + '月' if len(a.period) > 1 else \
        a.period[0][:4] + '年' + a.period[0][5:].lstrip('0') + '月'
    note = doc.add_paragraph()
    note.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    set_font(note.add_run(
        f'附注：本简报统计{period_txt}正式出版（正式刊期在{period_txt}）、且{a.org}为第一单位的'
        f'Web of Science收录论文，共{total}篇；期刊分区依据2025年升级版中科院期刊分区表；'
        f'表中饼图为各学科论文按第一单位所属学院的贡献率分布。{a.note_extra}'
        f'因Web of Science实时更新，数据为不完全统计，仅供参考。'),
        8.5, 'Microsoft YaHei UI', 'Microsoft YaHei UI', RGBColor(0x11, 0x01, 0x01))
    doc.save(a.out)
    print('saved', a.out, os.path.getsize(a.out))


if __name__ == '__main__':
    main()
