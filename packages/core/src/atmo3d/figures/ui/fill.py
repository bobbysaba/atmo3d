"""Fill panels, in the Layout tool at the figure (docs-dev/figures-ui-plan.md, 3.3; the old plan
views' pane had it): the grid's rows and columns, what each steps through (times, runs, heights,
fields, sections) and its list.  Run once: it writes ordinary panels, which can be changed one by
one; run it again to change them all.  Then the panel titles from what differs, or none."""

import html

import panel as pn

from .. import spec as fg
from ..choices import GRID_DIMS, _near
from ..shell import docedit as de, nodes
from ..times import _heights, _nearest_t
from .parts import SECTION, _grid, note

ZMODES = {"km": "height", "Model level": "level"}


def fill_card(frame):
    """The Fill panels tool, in a fold: its widgets are made when it is opened."""
    folds = frame.folds
    card = pn.Card(title="Fill panels", collapsed=True, **SECTION)

    def on_fold(ev):
        folds["fill"] = not ev.new
        if not ev.new and not card.objects:
            card.objects = fill_objs(frame)

    card.param.watch(on_fold, "collapsed")
    if folds.get("fill"):
        card.collapsed = False
    return card


def fill_objs(frame):
    shell = frame.shell
    doc = shell.doc
    was = de.guess_fill(doc)
    rname = nodes.run_names(doc)
    run_opts = {f"{k + 1}. {rname[r['id']]}": r["id"] for k, r in enumerate(doc["runs"])}
    dims = {k: v for k, v in GRID_DIMS.items()
            if v != "sections" or len(doc.get("sections") or {}) > 1}
    rows = pn.widgets.IntInput(name="Rows", start=1, end=12, value=was["rows"])
    cols = pn.widgets.IntInput(name="Columns", start=1, end=12, value=was["cols"])
    row_dim = pn.widgets.Select(name="Rows are", options=dims, value=was["row_dim"])
    col_dim = pn.widgets.Select(name="Columns are", options=dims, value=was["col_dim"])
    run = pn.widgets.Select(name="Run", options=run_opts,
                            value=was["runs"][0] if was["runs"] else doc["runs"][0]["id"])
    runs = pn.widgets.MultiChoice(name="Runs (blank: all)", options=run_opts,
                                  value=was["runs"] if len(was["runs"]) > 1 else [])
    time = pn.widgets.Select(name="Time", options=shell.time_opts(0))
    every = pn.widgets.IntInput(name="Every nth output", start=1, end=100,
                                value=_every(shell, was, run.value))
    heights = pn.widgets.TextInput(name="Heights (e.g. 1, 3, 6 or 1:6:1)", value=", ".join(
        f"{z:g}" for z in was["heights"]) or "1, 3, 6")
    zmode = pn.widgets.Select(name="Heights in", options=ZMODES, value=was["zmode"])
    names = {f"{shell.fields[f].label} [{f}]": f for f in shell.fields.defs}
    fields = pn.widgets.MultiChoice(name="Fields (each panel's fill)", options=names,
                                    value=[f for f in was["fields"] if f in names.values()])
    go = pn.widgets.Button(name="Fill the panels", button_type="primary", height=32,
                           margin=(6, 4))
    said = pn.pane.HTML(margin=(2, 4), sizing_mode="stretch_width")
    titles = pn.widgets.Button(name="Titles from what differs", button_type="light",
                               button_style="outline", height=30, margin=(6, 4))
    clear = pn.widgets.Button(name="Clear the titles", button_type="light",
                              button_style="outline", height=30, margin=(6, 4))

    def used():
        return [d for d in (row_dim.value, col_dim.value) if d != "none"]

    def first_run():
        return (runs.value or list(run_opts.values()))[0] if "runs" in used() else run.value

    def show(*ev):
        on = used()
        run.visible = "runs" not in on
        runs.visible = "runs" in on
        heights.visible = zmode.visible = "heights" in on
        fields.visible = "fields" in on
        every.visible = "times" in on
        time.name = "First time" if "times" in on else "Time"
        opts = shell.time_opts(de.run_index(shell.doc, first_run()))
        cur = time.value
        time.options = opts
        if opts:
            time.value = opts[next(iter(opts))] if cur is None else _near(opts, cur)

    def steps_of(d):
        """The list of one dimension, as long as it can be used."""
        nr, nc = int(rows.value or 1), int(cols.value or 1)
        n = nc if d == col_dim.value and row_dim.value != "none" else \
            nr if d == row_dim.value and col_dim.value != "none" else nr * nc
        if d == "times":
            tl = list(shell.time_opts(de.run_index(shell.doc, first_run())).values())
            at = tl.index(_nearest_t(tl, time.value))
            step = int(every.value or 1)
            return [tl[at + step * k] if at + step * k < len(tl) else None for k in range(n)]
        if d == "runs":
            return list(runs.value) or [r["id"] for r in shell.doc["runs"]]
        if d == "heights":
            return _heights(heights.value)
        if d == "fields":
            return [fg.layer_defaults("fill", shell.fields, f, 1.0) for f in fields.value]
        return list(shell.doc.get("sections") or {})

    def bad(text):
        said.object = f'<div class="cv-status" style="color:#f87171">{html.escape(text)}</div>'

    def on_go(e):
        nr, nc = int(rows.value or 1), int(cols.value or 1)
        if row_dim.value == col_dim.value != "none":
            bad("Rows and columns can't step through the same thing.")
            return
        try:
            steps = {d: steps_of(d) for d in used()}
        except ValueError as err:
            bad(str(err))
            return
        done = []

        def apply(d):
            done.append(de.fill_panels(
                d, nr, nc, row_dim.value, col_dim.value, steps, run=first_run(),
                time_s=None if "times" in steps else time.value, zmode=zmode.value))
            fields_colorbar(d, row_dim.value, col_dim.value)
            if len(used()) == 2 and not any(p.get("title") for p in de.panels_of(d, "plan")):
                de.auto_titles(d, shell.fields)  # (rows and columns, named)
        frame.fill_said = None  # (until the edit's showing is done)
        shell.edit(apply, node=nodes.FIGURE)
        made, gone = done[0]
        frame.fill_said = f"{made} panel{'s' if made != 1 else ''} filled" + (
            f"; {gone} no longer on the grid (Undo brings them back)." if gone else ".") + (
            " Panels of other kinds with no room are set aside; see above."
            if shell.doc.get(de.OFF_GRID) else "")
        frame.show(nodes.FIGURE)

    def on_titles(e):
        shell.edit(lambda d: de.auto_titles(d, shell.fields), node=nodes.FIGURE)

    def on_clear(e):
        def apply(d):
            for p in de.panels_of(d, "plan"):
                p["title"] = ""
                p.pop("rowlabel", None)
        shell.edit(apply, node=nodes.FIGURE)

    for w in (row_dim, col_dim, run, runs):
        w.param.watch(show, "value")
    go.on_click(on_go)
    titles.on_click(on_titles)
    clear.on_click(on_clear)
    show()
    if was["times"]:
        time.value = _near(time.options, was["times"][0])
    text = getattr(frame, "fill_said", None) or ""
    frame.fill_said = ""
    said.object = f'<div class="cv-hint">{html.escape(text)}</div>' if text else ""
    frame.fill_ws = dict(rows=rows, cols=cols, row_dim=row_dim, col_dim=col_dim, run=run,
                         runs=runs, time=time, every=every, heights=heights, zmode=zmode,
                         fields=fields, go=go)
    return [note("Writes the panels once; no rule is kept. Run it again to change them all: it "
                 "replaces runs and times set by hand, layers stay."),
            _grid(rows, cols, row_dim, col_dim, run, (runs, 2), time, every, heights, zmode,
                  (fields, 2), n=2),
            go, said, pn.Row(titles, clear, margin=0)]


def _every(shell, was, rid):
    """The step between the panels' times, in outputs of a run."""
    ts = was["times"]
    if len(ts) < 2:
        return 1
    tl = list(shell.time_opts(de.run_index(shell.doc, rid)).values())
    if not tl:
        return 1
    a, b = tl.index(_nearest_t(tl, ts[0])), tl.index(_nearest_t(tl, ts[1]))
    return max(1, b - a)


def fields_colorbar(doc, row_dim, col_dim):
    """Panels of different fields can't share one colorbar: one per row, column or panel, as
    a grid of fields does."""
    if "fields" not in (row_dim, col_dim):
        return
    style = doc.setdefault("style", {})
    cb = style.get("colorbar") or {}
    if cb.get("mode", "shared") == "shared":
        mode = "row" if row_dim == "fields" and col_dim != "none" else \
            "col" if col_dim == "fields" and row_dim != "none" else "each"
        style["colorbar"] = dict(cb, mode=mode)
