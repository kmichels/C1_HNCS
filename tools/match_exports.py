"""Phocus renames exports (B_0004_prv.tif ...). Match each export to its Capture One probe render
by image content so you know which raw it came from.

usage: python match_exports.py PHOCUS_EXPORT_DIR C1_PROBE_DIR
"""
import glob
import os
import sys

import numpy as np
import tifffile

P = sorted(glob.glob(os.path.join(sys.argv[1], "*.tif")))
C = sorted(glob.glob(os.path.join(sys.argv[2], "*.tif")))


def thumb(p):
    a = tifffile.imread(p)[..., :3].astype(np.float32)
    h, w = a.shape[:2]
    a = a[: h // 64 * 64, : w // 64 * 64].reshape(h // 64, 64, w // 64, 64, 3).mean((1, 3))
    g = np.log(a.mean(-1) + 50)
    return (g - g.mean()) / g.std()


tc = {os.path.basename(c)[:-4]: thumb(c) for c in C}
for p in P:
    t = thumb(p)
    sc = sorted(((float((t * v).mean()), k) for k, v in tc.items() if v.shape == t.shape), reverse=True)[:2]
    if not sc:
        print(os.path.basename(p), "no render with the same size (cropped in Phocus?)")
        continue
    nxt = f" (next {sc[1][1]} {sc[1][0]:.3f})" if len(sc) > 1 else ""
    print(f"{os.path.basename(p)} -> {sc[0][1]}  score {sc[0][0]:.3f}{nxt}")
