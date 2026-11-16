"""Side-by-side contact sheet from finished renders: one row per frame, the Phocus export first and
Capture One renders after it, each labelled with its median dE00 against the Phocus panel.

Renders are aligned to the Phocus export (score_render.py's alignment), cropped to the common area and
downscaled; the number is score_render.py's whole-frame median (clipped and busiest blocks left out).

usage: python contact_sheet.py OUT.jpg [--width 300] [--cols "Phocus|Capture One + HNCS|Capture One default"]
         [--footer "text"] --row LABEL PHOCUS.tif RENDER.tif [RENDER.tif ...] [--row ...]
  PHOCUS.tif: 16-bit ProPhoto export; RENDER.tif: Capture One 16-bit ROMM RGB at the same scale.
"""
import argparse
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from icc import de2000  # noqa: E402
from pairs import PROPHOTO_M, load, phocus_decode, romm_decode  # noqa: E402
from score_render import align, block_lab  # noqa: E402

BRADFORD_D50_D65 = np.array([[0.9555766, -0.0230393, 0.0631636], [-0.0282895, 1.0099416, 0.0210077], [0.0122982, -0.0204830, 1.3299098]])
XYZ_TO_SRGB = np.array([[3.2404542, -1.5371385, -0.4985314], [-0.9692660, 1.8760108, 0.0415560], [0.0556434, -0.2040259, 1.0572252]])


def font(size, bold=False):
    for path in ("/System/Library/Fonts/HelveticaNeue.ttc", "/System/Library/Fonts/Helvetica.ttc"):
        try:
            return ImageFont.truetype(path, size, index=1 if bold else 0)
        except OSError:
            continue
    return ImageFont.load_default()


def panel(img, decode, width):
    H, W = img.shape[:2]
    f = max(1, W // width)
    h2, w2 = H // f * f, W // f * f
    lin = decode(img[:h2, :w2].astype(np.float32) / 65535).reshape(h2 // f, f, w2 // f, f, 3).mean(axis=(1, 3))
    rgb = np.clip(lin @ (XYZ_TO_SRGB @ BRADFORD_D50_D65 @ PROPHOTO_M).T.astype(np.float32), 0, 1)
    v = np.where(rgb <= 0.0031308, 12.92 * rgb, 1.055 * rgb ** (1 / 2.4) - 0.055)
    im = Image.fromarray((v * 255 + 0.5).astype(np.uint8))
    return im.resize((width, round(im.size[1] * width / im.size[0])), Image.LANCZOS)


def score(a, b, bs=32):
    la, _, ma = block_lab(a, romm_decode, bs)
    lb, busy, mb = block_lab(b, phocus_decode, bs)
    ok = (lb[:, 0] > 3) & (lb[:, 0] < 97) & (la[:, 0] < 97) & (mb < 0.99) & (ma < 0.99)
    ok &= busy < np.percentile(busy[ok], 70)
    return float(np.median(de2000(la[ok], lb[ok])))


ap = argparse.ArgumentParser()
ap.add_argument("out")
ap.add_argument("--width", type=int, default=300)
ap.add_argument("--cols", default="Phocus|Capture One + HNCS|Capture One default")
ap.add_argument("--footer", default="")
ap.add_argument("--row", nargs="+", action="append", required=True, metavar="LABEL PHOCUS RENDER")
a = ap.parse_args()
cols = a.cols.split("|")
rows = []
for spec in a.row:
    label, ph_path, renders = spec[0], spec[1], spec[2:]
    ph = load(ph_path)
    cells, crop = [], None
    aligned = []
    for r in renders:
        c1 = load(r)
        (sa, sb), _ = align(c1, ph)
        aligned.append((c1[sa], sb))
    # common Phocus crop over all renders
    y0 = max(sb[0].start for _, sb in aligned); y1 = min(sb[0].stop for _, sb in aligned)
    x0 = max(sb[1].start for _, sb in aligned); x1 = min(sb[1].stop for _, sb in aligned)
    P = ph[y0:y1, x0:x1]
    cells.append((panel(P, phocus_decode, a.width), None))
    for (A, sb) in aligned:
        A = A[y0 - sb[0].start: y1 - sb[0].start, x0 - sb[1].start: x1 - sb[1].start]
        cells.append((panel(A, romm_decode, a.width), score(A, P)))
    rows.append((label, cells))
    print(label, ["%.2f" % c[1] for c in cells[1:]], flush=True)

pad, head, lab_h = 12, 34, 22
ncol = len(cols)
row_h = [max(c[0].size[1] for c in cells) for _, cells in rows]
W = pad + ncol * (a.width + pad)
H = head + sum(lab_h + h + pad for h in row_h) + (30 if a.footer else 8)
sheet = Image.new("RGB", (W, H), (28, 28, 28))
d = ImageDraw.Draw(sheet)
fb, fr, fs = font(15, True), font(13), font(12)
for i, c in enumerate(cols):
    d.text((pad + i * (a.width + pad), 10), c, fill=(235, 235, 235), font=fb)
y = head
for (label, cells), h in zip(rows, row_h):
    d.text((pad, y + 3), label, fill=(190, 190, 190), font=fr)
    y += lab_h
    for i, (im, sc) in enumerate(cells):
        x = pad + i * (a.width + pad)
        sheet.paste(im, (x, y))
        if sc is not None:
            t = f"ΔE00 {sc:.2f}"
            tw = d.textlength(t, font=fs)
            d.rectangle([x + a.width - tw - 12, y + 6, x + a.width - 4, y + 24], fill=(0, 0, 0))
            d.text((x + a.width - tw - 8, y + 8), t, fill=(255, 255, 255), font=fs)
    y += h + pad
if a.footer:
    d.text((pad, H - 24), a.footer, fill=(150, 150, 150), font=fs)
sheet.save(a.out, quality=88)
print(f"wrote {a.out} ({W}x{H})")
