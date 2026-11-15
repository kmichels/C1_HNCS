"""Compare highlight handling in Phocus and Capture One on a synthetic exposure ladder through raw clipping.

The test raw (make_synthetic_raw.py --device-npy, --scale 1.0) holds 37 colours (greys; 12 hues at
saturation 0.3, 0.6, 0.9) at 17 exposures from 2 stops under to 2 stops over the point where their
brightest channel reaches the sensor's white level. Raw values above white are clipped, as on a sensor.

usage: python highlight_test.py PATCHES.npz META.npy PHOCUS_DIR C1_DIR
  PHOCUS_DIR: default.tif plus variants (rec50.tif …); C1_DIR: H0.tif, H100.tif (Capture One, HNCS E5)
"""
import glob
import os
import sys

import numpy as np
import tifffile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from icc import D50, de2000, xyz_to_lab  # noqa: E402
from pairs import PROPHOTO_M, phocus_decode, romm_decode  # noqa: E402

z = np.load(sys.argv[1]); meta = np.load(sys.argv[2])
pos, P, dev, neutral = z["pos"], int(z["patch"]), z["device"], z["neutral"]
white = D50 / np.array([0.9642, 1.0, 0.82489])


def lab_of(path, decode):
    img = tifffile.imread(path)[..., :3].astype(np.float64) / 65535
    s_ = P // 2; m = s_ // 4
    v = np.array([img[y // 2 + m: y // 2 + s_ - m, x // 2 + m: x // 2 + s_ - m].reshape(-1, 3).mean(0) for y, x in pos])
    return xyz_to_lab((decode(v) @ PROPHOTO_M.T) * white)


ph = {os.path.basename(f)[:-4]: lab_of(f, phocus_decode) for f in sorted(glob.glob(os.path.join(sys.argv[3], "*.tif")))}
c1 = {os.path.basename(f)[:-4]: lab_of(f, romm_decode) for f in sorted(glob.glob(os.path.join(sys.argv[4], "*.tif")))}
nclip = (dev * neutral >= 1.0).sum(1)
hue, sat, expo = meta[:, 0], meta[:, 1], meta[:, 2]
H = lambda l: np.degrees(np.arctan2(l[:, 2], l[:, 1])) % 360
C = lambda l: np.hypot(l[:, 1], l[:, 2])

print("1. Greys: exposure (x clip point of green) -> L* a* b*")
g = np.flatnonzero(sat == 0); g = g[np.argsort(expo[g])]
cols = [("Phocus", ph["default"]), ("Phocus rec50", ph.get("rec50")), ("Phocus rec100", ph.get("rec100")), ("C1 HNCS", c1["H0"]),
        ("C1 Highlight -100", c1.get("Hm100")), ("C1 White -100", c1.get("Wm100"))]
print("   exp  clipped  " + "".join(f"{n:>24s}" for n, _ in cols))
for i in g:
    print(f"   {expo[i]:4.2f}   {nclip[i]}     " + "".join(f"   {L[i,0]:5.1f} {L[i,1]:+5.1f} {L[i,2]:+5.1f}  " if L is not None else "" for _, L in cols))

print("\n2. Colours: Phocus vs Capture One (HNCS E5, defaults), median dE00 by number of clipped raw channels")
for k in range(4):
    m = (sat > 0) & (nclip == k)
    if m.sum():
        print(f"   {k} clipped ({m.sum():3d} patches): dE00 {np.median(de2000(ph['default'][m], c1['H0'][m])):5.2f}; "
              f"L* Phocus {np.median(ph['default'][m, 0]):5.1f} vs C1 {np.median(c1['H0'][m, 0]):5.1f}; "
              f"chroma Phocus {np.median(C(ph['default'][m])):5.1f} vs C1 {np.median(C(c1['H0'][m])):5.1f}")

print("\n3. Hue drift past clipping: per colour, hue at each clipped exposure minus hue at its last unclipped exposure (median |deg|, by saturation)")
for s_ in (0.3, 0.6, 0.9):
    rows = {n: [] for n in ("Phocus", "C1")}
    for h in np.unique(hue[sat == s_]):
        idx = np.flatnonzero((sat == s_) & (hue == h)); idx = idx[np.argsort(expo[idx])]
        ref = [i for i in idx if nclip[i] == 0]
        if not ref:
            continue
        r = ref[-1]
        for n, L in (("Phocus", ph["default"]), ("C1", c1["H0"])):
            for i in idx:
                if nclip[i] > 0 and C(L[i:i + 1])[0] > 3:
                    rows[n].append(abs(((H(L[i:i + 1])[0] - H(L[r:r + 1])[0] + 180) % 360) - 180))
    print(f"   saturation {s_}: Phocus {np.median(rows['Phocus']):5.1f} deg, Capture One {np.median(rows['C1']):5.1f} deg")

print("\n4. What Phocus's highlight settings change (median dE00 vs default, by clipped channels 0/1/2/3)")
for n, L in ph.items():
    if n == "default":
        continue
    print(f"   {n:10s} " + "  ".join(f"{np.median(de2000(L[nclip == k], ph['default'][nclip == k])):5.2f}" for k in range(4)))
if "H100" in c1:
    print(f"   C1 Highlight 100 vs C1 default: " + "  ".join(f"{np.median(de2000(c1['H100'][nclip == k], c1['H0'][nclip == k])):5.2f}" for k in range(4)))

print("\n5. Lightness as exposure rises past clipping (saturation 0.6, median over hues): exposure -> L* Phocus | C1")
for e in np.unique(expo):
    m = (sat == 0.6) & (expo == e)
    print(f"   {e:4.2f}: {np.median(ph['default'][m, 0]):5.1f} | {np.median(c1['H0'][m, 0]):5.1f}   (clipped channels {np.round(np.mean(nclip[m]), 1)})")

print("\n6. Detail past clipping: how many distinct lightness steps each rendering keeps among the 9 exposures from")
print("   the clip point (x1) to 2 stops over (x4), greys and saturation 0.6 (L* differences > 0.5 between steps)")
for n, L in [("Phocus", ph["default"]), ("Phocus rec50", ph.get("rec50")), ("Phocus rec100", ph.get("rec100")),
             ("C1 HNCS", c1["H0"]), ("C1 Highlight -100", c1.get("Hm100")), ("C1 White -100", c1.get("Wm100"))]:
    if L is None:
        continue
    steps = []
    for s_ in (0.0, 0.6):
        for h in np.unique(hue[sat == s_]):
            idx = np.flatnonzero((sat == s_) & (hue == h) & (expo >= 1.0)); idx = idx[np.argsort(expo[idx])]
            steps.append(int((np.abs(np.diff(L[idx, 0])) > 0.5).sum()))
    clipped = (sat > 0) & (nclip == 1)
    print(f"   {n:18s} distinct steps median {np.median(steps):.0f} of 8; one-channel-clipped colours: L* {np.median(L[clipped, 0]):5.1f}, chroma {np.median(C(L[clipped])):5.1f}")
