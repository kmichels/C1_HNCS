"""Write a synthetic X2D II 3FR: a copy of a real raw whose active area is replaced by a grid of flat
colour patches with exactly known camera RGB, on a mid-grey background. Masked (optical black) borders
and all metadata are kept, so Phocus and Capture One treat it like the original.

Patch values are set in white-balanced camera RGB ("device", 0-1, green-normalised) using the host's
AsShotNeutral, spaced evenly in L*-like steps per channel. A mapping of patch -> device RGB and position
is written next to the raw as <name>.patches.npz.

usage: python make_synthetic_raw.py HOST.3fr OUT.3fr [--levels 22] [--patch 32] [--scale 0.92] [--seed 0] [--part i/N]
       [--neutral-from RAW | --neutral r,g,b] [--flat L]
  --part i/N puts only every N-th colour of the (shuffled) grid in this file, so a dense grid can be
  spread over N files that stay near the frame centre.
"""
import argparse
import os
import shutil

import numpy as np
import tifffile


def lstar01_inv(t):
    L = t * 100
    return np.where(L > 8, ((L + 16) / 116) ** 3, L * 27 / 24389)


ap = argparse.ArgumentParser()
ap.add_argument("host"); ap.add_argument("out")
ap.add_argument("--levels", type=int, default=22)
ap.add_argument("--patch", type=int, default=32)
ap.add_argument("--scale", type=float, default=0.92, help="device 1.0 maps to this fraction of the raw range")
ap.add_argument("--seed", type=int, default=0)
ap.add_argument("--uid", default="HNCSSYNTH0000001")
ap.add_argument("--part", default="0/1")
ap.add_argument("--flat", type=float, default=None, help="write a uniform grey at this L* instead of patches")
ap.add_argument("--neutral-from", default=None, help="use another raw's As Shot white balance (written to IFD0 AsShotNeutral and the maker-note copy 0xc628)")
ap.add_argument("--device-npy", default=None, help="custom patch list: an N x 3 .npy of device RGB (instead of the --levels grid); values above 1/scale clip at white")
ap.add_argument("--neutral", default=None, help="As Shot white balance as camera-RGB neutral r,g,b (g = 1), written like --neutral-from")
a = ap.parse_args()

with tifffile.TiffFile(a.host) as t:
    assert t.byteorder == "<"
    p0 = t.pages[0]
    sp = p0.pages[0]
    raw = sp.asarray().copy()
    off = sp.dataoffsets[0]
    nbytes = sp.databytecounts[0]
    black = sp.tags["BlackLevel"].value[0]
    white = sp.tags["WhiteLevel"].value
    cx0, cy0 = sp.tags["DefaultCropOrigin"].value
    cw, ch = sp.tags["DefaultCropSize"].value
    n = p0.tags["AsShotNeutral"].value
    neutral = np.array([n[0] / n[1], n[2] / n[3], n[4] / n[5]])  # R, G, B
    uid_tag = p0.tags["RawDataUniqueID"]
    uid_off, uid_len = uid_tag.valueoffset, uid_tag.count
    asn_off = p0.tags["AsShotNeutral"].valueoffset
nb_override = None
if a.neutral_from:
    with tifffile.TiffFile(a.neutral_from) as t2:
        nb_override = t2.pages[0].tags["AsShotNeutral"].value
    n = nb_override
    neutral = np.array([n[0] / n[1], n[2] / n[3], n[4] / n[5]])
if a.neutral:
    vals = [float(v) for v in a.neutral.split(",")]
    nb_override = tuple(x for v in vals for x in (65536, int(round(65536 / v))))
    n = nb_override
    neutral = np.array([n[0] / n[1], n[2] / n[3], n[4] / n[5]])
assert raw.nbytes == nbytes
rng = float(white - black) * a.scale

# X2D II raws are RGGB from the raw origin (red at even row, even column; the crop origin is even).
SITE = {(0, 0): 0, (0, 1): 1, (1, 0): 1, (1, 1): 2}


