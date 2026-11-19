"""Write Capture One settings files that give original X2D II raws Phocus's HNCS rendering, lens correction
included, with no corrected copies (Findings 39-41).

For each raw, from its lens setting (lens, focal length, aperture, focus code):
  - when that setting has a calibrated LCC (data/lcc_c1/<map key>.lcc and .json, made by state_lcc.py):
      the "HNCS E5 <lens>" profile, Linear Response, the LCC with colour cast and uniform light on (it carries
      Phocus's whole 2-D correction, so Light Falloff is off), and exposure and white balance that cancel the
      LCC's overall colour shift and add Phocus's lens-setting brightness. The lens's typical colour shift is
      built into its profiles (bake_lcc_colour.py, fit/lcc_colour.json), so the white balance only carries this
      setting's small remainder, and choosing another white balance in Capture One keeps the colour right;
  - otherwise a fallback: Phocus's correction as a radial Light Falloff curve, which can't follow its
    elliptical shape or colour shading (make the LCC with prepare_folder.py --make-lccs), and a white balance
    that cancels the colour shift built into the profile;
  - by the As Shot white balance, the lens's "Tungsten" profile below about 4000 K, its "Warm" profile up to
    about 4850 K, and its "Shade" profile above about 6200 K, where there is one;
  - the body's factory calibration (maker note 0x0019), as exposure and white balance relative to the body
    the profiles were made on, so any X2D II uses the same profiles (--no-body-gains turns this off).
Capture One applies a settings file only to a raw it hasn't seen, so write them before importing. They go in
<folder>/CaptureOne/Settings<version>/ beside the raws, where Capture One keeps its own; each raw also gets a
copy of its LCC file there (28 KB).

usage: python c1_sidecars.py RAW [RAW ...] [--dest DIR] [--force] [--no-body-gains]
       testing: [--maps DIR] [--lcc-dir DIR] [--profile FILE] [--state-lcc ID] [--state-comp EV,kR,kB]
"""
import argparse
import json
import os
import shutil
import sys
import uuid

import numpy as np
import tifffile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from make_preprocess_map import FIT, find_map, global_gain, lens_state, profile_name, reference_state  # noqa: E402
from makernote_transplant import entries  # noqa: E402

HALF_DIAG_UM = np.hypot(11656, 8742) / 2 * 3.76
TUNGSTEN_BELOW_K = 4000                                # tungsten profiles fit ~3100-4200 K and beat warm below ~4000 K
WARM_BELOW_K = 4850                                    # warm profiles fit 4200-5000 K; on real photos they win up to ~4850 K
SHADE_ABOVE_K = 6200                                   # shade profiles fit ~6300-8600 K and beat daylight from ~6200 K
BODY_REF = (2.600, 2.260)                              # GAIN record of the body the profiles were fitted on
COLOUR = os.path.join(FIT, "lcc_colour.json")          # each lens's LCC colour factor, built into its profiles


INSTALLED_BODY = os.path.join(HERE, "..", "data", "installed_body.json")   # bake_lcc_colour.py --body


def baked_colour(name, profile):
    """The gains built into the installed PROFILE, if it is one of lens NAME's HNCS profiles: the lens's LCC
    colour factor (kR, 1, kB) times the camera correction of bake_lcc_colour.py --body, if one was installed."""
    if not profile.startswith("HasselbladX2DII100C-HNCS E5 "):
        return np.ones(3)
    g = np.ones(3)
    c = json.load(open(COLOUR)).get(name) if os.path.exists(COLOUR) else None
    if c:
        g = g * np.array([c["kR"], 1.0, c["kB"]])
    if os.path.exists(INSTALLED_BODY):
        g = g * np.array(json.load(open(INSTALLED_BODY))["gains"])
    return g


def lcc_id(map_path):
    """LCC name for a map: its file stem with dots replaced, as Capture One names an LCC after its reference."""
    return os.path.splitext(os.path.basename(map_path))[0].replace(".", "p")


def settings_dir(folder):
    import plistlib
    try:
        v = plistlib.load(open("/Applications/Capture One.app/Contents/Info.plist", "rb"))["CFBundleShortVersionString"]
        name = "Settings" + "".join(v.split(".")[:3])
    except (OSError, KeyError):
        name = "Settings1690"
    return os.path.join(folder, "CaptureOne", name)


