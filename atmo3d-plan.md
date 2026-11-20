# atmo3d: rebuild plan (DRAFT for Bobby's revision)

Status: draft. Not yet handed to an agent. Bobby revises, then gives it to a Claude Code
agent on the HPC.

## 1. Goal

Turn `cm1view` (a CM1 viewer) into **atmo3d**: one app that opens any 3D atmospheric
data type, with a data-agnostic core (plotting, 3D rendering, cross-sections, caching,
the figure editor) and one package per data type. Data types at v1.0.0:

- **CM1** (existing)
- **WoFS** (existing; becomes native WRF names, no more renaming to CM1 names)
- **Bistatic radar** (new; native polar geometry)

Adding a future data type should mean adding a folder under `packages/` and registering
it, not editing the core.

## 2. Decisions already made

| Topic | Decision |
|---|---|
| Name | `atmo3d` (free on PyPI; no GitHub user/org holds it) |
| Repo | Rename the existing GitHub repo in place (keeps history, issues, redirects). No new repo, no deleting the old one |
| Structure | One monorepo: `packages/core`, `packages/cm1`, `packages/wofs`, `packages/radar` |
| App shape | One app that opens any data type, detected from the folder (as today) |
| Panels | Data-type-specific panels live in that data type's package; the core offers a registration API |
| Field names | No renaming to CM1 names. Each data type has its own field catalog (names, labels, units, colormaps, defaults, wind components) |
| Radar geometry | Native polar is the source of truth. Every non-polar view (cross-section, column, constant-height map, 3D) goes through a per-data-type **sampler**. Regridding is optional, off by default, and cached |
| Regrid | Settings live in the settings panel. Default is "none"; the first time a user regrids, they must confirm settings. Views show a "regridded: method, spacing" label |
| Saved files | Keep an upgrade path so old sessions and figures still load |
| Versions | Last cm1view release is 0.6.0 (tag `v0.6.0`). atmo3d is v1.0.0 when this plan is complete |
| Tests | Bobby runs the test suites. The agent says exactly which command to run and what to look for |
| Out of scope | Shipped demo data, radar demo cutouts, polished radar docs, publishing. These come after v1.0.0 work is done |

## 3. Ground rules for the agent

- Work in small commits, one logical step each. `master` must stay runnable after each
  phase; do the work on a branch and tell Bobby when a phase is ready to merge.
- Do not run the full test suite or heavy jobs yourself. Give Bobby the command (for
  example `pytest tests/test_images.py`) and what a pass looks like. Keep tool output small
  (no big dumps) to save tokens.
- Do not change behavior for CM1 or WoFS unless the phase says to. Image baselines in
  `tests/baseline/` must stay unchanged unless a phase says they will move.
- Stop at every **CHECKPOINT** and wait for Bobby.
- Radar data lives on the HPC at: `/glade/derecho/scratch/rasaba/20260403_20260404_results`. Never commit it.

## 4. Facts about the current code (found in the survey)

- Python 3.11+, Panel/Bokeh app. About 27k lines of code: `core/` 11k, `viewer/` 10.5k,
  `figures/` 4.5k, `pdecomp/` 1k; tests 15.5k.
- `core/models.py` already registers data types (`CM1`, `WoFS`); `core/run.py` has a
  model-neutral `Run` base class with capability flags (`terrain`, `storm_relative`,
  `traced_parcels`, `geo`). WoFS was added in steps W0 to W7 (see git log); use it as the
  pattern.
- `Run` assumes a regular grid: `xh`, `yh` (km), `z`, `zf`. Radar data does not fit this.
- About 100 places in `viewer/` and `figures/` hardcode CM1 field names (`th`, `prs`,
  `uinterp`, `vinterp`, `winterp`, `dbz`, `cref`, `SOUNDING_VARS` in `viewer/ui.py`, iso
  defaults in `viewer/layout.py`, and so on). WoFS renames WRF fields to these on read
  (`MAPPED` in `core/wofs.py`).
- CM1-specific code: `core/thermo.py`, `core/sounding_plot.py`, `core/parcels.py`,
  `core/trajcalc.py`, `core/track.py`, `pdecomp/`, and the viewer panels that use them
  (`viewer/sounding.py`, `viewer/parcels.py`, `viewer/tracking.py`).
- Tests use synthetic runs (`tests/synthetic.py`) and image baselines.

## 5. The radar data (one file inspected; verify the rest in Phase 4)

Folder: `20260403_20260404_results`, 19 CfRadial netCDF files named
`combined_radar_object_advcor_<n>_<YYYYMMDD_HHMMSS>.nc`, about 250 to 285 MB each, about
10 min apart (01:06 to 03:00 UTC on 2026-04-04). One file is one volume.

