"""Compare a Capture One probe render of a synthetic flat (with a generated settings file) against Phocus's
map in 2-D: per-channel raw-domain gain relative to the centre, block by block.

usage: python flat_2d.py RENDER.tif MAP.npz FLAT_DEVICE_LEVEL EXPOSURE_EV
"""
import os
import sys

import numpy as np
import tifffile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from pairs import romm_decode  # noqa: E402

rz = np.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "fit", "c1_response.npz"))
img = romm_decode(tifffile.imread(sys.argv[1])[..., :3].astype(np.float64) / 65535)
z = np.load(sys.argv[2]); mg, mr, b = z["raw_gain"], z["radius"], int(z["block"])
nby, nbx = mg.shape[:2]
blk = img[: nby * b, : nbx * b].reshape(nby, b, nbx, b, 3).mean(axis=(1, 3))
raw = np.stack([np.interp(blk[..., c], rz["c1"], rz["nominal"]) for c in range(3)], -1)
c0 = raw[mr < 0.03].mean(0)
d = np.log2(raw / c0) - np.log2(mg)
ok = (mr < 0.95) & (raw.max(-1) < 0.9)
print(f"blocks {int(ok.sum())}; centre raw RGB {np.round(c0, 4)} (green / expected {c0[1] / (float(sys.argv[3]) * 0.92 * 2 ** float(sys.argv[4])):.4f}; R/G, B/G {c0[0] / c0[1]:.4f}, {c0[2] / c0[1]:.4f})")
for ci, k in enumerate("RGB"):
    print(f"  {k}: render minus map, stops: rms {np.sqrt(np.mean(d[ok, ci] ** 2)):.3f}, p95 |.| {np.percentile(np.abs(d[ok, ci]), 95):.3f}, mean {d[ok, ci].mean():+.3f}")
for f in (0.4, 0.6, 0.8):
    ring = ok & (np.abs(mr - f) < 0.03)
    yy, xx = np.mgrid[0:nby, 0:nbx]; cy, cx = (nby - 1) / 2, (nbx - 1) / 2
    sides = [ring & (xx < cx) & (np.abs(yy - cy) < nby * 0.2), ring & (xx > cx) & (np.abs(yy - cy) < nby * 0.2),
             ring & (yy < cy) & (np.abs(xx - cx) < nbx * 0.25), ring & (yy > cy) & (np.abs(xx - cx) < nbx * 0.25)]
    print(f"  r {f}: green render minus map, left/right/top/bottom: " + " ".join(f"{d[s, 1].mean():+.3f}" for s in sides))
