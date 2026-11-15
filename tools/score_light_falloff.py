"""Score Capture One renders at several Light Falloff values against Phocus exports made with
lens corrections (vignetting) ON. Expects RENDER_ROOT/LF<value>/<frame>.tif (see
applescript/render_light_falloff.applescript) and Phocus Lab from save_phocus_lab.py in PHOCUS_ON_DIR.

usage: python score_light_falloff.py RENDER_ROOT PAIRS_DIR PHOCUS_ON_DIR BLOCK LF1,LF2,... FRAME [FRAME ...]
"""
import os
import sys

import numpy as np
import tifffile

sys.path.insert(0, os.path.dirname(__file__))
from icc import de2000  # noqa: E402
from render_lab import block_lab  # noqa: E402

ROOT, PAIRS, ON, BS = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
LFS = [int(v) for v in sys.argv[5].split(",")]
FR = sys.argv[6:]
summary = {}
for lf in LFS:
    meds = []
    print(f"Light Falloff {lf}:")
    for k in FR:
        npz = os.path.join(PAIRS, k + ".npz")
        z = np.load(npz)
        on = np.load(os.path.join(ON, k + ".npz"))
        img = os.path.join(ROOT, f"LF{lf}", k + ".tif")
        act = block_lab(img, npz, tifffile.TiffFile(img).pages[0].shape[:2], bs=BS)
        r = z["radius"]
        m = (z["dev_max"] < 0.97) & (on["ph_max"] < 0.995) & (on["lab"][:, 0] > 2) & (r < 0.95) & (act.max(axis=1) < 99)
        d = de2000(act[m], on["lab"][m])
        dl = act[m, 0] - on["lab"][m, 0]
        rm = r[m]
        bands = " | ".join(
            f"r{lo:.1f}: {np.median(d[(rm >= lo) & (rm < lo + .2)]):.2f} (dL {dl[(rm >= lo) & (rm < lo + .2)].mean():+.2f})"
            for lo in (0, .2, .4, .6, .8) if ((rm >= lo) & (rm < lo + .2)).sum() > 200
        )
        meds.append(np.median(d))
        print(f"  {k}: median {np.median(d):.2f} p90 {np.percentile(d, 90):.2f} | {bands}")
    summary[lf] = round(float(np.mean(meds)), 2)
print("mean of frame medians:", summary)
