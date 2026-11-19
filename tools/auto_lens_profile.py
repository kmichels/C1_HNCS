"""Build an HNCS E5 profile for a lens from any of its raws, unattended, using only Phocus.

Synthetic patch grids are written into a copy of one of the raws (so Phocus sees that lens), at the raw's
own white balance and five more daylight white balances, plus a flat field for Phocus's spatial gain.
Phocus renders them through its hot folder. Capture One's camera RGB for each patch comes from
fit/c1_patch_lookup.npz (measured once; the same for any lens and white balance), so Capture One isn't
needed. The fitted table is written as a Capture One profile, with the lens's LCC colour factor built in
(bake_lcc_colour.py: from its calibrated LCCs, or estimated from its maps until there are some).
The synthetic copies carry the reference body's factory gains, so the profile serves every X2D II body
(c1_sidecars.py corrects other bodies).

Phocus is restarted and its preferences restored afterwards; don't use it meanwhile. Raws are only read.

With --light shade it builds "HNCS E5 <name> Shade" instead, fitted on grids at 6300-8600 K (Finding 44), and
with --light tungsten "HNCS E5 <name> Tungsten", on Finding 21's four grids at about 3100-4200 K (Finding 46).
c1_sidecars.py picks them for photos whose As Shot is in shade or under tungsten light.

usage: python auto_lens_profile.py RAW [RAW ...] [--name NAME] [--out DIR] [--install] [--light daylight|shade|tungsten]
  NAME defaults to the lens model (e.g. XCD55V); files go to DIR (default: the repo's profiles/ and fit/);
  --install also copies the profile into ~/Library/ColorSync/Profiles (restart Capture One).
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile

import numpy as np
import tifffile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
from make_preprocess_map import lens_state, profile_name  # noqa: E402
from phocus_hotfolder import HotFolder, set_baseline_exposure, set_landscape, set_reference_body  # noqa: E402

WB_GRIDS = ["HNCSwbA1", "HNCSwbA2", "HNCSwbA3", "HNCSwbA4", "HNCSwbA5"]  # their As Shot neutrals are reused
# Kelvins on the daylight locus, offset like real X2D II As Shot neutrals: (33-level grid, 22-level grids)
LIGHTS = {"shade": (7300, (6300, 6800, 7900, 8600))}
TUNGSTEN_GRIDS = ["HNCStungA1", "HNCStungA2", "HNCStungA3", "HNCStungA4"]  # Finding 21's neutrals, 22-level grids only
OFF_LOCUS = (-0.055, -0.06)

ap = argparse.ArgumentParser()
ap.add_argument("raws", nargs="+")
ap.add_argument("--name", default=None)
ap.add_argument("--out", default=None, help="write everything into this folder instead of the repo")
ap.add_argument("--install", action="store_true")
ap.add_argument("--light", choices=("daylight", "shade", "tungsten"), default="daylight")
a = ap.parse_args()


def orientation(path):
    with tifffile.TiffFile(path) as t:
        tag = t.pages[0].tags.get("Orientation")
        return 1 if tag is None else tag.value


host = next((r for r in a.raws if orientation(r) == 1), a.raws[0])
lens = lens_state(host)[1]
name = a.name or profile_name(lens)
suffix = "" if a.light == "daylight" else " " + a.light.capitalize()
pname = f"HNCS E5 {name}{suffix}"
prof_dir = a.out or os.path.join(REPO, "profiles")
lut_path = os.path.join(a.out or os.path.join(REPO, "fit"), f"lut_e5_{name}{suffix.lower().replace(' ', '_')}.npz")
for d in (prof_dir, os.path.dirname(lut_path)):
    os.makedirs(d, exist_ok=True)
print(f"lens {lens} -> profile '{pname}', host {os.path.basename(host)}", flush=True)

py = sys.executable
work = tempfile.mkdtemp(prefix="hncs-lens-")
run = lambda *args: subprocess.run([py, "-I", *args], check=True, capture_output=True, text=True).stdout
try:
    grids = []
    neutral_arg = lambda nt: ["--neutral", ",".join(f"{v:.5f}" for v in nt)]  # noqa: E731
    if a.light == "daylight":
        for i in range(3):
            grids.append((f"g{i}", ["--levels", "33", "--part", f"{i}/3"]))
        for n in WB_GRIDS:
            grids.append((n[-3:], neutral_arg(np.load(os.path.join(REPO, "fit", "synthetic", "pairs", n + ".npz"))["neutral"])))
    elif a.light == "tungsten":
        for n in TUNGSTEN_GRIDS:
            grids.append((n[-2:], neutral_arg(np.load(os.path.join(REPO, "fit", "synthetic", "pairs", n + ".npz"))["neutral"])))
    else:
        from c1_sidecars import daylight_neutral
        main_k, wb_ks = LIGHTS[a.light]
        for i in range(3):
            grids.append((f"g{i}", ["--levels", "33", "--part", f"{i}/3", *neutral_arg(daylight_neutral(host, main_k, OFF_LOCUS))]))
        for k in wb_ks:
            grids.append((f"k{k}", neutral_arg(daylight_neutral(host, k, OFF_LOCUS))))
    for tag, extra in grids:
        run(os.path.join(HERE, "make_synthetic_raw.py"), host, os.path.join(work, f"{tag}.3fr"), "--uid", f"HNCSLENS{tag}".ljust(16, "0")[:16], *extra)
        set_landscape(os.path.join(work, f"{tag}.3fr"))
        set_baseline_exposure(os.path.join(work, f"{tag}.3fr"), 0.0)  # the Capture One lookup was measured at 0
        set_reference_body(os.path.join(work, f"{tag}.3fr"))  # fit the reference body; others are corrected per raw
    run(os.path.join(HERE, "make_synthetic_raw.py"), host, os.path.join(work, "flat.3fr"), "--flat", "45", "--uid", "HNCSLENSFLAT0000")
    set_landscape(os.path.join(work, "flat.3fr"))
    set_baseline_exposure(os.path.join(work, "flat.3fr"), 0.0)
    set_reference_body(os.path.join(work, "flat.3fr"))
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
    icc = f"HasselbladX2DII100C-{pname}.icm"
    if a.out:   # a test build: no colour factor
        print(run(os.path.join(HERE, "write_profile.py"), lut_path, pname, work).strip().splitlines()[0])
        shutil.copyfile(os.path.join(work, icc), os.path.join(prof_dir, icc))
    import json
    if a.light == "daylight":
        refs_path = os.path.join(a.out or os.path.join(REPO, "fit"), "lens_references.json")
        refs = json.load(open(refs_path)) if os.path.exists(refs_path) else {}
        refs[name] = lens_state(host)[0]
        json.dump(refs, open(refs_path, "w"), indent=2)
        print(f"table {lut_path}; reference lens state {refs[name]}")
    else:   # keep the pairs, as for the shipped tables, so the profile can be refitted without Phocus
        pz_dir = os.path.join(a.out or os.path.join(REPO, "fit"), "synthetic", "pairs")
        os.makedirs(pz_dir, exist_ok=True)
        for tag, _ in grids:
            shutil.copyfile(os.path.join(work, f"{tag}.npz"), os.path.join(pz_dir, f"HNCS{a.light}{name}_{tag}.npz"))
        print(f"table {lut_path}; pairs in {pz_dir}")
    if not a.out:   # every profile of the lens gets its LCC colour factor (and the new table its profile)
        from bake_lcc_colour import bake
        kR, kB = bake(name, install=a.install, quiet=True)
        print(f"wrote {os.path.join(prof_dir, icc)} with LCC colour red x{kR:.4f}, blue x{kB:.4f}")
    if a.install:
        if a.out:
            shutil.copyfile(os.path.join(prof_dir, icc), os.path.expanduser(f"~/Library/ColorSync/Profiles/{icc}"))
        print("installed; restart Capture One to see it")
finally:
    shutil.rmtree(work, ignore_errors=True)
