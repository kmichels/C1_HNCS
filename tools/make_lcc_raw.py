"""Write a synthetic LCC (flat-field) raw that makes Capture One reproduce a measured spatial gain.

Capture One's LCC flattens the reference image: where the reference is darker or bluer, it brightens or
removes blue. So the reference is written as the inverse of the wanted gain: raw_c(x, y) = base_c * 2^-g_c.
Wanted gains (stops, per channel, relative to the centre) come from Phocus gain maps (flat_gain.py):
  colour: g_B - g_G and g_R - g_G from a Phocus map (the part Light Falloff can't do);
  light (optional): a brightness residual, e.g. Phocus-with-corrections-on minus Capture One at LF 120.
Maps are smoothed with a 2-D polynomial before writing.

usage: python make_lcc_raw.py HOST.3fr OUT.3fr --colour PHOCUS_MAP.npz [--light-residual MAP_ON.npz C1_RENDER.tif] [--degree 6] [--level 0.35]
"""
import argparse
import os
import shutil
import sys

import numpy as np
import tifffile

sys.path.insert(0, os.path.dirname(__file__))
from pairs import romm_decode  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("host"); ap.add_argument("out")
ap.add_argument("--colour", required=True)
ap.add_argument("--light-residual", nargs=2, default=None, metavar=("PHOCUS_ON_MAP", "C1_RENDER"))
ap.add_argument("--degree", type=int, default=6)
ap.add_argument("--level", type=float, default=0.35, help="green level of the reference, device linear")
ap.add_argument("--uid", default="HNCSLCC000000001")
a = ap.parse_args()

pm = np.load(a.colour)
gain = np.log2(np.clip(pm["gain"], 1e-6, None))  # (nby, nbx, 3) stops
nby, nbx = gain.shape[:2]
H, W = (int(v) for v in pm["shape"])
b = int(pm["block"])
yy, xx = np.mgrid[0:nby, 0:nbx]
# block centres in normalised coordinates (-1..1 across the image)
u = ((xx + 0.5) * b - W / 2) / (W / 2)
v = ((yy + 0.5) * b - H / 2) / (H / 2)
want = {"R": gain[..., 0] - gain[..., 1], "G": np.zeros((nby, nbx)), "B": gain[..., 2] - gain[..., 1]}
if a.light_residual:
    on = np.log2(np.clip(np.load(a.light_residual[0])["gain"], 1e-6, None))
    img = tifffile.imread(a.light_residual[1])[..., :3].astype(np.float64) / 65535
    lin = romm_decode(img[: nby * b, : nbx * b].reshape(nby, b, nbx, b, 3).mean(axis=(1, 3)))
    r = np.load(a.colour)["radius"]
    c1 = np.log2(lin / lin[r < 0.05].mean(0))
    resid = on[..., 1] - c1[..., 1]
    for k in want:
        want[k] = want[k] + resid


def terms(u, v, deg):
    return np.stack([u**i * v**j for i in range(deg + 1) for j in range(deg + 1 - i)], -1)


ok = np.isfinite(gain).all(-1) & (np.abs(gain).max(-1) < 4)
T = terms(u[ok], v[ok], a.degree)
models = {}
for k, m in want.items():
    coef, *_ = np.linalg.lstsq(T, m[ok], rcond=None)
    models[k] = coef
    fit = T @ coef
    print(f"{k}: fitted map range {fit.min():+.3f}..{fit.max():+.3f} stops, rms residual {np.sqrt(np.mean((fit - m[ok]) ** 2)):.4f}")

with tifffile.TiffFile(a.host) as t:
    p0 = t.pages[0]
    sp = p0.pages[0]
    raw = sp.asarray().copy()
    off = sp.dataoffsets[0]
    black = sp.tags["BlackLevel"].value[0]
    white = sp.tags["WhiteLevel"].value
    cx0, cy0 = sp.tags["DefaultCropOrigin"].value
    cw, ch = sp.tags["DefaultCropSize"].value
    n = p0.tags["AsShotNeutral"].value
    neutral = np.array([n[0] / n[1], n[2] / n[3], n[4] / n[5]])
    uo, ul = p0.tags["RawDataUniqueID"].valueoffset, p0.tags["RawDataUniqueID"].count
rng = float(white - black) * 0.92
SITE = {(0, 0): ("R", 0), (0, 1): ("G", 1), (1, 0): ("G", 1), (1, 1): ("B", 2)}
for (pr, pc), (k, ci) in SITE.items():
    rows = np.arange(cy0 + ((pr - cy0) % 2), cy0 + ch, 2)
    cols = np.arange(cx0 + ((pc - cx0) % 2), cx0 + cw, 2)
    # active-area pixel -> normalised coordinates of the half-size export used for the maps
    uu = ((cols - cx0) / 2.0 - W / 2) / (W / 2)
    vv = ((rows - cy0) / 2.0 - H / 2) / (H / 2)
    for i0 in range(0, len(rows), 256):
        rr = rows[i0: i0 + 256]
        V, U = np.meshgrid(vv[i0: i0 + 256], uu, indexing="ij")
        g = terms(U.ravel(), V.ravel(), a.degree) @ models[k]
        val = black + rng * a.level * neutral[ci] * 2.0 ** (-g.reshape(U.shape))
        raw[np.ix_(rr, cols)] = np.clip(val, 0, 65535).astype(np.uint16)
shutil.copyfile(a.host, a.out)
with open(a.out, "r+b") as f:
    f.seek(off)
    f.write(raw.astype("<u2").tobytes())
    f.seek(uo)
    f.write(a.uid.encode()[:ul].ljust(ul, b"0"))
print(f"wrote LCC reference {a.out}")
