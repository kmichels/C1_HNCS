"""Which RGB space each sidecar ColorWorkingSpace value moves the tone curve into.

Undo Standard's fitted Hasselblad RGB curve on the Standard render (giving the colour stage's output in
linear Hasselblad RGB), convert to a candidate space, apply a per-channel curve (fitted) and compare with
the ColorWorkingSpace render. The right space should fit as tightly as FilmCurve 0 does in Hasselblad RGB.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *  # noqa: E402,F403
from scipy.optimize import least_squares  # noqa: E402
from fit import KNOTS, tone  # noqa: E402

SPACES = {  # rows: XYZ (D50) of the R, G, B primaries
    "Hasselblad RGB": HB_M,
    "Hasselblad L* RGB (wide)": np.array([[0.8723, 0.2811, 0.0], [0.0762, 0.6999, 0.0], [0.0157, 0.019, 0.8252]]),
    "ProPhoto (L* RGB v1)": PROPHOTO_M.T,
    "Rec.2020": np.array([[0.6734, 0.2790, -0.0019], [0.1656, 0.6753, 0.0300], [0.1251, 0.0457, 0.7973]]),
    "Display P3": np.array([[0.5151, 0.2412, -0.0011], [0.2920, 0.6922, 0.0419], [0.1571, 0.0666, 0.7841]]),
    "Adobe RGB": np.array([[0.6097, 0.3111, 0.0195], [0.2053, 0.6257, 0.0609], [0.1492, 0.0632, 0.7446]]),
    "sRGB / Rec.709": np.array([[0.4361, 0.2225, 0.0139], [0.3851, 0.7169, 0.0971], [0.1431, 0.0606, 0.7141]]),
}
Ls = lab("R3fc4")
ok = (DEV.max(1) < 0.9) & (Ls[:, 0] > 3) & (Ls[:, 0] < 95)
rng = np.random.default_rng(0)
_m = np.flatnonzero(ok & (SAT < 0.6)); sub = rng.choice(_m, min(len(_m), 3000), replace=False)


def A3(p, x):
    pp = np.maximum((x @ p[:9].reshape(3, 3).T) * np.exp(p[9]), 0)
    return xyz_to_lab(tone(pp, p[10:]) @ HB_M)


p0 = np.concatenate([np.eye(3).ravel(), [0.0], np.zeros(len(KNOTS) - 1)])
ps = least_squares(lambda p: (A3(p, LIN[sub]) - Ls[sub]).ravel(), p0, loss="soft_l1", f_scale=2.0, max_nfev=3000).x
grid = np.exp(np.linspace(np.log(1e-7), np.log(8.0), 6000))
tg = tone(np.stack([grid] * 3, 1), ps[10:])[:, 0]
o = np.argsort(tg)
hb = np.maximum(lab_to_xyz(Ls) / white @ np.linalg.inv(HB_M), 1e-8)
xyz_pre = np.interp(hb, tg[o], grid[o]) @ HB_M  # colour-stage output (XYZ, linear, before the curve)
sub2 = rng.choice(np.flatnonzero(ok), 4000, replace=False)


def in_space(M, k, idx, same_curve):
    rgb = xyz_pre[idx] @ np.linalg.inv(M)
    if same_curve:
        out = tone(np.maximum(rgb, 0) * np.exp(k[0]), ps[10:])
    else:
        out = tone(np.maximum(rgb, 0) * np.exp(k[0]), k[1:])
    return xyz_to_lab(out @ M * white)


print("median dE00 (moderate | saturated colours) for each candidate space; 'same curve' keeps Standard's curve, 'own curve' refits it")
for n in ("R3fc4", "R4cws1", "R4cws2", "R4cws3"):
    L_ = lab(n)
    print(f"-- {n}")
    for nm, M in SPACES.items():
        res = []
        for same in (True, False):
            k0 = np.zeros(1) if same else np.r_[0.0, ps[10:]]
            r = least_squares(lambda k: (in_space(M, k, sub2, same) - L_[sub2]).ravel(), k0, loss="soft_l1", max_nfev=2000)
            d = de2000(in_space(M, r.x, np.arange(len(L_)), same), L_)
            res.append(f"{np.median(d[ok & (SAT < 0.6)]):5.2f} | {np.median(d[ok & (SAT >= 0.6)]):5.2f}")
        print(f"   {nm:26s} same curve {res[0]}    own curve {res[1]}")
