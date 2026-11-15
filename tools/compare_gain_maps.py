"""Compare Capture One's spatial gain (from a probe render of a synthetic flat field) with Phocus's
(from flat_gain.py), by radius. Capture One's map needs no inversion: the probe render is camera RGB.

usage: python compare_gain_maps.py C1_PROBE_RENDER.tif PHOCUS_MAP.npz [--label text]
"""
import argparse
import os
import sys

import numpy as np
import tifffile

sys.path.insert(0, os.path.dirname(__file__))
from pairs import romm_decode  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("c1"); ap.add_argument("phocus"); ap.add_argument("--label", default="")
a = ap.parse_args()
pm = np.load(a.phocus)
b = int(pm["block"])
img = tifffile.imread(a.c1)[..., :3].astype(np.float64) / 65535
H, W = img.shape[:2]
nby, nbx = H // b, W // b
lin = romm_decode(img[: nby * b, : nbx * b].reshape(nby, b, nbx, b, 3).mean(axis=(1, 3)))
r = pm["radius"]
centre = lin[r < 0.05].mean(0)
c1 = np.log2(lin / centre)
ph = np.log2(np.clip(pm["gain"], 1e-6, None))
print(f"{a.label}  (stops vs centre; G = brightness, B-G = colour)")
print("   r    C1  G    B-G   R-G   |  Phocus G   B-G   R-G   |  diff G   B-G")
for lo in (0.2, 0.4, 0.6, 0.8, 0.9):
    m = (r >= lo - 0.025) & (r < lo + 0.025)
    if m.sum() < 5:
        continue
    c, p = c1[m].mean(0), ph[m].mean(0)
    print(f"  {lo:.1f}  {c[1]:+.3f} {c[2]-c[1]:+.3f} {c[0]-c[1]:+.3f}  |  {p[1]:+.3f} {p[2]-p[1]:+.3f} {p[0]-p[1]:+.3f}  |  {c[1]-p[1]:+.3f} {(c[2]-c[1])-(p[2]-p[1]):+.3f}")
