"""Shared data for the round-3 analyses: Phocus's renders of one synthetic patch grid (22^3 colours, owner's
35-100 host unless named otherwise) under different sidecar settings and factory gains.

Reads the local data/ folder (git-ignored): data/synth/r3/patch_lab.npz (Phocus Lab per patch, per
render) and data/synth/HNCSsynth03.pair.npz (Capture One probe: camera RGB per patch).
"""
import os
import sys

import numpy as np

R = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(R, "tools"))
from icc import D50, de2000, lab_to_xyz, xyz_to_lab  # noqa: E402,F401
from pairs import PROPHOTO_M  # noqa: E402
from fit import predict  # noqa: E402,F401

white = D50 / np.array([0.9642, 1.0, 0.82489])
_z = np.load(os.path.join(R, "data/synth/r3/patch_lab.npz"))
DEVN = _z["device_nominal"].astype(np.float64)
DEV = np.load(os.path.join(R, "data/synth/HNCSsynth03.pair.npz"))["dev"]
LIN = DEV ** 1.8
SAT = 1 - LIN.min(1) / np.maximum(LIN.max(1), 1e-9)
NEUT = np.ptp(DEVN, axis=1) < 1e-9
HB_M = np.array([[0.6491, 0.2989, 0.0046], [0.1886, 0.6575, 0.043], [0.1265, 0.0437, 0.7772]])  # Hasselblad RGB: rgb @ HB_M = XYZ


def lab(name):
    return _z[name].astype(np.float64)


def pp_lin(lab_):
    return lab_to_xyz(lab_) / white @ np.linalg.inv(PROPHOTO_M).T


def lab_from_pp(p):
    return xyz_to_lab((p @ PROPHOTO_M.T) * white)
