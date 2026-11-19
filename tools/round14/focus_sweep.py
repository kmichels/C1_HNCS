"""Sweep Phocus's focus input (byte 6 of maker-note 0x0018) on a synthetic flat made from one raw.

Builds a flat field (L* 30) in a copy of HOST, writes each focus code into its own copy, renders them in
Phocus through the hot folder (lens corrections on, and off for the first and last code), and reports
centre L*, green gain by radius and B-G at r 0.9 from flat_gain.py.

usage: python tools/round14/focus_sweep.py HOST.3fr LUT.npz OUTDIR CODE[,CODE...]   (run from the repo root)
"""
import os
import shutil
import struct
import subprocess
import sys

import numpy as np
import tifffile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from makernote_transplant import entries  # noqa: E402
from phocus_hotfolder import HotFolder, set_baseline_exposure, set_landscape  # noqa: E402

host, lut, out, codes = sys.argv[1], sys.argv[2], sys.argv[3], [int(c) for c in sys.argv[4].split(",")]
os.makedirs(out, exist_ok=True)
py = sys.executable
flat = os.path.join(out, "flat.3fr")
subprocess.run([py, "-I", os.path.join(HERE, "..", "make_synthetic_raw.py"), host, flat, "--flat", "30", "--uid", "HNCSFOCUSFLAT000"], check=True, capture_output=True)
set_landscape(flat)
set_baseline_exposure(flat, 0.0)
loc = entries(flat)[0x0018]["loc"]
with tifffile.TiffFile(flat) as t:
    uid_off = t.pages[0].tags["RawDataUniqueID"].valueoffset
jobs = [(c, 4) for c in codes] + [(codes[0], 0), (codes[-1], 0)]
rows = {}
with HotFolder() as hf:
    for code, lc in jobs:
        raw = os.path.join(out, f"f{code:02d}_lc{lc}.3fr")
        shutil.copyfile(flat, raw)
        with open(raw, "r+b") as f:
            f.seek(loc + 6); f.write(struct.pack("B", code))
            f.seek(uid_off); f.write(f"HNCSFOCUS{code:02d}LC{lc}".ljust(16, "0")[:16].encode())
        assert entries(raw)[0x0018]["raw"][6] == code
        tif = hf.render(raw, LensCorrection=lc)
        npz = os.path.join(out, f"f{code:02d}_lc{lc}.npz")
        subprocess.run([py, "-I", os.path.join(HERE, "..", "flat_gain.py"), lut, tif, npz], check=True, capture_output=True)
        os.remove(tif); os.remove(raw)
        z = np.load(npz)
        r, st = z["radius"].ravel(), np.log2(np.clip(z["gain"].reshape(-1, 3), 1e-6, None))
        prof = [st[(r >= x - 0.025) & (r < x + 0.025), 1].mean() for x in (0.2, 0.4, 0.6, 0.8, 0.9)]
        bg = (st[:, 2] - st[:, 1])[(r >= 0.875) & (r < 0.925)].mean()
        rows[(code, lc)] = (z["centre_lab"][0], prof, bg)
        print(f"code {code:2d} corrections {'on ' if lc else 'off'}: centre L* {z['centre_lab'][0]:.2f}; green gain r0.2/0.4/0.6/0.8/0.9 "
              + " ".join(f"{p:+.3f}" for p in prof) + f"; B-G r0.9 {bg:+.3f}", flush=True)
os.remove(flat)