def body_gain(raw):
    """Phocus's per-body camera RGB gain (1, kG, kB) relative to BODY_REF (Findings 13, 16, 35)."""
    rec = entries(raw)[0x0019]["raw"]
    g1, g2 = (round(float(v), 3) for v in np.frombuffer(rec[84:88], "<f2"))
    g1, g2 = (v if v > 0 else 2.1 for v in (g1, g2))
    return np.array([1.0, (g1 / BODY_REF[0]) ** 0.077, (g2 / BODY_REF[1]) ** 0.078])


def as_shot_kelvin(raw):
    """Correlated colour temperature of the raw's As Shot white balance, from its ColorMatrix1 (McCamy)."""
    with tifffile.TiffFile(raw) as t:
        tags = t.pages[0].tags
        v, n = tags["ColorMatrix1"].value, tags["AsShotNeutral"].value
    cm = np.array([v[2 * i] / v[2 * i + 1] for i in range(9)]).reshape(3, 3)
    xyz = np.linalg.solve(cm, np.array([n[0] / n[1], n[2] / n[3], n[4] / n[5]]))
    x, y = xyz[0] / xyz.sum(), xyz[1] / xyz.sum()
    m = (x - 0.3320) / (0.1858 - y)
    return 449 * m**3 + 3525 * m**2 + 6823.3 * m + 5520.33


def daylight_neutral(raw, kelvin, offset=(0.0, 0.0)):
    """As Shot neutral (R, 1, B) for a daylight-locus colour temperature, from the raw's ColorMatrix1, times
    exp(offset) on R and B. Real X2D II As Shot neutrals sit about (-0.05, -0.06) off the locus."""
    with tifffile.TiffFile(raw) as t:
        v = t.pages[0].tags["ColorMatrix1"].value
    cm = np.array([v[2 * i] / v[2 * i + 1] for i in range(9)]).reshape(3, 3)
    T = float(kelvin)
    if T <= 7000:
        x = -4.6070e9 / T**3 + 2.9678e6 / T**2 + 0.09911e3 / T + 0.244063
    else:
        x = -2.0064e9 / T**3 + 1.9018e6 / T**2 + 0.24748e3 / T + 0.237040
    y = -3.000 * x * x + 2.870 * x - 0.275
    n = cm @ np.array([x / y, 1.0, (1 - x - y) / y])
    n = n / n[1]
    return n * np.exp([offset[0], 0.0, offset[1]])


def profile_for(name, raw):
    """The lens's E5 profile, or its tungsten, warm or shade version for the photo's As Shot, when one exists."""
    k = as_shot_kelvin(raw)
    light = ("Tungsten" if k < TUNGSTEN_BELOW_K else "Warm" if k < WARM_BELOW_K else
             "Shade" if k > SHADE_ABOVE_K else None)
    if light:
        f = f"HasselbladX2DII100C-HNCS E5 {name} {light}.icm"
        if os.path.exists(os.path.join(HERE, "..", "profiles", f)):
            return f
    return f"HasselbladX2DII100C-HNCS E5 {name}.icm"


