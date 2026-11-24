"""One layer component (docs-dev/figures-ui-plan.md, Phase 5.2): the generic drawer
(ui/drawer.py) on one of the viewer's layers, a dict in a figure layer's form
(schema/viewer.py), with what its controls offer of the viewer's run.  The figure's layer
section is the same drawer on the document (ui/tools.py); this is it with no document.

  LayerDrawer(lay, role, kind, run=, fields=, on_change=, ...)
      .panel        its controls, side by side (a flat drawer: no folds, nothing inherited)
      .refresh()    after the viewer changed the layer itself (its toolbar's field, level)
      .ctl(key)     the control of a layer key ("field", "z", ...), or None
      .put(key, v)  a key set as its control would (with what it fills), from elsewhere
      .rerun(run, fields)  another run of the same grid shown in place
  skip: layer keys with no control here (the viewer's toolbar has them)
  An edit is written to `lay` in place (the viewer's dict stays the one it holds), then
  on_change(keys) with the top keys of it that changed (a fill writes some beside its own:
  a new field's colours and range).

What the viewer gives (each optional; none: what a figure's test page has):
  run         the run (core.run): its levels, heights, sweeps, frames
  fields      its fields (core.fields.Fields)
  runs()      {label: path} of the runs a difference can be taken from
  times(rid)  {label: time (s)} of a run's outputs (None: this one's)
  drawn()     (lo, hi) of the range the layer was last drawn with (Auto range off starts there)
  say(text, err)"""

import copy

import numpy as np
import panel as pn

from ...core import vectors
from ..schema import fills, viewer as V, where as W
from . import controls, drawer as D

PREV = "the output before"


# ------------------------------------------------------------ the viewer's levels
def _ground(run):
    """(mean, highest) ground height (km MSL) of a run whose levels follow the terrain."""
    if not getattr(run, "terrain", False):
        return 0.0, 0.0
    hgt = run.terrain_height()
    return float(np.mean(hgt)), float(np.max(hgt))


def _ztop(run):
    return float(np.floor(run.ztop * 10) / 10)


def level_range(run, mode):
    """(start, end, step, name) of the level slider of a layer in `mode` (a radar's: sweeps)."""
    ztop = _ztop(run)
    if not getattr(run, "grid", True):
        if mode == "sweep":
            return 0, max(1, int(getattr(run, "nsweeps", 1))) - 1, 1, "Sweep (0: lowest)"
        return 0.0, ztop, 0.05, "km above the radar"
    if mode == "level":
        return 0, run.nk - 1, 1, "Model level k"
    if mode == "msl":
        return 0.0, float(np.floor((ztop + _ground(run)[1]) * 10) / 10), 0.05, "km MSL"
    return 0.0, ztop, 0.05, "km AGL"


def relevel(run, old, new, z):
    """A level z of mode `old` as the same place in mode `new` (a model level's height, a
    height's level below it; from a column max or min: 1 km, the lowest level or sweep)."""
    lo, hi, _, _ = level_range(run, new)
    if not getattr(run, "grid", True):
        out = 0.0 if new == "sweep" else (float(z) if old == "height" and z is not None else 1.0)
        return float(min(max(out, lo), hi))
    ground = _ground(run)[0]

    def agl(m, v):
        return v - ground if m == "msl" else v
    if new == "level":
        out = run.level_weights(agl(old, float(z)))[0] if old in ("height", "msl") \
            and z is not None else 0
        return float(out)
    if old == "level" and z is not None:
        h = float(run.z[int(z)])
    elif old in ("height", "msl") and z is not None:
        h = agl(old, float(z))
    else:
        h = 1.0
    return round(float(min(max(h + ground * (new == "msl"), lo), hi)), 2)


class _Slider(controls.Ctl):
    """A slider's control: a change is its value let go (value_throttled), as the viewer's."""

    def watch(self, f):
        for w in self.parts:
            w.param.watch(lambda ev: f(), "value_throttled")


def _level_ctl(host):
    """The level of the layer's mode: its range (heights, model levels, sweeps) follows it."""
    run = host.run
    w = pn.widgets.FloatSlider(name="km AGL", start=0.0, end=max(_ztop(run), 0.05),
                               step=0.05, value=0.0, width=210)

    def put(v):
        lo, hi, step, name = level_range(run, host.doc.get("mode") or "height")
        hi = max(hi, lo + step)
        v = lo if v is None else min(max(float(v), lo), hi)
        w.param.update(start=lo, end=hi, step=step, value=v, name=name)
    return _Slider(w, get=lambda: float(w.value), set=put)


def _height_ctl(host, label):
    top = max(float(np.floor(host.run.ztop)), 0.05)
    w = pn.widgets.FloatSlider(name=label, start=0.0, end=top, step=0.05, value=0.0,
                               width=190)

    def put(v):
        w.value = min(max(float(v or 0.0), 0.0), top)
    return _Slider(w, get=lambda: float(w.value), set=put)


def _ref_ctl(host, row):
    """A vector's reference arrow: its label in the units of the layer's vector."""
    from ...viewer.numinput import FloatInput
    w = FloatInput(name=row.label, value=10.0, width=controls.WIDTH)

    def put(v):
        d = vectors.VECTORS.get(host.doc.get("vector"))
        w.name = f"Ref. arrow ({d.units})" if d is not None else row.label
        w.value = v
    return controls.Ctl(w, set=put)


