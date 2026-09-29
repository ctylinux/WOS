#!/usr/bin/env python3
"""按既有简报 docx 的版式生成新一期简报（表 + 按学科纵向合并的贡献率饼图）。

月度简报=第一单位为本校 且 正式刊期(PD)落在统计期，与 7 月简报口径一致。

用法:
  python3 build_briefing_from_template.py \
      --template "2026年7月闽南师范大学Web of Science收录论文简报（带图）.docx" \
      --csv "闽南师范大学_2026年8月_WOS论文_含中科院分区.csv" \
      --period 2026-08 --month 2026年8月 \
      --pie-dir "$WOS_WORKDIR/月报图表/2026年8月_简报口径" \
      --out "2026年8月闽南师范大学Web of Science收录论文简报（带图）.docx"

版式要点（来自 7 月模板）：表 3 列=学科名称 | 论文数量 | 饼图；同一学科的若干分区行 + 汇总行，
第 3 列在该学科内**纵向合并**，只放一张饼图；最后一个数据行是"总计"。
"""
import argparse
import copy
import csv
import os
import re
from collections import Counter, OrderedDict

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches

ap = argparse.ArgumentParser()
ap.add_argument("--template", required=True)
ap.add_argument("--csv", required=True)
ap.add_argument("--period", required=True, help="统计期前缀，如 2026-08；季报可给多个，逗号分隔：2026-04,2026-05,2026-06")
ap.add_argument("--month", required=True, help="中文月，如 2026年8月")
ap.add_argument("--pie-dir", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--org", default="闽南师范大学")
a = ap.parse_args()


def q_label(row):
    q = (row["大类分区"] or "").strip()
    return f"{q}TOP" if (row["Top期刊"] or "").strip() == "是" else q


rows = list(csv.DictReader(open(a.csv, encoding="utf-8-sig")))
prefs = [x.strip() for x in a.period.replace(" ", ",").split(",") if x.strip()]
kept = [r for r in rows if r[f"{a.org}是否第一单位"] == "是"
        and any((r["正式出版时间"] or "").startswith(p) for p in prefs)]
groups = OrderedDict()
for r in kept:
    groups.setdefault(r["中科院大类学科"], []).append(r)
order = sorted(groups, key=lambda d: (-len(groups[d]), d))
print(f"简报口径 {len(kept)} 篇 / {len(order)} 学科：" +
      "、".join(f"{d}{len(groups[d])}" for d in order))

doc = Document(a.template)
tbl = doc.tables[0]
trs = tbl._tbl.tr_lst
header_tr, data_trs, total_tr = trs[0], trs[1:-1], trs[-1]
row_first, row_mid, row_sum = data_trs[0], data_trs[1], data_trs[2]   # 模板：分区首行/续行/汇总行
print(f"模板行数 {len(trs)}：首行模板={row_first is not None}, 总计行={total_tr is not None}")

for tr in data_trs:
    tbl._tbl.remove(tr)


def clone(tr):
    return copy.deepcopy(tr)


def set_cells(tr, label, count):
    cells = tr.findall("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tc")
    for tcs, val in ((cells[0], label), (cells[1], count)):
        ps = tcs.findall(".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p")
        if not ps:
            continue
        runs = ps[0].findall("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}r")
        if not runs:
            continue
        for extra in runs[1:]:
            ps[0].remove(extra)
        ts = runs[0].findall(".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t")
        if ts:
            ts[0].text = str(val)
            for extra in ts[1:]:
                runs[0].remove(extra)


new_trs = []
for disc in order:
    rs = groups[disc]
    cnt = Counter(q_label(r) for r in rs)
    labels = sorted(cnt, key=lambda k: (k[:1], k))          # 1区TOP → 1区 → 2区…（容忍空分区）
    for i, lab in enumerate(labels):
        tr = clone(row_first if i == 0 else row_mid)
        set_cells(tr, f"{disc}{lab}", cnt[lab])
        new_trs.append((tr, disc if i == 0 else None))
    tr = clone(row_sum)
    set_cells(tr, f"{disc}汇总", len(rs))
    new_trs.append((tr, None))

for tr, disc in new_trs:
    total_tr.addprevious(tr)
set_cells(total_tr, "总计", len(kept))

# 段落文案：标题 + 附注（沿用模板措辞，只换月份、机构与篇数）
paras = doc.paragraphs
old_month = re.search(r"(\d{4})年(\d{1,2})月份", paras[0].text)
paras[0].text = paras[0].text.replace(old_month.group(0), f"{a.month}份")
if a.org != "闽南师范大学":                     # 换机构（模板取自闽南师大）
    n_org = 0
    for p in paras:
        for r in p.runs:
            if "闽南师范大学" in r.text:
                r.text = r.text.replace("闽南师范大学", a.org)
                n_org += 1
    print(f"机构名替换：{n_org} 处 → {a.org}")
note = None
for p in paras:
    if p.text.startswith("附注"):
        note = p
        break
if note is not None:
    new_note = re.sub(r"\d{4}年\d{1,2}月", a.month, note.text)
    new_note = re.sub(r"共\d+篇", f"共{len(kept)}篇", new_note)
    for i, r in enumerate(note.runs):
        r.text = new_note if i == 0 else ""
    print("附注:", new_note[:120])

# 把饼图塞进每个学科合并列的首行单元格
tbl = doc.tables[0]
ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
group_rows = [r for r in tbl._tbl.tr_lst if r is not None]
# 按表内顺序重新扫描：找出每个学科首个分区行的索引
data_rows = tbl._tbl.tr_lst[1:-1]
idx = 0
for disc in order:
    labels = sorted(Counter(q_label(r) for r in groups[disc]), key=lambda k: (k[:1], k))
    first_tr = data_rows[idx]
    idx += len(labels)
    # 汇总行紧跟其后
    idx += 1
    # 取该行第 3 列（合并单元格）并替换图片
    from docx.table import _Cell
    tr_obj = [row for row in tbl.rows if row._tr is first_tr]
    if not tr_obj:
        print("  ⚠️ 定位首行失败:", disc)
        continue
    cell = tr_obj[0].cells[2]
    # 饼图文件名：学科名可能被映射（如「未被2025版收录」→「其他（未被2025版分区表收录）」）
    cands = [f"{a.month}_{disc}.png", f"{a.month}_其他（未被2025版分区表收录）.png"]
    pie = next((os.path.join(a.pie_dir, c) for c in cands if os.path.exists(os.path.join(a.pie_dir, c))), cands[0])
    for p in list(cell.paragraphs[1:]):
        p._p.getparent().remove(p._p)
    p0 = cell.paragraphs[0]
    for r in list(p0.runs):
        r._r.getparent().remove(r._r)
    p0.alignment = WD_ALIGN_PARAGRAPH.CENTER
    if os.path.exists(pie):
        p0.add_run().add_picture(pie, width=Inches(2.48))
        print(f"  ✅ {disc}: {os.path.basename(pie)}")
    else:
        print(f"  ⚠️ 缺饼图: {pie}")

doc.save(a.out)
print("[OK]", a.out, os.path.getsize(a.out))
