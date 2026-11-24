"""The widget of a schema row's control (figures/schema: Control), for the drawer: make(row,
where, host) gives a Ctl, whose get() is what the row's as_.read takes and set() what its
as_.show gives.  A named control (a field menu, runs, times, a size) is a small component of
its own here; what it offers of the figure (its runs, their times, the fields) the host says:

  host.options(name, where)   a named list's {shown: saved}: "levelmodes", "vectors", "frames",
                              "sections", "layers:contour", "of:minus.run" (a run's times) ...
  host.fields                 the runs' fields (core.fields.Fields), or None
  host.runs()                 {label: run id}
  host.times(run_id)          {label: time (s)} of a run's outputs
  host.psets(where)           {label: choice} of the parcel sets that can be picked
  host.pvars(where)           {label: variable} of the parcels
  host.control(row, where)    (optional) a Ctl of the host's own, or None: the viewer's level
                              and height sliders (ui/layer.py)"""

import re

import panel as pn

from ...core.fields import deriv_name, deriv_options, split_deriv
from ...viewer.numinput import FloatInput
from .. import choices as C

WIDTH = 150  # (a control's width; a long one spans the drawer)


def _opts(options):
    return dict(options) if isinstance(options, dict) else {str(v): v for v in options or []}


def _keep(opts, value, said="(this figure's)"):
    """A choice's options, with a value they lack (an older figure's) kept as one."""
    if value is None or value in opts.values():
        return opts
    return {**opts, f"{value} {said}": value}


class Ctl:
    """A control: its widget(s) in .widget, get() / set(v) its value, watch(f) f() on a change
    by hand."""

    def __init__(self, widget, get=None, set=None, parts=None):
        self.widget = widget
        self.parts = [widget] if parts is None else parts
        self._get = get or (lambda: widget.value)
        self._set = set or (lambda v: setattr(widget, "value", v))

    def get(self):
        return self._get()

    def set(self, v):
        self._set(v)

    def watch(self, f):
        for w in self.parts:
            w.param.watch(lambda ev: f(), "value")


def _number(c, label):
    w = FloatInput(name=label, start=c.start, end=c.end, step=c.step or 0.1, width=WIDTH,
                   placeholder=c.placeholder or "")
    return Ctl(w)


def _int(c, label):
    return Ctl(pn.widgets.IntInput(name=label, start=c.start, end=c.end, step=c.step or 1,
                                   width=WIDTH))


def _choice(opts, label):
    w = pn.widgets.Select(name=label, options=opts, width=WIDTH)

    def put(v):
        w.options = _keep(_opts(w.options), v)
        w.value = v
    return Ctl(w, set=put)


def _blank_choice(opts, label, placeholder):
    """A choice that can be left blank (saved: none): its first option says what blank is."""
    blank = f"— {placeholder or 'none'}"
    w = pn.widgets.Select(name=label, options={blank: ""} | opts, width=WIDTH)

    def put(v):
        w.options = _keep({blank: ""} | _opts(opts), "" if v is None else v)
        w.value = "" if v is None else v
    return Ctl(w, get=lambda: None if w.value == "" else w.value, set=put)


def _colour(c, label):
    pick = pn.widgets.ColorPicker(name=label, width=70)
    if not c.blank:
        return Ctl(pick)
    off = pn.widgets.Checkbox(name=c.placeholder.capitalize(), margin=(24, 4, 0, 4))

    def put(v):
        off.value = not v
        pick.visible = bool(v)
        if v:
            pick.value = v if str(v).startswith("#") else _hex(v)

    def get():
        pick.visible = not off.value
        return "" if off.value else pick.value
    return Ctl(pn.Row(off, pick, margin=0), get=get, set=put, parts=[off, pick])


def _hex(c):
    from matplotlib.colors import to_hex
    try:
        return to_hex(c)
    except ValueError:
        return "#000000"


