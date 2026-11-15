"""Per-body adjustment for the HNCS profiles, from an X2D II raw's factory calibration record.

Phocus normalises each body with two half-float gains stored in maker-note entry 0x0019 (a "GAIN"
record, bytes 84-87); Capture One ignores them. A synthetic sweep showed Phocus's effect is equivalent
to multiplying camera RGB by
    ln kR = -0.0705 ln(g1/g1_ref)
    ln kB = -0.0875 ln(g1/g1_ref) + 0.0775 ln(g2/g2_ref)      (kG = 1)
relative to the body the profiles were fitted on (g1_ref = 2.600, g2_ref = 2.260). Validated on 32 raws
from another body: the grey offset fell from (-0.52, +0.53) a*/b* to (-0.08, -0.03).

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
g1, g2 = (float(v) for v in np.frombuffer(rec[84:88], "<f2"))
r1, r2 = (float(v) for v in a.ref.split(","))
kR = np.exp(-0.0705 * np.log(g1 / r1))
kB = np.exp(-0.0875 * np.log(g1 / r1) + 0.0775 * np.log(g2 / r2))
print(f"factory gains: {g1:.3f}, {g2:.3f} (reference {r1:.3f}, {r2:.3f})")
print(f"--input-gain {kR:.5f},1.00000,{kB:.5f}")
