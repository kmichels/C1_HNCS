"""Build the probe profile: a Capture One camera profile whose device RGB is read as ROMM RGB.

Render a raw through it and export to ROMM RGB 16-bit, and the TIFF holds exactly the
white-balanced camera RGB that Capture One hands to a camera ICC (gamma-1.8 encoded).

usage: python build_probe.py OUTDIR
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from icc import D50, InputProfile, MatrixProfile, Mft2, build_profile, de2000, desc_tag, lab_to_legacy16, text_tag, xyz_to_lab  # noqa: E402

IN = "/Applications/Capture One.app/Contents/Frameworks/ImageProcessing.framework/Versions/A/Resources/Profiles/Input/"
NAME = "HasselbladX2DII100C-E0 Probe"
outdir = sys.argv[1]
pro = InputProfile(IN + "HasselbladX2DII100C-ProStandard.icm")
romm = MatrixProfile("/System/Library/ColorSync/Profiles/ROMM RGB.icc")

G, NIN = 33, 1025


def lstar(y):
    return np.where(y > 216 / 24389, 116 * np.cbrt(y) - 16, y * 24389 / 27) / 100


# The shaper spaces grid nodes evenly in L* of each channel.
x = np.linspace(0, 1, NIN)
in_curves = np.round(np.tile(lstar(romm.decode(x, 0)), (3, 1)) * 65535).astype(np.uint16)
xs = np.linspace(0, 1, 200001)
node_x = np.interp(np.linspace(0, 1, G), lstar(romm.decode(xs, 0)), xs)
R, Gg, B = np.meshgrid(node_x, node_x, node_x, indexing="ij")
lab_nodes = xyz_to_lab(romm.to_xyz(np.stack([R, Gg, B], -1)) * (D50 / romm.wtpt))
probe = Mft2(np.eye(3), in_curves, lab_to_legacy16(lab_nodes), np.array([[0, 65535]] * 3, dtype=np.uint16))

path = os.path.join(outdir, NAME + ".icm")
tags = [("desc", desc_tag(NAME)), ("cprt", text_tag("Probe profile for fitting - not for editing")), ("wtpt", pro.tags["wtpt"]), ("A2B0", probe.serialize())]
open(path, "wb").write(build_profile(pro.data[:128], tags))
c = InputProfile(path)
assert c.desc() == NAME

rng = np.random.default_rng(1)
s = rng.random((200000, 3))
exact = xyz_to_lab(romm.to_xyz(s) * (D50 / romm.wtpt))
got = c.evaluate(s)
ok = (np.abs(exact[:, 1]) < 127) & (np.abs(exact[:, 2]) < 127)
d = de2000(exact[ok], got[ok])
print(f"wrote {path}")
print(f"probe vs exact ROMM ({ok.mean():.1%} representable): median {np.median(d):.3f} p99 {np.percentile(d, 99):.3f} dE00")
