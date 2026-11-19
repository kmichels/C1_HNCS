import colorsys, sys
import numpy as np
neutral = np.array([0.36817978, 1.0, 0.58943733])  # host HNCShl.3fr As Shot
levels = sorted(set(np.round(np.concatenate([2.0 ** np.arange(-4, 0.01, 0.25), [0.76, 0.80, 0.88, 0.92, 0.96, 0.99]]), 4)))
cols = [(0, 0.0)] + [(h, s) for s in (0.3, 0.6, 0.9) for h in range(0, 360, 30)]
dev, meta = [], []
for h, s in cols:
    c = np.array(colorsys.hsv_to_rgb(h / 360, s, 1.0))
    for r in levels:
        dev.append(c * r / np.max(c * neutral)); meta.append((h, s, r))
np.save('ladder_device.npy', np.array(dev)); np.save('ladder_meta.npy', np.array(meta))
print(len(dev), 'patches;', len(levels), 'levels:', levels)
