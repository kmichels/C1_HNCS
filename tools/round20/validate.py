"""Score the validation raws with settings files from the current LCC calibrations against Phocus renders
(render_phocus.py), as Finding 42 did: copies named V_<raw> go into the lab session with their settings files,
are rendered at 50% (sharpening, noise reduction and distortion off), scored with score_render.py, and
removed. Run with the lab session open in Capture One.

usage: python validate.py RAW... [--lab DIR] [--phocus DIR] [--out DIR] [--prefix V] [--profile FILE]
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
