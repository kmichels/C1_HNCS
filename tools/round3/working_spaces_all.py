"""Phocus's working spaces (sidecar ColorWorkingSpace 0-5) on the round-3 grid."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *  # noqa: E402,F403

names = {0: "Hasselblad RGB (menu)", 1: "Hasselblad L* RGB (menu)", 2: "ProPhoto primaries, L*", 3: "XYZ D50, L*, no Hasselblad RGB step",
         4: "XYZ D50, L*, via Hasselblad RGB", 5: "ProPhoto primaries, L* (built differently)"}
files = {0: "R3fc4", 1: "R4cws1", 2: "R4cws2", 3: "R4cws3", 4: "R6cws4", 5: "R6cws5"}
L = {k: lab(v) for k, v in files.items()}
ok = DEV.max(1) < 0.9
lv = np.flatnonzero(NEUT & ok); lv = lv[np.argsort(DEVN[lv, 0])]
Cr = np.hypot(L[0][:, 1], L[0][:, 2])
print("value  space                                    dE vs 0   chroma ratio   grey L* at camera 0.028 / 0.165 / 0.428")
for k, nm in names.items():
    l = L[k]; C = np.hypot(l[:, 1], l[:, 2]); m = ok & (Cr > 10)
    g = [l[lv[np.argmin(np.abs(DEVN[lv, 0] - t))], 0] for t in (0.028, 0.165, 0.428)]
    print(f"  {k}    {nm:42s} {np.median(de2000(l[ok], L[0][ok])):6.2f}   {np.median(C[m] / Cr[m]):8.3f}      " + " / ".join(f"{v:5.1f}" for v in g))
print("\npairwise median dE00:")
print("      " + "".join(f"{k:7d}" for k in names))
for a in names:
    print(f"  {a}   " + "".join(f"{np.median(de2000(L[a][ok], L[b][ok])):7.2f}" for b in names))
