import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
from scipy.optimize import least_squares
lut = np.load(f"{R}/data/luts/lut_e5b_35100.npz")["lut"]
KN = np.linspace(np.log(1e-3), np.log(1.0), 10)


def curve(v, k):
    # monotone-ish log-domain gain curve: v * exp(piecewise-linear in log v)
    lv = np.log(np.maximum(v, 1e-6))
    return v * np.exp(np.interp(lv, KN, k))


def hue(l):
    return np.degrees(np.arctan2(l[:, 2], l[:, 1]))


def report(name, pr, tgt, ok):
    d = de2000(pr, tgt); m = ok & (SAT < 0.6); s = ok & (SAT >= 0.6)
    print(f"   {name:58s} {np.median(d[m]):5.2f} {np.median(d[s]):6.2f}")


for alt, base, label in (("R3fc0", "R3fc4", "host white balance"), ("R3Wfc0", "R3Wbase", "tungsten white balance")):
    L0, L4 = lab(alt), lab(base)
    ok = (DEV.max(1) < 0.9) & (L4[:, 0] > 3) & (L4[:, 0] < 95) & (L0[:, 0] < 97)
    rng = np.random.default_rng(0); sub = rng.choice(np.flatnonzero(ok), 4000, replace=False)
    resid = L4 - predict(lut, DEV)  # table error at x, carried along for the 'tone first' model
    print(f"\n{label}: explaining the FilmCurve 0 render from the Standard render, median dE00 (moderate | saturated colours)")
    report("no change (FilmCurve 0 vs Standard as is)", L4, L0, ok)
    # H1: tone first: same curve on all three camera channels, then the Standard colour transform
    f = lambda k, idx: predict(lut, np.clip(curve(LIN[idx], k), 0, 1) ** (1 / 1.8)) + resid[idx]
    r = least_squares(lambda k: (f(k, sub) - L0[sub]).ravel(), np.zeros(10), loss="soft_l1")
    report("tone first: one curve on camera RGB, then Standard colour", f(r.x, np.arange(len(L0))), L0, ok)
    k_pre = r.x
    # H2: tone last, per channel: one curve on each linear ProPhoto channel of the Standard output
    pp4 = np.maximum(pp_lin(L4), 1e-6)
    g = lambda k, idx: lab_from_pp(curve(pp4[idx], k))
    r = least_squares(lambda k: (g(k, sub) - L0[sub]).ravel(), np.zeros(10), loss="soft_l1")
    report("tone last, per channel (ProPhoto linear)", g(r.x, np.arange(len(L0))), L0, ok)
    # H3: tone last on lightness only (a*, b* kept)
    h = lambda k, idx: np.stack([116 * np.cbrt(np.clip(curve(((L4[idx, 0] + 16) / 116) ** 3, k), 0, None)) - 16, L4[idx, 1], L4[idx, 2]], 1)
    r = least_squares(lambda k: (h(k, sub) - L0[sub]).ravel(), np.zeros(10), loss="soft_l1")
    report("tone last, lightness only (a*, b* kept)", h(r.x, np.arange(len(L0))), L0, ok)
    # H4: tone last on luminance, RGB ratios kept (hue and saturation in linear RGB kept)
    Y4 = np.maximum(pp4 @ PROPHOTO_M[1], 1e-6)
    q = lambda k, idx: lab_from_pp(pp4[idx] * (curve(Y4[idx], k) / Y4[idx])[:, None])
    r = least_squares(lambda k: (q(k, sub) - L0[sub]).ravel(), np.zeros(10), loss="soft_l1")
    report("tone last on luminance, linear RGB ratios kept", q(r.x, np.arange(len(L0))), L0, ok)
    gain_ev = [np.log2(curve(np.array([v]), k_pre)[0] / v) for v in (0.01, 0.05, 0.18, 0.45)]
    print("   tone-first curve: camera-RGB gain at 0.01/0.05/0.18/0.45 = " + " ".join(f"{e:+.2f}" for e in gain_ev) + " EV")
    m = ok & (np.hypot(L4[:, 1], L4[:, 2]) > 10)
    dh = ((hue(L0) - hue(L4) + 180) % 360) - 180
    print(f"   hue change FilmCurve 0 vs Standard (C* > 10): median |dh| {np.median(np.abs(dh[m])):.2f} deg, p90 {np.percentile(np.abs(dh[m]), 90):.2f}")
