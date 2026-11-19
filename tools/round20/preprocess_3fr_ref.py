"""Copy of tools/preprocess_3fr.py as of 8e1ca32, kept to make reference flats for Finding 43.

Write a corrected copy of an X2D II 3FR for Capture One: Phocus's spatial processing (vignetting
correction with lens corrections on, and its colour shading) baked into the sensor data, and optionally
the per-body factory-gain normalisation. Render the copy with an "HNCS E5 … (pre-processed)" style:
plain E5 profile, Light Falloff 0, no LCC. The original is only read.

The map is a raw-gain map from make_preprocess_map.py for the same lens state (lens, focal length,
aperture, focus code): either given with --map, or picked from a folder of maps with --maps (the nearest
focus code for the same lens setting if that exact map hasn't been made). Each raw channel is
multiplied by its gain, interpolated from the map's block centres to every photosite of the active area.
Values that would exceed the white level are clipped and counted (brightening corners uses up
highlight headroom there; with HNCS's tone curve those areas render near white anyway). Photosites
already clipped in the original stay at white so Capture One still treats them as clipped. (Scaling the
whole image down and raising BaselineExposure renders identically elsewhere but breaks that: the
clipped photosites end up brighter than their neighbours, a hard band once highlights are pulled down.)

usage: python preprocess_3fr.py IN.3fr OUT.3fr (--map MAP.npz | --maps DIR) [--body-gains [--ref 2.600,2.260]]
"""
import sys as _s, os as _o
_s.path.insert(0, _o.path.join(_o.path.dirname(_o.path.abspath(__file__)), '..'))
import argparse
import os
import shutil
import sys

import numpy as np
import tifffile
from scipy.interpolate import RegularGridInterpolator

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_preprocess_map import FIT, find_map, global_gain, lens_state, profile_name, reference_state  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("inp"); ap.add_argument("out")
g_ = ap.add_mutually_exclusive_group(required=True)
g_.add_argument("--map")
g_.add_argument("--maps", help="folder of make_preprocess_map.py maps; picks the one for this file's lens state")
ap.add_argument("--body-gains", action="store_true", help="also normalise the body to the reference factory gains")
ap.add_argument("--ref", default="2.600,2.260")
ap.add_argument("--uid", default=None)
ap.add_argument("--no-lens-brightness", action="store_true", help="skip Phocus's per-lens-state brightness normalisation")
a = ap.parse_args()
if os.path.exists(a.out):
    sys.exit(f"{a.out} exists; not overwriting")
if os.path.realpath(a.out) == os.path.realpath(a.inp):
    sys.exit("output must differ from input")

mp = a.map
if a.maps:
    key = lens_state(a.inp)[0]
    mp = find_map(a.maps, key)
    if mp is None:
        sys.exit(f"no map for {key} in {a.maps}: make one from this raw (see tools/README.md, pre-processing)")

with tifffile.TiffFile(a.inp) as t:
    p0 = t.pages[0]
    sp = p0.pages[0]
    raw = sp.asarray()
    off, nbytes = sp.dataoffsets[0], sp.databytecounts[0]
    black = int(sp.tags["BlackLevel"].value[0])
    white = int(np.min(sp.tags["WhiteLevel"].value))
    cx0, cy0 = sp.tags["DefaultCropOrigin"].value
    cw, ch = sp.tags["DefaultCropSize"].value
    uid_tag = p0.tags["RawDataUniqueID"]
    uid_off, uid_len = uid_tag.valueoffset, uid_tag.count
assert raw.dtype == np.uint16 and raw.nbytes == nbytes

z = np.load(mp)
gain, b = z["raw_gain"].astype(np.float64), int(z["block"])
H, W = (int(v) for v in z["shape"])
scale = ch / H  # raw photosites per export pixel (2 for a 50% export)
assert abs(scale - cw / W) < 0.01, "map shape doesn't match the active area's aspect"
nby, nbx = gain.shape[:2]
gg = 1.0
if not a.no_lens_brightness:
    name = profile_name(lens_state(a.inp)[1])
    ref = reference_state(name)
    lut = next((p for p in (os.path.join(FIT, f"lut_e5_{name}.npz"), os.path.join(FIT, f"lut_e5_{name.lower()}.npz")) if os.path.exists(p)), None)
    ref_path = find_map(os.path.dirname(mp), ref) if ref else None
    if ref_path and lut:
        gg = global_gain(mp, ref_path, lut)
        gain = gain * gg
print(f"lens-state brightness: x{gg:.4f} ({np.log2(gg):+.3f} stop)")
ys = cy0 + (np.arange(nby) + 0.5) * b * scale
xs = cx0 + (np.arange(nbx) + 0.5) * b * scale

k = np.ones(3)
if a.body_gains:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from makernote_transplant import entries
    rec = entries(a.inp)[0x0019]["raw"]
    g1, g2 = (round(float(v), 3) for v in np.frombuffer(rec[84:88], "<f2"))
    r1, r2 = (float(v) for v in a.ref.split(","))
    g1, g2 = (v if v > 0 else 2.1 for v in (g1, g2))
    k = np.array([1.0, (g1 / r1) ** 0.077, (g2 / r2) ** 0.078])
    print(f"body gains {g1:.3f}, {g2:.3f} -> camera RGB x {np.round(k, 5)}")

out = raw.astype(np.float32)
src_clip = raw >= white  # clipped in the original: no information, must stay at white so Capture One treats it as clipped
SITE = {(0, 0): 0, (0, 1): 1, (1, 0): 1, (1, 1): 2}  # RGGB from the raw origin
for (pr, pc), c in SITE.items():
    rows = np.arange(cy0 + ((pr - cy0) % 2), cy0 + ch, 2)
    cols = np.arange(cx0 + ((pc - cx0) % 2), cx0 + cw, 2)
    interp = RegularGridInterpolator((ys, xs), gain[..., c], bounds_error=False, fill_value=None)
    g = np.empty((len(rows), len(cols)), np.float32)
    for i0 in range(0, len(rows), 256):
        rr = rows[i0:i0 + 256]
        yy, xx = np.meshgrid(np.clip(rr, ys[0], ys[-1]), np.clip(cols, xs[0], xs[-1]), indexing="ij")
        g[i0:i0 + 256] = interp(np.stack([yy.ravel(), xx.ravel()], 1)).reshape(len(rr), len(cols))
    g *= k[c]
    out[np.ix_(rows, cols)] = (out[np.ix_(rows, cols)] - black) * g + black
act = out[cy0:cy0 + ch, cx0:cx0 + cw]
clipped = int(((act > white) & ~src_clip[cy0:cy0 + ch, cx0:cx0 + cw]).sum())
np.minimum(out, white, out=out)
out[src_clip] = white
print(f"map {os.path.basename(mp)}: raw gain {gain.min():.3f}..{gain.max():.3f}; "
      f"newly clipped photosites: {clipped} ({clipped / (ch * cw):.3%}); clipped in the original: {int(src_clip.sum())}")

shutil.copyfile(a.inp, a.out)
with open(a.out, "r+b") as fh:
    fh.seek(off)
    fh.write(np.round(out).astype("<u2").tobytes())
    uid = (a.uid or ("PP" + os.path.basename(a.out)[:14])).encode()[:uid_len].ljust(uid_len, b"0")
    fh.seek(uid_off)
    fh.write(uid)
print(f"wrote {a.out}")
