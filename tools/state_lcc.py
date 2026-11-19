"""Make and calibrate the per-lens-setting LCCs that c1_sidecars.py uses (Findings 40-41), with Capture One.

  ensure RAW [RAW ...]   for every lens setting among the raws whose LCC is missing: make it and calibrate it
                         (--recalibrate: also recalibrate LCCs calibrated before Finding 43)
  make HOST MAP          full-correction LCC reference (round17/make_state_lcc.py --full) for MAP, written into
                         the lab session's Capture folder; Create LCC; copied to data/lcc_c1/<id>.lcc
  calibrate HOST MAP     the LCC's overall colour and brightness offset, measured in Capture One's own output over
                         the frame on three L* 40 flats (the map multiplied into the raw, no LCC; the LCC; the LCC
                         plus a known exposure and white-balance step), saved as data/lcc_c1/<id>.json
  clean                  remove the reference raws and calibration flats from the lab session (quit Capture One
                         first)

The id is the map's file stem with dots replaced (c1_sidecars.lcc_id). HOST is any raw with the lens setting's
metadata. Needs Capture One running with the lab session open (default: ~/Pictures/X2D Profile, whose Capture
folder is --lab), and the probe profile installed (build_probe.py) before Capture One started. An LCC file
records HOST's camera serial number; data/ isn't committed.

usage: python state_lcc.py ensure RAW... [--lab DIR]
       python state_lcc.py make|calibrate HOST MAP [--lab DIR]
       python state_lcc.py clean [--lab DIR]
"""
import argparse
import glob
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
from c1_sidecars import lcc_id, settings_dir  # noqa: E402
from make_preprocess_map import FIT, apply_map, find_map, lens_state  # noqa: E402
from pairs import romm_decode  # noqa: E402
from phocus_hotfolder import set_baseline_exposure, set_landscape  # noqa: E402

REPO = os.path.join(HERE, "..")
LCC_DIR = os.path.join(REPO, "data", "lcc_c1")
WORK = os.path.join(REPO, "data", "synth", "state_lcc")
PROBE = "HasselbladX2DII100C-E0 Probe.icm"
STEP_WB, STEP_EV = (1.05, 1.05), 0.05   # calibration step: white balance kR, kB and exposure
CAL_LSTAR, CAL_AREA = 40, (0.05, 0.9)   # flat level (corners stay unclipped at f/2.5), radii compared
STEP = np.array([STEP_WB[0] * 2 ** STEP_EV, 2 ** STEP_EV, STEP_WB[1] * 2 ** STEP_EV])   # raw-domain gain per channel
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
        try:
            n = sum(int(osa(f'tell application "Capture One" to return count of (images of current document whose name is "{nm}")')) for nm in names)
        except RuntimeError:
            n = -1
        if n == len(names):
            return
        time.sleep(3)
    raise TimeoutError(f"Capture One didn't list {names}; is the lab session open?")


def wait_file(p, limit=300):
    t0 = time.time()
    while time.time() - t0 < limit:
        if os.path.exists(p) and os.path.getsize(p) > 100_000:
            s = os.path.getsize(p)
            time.sleep(1.5)
            if os.path.getsize(p) == s:
                return
        time.sleep(1)
    raise TimeoutError(f"no {p}")


def make(host, mp, lab):
    lid = lcc_id(mp)
    os.makedirs(WORK, exist_ok=True)
    ref = os.path.join(WORK, lid + ".3fr")
    subprocess.run([py, "-I", os.path.join(HERE, "round17", "make_state_lcc.py"), mp, host, ref, "--full",
                    "--uid", ("HNCSLCC" + lid.replace("_", "").replace("-", ""))[:16].ljust(16, "0")], check=True, capture_output=True)
    shutil.move(ref, os.path.join(lab, lid + ".3fr"))
    wait_listed([lid + ".3fr"])
    osa(f'tell application "Capture One" to create LCC (variant 1 of (first image of current document whose name is "{lid}.3fr"))')
    src = os.path.join(settings_dir(lab), f"{lid}.3fr.{lid}.lcc")
    for _ in range(60):
        if os.path.exists(src):
            break
        time.sleep(1)
    time.sleep(2)
    os.makedirs(LCC_DIR, exist_ok=True)
    shutil.copyfile(src, os.path.join(LCC_DIR, lid + ".lcc"))
    os.remove(os.path.join(lab, lid + ".3fr"))   # Capture One shows it as missing; the LCC is kept
    print(f"{lid}: LCC made", flush=True)


