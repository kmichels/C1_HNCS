"""Median L*, a*, b* offset of near-neutral blocks (Phocus C* < 10), Capture One render minus Phocus export.

usage: python neutral_offset.py PHOCUS.tif RENDER.tif [RENDER.tif ...]
"""
import os
import sys

import numpy as np
import tifffile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from icc import D50, xyz_to_lab  # noqa: E402
from pairs import PROPHOTO_M, phocus_decode, romm_decode  # noqa: E402

W = D50 / np.array([0.9642, 1.0, 0.82489])


def blocks(p, dec, b=32):
    im = tifffile.imread(p)[..., :3].astype(np.float32) / 65535
    h, w = (im.shape[0] // b) * b, (im.shape[1] // b) * b
    m = im[:h, :w].reshape(h // b, b, w // b, b, 3).mean(axis=(1, 3))
    return xyz_to_lab((dec(m.reshape(-1, 3)) @ PROPHOTO_M.T) * W)


P = blocks(sys.argv[1], phocus_decode)
for p in sys.argv[2:]:
    C = blocks(p, romm_decode)
    m = (P[:, 0] > 5) & (P[:, 0] < 95) & (C[:, 0] < 95) & (np.hypot(P[:, 1], P[:, 2]) < 10)
    d = np.median(C[m] - P[m], axis=0)
    print(f"{os.path.basename(p)}: near-neutral blocks {int(m.sum())}: dL {d[0]:+.2f} da {d[1]:+.2f} db {d[2]:+.2f}")
