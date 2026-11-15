"""Side-by-side contact sheet: Phocus | Capture One + HNCS | Capture One default, one row per frame.

Every panel is drawn from per-block mean Lab on the same grid, so the three columns line up exactly
and each panel's number is the median dE00 against the Phocus panel in that row.

usage: python contact_sheet.py OUT.jpg [--width 300] \
         --row "label" PAIRS.npz BLOCK PHOCUS_LAB.npz HNCS.tif DEFAULT.tif [--row ...]
  PAIRS.npz      pairs.py output for the frame (gives the block grid and alignment)
  BLOCK          block size of that grid at the renders' scale (16 for half-size renders of a 32 px grid)
  PHOCUS_LAB.npz save_phocus_lab.py output for the Phocus export being matched
"""
import argparse
import os
import sys

import numpy as np
import tifffile
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(__file__))
from icc import de2000, lab_to_xyz  # noqa: E402
from render_lab import block_lab  # noqa: E402

BRADFORD_D50_D65 = np.array([[0.9555766, -0.0230393, 0.0631636], [-0.0282895, 1.0099416, 0.0210077], [0.0122982, -0.0204830, 1.3299098]])
XYZ_TO_SRGB = np.array([[3.2404542, -1.5371385, -0.4985314], [-0.9692660, 1.8760108, 0.0415560], [0.0556434, -0.2040259, 1.0572252]])


def lab_to_srgb8(lab):
    lin = lab_to_xyz(lab) @ BRADFORD_D50_D65.T @ XYZ_TO_SRGB.T
    lin = np.clip(lin, 0, 1)
    v = np.where(lin <= 0.0031308, 12.92 * lin, 1.055 * lin ** (1 / 2.4) - 0.055)
    return np.round(v * 255).astype(np.uint8)


def font(size, bold=False):
    for path, idx in (("/System/Library/Fonts/HelveticaNeue.ttc", 1 if bold else 0), ("/System/Library/Fonts/Helvetica.ttc", 1 if bold else 0)):
        try:
            return ImageFont.truetype(path, size, index=idx)
        except OSError:
            continue
    return ImageFont.load_default()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--width", type=int, default=300)
    ap.add_argument("--row", nargs=6, action="append", required=True, metavar=("LABEL", "PAIRS", "BLOCK", "PHOCUS", "HNCS", "DEFAULT"))
    args = ap.parse_args()

    W = args.width
    pad, head, cap = 12, 34, 22
    cols = ["Phocus (HNCS)", "Capture One + HNCS E3", "Capture One default"]
    rows = []
    for label, pairs, bs, ph, hncs, default in args.row:
        z = np.load(pairs)
        ref = np.load(ph)["lab"]
        nb = int(z["nblocks"])
        shape = tifffile.TiffFile(hncs).pages[0].shape[:2]
        nby = shape[0] // int(bs)
        nbx = nb // nby
        panels, scores = [ref], [None]
        valid = (z["dev_max"] < 0.97) & (np.load(ph)["ph_max"] < 0.995) & (ref[:, 0] > 2)
        for path in (hncs, default):
            lab = block_lab(path, pairs, tifffile.TiffFile(path).pages[0].shape[:2], bs=int(bs))
            panels.append(lab)
            scores.append(float(np.median(de2000(lab[valid], ref[valid]))))
        imgs = []
        for lab in panels:
            im = Image.fromarray(lab_to_srgb8(lab.reshape(nby, nbx, 3)))
            imgs.append(im.resize((W, round(W * nby / nbx)), Image.LANCZOS))
        rows.append((label, imgs, scores))

    H_rows = [r[1][0].height for r in rows]
    sheet_w = pad + 3 * (W + pad)
    sheet_h = head + sum(h + cap + pad for h in H_rows) + pad
    sheet = Image.new("RGB", (sheet_w, sheet_h), (24, 24, 24))
    d = ImageDraw.Draw(sheet)
    fb, fr = font(15, bold=True), font(13)
    for i, c in enumerate(cols):
        d.text((pad + i * (W + pad), 10), c, fill=(235, 235, 235), font=fb)
    y = head
    for (label, imgs, scores), h in zip(rows, H_rows):
        for i, im in enumerate(imgs):
            x = pad + i * (W + pad)
            sheet.paste(im, (x, y))
            text = label if i == 0 else f"median ΔE00 {scores[i]:.2f} vs Phocus"
            d.text((x, y + h + 4), text, fill=(200, 200, 200), font=fr)
        y += h + cap + pad
    sheet.save(args.out, quality=85, optimize=True, progressive=True)
    print(f"wrote {args.out} {sheet.size} {os.path.getsize(args.out) / 1024:.0f} KB")
    for label, _, scores in rows:
        print(f"  {label}: HNCS {scores[1]:.2f} | default {scores[2]:.2f}")


if __name__ == "__main__":
    main()
