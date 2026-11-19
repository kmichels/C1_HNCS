"""Score the validation raws with settings files from the current LCC calibrations against Phocus renders
(render_phocus.py), as Finding 42 did: copies named V_<raw> go into the lab session with their settings files,
are rendered at 50% (sharpening, noise reduction and distortion off), scored with score_render.py, and
removed. Run with the lab session open in Capture One.

usage: python validate.py RAW... [--lab DIR] [--phocus DIR] [--out DIR] [--prefix V] [--profile FILE] [--wb-as-shot]
  --wb-as-shot: replace the settings file's white balance with plain As Shot, as choosing As Shot in Capture One does
  --undo-baked: with --wb-as-shot, also divide out the profile's built-in LCC colour, which is what As Shot did
  before the colour was built into the profiles (Finding 47)
"""
import argparse
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(HERE, "..")
sys.path.insert(0, TOOLS)
import numpy as np  # noqa: E402

from c1_sidecars import baked_colour, settings_dir  # noqa: E402
from make_preprocess_map import lens_state, profile_name  # noqa: E402
from state_lcc import wait_file, wait_listed  # noqa: E402

REPO = os.path.join(TOOLS, "..")
py = sys.executable


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("raws", nargs="+")
    ap.add_argument("--lab", default=os.path.expanduser("~/Pictures/X2D Profile/Capture"))
    ap.add_argument("--phocus", default=os.path.join(REPO, "data", "val", "r20", "phocus"))
    ap.add_argument("--out", default=os.path.join(REPO, "data", "val", "r20", "val"))
    ap.add_argument("--prefix", default="V", help="name prefix; use one Capture One hasn't seen in the session")
    ap.add_argument("--profile", default=None, help="override the profile c1_sidecars.py picks")
    ap.add_argument("--wb-as-shot", action="store_true")
    ap.add_argument("--undo-baked", action="store_true")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    stage = os.path.join(REPO, "data", "synth", "r20", "val")
    os.makedirs(stage, exist_ok=True)
    rendered = os.path.join(os.path.dirname(os.path.abspath(a.lab)), "Output", "r20val")
    for i in range(0, len(a.raws), 6):
        batch = []
        for raw in a.raws[i:i + 6]:
            stem = os.path.splitext(os.path.basename(raw))[0]
            if os.path.exists(os.path.join(a.out, f"{a.prefix}_{stem}.json")):
                continue
            nm = f"{a.prefix}_{stem}.3FR"
            p = os.path.join(stage, nm)
            shutil.copyfile(raw, p)
            r = subprocess.run([py, "-I", os.path.join(TOOLS, "c1_sidecars.py"), p, "--dest", a.lab, "--force",
                                *(["--profile", a.profile] if a.profile else [])], check=True, capture_output=True, text=True)
            print(r.stdout.strip().splitlines()[0], flush=True)
            if a.wb_as_shot:
                import re
                import tifffile
                with tifffile.TiffFile(p) as t:
                    n = t.pages[0].tags["AsShotNeutral"].value
                cos = os.path.join(settings_dir(a.lab), nm + ".cos")
                txt = open(cos).read()
                kc = np.ones(3)
                if a.undo_baked:
                    prof = re.search(r'K="ICCProfile" V="([^"]*)"', txt).group(1)
                    kc = baked_colour(profile_name(lens_state(p)[1]), prof)
                txt, k = re.subn(r'K="WhiteBalance" V="[^"]*"', f'K="WhiteBalance" V="{n[1] / n[0] / kc[0]:.6f};1;{n[5] / n[4] / kc[2]:.6f}"', txt)
                assert k == 1
                open(cos, "w").write(txt)
            shutil.move(p, os.path.join(a.lab, nm))
            batch.append((nm, stem))
        if not batch:
            continue
        wait_listed([nm for nm, _ in batch], limit=600)
        time.sleep(3)
        r = subprocess.run(["osascript", os.path.join(HERE, "render_val.applescript"), *[nm for nm, _ in batch]],
                           capture_output=True, text=True)
        print(r.stdout.strip(), r.stderr.strip()[-300:], flush=True)
        for nm, stem in batch:
            o = os.path.join(rendered, f"{a.prefix}_{stem}.tif")
            wait_file(o, limit=900)
            r = subprocess.run([py, "-I", os.path.join(TOOLS, "score_render.py"), os.path.join(a.phocus, f"{stem}.tif"), o,
                                "--json", os.path.join(a.out, f"{a.prefix}_{stem}.json")], capture_output=True, text=True)
            print(r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-300:], flush=True)
            os.remove(o)
            os.remove(os.path.join(a.lab, nm))
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
