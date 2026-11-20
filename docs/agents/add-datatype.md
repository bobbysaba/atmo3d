# Playbook: an AI agent adds a data type

This page is written for a coding agent (Claude Code, Codex, Copilot and the like), so a
person can hand it the job of teaching atmo3d a new kind of output. The person says:

> Follow docs/agents/add-datatype.md in the atmo3d repository for the files in
> `<path>`; name the data type `<name>`.

and the agent builds the package and its tests the way the core needs them, then reports
what it assumed. People can read it too: it is
[Writing a data type](../datatypes.md) as a procedure.

**Agent: follow the steps in order. Do not skip the stops. Where this page and the code
disagree, the code and [the contract](../datatypes.md) win: say so in your report.**

## 0. Rules for the whole job

- **Change nothing in `packages/core`.** If the data type seems to need a core change,
  stop and report it (step 8); do not make it.
- **Read data only as the steps say**: headers, a few values. Never load a whole file
  into memory, never walk a big directory tree recursively, never copy real values into
  the repository.
- **On a shared cluster, follow the site's rules** (the user's own instructions may say
  more): no recursive `find`, `du`, `ls -R` or `grep -r` above the data folder; list the
  data folder itself, one level deep. Anything heavy (a real-data test of a large grid, a
  full test suite) goes on a compute node: **give the user the exact command and wait**;
  never submit a batch job yourself.
- Work on a branch, in small commits; push only if the user asks.
- Use the tools this page names (`tools/new_datatype.py`, `atmo3d.testing.check_datatype`)
  rather than writing their equivalent.

## 1. Ask for the inputs

Ask the user for anything they did not give, in one message:

1. **The data path**: a folder holding one run (one experiment, one volume scan
   sequence, ...).
2. **The name**: a short lowercase key (`mpas`, `wrf_les`); it becomes `atmo3d_<name>`.
3. **Contribute or own package**: into this repository (`packages/<name>`), or a package
   of their own outside it (`--out DIR`: which folder?).
4. **What matters most to them**: which fields and views (maps, cross-sections,
   soundings, 3D, series, tracking), so you know which roles to get right first.

## 2. Inspect, read-only and bounded

Look at the data, not at more than you need:

- `ls` the data folder (one level). Note the file names, how many there are, any
  namelist or metadata file next to them.
- `ncdump -h` on **one** file, and on a second only if the names suggest the files
  differ (another time, another kind). For a format other than netCDF, its own header
  tool. Never `ncdump` without `-h`.
- From the headers, write down:
    - the dimensions and their sizes; which is time, which are x, y, z;
    - how time is written (a coordinate with `units = "seconds since ..."`, a string, the
      file name) and **how many times one file holds**;
    - the coordinate variables, their units, and whether x, y are on a map projection
      (lat/lon 2D arrays, a `grid_mapping`, projection attributes);
    - whether heights are the same in every column (a 1D `z`) or vary (terrain
      following, pressure or sigma levels, a 3D height field);
    - staggered dimensions (one point longer than another along the same axis);
    - every field's dimensions, units and `_FillValue` / `missing_value`;
    - global attributes that matter (model name, version, grid spacing, start time).
