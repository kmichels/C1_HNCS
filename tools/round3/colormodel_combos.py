"""ColorModel 1 combined with FilmCurve 0, and the ColorWorkingSpace key (round-3b renders)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *  # noqa: E402,F403
from scipy.optimize import least_squares  # noqa: E402

L = {n: lab(n) for n in ("R3fc4", "R3fc0", "R3cm1", "R4cm1fc0", "R4cws1", "R4cws2", "R4cws3", "R4cws1fc0")}
ok = (DEV.max(1) < 0.9) & (L["R3fc4"][:, 0] > 3) & (L["R3fc4"][:, 0] < 95)
lv = np.flatnonzero(NEUT & ok); lv = lv[np.argsort(DEVN[lv, 0])]
print("median dE00 between renders, and grey L* at camera 0.028 / 0.057 / 0.165 / 0.428")
for a, b in (("R4cws1", "R3fc4"), ("R4cws2", "R3fc4"), ("R4cws3", "R3fc4"), ("R4cws1fc0", "R3fc0"),
             ("R4cm1fc0", "R3cm1"), ("R4cm1fc0", "R3fc0"), ("R4cm1fc0", "R3fc4")):
    print(f"   {a:10s} vs {b:6s}: {np.median(de2000(L[a][ok], L[b][ok])):5.2f}")
for n in ("R3fc4", "R3fc0", "R3cm1", "R4cm1fc0"):
    g = [L[n][lv[np.argmin(np.abs(DEVN[lv, 0] - t))], 0] for t in (0.028, 0.057, 0.165, 0.428)]
    print(f"   {n:9s} greys " + " / ".join(f"{v:5.1f}" for v in g))

KN = np.linspace(np.log(1e-3), 0.0, 10)


def curve(v, k):
    return v * np.exp(np.interp(np.log(np.maximum(v, 1e-6)), KN, k))


def via_hb(src, k):
    hb = np.maximum(lab_to_xyz(src) / white @ np.linalg.inv(HB_M), 1e-6)
    return xyz_to_lab(curve(hb, k) @ HB_M * white)


sub = np.random.default_rng(0).choice(np.flatnonzero(ok), 4000, replace=False)
print("\nIs FilmCurve 0 the same Hasselblad RGB curve swap under ColorModel 1? median dE00 (moderate | saturated)")
r = least_squares(lambda k: (via_hb(L["R3fc4"][sub], k) - L["R3fc0"][sub]).ravel(), np.zeros(10), loss="soft_l1")
k_std = r.x
for nm, src, tgt, k in (("Standard -> FilmCurve 0 (fitted)", "R3fc4", "R3fc0", k_std),
                        ("ColorModel 1 -> ColorModel 1 + FilmCurve 0, same curve swap", "R3cm1", "R4cm1fc0", k_std)):
    d = de2000(via_hb(L[src], k), L[tgt])
    print(f"   {nm:62s} {np.median(d[ok & (SAT < 0.6)]):5.2f} | {np.median(d[ok & (SAT >= 0.6)]):5.2f}")
r = least_squares(lambda k: (via_hb(L["R3cm1"][sub], k) - L["R4cm1fc0"][sub]).ravel(), np.zeros(10), loss="soft_l1")
d = de2000(via_hb(L["R3cm1"], r.x), L["R4cm1fc0"])
print(f"   {'ColorModel 1 -> ColorModel 1 + FilmCurve 0, own curve fitted':62s} {np.median(d[ok & (SAT < 0.6)]):5.2f} | {np.median(d[ok & (SAT >= 0.6)]):5.2f}")
