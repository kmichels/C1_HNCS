import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
from scipy.optimize import least_squares
L35 = np.load(f"{R}/data/luts/lut_e5b_35100.npz")["lut"]; L28 = np.load(f"{R}/data/luts/lut_e5b_28p.npz")["lut"]
for base, lut, vs in (("R3fc4", L35, ("R3g1a", "R3g1d", "R3gj", "R3gz")), ("R3Pbase", L28, ("R3Pg1", "R3Pg2")), ("R3Wbase", L35, ("R3Wg1", "R3Wg2"))):
    Lb = lab(base); ok = (DEV.max(1) < 0.9) & (SAT < 0.6) & (Lb[:, 0] > 5) & (Lb[:, 0] < 92)
    resid0 = Lb - predict(lut, DEV)
    P_ = lambda k: predict(lut, np.clip(LIN[ok] * np.exp(k), 0, 1) ** (1 / 1.8)) + resid0[ok]
    for n in vs:
        Lt = lab(n)
        r = least_squares(lambda k: (P_(k) - Lt[ok]).ravel(), np.zeros(3))
        k = np.exp(r.x); d = de2000(P_(r.x), Lt[ok])
        print(f"{n:7s} kR kG kB = {k.round(4)}  -> relative to G: {np.round(k / k[1], 4)}  residual {np.median(d):.2f}; grey dL* {np.mean((Lt - Lb)[ok & NEUT, 0]):+.2f}")
