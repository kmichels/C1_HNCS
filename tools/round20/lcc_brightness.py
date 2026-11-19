"""Why do some photos come out brighter or darker overall with the LCC route than with a corrected copy
(Finding 42)? Renders each raw in Capture One through the probe profile, from copies in the lab session,
with four settings files, and compares them pixel for pixel:

  A   no LCC, no WhiteBalance key (the calibration's "no LCC" case; centre like the corrected copy)
  W   A plus a WhiteBalance key equal to As Shot             -> W/A: does the key itself change anything?
  L   the lens setting's LCC, WhiteBalance = As Shot, no calibration   -> L/W: the LCC's effect on this photo
  C   the LCC with its calibration (what prepare_folder writes)       -> C/A: what's left

The calibration predicts L/W = m^-s at the centre, from data/lcc_c1/<id>.json. Ratios are reported for the
frame centre (r < 0.15) by brightness level, and by radius.

usage: python lcc_brightness.py render RAW... [--lab DIR]
       python lcc_brightness.py analyse RAW...
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

import numpy as np
import tifffile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(HERE, "..")
sys.path.insert(0, TOOLS)
from c1_sidecars import lcc_id, settings_dir  # noqa: E402
from make_preprocess_map import FIT, find_map, lens_state  # noqa: E402
from pairs import romm_decode  # noqa: E402
from state_lcc import LCC_DIR, PROBE, osa, wait_file, wait_listed  # noqa: E402

REPO = os.path.join(TOOLS, "..")
STAGE = os.path.join(REPO, "data", "synth", "r20")
OUT = os.path.join(REPO, "data", "val", "r20")
VARIANTS = ("A", "W", "L", "C")
RECIPE = "HNCS r20"
py = sys.executable


def name(v, raw):
    return f"R20{v}_{os.path.splitext(os.path.basename(raw))[0]}.3FR"


def add_wb_key(cos, raw):
    with tifffile.TiffFile(raw) as t:
        n = t.pages[0].tags["AsShotNeutral"].value
    key = f'\t\t\t<E K="WhiteBalance" V="{n[1] / n[0]:.6f};1;{n[5] / n[4]:.6f}" />\n'
    s = open(cos).read()
    assert 'K="WhiteBalance"' not in s
    s = s.replace("\t\t</AL>", key + "\t\t</AL>")
    open(cos, "w").write(s)


def stage(p, nm, v, wb_raw, lab):
    """Write the settings file for variant V of the staged raw P (named NM) and move it into the lab."""
    empty = os.path.join(STAGE, "no_lcc")
    os.makedirs(empty, exist_ok=True)
    cmd = [py, "-I", os.path.join(TOOLS, "c1_sidecars.py"), p, "--dest", lab, "--profile", PROBE, "--force"]
    if v in ("A", "W", "N"):
        cmd += ["--lcc-dir", empty]
    elif v == "L":
        cmd += ["--state-comp", "0,1,1"]
    r = subprocess.run(cmd, check=True, capture_output=True, text=True)
    print(r.stdout.strip().splitlines()[0], flush=True)
    cos = os.path.join(settings_dir(lab), nm + ".cos")
    if v in ("W", "N"):
        add_wb_key(cos, wb_raw)
    if v == "N":   # no Light Falloff either
        s = open(cos).read()
        assert s.count("|100|1\"") == 1
        open(cos, "w").write(s.replace("|100|1\"", "|0|1\""))
    shutil.move(p, os.path.join(lab, nm))


def render(raws, lab):
    os.makedirs(STAGE, exist_ok=True)
    names = []
    for raw in raws:
        for v in VARIANTS:
            nm = name(v, raw)
            p = os.path.join(STAGE, nm)
            shutil.copyfile(raw, p)
            stage(p, nm, v, raw, lab)
            names.append(nm)
    process(names, lab)


def flats(host, levels, lab):
    """Flats at several L* levels in copies of HOST (landscape, BaselineExposure 0, as in calibration), each
    rendered with no correction (N), the radial curve (W) and the uncalibrated LCC (L)."""
    sys.path.insert(0, TOOLS)
    from phocus_hotfolder import set_baseline_exposure, set_landscape
    os.makedirs(STAGE, exist_ok=True)
    names = []
    tag = os.path.splitext(os.path.basename(host))[0][-4:]
    for L in levels:
        for v in ("N", "W", "L"):
            nm = f"R20F{v}{int(L):02d}_{tag}.3FR"
            p = os.path.join(STAGE, nm)
            subprocess.run([py, "-I", os.path.join(TOOLS, "make_synthetic_raw.py"), host, p, "--flat", str(L),
                            "--uid", f"R20F{v}{int(L):02d}{tag}".ljust(16, "0")[:16]], check=True, capture_output=True)
            set_landscape(p)
            set_baseline_exposure(p, 0.0)
            stage(p, nm, v, host, lab)
            names.append(nm)
    process(names, lab)


def refflats(host, L, lab):
    """A flat in a copy of HOST corrected the way pre-processing did it (raw x map x lens brightness, no LCC,
    no Light Falloff, exposure 0: P), and the same flat through the LCC route as prepare_folder writes it (C)."""
    from phocus_hotfolder import set_baseline_exposure, set_landscape
    os.makedirs(STAGE, exist_ok=True)
    tag = os.path.splitext(os.path.basename(host))[0][-4:]
    base = os.path.join(STAGE, f"flat_{tag}.3fr")
    subprocess.run([py, "-I", os.path.join(TOOLS, "make_synthetic_raw.py"), host, base, "--flat", str(L),
                    "--uid", f"R20R{tag}".ljust(16, "0")], check=True, capture_output=True)
    set_landscape(base)
    set_baseline_exposure(base, 0.0)
    names = []
    for v in ("P", "C"):
        nm = f"R20R{v}{int(L):02d}_{tag}.3FR"
        p = os.path.join(STAGE, nm)
        if v == "P":
            subprocess.run([py, os.path.join(HERE, "preprocess_3fr_ref.py"), base, p, "--maps",
                            os.path.join(FIT, "preprocess_maps"), "--uid", f"R20RP{tag}"], check=True, capture_output=True)
            subprocess.run([py, "-I", os.path.join(TOOLS, "c1_sidecars.py"), p, "--dest", lab, "--profile", PROBE,
                            "--force", "--lcc-dir", os.path.join(STAGE, "no_lcc")], check=True, capture_output=True)
            cos = os.path.join(settings_dir(lab), nm + ".cos")
            s = open(cos).read()
            assert s.count("|100|1\"") == 1 and s.count('K="Exposure"') == 1
            import re
            s = s.replace("|100|1\"", "|0|1\"")
            s = re.sub(r'K="Exposure" V="[^"]*"', 'K="Exposure" V="0.0000"', s)
            open(cos, "w").write(s)
            shutil.move(p, os.path.join(lab, nm))
        else:
            shutil.copyfile(base, p)
            stage(p, nm, "C", host, lab)
        names.append(nm)
    os.remove(base)
    process(names, lab)


def analyse_refflats(host, L):
    tag = os.path.splitext(os.path.basename(host))[0][-4:]
    im = {}
    for v in ("P", "C"):
        img = romm_decode(tifffile.imread(os.path.join(OUT, f"R20R{v}{int(L):02d}_{tag}.tif"))[..., :3].astype(np.float64) / 65535)
        im[v] = img
    H, W = im["P"].shape[:2]
    yy, xx = np.mgrid[:H, :W]
    r = np.hypot(yy - (H - 1) / 2, xx - (W - 1) / 2) / np.hypot((H - 1) / 2, (W - 1) / 2)
    q = np.log2(im["C"] / im["P"])
    ok = (im["P"].max(-1) < 0.9) & (im["C"].max(-1) < 0.9)
    out = [f"{os.path.basename(host)}: LCC route minus pre-processing, stops (G; R, B)"]
    out.append(f"  centre {np.round(q[(r < 0.02) & ok].mean(0), 4)}   whole frame (r<0.95) {np.round(q[(r < 0.95) & ok].mean(0), 4)}")
    out.append("  by radius G: " + " ".join(f"{b:.1f}:{q[(r >= b) & (r < b + 0.1) & ok][:, 1].mean():+.4f}" for b in np.arange(0, 1.0, 0.1)))
    print("\n".join(out))


def process(names, lab):
    wait_listed(names, limit=600)
    osa('tell application "Capture One"', 'set d to current document', f'set rn to "{RECIPE}"',
        'if not (exists recipe rn of d) then', 'make new recipe at end of recipes of d with properties {name:rn}',
        'set r to recipe rn of d', 'set output format of r to TIFF', 'set bits of r to 16', 'set color profile of r to "ROMM RGB"',
        'set output sub folder of r to "r20"', 'set ignore crop of r to true', 'set scaling method of r to Fixed',
        'set scaling unit of r to percent', 'set primary scaling value of r to 25', 'set existing files of r to overwrite',
        'end if', *[f'process (variant 1 of (first image of d whose name is "{nm}")) recipe rn' for nm in names],
        'end tell', timeout=600)
    src = os.path.join(os.path.dirname(os.path.abspath(lab)), "Output", "r20")
    os.makedirs(OUT, exist_ok=True)
    for nm in names:
        p = os.path.join(src, os.path.splitext(nm)[0] + ".tif")
        wait_file(p, limit=600)
        shutil.move(p, os.path.join(OUT, os.path.basename(p)))
        os.remove(os.path.join(lab, nm))   # Capture One shows it as missing; clean with state_lcc.py clean
    print(f"rendered {len(names)}; lab raws removed")


def load(v, raw):
    p = os.path.join(OUT, os.path.splitext(name(v, raw))[0] + ".tif")
    return romm_decode(tifffile.imread(p)[..., :3].astype(np.float64) / 65535)


def analyse(raws):
    for raw in raws:
        key = lens_state(raw)[0]
        lid = lcc_id(find_map(os.path.join(FIT, "preprocess_maps"), key))
        cal = json.load(open(os.path.join(LCC_DIR, lid + ".json")))
        m = np.array([cal["kR"], 1.0, cal["kB"]]) * 2 ** cal["ev"]
        pred = m ** -np.array(cal["slope"])
        im = {v: load(v, raw) for v in VARIANTS}
        H, W = im["A"].shape[:2]
        yy, xx = np.mgrid[:H, :W]
        r = np.hypot(yy - H / 2, xx - W / 2) / np.hypot(H / 2, W / 2)
        a = im["A"]
        ok = (a.min(-1) > 0.02) & (a.max(-1) < 0.85)
        for v in VARIANTS:
            ok &= (im[v].min(-1) > 0.005) & (im[v].max(-1) < 0.95)
        print(f"\n{os.path.basename(raw)}  {lid}  calibration predicts L/W = {np.round(pred, 4)}")

        def ratio(num, den, mask):
            q = np.log2(im[num][mask] / im[den][mask])
            return np.median(q, 0)

        for num, den in (("W", "A"), ("L", "W"), ("C", "A")):
            cen = ok & (r < 0.15)
            line = f"  {num}/{den} centre (stops R,G,B) {np.round(ratio(num, den, cen), 4)}"
            g = a[..., 1]
            lv = []
            for lo, hi in ((0.02, 0.08), (0.08, 0.2), (0.2, 0.4), (0.4, 0.85)):
                mk = cen & (g >= lo) & (g < hi)
                if mk.sum() > 500:
                    lv.append(f"{lo:.2f}-{hi:.2f}: {ratio(num, den, mk)[1]:+.4f} ({mk.sum()})")
            rad = []
            for lo in (0.0, 0.2, 0.4, 0.6, 0.8):
                mk = ok & (r >= lo) & (r < lo + 0.2)
                if mk.sum() > 500:
                    rad.append(f"r{lo:.1f}: {ratio(num, den, mk)[1]:+.4f}")
            print(line)
            print("     by level (G): " + "; ".join(lv))
            print("     by radius (G): " + "; ".join(rad))


def analyse_flats(host, levels):
    tag = os.path.splitext(os.path.basename(host))[0][-4:]
    print(f"flats in {os.path.basename(host)}: centre, log2 ratios (R, G, B)")
    for L in levels:
        c = {}
        for v in ("N", "W", "L"):
            p = os.path.join(OUT, f"R20F{v}{int(L):02d}_{tag}.tif")
            img = romm_decode(tifffile.imread(p)[..., :3].astype(np.float64) / 65535)
            H, W = img.shape[:2]
            c[v] = img[H // 2 - 40: H // 2 + 40, W // 2 - 40: W // 2 + 40].reshape(-1, 3).mean(0)
        f = lambda a, b: np.round(np.log2(c[a] / c[b]), 4)  # noqa: E731
        print(f"  L* {L:4.0f}  N level G {c['N'][1]:.4f}   W/N {f('W', 'N')}   L/N {f('L', 'N')}   L/W {f('L', 'W')}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("render", "analyse", "flats", "analyse-flats", "refflats", "analyse-refflats"))
    ap.add_argument("raws", nargs="+")
    ap.add_argument("--lab", default=os.path.expanduser("~/Pictures/X2D Profile/Capture"))
    ap.add_argument("--levels", default="10,20,35,50,65,80")
    a = ap.parse_args()
    levels = [float(v) for v in a.levels.split(",")]
    if a.cmd == "render":
        render(a.raws, a.lab)
    elif a.cmd == "analyse":
        analyse(a.raws)
    elif a.cmd == "flats":
        for h in a.raws:
            flats(h, levels, a.lab)
    elif a.cmd == "refflats":
        for h in a.raws:
            refflats(h, levels[0], a.lab)
    elif a.cmd == "analyse-refflats":
        for h in a.raws:
            analyse_refflats(h, levels[0])
    else:
        for h in a.raws:
            analyse_flats(h, levels)


if __name__ == "__main__":
    main()
