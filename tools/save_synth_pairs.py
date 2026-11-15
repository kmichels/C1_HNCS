"""Save one synthetic grid's pairs (Capture One probe camera RGB and Phocus's output, per patch) as an npz,
the format of fit/synthetic/pairs/ that fit_synthetic.py --pairs reads.

usage: python save_synth_pairs.py PATCHES.npz C1_PROBE.tif PHOCUS.tif OUT.npz
"""
import os
import sys

import numpy as np
import tifffile

sys.path.insert(0, os.path.dirname(__file__))
from icc import D50, xyz_to_lab  # noqa: E402
from pairs import PROPHOTO_M, phocus_decode, romm_decode  # noqa: E402

pz, c1p, php, out = sys.argv[1:5]
z = np.load(pz)
pos, P = z["pos"], int(z["patch"])


def patch_means(img):
    s_ = P // 2
    m = s_ // 4
    return np.array([img[y // 2 + m: y // 2 + s_ - m, x // 2 + m: x // 2 + s_ - m].reshape(-1, 3).mean(0) for y, x in pos])


c1 = patch_means(tifffile.imread(c1p)[..., :3].astype(np.float64) / 65535)
ph = patch_means(tifffile.imread(php)[..., :3].astype(np.float64) / 65535)
white = D50 / np.array([0.9642, 1.0, 0.82489])
np.savez_compressed(out, c1_romm=c1, phocus_prophoto=ph, device_nominal=z["device"], pos=pos, patch=P, active=z["active"],
                    neutral=z["neutral"], lab=xyz_to_lab((phocus_decode(ph) @ PROPHOTO_M.T) * white), device_c1_lin=np.clip(romm_decode(c1), 0, None))
print(f"wrote {out}: {len(pos)} patches, neutral {np.round(z['neutral'], 4)}")
