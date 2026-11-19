"""Camera neutral <-> correlated colour temperature for the X2D II, from IFD0 ColorMatrix1 (XYZ -> camera)."""
import sys
import numpy as np
import tifffile

def cm_of(path):
    with tifffile.TiffFile(path) as t:
        v = t.pages[0].tags['ColorMatrix1'].value
    return np.array([v[2*i] / v[2*i+1] for i in range(9)]).reshape(3, 3)

def neutral_of(path):
    with tifffile.TiffFile(path) as t:
        n = t.pages[0].tags['AsShotNeutral'].value
    return np.array([n[0]/n[1], n[2]/n[3], n[4]/n[5]])

def daylight_xy(T):
    if T <= 7000:
        x = -4.6070e9/T**3 + 2.9678e6/T**2 + 0.09911e3/T + 0.244063
    else:
        x = -2.0064e9/T**3 + 1.9018e6/T**2 + 0.24748e3/T + 0.237040
    return x, -3.000*x*x + 2.870*x - 0.275

def neutral_for(cm, T):
    x, y = daylight_xy(T)
    cam = cm @ np.array([x/y, 1.0, (1-x-y)/y])
    return cam / cam[1]

def cct_of(cm, neutral):
    XYZ = np.linalg.solve(cm, neutral)
    x, y = XYZ[0]/XYZ.sum(), XYZ[1]/XYZ.sum()
    n = (x - 0.3320) / (0.1858 - y)
    return 449*n**3 + 3525*n**2 + 6823.3*n + 5520.33  # McCamy

if __name__ == '__main__':
    for p in sys.argv[1:]:
        try:
            print(f"{cct_of(cm_of(p), neutral_of(p)):7.0f} K  {p}")
        except Exception as e:
            print(f"   error {p}: {e}")