- Radar: KTLX, 35.3334 N, 97.2778 W, altitude 389 m. VCP 212. Original container: NEXRAD
  Level II.
- Dimensions: `time` (one per **ray**, 11160; about 0.027 s apart), `range` (1832 gates,
  2125 m to 459875 m, 250 m spacing), `sweep` (14: fixed angles 0.5, 0.9, 1.3, 1.8, 2.4,
  3.1, 4.0, 5.1, 6.4, 8.0, 10.0, 12.5, 15.6, 19.5 degrees).
- Per-ray: `azimuth`, `elevation`, `nyquist_velocity`, `unambiguous_range`. Per-sweep:
  `sweep_number`, `fixed_angle`, `sweep_start_ray_index`, `sweep_end_ray_index`,
  `sweep_mode`.
- Fields on (`time`, `range`): `reflectivity`, `velocity`, `differential_reflectivity`,
  `spectrum_width`, `cross_correlation_ratio`, `differential_phase`,
  `clutter_filter_power_removed`; bistatic: `beta_nwc`, `beta_cutoff_nwc`,
  `bistatic_velocity_nwc`, `bistatic_velocity_unsmoothed_nwc`,
  `original_bistatic_velocity_nwc`, `receiver_ncp_nwc`, `receiver_rcp_nwc`,
  `receiver_bistatic_velocity_mask_nwc`, `receiver_qc_reason_flag_nwc`; retrievals: `u`,
  `v`, `w_direct`, `w`, `doppler_degree`.
- Retrieved `u`, `v` are sparse (valid only where bistatic coverage exists);
  `doppler_degree` is 2 there. In the file inspected, `w` and `w_direct` were all zeros.
- Receiver locations were not found in the file. Ask Bobby.
- Which fields matter and how they display is decided in the **variable audit**
  (Phase 6, with Bobby); do not decide it alone.

## 6. Phases

### Phase 0: Baseline and inventory (no behavior change)

1. Bobby runs the full suite on the HPC and records the result (pass/fail counts).
2. Agent lists every hardcoded CM1 field name in `viewer/` and `figures/` (file, line,
   what it does) in `docs-dev/hardcoded-names.md` (not published docs). Group by purpose:
   defaults, wind components, sounding inputs, iso defaults, and so on. Create
   `docs-dev/` (it does not exist yet) and keep it out of the mkdocs build.
3. Agent also lists every **model gate**: each place that branches on the data type
   (for example `run.model == "cm1"` in `pdecomp/__init__.py`, `model ==` / `.model in`
   checks, and the capability flags on `Run`), with file, line and what it gates. Phase 3
   uses this list to check that none are left.
4. Agent lists the tests that cover the CM1 and WoFS paths and flags thin spots;
   adds characterization tests only where a later phase would otherwise go unprotected.

Done when: suite result recorded, inventory file reviewed by Bobby.
**CHECKPOINT** after this phase.

### Phase 1: Rename to atmo3d (one mechanical commit)

Code (agent):
- Folder `cm1view/` to `atmo3d/`; every `import cm1view` / `from cm1view` / `from .. import`
  path that names it; `pyproject.toml` (project name, `[project.scripts]` entry, setuptools
  `include`, package-data key, URLs); CLI command `atmo3d`; `cm1view.sh` to `atmo3d.sh`
  and its text.
- The 17 `CM1VIEW_*` environment variables to `ATMO3D_*`: `ALLOW_WRITES_TO_OUTPUT`,
  `CACHE_DIR`, `CACHE_GB`, `CONFIG`, `EXPORTS_DIR`, `IMAGE_TOL`, `PDECOMP`,
  `PDECOMP_SCRIPT`, `RUNS_ROOT`, `SETTLE_SECONDS`, `SHOTS`, `TEST_DATA`, `TEST_RUN`,
  `TRACK_MOTION_WINDOW`, `TRAJ_MAX_INTERVAL`, `WOFS_MEMBER`, `WOFS_ROOT`.
- Home paths in `config.py` and the like: `~/.config/cm1view/config.toml` to
  `~/.config/atmo3d/config.toml`, `~/.cache/cm1view` to `~/.cache/atmo3d`, the
  `recent.json` location, `cm1view-demo-$USER` temp folders. No fallback to the old paths
  (sole user).
- Marker files `.cm1view-demo` and `.cm1view-demo-wofs`; saved-file attribute names such
  as `cm1view_name` and `cm1view_set` (readers accept the old and new names; writers use
  the new).