def _minus_run_ctl(host, row):
    """A difference's run: the runs are looked for once it is on (runs() lists folders)."""
    blank = f"— {row.control.placeholder or 'none'}"
    w = pn.widgets.Select(name=row.label, options={blank: ""}, width=controls.WIDTH)
    w.description = "The run to subtract (other runs on another grid are interpolated onto " \
                    "this one)"
    got = [False]

    def put(v):
        v = "" if v is None else v
        if not got[0] and host.doc.get("minus"):
            got[0] = True
            w.options = {blank: ""} | host.runs()
        w.options = controls._keep(dict(w.options), v, "")
        w.value = v
    host.forget_runs = lambda: got.__setitem__(0, False)
    return controls.Ctl(w, get=lambda: None if w.value == "" else w.value, set=put)


def _minus_time_ctl(host, row):
    """A difference's time: the outputs of the run it is taken from, as that run is now."""
    blank = f"— {row.control.placeholder or 'none'}"
    w = pn.widgets.Select(name=row.label, options={blank: ""}, width=controls.WIDTH)

    def put(v):
        v = "" if v is None else v
        opts = {blank: ""} | host.times(host.run_of(None))
        w.options = controls._keep(opts, v)
        w.value = v
    return controls.Ctl(w, get=lambda: None if w.value == "" else w.value, set=put)


# ------------------------------------------------------------ the host (ui/drawer.py's)
class LayerHost:
    """The drawer's host on one viewer layer: the layer is its document."""

    def __init__(self, lay, kind="plan", run=None, fields=None, on_change=None, runs=None,
                 times=None, drawn=None, say=None):
        self.doc, self.kind, self.run, self.fields = lay, kind, run, fields
        self.on_change, self._runs, self._times = on_change, runs, times
        self._drawn, self._say = drawn, say
        self.drawers = []
        self.forget_runs = lambda: None  # (a difference's run list: looked for again)

    @property
    def ctx(self):
        return fills.Context(
            fields=self.fields, drawn=self._drawn() if self._drawn is not None else None,
            relevel=(lambda old, new, z: relevel(self.run, old, new, z))
            if self.run is not None else None)

    def edit(self, fn):
        """fn(layer) on a copy; what it changed written to the layer itself, then shown, then
        on_change(the keys changed)."""
        lay = self.doc
        new = copy.deepcopy(lay)
        fn(new)
        gone = object()
        keys = {k for k in set(lay) | set(new) if lay.get(k, gone) != new.get(k, gone)}
        if not keys:
            return
        lay.clear()
        lay.update(new)
        for d in self.drawers:
            d.refresh()
        if self.on_change is not None:
            self.on_change(keys)

    def field_groups(self):
        """The field menu's groups: a cross-section's, the fields with heights."""
        return self.fields.groups(ndim=3) if self.kind == "xsec" else self.fields.groups()

    def say(self, text, err=False):
        if self._say is not None:
            self._say(text, err)

    # ---- what controls offer
    def control(self, row, where):
        k = row.control.kind
        if k == "vlevel":
            return _level_ctl(self) if self.run is not None else None
        if k == "vheight":
            return _height_ctl(self, row.label) if self.run is not None else None
        if k == "vref":
            return _ref_ctl(self, row)
        if k == "run" and row.control.options == "viewer":
            return _minus_run_ctl(self, row)
        if k == "time" and row.control.options == "minus":
            return _minus_time_ctl(self, row)
        return None

    def options(self, name, where):
        from ...viewer import ui
        run, F = self.run, self.fields
        if name == "levelmodes":
            if run is not None and not getattr(run, "grid", True):
                return ui.SWEEP_MODES
            return ui.TERRAIN_LEVEL_MODES if getattr(run, "terrain", False) else \
                ui.LEVEL_MODES
        if name == "vectors":
            return vectors.options(F) if F is not None else {}
        if name == "frames":
            return vectors.frames(run) if run is not None else {}
        return {}

    def runs(self):
        return dict(self._runs() if self._runs is not None else {})

    def run_of(self, where, key=None):
        """The run a difference's times are of: its own (None: this one)."""
        return (self.doc.get("minus") or {}).get("run")

    def times(self, run_id):
        """A run's output times, after "the output before" (a difference's)."""
        got = self._times(run_id) if self._times is not None else {}
        return {PREV: "prev", **dict(got or {})}

    def psets(self, where):
        return {}

    def pvars(self, where):
        return {}


# ------------------------------------------------------------ the component
class LayerDrawer:
    """The controls of one viewer layer (role: fill, more, contour, vectors; kind: plan or
    xsec), written to it as they change."""

    def __init__(self, lay, role, kind="plan", skip=(), **offers):
        self.lay, self.role, self.kind = lay, role, kind
        self.host = LayerHost(lay, kind, **offers)
        rows = [r for r in V.rows(role, kind) if r.key[len("layer."):] not in skip]
        self.drawer = D.Drawer(self.host, V.at(kind), rows, flat=True)
        self.host.drawers.append(self.drawer)
        self.panel = self.drawer.panel

    def refresh(self):
        self.drawer.refresh()

    def put(self, key, value):
        """Layer key set as its control would (what its row fills beside it too: a field's
        colours and range), shown, then on_change: for a key set elsewhere (the viewer's
        toolbar) or one skipped here."""
        row = next(r for r in V.rows(self.role, self.kind) if r.key == f"layer.{key}")
        where, ctx = self.drawer.where, self.host.ctx
        self.host.edit(lambda lay: W.write(lay, row, where, value, ctx))

    def rerun(self, run, fields):
        """Another run of the same grid shown in place (viewer/swap.py)."""
        self.host.run, self.host.fields = run, fields
        self.host.forget_runs()
        self.refresh()

    def ctl(self, key):
        for s in self.drawer.sections:
            for r in s.rows:
                if r.key == f"layer.{key}" and r.id in s.ctls:
                    return s.ctls[r.id]
        return None
