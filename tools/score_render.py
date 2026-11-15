"""Score finished Capture One renders (made with an HNCS profile, exported as 16-bit ROMM RGB) against a
Phocus export (16-bit ProPhoto) of the same raw at the same scale: align, compare per block in Lab.

Blocks with clipped or near-black values, and the busiest 30% of blocks (edges, where a sub-pixel
offset dominates), are left out. Reports the median dE00 over the frame and by radius.

usage: python score_render.py PHOCUS.tif C1_RENDER.tif [C1_RENDER.tif ...] [--block 32] [--json OUT]
"""
import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from icc import D50, de2000, xyz_to_lab  # noqa: E402
from pairs import PROPHOTO_M, crop_overlap, downsample_lum, load, phase_corr, phocus_decode, romm_decode  # noqa: E402

white = D50 / np.array([0.9642, 1.0, 0.82489])


def align(a, b):
    f = 8
    la, lb = downsample_lum(a, romm_decode, f), downsample_lum(b, phocus_decode, f)
    hh, ww = min(la.shape[0], lb.shape[0]), min(la.shape[1], lb.shape[1])
    dy8, dx8, _ = phase_corr(la[:hh, :ww], lb[:hh, :ww])
    dy, dx = dy8 * f, dx8 * f
    sa, sb = crop_overlap(a.shape, b.shape, dy, dx)
    A, B = a[sa], b[sb]
    H, W = A.shape[:2]
    T, res = 512, []
    for cy in (0.3, 0.5, 0.7):
        for cx in (0.3, 0.5, 0.7):
            y0, x0 = int(cy * H) - T // 2, int(cx * W) - T // 2
            ta = romm_decode(A[y0:y0 + T, x0:x0 + T].astype(np.float32) / 65535) @ PROPHOTO_M[1].astype(np.float32)
            tb = phocus_decode(B[y0:y0 + T, x0:x0 + T].astype(np.float32) / 65535) @ PROPHOTO_M[1].astype(np.float32)
            ty, tx, tp = phase_corr(ta, tb)
            if tp > 0.05:
                res.append((ty, tx))
    if res:
        dy += int(np.median([r[0] for r in res]))
        dx += int(np.median([r[1] for r in res]))
    return crop_overlap(a.shape, b.shape, dy, dx), (dy, dx)


def block_lab(img, decode, bs):
    H, W = img.shape[:2]
    nby, nbx = H // bs, W // bs
    x = decode(img[:nby * bs, :nbx * bs].astype(np.float32) / 65535).reshape(nby, bs, nbx, bs, 3)
    Y = x @ PROPHOTO_M[1].astype(np.float32)
    m = x.mean(axis=(1, 3)).reshape(-1, 3).astype(np.float64)
    return xyz_to_lab((m @ PROPHOTO_M.T) * white), Y.std(axis=(1, 3)).ravel() / np.maximum(Y.mean(axis=(1, 3)).ravel(), 1e-6), x.max(axis=(1, 3, 4)).ravel()


ap = argparse.ArgumentParser()
ap.add_argument("phocus"); ap.add_argument("renders", nargs="+")
ap.add_argument("--block", type=int, default=32)
ap.add_argument("--json", default=None)
a = ap.parse_args()
ph = load(a.phocus)
out = {}
for r in a.renders:
    c1 = load(r)
    if c1.shape[:2] != ph.shape[:2]:
        print(f"{os.path.basename(r)}: size {c1.shape[:2]} vs Phocus {ph.shape[:2]}; skipped")
        continue
    (sa, sb), shift = align(c1, ph)
    A, B = c1[sa], ph[sb]
    la, _, ma = block_lab(A, romm_decode, a.block)
    lb, busy, mb = block_lab(B, phocus_decode, a.block)
    H, W = A.shape[:2]
    nby, nbx = H // a.block, W // a.block
    yy, xx = np.mgrid[0:nby, 0:nbx]
    cy = yy * a.block + a.block / 2 + sa[0].start - c1.shape[0] / 2
    cx = xx * a.block + a.block / 2 + sa[1].start - c1.shape[1] / 2
    rad = (np.hypot(cy, cx) / np.hypot(c1.shape[0] / 2, c1.shape[1] / 2)).ravel()
    ok = (lb[:, 0] > 3) & (lb[:, 0] < 97) & (la[:, 0] < 97) & (mb < 0.99) & (ma < 0.99) & (rad < 0.95)
    ok &= busy < np.percentile(busy[ok], 70)
    d = de2000(la[ok], lb[ok])
    dl = la[ok, 0] - lb[ok, 0]
    rr = rad[ok]
    bands = {f"r{lo:.1f}": (float(np.median(d[(rr >= lo) & (rr < lo + .2)])), float(dl[(rr >= lo) & (rr < lo + .2)].mean()))
             for lo in (0, .2, .4, .6, .8) if ((rr >= lo) & (rr < lo + .2)).sum() > 50}
    out[os.path.join(os.path.basename(os.path.dirname(r)), os.path.basename(r))] = dict(median=float(np.median(d)), p90=float(np.percentile(d, 90)), dL=float(np.median(dl)), bands=bands, shift=shift, n=int(ok.sum()))
    print(f"{os.path.basename(r)}: median {np.median(d):.2f} p90 {np.percentile(d, 90):.2f} dL {np.median(dl):+.2f} | "
          + " | ".join(f"{k}: {v[0]:.2f} ({v[1]:+.1f})" for k, v in bands.items()) + f"  [shift {shift}, {ok.sum()} blocks]")
if a.json:
    json.dump(out, open(a.json, "w"), indent=1)
