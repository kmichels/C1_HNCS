"""Write a fitted LUT as a Capture One camera ICC (v2.4 scnr RGB->Lab, A2B0 mft2 33^3) and a matching .costyle."""
import argparse
import os
import sys
import uuid

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from fit import G, shaper  # noqa: E402
from icc import InputProfile, Mft2, build_profile, desc_tag, lab_to_legacy16, text_tag  # noqa: E402
from tetra import tetra  # noqa: E402

IN = "/Applications/Capture One.app/Contents/Frameworks/ImageProcessing.framework/Versions/A/Resources/Profiles/Input/"


def finalize(raw, knee=90.0, cmax=127.0):
    """Make the fitted LUT storable and well-behaved where there was no data:
    L* clipped to [0, 100] with chroma fading out as L* nears 100, then soft-compressed chroma."""
    lut = raw.copy()
    L = np.clip(lut[..., 0], 0, 100)
    a, b = lut[..., 1], lut[..., 2]
    C = np.hypot(a, b)
    h = np.arctan2(b, a)
    over = np.clip((raw[..., 0] - 95.0) / 10.0, 0, 1)  # beyond Phocus white: fade to neutral
    C = C * (1 - over)
    span = cmax - knee
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
    ap.add_argument("--input-gain", default=None, help="r,g,b linear gains applied before the LUT (via the input curves), e.g. to undo an LCC's global colour shift")
    args = ap.parse_args()

    raw = np.load(args.lut_npz)["lut"].reshape(G, G, G, 3)
    lut = finalize(raw)

    pro = InputProfile(IN + "HasselbladX2DII100C-ProStandard.icm")
    x = np.linspace(0, 1, 1025)
    gains = np.array([float(v) for v in args.input_gain.split(",")]) if args.input_gain else np.ones(3)
    curves = np.stack([np.round(shaper(np.stack([np.clip(x * gains[c] ** (1 / 1.8), 0, 1)] * 3, -1))[:, 0] * 65535).astype(np.uint16) for c in range(3)])
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
    b = predict(lut.reshape(-1, 3), np.clip((s ** 1.8 * gains) ** (1 / 1.8), 0, 1))
    err = np.abs(a - b).max()
    print(f"wrote {icc_path}; round-trip max |Lab| diff vs finalized LUT {err:.3f}")

    neutral = np.linspace(0, 1, 2001)
    Ln = tetra(back.a2b0, np.stack([neutral] * 3, -1))[:, 0]
    print(f"neutral L* monotone: {bool(np.all(np.diff(Ln) >= -1e-6))}; L* at device 0.18/0.5/0.9: {np.interp([0.18, 0.5, 0.9], neutral, Ln).round(1)}")

    style = f"""<?xml version="1.0"?>
<SL Engine="1300">
	<E K="FilmCurve" V="HasselbladX2DII100C-Linear Response.fcrv" />
	<E K="ICCProfile" V="{stem}.icm" />
	<E K="Name" V="{args.name}" />
	<E K="StyleSource" V="Styles" />
	<E K="UUID" V="{str(uuid.uuid4()).upper()}" />
</SL>
"""
    style_path = os.path.join(args.outdir, f"{args.name}.costyle")
    open(style_path, "w").write(style)
    print(f"wrote {style_path}")


if __name__ == "__main__":
    main()
