"""Build an HNCS E5 profile for a lens from any of its raws, unattended, using only Phocus.

Synthetic patch grids are written into a copy of one of the raws (so Phocus sees that lens), at the raw's
own white balance and five more daylight white balances, plus a flat field for Phocus's spatial gain.
Phocus renders them through its hot folder. Capture One's camera RGB for each patch comes from
fit/c1_patch_lookup.npz (measured once; the same for any lens and white balance), so Capture One isn't
needed. The fitted table is written as a Capture One profile, with a plain style and a "(pre-processed)"
style (Light Falloff 0) for raws made by preprocess_3fr.py.

Phocus is restarted and its preferences restored afterwards; don't use it meanwhile. Raws are only read.

usage: python auto_lens_profile.py RAW [RAW ...] [--name NAME] [--out DIR] [--install]
  NAME defaults to the lens model (e.g. XCD55V); files go to DIR (default: the repo's profiles/, styles/
  and fit/); --install also copies the profile and styles into Capture One's folders (restart Capture One).
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import uuid

import numpy as np
import tifffile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
from make_preprocess_map import lens_state, profile_name  # noqa: E402
from phocus_hotfolder import HotFolder, set_baseline_exposure, set_landscape  # noqa: E402

WB_GRIDS = ["HNCSwbA1", "HNCSwbA2", "HNCSwbA3", "HNCSwbA4", "HNCSwbA5"]  # their As Shot neutrals are reused

ap = argparse.ArgumentParser()
ap.add_argument("raws", nargs="+")
ap.add_argument("--name", default=None)
ap.add_argument("--out", default=None, help="write everything into this folder instead of the repo")
ap.add_argument("--install", action="store_true")
a = ap.parse_args()


def orientation(path):
    with tifffile.TiffFile(path) as t:
        tag = t.pages[0].tags.get("Orientation")
        return 1 if tag is None else tag.value


host = next((r for r in a.raws if orientation(r) == 1), a.raws[0])
lens = lens_state(host)[1]
name = a.name or profile_name(lens)
pname = f"HNCS E5 {name}"
prof_dir = a.out or os.path.join(REPO, "profiles")
style_dir = a.out or os.path.join(REPO, "styles")
lut_path = os.path.join(a.out or os.path.join(REPO, "fit"), f"lut_e5_{name}.npz")
for d in (prof_dir, style_dir, os.path.dirname(lut_path)):
    os.makedirs(d, exist_ok=True)
print(f"lens {lens} -> profile '{pname}', host {os.path.basename(host)}", flush=True)

py = sys.executable
work = tempfile.mkdtemp(prefix="hncs-lens-")
run = lambda *args: subprocess.run([py, "-I", *args], check=True, capture_output=True, text=True).stdout
try:
    grids = []
    for i in range(3):
        grids.append((f"g{i}", ["--levels", "33", "--part", f"{i}/3"]))
    for n in WB_GRIDS:
        nt = np.load(os.path.join(REPO, "fit", "synthetic", "pairs", n + ".npz"))["neutral"]
        grids.append((n[-3:], ["--neutral", ",".join(f"{v:.5f}" for v in nt)]))
    for tag, extra in grids:
        run(os.path.join(HERE, "make_synthetic_raw.py"), host, os.path.join(work, f"{tag}.3fr"), "--uid", f"HNCSLENS{tag}".ljust(16, "0")[:16], *extra)
        set_landscape(os.path.join(work, f"{tag}.3fr"))
        set_baseline_exposure(os.path.join(work, f"{tag}.3fr"), 0.0)  # the Capture One lookup was measured at 0
    run(os.path.join(HERE, "make_synthetic_raw.py"), host, os.path.join(work, "flat.3fr"), "--flat", "45", "--uid", "HNCSLENSFLAT0000")
    set_landscape(os.path.join(work, "flat.3fr"))
    set_baseline_exposure(os.path.join(work, "flat.3fr"), 0.0)
    exports = {}
    with HotFolder() as hf:
        for tag, _ in grids + [("flat", None)]:
            dst = os.path.join(work, f"{tag}_phocus.tif")
            shutil.move(hf.render(os.path.join(work, f"{tag}.3fr"), name=f"lens_{tag}.3fr", LensCorrection=0), dst)
            os.remove(os.path.join(work, f"{tag}.3fr"))
            exports[tag] = dst
            print(f"  Phocus rendered {tag}", flush=True)
    gainmap = os.path.join(work, "gainmap.npz")
    run(os.path.join(HERE, "flat_gain.py"), os.path.join(REPO, "fit", "lut_e4.npz"), exports["flat"], gainmap)
    pair_args = []
    for tag, _ in grids:
        pz = os.path.join(work, f"{tag}.npz")
        run(os.path.join(HERE, "save_synth_pairs.py"), os.path.join(work, f"{tag}.patches.npz"), "-", exports[tag], pz)
        os.remove(exports[tag])
        pair_args += ["--pairs", pz]
    log = run(os.path.join(HERE, "fit_synthetic.py"), lut_path, "--gainmap", gainmap, *pair_args)
    print("  " + [l for l in log.splitlines() if "residual" in l][-1].strip(), flush=True)
    print(run(os.path.join(HERE, "write_profile.py"), lut_path, pname, work).strip().splitlines()[-1])
    icc = f"HasselbladX2DII100C-{pname}.icm"
    shutil.copyfile(os.path.join(work, icc), os.path.join(prof_dir, icc))
    shutil.copyfile(os.path.join(work, f"{pname}.costyle"), os.path.join(style_dir, f"{pname}.costyle"))
    pp = f"{pname} (pre-processed)"
    with open(os.path.join(style_dir, f"{pp}.costyle"), "w") as f:
        f.write(f'<?xml version="1.0"?>\n<SL Engine="1300">\n\t<E K="FilmCurve" V="HasselbladX2DII100C-Linear Response.fcrv" />\n'
                f'\t<E K="ICCProfile" V="{icc}" />\n\t<E K="LensLightFallOff" V="|0|1" />\n\t<E K="Name" V="{pp}" />\n'
                f'\t<E K="StyleSource" V="Styles" />\n\t<E K="UUID" V="{str(uuid.uuid4()).upper()}" />\n</SL>\n')
    print(f"wrote {os.path.join(prof_dir, icc)}, styles '{pname}' and '{pp}', table {lut_path}")
    if a.install:
        shutil.copyfile(os.path.join(prof_dir, icc), os.path.expanduser(f"~/Library/ColorSync/Profiles/{icc}"))
        for s in (pname, pp):
            shutil.copyfile(os.path.join(style_dir, f"{s}.costyle"), os.path.expanduser(f"~/Library/Application Support/Capture One/Styles/{s}.costyle"))
        print("installed; restart Capture One to see them")
finally:
    shutil.rmtree(work, ignore_errors=True)