def _field(c, label, host):
    F = getattr(host, "fields", None)
    if F is None:  # (no runs' fields known: the name typed)
        return Ctl(pn.widgets.TextInput(name=label, width=WIDTH))
    from ...viewer.fieldmenu import FieldSelect
    groups = host.field_groups() if hasattr(host, "field_groups") else F.groups()
    field = FieldSelect(name=label, groups=groups, width=210)
    if c.options != "deriv":
        return Ctl(field, set=lambda v: setattr(field, "value", v if v in F else field.value))
    deriv = pn.widgets.Select(name="Derivative", options={"None": ""}, width=100)

    def put(v):
        op, base = split_deriv(v or "")
        if base in F:
            field.value = base
        deriv.options = deriv_options(F[field.value]) if field.value in F else {"None": ""}
        deriv.value = op if op in deriv.options.values() else ""
    return Ctl(pn.Row(field, deriv, margin=0), get=lambda: deriv_name(deriv.value, field.value),
               set=put, parts=[field, deriv])


def _runs(label, host):
    """Every run, one, or some (saved: None, [id], [ids])."""
    runs = host.runs()
    one = pn.widgets.Select(name=label, options={"All runs": "*", **runs, "Several runs…": "+"},
                            width=WIDTH)
    some = pn.widgets.MultiChoice(name="Runs", options=runs, width=260)

    def put(v):
        one.value = "*" if v is None else v[0] if len(v) == 1 and v[0] in runs.values() else "+"
        some.value = [r for r in v or [] if r in runs.values()]
        some.visible = one.value == "+"

    def get():
        some.visible = one.value == "+"
        return None if one.value == "*" else list(some.value) or None if one.value == "+" \
            else [one.value]
    return Ctl(pn.Row(one, some, margin=0), get=get, set=put, parts=[one, some])


def _size(label):
    w = FloatInput(name="Width (in)", step=0.25, width=100)
    h = FloatInput(name="Height (in)", step=0.25, width=100)

    def put(v):
        w.value, h.value = (list(v or [8.0, 6.0]) + [6.0])[:2]
    return Ctl(pn.Row(w, h, margin=0), get=lambda: [w.value or 8.0, h.value or 6.0], set=put,
               parts=[w, h])


def _cell(label):
    names = ("Row", "Column", "Rows tall", "Columns wide")
    ws = [pn.widgets.IntInput(name=n, start=1, width=80) for n in names]

    def put(v):
        r, c, rs, cs = (list(v or [0, 0, 1, 1]) + [1, 1])[:4]
        for w, x in zip(ws, (r + 1, c + 1, rs, cs)):
            w.value = int(x)
    return Ctl(pn.Row(*ws, margin=0), get=lambda: [ws[0].value - 1, ws[1].value - 1,
                                                   ws[2].value, ws[3].value],
               set=put, parts=ws)


