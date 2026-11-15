"""Phocus's four Response options, rendered via sidecar ColorModel 0 / 1 / 4 / 5 (plus 2, 3, 6 as checks)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *  # noqa: E402,F403

ref = lab("R3fc4")
ok = (DEV.max(1) < 0.9)
lv = np.flatnonzero(NEUT & ok); lv = lv[np.argsort(DEVN[lv, 0])]
Cr = np.hypot(ref[:, 1], ref[:, 2])
levels = (0.011, 0.028, 0.057, 0.165, 0.428, 0.6)
print("ColorModel  menu item (from Phocus's code)      dE vs Standard  dE vs Reproduction  chroma ratio  grey L* at camera " + " / ".join(f"{t}" for t in levels))
for n, cm, menu in (("R3fc4", 0, "Standard"), ("R3cm1", 1, "Reproduction"), ("R3cm2", 2, "(skipped by the menu)"), ("R3cm3", 3, "(skipped by the menu)"),
                    ("R5cm4", 4, "Reproduction Low Gain"), ("R5cm5", 5, "Negative"), ("R5cm6", 6, "(beyond the menu)")):
    l = lab(n); C = np.hypot(l[:, 1], l[:, 2]); m = ok & (Cr > 10)
    g = [l[lv[np.argmin(np.abs(DEVN[lv, 0] - t))], 0] for t in levels]
    print(f"   {cm}        {menu:32s} {np.median(de2000(l[ok], ref[ok])):8.2f}   {np.median(de2000(l[ok], lab('R3cm1')[ok])):12.2f}      {np.median(C[m] / Cr[m]):8.3f}      " + " / ".join(f"{v:5.1f}" for v in g))
