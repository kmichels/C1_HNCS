import os, shutil, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, '..')); sys.path.insert(0, HERE)
from phocus_hotfolder import HotFolder
from patch_means import patch_means
jobs = [("HNCSnc.3fr", "HNCSnc", {}), ("HNCSncE2.3fr", "HNCSnc", {"EV": 2.0}), ("HNCSncE4.3fr", "HNCSnc", {"EV": 4.0})]
jobs += [(f"HNCSwb{T}.3fr", f"HNCSwb{T}", {}) for T in (4200, 4500, 5000, 5500, 6000, 6500, 7000, 7500, 8000)]
os.makedirs("phocus", exist_ok=True)
root = os.path.expanduser("~/Pictures/HNCS r11 hot folder")
with HotFolder(root=root) as hf:
    for raw, patches, settings in jobs:
        tif = hf.render(raw, **settings)
        key = os.path.splitext(raw)[0]
        np.save(f"phocus/{key}.npy", patch_means(tif, f"{patches}.patches.npz"))
        if key in ("HNCSnc", "HNCSwb5500"):
            shutil.copyfile(tif, f"phocus/{key}.tif")
        os.remove(tif)
        print(raw, settings, "ok", flush=True)
shutil.rmtree(root, ignore_errors=True)
