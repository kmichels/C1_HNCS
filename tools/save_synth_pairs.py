"""Save one synthetic grid's pairs (Capture One probe camera RGB and Phocus's output, per patch) as an npz,
the format of fit/synthetic/pairs/ that fit_synthetic.py --pairs reads.

usage: python save_synth_pairs.py PATCHES.npz C1_PROBE.tif PHOCUS.tif OUT.npz
  C1_PROBE.tif may be "-": Capture One's camera RGB is then taken from fit/c1_patch_lookup.npz (measured
  for every patch value of the standard 22- and 33-level grids, and the same for any white balance and
  lens), falling back to its response curve (fit/c1_response.npz) for other values.
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


FIT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "fit")
if c1p == "-":
    lk = np.load(os.path.join(FIT, "c1_patch_lookup.npz"))
    table = {tuple(np.round(k.astype(np.float64), 6)): v.astype(np.float64) for k, v in zip(lk["nominal"], lk["c1"])}
    rz = np.load(os.path.join(FIT, "c1_response.npz"))
    lin = np.array([table.get(tuple(np.round(d, 6)), np.interp(d, rz["nominal"], rz["c1"])) for d in z["device"]])
    missing = sum(tuple(np.round(d, 6)) not in table for d in z["device"])
    if missing:
        print(f"{missing} patch values not in the lookup; used the response curve for them")
    c1 = np.where(lin > 0, np.maximum(lin, 0) ** (1 / 1.8), 0)  # stored for reference only
else:
    c1 = patch_means(tifffile.imread(c1p)[..., :3].astype(np.float64) / 65535)
    lin = np.clip(romm_decode(c1), 0, None)
ph = patch_means(tifffile.imread(php)[..., :3].astype(np.float64) / 65535)
white = D50 / np.array([0.9642, 1.0, 0.82489])
np.savez_compressed(out, c1_romm=c1, phocus_prophoto=ph, device_nominal=z["device"], pos=pos, patch=P, active=z["active"],
                    neutral=z["neutral"], lab=xyz_to_lab((phocus_decode(ph) @ PROPHOTO_M.T) * white), device_c1_lin=lin)
print(f"wrote {out}: {len(pos)} patches, neutral {np.round(z['neutral'], 4)}")
