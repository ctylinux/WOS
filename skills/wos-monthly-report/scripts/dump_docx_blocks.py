#!/usr/bin/env python3
"""Dump body block order of a .docx: paragraphs vs tables, with images per block."""
import sys
import zipfile

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

path = sys.argv[1]
d = Document(path)
body = d.element.body
ti = 0
pi = 0
media = {}
z = zipfile.ZipFile(path)
for name in z.namelist():
    if name.startswith("word/media/"):
        media[name.split("/")[-1]] = z.getinfo(name).file_size

for child in body.iterchildren():
    tag = child.tag.split("}")[-1]
    if tag == "p":
        p = Paragraph(child, d)
        imgs = [n for n in __import__("re").findall(r'r:embed="([^"]+)"', child.xml)]
        has_img = "graphicData" in child.xml
        print(f"[P{pi}] align={p.alignment} text={p.text.strip()[:60]!r}"
              f"{' IMG' if has_img else ''} {imgs}")
        pi += 1
    elif tag == "tbl":
        t = Table(child, d)
        print(f"[T{ti}] {len(t.rows)} 行 × {len(t.columns)} 列")
        for ri, row in enumerate(t.rows):
            cells = []
            for c in row.cells:
                imgs = __import__("re").findall(r'r:embed="([^"]+)"', c._tc.xml)
                txt = c.text.strip().replace("\n", " ")
                mark = f"<IMG {len(imgs)}>" if imgs else ""
                cells.append(f"{txt[:20]}{mark}")
            print(f"     r{ri}: " + " | ".join(cells))
        ti += 1
    elif tag == "sectPr":
        print("[SECTPR]")
print("media:", media)
