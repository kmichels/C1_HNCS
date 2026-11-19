"""Build each lens's LCC colour factor into its profiles (Finding 47).

An LCC shifts a photo's overall colour by a factor that is nearly the same for every setting of a lens (red
x1.02 and blue x0.96 on the 28P). Settings files used to cancel it in the white balance, so choosing a
white-balance preset or a Kelvin value in Capture One dropped it. This writes the factor into every profile
of the lens (daylight, Shade, Tungsten), acting like a raw-level multiplier, and records it in fit/lcc_colour.json; c1_sidecars.py
then divides it back out of each photo's white balance, so only the small per-setting remainder rides there.

The factor for a lens is the mean of its calibrated LCCs (data/lcc_c1/*.json), or, for a lens without any, an
estimate from its maps alone (each channel's mean of 1/map, which is what the LCC is normalised by; within
about 0.005 of calibration).

usage: python bake_lcc_colour.py [--lens NAME ...] [--install] [--if-estimated]
  --if-estimated: only lenses with no factor yet or one estimated from maps (prepare_folder.py --make-lccs
  uses this, so a calibrated factor never changes under photos already prepared)
"""
import argparse
import glob
import json
import os
import shutil
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from make_preprocess_map import FIT, profile_name  # noqa: E402

REPO = os.path.join(HERE, "..")
LCC_DIR = os.path.join(REPO, "data", "lcc_c1")
MAPS = os.path.join(FIT, "preprocess_maps")
COLOUR = os.path.join(FIT, "lcc_colour.json")
LIGHTS = ("", " Shade", " Tungsten")


def map_lens(map_path):
    return profile_name(str(np.load(map_path)["lens"]))


def map_estimate(map_path):
    z = np.load(map_path)
    inv = (1 / z["raw_gain"][z["radius"] < 0.97]).mean(0)
    return inv[1] / inv[0], inv[1] / inv[2]


def lens_factor(name):
    cal = []
    for p in glob.glob(os.path.join(LCC_DIR, "*.json")):
        j = json.load(open(p))
        mp = os.path.join(MAPS, j.get("map", ""))
        if j.get("reference") == "map in raw" and os.path.exists(mp) and map_lens(mp) == name:
            cal.append((j["kR"], j["kB"]))
    if cal:
        return float(np.mean([c[0] for c in cal])), float(np.mean([c[1] for c in cal])), f"calibrated from {len(cal)} LCC{'s' if len(cal) != 1 else ''}"
    est = [map_estimate(p) for p in glob.glob(os.path.join(MAPS, "*.npz")) if map_lens(p) == name]
    if est:
        return float(np.mean([e[0] for e in est])), float(np.mean([e[1] for e in est])), f"estimated from {len(est)} maps"
    return 1.0, 1.0, "none (no LCCs or maps yet)"


def table_for(name, light):
    suffix = light.lower().replace(" ", "_")
    for n in (name, name.lower()):
        p = os.path.join(FIT, f"lut_e5_{n}{suffix}.npz")
        if os.path.exists(p):
            return p
    return None


def bake(name, install=False, quiet=False):
    """Write every profile of lens NAME with its factor, record it, and return (kR, kB)."""
    kR, kB, source = lens_factor(name)
    colour = json.load(open(COLOUR)) if os.path.exists(COLOUR) else {}
    colour[name] = {"kR": round(kR, 5), "kB": round(kB, 5), "source": source}
    json.dump(colour, open(COLOUR, "w"), indent=1, sort_keys=True)
    for light in LIGHTS:
        lut = table_for(name, light)
        if lut is None:
            continue
        pname = f"HNCS E5 {name}{light}"
        subprocess.run([sys.executable, "-I", os.path.join(HERE, "write_profile.py"), lut, pname, os.path.join(REPO, "profiles"),
                        "--raw-gain", f"{kR:.5f},1,{kB:.5f}"], check=True, capture_output=True)
        icc = f"HasselbladX2DII100C-{pname}.icm"
        if install:
            shutil.copyfile(os.path.join(REPO, "profiles", icc), os.path.expanduser(f"~/Library/ColorSync/Profiles/{icc}"))
        if not quiet:
            print(f"{pname}: red x{kR:.4f}, blue x{kB:.4f} ({source})")
    return kR, kB


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lens", nargs="*", help="profile names, e.g. 28P XCD55V (default: every lens with a daylight table)")
    ap.add_argument("--install", action="store_true", help="also copy the profiles into ~/Library/ColorSync/Profiles")
    ap.add_argument("--if-estimated", action="store_true")
    a = ap.parse_args()
    names = a.lens or sorted({os.path.basename(p)[7:-4] for p in glob.glob(os.path.join(FIT, "lut_e5_*.npz"))
                              if not p.endswith(("_shade.npz", "_tungsten.npz"))})
    names = [{"28p": "28P"}.get(n, n) for n in names]
    colour = json.load(open(COLOUR)) if os.path.exists(COLOUR) else {}
    baked = 0
    for n in names:
        if a.if_estimated and "calibrated" in colour.get(n, {}).get("source", ""):
            continue
        bake(n, a.install)
        baked += 1
    if a.install and baked:
        print("installed; restart Capture One")


if __name__ == "__main__":
    main()
