"""Pair every probe render in a folder with its Phocus export, using the export names Phocus
recorded in each raw's .phos sidecar (so no content matching is needed).

usage: python pair_session.py RAW_DIR PROBE_DIR PHOCUS_DIR OUT_DIR --block 16 [--lift c2,c4] [--jobs 4]
"""
import argparse
import glob
import os
import plistlib
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

ap = argparse.ArgumentParser()
ap.add_argument("raws"); ap.add_argument("probe"); ap.add_argument("phocus"); ap.add_argument("out")
ap.add_argument("--block", default="16"); ap.add_argument("--lift", default="0,0"); ap.add_argument("--jobs", type=int, default=4)
a = ap.parse_args()
os.makedirs(a.out, exist_ok=True)
jobs = []
for phos in sorted(glob.glob(os.path.join(a.raws, "*.phos"))):
    p = plistlib.load(open(phos, "rb"))
    s = p["ImageSettings"][p["CurrentIx"]]
    stem = os.path.basename(phos).split(".")[0]
    probe = os.path.join(a.probe, stem + ".tif")
    exp = os.path.join(a.phocus, s.get("ExportName", ""))
    if not (os.path.exists(probe) and os.path.exists(exp)):
        print(f"{stem}: missing {'probe' if not os.path.exists(probe) else 'export'}"); continue
    jobs.append((stem, probe, exp))
here = os.path.dirname(os.path.abspath(__file__))


def run(j):
    stem, probe, exp = j
    r = subprocess.run([sys.executable, "-I", os.path.join(here, "pairs.py"), probe, exp, os.path.join(a.out, stem + ".npz"),
                        "--block", a.block, "--lift", a.lift], capture_output=True, text=True)
    return (r.stdout.strip().splitlines() or [r.stderr.strip()[-300:]])[-1]


with ThreadPoolExecutor(a.jobs) as ex:
    for line in ex.map(run, jobs):
        print(line, flush=True)