- If you need a value to settle a question (are the levels evenly spaced? which way does
  y run?), read only that coordinate variable (`ncdump -v z <file> | tail -n 5` prints
  the header, then z's values), never a 3D field.

Keep each finding with the header line it came from: step 4 writes them to `NOTES.md` in
the new package, and they are the evidence for the report.

## 3. Classify

Decide, and write the reasons in `NOTES.md`:

- **Gridded** (`core.run.Run`): a regular grid in x and y. Closest examples: the worked
  example (`packages/example`, named dims, several times per file), `atmo3d_cm1` (one
  time per file), `atmo3d_wofs` (map projection, terrain-following levels: `geo`,
  `terrain`, `heights()`).
- **Not gridded** (`core.run.Source` plus the hooks: `map_window`, `map_plane`,
  `level_text`, and with `sampled` the section and 3D hooks): radar volumes, points,
  unstructured meshes. Closest example: `atmo3d_radar`. An unstructured mesh (MPAS) is a
  `Source`, or a `Run` on a grid it is remapped to: **stop and ask** which the user wants
  before writing a reader.
- **The capabilities** it can claim (`core.capabilities.CAPS`): `soundings` when it has
  theta (or what makes it), pressure, vapour and both winds; `tracking` when it has w;
  `parcels` with `traced_parcels = True` when it has the 3D winds and no parcel output.
- **The roles** (`core.catalog.ROLES`) each field plays, and whether its units match the
  role's (winds m/s, theta K, pressure Pa, mixing ratios kg/kg, reflectivity dBZ).

## 4. Build

1. Start from the scaffold, in the repository's root, in the atmo3d environment:

        python tools/new_datatype.py <name> --label "<Name in lists>"            # contribute
        python tools/new_datatype.py <name> --label "<Name>" --out <folder>      # own package

   Run its test before changing anything; it must pass (it is the example renamed):
   `pytest tests/<name>` (own package: `pytest` in its folder).
2. Create `NOTES.md` in the package with what steps 2 and 3 found.
3. Adapt the copy, file by file, following the comments marked **REQUIRED** and
   optional in each (they describe the example's layout; rewrite them for yours as you
   go, so the comments describe the new files):
    - `model.py`: `PATTERN` (the run's file names), `TIME`; keep `looks` name-only and
      `count` cheap.
    - `run.py`: `AXES`, the coordinate names and `TO_KM`, `CONVERT` (each role in its
      role's units); then `__init__`, `_info`, `TimeView` where the layout differs (time
      from file names, one time per file: drop `source()` and let the core read
      `files[t]`; fields split over files: a view that joins them, as `atmo3d_wofs`'s
      `WRFView`). `run.times` is seconds since the first time, strictly increasing;
      `time_label` shows the real time when the files have one.
    - `catalog.py`: `ROLES` for every role the files have; `NATIVES` display defaults
      for the fields the user named in step 1, and the main ones; `other` / `hidden` for
      the internals.
    - `synthetic.py`: **the real files' layout** (the same dimension and variable names,
      units, attributes, fill values, staggering, times per file, quirks), at a tiny size
      (a few points per axis, two or three times), with values from formulas. No value
      copied from the real files.
4. Write the tests in `tests/<name>/test_<name>.py` (the scaffold wrote the contract check and a
   `-m real` test): add tests of the reads against the synthetic formulas, one for each
   thing the reader does (grid in km, times, each unit change, staggering, fill values,
   fields only some times have). `tests/example/test_example.py` is the model.

## 5. Check

- `pytest tests/<name>`: everything passes on the synthetic run.
- The real run: `check_datatype` on the user's path. On a small grid you may run
  `ATMO3D_<NAME>_ROOT=<path> pytest -m real tests/<name>` directly; on a large one
  (more than about 10⁷ points per 3D field), or on a login node of a shared cluster,
  **give the user that command to run on a compute node and wait for the result**.
- Read the check's report, warnings included: roles the catalog names that the run lacks,
  a folder auto-detect gives to another type, capabilities offered without inputs.
- `git diff --stat master -- packages/core` is empty.

**Done** means: `check_datatype` passes on the synthetic run and on the real path, the
package's tests pass, and nothing in `packages/core` changed.

## 6. Contribute or publish

- **Contribute**: do the by-hand steps the scaffold printed (`.github/workflows/tests.yml`,
  `environment.yml`, the root `pyproject.toml`, `.github/CODEOWNERS`), as
  [Contributing it](../datatypes.md#contributing-it-or-publishing-it) lists. Fill in the
  pull request template (`.github/PULL_REQUEST_TEMPLATE.md`) as the report's summary.
- **Own package**: nothing more; tell the user `pip install -e <folder>` in the atmo3d
  environment.

## 7. Report

End with a report to the user (and in the pull request description):

- what the data type reads, and which existing type it is closest to;
- **every assumption, with the header line it came from**, so a reviewer can check each:
  units, which dimension is which, staggering, the vertical coordinate, time, role
  mapping, fill values;
- what works (capabilities, roles mapped) and what does not yet;
- the real-data check: who ran it, on which path, the report's warnings;
- anything you stopped on and what the user decided.

## 8. Stop and ask

Stop, say what you found, and ask the user, when:

- **units** are missing, ambiguous or not the role's (is `p` in Pa or hPa? `q` a mixing
  ratio or specific humidity?);
- the **staggering** or which dimension is which is not clear from the names and sizes;
- the **vertical coordinate** is not heights above ground (pressure, sigma, terrain
  following, height above sea level);
- a field could play a **role** in more than one way (grid-relative or earth-relative
  winds; temperature where theta is needed: deriving theta needs pressure and a choice of
  constants);
- the data has **no grid** or an unstructured one (step 3);
- anything seems to need a **core change**: describe what and why, and do not make it;
- before **any batch job** or heavy run: give the command, do not run it.
