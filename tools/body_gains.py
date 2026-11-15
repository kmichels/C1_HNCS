"""Per-body adjustment for the HNCS profiles, from an X2D II raw's factory calibration record.

Phocus normalises each body with two half-float gains stored in maker-note entry 0x0019 (a "GAIN"
record, bytes 84-87); Capture One ignores them. Synthetic sweeps showed the first value acts as a green
gain and the second as a blue gain on camera RGB, independent of lens and nearly of white balance:
    kG = (g1 / g1_ref) ** 0.077
    kB = (g2 / g2_ref) ** 0.078            (kR = 1)
relative to the body the profiles were fitted on (g1_ref = 2.600, g2_ref = 2.260). Changing both values
at once combines the two effects. Validated on 32 raws from another body (2.363, 2.518): frame-centre
median 1.23 -> 0.96 dE00, grey offset (-0.52, +0.53) a*/b* -> (-0.08, +0.01).

Prints the --input-gain to pass to write_profile.py. For an "LCC" profile, multiply it with that
profile's LCC gain (fit/lcc/input_gains.txt) channel by channel.

usage: python body_gains.py YOUR_RAW.3fr [--ref 2.600,2.260]
"""
import argparse
import os

import numpy as np

src = open(os.path.join(os.path.dirname(__file__), "makernote_transplant.py")).read().split("ap = argparse")[0]
ns = {}
exec(src, ns)

ap = argparse.ArgumentParser()
ap.add_argument("raw")
ap.add_argument("--ref", default="2.600,2.260")
a = ap.parse_args()
rec = ns["entries"](a.raw)[0x0019]["raw"]
assert rec[:4] == b"GAIN", "maker-note 0x0019 is not a GAIN record"
g1, g2 = (round(float(v), 3) for v in np.frombuffer(rec[84:88], "<f2"))
r1, r2 = (float(v) for v in a.ref.split(","))
if g1 <= 0 or g2 <= 0:
    print(f"factory gains: {g1:.3f}, {g2:.3f}: Phocus treats a zero as roughly 2.1; using 2.1")
    g1, g2 = (v if v > 0 else 2.1 for v in (g1, g2))
kG = (g1 / r1) ** 0.077
kB = (g2 / r2) ** 0.078
print(f"factory gains: {g1:.3f}, {g2:.3f} (reference {r1:.3f}, {r2:.3f})")
print(f"--input-gain 1.00000,{kG:.5f},{kB:.5f}")
