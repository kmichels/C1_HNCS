import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
from scipy.optimize import least_squares
KN = np.linspace(np.log(1e-3), np.log(1.0), 10)
def curve(v, k):
    return v * np.exp(np.interp(np.log(np.maximum(v, 1e-6)), KN, k))
SPACES = {
    "ProPhoto (= Hasselblad L* RGB v1 primaries)": PROPHOTO_M.T,
    "Hasselblad L* RGB (wider primaries)": np.array([[0.8723, 0.2811, 0.0], [0.0762, 0.6999, 0.0], [0.0157, 0.019, 0.8252]]),
    "Hasselblad RGB": np.array([[0.6491, 0.2989, 0.0046], [0.1886, 0.6575, 0.043], [0.1265, 0.0437, 0.7772]]),
}
alt, base = sys.argv[1], sys.argv[2]
L0, L4 = lab(alt), lab(base)
ok = (DEV.max(1) < 0.9) & (L4[:, 0] > 3) & (L4[:, 0] < 95) & (L0[:, 0] < 97)
sub = np.random.default_rng(0).choice(np.flatnonzero(ok), 4000, replace=False)
X4 = lab_to_xyz(L4) / white
for name, M in SPACES.items():   # M: rows = primaries' XYZ, rgb @ M = XYZ
    rgb4 = np.maximum(X4 @ np.linalg.inv(M), 1e-6)
    for sep in (False, True):
        n = 30 if sep else 10
        def g(k, idx):
            kk = k.reshape(3, 10) if sep else np.tile(k, (3, 1))
            out = np.stack([curve(rgb4[idx, c], kk[c]) for c in range(3)], 1)
            return xyz_to_lab((out @ M) * white)
        r = least_squares(lambda k: (g(k, sub) - L0[sub]).ravel(), np.zeros(n), loss="soft_l1")
        d = de2000(g(r.x, np.arange(len(L0))), L0)
        m = ok & (SAT < 0.6); s = ok & (SAT >= 0.6)
        print(f"   {name:46s} {'3 curves' if sep else '1 curve ':8s} {np.median(d[m]):5.2f} {np.median(d[s]):6.2f}  p90 {np.percentile(d[ok], 90):5.2f}")
