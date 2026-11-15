"""Probe the structure of Phocus's HNCS transform from synthetic patch pairs (camera RGB -> Phocus Lab).

Reports:
  1. the neutral tone curve (L* and grey tint vs camera exposure);
  2. how well models of increasing complexity explain the data, on held-out patches:
     A  3x3 matrix -> ProPhoto -> one tone curve applied to each channel ("per-channel", like a classic DNG)
     B  3x3 matrix -> tone curve applied to luminance, chroma kept ("hue-preserving")
     C  A plus a 2.5-D hue/saturation table (hue x saturation bins, value-independent; like a DCP LookTable)
     D  the full 3-D LUT (33^3, as fitted for the profile)
  3. hue constancy: hue angle change when a colour is brightened (same camera RGB ratios, more exposure);
  4. gamut: Phocus output channels at 0 or full scale.

usage: python hncs_structure.py LUT.npz GAINMAP.npz PAIRS.npz [PAIRS.npz ...]
"""
import os
import sys

import numpy as np
from scipy.optimize import least_squares

sys.path.insert(0, os.path.dirname(__file__))
from fit import KNOTS, predict, tone  # noqa: E402
from icc import D50, de2000, xyz_to_lab, lab_to_xyz  # noqa: E402
from pairs import PROPHOTO_M  # noqa: E402

