# Phase 0 inventory (atmo3d plan)

Branch `atmo3d`, taken 2026-11-18 from `atmo3d/` at fce4255. Paths are relative to
`atmo3d/`. Line numbers will drift; use the quoted text to find a spot again.
Not part of the mkdocs build (outside `docs/`).

Suite result before this work: full suite passed (Bobby, 2026-11-18; counts not
recorded here, please add them: `pytest -q | tail -1`).

Method: quoted-string search in `viewer/` and `figures/` for the CM1 field names, then
read each hit; JS/`open(..., "w")`/Bokeh column names (`"v"`, `"w"`, `"s"`) were
dropped as noise. Names that look like fields but are **not** are in section 9.
Hits are grouped by what the name is used for, since Phase 2 works one group at a time.

CM1 names involved: `dbz`, `cref`, `winterp`, `uinterp`, `vinterp`, `thpert`, `th`,
`prs`, `qv`, `xvort`, `yvort`, `zvort`, `zagl`, `zmsl`.

## 1. Default fill / contour / "first field" choices

All of the form `"X" if "X" in F else next(iter(F.defs))`. The fallback already works
for any catalog; the named first choice is what needs to come from the data type.

| File:line | What it does |
|---|---|
| viewer/xsec.py:76 | cross-section fill: `dbz` |
| viewer/xsec.py:174 | cross-section reads `winterp` for its default variable |
| viewer/layout.py:80 | 3D ground-plane field: `cref`, else `dbz` |
| viewer/layout.py:81 | ground checkbox on when that field is `cref`/`dbz` |
| viewer/widgets.py:223 | map default var `winterp`, level 3 km vs 1 km |
| viewer/widgets.py:292 | map default fill: `cref`, else `dbz` |
| viewer/dist.py:35 | distribution default: `winterp` |
| viewer/series.py:37 | series default: `thpert` |
| viewer/tracking.py:39 | tracking default field: `winterp` |
| viewer/view3d.py:67 | slice-line "along" default: `winterp` |
| figures/scene.py:42 | scene floor field: `cref`, else `dbz` |
| figures/sources.py:213, 268, 295 | new source default field: `winterp` |
| figures/shell/statsview.py:22, 39 | stats default field: `winterp` |
| figures/shell/seriesview.py:27 | series default field: `winterp` |
| figures/shell/planview.py:42 | new fill/contour/shade layer: `dbz` / `winterp` / `winterp` |
| figures/spec/base.py:104 | figure default fill: `dbz`, else `cref` |
| figures/spec/base.py:107-110 | default layers: `winterp` contour at 3 km; `uinterp` present adds the wind layer |
| figures/spec/arrays.py:86 | scene ground default `var="dbz"` |

## 2. Per-field display and level defaults

