#!/usr/bin/env python3
"""
make_nominal_table.py - build the table of NOMINAL fiducial positions on a sensor.

Usage:  python3 make_nominal_table.py RAW_SENSOR_FILE [OUTPUT_FILE] [--cut UM]

RAW_SENSOR_FILE : CMM measurement of ALL fiducials of one sensor, lines
                  "Label, X, Y, Z[, extra]" with labels
                  LLcircle, LRcircle, URcircle, ULcircle  (corner circles)
                  LL01-LL16, LR01-LR18, UR01-UR18, UL01-UL16 (fiducial rows)
                  in a sensor-local frame (LLcircle at origin, LRcircle on x axis).
OUTPUT_FILE     : default PSFiducials_nominal.txt; lines "Label, X, Y, Z".

Method
  1. Fit an exact 1.000 mm grid to the fiducials: free parameters are the x of
     LL16/UL16 (left groups), the x of LR18/UR18 (right groups), the y of the
     bottom row, the y of the top row, and a small common rotation (check only).
     Outliers are rejected iteratively (|dx| or |dy| > cut, default 4 um) and
     re-admitted if they fit; the fiducial pattern is lithographic, so the grid
     is exact and outliers are fiducials of a slightly different shape.
  2. Idealise the circles: an exact rectangle whose width and height are the
     means of the measured ones, LLcircle at (0,0), sides parallel to x and y.
  3. Place the fiducial grid (rotation set to zero) centred on the circle
     rectangle, keeping the fitted left-right gap and row spacing.
  4. Outliers keep their own measured offset from the fitted grid, so the table
     describes what the CMM actually sees on them.
  Z is 0 for all points (flat sensor surface).
"""
import sys
import numpy as np

LEFT = {'LL': 16, 'UL': 16}    # numbered from the corner towards the centre
RIGHT = {'LR': 18, 'UR': 18}


def read(path):
    d = {}
    for line in open(path):
        p = [s.strip() for s in line.split(',')]
        if len(p) < 4:
            continue
        try:
            d[p[0]] = np.array([float(v) for v in p[1:4]])
        except ValueError:
            continue
    return d, [k for k in d]


def kpos(k):
    i = int(k[2:]); left = k[:2] in LEFT
    return (-(LEFT[k[:2]] - i) if left else (RIGHT[k[:2]] - i)), left, k[0] == 'L'


def fit(f, keys):
    A, b = [], []
    for k in keys:
        n, left, low = kpos(k); x, y = f[k][:2]
        A.append([left, not left, 0, 0, -y]); b.append(x - n)
        A.append([0, 0, low, not low, x]); b.append(y)
    s, *_ = np.linalg.lstsq(np.array(A, float), np.array(b), rcond=None)
    return s          # xL, xR, yB, yT, theta


def resid(s, f, k):
    n, left, low = kpos(k); x, y = f[k][:2]
    return (x - ((s[0] if left else s[1]) + n - s[4] * y),
            y - ((s[2] if low else s[3]) + s[4] * x))


def main():
    args = sys.argv[1:]
    cut = 0.004
    if '--cut' in args:
        i = args.index('--cut'); cut = float(args[i + 1]) / 1000; del args[i:i + 2]
    raw, order = read(args[0])
    out = args[1] if len(args) > 1 else 'PSFiducials_nominal.txt'
    f = {k: v for k, v in raw.items() if 'circle' not in k}

    keys = list(f)
    for _ in range(10):
        s = fit(f, keys)
        new = [k for k in f if max(map(abs, resid(s, f, k))) < cut]
        if set(new) == set(keys):
            break
        keys = new
    outl = sorted(set(f) - set(keys))
    s = fit(f, keys)

    c = {k: raw[k] for k in ('LLcircle', 'LRcircle', 'URcircle', 'ULcircle')}
    W = ((c['LRcircle'][0] - c['LLcircle'][0]) + (c['URcircle'][0] - c['ULcircle'][0])) / 2
    H = ((c['ULcircle'][1] - c['LLcircle'][1]) + (c['URcircle'][1] - c['LRcircle'][1])) / 2
    cx, cy = W / 2, H / 2
    gap, dy = s[1] - s[0], s[3] - s[2]
    xL, xR, yB, yT = cx - gap / 2, cx + gap / 2, cy - dy / 2, cy + dy / 2

    nom = {'LLcircle': (0, 0), 'LRcircle': (W, 0), 'URcircle': (W, H), 'ULcircle': (0, H)}
    for k in f:
        n, left, low = kpos(k)
        x = (xL if left else xR) + n; y = yB if low else yT
        if k in outl:
            ex, ey = resid(s, f, k); x += ex; y += ey
        nom[k] = (x, y)
    with open(out, 'w') as fo:
        for k in order:
            fo.write(f"{k}, {nom[k][0]:9.4f}, {nom[k][1]:9.4f}, {0:8.4f}\n")

    rms = 1e3 * np.sqrt(np.mean([np.hypot(*resid(s, f, k)) ** 2 for k in keys]))
    print(f"Grid fit: {len(keys)} fiducials used, rms {rms:.2f} um, "
          f"rotation {s[4]*1e6:.1f} urad (set to 0 in table)")
    print(f"Circle rectangle {W:.4f} x {H:.4f} mm; left-right gap {gap:.4f} mm; "
          f"row spacing {dy:.4f} mm")
    print(f"Outliers (own offsets kept): {', '.join(outl)}")
    for k in outl:
        ex, ey = resid(s, f, k); print(f"   {k}: dx {ex*1e3:6.1f} um, dy {ey*1e3:6.1f} um")
    print(f"Written: {out}")


if __name__ == '__main__':
    main()
