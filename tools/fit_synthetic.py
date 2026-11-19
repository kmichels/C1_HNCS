"""Fit a LUT from synthetic-raw pairs (Capture One probe render + Phocus export of the same synthetic 3FR),
optionally together with real-image pairs, and score it on real held-out frames.

Each patch gives one exact pair: the camera RGB Capture One hands its profile (read from the probe render)
and Phocus's Lab. Phocus's edge brightening (lens corrections off) is removed per patch with the lens's
measured lift, as for real pairs.

usage: python fit_synthetic.py OUT.npz --lift c2,c4 --synth NAME:PATCHES.npz:C1_RENDER.tif:PHOCUS.tif [...]
         [--pairs PAIRS.npz ...]   (saved pairs, e.g. fit/synthetic/pairs/*.npz, instead of renders)
         [--real PAIRS_DIR:FRAME,FRAME] [--test PAIRS_DIR:FRAME,FRAME] [--lam-s 1.0] [--compare LUT.npz]
"""
import argparse
import os
import sys

import numpy as np
import tifffile

sys.path.insert(0, os.path.dirname(__file__))
from fit import *  # noqa: F401,F403,E402
from icc import D50, xyz_to_lab  # noqa: E402
from pairs import PROPHOTO_M, phocus_decode, romm_decode  # noqa: E402
from write_profile import finalize  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("out")
ap.add_argument("--lift", default="0,0")
ap.add_argument("--gainmap", default=None, help="Phocus gain map (flat_gain.py, corrections off, same host): replaces --lift")
ap.add_argument("--synth", action="append", default=[])
ap.add_argument("--pairs", action="append", default=[], help="saved synthetic pairs (save_synth_pairs.py)")
ap.add_argument("--real", action="append", default=[])
ap.add_argument("--test", action="append", default=[])
ap.add_argument("--lam-s", type=float, default=1.0)
ap.add_argument("--real-weight", type=float, default=1.0)
ap.add_argument("--compare", default=None)
ap.add_argument("--test-radius", type=float, default=0.5)
ap.add_argument("--fade-start", type=float, default=100.0, help="table L* where chroma starts fading to neutral (over 10 L*); 95 before Finding 34")
ap.add_argument("--grey-fade-start", type=float, default=95.0, help="table L* where near-neutral nodes start fading to neutral; -1 for none")
ap.add_argument("--grey-chroma", type=float, default=6.0, help="C* below which a node counts as near-neutral for --grey-fade-start")
ap.add_argument("--knee", type=float, default=110.0, help="where chroma compression starts (90 before Finding 38)")
ap.add_argument("--cmax", type=float, default=127.5, help="what compressed chroma approaches")
ap.add_argument("--limit", choices=("chroma", "box"), default="box", help="compress C* (chroma) or max(|a*|,|b*|) (box, the encoding's real limit)")
a = ap.parse_args()
c2, c4 = (float(v) for v in a.lift.split(","))
white = D50 / np.array([0.9642, 1.0, 0.82489])


