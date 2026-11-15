"""E3: fit one LUT on XCD 28P (full-size, 32 px blocks) and XCD 35-100 (half-size, 16 px blocks) pairs,
both with that lens's Phocus edge lift removed, then refit inside the storable range.

usage: python fit_e3.py ROOT PAIRS_28P PAIRS_35100 OUT_LUT.npz [SKIP_FRAMES]
  ROOT holds the pairs folders; frame lists below are this dataset's frames.
  Set COMPARE_LUT=path/to/other_lut.npz to also score an earlier LUT on the same frames.
"""
import os, sys, time
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from fit import *  # noqa
from write_profile import finalize

ROOT, P28, P35, OUT = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
SKIP = set(sys.argv[5].split(",")) if len(sys.argv) > 5 and sys.argv[5] else set()
TR28 = ["B0000901", "B0000911", "B0000916", "B0000917", "B0000919", "B0000926", "B0000931"]
TE28 = ["B0000912", "B0000929", "B0000939"]
ALL35 = ["B0000621", "B0000623", "B0000630", "B0000632", "B0000677", "B0000679", "B0000700", "B0000701", "B0000702", "B0000703",
         "B0000727", "B0000746", "B0000825", "B0000829", "B0000832", "B0000858", "B0000861", "B0000863", "B0000865"]
TE35 = [ALL35[i] for i in (1, 5, 9, 13, 17)]
TR35 = [k for k in ALL35 if k not in TE35 and k not in SKIP]
fr = {k: load_frame(os.path.join(ROOT, P28, k + ".npz")) for k in TR28 + TE28}
fr.update({k: load_frame(os.path.join(ROOT, P35, k + ".npz")) for k in TR35 + TE35})
TRAIN, TEST = TR28 + TR35, TE28 + TE35
print("train:", TRAIN, "\ntest:", TEST)

CMP = os.environ.get("COMPARE_LUT")
e2 = np.load(CMP)["lut"] if CMP else None
if CMP:
    print("\nComparison LUT on each 35-100 frame (median dE00, mean da*, db*, dL* = LUT - Phocus):")
for k in ALL35 if CMP else []:
    v = fr.get(k) or load_frame(os.path.join(ROOT, P35, k + ".npz"))
    pr = v["W"] @ e2
    d = de2000(pr, v["lab"])
    print(f"  {k}: {np.median(d):.2f}  {np.mean(pr[:,1]-v['lab'][:,1]):+.2f} {np.mean(pr[:,2]-v['lab'][:,2]):+.2f} {np.mean(pr[:,0]-v['lab'][:,0]):+.2f}  n {len(d)}")

def stack(keys):
    return sp.vstack([fr[k]["W"] for k in keys]).tocsr(), np.concatenate([fr[k]["lab"] for k in keys])

rng = np.random.default_rng(0)
D = second_diff_ops()
p = fit_base(np.concatenate([fr[k]["dev"] for k in TRAIN]), np.concatenate([fr[k]["lab"] for k in TRAIN]), rng)
bn = base_model(node_dev(), p)
W, lab = stack(TRAIN)
WtW, DtD, Wtl = (W.T @ W).tocsr(), (D.T @ D).tocsr(), W.T @ lab
folds = TR28[::2] + TR35[::3]
cv = {}
for ls in (1.0, 3.0, 10.0):
    meds = []
    for hold in folds:
        Wh = fr[hold]["W"]
        A = (WtW - Wh.T @ Wh + ls * DtD + 1e-3 * sp.identity(G**3)).tocsc()
        solve = factorized(A)
        rhs = Wtl - Wh.T @ fr[hold]["lab"] + 1e-3 * bn
        lut = np.stack([solve(rhs[:, c]) for c in range(3)], 1)
        meds.append(float(np.median(score_w(lut, Wh, fr[hold]["lab"]))))
    cv[ls] = meds
    print(f"CV lam_s={ls}: {np.round(meds, 2).tolist()} mean {np.mean(meds):.3f}")
lam_s = min(cv, key=lambda k: np.mean(cv[k]))

wc = np.zeros(G**3); tgt = np.zeros((G**3, 3))
A0 = WtW + lam_s * DtD + 1e-3 * sp.identity(G**3)
lut = np.stack([factorized(A0.tocsc())(Wtl[:, c] + 1e-3 * bn[:, c]) for c in range(3)], 1)
for it in range(5):
    fin = finalize(lut.reshape(G, G, G, 3)).reshape(-1, 3)
    viol = np.abs(fin - lut).max(axis=1) > 0.05
    print(f"constraint iter {it}: nodes outside storable range {int(viol.sum())}")
    if not viol.any():
        break
    wc[viol] = 1e3; tgt[viol] = fin[viol]
    solve = factorized((A0 + sp.diags(wc)).tocsc())
    rhs = Wtl + 1e-3 * bn + wc[:, None] * tgt
    lut = np.stack([solve(rhs[:, c]) for c in range(3)], 1)
fin = finalize(lut.reshape(G, G, G, 3)).reshape(-1, 3)
np.savez(os.path.join(ROOT, OUT), lut=fin, base=p, lam_s=lam_s)
print(f"\nlam_s={lam_s}; train median {np.median(score_w(fin, W, lab)):.3f}")
print("HELD-OUT median dE00 (new LUT | comparison LUT):")
for k in TEST:
    d3 = score_w(fin, fr[k]["W"], fr[k]["lab"])
    cmp = f"{np.median(score_w(e2, fr[k]['W'], fr[k]['lab'])):.2f}" if CMP else "-"
    print(f"  {k}: {np.median(d3):.2f} p90 {np.percentile(d3, 90):.2f} | {cmp}")
