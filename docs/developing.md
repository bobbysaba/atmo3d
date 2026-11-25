# Developing atmo3d

## Tests

```bash
conda activate atmo3d
pytest -n auto                          # the suite, on synthetic demo runs, in parallel
pytest tests/wofs                       # one package's tests (tests/core: the core's)
pytest tests/core/test_tracking.py -k manual   # one file / matching tests
ATMO3D_TEST_RUN=/path/to/run pytest -m real   # checks on your own output (reads only)
pytest -m browser                       # the viewer in headless Firefox, with screenshots
```

Run the suite on a compute node rather than a shared login node: it starts reader
processes and renders figures.

- **Folders.** `tests/core/` tests the core (on the synthetic CM1 runs, so it needs the
  data-type packages installed, though the core never imports them); `tests/cm1/`,
  `tests/wofs/`, `tests/radar/` and `tests/example/` test one package each. The shared
  setup stays in `tests/`: `conftest.py`, the synthetic data (`synthetic.py`,
  `synthetic_wofs.py`, `synthetic_radar.py`, `synthetic_level2.py`), `catalog_checks.py` and `baseline/`. A test imports these by name (`from synthetic_wofs import make_wofs`),
  never another test file.
- **In parallel.** `pytest -n auto` (pytest-xdist) runs the tests in one worker per CPU
  the job may use, at most 8: the CPUs the process is allowed (a PBS or Slurm job's
  share of the node), else the machine's count. So 1 CPU runs one worker, as fast as without
  `-n`, and a laptop of 4 cores runs 4. `-n 4` asks for four; without `-n` the tests run
  one at a time, as before. Each worker has its own settings file and figure folders;
  the demo data is shared, written once (the first worker writes it, the others wait).

- **Test data.** `tests/synthetic.py` writes small analytic runs shaped like CM1 output
  (staggered winds, base state, swaths, one level per chunk), a weak-mesocyclone twin and
  their storm tracks, so the tests know every answer in advance. They are written once to
  `$ATMO3D_TEST_DATA` (default `<tmp>/atmo3d-demo-$USER`) and rewritten only when
  `synthetic.py` changes. Bump its `VERSION` when the fields change.
- **Demo run.** `atmo3d --demo` opens `demo_data/supercell`, a real CM1 run cut down by
  `tools/make_real_demo.py` (a box around the storms, every 10 min, 16-bit packed fields,
  1500 parcels; about 35 MB). `atmo3d/demo.py` copies it into the cache once.
  `tests/cm1/test_real_demo.py` checks it; to rebuild it from a new run:
  `python tools/make_real_demo.py RUN demo_data/supercell --force`.
- **WoFS demo data.** `tools/make_wofs_demo.py ROOT OUT` cuts a WoFS experiment down to
  a few members and cycles (default members 1–3, 2 h every 15 min), the fields atmo3d
  reads and 16-bit packed values, the whole domain kept (about 23 MB a member file).
  It is too large for the repository (about 600 MB) and is not in `demo_data/`;
  `ATMO3D_WOFS_ROOT=OUT pytest -m real tests/wofs/test_real_wofs.py` checks a build.
- **Radar demo data.** `tools/make_radar_demo.py SRC OUT` copies a folder of CfRadial
  volumes with every sweep, ray and gate kept, minus the padding rays past the sweep
  table and three receiver QC fields, 16-bit packed (about 19 MB a volume, from
  250–285 MB). Like the WoFS demo it is not in `demo_data/`;
  `ATMO3D_RADAR_ROOT=OUT pytest -m real tests/radar/test_real_radar.py` checks a build.
- **Isolation.** Tests use a throwaway settings file and write only into temporary
  folders. The pressure-decomposition tests work on copies of demo files.
- **Browser tests** need Firefox (on `PATH`, or `$FIREFOX`). Screenshots go to
  `$ATMO3D_SHOTS` (default: a temporary folder, printed with `pytest -s`).
