"""Per-block mean Lab (averaged per pixel) of a Capture One ROMM render, on the same block grid and
alignment as a pairs.py npz, so it can be scored against the Phocus Lab stored there."""
import os
import sys

import numpy as np
import tifffile

sys.path.insert(0, os.path.dirname(__file__))
from icc import D50, xyz_to_lab  # noqa: E402
from pairs import PROPHOTO_M, crop_overlap, romm_decode  # noqa: E402


def block_lab(render_path, npz_path, phocus_shape, bs=32):
    z = np.load(npz_path)
    dy, dx = (int(v) for v in z["shift"])
    img = tifffile.imread(render_path)[..., :3]
    sa, _ = crop_overlap(img.shape, phocus_shape, dy, dx)
    A = img[sa]
    nb = int(z["nblocks"])
    H, W = A.shape[:2]
    nby, nbx = H // bs, W // bs
    assert nby * nbx == nb, (nby, nbx, nb)
    out = np.zeros((nby, nbx, 3), np.float32)
    white = (D50 / np.array([0.9642, 1.0, 0.82489])).astype(np.float32)
    for by0 in range(0, nby, 16):
        by1 = min(nby, by0 + 16)
        n = by1 - by0
        a = A[by0 * bs : by1 * bs, : nbx * bs].astype(np.float32) / 65535
        lab = xyz_to_lab((romm_decode(a.reshape(n, bs, nbx, bs, 3)) @ PROPHOTO_M.T.astype(np.float32)) * white)
        out[by0:by1] = lab.mean(axis=(1, 3))
    return out.reshape(-1, 3)
