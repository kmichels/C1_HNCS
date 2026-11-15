"""Recover the spatial per-channel gain Phocus applies, from its export of a synthetic flat field.

The flat field has the same camera RGB everywhere. At each block, Phocus's output Lab is inverted
through a centre-accurate LUT (fitted on synthetic patches near the centre) to the camera RGB that would
give that colour at the centre; divided by the centre block's value, that is Phocus's gain map for each
channel. Reports radial profiles (in stops) and writes the maps to an npz.

usage: python flat_gain.py LUT.npz PHOCUS_EXPORT.tif OUT.npz [--block 32]
"""
import argparse
import sys
import os

import numpy as np
import tifffile

sys.path.insert(0, os.path.dirname(__file__))
from fit import predict  # noqa: E402
from icc import D50, xyz_to_lab  # noqa: E402
from pairs import PROPHOTO_M, phocus_decode  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("lut"); ap.add_argument("export"); ap.add_argument("out")
ap.add_argument("--block", type=int, default=32)
a = ap.parse_args()
lut = np.load(a.lut)["lut"]
img = tifffile.imread(a.export)[..., :3].astype(np.float64) / 65535
H, W = img.shape[:2]
b = a.block
nby, nbx = H // b, W // b
blk = img[: nby * b, : nbx * b].reshape(nby, b, nbx, b, 3).mean(axis=(1, 3))
white = D50 / np.array([0.9642, 1.0, 0.82489])
lab = xyz_to_lab((phocus_decode(blk.reshape(-1, 3)) @ PROPHOTO_M.T) * white)

# invert the LUT per block: Newton with a finite-difference Jacobian, device in gamma-1.8 encoding
d = np.full((len(lab), 3), 0.4)
for it in range(25):
    f0 = predict(lut, d) - lab
    J = np.zeros((len(lab), 3, 3))
    for c in range(3):
        dd = d.copy()
        dd[:, c] += 1e-3
        J[:, :, c] = (predict(lut, dd) - lab - f0) / 1e-3
    step = np.linalg.solve(J + 1e-9 * np.eye(3), f0[..., None])[..., 0]
    d = np.clip(d - step, 1e-4, 1.0)
    if np.abs(f0).max() < 1e-3:
        break
res = np.abs(predict(lut, d) - lab).max(1)
lin = d**1.8
yy, xx = np.mgrid[0:nby, 0:nbx]
cy, cx = (nby - 1) / 2, (nbx - 1) / 2
r = (np.hypot((yy - cy) * b, (xx - cx) * b) / np.hypot(H / 2, W / 2)).ravel()
centre = lin[r < 0.05].mean(0)
gain = lin / centre
stops = np.log2(gain)
np.savez(a.out, gain=gain.reshape(nby, nbx, 3), lab=lab.reshape(nby, nbx, 3), radius=r.reshape(nby, nbx), centre_lab=lab[r < 0.05].mean(0), block=b, shape=(H, W))
print(f"{os.path.basename(a.export)}: inversion max residual {res.max():.3f} (p99 {np.percentile(res, 99):.3f}); centre Lab {np.round(lab[r < 0.05].mean(0), 2)}")
print("   r     gain R/G/B (stops)          B/G, R/G (colour, stops)   Lab dL da db vs centre")
for lo in (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9):
    m = (r >= lo - 0.025) & (r < lo + 0.025)
    if m.sum() < 5:
        continue
    s = stops[m].mean(0)
    dl = (lab[m] - lab[r < 0.05].mean(0)).mean(0)
    print(f"  {lo:.1f}   {s[0]:+.3f} {s[1]:+.3f} {s[2]:+.3f}        {s[2]-s[1]:+.3f} {s[0]-s[1]:+.3f}          {dl[0]:+.2f} {dl[1]:+.2f} {dl[2]:+.2f}")
q = stops[:, 1].reshape(nby, nbx)
print(f"   symmetry (green, r~0.6): left {q[:, :nbx//6].mean():+.3f} right {q[:, -nbx//6:].mean():+.3f} top {q[:nby//6].mean():+.3f} bottom {q[-nby//6:].mean():+.3f}")