def fill(region_rows, region_cols, dev):
    r0, r1 = region_rows
    c0, c1 = region_cols
    for (pr, pc), ch_ in SITE.items():
        rs = r0 + ((pr - r0) % 2)
        cs = c0 + ((pc - c0) % 2)
        raw[rs:r1:2, cs:c1:2] = np.uint16(np.clip(black + rng * dev[ch_] * neutral[ch_], 0, white))  # a sensor saturates at white


# background: mid grey everywhere in the active area
bg = lstar01_inv(0.5 if a.flat is None else a.flat / 100)
fill((cy0, cy0 + ch), (cx0, cx0 + cw), np.array([bg, bg, bg]))
if a.flat is not None:
    shutil.copyfile(a.host, a.out)
    with open(a.out, "r+b") as f:
        f.seek(off)
        f.write(raw.astype("<u2").tobytes())
        f.seek(uid_off)
        f.write(a.uid.encode()[:uid_len].ljust(uid_len, b"0"))
    np.savez(os.path.splitext(a.out)[0] + ".flat.npz", level=bg, neutral=neutral, active=(ch, cw), scale=a.scale)
    print(f"wrote flat field {a.out}: L* {a.flat}, device {bg:.4f}")
    raise SystemExit

lv = lstar01_inv(np.linspace(0, 1, a.levels))
grid = np.stack(np.meshgrid(lv, lv, lv, indexing="ij"), -1).reshape(-1, 3)
if a.device_npy:
    grid = np.load(a.device_npy).astype(np.float64)
pi, pn = (int(v) for v in a.part.split("/"))
sel = np.random.default_rng(1234).permutation(len(grid))
grid = grid[np.sort(sel[pi::pn])]
side = int(np.ceil(np.sqrt(len(grid))))
P = a.patch
assert P % 2 == 0
x_start = cx0 + cw // 2 - side * P // 2
y_start = cy0 + ch // 2 - side * P // 2
x_start -= (x_start - cx0) % 2
y_start -= (y_start - cy0) % 2
order = np.random.default_rng(a.seed).permutation(side * side)
cells = order[: len(grid)]
pos = np.zeros((len(grid), 2), np.int32)
for i, cell in enumerate(cells):
    gy, gx = divmod(int(cell), side)
    y0, x0 = y_start + gy * P, x_start + gx * P
    fill((y0, y0 + P), (x0, x0 + P), grid[i])
    pos[i] = (y0 - cy0, x0 - cx0)  # top-left within the active (cropped) image

shutil.copyfile(a.host, a.out)
with open(a.out, "r+b") as f:
    f.seek(off)
    f.write(raw.astype("<u2").tobytes())
    uid = a.uid.encode()[:uid_len].ljust(uid_len, b"0")
    f.seek(uid_off)
    f.write(uid)
    if nb_override is not None:
        import struct
        f.seek(asn_off)
        f.write(struct.pack("<6I", *nb_override))
        data = open(a.host, "rb").read(400000)
        with tifffile.TiffFile(a.host) as t3:
            mn = t3.pages[0].tags["ExifTag"].value["MakerNote"]
        mo = data.find(mn[:64])
        cnt = struct.unpack_from("<H", data, mo)[0]
        for i in range(cnt):
            tag, typ, c_, val = struct.unpack_from("<HHII", data, mo + 2 + 12 * i)
            if tag == 0xC628 and typ == 5 and c_ == 3:
                f.seek(val)
                f.write(struct.pack("<6I", *nb_override))
np.savez(os.path.splitext(a.out)[0] + ".patches.npz", device=grid, pos=pos, patch=P, active=(ch, cw), neutral=neutral,
         scale=a.scale, black=black, white=white, levels=a.levels, background=bg)
r_max = np.max(np.sqrt(((pos[:, 0] + P / 2 - ch / 2) ** 2 + (pos[:, 1] + P / 2 - cw / 2) ** 2)) / np.hypot(ch / 2, cw / 2))
print(f"wrote {a.out}: {len(grid)} patches of {P}px in a {side}x{side} grid, max radius {r_max:.2f}; neutral {np.round(neutral, 4)}; black {black} white {white}")
