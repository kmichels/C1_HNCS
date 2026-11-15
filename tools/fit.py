"""Fit a 33^3 tetrahedral RGB->Lab LUT mapping Capture One's ICC input (device RGB, gamma 1/1.8)
to Phocus's Lab, from block pairs written by pairs.py."""
import os
import sys

import numpy as np
import scipy.sparse as sp
from scipy.optimize import least_squares
from scipy.sparse.linalg import factorized

sys.path.insert(0, os.path.dirname(__file__))
from icc import D50, de2000, xyz_to_lab  # noqa: E402

G = 33
PROPHOTO_M = np.array([[0.79767, 0.13519, 0.03134], [0.28804, 0.71188, 0.00009], [0.0, 0.0, 0.82491]])
PROPHOTO_INV = np.linalg.inv(PROPHOTO_M)


def lstar01(y):
    return np.where(y > 216 / 24389, 116 * np.cbrt(y) - 16, y * 24389 / 27) / 100


def romm_decode(v):
    v = np.clip(v, 0, 1)
    return np.where(v >= 0.001953, v**1.8, v / 16.0)


def shaper(dev):
    return lstar01(romm_decode(dev))


_xs = np.linspace(0, 1, 400001)
_sv = shaper(_xs)


def shaper_inv(t):
    return np.interp(t, _sv, _xs)


NODE_DEV = shaper_inv(np.linspace(0, 1, G))


def load_frame(path, max_radius=0.5, min_L=2.0):
    z = np.load(path)
    nb = int(z["nblocks"])
    W = sp.csr_matrix((z["coo_w"].astype(np.float64), (z["coo_b"], z["coo_n"])), shape=(nb, G**3))
    m = (
        (z["dev_max"] < 0.97)
        & (z["ph_max"] < 0.995)
        & (z["ph_min"] > 2 / 65535)
        & (z["radius"] < max_radius)
        & (z["lab"][:, 0] > min_L)
    )
    m &= np.asarray(W.sum(axis=1)).ravel() > 0.99
    return dict(
        mask=np.flatnonzero(m),
        W=W[m],
        lab=z["lab"][m].astype(np.float64),
        dev=z["dev"][m].astype(np.float64),
        radius=z["radius"][m],
        lin_std=z["lin_std"][m],
    )


# ---------- tetrahedral interpolation as a sparse matrix ----------
def tetra_cols_weights(dev):
    t = shaper(dev) * (G - 1)
    i = np.minimum(np.floor(t).astype(np.int64), G - 2)
    f = t - i
    fr, fg, fb = f[:, 0], f[:, 1], f[:, 2]
    n = len(dev)

    def idx(dr, dg, db):
        return (i[:, 0] + dr) * G * G + (i[:, 1] + dg) * G + (i[:, 2] + db)

    cols = np.zeros((n, 4), np.int64)
    w = np.zeros((n, 4), np.float32)
    cases = [
        ((fr >= fg) & (fg >= fb), (1, 0, 0), (1, 1, 0), fr, fg, fb),
        ((fr >= fb) & (fb > fg), (1, 0, 0), (1, 0, 1), fr, fb, fg),
        ((fb > fr) & (fr >= fg), (0, 0, 1), (1, 0, 1), fb, fr, fg),
        ((fg > fr) & (fr >= fb), (0, 1, 0), (1, 1, 0), fg, fr, fb),
        ((fg >= fb) & (fb > fr), (0, 1, 0), (0, 1, 1), fg, fb, fr),
        ((fb > fg) & (fg > fr), (0, 0, 1), (0, 1, 1), fb, fg, fr),
    ]
    c000, c111 = idx(0, 0, 0), idx(1, 1, 1)
    for cond, a, b, x, y, zz in cases:
        ca, cb = idx(*a), idx(*b)
        cols[cond] = np.stack([c000[cond], ca[cond], cb[cond], c111[cond]], 1)
        w[cond] = np.stack([1 - x[cond], x[cond] - y[cond], y[cond] - zz[cond], zz[cond]], 1)
    return cols, w


def tetra_weights(dev):
    cols, w = tetra_cols_weights(np.asarray(dev, dtype=np.float64).reshape(-1, 3))
    n = len(cols)
    rows = np.repeat(np.arange(n), 4)
    return sp.csr_matrix((w.ravel().astype(np.float64), (rows, cols.ravel())), shape=(n, G**3))


def second_diff_ops():
    ops = []
    for axis in range(3):
        rows, cols, vals = [], [], []
        r = 0
        for a in range(G):
            for b in range(G):
                for c in range(G):
                    coord = [a, b, c]
                    if coord[axis] == 0 or coord[axis] == G - 1:
                        continue
                    for off, v in ((-1, 1.0), (0, -2.0), (1, 1.0)):
                        cc = list(coord)
                        cc[axis] += off
                        rows.append(r)
                        cols.append(cc[0] * G * G + cc[1] * G + cc[2])
                        vals.append(v)
                    r += 1
        ops.append(sp.csr_matrix((vals, (rows, cols)), shape=(r, G**3)))
    return sp.vstack(ops).tocsr()


# ---------- parametric base: matrix -> ProPhoto linear -> shared tone curve -> Lab ----------
KNOTS = np.linspace(-14, 0.5, 16)


def tone(lin, params):
    slopes = np.exp(params)
    vals = KNOTS[0] + np.concatenate([[0.0], np.cumsum(slopes * np.diff(KNOTS))])
    x = np.log2(np.maximum(lin, 2.0**-20))
    y = np.interp(x, KNOTS, vals, left=None, right=None)
    below = x < KNOTS[0]
    y = np.where(below, vals[0] + (x - KNOTS[0]) * slopes[0], y)
    above = x > KNOTS[-1]
    y = np.where(above, vals[-1] + (x - KNOTS[-1]) * slopes[-1], y)
    return 2.0**y


def base_model(dev, p):
    M = p[:9].reshape(3, 3)
    gain = np.exp(p[9])
    lin = romm_decode(dev)
    pp = (lin @ M.T) * gain
    pp = tone(np.maximum(pp, 0), p[10:])
    xyz = pp @ PROPHOTO_M.T
    return xyz_to_lab(xyz)


def fit_base(dev, lab, rng):
    sel = rng.choice(len(dev), min(len(dev), 30000), replace=False)
    d, l = dev[sel], lab[sel]
    # init: camera RGB treated as ProPhoto (identity), gain 1, slope 1 everywhere
    p0 = np.concatenate([np.eye(3).ravel(), [0.0], np.zeros(len(KNOTS) - 1)])

    def resid(p):
        return (base_model(d, p) - l).ravel()

    res = least_squares(resid, p0, method="trf", loss="soft_l1", f_scale=2.0, max_nfev=400)
    return res.x


def node_dev():
    return np.stack(np.meshgrid(NODE_DEV, NODE_DEV, NODE_DEV, indexing="ij"), -1).reshape(-1, 3)


def fit_lut(W, lab, base_nodes, lam_s, lam_r, D, sample_w=None):
    Wt = W.T if sample_w is None else W.T.multiply(sample_w[None, :]).tocsr()
    A = (Wt @ W + lam_s * (D.T @ D) + lam_r * sp.identity(G**3)).tocsc()
    solve = factorized(A)
    rhs = Wt @ lab + lam_r * base_nodes
    return np.stack([solve(rhs[:, k]) for k in range(3)], 1)


def predict(lut, dev):
    return tetra_weights(dev) @ lut


def score_w(lut, W, lab):
    return de2000(W @ lut, lab)
