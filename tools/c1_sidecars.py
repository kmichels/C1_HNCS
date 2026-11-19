"""Pre-processing without copies: write Capture One settings files that reproduce Phocus's lens processing
on the original raws.

For each raw, from its Phocus map (fit/preprocess_maps, by lens, focal length, aperture and focus code):
  - LensLightFallOff: the map's green gain as a radial curve (radius in µm, EV; up to 16 points). Capture One
    applies it in linear raw space, as pre-processing does (Finding 39);
  - an LCC for the lens's colour shading (colour cast only), when data/lcc_c1/LCC_<lens>.lcc exists, with the
    "HNCS E5 <lens> LCC" profile that undoes the LCC's overall colour shift; otherwise the plain profile;
  - Exposure: the lens-setting brightness;
  - Linear Response.
Capture One honours a settings file only for raws it hasn't seen yet, so write them before importing.
A different body needs its own profile (body_gains.py --input-gain, multiplied by the LCC profile's gain).

An LCC file comes from Capture One: make a reference raw with make_lcc_raw.py (fit/lcc/colour_*.npz), run
Create LCC on it, and copy CaptureOne/Settings*/<ref>.<id>.lcc to data/lcc_c1/LCC_<lens>.lcc. It records the
reference raw's camera serial number, so it isn't committed.

usage: python c1_sidecars.py RAW [RAW ...] [--maps DIR] [--lcc-dir DIR] [--dest DIR] [--force]
"""
import argparse
import os
import shutil
import sys
import uuid

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from make_preprocess_map import FIT, find_map, global_gain, lens_state, profile_name, reference_state  # noqa: E402

HALF_DIAG_UM = np.hypot(11656, 8742) / 2 * 3.76
LCC_IDS = {"28P": "LCC_28P", "35-100": "LCC_35100"}

ap = argparse.ArgumentParser()
ap.add_argument("raws", nargs="+")
ap.add_argument("--maps", default=os.path.join(FIT, "preprocess_maps"))
ap.add_argument("--lcc-dir", default=os.path.join(HERE, "..", "data", "lcc_c1"))
ap.add_argument("--dest", default=None, help="folder the raws will be imported from (default: each raw's own folder)")
ap.add_argument("--force", action="store_true")
ap.add_argument("--state-lcc", default=None, help="use this per-lens-setting LCC (data/lcc_c1/ID.lcc) with uniform light on (testing)")
ap.add_argument("--state-comp", default=None, help="EV,kR,kB: cancel the state LCC's global offset (exposure, and R and B white-balance multipliers)")
ap.add_argument("--profile", default=None, help="override the ICC profile file name (testing, e.g. the probe)")
a = ap.parse_args()


def settings_dir():
    import plistlib
    try:
        v = plistlib.load(open("/Applications/Capture One.app/Contents/Info.plist", "rb"))["CFBundleShortVersionString"]
        return "Settings" + "".join(v.split(".")[:3])
    except (OSError, KeyError):
        return "Settings1690"


def falloff_curve(map_path):
    z = np.load(map_path)
    r, g = z["radius"].ravel(), z["raw_gain"][..., 1].ravel()
    pts = [(0.0, 0.0)]
    for f in (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95):
        m = np.abs(r - f) < 0.025
        pts.append((f * HALF_DIAG_UM, -float(np.log2(g[m].mean()))))
    edge = r > 0.96
    pts.append((28000.0, -float(np.log2(g[edge].mean()))))   # Capture One's own curves end at 28 mm
    return ";".join(f"{x:.0f},{y:.4f}" for x, y in pts)


for raw in a.raws:
    key, lens, focal, fnum = lens_state(raw)
    name = profile_name(lens)
    mp = find_map(a.maps, key)
    if mp is None:
        print(f"{os.path.basename(raw)}: no map for {key}; make it with auto_maps.py first")
        continue
    ref = reference_state(name)
    lut = next((p for p in (os.path.join(FIT, f"lut_e5_{name}.npz"), os.path.join(FIT, f"lut_e5_{name.lower()}.npz")) if os.path.exists(p)), None)
    ref_path = find_map(a.maps, ref) if ref else None
    ev = float(np.log2(global_gain(mp, ref_path, lut))) if (ref_path and lut) else 0.0
    lcc_id = a.state_lcc or LCC_IDS.get(name)
    lcc_file = os.path.join(a.lcc_dir, f"{lcc_id}.lcc") if lcc_id else None
    use_lcc = bool(lcc_file and os.path.exists(lcc_file))
    uniform = bool(a.state_lcc and use_lcc)
    profile = f"HasselbladX2DII100C-HNCS E5 {name}{' LCC' if use_lcc and not uniform else ''}.icm"
    if a.profile:
        profile = a.profile
    wb_key = ""
    if a.state_comp and uniform:
        dev, kr, kb = (float(v) for v in a.state_comp.split(","))
        ev += dev
        import tifffile
        with tifffile.TiffFile(raw) as t:
            nn = t.pages[0].tags["AsShotNeutral"].value
        mult = (nn[1] / nn[0] * kr, 1.0, nn[5] / nn[4] * kb)
        wb_key = f'\t\t\t<E K="WhiteBalance" V="{mult[0]:.6f};1;{mult[2]:.6f}" />\n'
    d = os.path.join(a.dest or os.path.dirname(os.path.abspath(raw)), "CaptureOne", settings_dir())
    os.makedirs(d, exist_ok=True)
    base = os.path.basename(raw)
    path = os.path.join(d, base + ".cos")
    if os.path.exists(path) and not a.force:
        print(f"{base}: settings file exists; skipped")
        continue
    lcc_keys = (f'\t\t\t<E K="ColorCastCorrection" V="1" />\n\t\t\t<E K="LccID" V="{lcc_id}" />\n'
                '\t\t\t<E K="LensLCCDustRemovalEnabled" V="0" />\n'
                f'\t\t\t<E K="LensLccLightFalloff" V="{int(uniform)}" />\n\t\t\t<E K="LensLccLightFalloffAmount" V="{100 if uniform else 0}" />\n') if use_lcc else ""
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
    if use_lcc:
        shutil.copyfile(lcc_file, os.path.join(d, f"{base}.{lcc_id}.lcc"))
    print(f"{base}: {os.path.basename(mp)}, exposure {ev:+.3f} EV, {'LCC ' + lcc_id if use_lcc else 'no LCC'}, profile {profile[20:-4]}")
