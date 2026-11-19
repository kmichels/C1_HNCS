"""Synthetic colour grids at As Shot white balances from 4200 to 8000 K (neutral from ColorMatrix1 on the
daylight locus), in a copy of the ladder's host raw. Run from data/synth/r11/."""
import os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from cct import cm_of, neutral_for
HOST = "../hl/HNCShl.3fr"
cm = cm_of(HOST)
for T in (4200, 4500, 5000, 5500, 6000, 6500, 7000, 7500, 8000):
    n = ",".join(f"{v:.5f}" for v in neutral_for(cm, T))
    subprocess.run([sys.executable, "-I", os.path.join(HERE, "..", "make_synthetic_raw.py"), HOST, f"HNCSwb{T}.3fr", "--levels", "9",
                    "--patch", "48", "--neutral", n, "--uid", f"HNCSWB000000{T:04d}"], check=True)
