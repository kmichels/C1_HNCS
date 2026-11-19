"""Capture One renders for the README contact sheet: S_<raw> with its settings file and D_<raw> at Capture
One's defaults, rendered at 50% like validate.py, kept in OUT. Run with the lab session open.

usage: python sheet_renders.py OUT PREFIX RAW...   (PREFIX: one Capture One has not seen in the session)
"""
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(HERE, "..")
sys.path.insert(0, TOOLS)
from state_lcc import wait_file, wait_listed  # noqa: E402

LAB = os.path.expanduser("~/Pictures/X2D Profile/Capture")
REPO = os.path.join(TOOLS, "..")
out, PRE, raws = sys.argv[1], sys.argv[2], sys.argv[3:]
os.makedirs(out, exist_ok=True)
stage = os.path.join(REPO, "data", "synth", "r20", "sheet")
os.makedirs(stage, exist_ok=True)
names = []
for raw in raws:
    stem = os.path.splitext(os.path.basename(raw))[0]
    for pre in (PRE + "S", PRE + "D"):  # names Capture One has not seen in the session
        nm = f"{pre}_{stem}.3FR"
        p = os.path.join(stage, nm)
        shutil.copyfile(raw, p)
        if pre == PRE + "S":
            r = subprocess.run([sys.executable, "-I", os.path.join(TOOLS, "c1_sidecars.py"), p, "--dest", LAB, "--force"],
                               check=True, capture_output=True, text=True)
            print(r.stdout.strip().splitlines()[0], flush=True)
        shutil.move(p, os.path.join(LAB, nm))
        names.append(nm)
wait_listed(names, limit=600)
for i in range(0, len(names), 6):
    r = subprocess.run(["osascript", os.path.join(HERE, "render_val.applescript"), *names[i:i + 6]], capture_output=True, text=True)
    print(r.stdout.strip(), r.stderr.strip()[-300:], flush=True)
    for nm in names[i:i + 6]:
        o = os.path.join(os.path.dirname(LAB), "Output", "r20val", os.path.splitext(nm)[0] + ".tif")
        wait_file(o, limit=900)
        shutil.move(o, os.path.join(out, os.path.basename(o)))
        os.remove(os.path.join(LAB, nm))
print("DONE", flush=True)
