"""Fit one LUT on several pairs sets, anchored to the sets from your own camera.

Phocus renders the same scene slightly differently on different camera bodies (and lenses): greys
shift by up to ~1 b*, which Capture One doesn't do. Sets listed in "offset_sets" (frames from another
body) get their own small offset, modelled like a white-balance difference: delta(L) = k * (L* + 16) / 116
per Lab channel, fitted jointly with the LUT. They then contribute colour shapes (skin, saturated
colours) without moving the overall balance, which the anchored sets decide.

usage: python fit_anchored.py CONFIG.json OUT_LUT.npz
CONFIG: as fit_multi.py, plus "offset_sets": [names], "lam_s": number (no cross-validation), "exclude": [frames]
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
excl = set(cfg.get("exclude", []))
offset_sets = set(cfg.get("offset_sets", []))
lam_s = float(cfg.get("lam_s", 1.0))
fr, TRAIN, TEST = {}, [], []
for st in cfg["sets"]:
    for k in st["train"] + st["test"]:
        if k in excl:
            continue
        fr[(st["name"], k)] = load_frame(os.path.join(root, st["pairs"], k + ".npz"))
    TRAIN += [(st["name"], k) for k in st["train"] if k not in excl]
    TEST += [(st["name"], k) for k in st["test"] if k not in excl]
print(f"train {len(TRAIN)}, test {len(TEST)}; offset sets {sorted(offset_sets)}; lam_s {lam_s}")

rng = np.random.default_rng(0)
D = second_diff_ops()
anch = [k for k in TRAIN if k[0] not in offset_sets]
p = fit_base(np.concatenate([fr[k]["dev"] for k in anch]), np.concatenate([fr[k]["lab"] for k in anch]), rng)
bn = base_model(node_dev(), p)
W = sp.vstack([fr[k]["W"] for k in TRAIN]).tocsr()
lab = np.concatenate([fr[k]["lab"] for k in TRAIN])
src = np.concatenate([[k[0]] * fr[k]["W"].shape[0] for k in TRAIN])
u = (lab[:, 0] + 16) / 116
A0 = (W.T @ W + lam_s * (D.T @ D) + 1e-3 * sp.identity(G**3)).tocsc()
solve = factorized(A0)
coef = {s: np.zeros(3) for s in offset_sets}


def targets():
    t = lab.copy()
    for s, c in coef.items():
        m = src == s
        t[m] += u[m, None] * c[None, :]
    return t


# Exact joint solve: for fixed offsets c the LUT is L(c) = x0 + sum_s c_s * x1_s (linear in c), so
# the optimal c solves a tiny linear system per Lab channel.
x0 = np.stack([solve((W.T @ lab + 1e-3 * bn)[:, c]) for c in range(3)], 1)
names = sorted(offset_sets)
U = np.stack([np.where(src == s, u, 0.0) for s in names], 1) if names else np.zeros((len(u), 0))
X1 = [solve(W.T @ U[:, j]) for j in range(len(names))]
WX1 = np.stack([W @ x for x in X1], 1) if names else np.zeros((len(u), 0))
r0 = W @ x0 - lab
M = U.T @ U - U.T @ WX1
for ch in range(3):
    if names:
        cvec = np.linalg.solve(M, U.T @ r0[:, ch])
        for j, s in enumerate(names):
            coef[s][ch] = cvec[j]
lut = x0 + sum(np.outer(X1[j], [coef[s][ch] for ch in range(3)]) for j, s in enumerate(names)) if names else x0
print("offsets " + ", ".join(f"{s}: dL {c[0]:+.2f} da {c[1]:+.2f} db {c[2]:+.2f} (at L*=100)" for s, c in coef.items()), flush=True)

t = targets()
Wtl = W.T @ t
wc = np.zeros(G**3)
tgt = np.zeros((G**3, 3))
for it in range(5):
    fin = finalize(lut.reshape(G, G, G, 3)).reshape(-1, 3)
    viol = np.abs(fin - lut).max(axis=1) > 0.05
    print(f"constraint iter {it}: nodes outside storable range {int(viol.sum())}", flush=True)
    if not viol.any():
        break
    wc[viol] = 1e3
    tgt[viol] = fin[viol]
    s2 = factorized((A0 + sp.diags(wc)).tocsc())
    rhs = Wtl + 1e-3 * bn + wc[:, None] * tgt
    lut = np.stack([s2(rhs[:, c]) for c in range(3)], 1)
fin = finalize(lut.reshape(G, G, G, 3)).reshape(-1, 3)
np.savez(OUT, lut=fin, base=p, lam_s=lam_s, offsets=json.dumps({s: c.tolist() for s, c in coef.items()}))

cmp_lut = np.load(os.path.join(root, cfg["compare"]))["lut"] if cfg.get("compare") else None
print(f"\nwrote {OUT}")
print("HELD-OUT median dE00: new LUT | new LUT with source offset | comparison LUT")
by = {}
for key in TEST:
    v = fr[key]
    pr = v["W"] @ fin
    d = de2000(pr, v["lab"])
    if key[0] in coef:
        uu = (v["lab"][:, 0] + 16) / 116
        d_off = de2000(pr, v["lab"] + uu[:, None] * coef[key[0]][None, :])
    else:
        d_off = d
    c = np.median(de2000(v["W"] @ cmp_lut, v["lab"])) if cmp_lut is not None else float("nan")
    by.setdefault(key[0], []).append((np.median(d), np.median(d_off), c))
    print(f"  {key[0]:>16s} {key[1]}: {np.median(d):.2f} | {np.median(d_off):.2f} | {c:.2f}")
for s, r in by.items():
    r = np.array(r)
    print(f"  mean of medians, {s}: {r[:, 0].mean():.2f} | {r[:, 1].mean():.2f} | {r[:, 2].mean():.2f}")
