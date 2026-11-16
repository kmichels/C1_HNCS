"""Turn Phocus's export of a synthetic flat into a raw-gain map for preprocess_3fr.py.

flat_gain.py measures Phocus's per-channel gain in Capture One's camera-RGB scale at the flat's level.
Capture One's Linear Response isn't proportional to raw values in the shadows (fit/c1_response.npz), so
each gain is converted to the raw gain that produces it at that level (and that BaselineExposure). The
result is a plain multiplier on raw values, independent of exposure, and is saved under a name built
from the lens state (lens, focal length, aperture) so preprocess_3fr.py --maps can find it.

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
                        lens=lens, focal=focal, fnumber=fnum)
    r = z["radius"]
    prof = " ".join(f"r{lo}: {np.log2(raw_gain[(r >= lo - .025) & (r < lo + .025), 1]).mean():+.2f}" for lo in (0.4, 0.6, 0.8, 0.9))
    print(f"wrote {out} (flat level {level:.4f}, BaselineExposure {be:+.3f}); green raw gain in stops {prof}")
