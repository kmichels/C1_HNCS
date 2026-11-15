import numpy as np
from icc import lab_from_legacy16

def tetra(m, rgb):
    rgb = np.asarray(rgb, dtype=float).reshape(-1, 3)
    n = m.in_curves.shape[1]
    sh = np.stack([np.interp(np.clip(rgb[:, c], 0, 1), np.linspace(0, 1, n), m.in_curves[c] / 65535) for c in range(3)], -1)
    g = m.grid; t = sh * (g - 1); i = np.minimum(np.floor(t).astype(int), g - 2); f = t - i
    C = m.clut.astype(float)
    def node(dr, dg, db): return C[i[:, 0] + dr, i[:, 1] + dg, i[:, 2] + db]
    fr, fg, fb = f[:, 0:1], f[:, 1:2], f[:, 2:3]
    c000, c111 = node(0, 0, 0), node(1, 1, 1)
    out = np.zeros_like(c000)
    conds = [(fr >= fg) & (fg >= fb), (fr >= fb) & (fb > fg), (fb > fr) & (fr >= fg), (fg > fr) & (fr >= fb), (fg >= fb) & (fb > fr), (fb > fg) & (fg > fr)]
    combos = [((1,0,0),(1,1,0), fr, fg, fb), ((1,0,0),(1,0,1), fr, fb, fg), ((0,0,1),(1,0,1), fb, fr, fg), ((0,1,0),(1,1,0), fg, fr, fb), ((0,1,0),(0,1,1), fg, fb, fr), ((0,0,1),(0,1,1), fb, fg, fr)]
    for cond, (a, b, x, y, z) in zip(conds, combos):
        ca, cb = node(*a), node(*b)
        out = np.where(cond, c000 + x * (ca - c000) + y * (cb - ca) + z * (c111 - cb), out)
    return lab_from_legacy16(out)
