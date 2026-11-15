import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
ref = lab("R3fc4")
Cr = np.hypot(ref[:, 1], ref[:, 2])
lv = np.flatnonzero(NEUT); lv = lv[np.argsort(DEVN[lv, 0])]
print("Sidecar change vs Standard (FilmCurve 4): median dE00 | grey L* at camera levels 0.05/0.18/0.45 | chroma ratio | |dh| median")
print(f"   {'FilmCurve 4':14s}  -     | " + " ".join(f"{ref[lv[np.argmin(np.abs(DEVN[lv,0]-t))],0]:5.1f}" for t in (0.05, 0.18, 0.45)))
for n, label in [("R3fc0", "FilmCurve 0"), ("R3fc5", "FilmCurve 5"), ("R3cm1", "ColorModel 1"), ("R3cm2", "ColorModel 2"), ("R3cm3", "ColorModel 3"), ("R3md1", "Mode 1"), ("R3md2", "Mode 2")]:
    l = lab(n); d = de2000(l, ref); C = np.hypot(l[:, 1], l[:, 2]); m = Cr > 10
    dh = np.abs(((np.degrees(np.arctan2(l[:, 2], l[:, 1])) - np.degrees(np.arctan2(ref[:, 2], ref[:, 1])) + 180) % 360) - 180)
    g = " ".join(f"{l[lv[np.argmin(np.abs(DEVN[lv,0]-t))],0]:5.1f}" for t in (0.05, 0.18, 0.45))
    print(f"   {label:14s} {np.median(d):5.2f} | {g} | {np.median(C[m] / Cr[m]):.3f} | {np.median(dh[m]):.2f}")
