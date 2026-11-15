"""Measure how much Phocus brightens frame edges (lens corrections off) for one lens.

Compares Phocus Lab with a centre-calibrated LUT's prediction, converts the lightness gap to
stops via the LUT's neutral tone slope, and fits lift(r) = c2*r^2 + c4*r^4 per frame and pooled
(r = distance from centre / half-diagonal). Feed the pooled c2,c4 to pairs.py --lift.

usage: python edge_lift.py LUT.npz PAIRS_DIR RAW_DIR FRAME [FRAME ...]
       (FRAME = raw file stem, e.g. B0000623; RAW_DIR is only used to read focal length and aperture)
"""
import os
import subprocess
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from fit import load_frame, predict  # noqa: E402

LUT, PAIRS, RAW = sys.argv[1], sys.argv[2], sys.argv[3]
FR = sys.argv[4:]
lut = np.load(LUT)["lut"]
x = np.linspace(-12, 0, 2401)
dev = (2.0 ** x) ** (1 / 1.8)
Ln = predict(lut, np.stack([dev] * 3, -1))[:, 0]
slope = np.gradient(Ln, x)


def md(k, key):
    out = subprocess.run(["mdls", "-raw", "-name", key, os.path.join(RAW, k + ".3FR")], capture_output=True, text=True).stdout
    try:
        return float(out)
    except ValueError:
        return float("nan")


allr, alle = [], []
for k in FR:
    fr = load_frame(os.path.join(PAIRS, k + ".npz"), max_radius=0.6)
    pred = fr["W"] @ lut
    s = np.interp(pred[:, 0], Ln, slope)
    ok = (s > 5) & (pred[:, 0] > 8) & (pred[:, 0] < 92)
    e = (fr["lab"][:, 0] - pred[:, 0])[ok] / s[ok]
    r = fr["radius"][ok]
    A = np.stack([np.ones_like(r), r**2, r**4], 1)
    w = np.ones_like(e)
    for _ in range(5):  # robust reweighting
        coef, *_ = np.linalg.lstsq(A * w[:, None], e * w, rcond=None)
        sc = 1.4826 * np.median(np.abs(e - A @ coef)) + 1e-6
        w = 1 / np.maximum(1, np.abs(e - A @ coef) / (2 * sc))
    prof = [coef[1] * q**2 + coef[2] * q**4 for q in (0.2, 0.4, 0.6)]
    print(f"{k} {md(k, 'kMDItemFocalLength'):5.0f}mm f/{md(k, 'kMDItemFNumber'):<4}: offset {coef[0]:+.2f} st | lift at r=.2/.4/.6 {np.round(prof, 2).tolist()} st")
    allr.append(r)
    alle.append(e - coef[0])

r = np.concatenate(allr)
e = np.concatenate(alle)
c, *_ = np.linalg.lstsq(np.stack([r**2, r**4], 1), e, rcond=None)
print(f"pooled: --lift {c[0]:.3f},{c[1]:.3f}  -> r=.3/.5/.6: {[round(c[0] * q**2 + c[1] * q**4, 2) for q in (0.3, 0.5, 0.6)]} stops")
