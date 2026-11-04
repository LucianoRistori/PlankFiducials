#!/usr/bin/env python3
"""
fiducial_fit.py - module and circle positions on a populated plank.

Usage:  fiducial_fit.py MEASUREMENT_FILE [--nominal FILE] [--maxrms UM]

MEASUREMENT_FILE : Label, X, Y, Z  with labels LL<m>, LR<m>, UR<m>, UL<m> for module m.
                   Header and other non-fiducial lines are ignored.
                   An optional point labelled ORG (normally first line) defines the
                   XYZ origin of the global system; otherwise the centroid of the
                   circles of all modules is used.
Nominal table    : Label, X, Y, Z (sensor frame), found in this order:
                   1. --nominal FILE
                   2. environment variable PLANK_NOMINAL
                   3. built-in default DEFAULT_NOMINAL (below)

Step 1: for each module, identify which fiducial was actually measured in each
        group (LL 1-16, LR/UR 1-18, UL 1-16) by a 2D rigid fit over all label
        combinations, then fit a 3D rigid transform nominal -> measured and
        compute the 3D positions of the 4 circles.
Step 2: global "mean" system: Z normal to the best-fit plane through all circles
        of all modules, X along the average local x axis of the modules,
        origin at ORG (if present) or at the circle centroid.
Step 3: transform circles and module poses to the mean system.

Output: the report is printed and written to <measurement>_report.txt in the
current directory; an existing report is never overwritten (_report_2.txt, ...).
"""
import sys, os, itertools, re, subprocess, datetime
import numpy as np

GROUPS = {'LL': 16, 'LR': 18, 'UR': 18, 'UL': 16}
CIRCLES = ['LLcircle', 'LRcircle', 'URcircle', 'ULcircle']
DEFAULT_NOMINAL = ('~/Dropbox/Documents/CMS/CMM_Work/Planks/PopulatedPlanks/'
                   'PS_Fiducials/PSFiducials_nominal.txt')


def read_table(path):
    """Read 'Label, X, Y, Z' lines; skip blank, comment, header and other
    non-numeric lines (e.g. ZONE3 template header text)."""
    d = {}
    for line in open(path):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        p = [s.strip() for s in line.split(',')]
        if len(p) < 4:
            continue
        try:
            d[p[0]] = np.array([float(v) for v in p[1:4]])
        except ValueError:
            continue
    return d


def rigid2d(A, B):
    ca, cb = A.mean(0), B.mean(0)
    a, b = A - ca, B - cb
    th = np.arctan2((a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0]).sum(), (a * b).sum())
    R = np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]])
    r = B - (A @ R.T + (cb - R @ ca))
    return np.sqrt((r ** 2).sum(1).mean())


def rigid3d(A, B):
    """Kabsch: B ~ R A + t"""
    ca, cb = A.mean(0), B.mean(0)
    U, S, Vt = np.linalg.svd((A - ca).T @ (B - cb))
    D = np.diag([1, 1, np.sign(np.linalg.det(Vt.T @ U.T))])
    R = Vt.T @ D @ U.T
    t = cb - R @ ca
    return R, t, B - (A @ R.T + t)


def identify(nom, B2):
    """Return (best labels, best rms, next-best rms) using 2D rigid fits."""
    res = []
    for combo in itertools.product(*[range(1, n + 1) for n in GROUPS.values()]):
        names = [f"{g}{i:02d}" for g, i in zip(GROUPS, combo)]
        A = np.array([nom[n][:2] for n in names])
        res.append((rigid2d(A, B2), names))
    res.sort(key=lambda x: x[0])
    return res[0][1], res[0][0], res[1][0]


