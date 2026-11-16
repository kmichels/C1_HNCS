"""Turn Phocus's export of a synthetic flat into a raw-gain map for preprocess_3fr.py.

flat_gain.py measures Phocus's per-channel gain in Capture One's camera-RGB scale at the flat's level.
Capture One's Linear Response isn't proportional to raw values in the shadows (fit/c1_response.npz), so
each gain is converted to the raw gain that produces it at that level (and that BaselineExposure). The
result is a plain multiplier on raw values, independent of exposure, and is saved under a name built
from the lens state (lens, focal length, aperture) so preprocess_3fr.py --maps can find it.

The map also keeps Phocus's absolute brightness at the frame centre (centre_lab, at the flat's level
with BaselineExposure 0). Phocus normalises brightness per lens state (aperture, focal length) on top of
its vignetting correction; global_gain() turns the difference from the profile's reference lens state
into one more raw multiplier.

usage: python make_preprocess_map.py FLAT_GAIN.npz FLAT.3fr OUTDIR [--flat-level L]
  FLAT.3fr is the synthetic flat (make_synthetic_raw.py --flat) Phocus rendered; its .flat.npz gives the
  level unless --flat-level is given.
"""
import argparse
import os

import numpy as np
import tifffile


def lens_state(path):
    """(key, lens, focal mm, f-number) from a 3FR's EXIF."""
    with tifffile.TiffFile(path) as t:
        ex = t.pages[0].tags["ExifTag"].value
    lens = str(ex.get("LensModel", "unknown")).split("@")[0].strip()
    r = lambda v: v[0] / v[1] if isinstance(v, tuple) else float(v)
    focal, fnum = r(ex.get("FocalLength", (0, 1))), r(ex.get("FNumber", (0, 1)))
    return f"{lens.replace(' ', '')}_{focal:.0f}mm_f{fnum:.1f}", lens, focal, fnum


SHIPPED_NAMES = {"XCD 28P": "28P", "XCD 35-100E": "35-100"}
FIT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "fit")


def reference_state(name):
    """Lens state the 'HNCS E5 <name>' profile was fitted at (fit/lens_references.json)."""
    import json
    refs = json.load(open(os.path.join(FIT, "lens_references.json")))
    return refs.get(name)


def global_gain(map_npz, ref_npz, lut_npz):
    """Raw multiplier that makes Phocus's centre brightness for this lens state match the profile's
    reference state, from the two maps' centre_lab (same flat level, BaselineExposure 0)."""
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from fit import predict
    lut = np.load(lut_npz)["lut"]

    def invert(lab):
        d = np.full((1, 3), 0.3)
        for _ in range(30):
            f0 = predict(lut, d) - lab[None]
            J = np.stack([(predict(lut, d + np.eye(3)[c] * 1e-3) - lab[None] - f0)[0] / 1e-3 for c in range(3)], 1)
            d = np.clip(d - np.linalg.solve(J + 1e-9 * np.eye(3), f0[0])[None], 1e-4, 1)
        return d[0] ** 1.8
    m, r = np.load(map_npz), np.load(ref_npz)
    if "centre_lab" not in m.files or "centre_lab" not in r.files:
        return 1.0
    ratio = invert(m["centre_lab"])[1] / invert(r["centre_lab"])[1]  # Capture One scale, green
    rz = np.load(os.path.join(FIT, "c1_response.npz"))
    n0 = float(m["level"])
    return float(np.interp(ratio * np.interp(n0, rz["nominal"], rz["c1"]), rz["c1"], rz["nominal"]) / n0)


def profile_name(lens):
    """Name used in 'HNCS E5 <name>' for a lens model (the shipped short names for the 28P and 35-100)."""
    return SHIPPED_NAMES.get(lens, lens.replace(" ", ""))


def baseline_exposure(path):
    with tifffile.TiffFile(path) as t:
        tags = t.pages[0].tags
        v = tags["BaselineExposure"].value if "BaselineExposure" in tags else (0, 1)
    return v[0] / v[1]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("flat_gain"); ap.add_argument("flat_raw"); ap.add_argument("outdir")
    ap.add_argument("--flat-level", type=float, default=None)
    a = ap.parse_args()
    level = a.flat_level
    if level is None:
        level = float(np.load(os.path.splitext(a.flat_raw)[0] + ".flat.npz")["level"])
    be = baseline_exposure(a.flat_raw)
    key, lens, focal, fnum = lens_state(a.flat_raw)
    z = np.load(a.flat_gain)
    rz = np.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "fit", "c1_response.npz"))
    n0 = level * 2.0 ** be
    c1 = np.interp(n0, rz["nominal"], rz["c1"])
    raw_gain = np.interp(z["gain"] * c1, rz["c1"], rz["nominal"]) / n0
    os.makedirs(a.outdir, exist_ok=True)
    out = os.path.join(a.outdir, key + ".npz")
    np.savez_compressed(out, raw_gain=raw_gain.astype(np.float32), block=z["block"], shape=z["shape"], radius=z["radius"],
                        lens=lens, focal=focal, fnumber=fnum, centre_lab=z["centre_lab"], level=n0, baseline_exposure=be)
    r = z["radius"]
    prof = " ".join(f"r{lo}: {np.log2(raw_gain[(r >= lo - .025) & (r < lo + .025), 1]).mean():+.2f}" for lo in (0.4, 0.6, 0.8, 0.9))
    print(f"wrote {out} (flat level {level:.4f}, BaselineExposure {be:+.3f}); green raw gain in stops {prof}")