def patch_means(img, pos, P):
    s_ = P // 2
    m = s_ // 4
    return np.array([img[y // 2 + m: y // 2 + s_ - m, x // 2 + m: x // 2 + s_ - m].reshape(-1, 3).mean(0) for y, x in pos])


devs, labs = [], []
specs = [("synth", s_) for s_ in a.synth] + [("pairs", s_) for s_ in a.pairs]
for kind, spec in specs:
    if kind == "synth":
        name, pz, c1p, php = spec.split(":")
        z = np.load(pz)
        pos, P, (ch, cw) = z["pos"], int(z["patch"]), z["active"]
        c1 = patch_means(tifffile.imread(c1p)[..., :3].astype(np.float64) / 65535, pos, P)
        ph = patch_means(tifffile.imread(php)[..., :3].astype(np.float64) / 65535, pos, P)
        lin = np.clip(romm_decode(c1), 0, None)
    else:
        name = os.path.basename(spec).replace(".npz", "")
        z = np.load(spec)
        pos, P, (ch, cw) = z["pos"], int(z["patch"]), z["active"]
        ph = z["phocus_prophoto"]
        lin = z["device_c1_lin"].copy()
    r = np.hypot(pos[:, 0] + P / 2 - ch / 2, pos[:, 1] + P / 2 - cw / 2) / np.hypot(ch / 2, cw / 2)
    if a.gainmap:
        gm = np.load(a.gainmap)
        gb = int(gm["block"])
        gy = np.clip(((pos[:, 0] + P / 2) / 2 // gb).astype(int), 0, gm["gain"].shape[0] - 1)
        gx = np.clip(((pos[:, 1] + P / 2) / 2 // gb).astype(int), 0, gm["gain"].shape[1] - 1)
        lin = lin * gm["gain"][gy, gx]
    else:
        lin = lin * (2.0 ** (c2 * r**2 + c4 * r**4))[:, None]
    dev = lin ** (1 / 1.8)
    lab = xyz_to_lab((phocus_decode(ph) @ PROPHOTO_M.T) * white)
    ok = (dev.max(1) < 0.97) & (ph.max(1) < 0.995) & (ph.min(1) > 2 / 65535) & (lab[:, 0] > 0.5)
    print(f"{name}: {ok.sum()} / {len(ok)} patches usable, max radius {r.max():.2f}")
    devs.append(dev[ok])
    labs.append(lab[ok])
dev_s = np.concatenate(devs)
lab_s = np.concatenate(labs)
W_s = tetra_weights(dev_s)

Ws, Ls = [W_s], [lab_s]
for spec in a.real:
    d, frames = spec.split(":")
    for k in frames.split(","):
        fr = load_frame(os.path.join(d, k + ".npz"))
        Ws.append(fr["W"] * np.sqrt(a.real_weight))
        Ls.append(fr["lab"] * np.sqrt(a.real_weight))
W = sp.vstack(Ws).tocsr()
lab = np.concatenate(Ls)
print(f"synthetic pairs {len(lab_s)}, total rows {W.shape[0]}")

rng = np.random.default_rng(0)
p = fit_base(dev_s, lab_s, rng)
bn = base_model(node_dev(), p)
D = second_diff_ops()
A0 = (W.T @ W + a.lam_s * (D.T @ D) + 1e-3 * sp.identity(G**3)).tocsc()
Wtl = W.T @ lab
solve = factorized(A0)
lut = np.stack([solve(Wtl[:, c] + 1e-3 * bn[:, c]) for c in range(3)], 1)
wc = np.zeros(G**3)
tgt = np.zeros((G**3, 3))
for it in range(5):
    fin = finalize(lut.reshape(G, G, G, 3), fade_start=a.fade_start, grey_fade_start=None if a.grey_fade_start < 0 else a.grey_fade_start, grey_chroma=a.grey_chroma, knee=a.knee, cmax=a.cmax, limit=a.limit).reshape(-1, 3)
    viol = np.abs(fin - lut).max(axis=1) > 0.05
    print(f"constraint iter {it}: nodes outside storable range {int(viol.sum())}", flush=True)
    if not viol.any():
        break
    wc[viol] = 1e3
    tgt[viol] = fin[viol]
    s2 = factorized((A0 + sp.diags(wc)).tocsc())
    rhs = Wtl + 1e-3 * bn + wc[:, None] * tgt
    lut = np.stack([s2(rhs[:, c]) for c in range(3)], 1)
fin = finalize(lut.reshape(G, G, G, 3), fade_start=a.fade_start, grey_fade_start=None if a.grey_fade_start < 0 else a.grey_fade_start, grey_chroma=a.grey_chroma, knee=a.knee, cmax=a.cmax, limit=a.limit).reshape(-1, 3)
np.savez(a.out, lut=fin, base=p, lam_s=a.lam_s, fade_start=a.fade_start, grey_fade_start=a.grey_fade_start, grey_chroma=a.grey_chroma, knee=a.knee, cmax=a.cmax, limit=a.limit, finalized=True)
d_s = de2000(W_s @ fin, lab_s)
print(f"\nwrote {a.out}; synthetic fit residual median {np.median(d_s):.2f} p90 {np.percentile(d_s, 90):.2f}")

cmp_lut = np.load(a.compare)["lut"] if a.compare else None
print("real held-out frames, median dE00: new LUT | comparison")
for spec in a.test:
    d, frames = spec.split(":")
    meds = []
    for k in frames.split(","):
        fr = load_frame(os.path.join(d, k + ".npz"), max_radius=a.test_radius)
        m1 = np.median(de2000(fr["W"] @ fin, fr["lab"]))
        m2 = np.median(de2000(fr["W"] @ cmp_lut, fr["lab"])) if cmp_lut is not None else float("nan")
        meds.append((m1, m2))
        print(f"  {k}: {m1:.2f} | {m2:.2f}")
    mm = np.array(meds)
    print(f"  mean: {mm[:, 0].mean():.2f} | {mm[:, 1].mean():.2f}")
