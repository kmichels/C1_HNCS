"""Pre-process a folder of X2D II raws: write a corrected copy of each (same file name) into another
folder, for Capture One with the "HNCS E5 … (pre-processed)" styles. Originals are only read; existing
copies are skipped. With --make-maps, missing maps are made first through Phocus (auto_maps.py).

usage: python preprocess_folder.py IN_DIR OUT_DIR [--maps fit/preprocess_maps] [--make-maps] [--body-gains]
"""
import argparse
import glob
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from make_preprocess_map import lens_state  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("inp"); ap.add_argument("out")
ap.add_argument("--maps", default=os.path.join(HERE, "..", "fit", "preprocess_maps"))
ap.add_argument("--make-maps", action="store_true", help="make missing maps with Phocus first (restarts Phocus)")
ap.add_argument("--body-gains", action="store_true")
a = ap.parse_args()
if os.path.realpath(a.inp) == os.path.realpath(a.out):
    sys.exit("OUT_DIR must differ from IN_DIR (corrected copies keep the original file names)")
raws = sorted(f for f in glob.glob(os.path.join(a.inp, "*")) if f.lower().endswith(".3fr"))
if not raws:
    sys.exit(f"no .3fr files in {a.inp}")
os.makedirs(a.out, exist_ok=True)
todo = [r for r in raws if not os.path.exists(os.path.join(a.out, os.path.basename(r)))]
missing = sorted({lens_state(r)[0] for r in todo if not os.path.exists(os.path.join(a.maps, lens_state(r)[0] + ".npz"))})
if missing and a.make_maps:
    subprocess.run([sys.executable, "-I", os.path.join(HERE, "auto_maps.py"), *todo, "--maps", a.maps], check=True)
    missing = sorted({lens_state(r)[0] for r in todo if not os.path.exists(os.path.join(a.maps, lens_state(r)[0] + ".npz"))})
done, skipped = 0, []
for r in todo:
    key = lens_state(r)[0]
    if key in missing:
        skipped.append(os.path.basename(r)); continue
    dst = os.path.join(a.out, os.path.basename(r))
    cmd = [sys.executable, "-I", os.path.join(HERE, "preprocess_3fr.py"), r, dst + ".part", "--maps", a.maps]
    if a.body_gains:
        cmd.append("--body-gains")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"{os.path.basename(r)}: failed: {res.stderr.strip()[-300:]}")
        if os.path.exists(dst + ".part"):
            os.remove(dst + ".part")
        continue
    os.replace(dst + ".part", dst)
    done += 1
    print(f"{os.path.basename(r)}: {res.stdout.strip().splitlines()[0]}", flush=True)
print(f"\n{done} written, {len(raws) - len(todo)} already there, {len(skipped)} without a map"
      + (f" ({', '.join(missing)}; run with --make-maps)" if skipped else ""))
