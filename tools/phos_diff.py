"""Flatten each sidecar's active ImageSettings entry and show the settings that differ between frames."""
import glob, os, plistlib, sys
from collections import defaultdict

def flat(o, p=""):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from flat(v, f"{p}/{k}")
    elif isinstance(o, list):
        if len(o) <= 8 and all(not isinstance(x, (dict, list)) for x in o):
            yield p, tuple(o)
        else:
            for i, v in enumerate(o):
                yield from flat(v, f"{p}[{i}]")
    elif isinstance(o, bytes):
        yield p, f"<{len(o)} bytes>"
    else:
        yield p, o

rows = {}
for d in sys.argv[1:]:
    for f in sorted(glob.glob(os.path.join(d, "*.phos"))):
        pl = plistlib.load(open(f, "rb"))
        ix = pl["CurrentIx"]
        rows[os.path.basename(f)[:8]] = dict(flat(pl["ImageSettings"][ix]))
keys = sorted(set().union(*rows.values()))
vary = defaultdict(dict)
for k in keys:
    vals = {n: r.get(k, "<absent>") for n, r in rows.items()}
    if len(set(map(repr, vals.values()))) > 1:
        vary[k] = vals
print(f"{len(rows)} frames, {len(keys)} settings, {len(vary)} differ")
for k, vals in vary.items():
    groups = defaultdict(list)
    for n, v in vals.items():
        groups[repr(v)[:60]].append(n[-3:])
    print(f"{k}:")
    for v, ns in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        print(f"    {v}  <- {' '.join(ns)}")
