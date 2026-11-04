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
2. **Global "mean" system:** Z is normal to the best-fit plane through all
   circles, X follows the average direction of the modules' local x axes, and
   the origin is the `ORG` point if present, otherwise the centroid of all
   circles. All modules are used; flags are informational.
3. **Results:** circle positions and module poses (centre, rotation about Z,
   tilts about X and Y) in the mean system.

Output: the report is printed and written to the current directory as
`<measurement>_report.txt`. An existing report is never overwritten: a second
analysis of the same file gives `<measurement>_report_2.txt`, then `_3`, and so on.
The report header records the analysis date and time, the code version (git
commit, with a warning if the code had uncommitted changes), the nominal table
used and the quality cut, so different reports of the same input can be compared.

`example_L1Bot.txt` is a sample 4-module measurement (bottom side) including
template header lines.

---

## Data locations

Nominal table, the raw sensor measurement it comes from, plank measurements
and results are kept in Dropbox, not in this repository:

    ~/Dropbox/Documents/CMS/CMM_Work/Planks/PopulatedPlanks/
        PS_Fiducials/PSFiducials_20261102162326.txt   raw sensor measurement
        PS_Fiducials/PSFiducials_nominal.txt          nominal table
        results/                                      analysis results
