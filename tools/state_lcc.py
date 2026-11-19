"""Make and calibrate a per-lens-setting LCC for the settings-file route (Finding 40), with Capture One.

  make HOST.3fr MAP.npz ID     writes a full-correction LCC reference (round17/make_state_lcc.py --full) into
                               the open session as ID.3fr, runs Create LCC on it, and copies the result to
                               data/lcc_c1/ID.lcc
  calibrate HOST.3fr ID        measures the LCC's overall colour and brightness offset on flat fields, in
                               Capture One's own output: an L* 60 flat without the LCC, one with it, and one
                               with it plus a known white-balance and exposure step. Saves the exposure and
                               R and B white-balance factors that cancel the offset to data/lcc_c1/ID.json,
                               which c1_sidecars.py --state-lcc ID then uses.

Needs Capture One running with a session open whose Capture folder is CAPTURE (default: the X2D Profile
session), and the probe profile installed (build_probe.py). HOST is any raw with the lens setting's metadata.
The LCC file records HOST's camera serial number; data/ isn't committed.

usage: python state_lcc.py make HOST MAP ID [--capture DIR]
       python state_lcc.py calibrate HOST ID [--capture DIR]
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time

import numpy as np
import tifffile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from pairs import romm_decode  # noqa: E402
from phocus_hotfolder import set_baseline_exposure, set_landscape  # noqa: E402

REPO = os.path.join(HERE, "..")
LCC_DIR = os.path.join(REPO, "data", "lcc_c1")
WORK = os.path.join(REPO, "data", "synth", "state_lcc")
STEP_WB, STEP_EV = (1.05, 1.05), 0.05  # calibration step: white balance kR, kB and exposure
STEP = (STEP_WB[0] * 2 ** STEP_EV, 2 ** STEP_EV, STEP_WB[1] * 2 ** STEP_EV)  # total raw-domain gain per channel

ap = argparse.ArgumentParser()
ap.add_argument("cmd", choices=("make", "calibrate"))
ap.add_argument("host")
ap.add_argument("rest", nargs="+")
ap.add_argument("--capture", default=os.path.expanduser("~/Pictures/X2D Profile/Capture"))
a = ap.parse_args()
os.makedirs(WORK, exist_ok=True)
os.makedirs(LCC_DIR, exist_ok=True)
py = sys.executable


def osa(*lines, timeout=180):
    args = ["osascript", "-e", f"with timeout of {timeout} seconds"]
    for ln in lines:
        args += ["-e", ln]
    args += ["-e", "end timeout"]
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(r.stderr.strip())
    return r.stdout.strip()


def wait_listed(names, limit=300):
    t0 = time.time()
    while time.time() - t0 < limit:
        n = 0
        for nm in names:
            try:
                n += int(osa(f'tell application "Capture One" to return count of (images of current document whose name is "{nm}")'))
            except RuntimeError:
                pass
        if n == len(names):
            return
        time.sleep(3)
    raise TimeoutError(f"Capture One didn't list {names}")


def settings_dir():
    import glob
    c = sorted(glob.glob(os.path.join(a.capture, "CaptureOne", "Settings*")))
    return c[-1] if c else os.path.join(a.capture, "CaptureOne", "Settings1690")


def flat(name, level=60):
    p = os.path.join(WORK, name + ".3fr")
    subprocess.run([py, "-I", os.path.join(HERE, "make_synthetic_raw.py"), a.host, p, "--flat", str(level),
                    "--uid", ("HNCSCAL" + name.replace("_", ""))[:16].ljust(16, "0")], check=True, capture_output=True)
    set_landscape(p)
    set_baseline_exposure(p, 0.0)
    return p


if a.cmd == "make":
    mp, lid = a.rest
    ref = os.path.join(WORK, lid + ".3fr")
    print(subprocess.run([py, "-I", os.path.join(HERE, "round17", "make_state_lcc.py"), mp, a.host, ref, "--full",
                          "--uid", ("HNCSLCC" + lid)[:16].ljust(16, "0")], check=True, capture_output=True, text=True).stdout.strip())
    shutil.move(ref, os.path.join(a.capture, lid + ".3fr"))
    wait_listed([lid + ".3fr"])
    osa(f'tell application "Capture One" to create LCC (variant 1 of (first image of current document whose name is "{lid}.3fr"))')
    src = os.path.join(settings_dir(), f"{lid}.3fr.{lid}.lcc")
    for _ in range(40):
        if os.path.exists(src):
            break
        time.sleep(1)
    time.sleep(2)
    shutil.copyfile(src, os.path.join(LCC_DIR, lid + ".lcc"))
    print(f"wrote {os.path.join(LCC_DIR, lid + '.lcc')}")
    raise SystemExit

(lid,) = a.rest
names = {"nolcc": f"CAL_{lid}_0", "lcc": f"CAL_{lid}_1", "step": f"CAL_{lid}_2"}
empty = os.path.join(WORK, "no_lcc")
os.makedirs(empty, exist_ok=True)
for key, nm in names.items():
    p = flat(nm)
    cmd = [py, "-I", os.path.join(HERE, "c1_sidecars.py"), p, "--dest", a.capture, "--profile", "HasselbladX2DII100C-E0 Probe.icm", "--force"]
    if key == "nolcc":
        cmd += ["--lcc-dir", empty]
    else:
        cmd += ["--state-lcc", lid, "--state-comp", "0,1,1" if key == "lcc" else f"{STEP_EV},{STEP_WB[0]},{STEP_WB[1]}"]
    subprocess.run(cmd, check=True, capture_output=True)
    shutil.move(p, os.path.join(a.capture, nm + ".3fr"))
wait_listed([nm + ".3fr" for nm in names.values()])
out = os.path.join(os.path.dirname(a.capture), "Output", "state_lcc_cal")
osa('tell application "Capture One"', 'set d to current document', 'set rn to "HNCS LCC calibration"',
    'if exists recipe rn of d then delete recipe rn of d', 'make new recipe at end of recipes of d with properties {name:rn}',
    'set r to recipe rn of d', 'set output format of r to TIFF', 'set bits of r to 16', 'set color profile of r to "ROMM RGB"',
    'set output sub folder of r to "state_lcc_cal"', 'set ignore crop of r to true', 'set scaling method of r to Fixed',
    'set scaling unit of r to percent', 'set primary scaling value of r to 25', 'set existing files of r to overwrite',
    *[f'process (variant 1 of (first image of d whose name is "{nm}.3fr")) recipe rn' for nm in names.values()],
    'end tell')
cen = {}
for key, nm in names.items():
    p = os.path.join(out, nm + ".tif")
    for _ in range(200):
        if os.path.exists(p) and os.path.getsize(p) > 1_000_000:
            s = os.path.getsize(p); time.sleep(1.5)
            if os.path.getsize(p) == s:
                break
        time.sleep(1)
    img = romm_decode(tifffile.imread(p)[..., :3].astype(np.float64) / 65535)
    H, W = img.shape[:2]
    cen[key] = img[H // 2 - 40: H // 2 + 40, W // 2 - 40: W // 2 + 40].reshape(-1, 3).mean(0)
# per channel, Capture One's output against a raw-domain gain m is locally out = c * m^s; two LCC renders give s
s = np.log(cen["step"] / cen["lcc"]) / np.log(np.array(STEP))
m = np.exp(np.log(cen["nolcc"] / cen["lcc"]) / s)
res = {"ev": float(np.log2(m[1])), "kR": float(m[0] / m[1]), "kB": float(m[2] / m[1]), "slope": s.tolist(),
       "centre_nolcc": cen["nolcc"].tolist(), "centre_lcc": cen["lcc"].tolist()}
json.dump(res, open(os.path.join(LCC_DIR, lid + ".json"), "w"), indent=1)
print(f"{lid}: exposure {res['ev']:+.4f} EV, kR {res['kR']:.4f}, kB {res['kB']:.4f} (local slopes {np.round(s, 3)})")
