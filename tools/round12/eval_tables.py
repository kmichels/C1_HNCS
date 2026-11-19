"""Score fitted tables offline, as Capture One would apply them once written as profiles.

- Ladder (round 11): Capture One's camera RGB per patch from a probe render (data/synth/r11/probe/), through
  each table, against Phocus's Lab (data/synth/r11/phocus/). Bands by the brightest raw channel's level.
- Real held-out pairs (data/pairs_35100 or data/pairs_28p): median dE00 per frame, frame centre.

A table saved without the `finalized` flag is finalized once more, as write_profile.py does for it.

usage: python eval_tables.py PAIRS_DIR LUT.npz [LUT.npz ...]   (run from the repo root)
"""
import glob
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from fit import G, de2000, load_frame, tetra_weights  # noqa: E402
from icc import D50, xyz_to_lab  # noqa: E402
from pairs import PROPHOTO_M, phocus_decode, romm_decode  # noqa: E402
from write_profile import finalize  # noqa: E402

R11 = "data/synth/r11"
W_ = D50 / np.array([0.9642, 1.0, 0.82489])
C = lambda lab: np.hypot(lab[:, 1], lab[:, 2])
med = np.median


def written(path):
    z = np.load(path)
    lut = z["lut"].reshape(G, G, G, 3)
    return (lut if "finalized" in z and bool(z["finalized"]) else finalize(lut)).reshape(-1, 3)


meta = np.load(f"{R11}/ladder_meta.npy")
hue, sat, lev = meta.T
probe = np.load(f"{R11}/probe/HNCSnc.npy")
ok = ((probe * 65535 > 1) & (probe * 65535 < 65534)).all(1)  # the probe clips camera RGB above 1: those patches can't be scored offline
dev = np.clip(romm_decode(probe), 0, None) ** (1 / 1.8)
Wl = tetra_weights(dev)
ph = xyz_to_lab((phocus_decode(np.load(f"{R11}/phocus/HNCSnc.npy")) @ PROPHOTO_M.T) * W_)
c1_actual = xyz_to_lab((romm_decode(np.load(f"{R11}/c1/HNCSnc.npy")) @ PROPHOTO_M.T) * W_)
frames = sorted(glob.glob(os.path.join(sys.argv[1], "*.npz")))
fr = [load_frame(f) for f in frames]
bands = [("<=0.50", ok & (lev <= 0.5)), ("0.59-0.84", ok & (lev > 0.5) & (lev <= 0.85)), ("0.88-0.99", ok & (lev > 0.85) & (lev < 1))]
groups = [("yellow-orange 30-90", np.isin(hue, (30, 60, 90))), ("other hues", ~np.isin(hue, (30, 60, 90, 240)))]
for path in sys.argv[2:]:
    lut = written(path)
    lab = Wl @ lut
    print(f"\n{path}")
    if "lut_e5_35-100" in path:
        print(f"  check: offline vs Capture One's actual render, median dE00 {med(de2000(lab, c1_actual)):.3f} (p90 {np.percentile(de2000(lab, c1_actual), 90):.3f})")
    d = de2000(lab, ph)
    g = ok & (sat == 0)
    print(f"  ladder greys dE00 median {med(d[g]):.2f} max {d[g].max():.2f}; grey |a*|,|b*| max {np.abs(lab[g, 1:]).max():.2f}")
    for gname, gm in groups:
        row = "  " + f"{gname:20s}"
        for b, bm in bands:
            m = gm & bm & (sat >= 0.6)
            row += f"  {b} {med(d[m]):5.2f} (dC* {med(C(lab[m]) - C(ph[m])):+6.1f})"
        print(row)
    m = ok & (sat > 0) & (lev < 1)
    print(f"  all colours the probe can score ({int(m.sum())}): {med(d[m]):.2f}, p90 {np.percentile(d[m], 90):.2f}")
    per = [med(de2000(f["W"] @ lut, f["lab"])) for f in fr]
    print(f"  real held-out ({len(fr)} frames): mean of medians {np.mean(per):.3f}, worst {max(per):.2f}; "
          f"near-white blocks (Phocus L* > 90): {med(np.concatenate([de2000(f['W'] @ lut, f['lab'])[f['lab'][:, 0] > 90] for f in fr])):.2f}")
