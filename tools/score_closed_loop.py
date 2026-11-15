"""Closed loop: score real Capture One renders (made with the fitted profile, Light Falloff 0) against
Phocus (lens corrections off), on the pairs grid.

usage: python score_closed_loop.py LUT.npz RENDER_DIR BLOCK PAIRS_DIR FRAME [FRAME ...]
  BLOCK is the pairs.py --block used for PAIRS_DIR (32 for full-size, 16 for half-size renders).
"""
import os
import sys

import numpy as np
import tifffile

sys.path.insert(0, os.path.dirname(__file__))
from fit import load_frame  # noqa: E402
from icc import de2000  # noqa: E402
from render_lab import block_lab  # noqa: E402

lut = np.load(sys.argv[1])["lut"]
RENDERS, BS, PAIRS = sys.argv[2], int(sys.argv[3]), sys.argv[4]
for k in sys.argv[5:]:
    npz = os.path.join(PAIRS, k + ".npz")
    img = os.path.join(RENDERS, k + ".tif")
    fr = load_frame(npz, max_radius=0.6)
    act = block_lab(img, npz, tifffile.TiffFile(img).pages[0].shape[:2], bs=BS)[fr["mask"]]
    r = fr["radius"]
    c = r < 0.3
    d = de2000(act, fr["lab"])
    dp = de2000(act, fr["W"] @ lut)
    bands = " ".join(f"{np.mean((act - fr['lab'])[(r >= lo) & (r < lo + .1), 0]):+.2f}" for lo in (0, .1, .2, .3, .4, .5))
    print(f"{k}: centre (r<0.3) render vs Phocus median {np.median(d[c]):.2f} p90 {np.percentile(d[c], 90):.2f} | "
          f"render vs LUT prediction {np.median(dp):.2f} | dL* by radius 0-0.6: {bands}")
