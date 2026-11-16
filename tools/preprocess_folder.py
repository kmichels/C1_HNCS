"""Pre-process a folder of X2D II raws: write a corrected copy of each (same file name) into another
folder, for Capture One with the "HNCS E5 … (pre-processed)" styles. Originals are only read; existing
copies are skipped. With --make-maps, missing maps are made first through Phocus (auto_maps.py); with
--make-profiles, an E5 profile and styles are built for any lens that has none (auto_lens_profile.py,
installed into Capture One; restart it afterwards).

Each copy also gets a Capture One settings sidecar (OUT_DIR/CaptureOne/Settings<version>/<name>.cos) that
opens it with the lens's E5 profile, Linear Response and Light Falloff 0, so no style needs applying.
Capture One reads it when it first sees the file (a session folder, or browsing to OUT_DIR); for an image it
already knows, apply the "(pre-processed)" style instead.

usage: python preprocess_folder.py IN_DIR OUT_DIR [--maps fit/preprocess_maps] [--make-maps] [--make-profiles]
       [--body-gains] [--no-sidecars]
"""
import argparse
import glob
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from make_preprocess_map import find_map, lens_state, profile_name  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("inp"); ap.add_argument("out")
ap.add_argument("--maps", default=os.path.join(HERE, "..", "fit", "preprocess_maps"))
ap.add_argument("--make-maps", action="store_true", help="make missing maps with Phocus first (restarts Phocus)")
ap.add_argument("--make-profiles", action="store_true", help="build an E5 profile for lenses without one (Phocus)")
ap.add_argument("--body-gains", action="store_true")
ap.add_argument("--no-sidecars", action="store_true", help="don't write Capture One settings sidecars")
a = ap.parse_args()
if os.path.realpath(a.inp) == os.path.realpath(a.out):
    sys.exit("OUT_DIR must differ from IN_DIR (corrected copies keep the original file names)")
raws = sorted(f for f in glob.glob(os.path.join(a.inp, "*")) if f.lower().endswith(".3fr"))
if not raws:
    sys.exit(f"no .3fr files in {a.inp}")
os.makedirs(a.out, exist_ok=True)
todo = [r for r in raws if not os.path.exists(os.path.join(a.out, os.path.basename(r)))]
keys = {r: lens_state(r)[0] for r in todo}
if a.make_maps and any(not os.path.exists(os.path.join(a.maps, k + ".npz")) for k in keys.values()):
    subprocess.run([sys.executable, "-I", os.path.join(HERE, "auto_maps.py"), *todo, "--maps", a.maps], check=True)
missing = sorted({k for k in keys.values() if find_map(a.maps, k) is None})
by_lens = {}
for r in raws:
    by_lens.setdefault(profile_name(lens_state(r)[1]), []).append(r)
no_profile = [n for n in by_lens if not os.path.exists(os.path.join(HERE, "..", "profiles", f"HasselbladX2DII100C-HNCS E5 {n}.icm"))]
if no_profile and a.make_profiles:
    for n in no_profile:
        subprocess.run([sys.executable, "-I", os.path.join(HERE, "auto_lens_profile.py"), *by_lens[n], "--install"], check=True)
    no_profile = [n for n in no_profile if not os.path.exists(os.path.join(HERE, "..", "profiles", f"HasselbladX2DII100C-HNCS E5 {n}.icm"))]
def c1_settings_dir():
    import plistlib
    try:
        v = plistlib.load(open("/Applications/Capture One.app/Contents/Info.plist", "rb"))["CFBundleShortVersionString"]
        return "Settings" + "".join(v.split(".")[:3])
    except (OSError, KeyError):
        return "Settings1690"


def write_sidecar(dst, name):
    import uuid
    d = os.path.join(os.path.dirname(dst), "CaptureOne", c1_settings_dir())
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, os.path.basename(dst) + ".cos")
    if os.path.exists(path):
        return
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
			<E K="ICCProfile" V="HasselbladX2DII100C-HNCS E5 {name}.icm" />
			<E K="LensLightFallOff" V="|0|1" />
		</DL>
	</VAR>
</IMG>
''')


done, skipped = 0, []
for r in todo:
    key = keys[r]
    if key in missing:
        skipped.append(os.path.basename(r)); continue
    dst = os.path.join(a.out, os.path.basename(r))
    cmd = [sys.executable, "-I", os.path.join(HERE, "preprocess_3fr.py"), r, dst + ".part", "--maps", a.maps]
    if a.body_gains:
        cmd.append("--body-gains")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"{os.path.basename(r)}: failed: {res.stderr.strip()[-300:]}")
        if os.path.exists(dst + ".part"):
            os.remove(dst + ".part")
        continue
    lens_name = profile_name(lens_state(r)[1])
    if not a.no_sidecars and lens_name not in no_profile:
        write_sidecar(dst, lens_name)  # before the raw appears, so Capture One finds it on first sight
    os.replace(dst + ".part", dst)
    done += 1
    print(f"{os.path.basename(r)}: {res.stdout.strip().splitlines()[0]}", flush=True)
print(f"\n{done} written, {len(raws) - len(todo)} already there, {len(skipped)} without a map"
      + (f" ({', '.join(missing)}; run with --make-maps)" if skipped else ""))
for n in sorted(by_lens):
    style = f"HNCS E5 {n} (pre-processed)"
    note = " (no profile yet: run with --make-profiles)" if n in no_profile else ""
    how = "opens with it already (sidecar)" if not a.no_sidecars and n not in no_profile else f"apply the style '{style}'"
    print(f"{n}: {how}{note}")
