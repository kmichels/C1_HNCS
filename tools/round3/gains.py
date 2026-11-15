import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
from scipy.optimize import least_squares
HB_M = np.array([[0.6491, 0.2989, 0.0046], [0.1886, 0.6575, 0.043], [0.1265, 0.0437, 0.7772]])
L35 = np.load(f"{R}/data/luts/lut_e5b_35100.npz")["lut"]; L28 = np.load(f"{R}/data/luts/lut_e5b_28p.npz")["lut"]


def formula(g1, g2):
    if g1 <= 0 or g2 <= 0:
        return None
    return np.exp(-0.0705 * np.log(g1 / 2.6)), np.exp(-0.0875 * np.log(g1 / 2.6) + 0.0775 * np.log(g2 / 2.26))


groups = [("35-100, host WB", "R3fc4", L35, [("R3g1a", 2.2, 2.26), ("R3g1d", 3.0, 2.26), ("R3gj", 2.2, 2.66), ("R3gz", 0, 0)]),
          ("28P host", "R3Pbase", L28, [("R3Pg1", 2.2, 2.26), ("R3Pg2", 2.6, 2.66)]),
          ("35-100, tungsten WB", "R3Wbase", L35, [("R3Wg1", 2.2, 2.26), ("R3Wg2", 2.6, 2.66)])]
print("variant  gains       greys da    db  | fitted kR     kB    | formula kR    kB    | median dE: change  after fit  with formula  | g1 structure: 3x3 pre, diag post (Hasselblad RGB)")
for gname, base, lut, vs in groups:
    print(f"-- {gname}")
    Lb = lab(base)
    ok = (DEV.max(1) < 0.9) & (SAT < 0.6) & (Lb[:, 0] > 5) & (Lb[:, 0] < 92)
    resid0 = Lb - predict(lut, DEV)
    neut = ok & NEUT
    for n, g1, g2 in vs:
        Lt = lab(n)
        P_ = lambda M, idx: predict(lut, np.clip(np.maximum(LIN[idx] @ M.T, 0), 0, 1) ** (1 / 1.8)) + resid0[idx]
        r = least_squares(lambda k: (P_(np.diag([np.exp(k[0]), 1, np.exp(k[1])]), ok) - Lt[ok]).ravel(), [0.0, 0.0])
        kR, kB = np.exp(r.x)
        d_fit = de2000(P_(np.diag([kR, 1, kB]), ok), Lt[ok])
        fk = formula(g1, g2)
        d_f = de2000(P_(np.diag([fk[0], 1, fk[1]]), ok), Lt[ok]) if fk else None
        d0 = de2000(Lt[ok], Lb[ok])
        dd = (Lt - Lb)[neut].mean(0)
        r3 = least_squares(lambda k: (P_(np.eye(3) + k.reshape(3, 3), ok) - Lt[ok]).ravel(), np.zeros(9))
        d3 = de2000(P_(np.eye(3) + r3.x.reshape(3, 3), ok), Lt[ok])
        hb = np.maximum(lab_to_xyz(Lb[ok]) / white @ np.linalg.inv(HB_M), 0)
        Q = lambda k: xyz_to_lab((hb * np.exp(np.r_[k[0], 0, k[1]])) @ HB_M * white)
        rp = least_squares(lambda k: (Q(k) - Lt[ok]).ravel(), [0.0, 0.0])
        dp = de2000(Q(rp.x), Lt[ok])
        fs = f"{fk[0]:.4f} {fk[1]:.4f}" if fk else "   n/a      "
        fd = f"{np.median(d_f):5.2f}" if fk else "  n/a"
        print(f"{n:7s} ({g1:.2f},{g2:.2f}) {dd[1]:+.2f} {dd[2]:+.2f} | {kR:.4f} {kB:.4f} | {fs} | {np.median(d0):5.2f} {np.median(d_fit):9.2f} {fd:>12s}  | {np.median(d3):.2f}, {np.median(dp):.2f} (post gains {np.round(np.exp(rp.x), 4)})")
