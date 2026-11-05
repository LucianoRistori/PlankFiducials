# PlankFiducials

**Author:** Luciano Ristori
**Date:** November 2026

---

## Overview

Python tools to analyse OGP CMM (ZONE3) measurements of fiducials on silicon
sensor modules mounted on a populated plank.

Each module is measured at 4 fiducials, one near each corner (LL, LR, UR, UL).
The default fiducials are the outermost ones (LL01, LR01, UR01, UL01), but any
fiducial along the same row may be used instead when the default one is hidden,
for example by encapsulant. The analysis recognises substitutes automatically.

The workflow has two steps:

1. `make_nominal_table.py` builds, once, the table of nominal positions of all
   fiducials and corner circles on a sensor, from a CMM measurement of one sensor.
2. `fiducial_fit.py` analyses each plank measurement using that table.

Requires Python 3 with numpy.

---

## Installation

Clone the repository and link the two scripts into `~/bin` (which must be on
the shell's search path), so they can be run from any directory:

    git clone https://github.com/LucianoRistori/PlankFiducials.git ~/code/CMM/PlankFiducials
    chmod +x ~/code/CMM/PlankFiducials/fiducial_fit.py ~/code/CMM/PlankFiducials/make_nominal_table.py
    ln -s ~/code/CMM/PlankFiducials/fiducial_fit.py ~/bin/fiducial_fit
    ln -s ~/code/CMM/PlankFiducials/make_nominal_table.py ~/bin/make_nominal_table

The links point to the files in the repository, so any change (or `git pull`)
takes effect immediately; nothing needs to be reinstalled. Check with
`which fiducial_fit`. If numpy is missing: `pip3 install numpy`.

Once installed, the commands below can be called without `python3` and without
the `.py` extension, e.g. `fiducial_fit MEASUREMENT_FILE`.

---

## make_nominal_table.py

    python3 make_nominal_table.py RAW_SENSOR_FILE [OUTPUT_FILE] [--cut UM]

Input: a CMM measurement of all fiducials of one sensor (`Label, X, Y, Z` per
line): the 4 corner circles (LLcircle, LRcircle, URcircle, ULcircle) and the
fiducial rows LL01-LL16, LR01-LR18, UR01-UR18, UL01-UL16, in a sensor frame with
LLcircle at the origin and LRcircle on the x axis.

What it does:

- Fits an exact 1.000 mm grid to the fiducials (the pattern is lithographic, so
  the grid is exact). Outliers (default cut 4 um) are fiducials of a slightly
  different shape; they are excluded from the fit.
- Idealises the circles to an exact rectangle (mean measured width and height).
- Centres the fiducial grid on the circle rectangle, with rows exactly parallel
  to x and y.
- Outliers keep their own measured offset from the grid, so the table describes
  what the CMM actually sees on them.
- Z = 0 for all points.

Output: `Label, X, Y, Z` per line (default name `PSFiducials_nominal.txt`).

---

## fiducial_fit.py

    fiducial_fit MEASUREMENT_FILE [--nominal FILE] [--maxrms UM]

Example, from any directory:

    fiducial_fit Layer1TopFiducials_20261028163846.txt

### Which nominal table is used

The nominal table is not given on the command line in normal use. The program
looks for it in this order and uses the first one that applies:

1. `--nominal FILE` on the command line, if given (for an occasional
   different table).
2. The environment variable `PLANK_NOMINAL`, if it is set, e.g. in
   `~/.bash_profile`:

        export PLANK_NOMINAL=~/Dropbox/Documents/CMS/CMM_Work/Planks/PopulatedPlanks/PS_Fiducials/PSFiducials_nominal.txt

3. The built-in default (constant `DEFAULT_NOMINAL` in `fiducial_fit.py`):
   `~/Dropbox/Documents/CMS/CMM_Work/Planks/PopulatedPlanks/PS_Fiducials/PSFiducials_nominal.txt`

The first line of every report states which table was used and where it came
from (`--nominal`, `PLANK_NOMINAL` or `built-in default`). If the file does not
exist, the program stops with an error saying which path it tried.

### Input and options

The `.txt` extension of the measurement file may be omitted.

Input: a ZONE3 fiducial file with lines `Name,X,Y,Z`, names LL1, LR1, UR1, UL1,
LL2, ... (corner + module number). Header text and non-fiducial lines (for
example circles) are ignored. An optional point named `ORG` defines the origin
of the global coordinate system.

What it does:

1. **Per module:** identifies which fiducial was actually measured in each
   corner (searching every position in the row), fits a 3D rigid transform from
   the nominal table to the 4 measured points, and computes the 3D positions of
   the 4 corner circles. A module is flagged when its XY fit RMS exceeds the cut
   (default 30 um); the z non-planarity of the 4 points is reported separately.
2. **Global "mean" system:** its axes are the mean orientation of the modules
   (X, Y, Z = average local x, y and normal of the modules, made exactly
   orthogonal); the origin is the `ORG` point if present, otherwise the
   centroid of all circles. All modules are used; flags are informational.
   See "The global reference system" below for the definition and the reasons.
3. **Results:** circle positions and module poses (centre, rotation about Z,
   tilts about X and Y) in the mean system.
4. **Superposition by X translations:** each module is shifted along X only,
   so that the circles of all modules match as well as possible (least
   squares). The best shift of a module is simply the mean X of its 4 circles;
   the report gives these translations, the step between consecutive modules,
   the reference rectangle (average of the shifted circles of all modules) and,
   for every circle, the residual (dX, dY, dZ) from the reference, with RMS
   values per module and for the whole plank, and a summary table with the
   MIN, MAX and RMS of dX, dY and dZ over all circles. On a perfect plank all these
   residuals are zero, so they are the raw material for figures of merit.

Output: the report is printed and written to the current directory as
`<measurement>_report.txt`. An existing report is never overwritten: a second
analysis of the same file gives `<measurement>_report_2.txt`, then `_3`, and so on.
The report header records the analysis date and time, the code version (git
commit, with a warning if the code had uncommitted changes), the full paths of
the nominal table, the measurement file and the report file itself, and the
quality cut, so different reports of the same input can be compared.

`example_L1Bot.txt` is a sample 4-module measurement (bottom side) including
template header lines.

---

## The global reference system

### What it is for

The results are meant to rank the mechanical quality of each plank. The idea
is simple: on a perfectly built plank, measured without errors, the 4 corner
circles of every module would form exactly the same rectangle, and the
rectangles of different modules would differ only by a shift along X. Any
deviation from that picture, after the X shifts, is a construction (or
measurement) error, and figures of merit can be built from it.

For this to work, the global reference system must be chosen so that it does
not absorb construction errors into its own definition.

### Definition used

- **Orientation.** Each module has its own orientation, given by the 3D fit of
  its fiducials: its local x axis (along the fiducial rows), local y axis and
  normal. The global axes are the **mean orientation of the modules**: the
  rotation that is closest, in the least-squares sense, to all module
  rotations (the orthogonal part of their sum). In practice global X, Y and Z
  are the average local x, y and normal of the modules, made exactly
  perpendicular to each other.
- **Origin.** The `ORG` point if it is in the measurement file, otherwise the
  centroid of all circles of all modules. The origin only shifts all
  coordinates together and does not change any relative quantity.

The module centres play no part in defining the orientation.

### Alternatives considered

1. **Axes from the module centres.** X along the best-fit line through the
   module centres, Z normal to the best-fit plane through all circles. (The
   first version of the program used the plane through all circles for Z.)
2. **Axes from external references on the plank,** for example the CMM
   alignment or dedicated reference points. This would require reference
   features that are not yet measured, and would mix the quality of the
   module placement with the quality of those references.

### Why the module orientations

Consider a plank where every module is rotated by the same small angle about
Z with respect to the line through the module centres: a "staircase".

- With the **module-based axes** (our choice), global X follows the modules.
  The modules come out unrotated, but their centres step in Y by about
  angle x pitch from one module to the next. After the X shifts the circle
  rectangles do **not** superimpose: the defect is visible.
- With **axes from the centres**, global X follows the line of centres. Every
  module comes out rotated by the same angle, and after the X shifts the
  rotated rectangles superimpose perfectly: the defect is **invisible**.

The same holds for a staircase in height (every module tilted by the same
angle about Y, centres at the same height). This is why Z is also taken from
the modules (their mean normal) and not from a plane fitted through all
circles: such a plane follows the module centres and would hide the tilt.

In short, a reference system built from the module centres absorbs any error
that is common to all modules; a system built from the mean module orientation
turns it into residuals, which is what a figure of merit needs.

### Things to keep in mind when reading the report

- The rotation and tilts of each module (rotZ, tiltX, tiltY) are measured with
  respect to the **average module**, so they average to about zero over the
  plank. A rotation or tilt common to all modules appears instead as a steady
  trend of the centre Y or Z with X.
- Module angles are measured over short distances (about 35 mm between the
  fiducials along x, about 98 mm along y). An angle error is multiplied by the
  distance from the centre of the plank, so measurement errors are amplified
  towards the ends of the plank, by a factor of order a few. Averaging over the
  modules reduces this.
- All modules, including flagged ones, enter the mean orientation. A badly
  measured module can therefore tilt the whole system; the report gives the
  RMS angle of the modules from the mean orientation as a check.
- Because each module gets its own X shift, errors in the spacing of the
  modules along the plank are not tested by this comparison. If the spacing
  matters, it needs a separate figure of merit (or fixed shifts equal to the
  design pitch).

---

## Data locations

Nominal table, the raw sensor measurement it comes from, plank measurements
and results are kept in Dropbox, not in this repository:

    ~/Dropbox/Documents/CMS/CMM_Work/Planks/PopulatedPlanks/
        PS_Fiducials/PSFiducials_20261102162326.txt   raw sensor measurement
        PS_Fiducials/PSFiducials_nominal.txt          nominal table
        results/                                      analysis results