| File:line | What it does |
|---|---|
| viewer/widgets.py:76 | colour range 5-30 for `winterp` (else the field's `vrange`) |
| viewer/widgets.py:85 | "Auto range" off for `winterp` |
| viewer/widgets.py:225 | level mode/value default depends on `winterp` |
| viewer/widgets.py:380-382 | extra-layer defaults: `winterp` contour at 3 km (5, 15, 25), `thpert` at level 0 (-6..-1) |
| viewer/xsec.py:103-107 | cross-section overlay contours: `winterp` (-10..30), `thpert` (-6..-1); `winterp` contour on by default |
| figures/spec/base.py:21 | `refl = field in ("dbz", "cref")` (reflectivity colour/limits handling) |
| figures/spec/panels.py:30 | `field in ("winterp", "w") and red == "max"`: "updraft speed" label |

## 3. Isosurface and 3D-scene defaults

| File:line | What it does |
|---|---|
| viewer/layout.py:49-52 | iso defaults: `dbz` 30, `winterp` +10 and -5, `zvort` 0.05 |
| figures/scene.py:24-25 | scene iso defaults: `dbz` 30, `winterp` +10 / -5 |
| figures/scene.py:190-191 | lone scene: one `dbz` 30 iso if `dbz` exists |
| viewer/view3d.py:62 | vorticity slice offered only if `xvort`, `yvort`, `zvort` all exist |

## 4. Wind components (and storm motion)

| File:line | What it does |
|---|---|
| viewer/view3d.py:533-534 | wind triple `uinterp`/`vinterp`/`winterp`; vorticity triple `xvort`/`yvort`/`zvort` for streamlines |
| viewer/view3d.py:567-569 | native `uinterp`/`vinterp` minus storm motion `cu`/`cv`, `winterp` for w |
| figures/spec/base.py:109 | wind layer is offered when `uinterp` is there |
| figures/sources.py:288 | `yfield` = `zvort` when present (vorticity sampled along a track) |
| figures/shell/statsview.py:31 | same `zvort` rule for stats |

(`core/vectors.py` and `core/fields.py` hold the names for the vector layers
themselves; they are outside this inventory's scope but will be part of Phase 2.)

## 5. Sounding inputs

| File:line | What it does |
|---|---|
| viewer/ui.py:17 | `SOUNDING_VARS = ("th", "prs", "qv", "uinterp", "vinterp")` (plus `zagl` on terrain runs: viewer/sounding.py:110, 159) |
| figures/spec/panels.py:15 | duplicate `SOUNDING_VARS` definition (figures side) |
| figures/spec/panels.py:631 | `names = SOUNDING_VARS + zagl` |
| viewer/sounding.py:105 | `BASE_VARS` must all be on the run, else no sounding |
| viewer/sounding.py:240-241 | `thermo.analyze(zc, c["prs"], c["th"], c["qv"], c["uinterp"] + run.umove, ...)` |
| figures/spec/panels.py:654-655 | the same call for the figure sounding |

The two `SOUNDING_VARS` copies should become one catalog entry (thermo inputs).

## 6. Time-height / series (name clash)

`"th"` is **also** the panel kind "time-height" (not potential temperature).
The two meanings must not be confused when Phase 2 searches for `"th"`:

- panel kind `"th"` (not a field): figures/render.py:128, 414; figures/kinds.py:56;
  figures/export.py:162; figures/settings.py:201, 218-221; figures/draw/v2.py:118-492;
  figures/draw/layers.py:307; figures/spec/doc.py:46, 401, 420; figures/spec/docfile.py:179,
  384; figures/spec/templates.py:44; figures/spec/panels.py:70, 590; figures/spec/base.py:395;
  figures/shell/{docedit,seriesview,looks,findview,gridview,inspector,frame}.py;
  figures/cards/seriescard.py; figures/sources.py:319; viewer/series.py:89, 397, 494.
- field `th` (potential temperature): viewer/ui.py:17, viewer/sounding.py:241 (via
  `c["th"]`), figures/spec/panels.py:15, 654; viewer/parcels.py:180 (parcel variable
  preference `th`, `b`, `z`).

A saved file's `"kind": "th"` is part of the file format: do not rename it.

## 7. Parcels and storm tracking (CM1 variable names inside CM1-only panels)

| File:line | What it does |
|---|---|
| viewer/parcels.py:171-180 | parcel plot variable preference: `w`, `z`; `th`, `b`, `z`; "w budget" kind |
| viewer/parcels.py:352-355, 462, 508, 1029, 1104-1116 | `"budget"` plot kind and the `dwdt` term |
| figures/spec/panels.py:143-172 | `parcel_series_defaults(var="w")`, `dwdt` to `w` delta, "Δw" label |
| viewer/tracking.py:35, 184-188 | tracking metrics `w`, `zeta`, `uh` with per-metric levels and smoothing |
| figures/shell/seriesview.py:152 | parcel series pick `w` |
| figures/widgets.py:208, figures/settings.py:197, figures/spec/base.py:176 | contour-key label `"w"` (a text default) |

These move with the CM1 package in Phase 5, so Phase 2 can leave them in place.

## 8. Z / level keys that are not field names but are data-type-shaped

| File:line | What it does |
|---|---|
| viewer/layout.py:136, figures/cards/scenecard.py:24 | streamline colour-by: `{"Height": "z", "Vertical velocity": "w"}` |
| figures/draw/scene3d.py:67-73 | stream colours by `stream["w"]` |
| figures/shell/planview.py:24 | `ZMODES = {"km": "height", "Model level": "level"}` |
| figures/cards/datacard.py:153 | `AXIS, UNIT = "height", "km"` |

## 9. Looks like a name but is not (ignore)

`zoomview.py` JS `kv('u'...)` / `kv('v'...)` (hover readout), Bokeh column names `"v"`,
`"s"`, `"zs"`, `"w"`, `"h"` in mapview/view3d/draw, `open(..., "w")`, table columns
`"t"`/`"v"` (own-data series, figures/spec/panels.py:115-320), `A{n}_v` arrays,
`pr["u"]`/`pr["v"]` (sounding profile dict, figures/spec/panels.py:722).

## 10. Names in `core/` that Phase 2 will meet (outside viewer/figures, for orientation)

`core/fields.py` (the catalog and derived fields; the main thing to split),
`core/wofs.py:54` `MAPPED` (WRF to CM1 renaming; Phase 2 removes it),
`core/thermo.py`, `core/sounding_plot.py`, `core/parcels.py`, `core/trajcalc.py`,
`core/track.py`, `core/vectors.py`, `pdecomp/` (all CM1 names).

# Model gates

Every place that branches on the data type. "Capability flag" = an attribute of `Run`
(`core/run.py:574-591`): `terrain`, `traced_parcels`, `storm_relative`, `geo`,
plus `model`, `model_label`. Phase 3 replaces each with a capability check or keeps it
with a reason.

## A. Direct data-type tests

| File:line | What it gates | Suggested Phase 3 fate |
|---|---|---|
| pdecomp/__init__.py:66 | `run.model == "cm1"` in `can_compute`: pressure decomposition only for CM1 | capability `pdecomp` |
| viewer/swap.py:21-22 | `(a.model, ...) != (b.model, ...)`: can a member be swapped in place (same model and grid) | keep, as a grid-compatibility check (model equality is fine: same type) |
| registry.py:126 | `self._runs[path][0].model != want`: re-open if the user picked another model | keep (picker semantics) |
| figures/runs.py:116 | `models.MODELS.get(self.run.model)`: model object for member lists | keep (registry lookup, not a branch) |
| viewer/widgets.py:553 | `json.dumps([path, self.run.model])`: picker go value | keep |
| core/models.py (all) | `CM1` / `WoFS` classes with `count`, `looks`, `parts`, `virtual`, `canonical`, `summary` | this is the registry; Phase 5 moves each into its package |
| `__main__.py:55-84`, `bench.py:48-90` | `--demo cm1|wofs` choices and demo dispatch | registry-driven choices |
| viewer/picker.py:45, 200-232 | model Select box; `models.get`/`detect` | registry-driven, nothing to gate |

## B. Capability flags on `Run`

`terrain` (a **geometry** flag: levels follow terrain), by far the most used. All of
these are "does this run have terrain-following levels":

core/render.py:318, 330, 347, 352, 373; core/volume3d.py:109, 115, 365, 383, 415, 426,
434, 446, 523, 558, 612, 615, 639; core/trajcalc.py:81, 118, 123, 129, 210, 236, 402,
422; core/fields.py:978, 1005, 1027, 1089, 1173; core/dist.py:88; core/track.py:90, 104;
core/azim.py:120; core/series.py:112, 627; viewer/layout.py:68-69; viewer/xsec.py:35,
111-112, 331; viewer/sounding.py:110, 159; viewer/widgets.py:249;
figures/scene.py:45; figures/spec/arrays.py:538, 559; figures/spec/panels.py:631.

`traced_parcels` (the model writes no parcel output; trajectories are traced):
core/parcels.py:112, 121 (`getattr(run, "traced_parcels", False)`),
viewer/parcels.py:252 (turns the "read file" parcel options off and explains why).

`storm_relative` (False for WoFS: no storm motion known):
core/vectors.py:43, core/fields.py:836 (skips fields flagged `d.storm`),
viewer/swap.py:24 (members must agree).

`geo` (map projection, WoFS only; CM1 is `None`):
viewer/geomap.py:72-223 (the whole Boundaries pill), figures/spec/base.py:111 and :51
(the "boundaries" layer), figures/spec/arrays.py:353 (its lines), figures/shell/planview.py:66
(`on_map`).

## C. Implicit gates (no `model ==`, but a CM1-only feature is unconditional)

These do not look at the model at all. They are what Phase 3 must find and put
behind a capability, because a radar run would hit them:

- **Soundings**: viewer/sounding.py:105 gates on `run.has(v) for v in BASE_VARS`, i.e. a
  name check; figures/spec/panels.py:631 builds the same.
- **Pressure decomposition**: viewer/widgets.py:496-501 and viewer/app.py:95, 348 call
  `pdecomp` unconditionally; only `can_compute` (A) decides.
- **Parcels / trajectories**: viewer/parcels.py (all), core/parcels.py, core/trajcalc.py.
- **Storm tracking**: viewer/tracking.py (all), core/track.py. viewer/tracking.py:116 shows
  the member controls "for runs read as several" (a `parts` check, not a model check).
- **Members / ensemble mean**: viewer/swap.py, viewer/widgets.py:616-627,
  viewer/tracking.py:525-540, viewer/diff.py:42, figures/runs.py:108 (`models.root_of`),
  viewer/mapview.py:351 (`getattr(self.run, "stat", None)`).
- **Storm motion** (`run.umove`/`run.vmove`): viewer/sounding.py:240-241,
  figures/spec/panels.py:654-655, viewer/swap.py:21-22.
- **Config**: `wofs_member` / `WOFS_*` settings read in core/wofs.py and shown in
  viewer/widgets.py:627.

# Tests

59 test files, all synthetic (`tests/synthetic.py` makes the CM1 run; `atmo3d.demo_wofs`
makes the WoFS one). Image baselines: 13 PNGs in `tests/baseline/`, driven by
`tests/test_images.py` (CM1 only).

Coverage of the CM1 path is broad (figure shell and spec: roughly 20 files; fields,
series, dist, azim, joint, sounding, parcels, tracking, pdecomp, export, session).

WoFS-specific tests: `test_wofs.py` (34: discovery, member and mean runs, values, base
state and perturbations, heights), `test_geo.py`, `test_storms.py`, `test_running.py`
(one WoFS case), `test_real_wofs.py` (needs real data), `test_figure_render.py`.

## Thin spots (what a later phase would leave unprotected)

1. **WoFS field names end-to-end (Phase 2).** `test_wofs.py` checks values and base
   state through the CM1 names. Nothing builds a WoFS figure or viewer and asserts the
   catalog, defaults, or sounding inputs. Renaming to WRF names would break no test
   until something looks at the viewer defaults.
2. **No image baseline for WoFS** (only CM1 in `test_images.py`).
3. **Saved-file upgrade (Phase 2.4).** `test_session.py:249` (older session opens) and
   `test_figure_spec.py` (older section/time-height/scene figures) cover the existing
   upgrades. There are **no fixtures of old WoFS files** (a session or figure that names
   WoFS fields as CM1 names). Phase 2 must generate them before changing the names.
4. **Model gates (Phase 3).** No test asserts which panels or toolbar items appear for
   a given model (e.g. that a WoFS run has no pdecomp, gets traced parcels, has a map).
   Closest: `test_parcels.py` (traced), `test_map.py`, `test_geo.py`.
5. **Registration (Phase 5).** `test_picker.py` and `test_wofs.py::test_experiment_is_one_run`
   cover detection; nothing for adding a third model.

## Proposed characterization tests (not yet written; for Bobby's approval)

- C1 `tests/test_defaults.py`: for the CM1 and WoFS demo runs, record the default
  fill, contour, iso, series, tracking fields and the wind triple that the viewer/figure
  pick (the section 1-4 groups). Protects Phase 2.
- C2 `tests/test_capabilities.py`: for the same two runs, record which of soundings,
  pdecomp, parcels (file / traced), tracking, geo, members the viewer exposes (the
  section B/C gates). Protects Phase 3.
- C3 old WoFS saved files: one session and one figure document naming CM1-style WoFS
  fields, loaded now (Phase 2.4 turns this into the upgrade test).

No tests were added in this step. These three are small (no baselines, no big data) and
use only the existing demo runs.

# Phase 2 status (2026-11-18)

Sections 1-5 and the core modules in section 10 now name **roles** (`core/catalog.py`
`ROLES`: `u`, `v`, `w`, `theta`, `pres`, `qv`, `refl`, ...) and ask the run's catalog
(`run.catalog`, `Fields.cat`, `F.role(r)`) for the field. Catalogs: `core/cm1_catalog.py`,
`core/wofs_catalog.py`. Derived fields in `core/fields.py` are written with role names and
bound per catalog (`_bind`). WoFS keeps WRF names; `core/wofs.py` only sums `THETA` (T+300)
and `PRES` (P+PB); base state `THETA0`, `PRES0`, `QVAPOR0`, `U0`, `V0`.

Deliberately left as they are:

- `zagl`, `zmsl` (section 8 and the terrain code): atmo3d's own height fields of a
  terrain-following run, computed by the reader, not a CM1 name. Phase 3 (terrain
  capability) is the place to revisit.
- Derived-field names (`thpert`, `prspert`, `buoy`, `uh25`, ...): the core's, the same
  for every data type.
- Section 7 (parcels, tracking metrics, `pdecomp/`): CM1-only code, moves in Phase 5.
  `pdecomp/` still names `prs`, `qv`, `uinterp`... and is gated to CM1.
- Section 6: panel kind `"th"` is part of the file format (untouched; the upgrade's key
  allowlist never sees it).
- Placeholder text such as `"e.g. 2x3 dbz w"` (figures/style.py).

Saved files: session format 2; `core.catalog.rename_fields` + `renames_for` rename an
old WoFS file's fields by `wofs_catalog.OLD_NAMES` when all its runs are WoFS (a figure
mixing CM1 and WoFS runs is left as saved, with a note: one layer's field name cannot
suit both). Figure documents keep `version` 3: the renaming is idempotent, so no marker
is needed. Fixtures: `tests/data/old_files` (written by the pre-Phase-2 code).

# Phase 3 status (2026-11-19)

Capabilities: `core/capabilities.py` (`CAPS`: soundings, parcels, traced_parcels, pdecomp,
tracking, storm_relative, terrain, geo, native_polar). A data type declares
`Run.OFFERS` (CM1: soundings, parcels, pdecomp, tracking; WoFS: soundings, tracking.
No parcels for WoFS, Bobby 2026-11-19; `core.parcels.offered`/`for_run` check the
capability, so trajectories are not traced for it anywhere. WoFS keeps
`traced_parcels = True` as a description, and the traced code in `core/trajcalc.py`
stays tested through test_wofs.py, which turns parcels on for WoFS in the test). The four old flags stay attributes and are capabilities too. `run.offers(c)`:
the data type offers it. `run.can(c)`: it offers it and this run has the inputs.

Panels: `viewer/panels.py` holds the registry (`Tool`: key, label, icon, tip, layout,
title, modes, needs, shown). `register()` adds a tool, `for_run(run)` returns (panels
built, rail tools). The tab strip holds every panel whose `needs` the data type offers.
The rail button also needs `run.can(needs)`, or `shown(run)` when given. The old
`TOOLS`, `TOOL_OF`, `PANELS`, `TAB_MODE` and `PANEL_TITLES` tables in `viewer/ui.py` are
gone, and so is the hand-built tool list in `viewer/widgets.py`. The panel contents are
`Layout._snd_layout`, `_xs_layout`, `_trk_layout`, `_ser_layout`, `_dist_layout`
(and `_par_layout`). The panels are still the Viewer's mixins (Phase 5 moves them).
`_show_panel` takes a panel key (or an int, the registry place, as a saved session
records it). `_panel()` and `_panel_open(key)` replace the `tabs.active == N` checks.

Saved sessions: `panel.tab` is the panel's place in the registry. For CM1 and WoFS that
is the same number as before (all six built-in panels are built for both).

## What happened to each gate

| Gate (Phase 0 list) | Fate |
|---|---|
| A pdecomp/__init__.py `run.model == "cm1"` | replaced: `run.offers("pdecomp")` |
| A viewer/swap.py:21-22 model equality | kept: a grid-compatibility check (a member swaps only for one of the same type and grid) |
| A registry.py:126 `.model != want` | kept: picker semantics (re-open as the type the user picked) |
| A figures/runs.py:116, viewer/widgets.py:553, core/models.py, viewer/picker.py | kept: registry lookups and data, not branches; Phase 5 moves the registry into packages |
| A `__main__.py`, `bench.py` `--demo cm1/wofs` | kept: picks which demo to build; Phase 5 makes the choices registry-driven |
| B `terrain`, `geo`, `storm_relative`, `traced_parcels` reads (about 60) | kept as attribute reads: they are the capabilities (`can()` reads the same flag) and also carry how (the Geo object, terrain heights) |
| B tracking (viewer/widgets.py rail and storm button) | replaced: `run.can("tracking")` |
| C soundings: rail | replaced: built and shown when the type offers soundings (still shown if a run lacks the inputs; the panel says what is missing, as before) |
| C soundings: figures/spec/panels.py | replaced: `run.offers("soundings")` before the name check |
| C soundings: viewer/sounding.py:105 name check | kept: the per-run input check inside the panel |
| C pdecomp: viewer/widgets.py:496-501, app.py:95, 348 | kept: these read the write-permission setting; computing goes through `can_compute`, now gated by `offers` |
| C parcels: rail | replaced: `run.can("parcels")` |
| C parcels: core/parcels.py `offered`, `for_run` (viewer/swap.py, core/export.py use them) | replaced: return nothing unless `run.offers("parcels")` |
| C parcels/trajectories: core/parcels.py, core/trajcalc.py | kept: the feature itself, reached only through the panel |
| C tracking: viewer/tracking.py, core/track.py | kept: the feature itself (rail and storm button gated above) |
| C members/ensemble mean (`parts`, `stat`) | kept: members come from the data type's `parts` in core/models.py, so any type that lists parts gets them; not a capability |
| C storm motion `umove`/`vmove` | kept: grid motion is model-neutral (0 when none) |
| C config `wofs_member` / `WOFS_*` | kept: read by the WoFS reader only; moves with it in Phase 5 |

Saved sessions also record the open panel's key (`panel.key`), and the reader uses it
first. `panel.tab` is still written for older versions, and a session without a key
falls back to it. A key whose panel this viewer lacks (package not installed) stays
closed. The extra field is ignored by readers that don't know it, so FORMAT stays 2.
