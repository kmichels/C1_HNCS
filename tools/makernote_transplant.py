"""Copy selected Hasselblad maker-note entries from a donor 3FR into a copy of a target 3FR, in place.

The X2D II maker note is a TIFF IFD with absolute offsets. Entries whose size matches in both files are
overwritten in place (inline values in the entry itself, larger values at their data offset), so no
offsets move. Used to find which maker-note data changes Phocus's rendering.

usage: python makernote_transplant.py TARGET.3fr DONOR.3fr OUT.3fr TAG[,TAG...] [--uid UID16]
  TAG as hex (0x0074) or 'all' for every same-size entry that differs.
"""
import argparse
import shutil
import struct

import tifffile

TS = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 7: 1, 8: 2, 9: 4, 10: 8, 11: 4, 12: 8}


def entries(path):
    data = open(path, "rb").read(400000)
    with tifffile.TiffFile(path) as t:
        b = t.pages[0].tags["ExifTag"].value["MakerNote"]
    off = data.find(b[:64])
    n = struct.unpack_from("<H", data, off)[0]
    out = {}
    for i in range(n):
        pos = off + 2 + 12 * i
        tag, typ, cnt, val = struct.unpack_from("<HHII", data, pos)
        size = TS.get(typ, 1) * cnt
        loc = pos + 8 if size <= 4 else val
        out[tag] = dict(typ=typ, cnt=cnt, size=size, loc=loc, raw=data[loc: loc + size])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("target"); ap.add_argument("donor"); ap.add_argument("out"); ap.add_argument("tags")
    ap.add_argument("--uid", default=None)
    a = ap.parse_args()
    T, D = entries(a.target), entries(a.donor)
    if a.tags == "all":
        tags = [t for t in T if t in D and T[t]["size"] == D[t]["size"] and T[t]["raw"] != D[t]["raw"]]
    else:
        tags = [int(x, 16) for x in a.tags.split(",")]
    shutil.copyfile(a.target, a.out)
    done, skipped = [], []
    with open(a.out, "r+b") as f:
        for tag in tags:
            if tag not in T or tag not in D or T[tag]["size"] != D[tag]["size"] or T[tag]["typ"] != D[tag]["typ"]:
                skipped.append(f"0x{tag:04x}")
                continue
            f.seek(T[tag]["loc"])
            f.write(D[tag]["raw"])
            done.append(f"0x{tag:04x}")
        if a.uid:
            with tifffile.TiffFile(a.target) as t:
                uo = t.pages[0].tags["RawDataUniqueID"].valueoffset
            f.seek(uo)
            f.write(a.uid.encode()[:16].ljust(16, b"0"))
    chk = entries(a.out)
    assert all(chk[int(t, 16)]["raw"] == D[int(t, 16)]["raw"] for t in done)
    print(f"{a.out}: transplanted {len(done)} entries {','.join(done)}; skipped {skipped}")


if __name__ == "__main__":
    main()
