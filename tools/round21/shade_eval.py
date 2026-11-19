"""Score profile tables offline across white balance (Finding 44): Finding 33's grids at 4200-8000 K (35-100
host, on the daylight locus; Phocus's patch means in data/synth/r11/phocus/) and any saved pairs sets. Capture
One's camera RGB per patch comes from fit/c1_patch_lookup.npz, through each table as Capture One would apply
it once written. Median ΔE00 on patches whose brightest raw channel is below 0.5 and Phocus L* above 8, by
Phocus chroma, as in Finding 33.

usage: python shade_eval.py LUT.npz [LUT.npz ...] [--pairs PAIRS.npz ...]   (run from the repo root)
"""
import argparse
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from fit import G, predict  # noqa: E402
from icc import D50, de2000, xyz_to_lab  # noqa: E402
from pairs import PROPHOTO_M, phocus_decode  # noqa: E402
from write_profile import finalize  # noqa: E402

R11 = "data/synth/r11"
W_ = D50 / np.array([0.9642, 1.0, 0.82489])
C = lambda lab: np.hypot(lab[:, 1], lab[:, 2])  # noqa: E731
lk = np.load("fit/c1_patch_lookup.npz")
LOOKUP = {tuple(np.round(k.astype(np.float64), 6)): v.astype(np.float64) for k, v in zip(lk["nominal"], lk["c1"])}
rz = np.load("fit/c1_response.npz")


def written(path):
    z = np.load(path)
    lut = z["lut"].reshape(G, G, G, 3)
    return (lut if "finalized" in z and bool(z["finalized"]) else finalize(lut)).reshape(-1, 3)


def c1_dev(device):
    lin = np.array([LOOKUP.get(tuple(np.round(d, 6)), np.interp(d, rz["nominal"], rz["c1"])) for d in device])
    return np.clip(lin, 0, None) ** (1 / 1.8)


def row(lut, dev, P, ok):
    d = de2000(predict(lut, dev), P)
    cp = C(P)
    out = []
    for lo, hi in ((20, 40), (40, 60)):
        m = ok & (cp >= lo) & (cp < hi)
        out.append(np.median(d[m]))
    out.append(np.median(d[ok]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("luts", nargs="+")
    ap.add_argument("--pairs", action="append", default=[])
    a = ap.parse_args()
    luts = [(os.path.basename(p)[:-4], written(p)) for p in a.luts]
    print("ΔE00 medians: C* 20-40 | C* 40-60 | all (patches below raw 0.5)")
    print(f"{'grid':22s} " + "".join(f"{n:>26s}" for n, _ in luts))
    for T in (4200, 4500, 5000, 5500, 6000, 6500, 7000, 7500, 8000):
        z = np.load(f"{R11}/HNCSwb{T}.patches.npz")
        raw = z["device"] * z["neutral"] * float(z["scale"])
        P = xyz_to_lab((phocus_decode(np.load(f"{R11}/phocus/HNCSwb{T}.npy")) @ PROPHOTO_M.T) * W_)
        ok = (raw.max(1) < 0.5) & (P[:, 0] > 8)
        dev = c1_dev(z["device"])
        print(f"{'locus ' + str(T) + ' K':22s} " + "".join("    {:5.2f} | {:5.2f} | {:5.2f}".format(*row(l, dev, P, ok)) for _, l in luts))
    for p in a.pairs:
        z = np.load(p)
        raw = z["device_nominal"] * z["neutral"]
        ok = (raw.max(1) < 0.5 * raw.max()) & (z["lab"][:, 0] > 8)
        dev = np.clip(z["device_c1_lin"], 0, None) ** (1 / 1.8)
        print(f"{os.path.basename(p)[:-4][:22]:22s} " + "".join("    {:5.2f} | {:5.2f} | {:5.2f}".format(*row(l, dev, z['lab'], ok)) for _, l in luts))


if __name__ == "__main__":
    main()
