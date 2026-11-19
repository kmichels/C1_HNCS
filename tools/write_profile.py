"""Write a fitted LUT as a Capture One camera ICC (v2.4 scnr RGB->Lab, A2B0 mft2 33^3)."""
import argparse
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from fit import G, shaper  # noqa: E402
from icc import InputProfile, Mft2, build_profile, desc_tag, lab_to_legacy16, text_tag  # noqa: E402
from tetra import tetra  # noqa: E402

IN = "/Applications/Capture One.app/Contents/Frameworks/ImageProcessing.framework/Versions/A/Resources/Profiles/Input/"


def finalize(raw, knee=90.0, cmax=127.0, fade_start=95.0, grey_fade_start=None, grey_chroma=20.0, limit="chroma"):
    """Make the fitted LUT storable and well-behaved where there was no data:
    L* clipped to [0, 100] with chroma fading out over the 10 L* above fade_start, then soft-compressed chroma.
    With grey_fade_start, near-neutral nodes (C* under grey_chroma) also fade from that L*: Phocus's white is neutral,
    and the fit has no unclipped data there, while saturated colours near L* 98 keep their chroma.
    limit "chroma" compresses C* above knee toward cmax; "box" compresses max(|a*|, |b*|) instead, hue kept,
    which is what the legacy Lab encoding (each of a*, b* within -128..128) actually limits."""
    lut = raw.copy()
    L = np.clip(lut[..., 0], 0, 100)
    a, b = lut[..., 1], lut[..., 2]
    C = np.hypot(a, b)
    h = np.arctan2(b, a)
    over = np.clip((raw[..., 0] - fade_start) / 10.0, 0, 1)
    if grey_fade_start is not None:
        greyish = np.clip((grey_chroma - C) / (0.6 * grey_chroma), 0, 1)
        over = np.maximum(over, np.clip((raw[..., 0] - grey_fade_start) / 10.0, 0, 1) * greyish)
    C = C * (1 - over)
    span = cmax - knee
    if limit == "box":
        m = C * np.maximum(np.abs(np.cos(h)), np.abs(np.sin(h)))
        m2 = np.where(m > knee, knee + span * np.tanh((m - knee) / span), m)
        C = C * np.where(m > 0, m2 / np.maximum(m, 1e-9), 1.0)
    else:
        C = np.where(C > knee, knee + span * np.tanh((C - knee) / span), C)
    lut[..., 0] = L
    lut[..., 1] = C * np.cos(h)
    lut[..., 2] = C * np.sin(h)
    lut[0, 0, 0] = (0, 0, 0)
    return lut


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("lut_npz")
    ap.add_argument("name", help="suffix, e.g. 'HNCS E1'")
    ap.add_argument("outdir")
    ap.add_argument("--input-gain", default=None, help="r,g,b linear gains applied before the LUT (via the input curves)")
    ap.add_argument("--raw-gain", default=None, help="r,g,b gains that act like raw-level multipliers (a white balance "
                    "factor): applied through Capture One's raw response (fit/c1_response.npz), whose shadow toe makes a "
                    "raw multiplier count for more in dark tones than the same gain at the profile input (Finding 47)")
    args = ap.parse_args()

    z = np.load(args.lut_npz)
    raw = z["lut"].reshape(G, G, G, 3)
    # fit_synthetic.py saves an already finalized table; finalizing it again would fade and compress twice.
    # Older tables (no flag) keep the second pass so they rebuild exactly as shipped.
    lut = raw if "finalized" in z and bool(z["finalized"]) else finalize(raw)

    pro = InputProfile(IN + "HasselbladX2DII100C-ProStandard.icm")
    x = np.linspace(0, 1, 1025)
    gains = np.array([float(v) for v in args.input_gain.split(",")]) if args.input_gain else np.ones(3)
    raw_gains = np.array([float(v) for v in args.raw_gain.split(",")]) if args.raw_gain else np.ones(3)

    def through(x, c):
        """Profile-input value x (gamma 1.8) after the channel's input gain and raw-level gain."""
        lin = x ** 1.8 * gains[c]
        if raw_gains[c] != 1:
            rz = np.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "fit", "c1_response.npz"))
            n, v = rz["nominal"], rz["c1"]
            top = (v[-1] - v[-2]) / (n[-1] - n[-2])
            raw = np.where(lin <= v[-1], np.interp(lin, v, n), n[-1] + (lin - v[-1]) / top)
            raw = raw * raw_gains[c]
            lin = np.where(raw <= n[-1], np.interp(raw, n, v), v[-1] + (raw - n[-1]) * top)
        return np.clip(lin, 0, 1) ** (1 / 1.8)

    curves = np.stack([np.round(shaper(np.stack([through(x, c)] * 3, -1))[:, 0] * 65535).astype(np.uint16) for c in range(3)])
    m = Mft2(np.eye(3), curves, lab_to_legacy16(lut), np.array([[0, 65535]] * 3, dtype=np.uint16))
    stem = f"HasselbladX2DII100C-{args.name}"
    data = build_profile(
        pro.data[:128],
        [("desc", desc_tag(stem)), ("cprt", text_tag("Fitted to Phocus renders; personal use")), ("wtpt", pro.tags["wtpt"]), ("A2B0", m.serialize())],
    )
    icc_path = os.path.join(args.outdir, stem + ".icm")
    open(icc_path, "wb").write(data)

    back = InputProfile(icc_path)
    assert back.desc() == stem
    rng = np.random.default_rng(0)
    s = rng.random((20000, 3))
    from fit import predict
    a = tetra(back.a2b0, s)
    b = predict(lut.reshape(-1, 3), np.stack([through(s[:, c], c) for c in range(3)], 1))
    err = np.abs(a - b).max()
    print(f"wrote {icc_path}; round-trip max |Lab| diff vs finalized LUT {err:.3f}")

    neutral = np.linspace(0, 1, 2001)
    Ln = tetra(back.a2b0, np.stack([neutral] * 3, -1))[:, 0]
    print(f"neutral L* monotone: {bool(np.all(np.diff(Ln) >= -1e-6))}; L* at device 0.18/0.5/0.9: {np.interp([0.18, 0.5, 0.9], neutral, Ln).round(1)}")



if __name__ == "__main__":
    main()
