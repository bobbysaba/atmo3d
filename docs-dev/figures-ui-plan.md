# Plan: a new Figure workspace (viewer layout + grid first), and a smaller figures package

Status (2026-11-23): decisions answered (below); Phase 0 started on branch `figures-ui`
(nothing committed yet). 0.1/0.2 built as a test rather than a tool (it needs the test
fixtures' demo data and Viewer): tests/core/figure_inventory.py collects,
tests/core/test_figure_inventory.py (one test per kind + the dialogs, so -n 4 helps) checks
or (ATMO3D_WRITE_INVENTORY=1) writes tests/core/figure_inventory/<part>.json;
`python tests/core/figure_inventory.py` writes docs-dev/figures-inventory.md from them. 1971 controls found, every
fold and layer row opened, one of each layer type, an inset and each annotation added. Not
covered: parcels layers (need a parcel set), map boundaries (the demo run has no map). Keyed run
done (Bobby's node, -n 4, 8.5 min): 1746 of 1971 controls mapped to the keys they write, 451
settings. Findings (0.3):
- Two controls for one setting in one place: only 3 real cases: `look.legend.where` ("Layer
  legend on" and "Legends on"), `runs[].track` ("Viewer's track", "Track file", "Track file
  path": one choice, three controls), `layer.on` (a row's on box and its "In panels" list).
  Six more are one control filling another in (a Width turns automatic size off; a vector
  field sets its scale; a series' region its automatic legend): kept.
- The same setting at several levels, by design: 280 of 366 settings (kind + panel 170;
  kind + panel + layer 44; layer + panel 35; figure + panel 27). Today each level is its
  own screen with its own copy of the control; in the new design each is one schema row and
  one control, the level switch says where it writes. This, and the per-kind screens behind
  it, is where the length is, not in duplicated controls.
- 99 controls rewrite more than 3 keys (they rebuild: a panel's type, the grid, a field's
  derivative, a difference or ensemble).
- 225 write nothing when changed alone: single-run choices (the demo figures have one run),
  Add menus, grid moves a 1 × 2 grid has no room for, the Export dialog's copies (written on
  Save). The schema rows for these come from the code (Phase 2), not from the inventory.
Phase 1 deferred (see there); Phase 0 left uncommitted; Phase 2 passed (full suite, Bobby);
Phase 3: frame, level switch and plan views built, first checkpoint passed; plan views,
cross-sections, insets and Find wholly in the frame, their old screens deleted (3.3 step 2,
passed); every other kind in the frame (3.3 step 3, passed 2026-11-23: full suite green); step 4
(annotations and placing, the grid's actions, the Runs tool, the Export dialog's rows) passed;
3.4 (the old editor deleted) passed; 3.5 (docs) passed; Phase 4 built (see there), checkpoint passed; Phase 5: go (decision 3,
2026-11-23), planned (see there); 5.1 built; 5.2 built; 5.3–5.6 built 2026-11-24, checkpoint
passed 2026-11-24 (Bobby: full suite green after two fixes, map and Cross-section used);
Phase 6 (mockup C, click a part of the preview) planned 2026-11-24 and built the same day
(uncommitted; see its "Built" notes), at its checkpoint.
Bobby's answers: 1 = no side-by-side (the old editor is deleted once the new one is
confirmed working); 2 = left to Claude: written to each panel of the row or column (no
format change), and a panel added to a row or column starts as a copy of its neighbour
there, so it picks up the row's settings; 3 = go (2026-11-23); 4 = keep
Find; 5 = 2.0.0.
Mockups (static HTML): /glade/derecho/scratch/rasaba/atmo3d_figure_mockups/ (A = Main.html,
B = GridFirst.html, C = Direct.html). Bobby chose A + B now, C later.

## Goal

1. **One feel.** The Figure workspace uses the viewer's layout: top bar, tool rail, drawers,
   time slider (mockup A). The tree and the inspector go.
2. **Grid first.** The grid is the editor: row and column headers carry what differs (run,
   time, field, height) and are picked like panels; the layers every panel draws are chips
   above the grid; a dot marks a panel's own change (mockup B).
3. **Nothing lost.** Every setting the editor offers today is still offered, at every level
   it can be set at today (figure, kind, panel, layer, inset), checked by a test.
4. **Less code.** Each setting is described once and drawn by one generic drawer; no
   per-kind settings screens, no hidden copies of widgets, one document format drawn.

What does not change: the figure document (version 3) and what is saved (image, spec,
script, data), so saved figures and templates open as before; drawing (`figures/draw`),
the data behind panels (`render.py`), `atmo3d render`, animations, Apply to other runs.

## Where the code is today (2026-11-23, lines)

| Area | Lines | Fate |
|---|---|---|
| Editor UI: `shell/`, `cards/`, editor mixins (`widgets`, `style`, `quick`, `sources`, `runs`, `scene`, `anim`, `export`, `editor`, `click`, `settings`) | 15 047 | rewritten; target 8–10k |
| of which per-kind settings screens (`planview`, `xsecview`, `entryview`, `seriesview`, `statsview`, `sceneview`, `looks`, `layerrow`) | 3 301 | replaced by one drawer |
| of which cards (`cards/`, settings in the old form behind `layerrow`'s adapter) | 3 541 | replaced by schema rows |
| Format translation (`draw/v2.py`, `draw/v3.py`, `combo.py`, `spec/docfile.py`) | 1 197 | mostly gone (Phase 1) |
| Drawing (`draw/`) | 5 127 | kept |
| Spec, data, export, batch (`spec/`, `render.py`, `batch.py`) | 5 789 | kept, smaller after Phase 1 |
| Whole `figures/` | 26 299 | target ~18–20k |

The targets are estimates; each checkpoint records the real count.

What makes the editor long, in short:
- each kind's settings screen re-implements "all panels / this panel / this layer";
- the cards predate the shell and work in the version-1 form; `layerrow.py` translates;
- `widgets.py` builds hidden widgets that `looks.py` and the Export dialog clone
  (`settings.Setting.widget` names an editor attribute, not a control);
- a document is resolved to a version-2 spec to draw, and one panel at a time to a
  version-1 spec to read its data.

## Guardrails (all phases)

- **Unchanged tests stay green.** The tests with no editor in them
  (`tests/core/test_figure_{doc,drawing,export,runs,spec,tablefile,video,layers}.py`) and
  the image baselines in `tests/baseline/` are not edited, except an import of a moved
  helper (`test_figure_spec.py` takes `parse_panels`, `panels_text` from
  `cards/distcard.py`; they move to `spec/` when the cards go). They prove a figure still
  draws the same.
- **Mixed tests** (`test_figure.py`, `test_figure_render.py`) draw through the editor's
  fixtures (`conftest.render`, `set_look`, `ed.shell`): the fixtures are moved to the new
  shell, the assertions kept; the few that walk the inspector's widgets are rewritten.
- **UI tests are about the old UI** (`test_figure_shell_*.py`; `test_figure_settings.py`,
  which tests today's settings table). They are rewritten with each phase against the new
  one, kept for what they check (an edit reaches the right panels, undo, saving), not for
  which widget does it.
- **The inventory test** (Phase 0) is the check behind "nothing lost".
- Work on a branch from master (`figures-ui`); a checkpoint ends each phase: Bobby looks at
  it running, runs the full suite (`pytest -n 4` on his node), and says go.
- Docs (`docs/guide/figures*.md`) and `docs/changelog.md` change with the phase that
  changes what a user sees.

## Phase 0: inventory (no change to the app)

0.1 `tools/figure_inventory.py`: open a set of figures (one of each kind, plus insets,
    annotations, several runs, a 3D scene), visit every node of today's tree, open every
    section, and record each control: its label, the document key it writes, the levels it
    can be set at, the kinds it applies to, its kind of control (number, choice and its
    options, text, colour, toggle, list). Output: `docs-dev/figures-inventory.md` (for
    reading) and `tests/core/figure_inventory.json` (for the test).
0.2 `tests/core/test_figure_inventory.py`: every inventory entry is a row of the new
    settings schema at the same levels (skipped until Phase 2 builds the schema; it is
    what each later phase must keep green).
0.3 Mark in the inventory what is the same setting offered in two places (likely: a
    layer's look on the kind's node and on a panel; colorbar settings on the bar's panel
    and in the look; the Export dialog's copies). Each becomes one row with several levels.

Checkpoint: Bobby reads the inventory; anything that should go anyway is struck there.

## Phase 1: draw the document directly (internal, invisible)

**Deferred (2026-11-23, Bobby).** It conflicts with the guardrails: exported scripts and
saved spec files hold the version-2 spec ("what is saved" does not change); tests not to be
edited draw version 2 or call upgrade / resolve / one_panel (`test_figure_spec`,
`test_figure_doc`, `test_legend`); reading a panel's data (`spec/base`, `panels`, `arrays`,
`sections`, ~2.8k lines) and `to_doc` run on the version-1 one-panel spec, so 1.2 means
rewriting data reading, for an estimated net saving of a few hundred lines. Phases 2-3 do not
depend on it: `resolve()` and `one_panel` stay the internal drawing and reading format.
Revisit after Phase 3, once the cards and `layerrow.py`'s adapter are gone.

1.1 `figdraw.draw` and `FigureData` take a version-3 document. Older figures (versions 1
    and 2, figures of parts) are converted once, when they are opened (`to_doc` already
    does it).
1.2 Panel data is read from the document's panel (with its runs and kind settings
    resolved), not from a one-panel version-1 spec (`one_panel`).
1.3 Delete what is left of `draw/v3.resolve`, the version-2 views in `draw/v2.py` that only
    drawing used, and the parts of `spec/docfile.py` that went through version 1. The
    old cards still need their adapter until Phase 3; it stays in `layerrow.py` until then.

Checkpoint: unchanged tests and baselines pass; line count recorded.

## Phase 2: one settings schema, one drawer

2.1 Extend `figures/settings.py` into the schema of every setting in the inventory. A row:
    document key; control (kind, options, bounds, step, unit), described in the row, not
    borrowed from a hidden widget; section; kinds it applies to; levels it can be set at
    (figure, kind, row/column, panel, layer, inset); default; help text. Layer settings
    (fill, contours, vectors, lines, series, soundings, distributions, ...) are rows too,
    grouped by layer type; what a row needs that a table cannot say (a field menu, a
    colour ramp, the A–B of a section, a series' values table) is one named control kind
    with its own small component.
2.2 `figures/ui/drawer.py`: one generic drawer that builds a section from schema rows at a
    level: reads values through the document's resolution (style → kind → panel), writes
    through `shell/docedit.py` (kept: it is the widget-free write path, and tested),
    shows "changed here / use the shared setting" and "Reset section" in one place.
    Controls are made only when their section opens (as today).
2.3 The Find box becomes a search over schema rows (`findview.py` shrinks to a list).
2.4 The inventory test turns on and passes.

Checkpoint: a test page draws every kind's drawer from the schema (no new shell yet).

**Progress (2026-11-23).**
- `figures/choices.py`: the choice lists (`{shown: saved}`) moved out of the cards, no widgets; the
  cards import them from there. The text conversions the cards and the schema share (`_xy`,
  `_panels_loose`, ...) are in `figures/schema/__init__.py`, the cards import them.
- `figures/schema/__init__.py`: `Control` (number, int, choice, multi, text, toggle, colour, code;
  named: field, panel, panels, xy, box, layer), `Row` (key, label, control, section, kinds,
  levels, default, as_, help, when, packed, also, writer), the table (`ROWS`, `BY_KEY`,
  `sections`, `rows_of`, `search` for Find), conditions (`WHEN`: a kind's own colorbar only beside
  another kind; an older figure's t0).
- `figures/schema/look.py`: every look setting, 285 rows (style, kinds, a panel's, an inset's;
  3D scenes' blocks, with their isosurface and vector items). Defaults as the old table had them;
  KEEP for the blocks every figure has whole (the drawer falls back to `spec.fresh_look`).
- `figures/schema/where.py`: `Where(level, kind, pid, iid, item)`; `value`, `write`, `own`,
  `take_back` (the old `looks.Scope` as functions; scenes through `docedit.write_scene`).
- `tests/core/test_figure_schema.py` (no viewer, ~2 s): rows well formed; every old-table row has
  one; reading and writing each shared row at every level makes the same document as the old
  Scope (291 row × place pairs); all 973 look writes of the inventory are rows at their level.
- `settings.py` (the old table) stays for the old editor until 3.4 deletes both.

- 2.1b `figures/schema/layer.py`: every layer setting, 228 rows by layer type (map layers: shared,
  a panel's, an inset's; entries: a panel's own; a parcel series and your own data are types of
  their own, `series:parcels`, `series:table`, `profile:table`). One key, a row per meaning
  (`layer.cmap~fill`, `layer.cmap~parcels`; `row_for(key, type)`). Conditions as the old cards'
  `show()` (`"style=barbs and !@xsec"`); fills as their handlers (`schema/fills.py`: a fill's field
  brings its colours, a vector its scale, a difference or ensemble its colours, a recipe its
  normal form, a parcel set its rule; a `Context` gives what they need of the runs). Written
  through `docedit.write_shared` / `write_panel` (and the colorbar's followers, `shell/bars.py`).
  `tests/core/test_figure_schema_layers.py` (38 tests): reading as a panel draws it, writing as
  docedit, take back, conditions, fills, and every layer write of the inventory a row of its type
  at its level (the series card's hidden other-kind controls named as such).

- 2.1c `figures/schema/doc.py`: the document's own settings, 75 rows (the figure's size, title,
  export, background, code, grid; a run's; a panel's title, row label, place, run and time, height,
  section, colorbar; an inset's; a section line's; an annotation's), read and written where they
  are, through docedit where it has a change of its own (`set_grid`, `set_shares`, `set_t0`,
  `set_height`, `place_panel`, `set_panel_colorbar`, `write_section`). A scene's parcel items, and
  the fills of a scene item (a new Vector its Ref. length; Colour by its units; a set picked).
  `tests/core/test_figure_schema_doc.py`.
- 2.2 `figures/ui/drawer.py` (+ `ui/controls.py`, a widget per control kind): a place's rows by
  section, each a fold built when opened; values as the document resolves them; a change is
  `where.write` through the host (who keeps undo); what is set here marked, ↺ to take it back,
  "Reset section"; a bad value said, not written. `rows_at(doc, where, part)` says which rows a
  place has. `tests/core/test_figure_drawer.py`: a drawer at every one of 57 places of a figure
  with a panel of every kind (`ui/samples.py`), every section open.
- 2.3 `figures/ui/find.py`: Find over the schema rows, each hit with the places in this figure it
  can be set at. The old `shell/findview.py` stays with the old shell (3.4 deletes both).
- 2.4 `tests/core/test_figure_inventory.py` checks the stored inventory against the schema, no
  viewer: every key a control wrote is a row at its level, kind and layer type; every control that
  wrote none is a row of its label, a row under another label, or a tool or dialog setting of the
  new shell (`figure_inventory.OFFERED_AS`: Phase 3's checklist). A planted missing row is caught.
  The coverage tests of the schema files moved into it.
- One fix found on the way: rows of a parcel series and of your own data were not offered (the
  raw layer type was compared, not `series:parcels`); a test now holds it.
- Moved out of widget modules (the old ones import them back): `known_cmap`, `_nice`
  (`choices.py`), `parse_panels`, `panels_text` (`schema`), the inset's place choices
  (`choices.INSET_LOCS`).

Checkpoint (Phase 2): `python tools/schema_drawers.py` (port 5007; it prints the SSH tunnel), and
the full suite (`pytest -n 4`).

## Phase 3: the new shell (mockup A)

3.1 The frame: top bar (workspaces, runs, undo/redo, Auto-redraw, Export), tool rail
    (Layout, Layers, Look, Marks, Times, Runs), one drawer at a time, the preview with its
    toolbar (Fit / Actual size, Colours, Click), the time slider; built from the viewer's
    pieces (`viewer/ui.py`: drawers, pills, rail), moved where both import them.
3.2 The level switch at the top of each drawer ("All plan views / Row / Panel f / Layer"),
    following what is picked in the preview; it replaces the tree.
3.3 Port the kinds onto the drawer, one at a time, deleting each kind's settings screen
    and cards as it moves: plan views and insets; cross-sections and sections;
    time–height and time series (with their own data and parcel series); soundings;
    distributions, profiles, joint distributions, azimuthal means, tables; 3D scenes.
    Then annotations and placing, the Export dialog, the New dialog, templates.
3.4 Delete the old shell (`shell/frame.py`, `treeview.py`, `nodes.py`'s tree, `inspector.py`,
    the per-kind views, `cards/`), `widgets.py`'s hidden widgets, and the adapter in
    `layerrow.py`.
3.5 Docs: `docs/guide/figures*.md` rewritten for the new layout; changelog.

Checkpoint after plan views (3.3, first kind), then after all kinds and the deletion.

**Progress (2026-11-23).** 3.1, 3.2 and the plan views of 3.3 built, not committed:
- `figures/ui/frame.py` (162 lines): the page. Top bar (a Runs button naming the runs, New,
  undo, redo, Auto-redraw, Redraw, Export), the rail (the viewer's `RAIL_BTN` look; the lit
  tool again closes its drawer), one drawer (title, level switch, body; 450 px, scrolls), the
  preview (Size, Colours, Click; the picture, the time slider, the status line). The shell
  (`shell/frame.py`) keeps the document, undo, drawing, the slider and the picked node; its
  page is now this, and it calls `frame.show(node)` where it showed the inspector and
  `frame.refresh()` after an edit made from what is shown.
- `figures/ui/levels.py`: the level switch. `where_of(doc, node)` (the old tree's nodes as
  schema places), `ladder(doc, node, last)`: Figure, All <kind> for each kind, and the last
  panel picked with its inset or layer (so up to All plan views and back is a click each);
  the line under it says what an edit reaches. Clicking a panel in the preview picks it, as
  before.
- `figures/ui/tools.py`: what each tool shows at a place. A schema row's tool goes by its
  section (`tool_of`: Layout = Figure, Grid, Spacing, Panel, Where it sits, Area; Marks =
  Annotations, Section line, Contour key, Maximum and minimum; Times = a panel's run and time,
  Animation; Runs = runs; the Export section stays the Export dialog's; layer and 3D-scene
  item rows are Layers'; the rest Look). Lists (shared layers, a panel's, an inset's,
  annotations) are `Item`s: a fold with ↑ ↓ ⧉ ✕ and its drawer, made when opened; what is open
  is kept by key across rebuilds and undo. Shared layers keep "Drawn in panels", "Keep apart",
  "↺ All as shared" and Copy a layer's look; a panel's shared layer says "changed here" and has
  "↺ Use the shared settings"; Layout has the size presets and Fit height, the figure type,
  the grid map, panels set aside, Add a panel, Fill panels, a panel's type, copy and remove,
  zoom insets.
- `figures/ui/host.py`: the drawer's host on the shell (the runs' fields, times, vectors and
  frames, sections, layers, parcel sets and variables, the map's view for a new box).
- Still from the old inspector's panes, as they are (they move with their kinds, 3.3, and go
  in 3.4): the grid's figure type, map, aside and add-panel; Fill panels; Copy a layer's look;
  adding an annotation and a zoom inset; section lines (with "use the map's A–B"); the Runs
  tool (track files, storms, time matching). The tree and the inspector are still built, off
  the page, so the old UI tests keep checking the edits they make until each kind's are
  rewritten.
- `tests/core/test_figure_frame.py` (18 tests, ~35 s): where_of and the ladder; every schema
  row in one tool; every plan-view setting of the figure, kind, panel and inset places offered
  by a tool (nothing lost); on the demo run: every tool at every level shows, the switch follows
  the pick, a shared layer's change reaches every panel and undoes, a panel's stays its own and
  is taken back, a panel's colour range under a shared colorbar is followed by the panels
  sharing it (as before: `shell/bars.py`), adding a shared layer opens it, a panel's look is
  its own, the rail closes its drawer, Marks adds an annotation open. `test_browser.py`
  expects one drawer column, and opens the Runs tool from the rail.
- Kinds other than plan views already get the generic drawer in Layers and Look (their rows
  are in the schema); their own actions (adding entries, a 3D scene's items) are not in the
  new frame yet: the next steps of 3.3.
- Not done for this checkpoint, on purpose: deleting `shell/planview.py` and the plan views'
  old tests. Cross-sections' screen is a subclass of it, and its tests still check edits the
  new frame makes through the same docedit functions; they are rewritten and the screen
  deleted once Bobby has used the new frame (so a change of design costs nothing to undo).
- Lines: 873 new (`ui/frame`, `levels`, `tools`, `host`); nothing deleted yet.

**First checkpoint passed (2026-11-23, Bobby: full suite green, likes the look).** His one
request, done: new figures start empty (`FigureSources._blank` is the page's figure; the New
dialog's fill starts at None (`quick.NO_FILL`), a fill chosen is the only layer; Add a panel's
first plan view or section of a figure with no layers draws nothing). `fg.default_spec` is
unchanged (the viewer's tools, templates, `atmo3d render` start from it). The tests are written
on the old start: `conftest._old_start` gives every test editor the old page figure and the
old New-dialog layers; `tests/core/test_figure_blank.py` checks the real start; one UI test
(`test_a_plan_view_joins_a_figure_of_soundings`) now expects the empty plan view.

Next (second half of 3.3): rewrite the plan-view and inset UI tests on the frame, delete
`shell/planview.py`'s screen (cross-sections' screen subclasses it: port them together or move
what they share), then the other kinds, annotations and placing, the Export and New dialogs,
templates; then 3.4 and 3.5.

**Step 2 (2026-11-23): plan views, cross-sections, insets and Find wholly in the frame**, not
committed:
- Deleted: `shell/planview.py`, `xsecview.py`, `insetview.py`, `sectionrow.py`, `findview.py`,
  `cards/seccard.py`, `layerrow.py`'s section and inset adapters (1 570 lines). The old
  inspector (still built off the page for the kinds not ported) shows a note at plan-view,
  cross-section and inset nodes (`inspector.PORTED`); `ScenePane` took the three methods it had
  from the plan pane.
- New: `ui/actions.py` (a new layer, Copy a layer's look, a zoom inset, sections: add, copy,
  remove, a panel's own, keep apart, the map's A–B; One per run; titles from what each shows),
  `ui/fill.py` (Fill panels), `ui/parts.py` (note, head, button). 473 lines.
- Sections are in Layers (they are what a cross-section draws): All cross-sections lists them
  above the shared layers (All plan views below, when a Section line layer draws one); a
  cross-section has its section (pick, + Section, Keep apart, its settings, the map's A–B) above
  its layers. One per run and + Cross-section panel are in Layout.
- Find is in the top bar (`ui/find.py` on the frame): hits over the drawer, the place of what is
  picked first (`Frame._prefer`); a hit opens its tool there (`frame.node_of`: a shared layer's,
  section's or annotation's fold open), its section open and the setting outlined, or says it
  isn't shown there; the Export dialog's open the dialog. `schema.search` ranks as the old Find
  did (name first) and reads colour/color, centre/center, colour bar/colorbar alike.
- What the inventory test had not caught, found by rewriting the tests (now rows or frame parts,
  tested): a panel's colorbar label, ticks and arrows (`panels[].colorbar.*`, writer "bar": read
  from and written to the bar the panel controls; `@controls its bar`, and the panel's Colorbar
  rows hidden while the figure has no bars); "Go to panel a" on a panel sharing another's bar and
  *Match the bar* on a layer whose colours differ; a fixed box starting from what the panel
  shows (look fill `area box`, `Context.shown`); an inset's "Centre east, north of the storm"
  (`look.domain.off`, inset); an inset's place and box marked and reset against a new inset's
  (`where.own`/`take_back`); "Set in a panel alone: panel c" under a kind's Look; the shared-range
  hint on a panel's area; "↺ Use the shared settings" following an edit (`Frame.live`); a
  drawer's sections open by hand staying open across undo (`Drawer(folds=)`, by place); at the
  top (the figure, a kind's own blocks) a section counting what differs from a new figure, its
  reset and ↺ going back to a new figure's (letters following the count again, your own code
  marked with no reset), and a kind's reset saying which panels keep their own.
- Tests rewritten on the frame (conftest: `at_tool`, `control`, `row_ctl`, `press`,
  `drawer_text`): `test_figure_shell_plan.py`, `_inset.py`, `_area.py`, `_find.py` (but the
  soundings' and distributions' neighbours, still the old inspector's), the cross-section
  tests of `_series.py` (+ One per run and a new section, the sections list), and the
  plan-node checks of `_shell.py`, `_mixed.py`, `_export.py` (bars), `_scene.py` (annotations
  in Marks). The inventory's plan and xsec parts are final (their old screens are gone:
  `test_figure_inventory.GONE`; the collector itself deleted in 5.6).
- Checked on the login node: every figure UI test file (`test_figure_frame`, `_blank`,
  `_drawer`, `_schema*`, `_inventory`, `_shell*`, `_render`, `_settings`): 600+ pass.
  `test_browser.py` not run (no Firefox here).
- `figures/` is 30 341 lines (the old editor of the other kinds still in it).

Checkpoint (step 2): `atmo3d --demo`, Figure: Find in the top bar; a plan view's Fill panels
(Layout, figure); a cross-section's section (Layers at the panel), One per run (Layout); a zoom
inset's Where it sits / Area (Layout) and Box and lines (Look); a panel's colorbar (Look). Then
`pytest -n 4`. Next after the go: soundings (entryview), then time–height and time series,
the stats kinds, 3D scenes; annotations and placing; Export and New dialogs; templates.

**Step 3 (2026-11-23): every other kind in the frame**, not committed; its checkpoint passed
(Bobby: full suite green, skips aside):
- Soundings, time–height and time series, distributions, profiles, joint distributions,
  azimuthal means, tables and 3D scenes are wholly in the frame: `ui/entries.py` (a panel's
  entries: add, move, copy, remove, own data, parcel series), `ui/scene.py` (a 3D scene's
  items), `ui/values.py` (the Values table, on the document's entry).
- Deleted: `shell/entryview.py`, `seriesview.py`, `statsview.py`, `sceneview.py`; `layerrow.py`
  trimmed to `CardHost` and the shared parts. The old inspector shows only the Figure and Runs
  nodes (off the page); the frame still takes the grid's actions, the Runs tool and adding an
  annotation from it.
- The schema gained the old cards' show-rules (a distribution's and joint's plot, the skew-T
  layout, how far the figure's legend reaches) and the own-data header fill.
- Tests rewritten on the frame, and `tests/core/test_figure_frame_kinds.py`.
- `figures/` is 29 719 lines.

**Step 4: the last of 3.3**: what the frame still takes from the old inspector moves into
`figures/ui/`: the grid's actions (figure type, panels set aside, add a panel, fill empty
cells, a panel's type, copy, remove: `ui/grid.py` from `shell/gridview.py`), the Runs tool
(`ui/runs.py`), annotations (adding one, and placing by clicking: `ui/actions.py`,
`shell/placing.py` off the inspector), the Export dialog's image rows from the schema
(`Export` section, generic drawer) instead of `looks.rows_of`. Then the inspector, the tree
(`treeview.py`, `nodes.tree_items`), `annotview.py`, `gridview.py` go, and the frame stops
building them. Checkpoint, then 3.4 (`cards/`, `looks.py`, `settings.py`, the hidden widgets).

Progress (step 4), not committed:
- `ui/grid.py` (the shell's `grid`: figure type, set aside, add a panel, fill empty cells, a
  panel's type, copy; the grid map), `ui/runs.py` (the Runs tool: each run's schema rows in a
  drawer, so Find reaches them; how runs line up; add, remove; what a run holds). The run's
  Track control is the old pane's whole picker (the viewer's track, a file found beside the
  run, a path typed, the storm in it: `controls._track`, `host.track_files`).
- Annotations: `actions.add_annotation` / `append_annotation`; placing one by clicking opens
  Marks with it open; a panel's own area dragged opens Layout at its Area. An annotation whose
  panels are all gone says so in its fold (the old row's "no such panel").
- Found in porting: an edit from the drawer that changes the figure's shape (grid rows and
  columns, a panel's cell or kind, the lists) only refreshed the controls, so the grid map and
  the panels set aside were stale; the frame now rebuilds its drawer then (`frame.shape`).
- The Export dialog's image rows are the schema's Export section in a drawer.
- Deleted: `shell/inspector.py`, `treeview.py`, `annotview.py`, `gridview.py` (1 004 lines);
  the shell builds neither tree nor inspector. `nodes.tree_items` stays (the tests list a
  figure's nodes by it) until 3.4. The inventory's collection from the old editor is gone with
  it: every kind's part is final; only the dialogs' can be collected again.
- `figures/` is 29 240 lines (from 29 719).

**3.4: the old editor deleted** (not committed):
- Gone: `cards/` (every card), `settings.py` (the old table), `shell/looks.py`, `shell/layerrow.py`
  (CardHost, Shared), `widgets.py`, the hidden widgets of `style.py` and `scene.py`,
  `runs.RunLists`, `nodes.tree_items`.
- Kept, moved: the layout helpers (`SECTION`, `_grid`, `_hint`, `_f`, `_auto`, `_chk`) to
  `ui/parts.py`; `_near`, `_dark`, `_hex` to `choices.py`; the parcel-set helpers
  (`parcel_source`, `parcel_sets`, `parcel_pick`) to `sources.py`; the Values table to
  `ui/seriesvals.py`, its host being `ui/values._Entry` itself; the save path, "Also the script
  and data" and the message line to `export._build_save`.
- A new figure's defaults (`settings.filled`) are `schema.filled`, from the schema's rows; the
  same spec as the old table's (checked before deleting it), and a test.
- Tests: the ones comparing the schema with the old table or Scope became round trips at every
  place (`test_figure_schema.py`: written, read back, own, taken back); the old table's own
  test file went; the tree's node lists are `conftest.every_node`; `conftest.put` takes a
  schema key.
- `figures/` is 24 819 lines (from 29 240 after step 4).

**3.5: docs** (not committed):
- `docs/guide/figures.md` (*The editor*: top bar, the rail's tools and what each holds, the level
  switch and what an edit reaches, marks and ↺, shared layers and sections, Find, the preview's
  bar), `figures-panels.md`, `figures-layers.md`, `figures-style.md`, `figures-export.md`: every
  "tree", "node", "inspector", "card" and "Mouse" now names the tool and level; the anchors are
  kept (links checked). Also `recipes.md`, `troubleshooting.md`, `parcels.md`, `shortcuts.md`.
  `changelog.md`: the "in progress" entry made final.
- In the code: the New dialog's notes (`kinds.py`) and the inset drag's hint and message
  (`shell/placing.py`) said "in the tree"; a new zoom inset dragged now opens Layout at it (as a
  panel's area does). Found missing while writing: *Your own code*'s **Plain text box** (for a
  browser that can't load the highlighted editor from the CDN; it writes no setting, so the
  inventory had no row for it): back in `ui/controls._code`, tested in `test_figure_drawer.py`.
- Not changed: `docs/developing.md` (Bobby's uncommitted edits) still lists
  `test_figure_shell.py` as "its tree, picking, edits and undo".

## Phase 4: grid first (mockup B)

4.1 Row and column headers above and beside the preview, labelled with what differs
    (from the grid's "panels differ in"); picking one sets the level switch to that row or
    column. Edits there are written to each panel of it (see decision 2).
4.2 The layer chips above the grid: the shared layers, each opening its drawer section;
    "+ Layer".
4.3 A dot on a panel with its own changes; the drawer lists them with "Use the shared
    ones" (today's override reset, from one place).
4.4 "What the grid varies" in the Layout drawer: rows differ in / columns differ in, and
    their values (today's Fill panels), editable in place.
4.5 Docs, changelog.

Checkpoint: Bobby makes two of his own figures (e.g. the tor/ntor × time grid of
`pub_figs.ipynb`) start to finish in it.

Built (2026-11-23, uncommitted):
- `ui/lines.py` (no widgets): a row or column is a node (`row:<r>`, `col:<c>`) picked like a
  panel; its members are the panels of the kind most of it is (a panel spanning lines is in
  each); `varies()` finds what each row (column) has one of and the rows (columns) differ in
  (run, time, height, first fill's field); `heads()` the headers from the drawn boxes;
  `own_changes()` / `use_shared()` a panel's changes to shared layers, own layers, own look;
  `copy_from()` decision 2's copy.
- `ui/levels.py`: `spread(doc, node)` the places a row or column's edit is written to;
  `where_of` a line's is its first panel's; the ladder offers the line picked last.
- `ui/drawer.py`: `Drawer(spread=...)` writes, takes back and resets at each place, marks a
  row its panels differ in with a dashed outline.
- `ui/gridfirst.py`: each tool at a row or column (Layout: what it varies, its share, + Panel
  in this row; Layers: its panels' own changes; Look, Times: spread drawers; Marks, Runs: the
  figure's), the own-changes list (also at the end of a panel's Layers), the layer chips, the
  dots, *What the grid varies* (Layout at the figure, each line's value editable).
- `click.py` ClickImage: `heads` drawn in a margin above and left of the image (clicking one
  sets `head`), `dots`. `shell/frame.py` sets them in `_mark` (after each draw, pick and edit).
- `ui/grid.py`: a plan view or cross-section added at a given cell (Layout's Add at a free
  cell, + Panel in this row, Fill empty cells) is `lines.copy_from` its neighbour; other kinds,
  and the kinds' own *+ … panel* buttons and new rows/columns, as before (a sounding's entries
  are its own; *+ Cross-section panel* makes the y–z twin).
- Tests: `tests/core/test_figure_grid_first.py` (18). Not checkable here: the headers' and
  dots' JavaScript (no browser, no Node): look at it running.
- Docs: figures.md (the preview's headers, chips, dots; the switch), figures-panels.md
  (*Picking a row or a column*, *Filling a grid*), changelog.

## Phase 5 (decision 3: go, 2026-11-23): one layer component for the viewer and the figures

The viewer's layer drawers (Map: the fill, More fills, Contours, Vectors; the Cross-section
tool's the same four) and the figure's layer section show the same settings; they become one
component on the schema, with the figure-only rows hidden in the viewer. 3D (isosurfaces,
3D vectors, streamlines, the floor) is not in it: no figure layer matches it closely enough
(a 3D scene's own rows, `schema/look.py`, are a later candidate).

### What differs today (read from the code, 2026-11-23)

The two hold and draw layers differently: the viewer holds a layer as a dict of live widgets
(`viewer/widgets.py`, `xsec.py`), reads them when it draws with Bokeh (`mapview._map_spec`,
`xsec`), and saves them as a session (`session.py` FILL_KEYS, OV_KEYS, VEC_KEYS, MAIN_FILL,
XS_*); a figure holds a layer as a document dict (`layers[id]`), edited through
`schema.where`, drawn with matplotlib.

| Setting | Viewer (session key: values) | Figure (layer key: values) | Proposed |
|---|---|---|---|
| on | `on` | `on` | same |
| field | `var` (+ main fill's `op`: derivative) | `field` (derivative in the name, `split_deriv`) | figure's; the viewer's `op` becomes the name's derivative |
| level | `mode` height/msl/level/colmax/colmin, radar sweep/height/colmax/colmin; `level` | `mode` (levelmodes), `z` | figure's keys; the viewer's level slider stays a control kind (sweeps, k) |
| draw as | `style` image/contourf | `style` mesh/contourf | figure's; viewer draws mesh as its image |
| colours | `cmap`, `rev` | `cmap`, `reverse` | figure's |
| range | `auto` + `vmin`, `vmax` | `vmin`, `vmax` (no auto) | viewer-only row `auto` (level "viewer") |
| contour intervals (main fill, contourf) | `nlev` | `nlevels` (colour steps, 0 smooth) | one key `nlevels`; the viewer's 0 means its 15 |
| opacity | `alpha` | `alpha` | same |
| clear outside range (more fills) | `clip` | none (`mask_below` is near) | viewer-only row |
| difference (main fill) | `diff` on/run/time ("prev") | `minus` run/time_s/grid | figure's block; "the output before" is a viewer-only choice |
| contour levels | `levels` | `levels` | same text form |
| contour colour, width | `color` hex, `width` | `color` (any matplotlib colour), `lw` | figure's keys; the viewer's colour picker writes hex, which matplotlib reads |
| dash negative | `negdash` | `neg_dashed` | figure's |
| vector | `q`, `frame`, `color` | `vector`, `frame`, `color` | figure's |
| vector height | `level` (km AGL) | `z` | figure's |
| vector look | `style` arrows/streamlines, `density` (arrows across, 8–50), `ref` (reference arrow) | `style` arrows/barbs/streamlines, `spacing` km, `scale`, `key`, `density` (streamlines) | viewer-only rows `across`, `ref` (different meanings, kept apart) |

Figure-only, hidden in the viewer: time window, z_fixed, mask_below, white_first, scale (log),
colorbar rows, ensemble, legend, contour labels, barbs, scale/width/key/arrowsize/barb_len.
(Later, one by one, as the Bokeh drawing learns them.)

### Steps

5.1 **The viewer level.** `Where(level="viewer")` (schema/where.py): its layer is a dict the
    viewer holds (no document); rows get `levels` including "viewer" where the viewer offers
    them; the viewer-only rows above (`auto`, `clip`, `across`, `ref`, the "prev" time) are
    rows at that level only. `levels`/the ladder never offer "viewer" in the figure. Tests
    (no viewer): every session key of FILL_KEYS/OV_KEYS/VEC_KEYS/MAIN_FILL/XS_* maps to a row
    at level viewer, round trip.
    Built (2026-11-23, uncommitted): `figures/schema/viewer.py`: `rows(role, kind)` (roles
    fill, more, contour, vectors; kinds plan, xsec), copies of the figure's rows with the
    viewer's labels, choices (no barbs; Pixels / Filled contours), conditions and defaults, plus
    VIEWER_ONLY (`auto`, `clip`, `across`, `stream_n`, `ref`); `new()`, `from_session()`,
    `to_session()`. `where.py`: at level "viewer" the document is the layer (layer_at,
    write_layer); `fills.py`: the viewer's fills (field: its colormap and range, the first fill
    back on Auto; difference: RdBu_r; vector: its reference arrow; Auto off: the range last
    drawn, Context.drawn). The figure's table (schema.ROWS) is unchanged. Changes to the table
    above: the viewer's one `density` is two keys, `across` (arrows) and `stream_n`
    (streamlines), so switching style keeps each; a viewer difference has no `grid` (it
    interpolates). Controls the viewer's host makes: `vlevel` (its level slider), `vheight`, a
    difference's run (options "viewer") and time (options "minus", with "prev").
    Tests: tests/core/test_viewer_layers.py (29, no viewer).
5.2 **One layer component** (`figures/ui/layer.py`, or `ui/` moved to a shared place): the
    generic Drawer on one layer dict with an `on_change(keys)` callback; used by the figure's
    layer section (unchanged look) and by the viewer.
    Built (2026-11-23, uncommitted): `figures/ui/layer.py`: `LayerDrawer(lay, role, kind, run=,
    fields=, on_change=, runs=, times=, drawn=, say=)` (`.panel`, `.refresh()` after the viewer
    changes the layer itself, `.ctl(key)`), on `LayerHost` (the layer is its document; an edit is
    made on a copy, written back into the same dict, then `on_change(keys changed)`). The figure's
    layer section is the same `Drawer`, unchanged. `Drawer(flat=True)`: no folds, the controls
    side by side (wrapping, as the viewer's rows), no marks, ↺ or reset. `controls.make` asks
    `host.control(row, where)` first: the viewer's level slider (range and name follow the mode:
    heights AGL/MSL, model levels, a radar's sweeps or height above it; `layer.level_range`), its
    vector height slider (both changed on let go, `value_throttled`, as the viewer's), and a
    difference's time (the outputs of the run it is taken from, as that run is now, after *the
    output before*). New fill `viewer mode` (Context.relevel): a mode change keeps the place (a
    model level's height, a height's level below it), as `_level_pair` did. Not the same as the
    viewer today: opacity and line width are number boxes, not sliders (5.3 decides); the field
    menu lists every field for a cross-section's layers (its 3D-only list: 5.4).
    Tests: tests/core/test_viewer_layer_drawer.py (16, no viewer).
5.3 **The map's drawers on it.** The viewer holds `self.layers` (fill, more fills, contours,
    vectors) as layer dicts; `mapview._map_spec` and the restyle-only paths (opacity, colormap,
    colour, width: no new data) read them, from a key → redraw table; Add/remove rows as today
    (the limits 3/6/3 kept). Toolbar quick controls (field, level, style) write the same dict.
    Checkpoint: Bobby uses the map (`atmo3d --demo`, a radar run), full suite.
    Built (2026-11-23/24, uncommitted): `viewer/layers.py` (MapLayers mixin, `Layer`: a dict,
    its LayerDrawer, its row and ✕, `.last`); `self.map_fill` (skip on/field/mode/z: the
    toolbar's `fill_var`, `fill_op`, `fill_mode`, `fill_lvl` write them, `_on_bar_level`,
    `_on_fill_var` → `drawer.put("field")`), `fills`, `ovs`, `vecs` as Layers; `_map_spec`
    reads the dicts; `_drop_layer` for every row. No redraw table: every change redraws the
    map (the job reads from the cache, so a colour or an opacity costs no reading); add one
    only if the map feels slower. Opacity and line width stay number boxes (not sliders).
    `figures/sources.py` takes the range from `map_fill.last`. bench.py's map actions use
    `drawer.put`.
5.4 **The cross-section tool's on it** (xs fill, fills, contours, vectors).
    Built (2026-11-24, uncommitted): `xs_main` (kind "xsec", skip field: the toolbar's
    `xs_fill`, `_on_xs_fill` → `drawer.put`), `xs_fills`, `xs_ovs`, `xs_vecs` as Layers
    (`_new_fill`, `_new_contour`, `_new_vec` shared with the map); `xs_spec` reads them;
    `_layer_place` / `_drop_layer` / `_layer_changed` by `o.kind`. The field menu of a section's
    layers lists the fields with heights (`LayerHost.field_groups`, asked by `controls._field`).
    Section vectors: *Arrows across* 8–60, default 28, as before (an override in LAYOUT).
    Deleted: the xs_* style widgets, `_wire_fill/_wire_overlay/_wire_vec`, `_layer_request`,
    `_on_xs_auto`, `_auto_toggled`, `_xs_range`, diff.py's `_diff_widgets`, `_wire_diff`,
    `_minus_spec`, `_minus_times` (`layers.minus_spec` of a layer instead).
5.5 **Sessions**: written as layer dicts (FORMAT 3); `session.upgrade` reads FORMAT 2 (the
    table above, in one function); tests/core/test_session.py's saved sessions still open.
    Built (2026-11-24, uncommitted): FORMAT = 3; `fill`, `fills`, `contours`, `vectors` (and the
    section's `fill`, `fills`, `contours`, `vectors`) are `V.saved(lay)` (the dict but type and
    role); no `diff` (a layer's `minus`). `session._layers_v3` (in `upgrade`, ver < 3) reads a
    FORMAT 2 session's into them with `V.upgraded` (what it had, nothing more; a difference off
    is `minus: None`, which `_put_layer` takes as none), so a layer put back keeps what the
    session lacks. `to_session` deleted; `from_session` kept for the upgrade. Tests:
    test_session.py `test_a_format_2_session_opens` (a 1.1.0 session written out by hand),
    test_viewer_layers.py `test_a_format_2_layer_upgraded` (the FORMAT 2 keys are now listed in
    the test).
5.6 **Clean up**: the viewer's per-layer widget code deleted (`_contour_widgets`,
    `_fill_widgets`, `_vec_row`, their wiring); docs (`docs/guide/` map and cross-section
    pages), changelog. Checkpoint: full suite, Bobby uses both.
    Built (2026-11-24): `_contour_widgets`, `_fill_widgets`, `_drop_row` deleted; `_vec_row`
    kept for the 3D vectors only (3D is out of this phase), its streamline branch gone. Docs:
    map.md (Draw as, Min/Max shown with Auto range off, *Drawn*, Streamline density as its own
    row), cross-sections.md, developing.md (layers.py, schema/viewer.py, ui/layer.py, the
    tests), changelog (two entries). Not run: any test (Bobby's instruction); one smoke script
    built a viewer, the map's and section's layers, a session round trip (equal), before the
    FORMAT 3 change. Tests to run first: tests/core/test_map.py, test_session.py,
    test_viewer_layers.py, test_viewer_layer_drawer.py, test_timing.py, tests/radar, then the suite.
    Bobby's suite run: 2 failed (a test's local `w` hid the helper; `_checked_layer` asked a
    list, CMAPS, for .values()), both fixed. The inventory's collector deleted
    (`test_write_inventory`, its 12 skips, and figure_inventory.py's screen walk): every old
    screen is gone, so the stored parts are final; the schema checks against them stay.

What is gained: one place to add a layer setting (a schema row), the same labels and
controls in both workspaces, the viewer's layer widgets (~600 lines of widgets.py, xsec.py,
session.py) replaced by rows.
Risk: the viewer's map is its most-used screen; its restyle-only fast paths must stay fast
(step 5.3's redraw table), and a radar run's sweeps must keep working.

## Phase 6: click a part of the preview (from mockup C, planned 2026-11-24)

Bobby asked what of mockup C can be adopted. Most of the ground is laid: a click on a panel
picks it (`shell/frame.py` `_on_click`, `nodes.pick_at` on `click.panel_boxes`), and Find's
`ui/frame.Frame.go_to(row, where)` already opens a setting's tool at its place, its section
open and the setting lit. What is missing is knowing which part of a panel was clicked.
Nothing here changes the document format or the drawing (scripts and saved figures as they
are): it is the preview's click handling plus a map of where each part was drawn.

6.1 A parts map (`click.py`, next to `panel_boxes`): `part_boxes(fig, spec, size_px, dpi)` ->
    [(box, panel or None, part)] for each panel's title, x/y axis labels, legend (from
    `ax.get_legend()` / `_cv_entries`), and the figure's suptitle and figure legend; boxes in
    the same fractions as `panel_boxes`, small parts first so they win over their panel.
    Each part names a schema row (title -> the panel's title row, ...). Tests: the boxes of a
    drawn figure hold the artists' extents; a click there gives the row.
6.2 Click a part: `_on_click` tries the parts map before the panel; a hit calls `go_to(row,
    where)` (the panel picked, its section open, the setting lit). A click elsewhere in a
    panel picks it as today; Click to (placing) still comes first.
6.3 Colorbars: record which panels each bar serves when it is drawn (`draw/figure.py`: one
    shared bar, per-group bars, a panel's own bar, `draw/layers.py`), e.g. `fig._cv_bars =
    [(cax, [panel ids], mode)]`. A click on one opens its colorbar section at the level that
    owns it (the panel; the row/column for groups; the figure for one shared bar).
6.4 The drawer's note on a shared part ("Shared by a and b. Its colours follow panel a's
    fill.") and Jump to links ("Panel a's fill", "All colorbars"): each link a `go_to`.
6.5 (optional, last) Hover outlines: dashed outline of the clickable part under the mouse, in
    `ClickImage`'s JS from the parts map (not browser-checkable here: no Firefox/Node).
6.6 Docs (`docs/guide/figures.md` and the panel/style pages: "click a title, label, legend or
    colorbar"), changelog under *Unreleased*.

Checkpoint: Bobby clicks each part in `atmo3d --demo` figures (one panel, a 2 x 2 grid with a
shared colorbar, a sounding), full suite. Version: 2.0.0 ships Phases 0-5 first; Phase 6 is
2.1.0 unless Bobby says otherwise.

### Built (2026-11-24, uncommitted)

- 6.1 `click.py`: `Part` (box, panel, part, panels, mode), `part_boxes`, `part_at`, and
  `watch_parts(fig)`. Text is laid out at the dpi it is drawn at, so reading extents after the
  save (as `panel_boxes` does for axes) put letters and y labels in the wrong place (checked on a
  plain figure saved at 80 dpi from a 100 dpi figure). The extents are read in matplotlib's
  `draw_event` instead: in savefig's last draw of a trimmed box the display pixels are the
  image's, so a box is just pixels / image size. The drawing marks what it drew:
  `ax._cv_tags` (panel letter, time, run, height labels: `_decorate`), `ax._cv_rowlabel`,
  `legend._cv_block` (a legend drawn from the block's settings, not the panel's own),
  `ax._cv_own_bar` (joint / azim, `draw/lines.py`).
- 6.2 `shell/frame.py`: `_on_click` tries Click to, then `part_at(self._parts)`, then the panel.
  `ui/clicked.py` (no widgets) says what a part opens: `PARTS` maps a part to a schema row; the
  place is the row's place nearest the panel (`nearest`: the panel, its kind, the figure, from
  `find.places`); a panel's own legend is its kind's (`LEGEND_OPTS`), an own colorbar
  `look.joint/azim.cbar_label`. `Frame.go_part` opens it through `go_to`, which takes `node=`
  (a row or column) and `said=` (the note: *Clicked the x label: …*, *Jumped to: …*).
- 6.3 `draw/layers.note_bar` records each bar on the root figure, `fig._cv_bars = [(cax, ids,
  mode)]` (`_colorbars`: shared, row, col, each; `_draw2`'s one bar: "figure").
  `clicked.bar_target` takes the members from `shell/bars.bar_of` (controlling panel first, and
  whether colours follow): a named group -> its first panel's *The bar it shares*; row / col ->
  that row or column node, *Colorbar label*; one panel's -> the panel's *Colorbar label*; else
  the figure's *Colorbars*.
- 6.4 the note and links show under the level switch (`Frame.links`, cleared by `show`): *Shared
  by panels a, b and c. Its colours follow panel a's fill.*, **Jump to: Panel a's fill**
  (`layer.cmap` of its first bar fill), **Jump to: All colorbars**, **Jump to: Panel a's
  colorbar** (whichever is not where the click went).
- 6.5 `ClickImage.zones` ([l, r, t, b, words]): the part under the mouse dashed-outlined, its
  words as the image's tooltip; none while Click to is on (`_show_image`). JS not
  browser-checked (no Firefox/Node here).
- 6.6 `docs/guide/figures.md` (The editor), `figures-style.md` (Colorbar), changelog.
- Not clickable: a 3D scene's colorbars, inset parts (a click in an inset picks it, as before),
  the contour key, annotations (Marks; *Drag: move an annotation* moves them).
- Tests: `tests/core/test_figure_parts.py` (parts map on a plain figure; targets on small
  documents; in the shell: a title, an x label, the shared bar and its jump, a bar per row,
  Click to first, zones). NOT run here. Run first: `pytest tests/core/test_figure_parts.py
  tests/core/test_figure_shell.py tests/core/test_figure_shell_find.py
  tests/core/test_figure_shell_scene.py tests/core/test_figure_shell_inset.py`, then the suite.

## Later: hover-free extras of mockup C

The breadcrumb (Figure > row > part) is mostly the level switch already; anything of mockup C
not in Phase 6 waits.


## Decisions for Bobby

1. **Old and new editor side by side?** Recommended: no. The new shell lives on the branch
   and replaces the old one when every kind is ported; master keeps the old one for real
   work meanwhile. (A setting to switch means keeping both working.)
2. **Row/column edits: stored, or written to the panels?** Recommended: written to each
   panel of the row or column, so the document format does not change. (Stored row and
   column settings would let a panel added later pick them up, at the cost of a format
   change.)
3. **Phase 5: share the layer component with the viewer?** Recommended: decide at Phase 4's
   checkpoint, once the schema exists.
4. **Keep the Find box?** Recommended: yes, as a search over the schema (cheap after
   Phase 2).
5. **Version at the end:** 2.0.0 (the editor is new; saved figures still open) or 1.2.0.
   Recommended: 2.0.0.