lut = np.load(sys.argv[1])["lut"]
gm = np.load(sys.argv[2])
devs, labs, raw_ph = [], [], []
for f in sys.argv[3:]:
    z = np.load(f)
    pos, P = z["pos"], int(z["patch"])
    gb = int(gm["block"])
    gy = np.clip(((pos[:, 0] + P / 2) / 2 // gb).astype(int), 0, gm["gain"].shape[0] - 1)
    gx = np.clip(((pos[:, 1] + P / 2) / 2 // gb).astype(int), 0, gm["gain"].shape[1] - 1)
    lin = z["device_c1_lin"] * gm["gain"][gy, gx]
    ok = (lin.max(1) ** (1 / 1.8) < 0.97) & (z["phocus_prophoto"].max(1) < 0.995) & (z["phocus_prophoto"].min(1) > 2 / 65535) & (z["lab"][:, 0] > 1)
    devs.append(lin[ok]); labs.append(z["lab"][ok]); raw_ph.append(z["phocus_prophoto"])
lin = np.concatenate(devs); lab = np.concatenate(labs); ph_all = np.concatenate(raw_ph)
white = D50 / np.array([0.9642, 1.0, 0.82489])
print(f"{len(lab)} usable patches")

# 1. neutral tone curve
g = np.ptp(lin, axis=1) / np.maximum(lin.mean(1), 1e-9) < 0.02
order = np.argsort(lin[g, 1])
yv = lin[g, 1][order]; lv = lab[g][order]
print("\n1. Neutral axis (camera green, linear) -> Phocus L*, a*, b*:")
for target in (0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.4, 0.6, 0.75):
    i = np.argmin(np.abs(np.log(yv) - np.log(target)))
    print(f"   {yv[i]:.4f} ({np.log2(yv[i] / 0.18):+.2f} EV from 0.18): L* {lv[i, 0]:6.2f}  a* {lv[i, 1]:+.2f}  b* {lv[i, 2]:+.2f}")

# split for held-out evaluation
rng = np.random.default_rng(0)
test = rng.random(len(lab)) < 0.25
C_out = np.hypot(lab[:, 1], lab[:, 2])
sat_in = 1 - lin.min(1) / np.maximum(lin.max(1), 1e-9)  # camera-RGB saturation (0 = grey, 1 = a pure primary)
inr = sat_in < 0.6  # fit the simple models on moderately saturated colours


def model_A(p, x):
    # per-channel: matrix -> ProPhoto linear -> one tone curve on each channel (fit.base_model)
    pp = np.maximum((x @ p[:9].reshape(3, 3).T) * np.exp(p[9]), 0)
    return xyz_to_lab(tone(pp, p[10:]) @ PROPHOTO_M.T)


def model_B(p, x):
    # hue-preserving: the tone curve acts on luminance; RGB scaled by the same factor
    pp = np.maximum((x @ p[:9].reshape(3, 3).T) * np.exp(p[9]), 1e-9)
    Y = np.maximum(pp @ PROPHOTO_M[1], 1e-9)
    return xyz_to_lab((pp * (tone(Y, p[10:]) / Y)[:, None]) @ PROPHOTO_M.T)


def fit(model):
    p0 = np.concatenate([np.eye(3).ravel(), [0.0], np.zeros(len(KNOTS) - 1)])
    tr = np.flatnonzero(~test & inr)
    tr = rng.choice(tr, min(len(tr), 20000), replace=False)
    r = least_squares(lambda p: (model(p, lin[tr]) - lab[tr]).ravel(), p0, method="trf", loss="soft_l1", f_scale=2.0, max_nfev=2000)
    return r.x


print("\n2. Model fits on held-out patches, median dE00 by camera-RGB saturation (fit on saturation < 0.6):")
bands = ((0, 0.3), (0.3, 0.6), (0.6, 0.85), (0.85, 1.01))
print("   " + " " * 42 + "  ".join(f"{lo:.2f}-{hi:.2f}" for lo, hi in bands))
res = {}
for name, model in (("A matrix + per-channel tone curve", model_A), ("B matrix + hue-preserving tone curve", model_B)):
    p = fit(model)
    pr = model(p, lin)
    res[name] = (p, model)
    d = de2000(pr, lab)
    print(f"   {name:42s}" + "  ".join(f"{np.median(d[test & (sat_in >= lo) & (sat_in < hi)]):9.2f}" for lo, hi in bands))

# C: model A + 2.5-D hue/sat table on the residual, binned by output hue and chroma
pA, mA = res["A matrix + per-channel tone curve"]
predA = mA(pA, lin)
def lch(l):
    return np.stack([l[:, 0], np.hypot(l[:, 1], l[:, 2]), np.degrees(np.arctan2(l[:, 2], l[:, 1])) % 360], 1)
LA, LT = lch(predA), lch(lab)
hb = (LA[:, 2] // 10).astype(int) % 36
cb = np.clip((LA[:, 1] // 10).astype(int), 0, 9)
tr = ~test & inr
dh = np.zeros((36, 10)); cs = np.ones((36, 10)); cnt = np.zeros((36, 10))
for i in range(36):
    for j in range(10):
        m = tr & (hb == i) & (cb == j) & (LA[:, 1] > 2)
        if m.sum() >= 5:
            dh[i, j] = np.median(((LT[m, 2] - LA[m, 2] + 180) % 360) - 180)
            cs[i, j] = np.median(LT[m, 1] / np.maximum(LA[m, 1], 1e-6))
            cnt[i, j] = m.sum()
h2 = np.radians(LA[:, 2] + dh[hb, cb]); c2 = LA[:, 1] * cs[hb, cb]
predC = np.stack([predA[:, 0], c2 * np.cos(h2), c2 * np.sin(h2)], 1)
d = de2000(predC, lab)
print(f"   {'C  A + 2.5-D hue/saturation table':42s}" + "  ".join(f"{np.median(d[test & (sat_in >= lo) & (sat_in < hi)]):9.2f}" for lo, hi in bands))
d = de2000(predict(lut, lin ** (1 / 1.8)), lab)
print(f"   {'D  full 3-D LUT (profile; trained on all)':42s}" + "  ".join(f"{np.median(d[test & (sat_in >= lo) & (sat_in < hi)]):9.2f}" for lo, hi in bands))
print("   patches per band: " + ", ".join(str(int((test & (sat_in >= lo) & (sat_in < hi)).sum())) for lo, hi in bands))
print(f"   (hue/sat table bins filled: {(cnt > 0).sum()} of 360; hue shifts range {dh[cnt > 0].min():+.1f}..{dh[cnt > 0].max():+.1f} deg, saturation scale {cs[cnt > 0].min():.2f}..{cs[cnt > 0].max():.2f})")

# 3. hue constancy along exposure, using the smooth 3-D LUT
print("\n3. Hue angle change when a colour is brightened 1 and 2 stops (same camera RGB ratios):")
bases = {"red": (0.06, 0.012, 0.008), "orange": (0.07, 0.03, 0.008), "yellow": (0.06, 0.05, 0.01), "green": (0.02, 0.05, 0.015),
         "cyan": (0.01, 0.04, 0.05), "blue": (0.008, 0.012, 0.06), "magenta": (0.05, 0.012, 0.05), "skin": (0.09, 0.055, 0.035)}
for nm, b in bases.items():
    b = np.array(b)
    hs = []
    for k in (1, 2, 4):
        l = predict(lut, np.clip(b * k, 0, 1) ** (1 / 1.8))
        hs.append((np.degrees(np.arctan2(l[0, 2], l[0, 1])) % 360, l[0, 0], np.hypot(l[0, 1], l[0, 2])))
    print(f"   {nm:8s}: hue {hs[0][0]:6.1f} -> {hs[1][0]:6.1f} -> {hs[2][0]:6.1f} deg (L* {hs[0][1]:.0f}/{hs[1][1]:.0f}/{hs[2][1]:.0f}, C* {hs[0][2]:.0f}/{hs[1][2]:.0f}/{hs[2][2]:.0f})")

# 4. gamut handling
lo = (ph_all <= 1 / 65535).any(1); hi = (ph_all >= 65534 / 65535).any(1)
print(f"\n4. Phocus output channels clipped in ProPhoto: at 0 in {lo.mean():.1%} of all patches, at full scale in {hi.mean():.1%}")
print(f"   max output chroma C* {C_out.max():.0f}; patches with C* > 100: {(C_out > 100).mean():.1%}")
