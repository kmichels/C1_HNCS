"""What changes in Phocus's colour transform with white balance.

For synthetic patch pairs rendered at different As Shot white balances, compares Phocus's output with a
reference table fitted at one white balance, after letting a simple correction absorb the difference:
  none   the reference table as is
  diag   per-channel gains on white-balanced camera RGB before the table (a white-balance tweak)
  3x3    a full 3x3 matrix on camera RGB before the table (a different colour matrix, as in a dual-
         illuminant DNG profile)
  post   a 3x3 matrix on the output (XYZ) after the table (a chromatic adaptation after the transform)
Corrections are fitted on moderate colours (camera-RGB saturation < 0.6); near-whites (L* > 93), where
the tables fit worst, are left out. If "3x3" brings the difference down to the reference table's own fit error, the white-balance
dependence is a change of colour matrix.

usage: python hncs_wb_structure.py LUT.npz GAINMAP.npz REF_PAIRS.npz[,...] PAIRS.npz [PAIRS.npz ...]
"""
import os
import sys

import numpy as np
from scipy.optimize import least_squares

sys.path.insert(0, os.path.dirname(__file__))
from fit import predict  # noqa: E402
from icc import de2000, lab_to_xyz, xyz_to_lab  # noqa: E402

lut = np.load(sys.argv[1])["lut"]
gm = np.load(sys.argv[2])


def load(f):
    z = np.load(f)
    pos, P = z["pos"], int(z["patch"])
    gb = int(gm["block"])
    gy = np.clip(((pos[:, 0] + P / 2) / 2 // gb).astype(int), 0, gm["gain"].shape[0] - 1)
    gx = np.clip(((pos[:, 1] + P / 2) / 2 // gb).astype(int), 0, gm["gain"].shape[1] - 1)
    lin = z["device_c1_lin"] * gm["gain"][gy, gx]
    ok = (lin.max(1) ** (1 / 1.8) < 0.95) & (z["phocus_prophoto"].max(1) < 0.995) & (z["phocus_prophoto"].min(1) > 2 / 65535) & (z["lab"][:, 0] > 3) & (z["lab"][:, 0] < 93)
    sat = 1 - lin.min(1) / np.maximum(lin.max(1), 1e-9)
    return lin[ok], z["lab"][ok], sat[ok], z["neutral"]


def pred(lin, M=None, post=None):
    x = lin if M is None else np.maximum(lin @ M.T, 0)
    out = predict(lut, np.clip(x, 0, 1) ** (1 / 1.8))
    if post is not None:
        out = xyz_to_lab(np.maximum(lab_to_xyz(out) @ post.T, 1e-9))
    return out


rng = np.random.default_rng(0)
print("set        R/B neutral   median dE00 (moderate colours, s < 0.6 | all)        fitted")
print("                          none        diag        3x3         post")
for spec in sys.argv[3:]:
    parts = [load(f) for f in spec.split(",")]
    lin = np.concatenate([p[0] for p in parts]); lab = np.concatenate([p[1] for p in parts]); sat = np.concatenate([p[2] for p in parts])
    nt = parts[0][3]
    m = sat < 0.6
    sub = rng.choice(np.flatnonzero(m), min(int(m.sum()), 6000), replace=False)
    res = {}
    res["none"] = de2000(pred(lin), lab)
    r = least_squares(lambda k: (pred(lin[sub], np.diag(np.exp(k))) - lab[sub]).ravel(), np.zeros(3), loss="soft_l1", f_scale=2.0)
    Md = np.diag(np.exp(r.x)); res["diag"] = de2000(pred(lin, Md), lab)
    r = least_squares(lambda k: (pred(lin[sub], (np.eye(3) + k.reshape(3, 3))) - lab[sub]).ravel(), np.zeros(9), loss="soft_l1", f_scale=2.0)
    M3 = np.eye(3) + r.x.reshape(3, 3); res["3x3"] = de2000(pred(lin, M3), lab)
    r = least_squares(lambda k: (pred(lin[sub], post=np.eye(3) + k.reshape(3, 3)) - lab[sub]).ravel(), np.zeros(9), loss="soft_l1", f_scale=2.0)
    Mp = np.eye(3) + r.x.reshape(3, 3); res["post"] = de2000(pred(lin, post=Mp), lab)
    name = os.path.basename(spec.split(",")[0]).replace(".npz", "")
    cols = "  ".join(f"{np.median(res[k][m]):4.2f}|{np.median(res[k]):4.2f}" for k in ("none", "diag", "3x3", "post"))
    print(f"{name:10s} {nt[0] / nt[2]:6.3f}       {cols}    diag {np.round(np.diag(Md), 4)}  3x3 rows {np.round(M3, 3).tolist()}")