- `environment.yml` (name and comments), `mkdocs.yml` (site name, `site_url`, `repo_url`,
  `repo_name`, nav label), `.github/workflows/docs.yml`, `README.md`, `docs/`, tests, test
  baselines only if they embed the name.
- Use `grep -rIn cm1view` to confirm nothing is left (excluding `.git` and git history).
  About 814 occurrences in 129 files at the last check (excluding `.git` and
  `cm1view.egg-info`; also skip `.claude/` and `__pycache__`). Afterward run
  `pip install -e .` again so the package metadata and entry point use the new name. Distinguish uses that are really the
  model name "CM1" (keep) from the project name (change).

Bobby does himself (outside the agent): rename the GitHub repo, `git remote set-url origin`
on every clone including the HPC, rename local folders, rename the conda env, move
`~/.config/cm1view` and `~/.cache/cm1view`, update GitHub Pages and any links.

Done when: `pytest` result matches Phase 0; `atmo3d --demo` starts.
**CHECKPOINT**.

### Phase 2: Per-data-type field catalogs, no CM1 names in the core

1. Define the catalog interface (field names, labels, units, display defaults, wind
   components, default fill/contour/iso fields, field groups). `core/fields.py` is the
   current implementation; the CM1 catalog moves out of it as data, derived-field machinery
   stays in the core.
2. The viewer and figures ask the run's data type for defaults and wind components instead
   of using names. Work from the Phase 0 inventory; one commit per group.
3. WoFS uses native WRF names. Remove `MAPPED` renaming. Derived fields that need
   `th`/`prs`/`qv` get per-data-type definitions.
4. **Upgrade path** for saved files: bump the spec/session version; old CM1 files load
   unchanged (CM1 names do not change); old WoFS sessions and figures map old names to
   WRF names through an explicit table; add tests with fixtures for each.

Done when: CM1 images are pixel-identical to baselines; WoFS tests updated and passing;
old saved files load.
**CHECKPOINT**.

### Phase 2b: Field and equation audit (interactive, with Bobby; do not skip)

Starts only after the Phase 2 CHECKPOINT is passed. Bobby confirms every decision; the
agent prepares the lists and does not decide alone.

1. **Variable audit, CM1 and WoFS.** For every field a reader lists, decide with Bobby:
   shown or hidden, display name, units, colormap, range, diverging or not. Settle the
   fields that are not plainly "in the file":
   - WoFS sums `THETA` (T + 300) and `PRES` (P + PB);
   - WoFS base state `THETA0`, `PRES0`, `QVAPOR0`, `U0`, `V0` (the first time's field,
     not a true base state);
   - `zagl` and `zmsl` (computed from the geopotential);
   - CM1 pressure decomposition, offered as computable when no file holds it;
   - derivatives (`ddz.X`, `ddx.X`, `ddy.X`, `gradh.X`) of any field;
   - WoFS's WRF 2D/3D diagnostics, currently all listed.

   Output: each data type's catalog (`core/cm1_catalog.py`, `core/wofs_catalog.py`)
   updated to the reviewed list; a field hidden by the audit is not shown anywhere.
2. **Derived-field audit.** The agent writes `docs-dev/derived-fields.md`, one entry per
   derived field in `core/fields.py` (and `pdecomp/`): the equation as coded, its
   reference (e.g. Bolton 1980 eq. 43 for θe), units, sign convention, inputs by role,
   and every assumption flagged for confirmation (e.g. buoyancy loads hydrometeors in
   θρ but not in the base state; RH over liquid only; a WoFS perturbation is the change
   since the first time; storm-relative fields hidden without a storm motion). Bobby
   goes through it and marks each field confirmed, corrected, or dropped.
3. **Fix and test.** Correct the equations Bobby changes. Each confirmed field gets a
   test with an analytic answer on synthetic data.
4. **Show only confirmed fields with their inputs.** Add a `confirmed` flag to derived
   fields. A derived field is listed only when it is confirmed and every input it needs
   exists in the run (the input check already exists in `_make_fields`). While the audit
   is under way, unconfirmed fields are listed marked "unverified"; once it is done they
   are hidden. Say beforehand if this moves any image baseline in `tests/baseline/`.
5. **Derived-field docs page** (Bobby, 2026-11-19; after step 3, so the equations are the
   final ones). A page under `docs/guide/` listing every derived field: what it is, the
   equation as coded, units, sign convention, inputs, and what it leaves out (e.g. `ztend`
   has no advection, f or mixing). No literature references. Link it from `fields.md`.

