"""What sidecar ColorModel 1 changes, compared with Standard (ColorModel 0), on the round-3 grid.

1. Neutral axis of both.
2. Models of the ColorModel 1 render (held-out patches, median dE00 by camera-RGB saturation):
   - the Standard render with a 3x3 on camera RGB in front (a different colour matrix, same rest)
   - the Standard render with a per-channel curve in Hasselblad RGB after (a different tone curve)
   - both
   - matrix -> Hasselblad RGB -> per-channel curve fitted to each render (A3; no 3-D table)
   - the raw file's own DNG ColorMatrix1 (fixed, white-balanced and adapted to D50 the DNG way)
     -> Hasselblad RGB -> per-channel curve: is the render colorimetric?
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *  # noqa: E402,F403
import tifffile  # noqa: E402
from scipy.optimize import least_squares  # noqa: E402
from fit import KNOTS, tone  # noqa: E402

lut = np.load(f"{R}/data/luts/lut_e5b_35100.npz")["lut"]
Ls, Lc = lab("R3fc4"), lab("R3cm1")
ok = (DEV.max(1) < 0.9) & (Ls[:, 0] > 3) & (Ls[:, 0] < 95) & (Lc[:, 0] < 97)
rng = np.random.default_rng(0)
test = rng.random(len(Ls)) < 0.25
train = ok & ~test & (SAT < 0.6)
sub = rng.choice(np.flatnonzero(train), min(int(train.sum()), 4000), replace=False)
bands = ((0, 0.3), (0.3, 0.6), (0.6, 0.85), (0.85, 1.01))


def score(name, pr, tgt):
    d = de2000(pr, tgt)
    print(f"   {name:62s}" + "  ".join(f"{np.median(d[ok & test & (SAT >= lo) & (SAT < hi)]):6.2f}" for lo, hi in bands))


lv = np.flatnonzero(NEUT & ok); lv = lv[np.argsort(DEVN[lv, 0])]
print("1. Greys (camera level -> L*, a*, b*): Standard | ColorModel 1")
for t in (0.01, 0.03, 0.05, 0.1, 0.18, 0.3, 0.45, 0.6):
    i = lv[np.argmin(np.abs(DEVN[lv, 0] - t))]
    print(f"   {DEVN[i, 0]:.3f}:  {Ls[i, 0]:5.1f} {Ls[i, 1]:+5.2f} {Ls[i, 2]:+5.2f}  |  {Lc[i, 0]:5.1f} {Lc[i, 1]:+5.2f} {Lc[i, 2]:+5.2f}")

print("\n2. Explaining the ColorModel 1 render, held-out median dE00 by camera-RGB saturation")
print("   " + " " * 62 + "  ".join(f"{lo:.2f}-{hi:.2f}"[:6] for lo, hi in bands))
resid = Ls - predict(lut, DEV)
score("no change (Standard as is)", Ls, Lc)
KN = np.linspace(np.log(1e-3), 0.0, 10)


def curve(v, k):
    return v * np.exp(np.interp(np.log(np.maximum(v, 1e-6)), KN, k))


def pre(k, idx):
    M = np.eye(3) + k[:9].reshape(3, 3)
    return predict(lut, np.clip(np.maximum(LIN[idx] @ M.T, 0), 0, 1) ** (1 / 1.8)) + resid[idx]


def post(lab_, k):
    hb = np.maximum(lab_to_xyz(lab_) / white @ np.linalg.inv(HB_M), 1e-6)
    return xyz_to_lab(curve(hb, k) @ HB_M * white)


r = least_squares(lambda k: (pre(k, sub) - Lc[sub]).ravel(), np.zeros(9), loss="soft_l1")
score("Standard with a different matrix in front", pre(r.x, np.arange(len(Ls))), Lc)
Mpre = np.eye(3) + r.x.reshape(3, 3)
r = least_squares(lambda k: (post(Ls[sub], k) - Lc[sub]).ravel(), np.zeros(10), loss="soft_l1")
score("Standard with a different tone curve after", post(Ls, r.x), Lc)
r = least_squares(lambda k: (post(pre(k[:9], sub), k[9:]) - Lc[sub]).ravel(), np.zeros(19), loss="soft_l1")
score("both", post(pre(r.x[:9], np.arange(len(Ls))), r.x[9:]), Lc)
Mboth = np.eye(3) + r.x[:9].reshape(3, 3)


def A3(p, x):
    pp = np.maximum((x @ p[:9].reshape(3, 3).T) * np.exp(p[9]), 0)
    return xyz_to_lab(tone(pp, p[10:]) @ HB_M)


p0 = np.concatenate([np.eye(3).ravel(), [0.0], np.zeros(len(KNOTS) - 1)])
fits = {}
for nm, L_ in (("Standard", Ls), ("ColorModel 1", Lc)):
    rr = least_squares(lambda p: (A3(p, LIN[sub]) - L_[sub]).ravel(), p0, loss="soft_l1", f_scale=2.0, max_nfev=3000)
    fits[nm] = rr.x
    score(f"matrix + Hasselblad RGB curve, fitted to {nm} (scored on {nm})", A3(rr.x, LIN), L_)

with tifffile.TiffFile(f"{R}/data/synth/HNCSsynth03.3fr") as t:
    cm = t.pages[0].tags["ColorMatrix1"].value; n = t.pages[0].tags["AsShotNeutral"].value
CM = np.array([cm[2 * i] / cm[2 * i + 1] for i in range(9)]).reshape(3, 3)  # XYZ -> camera
neutral = np.array([n[0] / n[1], n[2] / n[3], n[4] / n[5]])
cam2xyz = np.linalg.inv(CM)
wxyz = cam2xyz @ neutral
BR = np.array([[0.8951, 0.2664, -0.1614], [-0.7502, 1.7135, 0.0367], [0.0389, -0.0685, 1.0296]])
d50 = np.array([0.9642, 1.0, 0.82489])
adapt = np.linalg.inv(BR) @ np.diag((BR @ d50) / (BR @ (wxyz / wxyz[1]))) @ BR
colorimetric = adapt @ cam2xyz @ np.diag(neutral)          # white-balanced camera RGB -> XYZ D50
Mcol = (colorimetric.T @ np.linalg.inv(HB_M)).T             # white-balanced camera RGB -> Hasselblad RGB (linear)


def colmodel(p, x):
    pp = np.maximum((x @ Mcol.T) * np.exp(p[0]), 0)
    return xyz_to_lab(tone(pp, p[1:]) @ HB_M)


for nm, L_ in (("Standard", Ls), ("ColorModel 1", Lc)):
    rr = least_squares(lambda p: (colmodel(p, LIN[sub]) - L_[sub]).ravel(), np.r_[0.0, np.zeros(len(KNOTS) - 1)], loss="soft_l1", f_scale=2.0, max_nfev=3000)
    score(f"file's ColorMatrix1 (fixed) + Hasselblad RGB curve, vs {nm}", colmodel(rr.x, LIN), L_)


def norm(M):
    return M / M.sum(1, keepdims=True)


print("\n3. Matrices, camera RGB -> Hasselblad RGB, rows normalised to sum 1:")
print("   file's ColorMatrix1 (DNG way):\n" + str(np.round(norm(Mcol), 3)))
for nm in fits:
    print(f"   fitted to {nm}:\n" + str(np.round(norm(fits[nm][:9].reshape(3, 3)), 3)))
print("   3x3 in front of Standard that best gives ColorModel 1 (with a new curve):\n" + str(np.round(Mboth, 3)))

# 4. Same colour stage as Standard, then a different 3x3 and curve in linear Hasselblad RGB:
#    undo Standard's fitted Hasselblad RGB curve on the Standard render, apply M2 and a new curve.
ps = fits["Standard"]
grid = np.exp(np.linspace(np.log(1e-6), np.log(4.0), 4000))
tg = tone(np.stack([grid] * 3, 1), ps[10:])[:, 0]
order_ = np.argsort(tg)
hb_s = np.maximum(lab_to_xyz(Ls) / white @ np.linalg.inv(HB_M), 1e-7)
pre_s = np.interp(hb_s, tg[order_], grid[order_])  # Standard's linear Hasselblad RGB before its curve


def mid(k, idx):
    M2 = np.eye(3) + k[:9].reshape(3, 3)
    return xyz_to_lab(curve(np.maximum(pre_s[idx] @ M2.T, 1e-7) * np.exp(k[9]), k[10:]) @ HB_M * white)


print("\n4. Standard's colour stage, then a new 3x3 and curve in linear Hasselblad RGB")
print("   " + " " * 62 + "  ".join(f"{lo:.2f}-{hi:.2f}"[:6] for lo, hi in bands))
r = least_squares(lambda k: (mid(np.r_[np.zeros(10), k], sub) - Lc[sub]).ravel(), np.zeros(10), loss="soft_l1")
score("new curve only (check)", mid(np.r_[np.zeros(10), r.x], np.arange(len(Ls))), Lc)
r = least_squares(lambda k: (mid(k, sub) - Lc[sub]).ravel(), np.zeros(20), loss="soft_l1")
score("new 3x3 + new curve", mid(r.x, np.arange(len(Ls))), Lc)
print("   3x3 between colour stage and curve:\n" + str(np.round(np.eye(3) + r.x[:9].reshape(3, 3), 3)))
k_final = r.x
d = de2000(mid(k_final, np.arange(len(Ls))), Lc)
for nm, m in (("greys", ok & NEUT), ("dark (L* < 30)", ok & (Lc[:, 0] < 30)), ("mid", ok & (Lc[:, 0] >= 30) & (Lc[:, 0] < 70)), ("light (L* >= 70)", ok & (Lc[:, 0] >= 70))):
    print(f"   left over by lightness, {nm:18s} median {np.median(d[m]):.2f}")
