"""Make pre-processing maps for every lens state (lens, focal length, aperture) among the given raws that
fit/preprocess_maps (or --maps) doesn't have yet: a synthetic flat from one raw of each state, rendered by
Phocus through its hot folder with lens corrections on, measured and converted to a raw-gain map.
Phocus is restarted and its preferences restored afterwards; don't use it meanwhile. Raws are only read.

usage: python auto_maps.py RAW [RAW ...] [--maps fit/preprocess_maps] [--dry-run]
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from make_preprocess_map import lens_state  # noqa: E402
from phocus_hotfolder import HotFolder  # noqa: E402

LUTS = {"XCD28P": "lut_e5_28p.npz", "XCD35-100E": "lut_e5_35-100.npz"}


def set_landscape(path):
    """Orientation 1 in the flat copy, so Phocus exports it in sensor orientation like the raw data."""
    import struct
    import tifffile
    with tifffile.TiffFile(path) as t:
        tag = t.pages[0].tags.get("Orientation")
        if tag is None or tag.value == 1:
            return
        off = tag.valueoffset
    with open(path, "r+b") as f:
        f.seek(off)
        f.write(struct.pack("<H", 1))

ap = argparse.ArgumentParser()
ap.add_argument("raws", nargs="+")
ap.add_argument("--maps", default=os.path.join(HERE, "..", "fit", "preprocess_maps"))
ap.add_argument("--dry-run", action="store_true")
a = ap.parse_args()
todo = {}
for r in a.raws:
    key, lens, focal, fnum = lens_state(r)
    if not os.path.exists(os.path.join(a.maps, key + ".npz")):
        todo.setdefault(key, (r, lens))
print(f"{len(todo)} lens states need a map: {', '.join(sorted(todo)) or '-'}")
if a.dry_run or not todo:
    sys.exit(0)
py = sys.executable
work = tempfile.mkdtemp(prefix="hncs-maps-")
try:
    hf = HotFolder()
    with hf:
        for key, (raw, lens) in sorted(todo.items()):
            flat = os.path.join(work, f"flat_{key}.3fr")
            subprocess.run([py, "-I", os.path.join(HERE, "make_synthetic_raw.py"), raw, flat, "--flat", "30", "--uid", "HNCSAUTOMAP00000"], check=True, capture_output=True)
            set_landscape(flat)
            tif = hf.render(flat, name=f"flat_{key}.3fr", LensCorrection=4)
            lut = os.path.join(HERE, "..", "fit", LUTS.get(lens.replace(" ", ""), "lut_e4.npz"))
            fg = os.path.join(work, f"gain_{key}.npz")
            subprocess.run([py, "-I", os.path.join(HERE, "flat_gain.py"), lut, tif, fg], check=True, capture_output=True)
            out = subprocess.run([py, "-I", os.path.join(HERE, "make_preprocess_map.py"), fg, flat, a.maps], check=True, capture_output=True, text=True).stdout.strip()
            print(out)
            for f in (flat, tif, fg, os.path.splitext(flat)[0] + ".flat.npz"):
                if os.path.exists(f):
                    os.remove(f)
finally:
    shutil.rmtree(work, ignore_errors=True)