Done when: both lists reviewed by Bobby; catalogs and derived fields match them; tests
pass. The radar variable audit (Phase 6, step 1) follows the same template.
**CHECKPOINT** after step 1, and after step 2 is reviewed.

### Phase 3: Capabilities and panel registration API

1. A data type declares its capabilities (soundings, parcels, pressure decomposition,
   storm tracking, storm-relative winds, terrain-following levels, geo, native polar view,
   and so on). Extend the existing flags on `Run`.
2. Add a small API for a data type's package to register panels (and their toolbar/tab
   entries). The viewer builds its layout from the registry.
3. Gate the existing panels on capabilities; do not move them yet.

Done when: every model gate in the Phase 0 list is replaced by a capability check (or
listed as deliberately kept, with a reason); tests pass.
**CHECKPOINT**.

### Phase 4: Radar design spike (report, not code to keep)

1. Verify all 19 files share the layout in Section 5; report differences.
2. Prototype the **sampler** primitive: given x, y, z points (km, radar-relative), return
   field values by polar interpolation. Include the beam-height model (earth curvature and
   standard refraction as one explicit, shared choice).
3. Measure: sampler cost for a cross-section and a column; a cached regrid of one volume
   (field, 500 m and 1 km spacing); memory. Report real numbers.
4. Prototype a native sweep-structured grid for 3D isosurfaces (PyVista) and say what the
   gap between sweeps does at long range.
5. **Decide the radar run object.** `Run` assumes a regular `xh`/`yh`/`z` grid. Say
   whether radar should subclass `Run` (with the grid parts unused or synthesized), or get
   a sibling base class that shares only the neutral parts (times, fields, caching, geo).
   List what the core, viewer and figures would need to accept either. Phase 5 splits the
   core around this answer, so it must be settled here.
6. Write a short report in `docs-dev/radar-spike.md` with a recommendation on what to
   build first, including the run-object decision.

Done when: Bobby has read the report and decided. (Decided 2026-11-19: `docs-dev/radar-spike.md` section 8.)
**CHECKPOINT** (design decision).

### Phase 5: Split into the monorepo

1. Move to `packages/core`, `packages/cm1`, `packages/wofs` (radar comes in Phase 6).
   Use workspaces so apps import the core from source. Data types register through
   entry points or a registry module; document the one-line registration.
2. Move the CM1-only panels and modules (`thermo`, `sounding_plot`, `parcels`,
   `trajcalc`, `track`, `pdecomp`, the soundings/parcels/tracking panels) into
   `packages/cm1` via the panel registration API.
3. CI: path-filtered tests (core changes run everything; a data-type package runs its
   own).
4. Collaborators: add `.github/CODEOWNERS` (core owned by Bobby; each data-type package
   gets its own owners), a short `CONTRIBUTING.md` (branch, PR, which tests to run).
   Bobby configures branch protection: require a PR and code-owner review on `master`.
5. Keep the one-command UX: `atmo3d /path/to/run` detects the data type.

Done when: tests pass; `atmo3d --demo` works; adding an empty data type folder takes no
core edits.

Decisions (Bobby, 2026-11-19): packages import as `atmo3d` (core), `atmo3d_cm1`,
`atmo3d_wofs`, registered through the `atmo3d.datatypes` entry point (each installed
editable; no uv here). `thermo`, `sounding_plot`, `track` and the Sounding/Track panels
**stay in core**, because WoFS offers soundings and tracking too. Parcels, trajcalc,
pdecomp and the Parcels panel moved to `packages/cm1`; the core reaches them through
`core/services.py` and `viewer/ext.py` (no core import of a data-type package; tested).
Status: step 1-5 done on branch `phase5-monorepo`; Bobby still runs the full suite and sets
branch protection.
**CHECKPOINT**.

### Phase 6: Radar package

1. **Variable audit (interactive, with Bobby; do not skip).** (2026-11-19: self-explanatory rows decided in `docs-dev/radar-audit.md`; the rest wait on the data providers, `docs-dev/radar-questions.md`.) Go through every field in
   the files and decide: shown in the UI or hidden, display name, units, colormap, range,
   diverging or not, mask rules (for example QC flags, where `doppler_degree` < 2), which
   are retrieved vs observed, and what derived fields are wanted. Output: the radar
   field catalog.
2. Reader: CfRadial files to `Run`-like volumes (one file is one time); radar site as the
   origin; lat/lon via `geo` for map boundaries; native storage as sweeps x rays x gates.
   (2026-11-19: done. `core.run` split into `Source` / `Run(Source)` first, which Phase 5 had
   not done; `atmo3d_radar.run.PolarRun(Source)`. `core.fields.Fields` still needs a grid,
   so the app cannot open a radar folder until steps 3-4.)
