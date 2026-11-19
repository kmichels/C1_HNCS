"""Mean 16-bit RGB (0-1) per patch of a 50% export, centre half of each patch."""
import numpy as np
import tifffile

def patch_means(tif, patches_npz):
    z = np.load(patches_npz)
    pos, P = z["pos"], int(z["patch"])
    img = tifffile.imread(tif)[..., :3].astype(np.float64) / 65535
    s = P // 2; m = s // 4
    return np.array([img[y // 2 + m: y // 2 + s - m, x // 2 + m: x // 2 + s - m].reshape(-1, 3).mean(0) for y, x in pos])
