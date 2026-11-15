"""Compare Phocus hot-folder exports of synthetic raws that share the same patch layout.

For each named file, finds its export via the .phos sidecar, reads the patch centres, and reports how far
it is from two reference files (median dE00 over patches, and the mean shift on grey patches). A file that
matches reference A and not B carries A's behaviour.

usage: python synth_compare.py RAW_DIR EXPORT_DIR PATCHES.npz REF_A REF_B NAME [NAME ...]
  names are file stems without .3fr (e.g. HNCSsynth03)
"""
import os
import plistlib
import sys

import numpy as np
import tifffile

sys.path.insert(0, os.path.dirname(__file__))
from icc import D50, de2000, xyz_to_lab  # noqa: E402
from pairs import PROPHOTO_M, phocus_decode  # noqa: E402

RAW, EXP, PATCHES, A, B = sys.argv[1:6]
NAMES = sys.argv[6:]
z = np.load(PATCHES)
pos, P, devn = z["pos"], int(z["patch"]), z["device"]
s_ = P // 2
m = s_ // 4
white = D50 / np.array([0.9642, 1.0, 0.82489])


def lab_of(stem):
    p = plistlib.load(open(os.path.join(RAW, stem + ".3fr.phos"), "rb"))
    e = p["ImageSettings"][p["CurrentIx"]].get("ExportName", "")
    img = tifffile.imread(os.path.join(EXP, e))[..., :3].astype(np.float64) / 65535
    v = np.array([img[y // 2 + m: y // 2 + s_ - m, x // 2 + m: x // 2 + s_ - m].reshape(-1, 3).mean(0) for y, x in pos])
    return xyz_to_lab((phocus_decode(v) @ PROPHOTO_M.T) * white), e


L = {n: lab_of(n) for n in [A, B] + NAMES}
neut = np.ptp(devn, axis=1) < 1e-9
ok = np.all([L[n][0][:, 0] > 2 for n in L], axis=0)


def cmp(a, b):
    d = de2000(L[a][0], L[b][0])
    dd = L[a][0] - L[b][0]
    g = neut & ok
    return f"dE {np.median(d[ok]):.2f} | greys dL {dd[g, 0].mean():+.2f} da {dd[g, 1].mean():+.2f} db {dd[g, 2].mean():+.2f}"


print(f"{A} vs {B}: {cmp(A, B)}")
for n in NAMES:
    print(f"{n:14s} vs {A}: {cmp(n, A)}   ||   vs {B}: {cmp(n, B)}")
