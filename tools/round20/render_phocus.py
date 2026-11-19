"""Phocus renders (Standard, lens corrections on) of the validation raws, for re-scoring (Finding 43).

usage: python render_phocus.py OUTDIR RAW...
"""
import os
import shutil
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from phocus_hotfolder import HotFolder  # noqa: E402

out = sys.argv[1]
with HotFolder() as hf:
    for f in sys.argv[2:]:
        dst = os.path.join(out, os.path.splitext(os.path.basename(f))[0] + ".tif")
        if os.path.exists(dst):
            continue
        shutil.move(hf.render(f, LensCorrection=4), dst)
        print("phocus", f, flush=True)
