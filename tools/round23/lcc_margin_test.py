"""Does Capture One's LCC normalisation look at the sensor margin outside the default crop? (Finding 47)

Makes two full-correction LCC references for one map in a copy of HOST: A as state_lcc.py makes it, B the same
with every photosite outside the default crop set to a strongly coloured constant. Creates both LCCs in the lab
session, applies each (uncalibrated, white balance As Shot) to the same L* 40 flat, renders through the probe,
and prints the centre and whole-frame colour of the two renders. If B differs from A, the margin takes part.

usage: python lcc_margin_test.py HOST MAP [--lab DIR] [--margin r,g,b]   (Capture One open on the lab session,
       probe profile installed before it started)
"""
import argparse
import os
import shutil
import subprocess
import sys
import time

import numpy as np
import tifffile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(HERE, "..")
sys.path.insert(0, TOOLS)
from c1_sidecars import settings_dir  # noqa: E402
from pairs import romm_decode  # noqa: E402
from phocus_hotfolder import set_baseline_exposure, set_landscape  # noqa: E402
from state_lcc import PROBE, osa, wait_file, wait_listed  # noqa: E402

REPO = os.path.join(TOOLS, "..")
WORK = os.path.join(REPO, "data", "synth", "r23")
LCCS = os.path.join(WORK, "lcc")
py = sys.executable


def paint_margin(path, frac):
    """Set every photosite outside the default crop to frac x (white - black) above black, per CFA colour."""
    with tifffile.TiffFile(path) as t:
        sp = t.pages[0].pages[0]
        raw = sp.asarray().copy()
        off = sp.dataoffsets[0]
        black, white = int(sp.tags["BlackLevel"].value[0]), int(np.min(sp.tags["WhiteLevel"].value))
        cx0, cy0 = sp.tags["DefaultCropOrigin"].value
        cw, ch = sp.tags["DefaultCropSize"].value
    inside = np.zeros(raw.shape, bool)
    inside[cy0:cy0 + ch, cx0:cx0 + cw] = True
    yy, xx = np.indices(raw.shape)
    chan = np.where((yy % 2 == 0) & (xx % 2 == 0), 0, np.where((yy % 2 == 1) & (xx % 2 == 1), 2, 1))
    val = black + np.array(frac)[chan] * (white - black)
    raw[~inside] = np.round(val[~inside]).astype(np.uint16)
    with open(path, "r+b") as f:
        f.seek(off)
        f.write(raw.astype("<u2").tobytes())
    return int((~inside).sum()), raw.size


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("host")
    ap.add_argument("map")
    ap.add_argument("--lab", default=os.path.expanduser("~/Pictures/X2D Profile/Capture"))
    ap.add_argument("--margin", default="0.8,0.3,0.05")
    a = ap.parse_args()
    os.makedirs(LCCS, exist_ok=True)
    names = {}
    for key in ("A", "B"):
        lid = f"MT{key}"
        ref = os.path.join(WORK, lid + ".3fr")
        subprocess.run([py, "-I", os.path.join(TOOLS, "round17", "make_state_lcc.py"), a.map, a.host, ref, "--full",
                        "--uid", f"HNCSMARGIN{key}".ljust(16, "0")], check=True, capture_output=True)
        if key == "B":
            n, tot = paint_margin(ref, [float(v) for v in a.margin.split(",")])
            print(f"margin: {n} of {tot} photosites ({n / tot:.1%}) set to {a.margin} of range")
        shutil.move(ref, os.path.join(a.lab, lid + ".3fr"))
        names[key] = lid
    wait_listed([f"{lid}.3fr" for lid in names.values()])
    for lid in names.values():
        osa(f'tell application "Capture One" to create LCC (variant 1 of (first image of current document whose name is "{lid}.3fr"))')
    for lid in names.values():
        src = os.path.join(settings_dir(a.lab), f"{lid}.3fr.{lid}.lcc")
        for _ in range(60):
            if os.path.exists(src):
                break
            time.sleep(1)
        time.sleep(2)
        shutil.copyfile(src, os.path.join(LCCS, lid + ".lcc"))
        os.remove(os.path.join(a.lab, lid + ".3fr"))
    flats = []
    for key, lid in names.items():
        nm = f"MTF{key}"
        p = os.path.join(WORK, nm + ".3fr")
        subprocess.run([py, "-I", os.path.join(TOOLS, "make_synthetic_raw.py"), a.host, p, "--flat", "40",
                        "--uid", f"HNCSMTFLAT{key}".ljust(16, "0")], check=True, capture_output=True)
        set_landscape(p)
        set_baseline_exposure(p, 0.0)
        subprocess.run([py, "-I", os.path.join(TOOLS, "c1_sidecars.py"), p, "--dest", a.lab, "--profile", PROBE, "--force",
                        "--no-body-gains", "--lcc-dir", LCCS, "--state-lcc", lid, "--state-comp", "0,1,1"], check=True, capture_output=True)
        shutil.move(p, os.path.join(a.lab, nm + ".3fr"))
        flats.append(nm)
    wait_listed([f + ".3fr" for f in flats])
    osa('tell application "Capture One"', 'set d to current document', 'set rn to "HNCS LCC calibration"',
        *[f'process (variant 1 of (first image of d whose name is "{f}.3fr")) recipe rn' for f in flats], 'end tell')
    out = os.path.join(os.path.dirname(os.path.abspath(a.lab)), "Output", "state_lcc_cal")
    res = {}
    for f in flats:
        p = os.path.join(out, f + ".tif")
        wait_file(p)
        img = romm_decode(tifffile.imread(p)[..., :3].astype(np.float64) / 65535)
        H, W = img.shape[:2]
        res[f] = (img[H // 2 - 40: H // 2 + 40, W // 2 - 40: W // 2 + 40].reshape(-1, 3).mean(0), img.reshape(-1, 3).mean(0))
        os.remove(p)
        os.remove(os.path.join(a.lab, f + ".3fr"))
    for f, (c, m) in res.items():
        print(f"{f}: centre RGB {np.round(c, 5)}  R/G {c[0] / c[1]:.4f}  B/G {c[2] / c[1]:.4f}   frame mean R/G {m[0] / m[1]:.4f} B/G {m[2] / m[1]:.4f}")
    (ca, _), (cb, _) = res["MTFA"], res["MTFB"]
    print(f"B minus A at the centre, stops (R, G, B): {np.round(np.log2(cb / ca), 4)}")


if __name__ == "__main__":
    main()
