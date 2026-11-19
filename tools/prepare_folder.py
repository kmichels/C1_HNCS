"""Prepare a folder of X2D II raws for Capture One with Phocus's HNCS rendering: one command, no copies.

Writes a Capture One settings file beside each raw (c1_sidecars.py), so Capture One opens it with the lens's
HNCS E5 profile, Linear Response, Phocus's lens correction as an LCC for its lens setting, and the body's
calibration. Run it before Capture One first sees the raws. What it needs, it can make first:
  --make-maps      Phocus's correction map for each new lens setting (Phocus, about 25 s each)
  --make-profiles  an E5 profile for each new lens (Phocus, about 5 minutes each; restart Capture One after)
  --make-lccs      the LCC and its calibration for each lens setting without one (Capture One, about 1.5
                   minutes each). Needs Capture One open on the lab session (--lab, default the X2D Profile
                   session's Capture folder) and the probe profile installed before it started.
Lens settings without an LCC fall back to a radial falloff curve, which is less accurate on wide lenses.
Don't use Phocus or Capture One's lab session while it runs.

usage: python prepare_folder.py FOLDER [--dest DIR] [--make-maps] [--make-profiles] [--make-lccs] [--lab DIR]
       [--no-body-gains] [--force]
"""
import argparse
import glob
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from make_preprocess_map import FIT, lens_state, profile_name  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("folder")
ap.add_argument("--dest", default=None, help="folder the raws will be imported from, if not FOLDER")
ap.add_argument("--make-maps", action="store_true")
ap.add_argument("--make-profiles", action="store_true")
ap.add_argument("--make-lccs", action="store_true")
ap.add_argument("--lab", default=os.path.expanduser("~/Pictures/X2D Profile/Capture"))
ap.add_argument("--no-body-gains", action="store_true")
ap.add_argument("--force", action="store_true", help="rewrite existing settings files")
a = ap.parse_args()
py = sys.executable
raws = sorted(f for f in glob.glob(os.path.join(a.folder, "*")) if f.lower().endswith(".3fr"))
if not raws:
    sys.exit(f"no .3fr files in {a.folder}")
maps = os.path.join(FIT, "preprocess_maps")
if a.make_maps and any(not os.path.exists(os.path.join(maps, lens_state(r)[0] + ".npz")) for r in raws):
    subprocess.run([py, "-I", os.path.join(HERE, "auto_maps.py"), *raws, "--maps", maps], check=True)
by_lens = {}
for r in raws:
    by_lens.setdefault(profile_name(lens_state(r)[1]), []).append(r)
no_profile = [n for n in by_lens if not os.path.exists(os.path.join(HERE, "..", "profiles", f"HasselbladX2DII100C-HNCS E5 {n}.icm"))]
if no_profile and a.make_profiles:
    for n in no_profile:
        subprocess.run([py, "-I", os.path.join(HERE, "auto_lens_profile.py"), *by_lens[n], "--install"], check=True)
    print("new profiles installed: restart Capture One before importing", flush=True)
    no_profile = []
if a.make_lccs:
    subprocess.run([py, "-I", os.path.join(HERE, "state_lcc.py"), "ensure", *raws, "--lab", a.lab], check=True)
todo = [r for r in raws if profile_name(lens_state(r)[1]) not in no_profile]
for n in no_profile:
    print(f"{n}: no E5 profile yet; run with --make-profiles ({len(by_lens[n])} raws skipped)")
cmd = [py, "-I", os.path.join(HERE, "c1_sidecars.py"), *todo]
cmd += ["--dest", a.dest] if a.dest else []
cmd += ["--no-body-gains"] if a.no_body_gains else []
cmd += ["--force"] if a.force else []
if todo:
    subprocess.run(cmd, check=True)