def calibrate(host, mp, lab):
    lid = lcc_id(mp)
    os.makedirs(WORK, exist_ok=True)
    empty = os.path.join(WORK, "no_lcc")
    os.makedirs(empty, exist_ok=True)
    tag = lid.replace("_", "").replace("-", "")
    names = {"ref": f"CAL_{lid}_0", "lcc": f"CAL_{lid}_1", "step": f"CAL_{lid}_2"}
    for key, nm in names.items():
        p = os.path.join(WORK, nm + ".3fr")
        uid = (f"HNCSC{key[0]}" + tag)[:16].ljust(16, "0")
        subprocess.run([py, "-I", os.path.join(HERE, "make_synthetic_raw.py"), host, p, "--flat", str(CAL_LSTAR),
                        "--uid", uid], check=True, capture_output=True)
        set_landscape(p)
        set_baseline_exposure(p, 0.0)
        cmd = [py, "-I", os.path.join(HERE, "c1_sidecars.py"), p, "--dest", lab, "--profile", PROBE, "--force", "--no-body-gains"]
        if key == "ref":   # Phocus's correction multiplied into the raw itself; no LCC, no Light Falloff
            flat = p + ".flat"
            os.replace(p, flat)
            apply_map(flat, p, mp, uid)
            os.remove(flat)
            cmd += ["--lcc-dir", empty]
        else:
            cmd += ["--state-lcc", lid, "--state-comp", "0,1,1" if key == "lcc" else f"{STEP_EV},{STEP_WB[0]},{STEP_WB[1]}"]
        subprocess.run(cmd, check=True, capture_output=True)
        if key == "ref":
            cos = os.path.join(settings_dir(lab), nm + ".3fr.cos")
            s = open(cos).read()
            assert s.count('|100|1"') == 1
            open(cos, "w").write(s.replace('|100|1"', '|0|1"'))
        shutil.move(p, os.path.join(lab, nm + ".3fr"))
    wait_listed([nm + ".3fr" for nm in names.values()])
    osa('tell application "Capture One"', 'set d to current document', 'set rn to "HNCS LCC calibration"',
        'if not (exists recipe rn of d) then', 'make new recipe at end of recipes of d with properties {name:rn}',
        'set r to recipe rn of d', 'set output format of r to TIFF', 'set bits of r to 16', 'set color profile of r to "ROMM RGB"',
        'set output sub folder of r to "state_lcc_cal"', 'set ignore crop of r to true', 'set scaling method of r to Fixed',
        'set scaling unit of r to percent', 'set primary scaling value of r to 25', 'set existing files of r to overwrite',
        'end if', *[f'process (variant 1 of (first image of d whose name is "{nm}.3fr")) recipe rn' for nm in names.values()],
        'end tell')
    out = os.path.join(os.path.dirname(os.path.abspath(lab)), "Output", "state_lcc_cal")
    img = {}
    for key, nm in names.items():
        p = os.path.join(out, nm + ".tif")
        wait_file(p)
        img[key] = romm_decode(tifffile.imread(p)[..., :3].astype(np.float64) / 65535)
        os.remove(p)
        os.remove(os.path.join(lab, nm + ".3fr"))
    # Compared over the frame, not at the centre: the LCC matches the map's shape but not at the centre spot
    # (Finding 43). Per channel, Capture One's output is locally out = c * gain^s; the two LCC flats give s.
    H, W = img["ref"].shape[:2]
    yy, xx = np.mgrid[:H, :W]
    r = np.hypot(yy - (H - 1) / 2, xx - (W - 1) / 2) / np.hypot((H - 1) / 2, (W - 1) / 2)
    ok = (r >= CAL_AREA[0]) & (r < CAL_AREA[1])
    for v in img.values():
        ok &= (v.min(-1) > 0.005) & (v.max(-1) < 0.85)
    lr = np.log(img["ref"][ok] / img["lcc"][ok]).mean(0)
    s = np.log(img["step"][ok] / img["lcc"][ok]).mean(0) / np.log(STEP)
    m = np.exp(lr / s)
    res = {"ev": float(np.log2(m[1])), "kR": float(m[0] / m[1]), "kB": float(m[2] / m[1]), "slope": s.tolist(),
           "map": os.path.basename(mp), "host": os.path.basename(host), "reference": "map in raw",
           "area": list(CAL_AREA), "lstar": CAL_LSTAR, "pixels": int(ok.sum())}
    if not all(0.8 < v < 1.4 for v in s):
        raise RuntimeError(f"{lid}: implausible local slopes {s}; calibration not saved")
    json.dump(res, open(os.path.join(LCC_DIR, lid + ".json"), "w"), indent=1)
    print(f"{lid}: calibrated, exposure {res['ev']:+.4f} EV, kR {res['kR']:.4f}, kB {res['kB']:.4f}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("ensure", "make", "calibrate", "clean"))
    ap.add_argument("args", nargs="*")
    ap.add_argument("--lab", default=os.path.expanduser("~/Pictures/X2D Profile/Capture"))
    ap.add_argument("--maps", default=os.path.join(FIT, "preprocess_maps"))
    ap.add_argument("--recalibrate", action="store_true", help="ensure: also recalibrate LCCs calibrated the old way")
    a = ap.parse_args()
    if a.cmd == "clean":
        n = 0
        for f in glob.glob(os.path.join(a.lab, "CAL_*.3fr")) + glob.glob(os.path.join(a.lab, "XCD*.3fr")):
            stem = os.path.basename(f)
            os.remove(f)
            for g in glob.glob(os.path.join(settings_dir(a.lab), stem + "*")) + glob.glob(os.path.join(a.lab, "CaptureOne", "Cache", "*", stem + "*")):
                os.remove(g)
            n += 1
        print(f"removed {n} lab raws and their settings")
        return
    if a.cmd in ("make", "calibrate"):
        host, mp = a.args
        (make if a.cmd == "make" else calibrate)(host, mp, a.lab)
        return
    todo = {}
    for r in a.args:
        mp = find_map(a.maps, lens_state(r)[0])
        if mp is None:
            print(f"{os.path.basename(r)}: no map for {lens_state(r)[0]}; make maps first")
            continue
        lid = lcc_id(mp)
        js = os.path.join(LCC_DIR, lid + ".json")
        old = os.path.exists(js) and json.load(open(js)).get("reference") != "map in raw"
        if not (os.path.exists(os.path.join(LCC_DIR, lid + ".lcc")) and os.path.exists(js)) or (a.recalibrate and old):
            todo.setdefault(mp, r)
    print(f"{len(todo)} LCC(s) to make", flush=True)
    for mp, host in todo.items():
        if not os.path.exists(os.path.join(LCC_DIR, lcc_id(mp) + ".lcc")):
            make(host, mp, a.lab)
        calibrate(host, mp, a.lab)


if __name__ == "__main__":
    main()
