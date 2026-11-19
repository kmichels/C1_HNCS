"""Does Phocus apply a third body's factory gains as body_gains.py predicts?

The round-11 ladder rendered by Phocus twice: as is (owner's GAIN record) and with maker-note 0x0019 from
another body. Prediction: the second render equals the first with camera RGB scaled by body_gains.py's
(1, kG, kB), evaluated through HNCS E5 35-100 on Capture One's camera RGB for each patch (probe render).
Run from the repo root after the renders exist in data/synth/r11/phocus/HNCSnc{,Body3}_body.npy.

usage: python tools/round13/body_test.py KG KB
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from fit import de2000, tetra_weights  # noqa: E402
from icc import D50, xyz_to_lab  # noqa: E402
from pairs import PROPHOTO_M, phocus_decode, romm_decode  # noqa: E402

R = "data/synth/r11"
W = D50 / np.array([0.9642, 1.0, 0.82489])
kG, kB = (float(v) for v in sys.argv[1:3])
meta = np.load(f"{R}/ladder_meta.npy")
hue, sat, lev = meta.T
ph = lambda k: xyz_to_lab((phocus_decode(np.load(f"{R}/phocus/{k}.npy")) @ PROPHOTO_M.T) * W)
own, other = ph("HNCSnc_body"), ph("HNCSncBody3_body")
probe = np.load(f"{R}/probe/HNCSnc.npy")
ok = ((probe * 65535 > 1) & (probe * 65535 < 65534)).all(1) & (lev <= 0.71) & (own[:, 0] > 5)
lin = np.clip(romm_decode(probe), 0, None)
lut = np.load("fit/lut_e5_35-100.npz")["lut"]
pred_own = tetra_weights(lin ** (1 / 1.8)) @ lut
pred_other = tetra_weights(np.clip(lin * np.array([1.0, kG, kB]), 0, 1) ** (1 / 1.8)) @ lut
meas, pred = other - own, pred_other - pred_own
g = ok & (sat == 0)
c = ok & (sat > 0)
print(f"body gains kG {kG}, kB {kB}; {int(ok.sum())} patches")
print(f"greys:   measured da* {np.median(meas[g, 1]):+.2f} db* {np.median(meas[g, 2]):+.2f} | predicted da* {np.median(pred[g, 1]):+.2f} db* {np.median(pred[g, 2]):+.2f}")
print(f"colours: measured |dLab| median {np.median(np.linalg.norm(meas[c], axis=1)):.2f}; predicted {np.median(np.linalg.norm(pred[c], axis=1)):.2f}")
print(f"Phocus own vs other record, median dE00: {np.median(de2000(own[ok], other[ok])):.2f}")
print(f"other-record render vs prediction (own render shifted by the predicted change), median dE00: "
      f"{np.median(de2000(other[ok], own[ok] + pred[ok])):.2f} (p90 {np.percentile(de2000(other[ok], own[ok] + pred[ok]), 90):.2f})")
for name, k in (("no correction", (1.0, 1.0)), ("formula", (kG, kB))):
    p2 = tetra_weights(np.clip(lin * np.array([1.0, *k]), 0, 1) ** (1 / 1.8)) @ lut
    print(f"  {name:14s}: E5 table on scaled camera RGB vs the other-record Phocus render, median dE00 {np.median(de2000(p2[ok], other[ok])):.2f}; greys da*/db* {np.median((p2 - other)[g, 1]):+.2f}/{np.median((p2 - other)[g, 2]):+.2f}")
