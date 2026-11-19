"""Round 11 (Finding 33): Phocus vs Capture One + HNCS E5 35-100 on synthetic patches.

A. Bright colours: 12 hues at saturation 0.3/0.6/0.9 plus grey, each at 23 levels of its brightest raw
   channel (1/16 to 1.0 of the white level, finer steps from 0.71), at EV 0.
B. Exposure pushes: the same raw rendered at +1 and +2 EV in both apps (Phocus sidecar EV 2.0 / 4.0,
   Capture One exposure 1 / 2), compared with each other and with the unpushed patch at 2x / 4x level.
C. White balance: a 9-level colour grid at As Shot neutrals for 4200-8000 K.
D. Lightness and chroma by level for a few hues.

Run from data/synth/r11/ after render_phocus.py and render_c1.applescript (patch means in phocus/ and c1/).
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from icc import D50, de2000, xyz_to_lab  # noqa: E402
from pairs import PROPHOTO_M, phocus_decode, romm_decode  # noqa: E402

W = D50 / np.array([0.9642, 1.0, 0.82489])
ph = lambda k: xyz_to_lab((phocus_decode(np.load(f"phocus/{k}.npy")) @ PROPHOTO_M.T) * W)
c1 = lambda k: xyz_to_lab((romm_decode(np.load(f"c1/{k}.npy")) @ PROPHOTO_M.T) * W)
C = lambda lab: np.hypot(lab[:, 1], lab[:, 2])
dh = lambda a, b: (np.degrees(np.arctan2(a[:, 2], a[:, 1]) - np.arctan2(b[:, 2], b[:, 1])) + 180) % 360 - 180
med = np.median

meta = np.load("ladder_meta.npy")
hue, sat, lev = meta.T
P0, C0 = ph("HNCSnc"), c1("HNCSnc")
d0 = de2000(P0, C0)

print("A. Bright colours (EV 0). Median dE00 Phocus vs Capture One by brightest raw channel level")
print("   level   grey dE  (L* Phocus/C1)   colours dE   dL* (C1-Phocus)  dC* (C1-Phocus)")
for r in np.unique(lev):
    g = (lev == r) & (sat == 0)
    m = (lev == r) & (sat > 0)
    print(f"   {r:.3f}   {d0[g][0]:5.2f}  ({P0[g, 0][0]:5.1f}/{C0[g, 0][0]:5.1f})      {med(d0[m]):5.2f}        "
          f"{med(C0[m, 0] - P0[m, 0]):+5.2f}           {med(C(C0[m]) - C(P0[m])):+5.2f}")
bands = [("0.06-0.50", lev <= 0.5), ("0.59-0.84", (lev > 0.5) & (lev <= 0.85)), ("0.88-0.99", (lev > 0.85) & (lev < 1.0))]
print("\n   by hue, saturation 0.6 and 0.9: median dE00 (dL*, dC*, dh in degrees; Capture One minus Phocus)")
print("   hue   " + "".join(f"{b:>34s}" for b, _ in bands))
for h in np.unique(hue[sat > 0]):
    row = f"   {h:3.0f}  "
    for _, bm in bands:
        m = bm & (hue == h) & (sat >= 0.6)
        row += f"   {med(d0[m]):5.2f} ({med(C0[m, 0] - P0[m, 0]):+5.1f},{med(C(C0[m]) - C(P0[m])):+5.1f},{med(dh(C0[m], P0[m])):+5.1f})"
    print(row)
for s in (0.3, 0.6, 0.9):
    print(f"   sat {s}: " + "  ".join(f"{b} {med(d0[bm & (sat == s)]):.2f} (max {d0[bm & (sat == s)].max():.2f})" for b, bm in bands))

print("\nB. Exposure pushes. Patches whose pushed level stays at or below 0.84")


def at(factor):
    """Index of the same colour at FACTOR x the level, or -1."""
    out = np.full(len(meta), -1)
    for i, (h, s, r) in enumerate(meta):
        j = np.flatnonzero((hue == h) & (sat == s) & np.isclose(lev, r * factor, rtol=2e-3))
        if len(j):
            out[i] = j[0]
    return out


for key, ev in (("HNCSncE2", 1), ("HNCSncE4", 2)):
    Pk, Ck = ph(key), c1(key)
    f = 2 ** ev
    j = at(f)
    m = (lev * f <= 0.845) & (j >= 0)
    dk = de2000(Pk, Ck)
    print(f"   +{ev} EV: Phocus vs C1 dE00 median {med(dk[m]):.2f} (p90 {np.percentile(dk[m], 90):.2f}); "
          f"C1-Phocus dC* {med(C(Ck[m]) - C(Pk[m])):+.2f}, dL* {med(Ck[m, 0] - Pk[m, 0]):+.2f}")
    print(f"          the same colours unpushed at {f}x the level: dE00 {med(d0[j[m]]):.2f}; dC* {med(C(C0[j[m]]) - C(P0[j[m]])):+.2f}")
    print(f"          push vs more light, within each app: Phocus dE00 {med(de2000(Pk[m], P0[j[m]])):.2f}, "
          f"C1 dE00 {med(de2000(Ck[m], C0[j[m]])):.2f}")
    for s in (0.3, 0.6, 0.9):
        ms = m & (sat == s)
        print(f"          sat {s}: dE00 {med(dk[ms]):.2f}, dC* {med(C(Ck[ms]) - C(Pk[ms])):+.2f}")

print("\nC. White balance. Patches with brightest raw channel < 0.5; median dE00 by Phocus chroma (n), and greys")
print("   K       C*<20        20-40        40-60        60+          all   p90   grey da* db* (C1-Phocus)")
for T in (4200, 4500, 5000, 5500, 6000, 6500, 7000, 7500, 8000):
    z = np.load(f"HNCSwb{T}.patches.npz")
    dev = z["device"]
    raw = dev * z["neutral"] * float(z["scale"])
    P, Q = ph(f"HNCSwb{T}"), c1(f"HNCSwb{T}")
    d = de2000(P, Q)
    ok = (raw.max(1) < 0.5) & (P[:, 0] > 8)
    grey = ok & (np.ptp(dev, 1) < 1e-9)
    cp = C(P)
    row = f"   {T}  "
    for lo, hi in ((0, 20), (20, 40), (40, 60), (60, 999)):
        m = ok & (cp >= lo) & (cp < hi)
        row += f"  {med(d[m]):5.2f} ({m.sum():3d})"
    print(row + f"   {med(d[ok]):5.2f} {np.percentile(d[ok], 90):5.2f}   {med(Q[grey, 1] - P[grey, 1]):+5.2f} {med(Q[grey, 2] - P[grey, 2]):+5.2f}")

print("\nD. L*/C* by level from 0.25, Phocus | Capture One")
for h, s in ((60, 0.6), (60, 0.9), (30, 0.9), (180, 0.9), (300, 0.9), (330, 0.6), (240, 0.6), (0, 0.6)):
    idx = np.flatnonzero((hue == h) & (sat == s))
    idx = idx[np.argsort(lev[idx])]
    print(f"   hue {h} sat {s}: " + "  ".join(f"{lev[i]:.2f}:{P0[i, 0]:.0f}/{C(P0)[i]:.0f}|{C0[i, 0]:.0f}/{C(C0)[i]:.0f}"
                                         for i in idx if lev[i] >= 0.25))