- **Image baselines.** `tests/core/test_images.py` draws typical figures of the demo run (plan
  view, cross-section, time–height, time series, soundings, distributions, a difference
  fill, a swath, parts, a dark style) and compares each with a PNG in `tests/baseline/`;
  it also checks that save → load → draw of every panel kind gives the identical image.
  A missing baseline is written on the first run. `ATMO3D_IMAGE_TOL` sets the allowed RMS
  difference (0–255, default 3), because fonts and matplotlib versions shift pixels
  between machines. When a figure changes **on purpose**, look at the failure's
  `*-failed-diff.png` (left in pytest's temporary folder), then rewrite the baselines with
  `pytest tests/core/test_images.py --make-baselines` and commit the new PNGs. Commit
  baselines made with the versions in `environment.yml`.
- **Fixtures** (`tests/conftest.py`): `demo_root`, `demo_run`, `reg` (one Registry for
  the session) and `viewer` (a fresh Viewer on the demo supercell at its first storm
  time). `wait(pred)` polls background work; `tap(v, x, y)` is a map click. For the
  figure tests (`tests/core/test_figure*.py`): `ed` (the viewer's figure editor, no auto
  render), `coarse_run` (a second run with other output times), `new_spec(ed, kind, rows, cols)`
  (the spec the New dialog starts from), `doc_now(ed)`, `put(s, widget, value)`,
  `render(ed, figure)`, `settled(ed, figure)` and the spec helpers `difference_layer`,
  `swath_layer`, `edited_v1`.

### Which test file covers what

Files in `tests/core/` unless the row says otherwise.

| File | Covers |
|---|---|
| `test_fields.py` | Derived fields, shared reads, the cache, the base state; levels read together, volumes in slabs, parts of fields larger than the cache |
| `cm1/test_pool.py` | The shared reader processes: one pool for every run, files kept open, the scan of a run's files, work spread to a width, reading ahead over times |
| `test_timing.py` | The timing hooks of `--timing` and `atmo3d bench`, the log summary |
| `test_map.py` | Map, cross-section and 3D: layers, differences, streamlines, the region and floor |
| `test_streamlines.py` | The 3D streamline tracer on analytic winds, and the 3D pane's restyle echo |
| `test_sounding.py` | Soundings, comparison styles, zoom and the hover data |
| `test_tracking.py` | Automatic and hand-placed tracking, save and load, storm-following soundings |
| `test_session.py` | Session files: save, load, rows and values a run cannot take, another run's session; soundings, section, 3D, series and distributions back; a FORMAT 2 (1.1.0) session |
| `test_viewer_layers.py`, `test_viewer_layer_drawer.py` | The map's and section's layers on the schema and their drawer, without a viewer |
| `test_export.py` | netCDF export: values == the volumes / map planes, heights, box, stop, missing times, the dialog, `atmo3d export` |
| `test_series.py`, `test_dist.py` | Series (cache, time–height, files) and distributions |
| `cm1/test_parcels.py` | Parcel output: reads, lattice, selections, sets, trajectory cache, heads, wraps, split files; the Parcels panel |
| `cm1/test_pdecomp.py` | The pressure decomposition, on copies of demo files |
| `test_figure_shell.py` | The figure editor: its tree, picking, edits and undo |
| `test_figure_shell_plan.py` | Plan views there: shared layers and overrides, heights, time zero, Fill panels, look settings, the New dialog |
| `test_figure_shell_*.py` | The other kinds there, mixed grids, insets, Find, the scrubber, Export, other runs |
| `test_figure_doc.py` | The document: drawing from it |
| `test_figure_drawing.py` | What figures draw and save: each kind's plots, tables, series, animations, the script, own code |
| `test_figure.py`, `test_figure_layers.py`, `test_figure_runs.py`, `test_figure_export.py`, `test_figure_spec.py` | Without the editor: thumbnails, layer data, runs and time zeros, frames, the spec's panels and edits |
| `test_legend.py` | Legends of blocks and panels |
| `test_images.py` | Image baselines and save–load–draw |
| `test_datatypes.py`, `test_datatype_check.py` | Data types plug in with no core edits; the extension API's version rule; what `check_datatype` reports of a broken data type |
| `test_catalog.py` | The field catalog: tidied units and labels, renamed fields in saved files, derived fields' units |
| `cm1/`, `wofs/`, `radar/` `test_<type>_contract.py`, `test_<type>_outputs.py` | Each data type passes `check_datatype` on its synthetic run; its field table and catalog |
| `wofs/test_wofs.py` | The WoFS reader on `tests/synthetic_wofs.py`, members and the mean |
| `test_settings.py`, `test_picker.py`, `test_ui.py` | Settings, the run picker, layout logic |
| `test_browser.py` | The viewer in headless Firefox (marker `browser`) |
| `cm1/test_real.py`, `wofs/test_real_wofs.py` | Your own output (marker `real`) |
| `example/test_example.py`, `example/test_new_datatype.py` | The worked example data type (`packages/example`), on its own synthetic run: the contract check and its reads; the scaffold (`tools/new_datatype.py`) in both modes |
| `radar/test_radar_*.py` | Radar, on `tests/synthetic_radar.py` (analytic answers): reader, PPI, sampler, regrid, hand-worked cases |
| `radar/test_radar_level2.py`, `test_radar_aws.py`, `test_radar_live.py`, `test_radar_dealias.py` | NEXRAD Level II on `tests/synthetic_level2.py`: the decoder and runs, AWS fetching and live mode (a fake archive, no network), velocity dealiasing on folded analytic winds |
| `radar/test_real_radar.py` | Your own radar folder: `ATMO3D_RADAR_ROOT=... pytest -m real` |

## Layout

A monorepo: `packages/core` (import name `atmo3d`: everything below except the data-type
parts), `packages/cm1` (`atmo3d_cm1`: the CM1 reader, field catalog, parcels, trajectory
tracing, pressure decomposition and the Parcels panel), `packages/wofs` (`atmo3d_wofs`:
the WoFS reader, catalog and demo) and `packages/radar` (`atmo3d_radar`: the CfRadial
and NEXRAD Level II readers and catalog). `packages/example` (`atmo3d_example`) is the worked example of a
data type: no part of the app, it is the pattern new ones are copied from
([Writing a data type](datatypes.md#the-worked-example)). `tests/`, `docs/` and `tools/`
stay at the top. Install the four
editable (`pip install -e packages/core -e packages/cm1 -e packages/wofs -e packages/radar`; the
conda environment does it). The paths below are relative to `packages/core/src/` unless
they name a data-type package.

```
atmo3d/                  config.py (settings: file, precedence, save folders, run search),
                          registry.py (open runs shared by sessions, run discovery),
                          theme.py (colours and CSS), demo.py (the real demo run
                          atmo3d --demo opens, demo_data/), __main__.py (command line; `render` goes
                          to figures/batch.py, `export` to core/export.py), bench.py
                          (`atmo3d bench`: the viewer's actions timed without a browser)

core/                     model output, no UI
  run.py                  file discovery, staggered->scalar reads, 3D cache, parallel reads
                          (levels together, parts of fields, reading ahead over times)
  pool.py                 the one set of reader processes every run and tool shares
  fields.py               field catalog, derived fields, colormaps
  thermo.py               parcel theory (numba), kinematics, composite parameters
  sounding_plot.py        skew-T / hodograph / profiles / parameter table
  render.py               map + cross-section computations (contours, vectors, sampling,
                          differences with another run or time, regridding)
  vectors.py              the vector quantities (wind, horizontal vorticity, baroclinic
                          generation) that map, section, 3D and figures draw
  track.py                meso tracking + CSV/text export
  volume3d.py             isosurfaces, surface vectors, streamlines + Plotly scene
  series.py               time series of reduced fields: compute, cache, files
  dist.py                 distributions: a field's values over a region, their summary
  swath.py                time-window reductions (swaths, storm-following composites)
  services.py             tools only some data types bring (parcels, pdecomp, trajcalc):
                          shared code calls them through it; the package provides them
  export.py               netCDF export of fields (box, times, model levels or heights,
                          streamed per time) and `atmo3d export`

(atmo3d_cm1/pdecomp/     pressure decomposition: file fields, computing one time on
                          request, and the solver (runs in its own process))

viewer/                   the interactive page (Panel / Bokeh)
  app.py                  the Viewer (built from the mixins below), wiring; the page
  widgets.py              Viewer mixin: the toolbars' and drawers' controls, the run picker
  layers.py               Viewer mixin: the map's and the section's layers (fill, more fills,
                          contours, vectors): dicts in a figure layer's form, their controls
                          the figures' layer component (figures/ui/layer.py)
  mapview.py              Viewer mixin: the map, storm motion and the map job
  layout.py               Viewer mixin: panels, top bar, toolbars, the main column
  events.py               Viewer mixin: time, playback, tool modes, map clicks and drags
  ui.py                   shared UI pieces: constants, figure styling, drawers, tool rail
  sounding.py             Viewer mixin: soundings, their graphics, style and zoom
  tracking.py             Viewer mixin: storm tracking and the storm chip
  series.py               Viewer mixin: the Series panel and plots
  dist.py                 Viewer mixin: the Distribution panel, plots and statistics
  parcels.py              Viewer mixin: the Parcels panel, sets, trajectories on the map
  xsec.py                 Viewer mixin: cross-sections
  diff.py                 Viewer mixin: map / section fill differences (minus a time or run)
  session.py              Viewer mixin: session files (collect / put back what the viewer
                          shows; the Session dialog; ?session=)
  export.py               Viewer mixin: the Export data dialog (core/export.py in the
                          "exp" pool, progress, Stop)
  view3d.py               Viewer mixin: 3D scene, pressure-decomposition button, streamlines
                          (picking, the card, pins; the pointer is followed in the browser)
  items.py                Viewer mixin: the items tray
  zoomview.py             zoomable image component (sounding graphics) and the parameter
                          table
  timing.py               `--timing`: every update timed into a log; the hooks of bench
  numinput.py             FloatInput: a number box that keeps what you typed, tidy to 7
                          significant digits
  settings.py             settings window (first run and ⚙) and the overwrite prompt
  picker.py               run picker (header dialog and the page without a run)

figures/                  the Figure workspace
  spec/                   figure spec, panel data, export (fg.<name> for any module's)
    base.py               the spec: defaults, panels, layer groups, times, animation
    arrays.py             plan-view and cross-section panel arrays
    panels.py             time-series, time-height, sounding and distribution panels
    bundle.py             export: image, arrays, stand-alone script, spec
    templates.py          templates, style presets (scripting only), copying a layer's look
    doc.py                the figure document (version 3): to_doc from older figures,
                          one_panel to read a panel's arrays
  draw/                   matplotlib drawing of a figure; source() stitches its modules
                          into exported scripts, so they import each other only with
                          "from .<module> import ..." lines
    base.py               colours, levels, fonts, text, saving
    v3.py                 resolve() of the document (version 3) to version 2
    v2.py                 upgrade() to version 2, views of blocks and panels
    layers.py             map layers and colorbars
    lines.py              time-series and distribution panels
    sounding.py           skew-T, hodograph, parameter table
    figure.py             draw(): blocks, panels, labels, annotations
  render.py               FigureData: a spec's panel data (runs, tracks, series,
                          caches) without the editor or Panel; the editor's .data
  batch.py                `atmo3d render`: saved figures and templates drawn
                          without the viewer (images, bundles, GIFs); the GIF frame
                          helpers anim.py uses
  schema/                 every setting of a figure, one row each (no widgets): its key,
                          control, section, kinds, levels, default, help
    look.py, layer.py, doc.py
                          look rows, layer rows by layer type, the document's own rows
    where.py              a row read, written, taken back at a place (figure, kind, panel,
                          inset, layer)
    fills.py              what a row sets beside itself (a field: its colours)
    viewer.py             the viewer's map and section layers as rows (level "viewer"),
                          and FORMAT 2 sessions' layers read into them
  ui/                     the Figure workspace's page, on the schema
    frame.py              the frame: top bar, tool rail, one drawer, the preview
    tools.py              the tools' drawers (Layout, Layers, Look, Marks, Times, Runs)
    levels.py             the level switch: what an edit reaches
    drawer.py, controls.py
                          one generic drawer of schema rows; a widget per control kind
    find.py               Find over the schema
    grid.py, fill.py, runs.py, actions.py, entries.py, scene.py
                          the grid's actions, Fill panels, the Runs tool, adding layers and
                          annotations, a panel's entries, a 3D scene's items
    values.py, seriesvals.py
                          the Values table of a series or profile (your edits of its points)
    host.py, parts.py     what the controls ask of the figure (fields, runs); small widgets
    layer.py              the same drawer on one viewer layer (the map's and section's)
  shell/                  the editor on the document, without the page's widgets
    nodes.py              the places an edit can be made at, and their names
    docedit.py            changes to a document: layers shared or a panel's, what differs,
                          heights, time zero, filling panels, the grid, size (no widgets)
    bars.py               which colorbar speaks for a layer, and its settings
    placing.py            clicks and drags in the preview
    exportview.py, multirun.py
                          the Export dialog; saving for other runs
    scrub.py, vision.py   the preview's time slider and colour-vision preview
    frame.py              FigureShell: the document, undo, the preview
  editor.py               FigureEditor: what the shell works with, one mixin a module below
  choices.py              the choice lists ({shown: saved}) of the schema's controls
  style.py, scene.py      editor mixins: templates; what a scene takes from the viewer
  runs.py                 editor mixin: runs a figure could add, track words; AllFields
  sources.py              editor mixin: new figures from the viewer's tools, a new panel's
                          entries (their data: render.py)
  export.py               editor mixin: saving, reopening, autosave
  quick.py                editor mixin: the New dialog
  anim.py                 editor mixin: animations
  click.py                the preview image widget; where clicks land
  combo.py                figures of parts, an older form: combine, for conversion and tests
  times.py                helpers for model times and typed heights

tests/                    pytest suite: core/, and a folder per data-type package
docs/                     these pages
```

A mixin's methods run as the Viewer's (or the editor's) own: they use its widgets and
state through `self`. New features go in the mixin they belong to, or a new one added to
the class's bases.

## Adding a data type

A data type is a package of its own, found through an entry point; nothing in the core
changes. `tools/new_datatype.py <name>` starts one from the worked example
(`packages/example`). The walk-through, what a data type must provide, the extension API
and its version, and the conformance check `atmo3d.testing.check_datatype` are in
[Writing a data type](datatypes.md).

## Adding a derived field

Derived fields are defined in `atmo3d/core/fields.py` (`_make_fields`) as `FieldDef`s: a
name, label, units and menu group, a default colormap and range, the fields it needs
(`deps`) and a function of them (`func`). They then appear in every
field menu (map, section, 3D, series, figures). A dep can be a derivative of a native
field (`"ddz.winterp"`, `"ddx.uinterp"`: per metre, as the Derivative select gives it), as
for the vorticity tendencies; the field is then computed from whole levels, and series
read the points just outside their region. A *column field* (`layer=(z0, z1)` km AGL) is
2D from 3D natives: its `func` gets each input on the levels of the layer only
(`(levels, ny, nx)`) and their thickness in it, `c["dz"]` (m), as for updraft helicity,
with their heights `c["zk"]` and the layer top `c["top"]` (km); `edges=True` adds the
level just outside each end (thickness 0) for interpolating to the bounds, as the bulk
shear and helicity do (`at_height`, `layer_points`). The series worker then reads just
those levels. `costly=True` marks a column field that is slow per column (the parcels
of `thermo.parcel_columns`): it is computed on every `column_stride(run)`-th column,
and its `func` gets `c["memo"]`, a dict shared by the fields of one time (so SB CAPE,
SB CIN and STP lift the SB parcel once), and `c["threads"]`.

A field only one person needs does not have to be built in: it can be an expression in
their own file ([Your own derived fields](guide/user-fields.md)). Build one in when
others will use it, or when an expression cannot write it (a column field, a parcel).

### Checklist for a new derived field

Every built-in field is reviewed before it is listed. A field not in `CONFIRMED` is listed
only among the hidden fields, marked *(unverified)*, and `test_confirmed_matches_the_fields`
fails until it is added. A pull request that adds a field has:

1. **The equation and its source**: in the pull request, the equation as coded and the
   paper, textbook or model code it comes from (with the page or line), and the
   constants it uses (the model's own κ, Rd, cp where they differ).
2. **Its inputs in raw units**: a `func` gets natives as the files store them (qv in
   kg/kg, p in Pa) and derivatives per metre. Name inputs by role (`theta`, `qv`), not by
   one model's names, so every data type that has them gets the field.
3. **An analytic test** in `tests/core/test_derived_analytic.py`: synthetic inputs whose
   answer is known by hand (a uniform lapse rate, a circular hodograph), not the code's
   own output fed back. Include a sign or an edge case: zero, a negative, a missing
   optional input.
4. **A `note`**: what it leaves out or assumes, in a sentence ("Over liquid water at
   every temperature").
5. **A row in [Derived fields](guide/derived-fields.md)**: name, label and units, the
   equation as coded, inputs, and the note word for word
   (`test_docs_page_lists_every_field_and_note` checks both).
6. **Its name in `CONFIRMED`** (`core/fields.py`), added once the review agrees with the
   equation and the test.
7. **A line in [Changes](changelog.md)** under *Unreleased*.

The reviewer checks the equation against its source, the units at each step, and that
the test's answer was worked out independently of the code.

## Adding a vector

The vectors the map, the cross-section, the 3D scene and figures can draw are the
entries of `VECTORS` in `atmo3d/core/vectors.py`: a key, a label, units, the names of
its x, y and vertical component fields, and a typical magnitude (the default reference
arrow). The component fields must exist in the field catalog (add them as derived fields
if they do not, as for `bgen_x` and `bgen_y`). A vector is offered only when the run has
its components. Also add its arrow units to `KEY_UNITS` in
`atmo3d/figures/draw/layers.py`, because exported figures draw their key arrows without
the viewer.

## Building the documentation

The site is built by MkDocs (Material theme) from `README.md` and `CONTRIBUTING.md` (the
home page and *Contributing*, made by `docs/hooks/readme.py`, so each has one source) and
`docs/`, with the pages listed under `nav` in `mkdocs.yml`:

```bash
pip install "mkdocs>=1.6,<2" "mkdocs-material>=9.5,<10"
mkdocs serve           # preview at http://127.0.0.1:8000
mkdocs build --strict  # what the GitHub Actions workflow runs
```

`--strict` turns warnings into errors, so a link to a missing page, or a page missing from
`nav`, fails the build. A new page needs an entry in `nav`. Link between pages with
relative paths (`soundings.md#comparing-places-and-times`); anchors are the lower-case,
hyphenated headings. The workflow in `.github/workflows/docs.yml` publishes on a push that
changes `README.md`, `CONTRIBUTING.md`, `docs/` or `mkdocs.yml`.

When behaviour changes, change the page that describes it in the same commit, and add a
line to [Changes](changelog.md).

## Maintaining the repository

How a contributor works is in [Contributing](contributing.md). This section is the
maintainer's side: who can do what on GitHub, and how a release is made.

### Branch protection

`master` is protected: a change needs a pull request, the `test` check (the job of
`.github/workflows/tests.yml`) passing, and a code owner's approval. When a pull request
changes nothing the path filter tracks (docs only, say), the `test` job is skipped, and
GitHub counts a skipped required check as passed.

GitHub never lets the author of a pull request approve it, so while the maintainer is the
only code owner, their own pull requests can merge only by the admin bypass. Leave
*Do not allow bypassing the above settings* (`enforce_admins`) off until there is a second
code owner, then turn it on, so the maintainer's changes are reviewed too.

### Adding a collaborator

Contributors do not need any access: they fork, and open pull requests from the fork.
Give someone access to the repository only when they will **review**, as the owner of a
data-type package:

1. *Settings → Collaborators → Add people*, role **Write**. GitHub accepts a code owner's
   approval only from someone with write access.
2. Add them to that package's line in `.github/CODEOWNERS`, after the maintainer:

        /packages/<name>/          @bobbysaba @their-github-name

   Any one owner on the line can approve a change there. Later lines win, so a package's
   line must come after the `*` line, and a change that also touches `packages/core`
   still needs the core owner. Their package's tests (`tests/<name>/`) can have a line
   of its own the same way.
3. Make that change by pull request, like any other.

### Protecting release tags

Tags are not protected yet. Before a second person has write access, add a tag ruleset,
so that only the maintainer can create, move or delete a release tag: *Settings → Rules →
Rulesets → New ruleset → New tag ruleset*, target `v*`, enforcement *Active*, rules
*Restrict creations*, *Restrict updates* and *Restrict deletions*, and the maintainer
(the *Repository admin* role) in the bypass list.

### Releases

Versions follow `MAJOR.MINOR.PATCH`, the same in every package, with a matching git tag
(`v1.0.0`). To release:

1. On a branch, set the version in `pyproject.toml`, `packages/*/pyproject.toml` (all
   five, the example's too) and `__version__` in `packages/core/src/atmo3d/__init__.py`.
2. Move the *Unreleased* heading of [Changes](changelog.md) to the new version and date.
3. Run the full suite (`pytest`, on a compute node), merge the pull request, then tag the
   merge commit on `master` and push the tag:

        git switch master && git pull
        git tag v1.1.0
        git push origin v1.1.0
