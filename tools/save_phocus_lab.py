import sys, os, numpy as np, tifffile
sys.path.insert(0, os.path.dirname(__file__))
from icc import D50, xyz_to_lab
from pairs import PROPHOTO_M, phocus_decode
src, out = sys.argv[1], sys.argv[2]; bs = int(sys.argv[3]) if len(sys.argv) > 3 else 32
a = tifffile.imread(src)[..., :3]
H, W = a.shape[:2]; nby, nbx = H // bs, W // bs
lab_mean = np.zeros((nby, nbx, 3), np.float32); ph_max = np.zeros((nby, nbx), np.float32)
white = (D50 / np.array([0.9642, 1.0, 0.82489])).astype(np.float32)
for by0 in range(0, nby, 16):
    by1 = min(nby, by0 + 16); n = by1 - by0
    b = a[by0 * bs:by1 * bs, :nbx * bs].astype(np.float32).reshape(n, bs, nbx, bs, 3) / 65535
    lab_mean[by0:by1] = xyz_to_lab((phocus_decode(b) @ PROPHOTO_M.T.astype(np.float32)) * white).mean(axis=(1, 3))
    ph_max[by0:by1] = b.max(axis=(1, 3, 4))
np.savez_compressed(out, lab=lab_mean.reshape(-1, 3), ph_max=ph_max.reshape(-1))
print(out, nby, nbx)
