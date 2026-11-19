"""Tests A and B for pre-processing without copies: does Capture One use a light-falloff curve written into
a .cos sidecar, and does it apply the curve in linear raw space?

Writes synthetic flat fields (L* 10, 30, 60) from a host raw into the session's Capture folder, each preceded
by a sidecar with the probe profile, Linear Response and a custom falloff curve. Also an L* 30 flat with
falloff off and one with no sidecar (Capture One's own lens data). Render variant 1 of each through the probe
recipe afterwards, then run with --score.

usage: python falloff_sidecar_test.py HOST.3fr CAPTURE_DIR            (write)
       python falloff_sidecar_test.py --score RENDER_DIR WORK_DIR     (measure)
"""
import os
import subprocess
import sys
import uuid

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
CURVE = "0,0;14000,-0.5;28000,-1"   # EV against radius in µm: 0 at the centre, -0.5 at half radius, -1 at the corner
WORK = os.path.join(HERE, "..", "..", "data", "synth", "r16")


def sidecar(path, falloff):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(f'''<?xml version="1.0"?>
<IMG>
	<E K="UUID" V="{str(uuid.uuid4()).upper()}" />
	<E K="Version" V="1530" />
	<VAR Engine="1300">
		<E K="ProductID" V="HasselbladX2DII100C" />
		<E K="UUID" V="{str(uuid.uuid4()).upper()}" />
		<DL>
			<E K="FilmCurve" V="HasselbladX2DII100C-Linear Response.fcrv" />
			<E K="ICCProfile" V="HasselbladX2DII100C-E0 Probe.icm" />
			<E K="LensLightFallOff" V="{falloff}" />
		</DL>
	</VAR>
</IMG>
''')


if sys.argv[1] != "--score":
    from phocus_hotfolder import set_baseline_exposure, set_landscape
    host, cap = sys.argv[1], sys.argv[2]
    settings = os.path.join(cap, "CaptureOne", "Settings1690")
    jobs = [("CF_L10", 10, f"{CURVE}|100|1"), ("CF_L30", 30, f"{CURVE}|100|1"), ("CF_L60", 60, f"{CURVE}|100|1"),
            ("CF_L30off", 30, "|0|1"), ("CF_L30db", 30, None)]
    os.makedirs(WORK, exist_ok=True)
    for i, (name, L, fo) in enumerate(jobs):
        tmp = os.path.join(WORK, name + ".3fr")
        subprocess.run([sys.executable, "-I", os.path.join(HERE, "..", "make_synthetic_raw.py"), host, tmp, "--flat", str(L),
                        "--uid", f"HNCSFALLOFF{i:05d}"], check=True, capture_output=True)
        set_landscape(tmp)
        set_baseline_exposure(tmp, 0.0)
        if fo is not None:
            sidecar(os.path.join(settings, name + ".3fr.cos"), fo)
        os.replace(tmp, os.path.join(cap, name + ".3fr"))
        print("wrote", name, "sidecar" if fo else "no sidecar")
    raise SystemExit

import tifffile
from pairs import romm_decode
rz = np.load(os.path.join(HERE, "..", "..", "fit", "c1_response.npz"))
rend = sys.argv[2]
pitch_um = 3.76 * 2                      # 50% render
curve = np.array([[float(v) for v in p.split(",")] for p in CURVE.split(";")])
print("radius(um)  curve EV  | per flat: C1-domain gain (stops), raw-equivalent gain (stops)")
res = {}
for name in ("CF_L10", "CF_L30", "CF_L60", "CF_L30off", "CF_L30db"):
    img = romm_decode(tifffile.imread(os.path.join(rend, name + ".tif"))[..., :3].astype(np.float64) / 65535)
    g = img[..., 1]
    H, W = g.shape
    yy, xx = np.mgrid[0:H, 0:W]
    r = np.hypot(yy - (H - 1) / 2, xx - (W - 1) / 2) * pitch_um
    c0 = g[r < 400].mean()
    prof = []
    for rad in (7000, 14000, 21000, 26000):
        m = np.abs(r - rad) < 300
        v = g[m].mean()
        n0 = np.interp(c0, rz["c1"], rz["nominal"])
        raw = np.interp(v, rz["c1"], rz["nominal"]) / n0
        prof.append((np.log2(v / c0), np.log2(raw)))
    res[name] = prof
    print(f"{name:10s} centre C1 green {c0:.4f} | " + "  ".join(f"r{rad // 1000}mm {a:+.3f}/{b:+.3f}" for rad, (a, b) in zip((7, 14, 21, 26), prof)))
print("curve EV at r 7/14/21/26 mm:", np.round(-np.interp([7000, 14000, 21000, 26000], curve[:, 0], curve[:, 1]), 3), "(as a gain)")
