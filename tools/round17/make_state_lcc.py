"""LCC reference raw for one lens setting: the part of Phocus's map a radial falloff curve can't carry.

The settings-file route (c1_sidecars.py) applies the map's green gain as a radial curve c(r). This writes a
reference whose LCC, with colour cast and uniform light both on, adds the rest per channel:
    want_c(x, y) = log2(map_c(x, y)) - c(r)            (stops; R, G and B)
Capture One's LCC flattens the reference, so the reference is the inverse: raw_c = base_c * 2^(-k * want_c),
with k a response exponent (1 for colour, measured in Finding 39; to be measured for uniform light).
Smoothed with a 2-D polynomial.

usage: python make_state_lcc.py MAP.npz HOST.3fr OUT.3fr [--k 1.0] [--degree 8] [--uid UID]
"""
import argparse
import os
import shutil
import sys

import numpy as np
import tifffile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
HALF_DIAG_UM = np.hypot(11656, 8742) / 2 * 3.76

ap = argparse.ArgumentParser()
ap.add_argument("map"); ap.add_argument("host"); ap.add_argument("out")
ap.add_argument("--k", type=float, default=1.0)
ap.add_argument("--degree", type=int, default=8)
ap.add_argument("--level", type=float, default=0.35)
ap.add_argument("--uid", default="HNCSSTATELCC0001")
ap.add_argument("--full", action="store_true", help="carry the whole map (no radial curve): Capture One turns Light Falloff off when uniform light is on")
a = ap.parse_args()


def curve_points(z):
    r, g = z["radius"].ravel(), z["raw_gain"][..., 1].ravel()
    pts = [(0.0, 0.0)]
    for f in (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95):
        m = np.abs(r - f) < 0.025
        pts.append((f * HALF_DIAG_UM, float(np.log2(g[m].mean()))))
    pts.append((28000.0, float(np.log2(g[r > 0.96].mean()))))
    return np.array(pts)


z = np.load(a.map)
gain = np.log2(np.clip(z["raw_gain"], 1e-6, None))
nby, nbx = gain.shape[:2]
H, W = (int(v) for v in z["shape"])
b = int(z["block"])
pts = curve_points(z)
c = 0.0 if a.full else np.interp(z["radius"] * HALF_DIAG_UM, pts[:, 0], pts[:, 1])
want = gain - (c if a.full else c[..., None])
yy, xx = np.mgrid[0:nby, 0:nbx]
u = ((xx + 0.5) * b - W / 2) / (W / 2)
v = ((yy + 0.5) * b - H / 2) / (H / 2)


def terms(u, v, deg):
    return np.stack([u**i * v**j for i in range(deg + 1) for j in range(deg + 1 - i)], -1)


ok = z["radius"] < 0.97
T = terms(u[ok], v[ok], a.degree)
models = []
for ci, k in enumerate("RGB"):
    coef, *_ = np.linalg.lstsq(T, want[..., ci][ok], rcond=None)
    fit = T @ coef
    models.append(coef)
    print(f"{k}: non-radial part {fit.min():+.3f}..{fit.max():+.3f} stops, fit rms {np.sqrt(np.mean((fit - want[..., ci][ok]) ** 2)):.4f}")

with tifffile.TiffFile(a.host) as t:
    p0 = t.pages[0]; sp = p0.pages[0]
    raw = sp.asarray().copy(); off = sp.dataoffsets[0]
    black = sp.tags["BlackLevel"].value[0]; white = sp.tags["WhiteLevel"].value
    cx0, cy0 = sp.tags["DefaultCropOrigin"].value; cw, ch = sp.tags["DefaultCropSize"].value
    n = p0.tags["AsShotNeutral"].value
    neutral = np.array([n[0] / n[1], n[2] / n[3], n[4] / n[5]])
    uo, ul = p0.tags["RawDataUniqueID"].valueoffset, p0.tags["RawDataUniqueID"].count
rng = float(white - black) * 0.92
for (pr, pc), ci in {(0, 0): 0, (0, 1): 1, (1, 0): 1, (1, 1): 2}.items():
    rows = np.arange(cy0 + ((pr - cy0) % 2), cy0 + ch, 2)
    cols = np.arange(cx0 + ((pc - cx0) % 2), cx0 + cw, 2)
    uu = ((cols - cx0) / 2.0 - W / 2) / (W / 2)
    vv = ((rows - cy0) / 2.0 - H / 2) / (H / 2)
    for i0 in range(0, len(rows), 256):
        rr = rows[i0: i0 + 256]
        V, U = np.meshgrid(vv[i0: i0 + 256], uu, indexing="ij")
        g = (terms(U.ravel(), V.ravel(), a.degree) @ models[ci]).reshape(U.shape)
        raw[np.ix_(rr, cols)] = np.clip(black + rng * a.level * neutral[ci] * 2.0 ** (-a.k * g), 0, 65535).astype(np.uint16)
shutil.copyfile(a.host, a.out)
with open(a.out, "r+b") as f:
    f.seek(off); f.write(raw.astype("<u2").tobytes())
    f.seek(uo); f.write(a.uid.encode()[:ul].ljust(ul, b"0"))
print(f"wrote {a.out}")