def falloff_curve(map_path):
    z = np.load(map_path)
    r, g = z["radius"].ravel(), z["raw_gain"][..., 1].ravel()
    pts = [(0.0, 0.0)]
    for f in (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95):
        m = np.abs(r - f) < 0.025
        pts.append((f * HALF_DIAG_UM, -float(np.log2(g[m].mean()))))
    pts.append((28000.0, -float(np.log2(g[r > 0.96].mean()))))   # Capture One's own curves end at 28 mm
    return ";".join(f"{x:.0f},{y:.4f}" for x, y in pts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("raws", nargs="+")
    ap.add_argument("--dest", default=None, help="folder the raws will be imported from (default: each raw's own folder)")
    ap.add_argument("--force", action="store_true", help="overwrite existing settings files")
    ap.add_argument("--no-body-gains", action="store_true")
    ap.add_argument("--maps", default=os.path.join(FIT, "preprocess_maps"))
    ap.add_argument("--lcc-dir", default=os.path.join(HERE, "..", "data", "lcc_c1"))
    ap.add_argument("--profile", default=None, help="override the ICC profile file name (testing, e.g. the probe)")
    ap.add_argument("--state-lcc", default=None, help="use this LCC instead of the lens setting's (testing)")
    ap.add_argument("--state-comp", default=None, help="EV,kR,kB instead of the LCC's saved calibration (testing)")
    a = ap.parse_args()

    counts = {"lcc": 0, "fallback": 0, "skipped": 0}
    for raw in a.raws:
        base = os.path.basename(raw)
        key, lens, focal, fnum = lens_state(raw)
        name = profile_name(lens)
        mp = find_map(a.maps, key)
        if mp is None:
            print(f"{base}: no map for {key}; make it first (prepare_folder.py --make-maps)")
            counts["skipped"] += 1
            continue
        d = settings_dir(a.dest or os.path.dirname(os.path.abspath(raw)))
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, base + ".cos")
        if os.path.exists(path) and not a.force:
            print(f"{base}: settings file exists; skipped")
            counts["skipped"] += 1
            continue

        ref = reference_state(name)
        lut = next((p for p in (os.path.join(FIT, f"lut_e5_{name}.npz"), os.path.join(FIT, f"lut_e5_{name.lower()}.npz")) if os.path.exists(p)), None)
        ref_path = find_map(a.maps, ref) if ref else None
        ev = float(np.log2(global_gain(mp, ref_path, lut))) if (ref_path and lut) else 0.0
        gains = body_gain(raw) if not a.no_body_gains else np.ones(3)       # R, G, B raw-domain gains

        sid = a.state_lcc or lcc_id(mp)
        state = os.path.exists(os.path.join(a.lcc_dir, sid + ".lcc")) and (a.state_comp or os.path.exists(os.path.join(a.lcc_dir, sid + ".json")))
        if state:
            if a.state_comp:
                cev, ckr, ckb = (float(v) for v in a.state_comp.split(","))
            else:
                cj = json.load(open(os.path.join(a.lcc_dir, sid + ".json")))
                cev, ckr, ckb = cj["ev"], cj["kR"], cj["kB"]
            gains = gains * np.array([ckr, 1.0, ckb]) * 2 ** cev
            use_id, uniform = sid, True
            route = f"LCC {sid}"
        else:
            use_id, uniform = None, False
            route = f"fallback: radial falloff curve (no LCC for {lcc_id(mp)} yet)"
        profile = profile_for(name, raw)
        if a.profile:
            profile = a.profile
        gains = gains / baked_colour(name, profile)   # the profile already applies these (LCC colour, installed body)

        ev += float(np.log2(gains[1]))
        wb = gains / gains[1]
        lcc_keys = (f'\t\t\t<E K="ColorCastCorrection" V="1" />\n\t\t\t<E K="LccID" V="{use_id}" />\n'
                    '\t\t\t<E K="LensLCCDustRemovalEnabled" V="0" />\n'
                    f'\t\t\t<E K="LensLccLightFalloff" V="{int(uniform)}" />\n'
                    f'\t\t\t<E K="LensLccLightFalloffAmount" V="{100 if uniform else 0}" />\n') if use_id else ""
        wb_key = ""
        if uniform or np.abs(wb - 1).max() > 1e-4:   # with an LCC always, as in its calibration
            with tifffile.TiffFile(raw) as t:
                nn = t.pages[0].tags["AsShotNeutral"].value
            mult = (nn[1] / nn[0] * wb[0], 1.0, nn[5] / nn[4] * wb[2])
            wb_key = f'\t\t\t<E K="WhiteBalance" V="{mult[0]:.6f};1;{mult[2]:.6f}" />\n'
        with open(path, "w") as f:
            f.write(f'''<?xml version="1.0"?>
<IMG>
	<E K="UUID" V="{str(uuid.uuid4()).upper()}" />
	<E K="Version" V="1530" />
	<VAR Engine="1300">
		<E K="ProductID" V="HasselbladX2DII100C" />
		<E K="UUID" V="{str(uuid.uuid4()).upper()}" />
		<AL>
			<E K="FilmCurve" V="HasselbladX2DII100C-Linear Response.fcrv" />
			<E K="ICCProfile" V="{profile}" />
			<E K="LensLightFallOff" V="{falloff_curve(mp)}|{0 if uniform else 100}|1" />
			<E K="Exposure" V="{ev:.4f}" />
{lcc_keys}{wb_key}		</AL>
	</VAR>
</IMG>
''')
        if use_id:
            shutil.copyfile(os.path.join(a.lcc_dir, f"{use_id}.lcc"), os.path.join(d, f"{base}.{use_id}.lcc"))
        counts["lcc" if state else "fallback"] += 1
        print(f"{base}: {os.path.basename(mp)}, exposure {ev:+.3f} EV, {route}, profile {profile[20:-4]}")
    print(f"\n{counts['lcc']} with their lens setting's LCC, {counts['fallback']} on the fallback, {counts['skipped']} skipped")


if __name__ == "__main__":
    main()
