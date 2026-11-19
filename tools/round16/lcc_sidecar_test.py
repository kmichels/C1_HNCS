"""Test C: can a hand-written .cos carry an LCC (colour cast only) together with a custom falloff curve?

Writes an L* 30 flat from HOST into CAPTURE_DIR, preceded by a sidecar whose <AL> block sets the probe
profile, Linear Response, a custom LensLightFallOff curve, ColorCastCorrection 1 and LccID, and copies
LCC_FILE beside it as <name>.3fr.<LccID>.lcc. Then --score compares the rendered flat's B-G and green
profile with the LCC's colour map and the curve.

usage: python lcc_sidecar_test.py HOST.3fr CAPTURE_DIR LCC_FILE LCC_ID [--where AL|DL]
       python lcc_sidecar_test.py --score RENDER.tif COLOUR_MAP.npz
"""
import os
import shutil
import subprocess
import sys
import uuid

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
CURVE = "0,0;14000,-0.5;28000,-1"

if sys.argv[1] != "--score":
    from phocus_hotfolder import set_baseline_exposure, set_landscape
    host, cap, lcc, lcc_id = sys.argv[1:5]
    where = sys.argv[sys.argv.index("--where") + 1] if "--where" in sys.argv else "AL"
    name = f"CL_{where}"
    work = os.path.join(HERE, "..", "..", "data", "synth", "r16")
    tmp = os.path.join(work, name + ".3fr")
    subprocess.run([sys.executable, "-I", os.path.join(HERE, "..", "make_synthetic_raw.py"), host, tmp, "--flat", "30",
                    "--uid", f"HNCSLCCTEST{where}000"[:16]], check=True, capture_output=True)
    set_landscape(tmp); set_baseline_exposure(tmp, 0.0)
    settings = os.path.join(cap, "CaptureOne", "Settings1690")
    keys = f'''			<E K="FilmCurve" V="HasselbladX2DII100C-Linear Response.fcrv" />
			<E K="ICCProfile" V="HasselbladX2DII100C-E0 Probe.icm" />
			<E K="LensLightFallOff" V="{CURVE}|100|1" />
			<E K="ColorCastCorrection" V="1" />
			<E K="LccID" V="{lcc_id}" />
			<E K="LensLCCDustRemovalEnabled" V="0" />
			<E K="LensLccLightFalloff" V="0" />
			<E K="LensLccLightFalloffAmount" V="0" />
'''
    with open(os.path.join(settings, name + ".3fr.cos"), "w") as f:
        f.write(f'''<?xml version="1.0"?>
<IMG>
	<E K="UUID" V="{str(uuid.uuid4()).upper()}" />
	<E K="Version" V="1530" />
	<VAR Engine="1300">
		<E K="ProductID" V="HasselbladX2DII100C" />
		<E K="UUID" V="{str(uuid.uuid4()).upper()}" />
		<{where}>
{keys}		</{where}>
	</VAR>
</IMG>
''')
    shutil.copyfile(lcc, os.path.join(settings, f"{name}.3fr.{lcc_id}.lcc"))
    os.replace(tmp, os.path.join(cap, name + ".3fr"))
    print("wrote", name)
    raise SystemExit

import tifffile
from pairs import romm_decode
rz = np.load(os.path.join(HERE, "..", "..", "fit", "c1_response.npz"))
img = romm_decode(tifffile.imread(sys.argv[2])[..., :3].astype(np.float64) / 65535)
raw = np.stack([np.interp(img[..., c], rz["c1"], rz["nominal"]) for c in range(3)], -1)
H, W = raw.shape[:2]
yy, xx = np.mgrid[0:H, 0:W]
r_um = np.hypot(yy - (H - 1) / 2, xx - (W - 1) / 2) * 3.76 * 2
rn = r_um / np.hypot(H / 2, W / 2) / 7.52
c0 = raw[r_um < 400].mean(0)
cm = np.load(sys.argv[3])
print("r (fraction of half-diagonal) | green gain, stops (curve) | B-G stops measured | B-G in the LCC's colour map")
for f_ in (0.2, 0.4, 0.6, 0.8, 0.9):
    m = np.abs(rn - f_) < 0.01
    v = raw[m].mean(0) / c0
    curve_ev = -np.interp(f_ * np.hypot(H / 2, W / 2) * 7.52, [0, 14000, 28000], [0, -0.5, -1])
    mm = np.abs(cm["radius"] - f_) < 0.02 if "radius" in cm.files else None
    cmap = (np.log2(cm["gain"][..., 2]) - np.log2(cm["gain"][..., 1]))[mm].mean() if mm is not None else float("nan")
    print(f"  {f_:.1f}   {np.log2(v[1]):+.3f} ({curve_ev:+.3f})   {np.log2(v[2] / v[1]):+.3f}   {cmap:+.3f}")
