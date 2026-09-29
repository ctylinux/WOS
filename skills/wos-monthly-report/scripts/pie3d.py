#!/usr/bin/env python3
"""3D pie renderer matching the user's 简报 chart style (measured from the July 2026 file).

Style facts measured from the shipped charts: canvas aspect 1.535 (Word displays the image at
2.48 x 1.62 in), top colours #0E9BD3 / #E57030 / #4CA52C, 3D side band = top x 0.56, white 2px
separators, slice labels in #404040 (college name on line 1, percentage on line 2), no title,
no legend. Slices start at 12 o'clock and run clockwise (Excel convention).

Canvas is 1240x808 (same 1.535 ratio, pie drawn at the July pixel size) so that pies with 3-4
colleges have room for every label; labels are placed on the bisector and nudged around the
ring until the text block clears the extruded silhouette, the canvas edge and the other labels.

    from pie3d import render_pie
    render_pie('/tmp/p.png', [('数学与统计学院', 3), ('计算机学院', 1)])
"""
import os
import math

from PIL import Image, ImageDraw, ImageFont

FONT = os.environ.get("WOS_FONT", "") or os.path.expanduser("~/.local/share/fonts/wqy-zenhei.ttc")  # WenQuanYi Zen Hei (CJK, no sudo needed)
TOP_COLORS = [(14, 155, 211), (229, 112, 48), (76, 165, 44), (255, 192, 0), (165, 165, 165), (112, 48, 160)]
TEXT_COLOR = (64, 64, 64)
SS = 3  # supersample factor
W, H = 1240, 808
CX, CY, RX, RY, DEPTH = 620, 355, 253, 160, 101


def _side(c):
    return tuple(int(v * 0.56) for v in c)


def render_pie(path, items, font_size=38):
    """items: [(label, value)] — rendered to path (PNG)."""
    img = Image.new("RGB", (W * SS, H * SS), "white")
    d = ImageDraw.Draw(img)
    total = sum(v for _, v in items) or 1
    n = len(items)
    slices = []
    a = 270.0
    for i, (label, v) in enumerate(items):
        sweep = 360.0 * v / total
        slices.append((label, v, a, a + sweep, TOP_COLORS[i % len(TOP_COLORS)]))
        a += sweep

    bbox = [(CX - RX) * SS, (CY - RY) * SS, (CX + RX) * SS, (CY + RY) * SS]

    if n > 1:
        # extruded side walls: only the parts of each slice arc in the FRONT half (y >= CY).
        # Angles start at 270 and wrap past 360, so walk the arc and keep contiguous runs.
        for label, v, a0, a1, col in slices:
            run = []
            step = max(0.5, (a1 - a0) / 180.0)
            t = a0
            while t <= a1 + 1e-9:
                x = CX + RX * math.cos(math.radians(t))
                y = CY + RY * math.sin(math.radians(t))
                if y >= CY - 0.5:
                    run.append((x, y))
                else:
                    if len(run) >= 2:
                        d.polygon([(px * SS, py * SS) for px, py in run] +
                                  [(px * SS, (py + DEPTH) * SS) for px, py in reversed(run)],
                                  fill=_side(col))
                    run = []
                t += step
            if len(run) >= 2:
                d.polygon([(px * SS, py * SS) for px, py in run] +
                          [(px * SS, (py + DEPTH) * SS) for px, py in reversed(run)],
                          fill=_side(col))
        for label, v, a0, a1, col in slices:
            d.pieslice(bbox, a0, a1, fill=col, outline="white", width=max(1, int(2 * SS)))
    else:
        pts = [(CX + RX * math.cos(math.radians(t)), CY + RY * math.sin(math.radians(t)))
               for t in range(0, 181, 2)]
        d.polygon([(x * SS, y * SS) for x, y in pts] +
                  [(x * SS, (y + DEPTH) * SS) for x, y in reversed(pts)], fill=_side(TOP_COLORS[0]))
        d.ellipse(bbox, fill=TOP_COLORS[0], outline="white", width=max(1, int(2 * SS)))

    try:
        font = ImageFont.truetype(FONT, font_size * SS)
    except Exception:
        font = ImageFont.load_default()

    sil_cy, sil_ry = CY + DEPTH / 2.0, RY + DEPTH / 2.0

    def hits_pie(x0, y0, x1, y1):
        for gx in range(5):
            for gy in range(5):
                x = x0 + (x1 - x0) * gx / 4.0
                y = y0 + (y1 - y0) * gy / 4.0
                if ((x - CX) / RX) ** 2 + ((y - sil_cy) / sil_ry) ** 2 < 1.0:
                    return True
        return False

    placed = []
    for label, v, a0, a1, col in slices:
        pct = 100.0 * v / total
        lines = [label, f"{pct:.0f}%"]
        bw = [font.getbbox(t)[2] - font.getbbox(t)[0] for t in lines]
        block_w = max(w / SS for w in bw) + 4
        block_h = 2.0 * (font_size + 4)
        base = (a0 + a1) / 2.0
        if n == 1:
            candidates = [90.0]
        else:
            offs = []
            for k in range(0, 181, 10):
                offs.append(k)
                if k:
                    offs.append(-k)
            candidates = [base + d for d in offs]
        chosen = None
        for ang in candidates:
            rad = math.radians(ang)
            lx = CX + math.cos(rad) * (RX + block_w / 2 + 14)
            ly = sil_cy + math.sin(rad) * (sil_ry + block_h / 2 + 14)
            x0 = min(max(lx - block_w / 2, 6), W - block_w - 6)
            y0 = min(max(ly - block_h / 2, 6), H - block_h - 6)
            if hits_pie(x0, y0, x0 + block_w, y0 + block_h):
                continue
            if any(not (x0 + block_w + 8 < px0 or px0 + pw + 8 < x0 or
                        y0 + block_h + 6 < py0 or py0 + ph + 6 < y0)
                   for px0, py0, pw, ph in placed):
                continue
            chosen = (x0, y0)
            break
        if chosen is None:
            rad = math.radians(base)
            lx = CX + math.cos(rad) * (RX + block_w / 2 + 14)
            ly = sil_cy + math.sin(rad) * (sil_ry + block_h / 2 + 14)
            chosen = (min(max(lx - block_w / 2, 6), W - block_w - 6),
                      min(max(ly - block_h / 2, 6), H - block_h - 6))
        x0, y0 = chosen
        placed.append((x0, y0, block_w, block_h))
        ty = y0 * SS
        for t, wd in zip(lines, bw):
            d.text(((x0 + (block_w - wd / SS) / 2) * SS, ty), t, font=font, fill=TEXT_COLOR)
            ty += (font_size + 4) * SS

    Image.open  # noqa: B018  (keeps PIL import used if refactored)
    img.resize((W, H), Image.LANCZOS).save(path)
    return path
