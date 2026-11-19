"""Rank raws by how much of the frame is bright, saturated yellow to orange: the colours Finding 34 fixed.

Per 32x32-photosite block of the active area, white-balanced camera RGB (As Shot). A block counts when its
green raw level is at least 0.55 of white (where Phocus's yellows pass L* 95), blue is at most half of
green and red at least 0.6 of green. Prints the fraction of the frame that qualifies.

usage: python find_bright_yellow.py LIST.txt   (one 3FR path per line)
"""
import sys

import numpy as np
import tifffile

for path in open(sys.argv[1]).read().splitlines():
    try:
        with tifffile.TiffFile(path) as t:
            p0 = t.pages[0]
            if p0.tags["Model"].value != "X2D II 100C":
                continue
            sp = p0.pages[0]
            raw = sp.asarray()
            black, white = sp.tags["BlackLevel"].value[0], sp.tags["WhiteLevel"].value
            cx, cy = sp.tags["DefaultCropOrigin"].value
            cw, ch = sp.tags["DefaultCropSize"].value
            n = p0.tags["AsShotNeutral"].value
            lens = p0.tags["ExifTag"].value.get("LensModel", "")
        neutral = np.array([n[0] / n[1], n[2] / n[3], n[4] / n[5]])
        a = (raw[cy:cy + ch, cx:cx + cw].astype(np.float32) - black) / (white - black)
        h, w = (a.shape[0] // 32) * 32, (a.shape[1] // 32) * 32
        a = a[:h, :w]
        rgb = np.stack([a[0::2, 0::2], (a[0::2, 1::2] + a[1::2, 0::2]) / 2, a[1::2, 1::2]], -1)
        rgb = rgb.reshape(h // 32, 16, w // 32, 16, 3).mean(axis=(1, 3))
        dev = rgb / neutral
        m = (rgb[..., 1] >= 0.55) & (dev[..., 2] <= 0.5 * dev[..., 1]) & (dev[..., 0] >= 0.6 * dev[..., 1]) & (rgb.max(-1) < 0.98)
        print(f"{m.mean() * 100:6.2f}%\t{lens}\t{path}", flush=True)
    except Exception as e:
        print(f"ERR\t{e}\t{path}", flush=True)