def main():
    args = sys.argv[1:]
    maxrms = 0.030
    if '--maxrms' in args:
        i = args.index('--maxrms'); maxrms = float(args[i + 1]) / 1000; del args[i:i + 2]
    nominal = None
    if '--nominal' in args:
        i = args.index('--nominal'); nominal = args[i + 1]; del args[i:i + 2]
    if len(args) != 1:
        sys.exit("usage: fiducial_fit MEASUREMENT_FILE [--nominal FILE] [--maxrms UM]")
    if nominal:
        source = '--nominal'
    elif os.environ.get('PLANK_NOMINAL'):
        nominal, source = os.environ['PLANK_NOMINAL'], 'PLANK_NOMINAL'
    else:
        nominal, source = DEFAULT_NOMINAL, 'built-in default'
    nominal = os.path.expanduser(nominal)
    if not os.path.isfile(nominal):
        sys.exit(f"Nominal table not found: {nominal}  (from {source})\n"
                 "Give it with --nominal FILE or set PLANK_NOMINAL.")
    nom = read_table(nominal)
    meas = read_table(args[0])
    args = [nominal, os.path.abspath(args[0])]
    # report file, never overwritten: <measurement>_report.txt, _report_2.txt, ...
    base = os.path.abspath(os.path.splitext(os.path.basename(args[1]))[0] + '_report')
    name, n = base + '.txt', 1
    while os.path.exists(name):
        n += 1; name = f"{base}_{n}.txt"
    org = meas.pop('ORG', None)
    # keep only fiducial points LL<m>, LR<m>, UR<m>, UL<m>; ignore anything else
    # (e.g. circle lines from the ZONE3 circle block)
    meas = {k: v for k, v in meas.items() if re.fullmatch(r'(LL|LR|UR|UL)\d+', k)}
    mods = sorted({k[2:] for k in meas}, key=lambda s: (len(s), s))

    out = []
    pr = out.append
    pr(f"Analysis date : {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    pr(f"Code version  : fiducial_fit {code_version()}")
    pr(f"Nominal table : {args[0]}  (from {source})")
    pr(f"Measurement   : {args[1]}")
    pr(f"Report file   : {name}")
    pr(f"Quality cut   : XY fit RMS < {maxrms*1000:.1f} um\n")

    # ---------------- Step 1 ----------------
    pr("STEP 1 - per-module fits (measurement coordinates, mm)")
    M = {}
    for m in mods:
        B = np.array([meas[g + m] for g in GROUPS])
        names, rms2, next2 = identify(nom, B[:, :2])
        A = np.array([nom[n] for n in names])
        R, t, r = rigid3d(A, B)
        rms = np.sqrt((r[:, :2] ** 2).sum(1).mean())      # XY quality
        warp = np.abs(r[:, 2]).mean()                     # z non-planarity of the 4 points
        circ = {c: R @ nom[c] + t for c in CIRCLES}
        good = rms < maxrms
        M[m] = dict(names=names, R=R, t=t, r=r, rms=rms, warp=warp, circ=circ, good=good)
        pr(f"\nModule {m}:  {'OK' if good else 'FLAGGED (XY fit RMS above cut)'}")
        for g, n in zip(GROUPS, names):
            sub = '' if n == f"{g}01" else '   <- substitute'
            pr(f"   {g}{m:<3s} identified as {n}{sub}")
        pr(f"   identification: best 2D RMS {rms2*1000:.1f} um, next best {next2*1000:.0f} um")
        pr(f"   3D fit: XY RMS {rms*1000:.1f} um;  z non-planarity (mean |dz|) {warp*1000:.1f} um")
        pr(f"   residuals (dx,dy,dz) um:")
        for g, rr in zip(GROUPS, r):
            pr(f"      {g}{m:<3s} {rr[0]*1000:7.1f} {rr[1]*1000:7.1f} {rr[2]*1000:7.1f}")
        for c in CIRCLES:
            p = circ[c]; pr(f"   {c:9s} {p[0]:10.4f} {p[1]:10.4f} {p[2]:9.4f}")

    goodm = mods          # all modules enter the global system; flags are informational

    # ---------------- Step 2 ----------------
    P = np.array([M[m]['circ'][c] for m in goodm for c in CIRCLES])
    cen = P.mean(0)
    n = np.linalg.svd(P - cen)[2][2]
    if n[2] < 0:
        n = -n
    xs = np.array([M[m]['R'][:, 0] for m in goodm])
    xs = xs - np.outer(xs @ n, n)
    X = xs.mean(0); X /= np.linalg.norm(X)
    Y = np.cross(n, X)
    G = np.vstack([X, Y, n])          # rows = global axes in measurement coords
    O = org if org is not None else cen
    to_g = lambda p: G @ (p - O)

    pr("\nSTEP 2 - global mean system (in measurement coordinates)")
    pr(f"   modules used : {', '.join(goodm)}")
    pr(f"   origin       : {'ORG point' if org is not None else 'centroid of circles'}"
       f"  ({O[0]:.4f}, {O[1]:.4f}, {O[2]:.4f})")
    for lab, v in zip('XYZ', G):
        pr(f"   {lab} axis       : ({v[0]: .6f}, {v[1]: .6f}, {v[2]: .6f})")
    rz = np.arctan2(X[1], X[0]); tilt = np.arccos(n[2])
    pr(f"   rotation of X about measurement z: {rz*1000:.3f} mrad;  plane tilt: {tilt*1000:.3f} mrad")
    pr(f"   circle RMS distance from plane: {np.sqrt(((P-cen)@n)**2).mean()*1000:.1f} um")

    # ---------------- Step 3 ----------------
    pr("\nSTEP 3 - results in the global mean system (mm, angles in mrad)")
    pr("   module  status   centre X    centre Y    centre Z   rotZ     tiltX    tiltY")
    for m in mods:
        d = M[m]
        Rg = G @ d['R']                       # local axes in global frame (columns)
        c = to_g(np.mean([d['circ'][k] for k in CIRCLES], 0))
        rotz = np.arctan2(Rg[1, 0], Rg[0, 0])
        tiltx = np.arctan2(Rg[1, 2], Rg[2, 2])   # rotation about global X
        tilty = np.arctan2(-Rg[0, 2], Rg[2, 2])  # rotation about global Y
        d['g'] = {k: to_g(p) for k, p in d['circ'].items()}
        pr(f"   {m:6s}  {'OK  ' if d['good'] else 'FLAG'}  {c[0]:10.4f}  {c[1]:10.4f}  {c[2]:9.4f}"
           f"  {rotz*1000:7.3f}  {tiltx*1000:7.3f}  {tilty*1000:7.3f}")
    pr("\n   Circle positions:")
    pr("   module  circle         X          Y          Z")
    for m in mods:
        for k in CIRCLES:
            p = M[m]['g'][k]
            pr(f"   {m:6s}  {k:9s} {p[0]:10.4f} {p[1]:10.4f} {p[2]:9.4f}")

    text = "\n".join(out) + "\n"
    print(text)
    open(name, 'w').write(text)
    print(f"Report written to {name}")


def code_version():
    """git commit of this script's repository, with a warning for local changes."""
    d = os.path.dirname(os.path.realpath(__file__))
    try:
        h = subprocess.run(['git', '-C', d, 'rev-parse', '--short', 'HEAD'],
                           capture_output=True, text=True, timeout=5).stdout.strip()
        dirty = subprocess.run(['git', '-C', d, 'status', '--porcelain', '--untracked-files=no'],
                               capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception:
        return 'unknown (git not available)'
    if not h:
        return 'unknown (not a git repository)'
    return h + ('  (WARNING: uncommitted changes in the code)' if dirty else '')


if __name__ == '__main__':
    main()
