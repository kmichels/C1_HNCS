"""Fit one LUT on several pairs sets (lenses / sources) described by a JSON config, cross-validate the
smoothness, refit inside the storable range, and score held-out frames.

usage: python fit_multi.py CONFIG.json OUT_LUT.npz

CONFIG:
{
  "root": "data",
  "sets": [{"name": "28P", "pairs": "pairs_28p_lifted", "train": ["B0000901", ...], "test": [...]}, ...],
  "compare": "luts/lut_e3c.npz",          # optional: score an earlier LUT on the same frames
  "lam_s": [1.0, 3.0],                     # smoothness values to cross-validate
  "cv_every": 3                            # leave out every Nth training frame of each set as a CV fold
}
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from fit import *  # noqa: F401,F403,E402
from write_profile import finalize  # noqa: E402

cfg = json.load(open(sys.argv[1]))
OUT = sys.argv[2]
root = cfg.get("root", ".")
fr, setof, TRAIN, TEST = {}, {}, [], []
for st in cfg["sets"]:
    for k in st["train"] + st["test"]:
        fr[(st["name"], k)] = load_frame(os.path.join(root, st["pairs"], k + ".npz"))
        setof[(st["name"], k)] = st["name"]
    TRAIN += [(st["name"], k) for k in st["train"]]
    TEST += [(st["name"], k) for k in st["test"]]
print(f"train {len(TRAIN)} frames, test {len(TEST)} frames, blocks {sum(fr[k]['W'].shape[0] for k in TRAIN)} train")

cmp_lut = np.load(os.path.join(root, cfg["compare"]))["lut"] if cfg.get("compare") else None
if cmp_lut is not None:
    print("\ncomparison LUT on every frame (median dE00 | mean dL* da* db*, LUT - Phocus):")
    for key in TRAIN + TEST:
        v = fr[key]
        pr = v["W"] @ cmp_lut
        d = de2000(pr, v["lab"])
        dd = (pr - v["lab"]).mean(0)
        tag = "test " if key in TEST else "train"
        print(f"  {tag} {key[0]:>16s} {key[1]}: {np.median(d):.2f} | {dd[0]:+.2f} {dd[1]:+.2f} {dd[2]:+.2f}")

rng = np.random.default_rng(0)
D = second_diff_ops()
p = fit_base(np.concatenate([fr[k]["dev"] for k in TRAIN]), np.concatenate([fr[k]["lab"] for k in TRAIN]), rng)
bn = base_model(node_dev(), p)
W = sp.vstack([fr[k]["W"] for k in TRAIN]).tocsr()
lab = np.concatenate([fr[k]["lab"] for k in TRAIN])
WtW, DtD, Wtl = (W.T @ W).tocsr(), (D.T @ D).tocsr(), W.T @ lab
every = cfg.get("cv_every", 3)
folds = []
for st in cfg["sets"]:
    folds += [(st["name"], k) for k in st["train"][::every]]
cv = {}
for ls in cfg.get("lam_s", [1.0, 3.0]):
    meds = []
    for hold in folds:
        Wh = fr[hold]["W"]
        solve = factorized((WtW - Wh.T @ Wh + ls * DtD + 1e-3 * sp.identity(G**3)).tocsc())
        rhs = Wtl - Wh.T @ fr[hold]["lab"] + 1e-3 * bn
        lut = np.stack([solve(rhs[:, c]) for c in range(3)], 1)
        meds.append(float(np.median(score_w(lut, Wh, fr[hold]["lab"]))))
    cv[ls] = meds
    print(f"CV lam_s={ls}: mean {np.mean(meds):.3f} | {np.round(meds, 2).tolist()}", flush=True)
lam_s = min(cv, key=lambda k: np.mean(cv[k]))

wc = np.zeros(G**3)
tgt = np.zeros((G**3, 3))
A0 = WtW + lam_s * DtD + 1e-3 * sp.identity(G**3)
lut = np.stack([factorized(A0.tocsc())(Wtl[:, c] + 1e-3 * bn[:, c]) for c in range(3)], 1)
for it in range(5):
    fin = finalize(lut.reshape(G, G, G, 3)).reshape(-1, 3)
    viol = np.abs(fin - lut).max(axis=1) > 0.05
    print(f"constraint iter {it}: nodes outside storable range {int(viol.sum())}", flush=True)
    if not viol.any():
        break
    wc[viol] = 1e3
    tgt[viol] = fin[viol]
    solve = factorized((A0 + sp.diags(wc)).tocsc())
    rhs = Wtl + 1e-3 * bn + wc[:, None] * tgt
    lut = np.stack([solve(rhs[:, c]) for c in range(3)], 1)
fin = finalize(lut.reshape(G, G, G, 3)).reshape(-1, 3)
np.savez(OUT, lut=fin, base=p, lam_s=lam_s)
print(f"\nlam_s={lam_s}; train median {np.median(score_w(fin, W, lab)):.3f}; wrote {OUT}")
print("HELD-OUT median dE00 (new LUT | comparison LUT):")
for key in TEST:
    d = score_w(fin, fr[key]["W"], fr[key]["lab"])
    c = f"{np.median(score_w(cmp_lut, fr[key]['W'], fr[key]['lab'])):.2f}" if cmp_lut is not None else "-"
    print(f"  {key[0]:>16s} {key[1]}: {np.median(d):.2f} p90 {np.percentile(d, 90):.2f} | {c}")
for st in cfg["sets"]:
    ks = [k for k in TEST if k[0] == st["name"]]
    if ks:
        a = np.mean([np.median(score_w(fin, fr[k]["W"], fr[k]["lab"])) for k in ks])
        b = np.mean([np.median(score_w(cmp_lut, fr[k]["W"], fr[k]["lab"])) for k in ks]) if cmp_lut is not None else float("nan")
        print(f"  mean of medians, {st['name']}: {a:.2f} | {b:.2f}")
