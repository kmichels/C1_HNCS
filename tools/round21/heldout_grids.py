"""Held-out white-balance grids for checking shade profiles (Finding 44): 22-level grids at the given Kelvins on
the ColorMatrix1 daylight locus (no off-locus offset, unlike the fitting grids), in a copy of each host raw with
the reference body's record, rendered by Phocus with lens corrections off and saved as pairs for shade_eval.py.

usage: python heldout_grids.py OUTDIR RAW... [--kelvin 6500,7500] [--tungsten]
  --tungsten: instead, grids halfway between Finding 21's tungsten grids (log space), t = 0.625 and 1.125
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(HERE, "..")
sys.path.insert(0, TOOLS)
from c1_sidecars import daylight_neutral  # noqa: E402
from make_preprocess_map import lens_state, profile_name  # noqa: E402
from phocus_hotfolder import HotFolder, set_baseline_exposure, set_landscape, set_reference_body  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("out")
ap.add_argument("raws", nargs="+")
ap.add_argument("--kelvin", default="6500,7500")
ap.add_argument("--tungsten", action="store_true")
a = ap.parse_args()
os.makedirs(a.out, exist_ok=True)
work = tempfile.mkdtemp(prefix="hncs-heldout-")
py = sys.executable
try:
    jobs = []
    for raw in a.raws:
        name = profile_name(lens_state(raw)[1])
        if a.tungsten:
            import numpy as np
            st = [np.load(os.path.join(TOOLS, "..", "fit", "synthetic", "pairs", f"HNCStungA{i}.npz"))["neutral"] for i in (1, 2, 3, 4)]
            targets = [("T12", np.sqrt(st[0] * st[1])), ("T34", np.sqrt(st[2] * st[3]))]
        else:
            targets = [(f"L{k}", daylight_neutral(raw, k)) for k in (int(v) for v in a.kelvin.split(","))]
        for k, nt in targets:
            tag = f"{name}_{k}"
            p = os.path.join(work, tag + ".3fr")
            n = ",".join(f"{v:.5f}" for v in nt)
            subprocess.run([py, "-I", os.path.join(TOOLS, "make_synthetic_raw.py"), raw, p, "--neutral", n,
                            "--uid", f"HNCSHO{k}{name}".replace("-", "")[:16].ljust(16, "0")], check=True, capture_output=True)
            set_landscape(p)
            set_baseline_exposure(p, 0.0)
            set_reference_body(p)
            jobs.append((tag, p))
    with HotFolder() as hf:
        for tag, p in jobs:
            tif = os.path.join(work, tag + "_phocus.tif")
            shutil.move(hf.render(p, name=f"ho_{tag}.3fr", LensCorrection=0), tif)
            subprocess.run([py, "-I", os.path.join(TOOLS, "save_synth_pairs.py"), p[:-4] + ".patches.npz", "-", tif,
                            os.path.join(a.out, f"HNCSheldout_{tag}.npz")], check=True, capture_output=True)
            os.remove(tif)
            os.remove(p)
            print("rendered", tag, flush=True)
finally:
    shutil.rmtree(work, ignore_errors=True)