3. Native **PPI** view panel (registered by the radar package).
   (2026-11-19: done, as Bobby chose: radar opens in the shared viewer and its main map
   draws the chosen sweep (level mode "sweep"; `atmo3d_radar.ppi`, nearest ray and gate
   on the map's pixels); the radar's "PPI" panel lists the sweeps and shows the gate under
   a click. Grid-only tools, 3D and figures are off on radar (`grid` capability) until
   step 4.)
4. Sampler-based cross-section, column and constant-height views, and 3D (native
   structured grid), per the Phase 4 decision.
   (2026-11-19: done. `atmo3d_radar.sampler` (the Phase 4 prototype, numba; ray gaps as
   on the PPI; settings `radar_sampling`, `radar_max_gap_km`, default: every gap
   bridged); the radar map's level control adds "Height (km)" (CAPPI) and "Column
   max/min" (of the sweeps: composite reflectivity, audit D3, as a level mode rather
   than a separate field); Cross-section and 3D region are on for radar (capability
   `sampled`), the 3D workspace with isosurfaces by index-space marching cubes
   (`atmo3d_radar.scene`) and the floor; the PPI panel draws the column under a click;
   map vectors at a height. Core hooks on the run (`map_plane`, `section_points`,
   `sample_section`, `build_scene`), grid code paths unchanged. Still off on radar:
   Series, Distribution, 3D vectors and streamlines, the Figure workspace, sessions.
   The `Fields` neutral/grid split was not needed: `Fields` leaves out the grid-only
   derived fields on a run with no grid (step 3).)
5. **Regrid** (optional, off by default): settings in the settings panel (method,
   horizontal and vertical spacing, maximum range, gap masking); a first-use dialog that
   requires confirming settings; cached with the settings in the cache key; a "regridded:
   method, spacing" label on every view; the settings are saved into figure bundles,
   exports, and sessions.
   (2026-11-19: done. `atmo3d_radar.regrid.RegriddedRun(Run)` at the virtual path
   `<folder>/regrid_<method>_dx<km>_dz<km>_r<km>_gap<km>`, so the settings travel with
   sessions, figure bundles, exports and the address; the toolbar's parts switch
   (Native sweeps | Regridded) opens it only after a dialog confirming the settings
   (`regrid_ui`), saved as `radar_regrid_*`; each field and time regridded when first
   read (the sampler at every grid point; about 2-3 s at 0.5 km over 150 km), kept in
   the 3D cache and as .npy cache files (settings and source file state in the key;
   at most 4 GB per regridded run); "regridded: method, spacing" on the map, section,
   3D, series and distribution views; export attributes `atmo3d_regrid*`. Every grid
   feature works on it, with derived wind fields (audit D2) and a derived vertical
   vorticity where the data type has none. Core: `Model.parts_of`, `folder_label`,
   `parts_tip`; `_ext_modals`; grid isosurfaces treat empty (NaN) points as outside.)
6. Tests: a small synthetic radar generator (like `tests/synthetic.py`) with analytic
   answers; reader, sampler and regrid tests.
   (2026-11-19: done. `tests/synthetic_radar.py` (steps 2-4); `test_radar_reader.py`,
   `test_radar_ppi.py`, `test_radar_sampler.py`, `test_radar_regrid.py`, and
   `test_radar_analytic.py` (hand-worked answers: across north, the half-weight rule
   at a missing gate, a missing sector, sweeps with different ray counts, a volume cut
   short, the regrid's grid points): 65 tests, in `tests/radar-tests.txt` for CI.
   `test_real_radar.py` checks your own folder: ATMO3D_RADAR_ROOT=... pytest -m real.)

Done when: Bobby can open the 19-file folder, scrub through times, see PPIs, cross-sections
and 3D, and regrid with confirmed settings. **CHECKPOINT** after steps 1, 3, and 5.

### Phase 7: Finish

1. Minimal docs for new features (a radar guide page, the regrid settings, the new
   registration API in `docs/developing.md`). No rename or migration docs.
2. Changelog; version to **1.0.0**.
3. Final full-suite run by Bobby.

## 7. Open items

- Receiver locations for the bistatic geometry: where do they come from?
- Real `w` data in other files, or always zero? (Phase 4: `w` is nonzero in files 1-18; `w_direct` is zero in all 19. See `docs-dev/radar-spike.md`.)
- Depth of the upgrade path (figures only, or sessions too). Plan assumes both.
- Whether the radar collaborators get write access or work through forks and PRs
  (Phase 5 sets up CODEOWNERS either way).
