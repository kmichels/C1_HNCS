"""Align a Capture One probe render (ROMM-encoded ICC input) with a Phocus ProPhoto export and
extract block-mean pairs: device RGB (what the ICC receives) -> Phocus Lab D50."""
import argparse
import os
import sys

import numpy as np
import tifffile

sys.path.insert(0, os.path.dirname(__file__))
from icc import D50, xyz_to_lab  # noqa: E402
from fit import G, tetra_cols_weights  # noqa: E402

PROPHOTO_M = np.array([[0.79767, 0.13519, 0.03134], [0.28804, 0.71188, 0.00009], [0.0, 0.0, 0.82491]])
ROMM_M = PROPHOTO_M


def romm_decode(v):
    v = np.clip(v, 0, 1)
    return np.where(v >= 0.001953, v**1.8, v / 16.0)


def phocus_decode(v):
    return np.clip(v, 0, 1) ** 1.80078


def load(path):
    a = tifffile.imread(path)
    return a[..., :3]


def downsample_lum(lin_rgb_u16, decode, factor):
    h, w, _ = lin_rgb_u16.shape
    h2, w2 = h // factor * factor, w // factor * factor
    out = np.zeros((h2 // factor, w2 // factor), np.float64)
    for y0 in range(0, h2, factor * 256):
        y1 = min(h2, y0 + factor * 256)
        strip = decode(lin_rgb_u16[y0:y1, :w2].astype(np.float32) / 65535.0)
        Y = strip @ PROPHOTO_M[1].astype(np.float32)
        out[y0 // factor : y1 // factor] = Y.reshape((y1 - y0) // factor, factor, w2 // factor, factor).mean(axis=(1, 3))
    return out


def phase_corr(a, b):
    """Shift (dy, dx) such that b[y, x] ~ a[y - dy, x - dx]."""
    def prep(x):
        x = np.log(x + 1e-4)
        gy, gx = np.gradient(x)
        g = np.hypot(gy, gx)
        win = np.outer(np.hanning(g.shape[0]), np.hanning(g.shape[1]))
        return (g - g.mean()) * win

    A = np.fft.fft2(prep(a))
    B = np.fft.fft2(prep(b))
    R = B * np.conj(A)
    R /= np.abs(R) + 1e-12
    r = np.fft.ifft2(R).real
    dy, dx = np.unravel_index(np.argmax(r), r.shape)
    if dy > r.shape[0] // 2:
        dy -= r.shape[0]
    if dx > r.shape[1] // 2:
        dx -= r.shape[1]
    return int(dy), int(dx), float(r.max())


def crop_overlap(shape_a, shape_b, dy, dx):
    """Return slices into a and b covering the overlap when b is shifted by (dy, dx) relative to a."""
    ha, wa = shape_a[:2]
    hb, wb = shape_b[:2]
    ya0, xa0 = max(0, -dy), max(0, -dx)
    yb0, xb0 = max(0, dy), max(0, dx)
    h = min(ha - ya0, hb - yb0)
    w = min(wa - xa0, wb - xb0)
    return (slice(ya0, ya0 + h), slice(xa0, xa0 + w)), (slice(yb0, yb0 + h), slice(xb0, xb0 + w))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("c1")
    ap.add_argument("phocus")
    ap.add_argument("out")
    ap.add_argument("--block", type=int, default=32)
    ap.add_argument("--lift", default="0,0", help="c2,c4: Phocus edge lift in stops = c2*r^2 + c4*r^4 (r = radius / half-diagonal)")
    args = ap.parse_args()

    c1 = load(args.c1)
    ph = load(args.phocus)
    if c1.shape[:2] != ph.shape[:2] and c1.shape[:2] == ph.shape[1::-1]:
        raise SystemExit(f"orientation differs: {c1.shape} vs {ph.shape}")
    f = 8
    la = downsample_lum(c1, romm_decode, f)
    lb = downsample_lum(ph, phocus_decode, f)
    hh, ww = min(la.shape[0], lb.shape[0]), min(la.shape[1], lb.shape[1])
    dy8, dx8, peak = phase_corr(la[:hh, :ww], lb[:hh, :ww])
    dy, dx = dy8 * f, dx8 * f

    # Refine at full resolution on tiles, and check the shift is uniform (no scale/distortion mismatch).
    sa, sb = crop_overlap(c1.shape, ph.shape, dy, dx)
    A = c1[sa]
    B = ph[sb]
    H, W = A.shape[:2]
    tiles = []
    T = 768
    for cy in (0.15, 0.32, 0.5, 0.68, 0.85):
        for cx in (0.15, 0.32, 0.5, 0.68, 0.85):
            y0, x0 = int(cy * H) - T // 2, int(cx * W) - T // 2
            ta = romm_decode(A[y0 : y0 + T, x0 : x0 + T].astype(np.float32) / 65535) @ PROPHOTO_M[1].astype(np.float32)
            tb = phocus_decode(B[y0 : y0 + T, x0 : x0 + T].astype(np.float32) / 65535) @ PROPHOTO_M[1].astype(np.float32)
            ty, tx, tp = phase_corr(ta, tb)
            tiles.append((cy, cx, ty, tx, round(tp, 3)))
    good = [t for t in tiles if t[4] > 0.05]
    if not good:
        good = tiles
    ry = int(np.median([t[2] for t in good]))
    rx = int(np.median([t[3] for t in good]))
    spread = max(max(abs(t[2] - ry), abs(t[3] - rx)) for t in good)
    dy += ry
    dx += rx
    sa, sb = crop_overlap(c1.shape, ph.shape, dy, dx)
    A = c1[sa]
    B = ph[sb]
    H, W = A.shape[:2]

    bs = args.block
    c2, c4 = (float(v) for v in args.lift.split(","))
    half_diag = np.hypot(c1.shape[0] / 2, c1.shape[1] / 2)
    nby, nbx = H // bs, W // bs
    yy, xx = np.mgrid[0:nby, 0:nbx]
    cy_full = (yy * bs + bs / 2 + sa[0].start) - c1.shape[0] / 2
    cx_full = (xx * bs + bs / 2 + sa[1].start) - c1.shape[1] / 2
    radius = (np.hypot(cy_full, cx_full) / np.hypot(c1.shape[0] / 2, c1.shape[1] / 2)).astype(np.float32)

    dev_mean = np.zeros((nby, nbx, 3), np.float32)
    lin_std = np.zeros((nby, nbx), np.float32)
    dev_max = np.zeros((nby, nbx), np.float32)
    lab_mean = np.zeros((nby, nbx, 3), np.float32)
    ph_min = np.zeros((nby, nbx), np.float32)
    ph_max = np.zeros((nby, nbx), np.float32)
    coo_b, coo_n, coo_w = [], [], []
    G3 = G**3
    white = (D50 / np.array([0.9642, 1.0, 0.82489])).astype(np.float32)
    rows = 16
    for by0 in range(0, nby, rows):
        by1 = min(nby, by0 + rows)
        n = by1 - by0
        ya, yb = by0 * bs, by1 * bs
        a = A[ya:yb, : nbx * bs].astype(np.float32) / 65535
        b = B[ya:yb, : nbx * bs].astype(np.float32) / 65535
        a_r = a.reshape(n, bs, nbx, bs, 3)
        b_r = b.reshape(n, bs, nbx, bs, 3)
        if c2 or c4:
            yy_px = (np.arange(ya, yb) + sa[0].start - c1.shape[0] / 2)[:, None]
            xx_px = (np.arange(nbx * bs) + sa[1].start - c1.shape[1] / 2)[None, :]
            rr = np.hypot(yy_px, xx_px) / half_diag
            gain = (2.0 ** (c2 * rr**2 + c4 * rr**4)).astype(np.float32).reshape(n, bs, nbx, bs, 1)
            lin_adj = romm_decode(a_r) * gain
            a_r_dev = np.where(lin_adj >= 0.001953**1.8, np.maximum(lin_adj, 0) ** (1 / 1.8), lin_adj * 16.0).astype(np.float32)
        else:
            a_r_dev = a_r
        lin = romm_decode(a_r_dev)
        dev_mean[by0:by1] = lin.mean(axis=(1, 3)) ** (1 / 1.8)
        Y = lin @ PROPHOTO_M[1].astype(np.float32)
        lin_std[by0:by1] = Y.std(axis=(1, 3)) / (Y.mean(axis=(1, 3)) + 1e-6)
        dev_max[by0:by1] = a_r.max(axis=(1, 3, 4))
        ph_min[by0:by1] = b_r.min(axis=(1, 3, 4))
        ph_max[by0:by1] = b_r.max(axis=(1, 3, 4))
        lab_px = xyz_to_lab((phocus_decode(b_r) @ PROPHOTO_M.T.astype(np.float32)) * white)
        lab_mean[by0:by1] = lab_px.mean(axis=(1, 3))

        keep = (radius[by0:by1] < 0.6) & (dev_max[by0:by1] < 0.97)
        if not keep.any():
            continue
        blk_ids = (np.arange(by0, by1)[:, None, None, None] * nbx + np.arange(nbx)[None, None, :, None])
        blk_ids = np.broadcast_to(blk_ids, (n, bs, nbx, bs))
        sel = np.broadcast_to(keep[:, None, :, None], (n, bs, nbx, bs))
        d = a_r_dev[sel]
        bid = blk_ids[sel]
        cols, w = tetra_cols_weights(d)
        keys = bid[:, None].astype(np.int64) * G3 + cols
        uk, inv = np.unique(keys.ravel(), return_inverse=True)
        acc = np.bincount(inv, weights=w.ravel()) / (bs * bs)
        coo_b.append((uk // G3).astype(np.int32))
        coo_n.append((uk % G3).astype(np.int32))
        coo_w.append(acc.astype(np.float32))

    np.savez_compressed(
        args.out,
        dev=dev_mean.reshape(-1, 3),
        lab=lab_mean.reshape(-1, 3),
        lin_std=lin_std.reshape(-1),
        dev_max=dev_max.reshape(-1),
        ph_min=ph_min.reshape(-1),
        ph_max=ph_max.reshape(-1),
        radius=radius.reshape(-1),
        coo_b=np.concatenate(coo_b),
        coo_n=np.concatenate(coo_n),
        coo_w=np.concatenate(coo_w),
        nblocks=np.array(nby * nbx),
        shift=np.array([dy, dx]),
    )
    print(
        f"{os.path.basename(args.c1)}: c1 {c1.shape[:2]} phocus {ph.shape[:2]} shift (dy,dx)=({dy},{dx}) "
        f"tile spread {spread}px over {len(good)}/{len(tiles)} confident tiles; blocks {nby}x{nbx}; weights {sum(len(x) for x in coo_w)}"
    )

if __name__ == "__main__":
    main()