def _box(label):
    w = pn.widgets.TextInput(name=label, placeholder="x0, x1, y0, y1", width=220)

    def get():
        v = re.findall(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?", w.value or "")
        if len(v) != 4:
            return None
        box = [float(x) for x in v]
        if box[1] <= box[0] or box[3] <= box[2]:
            raise ValueError("the box needs x max above x min and y max above y min")
        return box
    return Ctl(w, get=get, set=lambda v: setattr(w, "value", ", ".join(
        f"{float(x):g}" for x in v) if v else ""))


def _times(label, host, where):
    from ..spec.tables import parse_times, times_text
    w = pn.widgets.TextInput(name=label, placeholder="30, 60, 90 or 30-120/15", width=210)
    outs = list(host.times(None).values())
    return Ctl(w, get=lambda: parse_times(w.value, outs)[0],
               set=lambda v: setattr(w, "value", times_text(v or [])))


def _table(c, label):
    from ..spec.panels import parse_table, table_text
    w = pn.widgets.TextAreaInput(name=label, rows=6, sizing_mode="stretch_width")
    axis = c.options or "time"
    return Ctl(w, get=lambda: parse_table(w.value, axis)[0],
               set=lambda v: setattr(w, "value", table_text(v, axis) if (v or {}).get("t")
                                     else ""))


def _storms(track):
    """The storms of a track file ([]: the viewer's, none, or one storm)."""
    from ...core import track as trk
    from ..runs import _track_path
    if not track or track == "viewer":
        return []
    try:
        return trk.storms(_track_path(track))
    except Exception:  # noqa: BLE001  (no such file yet, or not a track)
        return []


def _track(label, host, where):
    """A run's storm track: the viewer's (its own run), one of its track files, a path typed,
    or none; and the storm of the file followed (one of several).  Saved: {track, storm}."""
    from ..runs import TYPE_PATH, _track_options, _track_path
    from ..shell.docedit import MISSING
    track_of = getattr(host, "track_files", None)
    found, own = track_of(where) if track_of else ([], False)
    viewer = pn.widgets.Checkbox(name="Viewer's track", visible=own, margin=(5, 6, 8, 6))
    pick = pn.widgets.Select(name="Track file", options=_track_options(found),
                             sizing_mode="stretch_width", visible=bool(found))
    box = pn.widgets.TextInput(name="Track file path (blank: none)", sizing_mode="stretch_width")
    storm = pn.widgets.Select(name="Storm", options=[], sizing_mode="stretch_width",
                              description="Which storm of the track file this run's panels "
                                          "follow (the file holds several)")
    quiet = []

    def now():
        if viewer.value:
            return "viewer"
        if pick.visible and pick.value != TYPE_PATH:
            return pick.value
        return box.value.strip()

    def shape(track, keep=None):
        """The widgets for a track: which show, the storms it has (keep: the one picked)."""
        typed = track != "viewer" and bool(track) and _track_path(track) not in found
        pick.disabled = box.disabled = track == "viewer"
        box.visible = typed or not found or pick.value == TYPE_PATH
        names = _storms(track)
        storm.options = names
        storm.value = keep if keep in names else (names[0] if names else None)
        storm.visible = bool(names)

    def put(v):
        from ...core import track as trk
        v = v or {}
        track = v.get("track") or ""
        quiet.append(1)
        try:
            viewer.value = track == "viewer"
            typed = track != "viewer" and bool(track) and _track_path(track) not in found
            pick.value = TYPE_PATH if typed else ("" if track == "viewer" else _track_path(track))
            box.value = "" if track == "viewer" else track
            shape(track, trk.storm_name(v.get("storm") or ""))
        finally:
            quiet.clear()

    def on_track(ev):
        """A new track: the same storm when its file has it, else the file's first."""
        if quiet:
            return
        if ev.obj is pick and ev.new == TYPE_PATH:
            box.visible = True
        track = now()
        keep = storm.value
        if track == "viewer":
            keep = getattr(host, "viewer_storm", lambda: "")()
        shape(track, keep)

    for w in (viewer, pick, box):  # (before the drawer's watcher: the storms first)
        w.param.watch(on_track, "value")

    def get():
        track = now()
        if track == "viewer":
            s = getattr(host, "viewer_storm", lambda: "")()
        else:
            s = storm.value if storm.visible else ""
        return dict(track=track, storm=s or MISSING)
    ctl = Ctl(pn.Column(viewer, pick, box, storm, margin=0, sizing_mode="stretch_width"),
              get=get, set=put, parts=[viewer, pick, box, storm])
    return ctl


def _code(label):
    """Python code: a highlighted editor, and a plain box for a browser without internet (the
    editor comes from a CDN, so it can stay blank): both hold the same text; which one shows is
    remembered."""
    from ... import config
    editor = pn.widgets.CodeEditor(language="python", height=200, sizing_mode="stretch_width")
    plain = pn.widgets.TextAreaInput(
        name=label, height=200, sizing_mode="stretch_width",
        placeholder="e.g.\nax = axs[0]\nax.plot([-5, 5], [0, 0], 'w--', lw=1)\n"
                    "ax.text(0.5, 1.02, 'my note', transform=ax.transAxes)",
        stylesheets=["textarea { font-family: ui-monospace, Menlo, Consolas, monospace;"
                     " font-size: 12px; }"])
    box = pn.widgets.Checkbox(name="Plain text box (if the highlighted editor stays blank, e.g. "
                                   "without internet)",
                              value=config.state("figure_code_plain") == "1")
    copying = []  # (one box being given the other's text: not an edit of its own)

    def show():
        editor.visible, plain.visible = not box.value, bool(box.value)

    def on_box(ev):
        show()
        config.set_state("figure_code_plain", "1" if ev.new else "")

    def copy_to(other):
        def put(ev):
            if other.value != ev.new:
                copying.append(1)
                try:
                    other.value = ev.new
                finally:
                    copying.pop()
        return put

    editor.param.watch(copy_to(plain), "value")
    plain.param.watch(copy_to(editor), "value")
    box.param.watch(on_box, "value")
    show()
    ctl = Ctl(pn.Column(editor, plain, box, margin=0, sizing_mode="stretch_width"),
              get=lambda: editor.value or "", set=lambda v: setattr(editor, "value", v or ""),
              parts=[editor, plain])

    def watch(f):
        for w in (editor, plain):
            w.param.watch(lambda ev: None if copying else f(), "value")
    ctl.watch = watch
    return ctl


def make(row, where, host):
    """The control of a schema row at `where` (the host's own, host.control, first: the
    viewer's level slider)."""
    own = getattr(host, "control", None)
    if own is not None:
        ctl = own(row, where)
        if ctl is not None:
            return ctl
    c, label = row.control, row.label
    k = c.kind
    if k == "number":
        return _number(c, label)
    if k == "int":
        return _int(c, label)
    if k in ("choice", "layer"):
        opts = _opts(c.options) if not isinstance(c.options, str) else \
            dict(host.options(c.options, where) or {})
        return _choice(opts, label)
    if k == "multi":
        opts = _opts(c.options) if not isinstance(c.options, str) else host.options(c.options,
                                                                                    where)
        return Ctl(pn.widgets.MultiChoice(name=label, options=opts, width=300))
    if k in ("text", "levels", "panels", "xy"):
        return Ctl(pn.widgets.TextInput(name=label, placeholder=c.placeholder, width=WIDTH))
    if k == "longtext":
        return Ctl(pn.widgets.TextAreaInput(name=label, rows=4, sizing_mode="stretch_width"))
    if k == "code":
        return _code(label)
    if k == "toggle":
        return Ctl(pn.widgets.Checkbox(name=label, margin=(24, 4, 0, 4)))
    if k == "colour":
        return _colour(c, label)
    if k == "cmap":
        return _choice(_opts(C.FIG_CMAPS), label)
    if k == "panel":
        return _choice(_opts(C.PANEL_CHOICES), label)
    if k == "field":
        return _field(c, label, host)
    if k == "run":
        opts = host.runs()
        return _blank_choice(opts, label, c.placeholder) if c.blank else _choice(opts, label)
    if k == "runs":
        return _runs(label, host)
    if k == "time":
        of = c.options[3:] if isinstance(c.options, str) and c.options.startswith("of:") \
            else None
        opts = host.times(host.run_of(where, of))
        return _blank_choice(opts, label, c.placeholder) if c.blank else _choice(opts, label)
    if k == "times":
        return _times(label, host, where)
    if k == "pset":
        return _choice(host.psets(where), label)
    if k == "pvar":
        return _blank_choice(host.pvars(where), label, "set colour")
    if k == "size":
        return _size(label)
    if k == "cell":
        return _cell(label)
    if k == "box":
        return _box(label)
    if k == "table":
        return _table(c, label)
    if k == "track":
        return _track(label, host, where)
    if k == "values":  # (a series' or profile's values and your edits: the host's table)
        table = getattr(host, "values", None)
        if table is not None:
            return table(row, where)
        return Ctl(pn.pane.HTML('<div class="cv-hint">Its values and your edits of them: the '
                                "Values table.</div>"), get=lambda: None, set=lambda v: None,
                   parts=[])
    raise ValueError(f"{row.id}: no control of kind {k!r}")
