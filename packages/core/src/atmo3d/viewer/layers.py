"""The map's and the cross-section's layers (docs-dev/figures-ui-plan.md, Phase 5.3, 5.4):
their first fill, more fills, contours and vectors.  Each is a dict in a figure layer's form (figures/schema/viewer.py) and
its controls are the layer component the figures use (figures/ui/layer.py); the map's job
(mapview._map_spec) reads the dicts.  The first fill's field and level are the toolbar's
(fill_var, fill_op, fill_mode, fill_lvl, which the data types' panels watch); the rest of it
is the Style drawer.

  self.map_fill            the first fill (a Layer)
  self.fills, ovs, vecs    the more fills, contours and vectors (Layers), as many as their
                           drawers list (FILL_MAX, OV_MAX, VEC_MAX)
  self.xs_main, xs_fills, xs_ovs, xs_vecs
                           the cross-section's the same (kind "xsec": xsec.py adds them; its
                           first fill's field is its toolbar's xs_fill)

A mixin of the Viewer (atmo3d/viewer/app.py): its methods use the Viewer's widgets and state."""

import copy

import panel as pn

from ..core import vectors
from ..core.fields import CMAPS, deriv_name, split_deriv
from ..figures.schema import viewer as V
from ..figures.ui.layer import LayerDrawer, level_range

RULE = {"border-top": "1px solid rgba(148,163,184,.18)"}  # (above every row but the first)
TOOLBAR = ("on", "field", "mode", "z")  # (the first fill's: on the toolbar, or none)


class Layer:
    """One map (kind "plan") or cross-section ("xsec") layer: its dict (.lay), its controls
    (.drawer), its row in a drawer (.row, with a remove button .drop), the range it was last
    drawn with (.last: Auto range off starts there)."""

    def __init__(self, v, role, lay, n=0, tip=None, skip=(), kind="plan"):
        self.lay, self.role, self.kind, self.last = lay, role, kind, None
        self.drawer = LayerDrawer(lay, role, kind, skip=skip,
                                  on_change=lambda keys: v._layer_changed(self, keys),
                                  drawn=lambda: self.last, **v._layer_offers())
        self.drop = None
        objs = [self.drawer.panel]
        if tip:
            self.drop = pn.widgets.Button(name="", icon="x", button_type="light", width=36,
                                          height=32, margin=(5, 4, 8, 4), description=tip)
            objs.append(self.drop)
        self.row = pn.Row(*objs, margin=0, sizing_mode="stretch_width",
                          styles=RULE if n else {})

    def __getitem__(self, key):
        return self.lay[key]


def minus_spec(lay):
    """What a fill's difference subtracts: None (no difference) or {path: "" for this run, time:
"" the shown time, "prev" or a time in s} (diff.py's _minus_ref finds it)."""
    m = lay.get("minus")
    if not m:
        return None
    t = m.get("time_s")
    return dict(path=m.get("run") or "", time="" if t is None else t)


class MapLayers:
    OV_COLORS = ("#ffffff", "#60a5fa", "#f472b6", "#facc15", "#4ade80", "#c084fc")
    OV_MAX = len(OV_COLORS)
    FILL_MAX = 3
    VEC_COLORS = ("#e5e7eb", "#fbbf24", "#22d3ee")
    VEC_MAX = len(VEC_COLORS)

    # ------------------------------------------------------------ what the controls offer
    def _layer_offers(self):
        def runs():
            return {k: p for k, p in self._minus_runs().items() if p}

        def times(rid):  # (a difference's fixed time: this run's outputs, as before)
            run = self.run
            return {run.time_label(k): float(t) for k, t in enumerate(run.times)}

        def say(text, err=False):
            self._set_status(f'<span style="color:#f87171">{text}</span>' if err else text)
        return dict(run=self.run, fields=self.F, runs=runs, times=times, say=say)

    def _layer_changed(self, o, keys):
        """A layer's control changed it: the map (or the section) is drawn again (every key:
        the job reads its data from the cache, so a colour or an opacity costs no reading)."""
        if o.kind == "xsec":
            self.request_xsec()
        else:
            self.request_map()

    def _map_layers(self):
        return [self.map_fill, *self.fills, *self.ovs, *self.vecs]

    def _xs_layers(self):
        return [self.xs_main, *self.xs_fills, *self.xs_ovs, *self.xs_vecs]

    def _rerun_layers(self):
        """Another run of the same grid shown in place (swap.py): the controls offer its
        levels, and a difference from it is one from this run."""
        for o in self._map_layers() + self._xs_layers():
            m = o.lay.get("minus")
            if m and m.get("run") == self.run.path:
                m["run"] = None
            o.drawer.rerun(self.run, self.F)

    # ------------------------------------------------------------ the first fill
    def _build_map_fill(self, field):
        """The first fill: the toolbar's field and level, the Style drawer's rest."""
        d = self.F[field]
        lo, hi = d.vrange or (0.0, 1.0)
        lay = V.new("fill", field=deriv_name(self.fill_op.value, self.fill_var.value),
                    mode=self.fill_mode.value, z=float(self.fill_lvl.value), cmap=d.cmap,
                    vmin=lo, vmax=hi)
        self.map_fill = Layer(self, "fill", lay, skip=TOOLBAR)

    def _on_bar_level(self, ev):
        """The toolbar's level mode or level: the first fill's (its level: a redraw when let
        go, value_throttled)."""
        self.map_fill.lay.update(mode=self.fill_mode.value, z=float(self.fill_lvl.value or 0))
        if ev.obj is self.fill_mode:
            self.request_map()

    # ------------------------------------------------------------ rows: add, remove
    def _level_start(self, lay, mode="height", z=1.0):
        """A new row's level: the mode and level given (a radar's: its lowest sweep)."""
        if not self.run.grid:
            lay.update(mode="sweep", z=0.0)
        else:
            lay.update(mode=mode, z=float(z))

    def _new_fill(self, role="more", kind="plan"):
        """A more fill's dict: w (5 to 30 m/s, an own range) or the shown field."""
        F = self.F
        var = F.role("w") or (self.fill_var.value if kind == "plan" else self.xs_fill.value)
        w = var == F.role("w")
        d = F[var]
        lo, hi = (5.0, 30.0) if w else (d.vrange or (0.0, 1.0))
        return V.new(role, kind, field=var, cmap=d.cmap, auto=not w, vmin=lo, vmax=hi), w

    def _new_vec(self, rows, kind="plan", **values):
        """A vector layer's dict: the wind first, then a vector not shown yet, in a colour the
        other rows don't use."""
        run = self.run
        opts = vectors.options(self.F)
        used = {o["vector"] for o in rows}
        q = "wind" if not rows else next((k for k in opts.values() if k not in used), "wind")
        taken = {o["color"] for o in rows}
        color = next((c for c in self.VEC_COLORS if c not in taken), self.VEC_COLORS[0])
        return V.new("vectors", kind, vector=q, color=color, frame=vectors.frame_of(
            run, "grid" if (run.umove or run.vmove) else "ground"), **values)

    def _new_contour(self, rows, var, levels, kind="plan"):
        used = {o["color"] for o in rows}
        color = next((c for c in self.OV_COLORS if c not in used), self.OV_COLORS[0])
        return V.new("contour", kind, field=var, levels=levels, color=color)

    def _add_row(self, o, rows, box, add, most):
        o.drop.on_click(lambda e: self._drop_layer(o))
        rows.append(o)
        box.append(o.row)
        add.disabled = len(rows) >= most

    def _add_fill(self):
        """One more fill, drawn over the first: its row in the More fills drawer, its image /
        bands and colorbar on the map.  w: 5 to 30 m/s at 3 km, cleared outside its range so
        the fill below shows through."""
        n = len(self.fills)
        if n >= self.FILL_MAX:
            return
        lay, w = self._new_fill()
        self._level_start(lay, z=3.0 if w else 1.0)
        self._add_row(Layer(self, "more", lay, n, "Remove this fill"), self.fills,
                      self.fill_list, self.fill_add, self.FILL_MAX)
        self._fill_glyphs()
        self.request_map()

    def _add_overlay(self):
        """One more contour overlay: its row in the Contours drawer, its lines on the map."""
        n = len(self.ovs)
        if n >= self.OV_MAX:
            return
        var, mode, level, levels = (self._ov_next[n] if n < len(self._ov_next)
                                    else self._ov_default)
        lay = self._new_contour(self.ovs, var, levels)
        self._level_start(lay, mode, level)
        if not self.run.grid:  # (a radar's: off until asked for)
            lay["on"] = False
        self._add_row(Layer(self, "contour", lay, n, "Remove this contour"), self.ovs,
                      self.ov_list, self.ov_add, self.OV_MAX)
        if hasattr(self, "ov_r"):  # added from the page: the map exists
            self._ov_glyphs()
            self.request_map()

    def _add_vec(self, on=True):
        """One more vector layer: its row in the Vectors drawer, its arrows (or streamlines)
        on the map: the wind first, then a vector not shown yet."""
        n = len(self.vecs)
        if n >= self.VEC_MAX:
            return
        lay = self._new_vec(self.vecs, on=on)
        self._add_row(Layer(self, "vectors", lay, n, "Remove these vectors"), self.vecs,
                      self.vec_list, self.vec_add, self.VEC_MAX)
        if hasattr(self, "vec_r"):  # added from the page: the map exists
            self._vec_glyphs()
            self.request_map()

    def _layer_place(self, o):
        """(rows, drawer list, Add button, glyphs, the renderers of one) of layer o."""
        if o.kind == "xsec":
            if o in self.xs_fills:
                return (self.xs_fills, self.xs_fill_list, self.xs_fill_add, self.xs_fill_r,
                        lambda g: (g["img"], g["poly"]))
            if o in self.xs_ovs:
                return self.xs_ovs, self.xs_ov_list, self.xs_ov_add, self.xs_ov_r, \
                    lambda g: g[2:]
            return self.xs_vecs, self.xs_vec_list, self.xs_vec_add, self.xs_vec_r, \
                lambda g: (g["seg"], g["head"])
        if o in self.fills:
            return (self.fills, self.fill_list, self.fill_add, self.fill_r,
                    lambda g: (g["img"], g["poly"]))
        if o in self.ovs:
            return self.ovs, self.ov_list, self.ov_add, self.ov_r, lambda g: g[2:]
        return self.vecs, self.vec_list, self.vec_add, self.vec_r, lambda g: g["rs"]

    def _drop_layer(self, o):
        """Remove layer row o: its row, its glyphs (and a fill's colorbar) off the map (or the
        section)."""
        rows, box, add, glyphs, drawn = self._layer_place(o)
        i = rows.index(o)
        rows.pop(i)
        box.remove(o.row)
        if rows:
            rows[0].row.styles = {}
        add.disabled = False
        if i < len(glyphs):
            g = glyphs.pop(i)
            gone = drawn(g)
            fig = self.xs_fig if o.kind == "xsec" else self.fig
            fig.renderers = [r for r in fig.renderers if all(r is not x for x in gone)]
            if isinstance(g, dict) and "cbar" in g:
                fig.right = [x for x in fig.right if x is not g["cbar"]]
        self._layer_changed(o, ())

    # ------------------------------------------------------------ sessions (FORMAT 3: session.py)
    def _checked_layer(self, o, lay, skipped):
        """lay (a session's, over o's) with what this run cannot take put back as o has it
        (a field or vector another run lacks, a level mode it has not, a level above its
        top); their names added to skipped."""
        old, F = o.lay, self.F
        opts = o.drawer.host.options

        def keep(key, ok, name):
            if key in lay and lay[key] != old.get(key) and not ok(lay[key]):
                skipped.append(f"{name} {lay[key]}")
                lay[key] = old.get(key)
        keep("field", lambda v: v in F, "var")
        keep("vector", lambda v: v in vectors.options(F).values(), "q")
        keep("frame", lambda v: v in vectors.frames(self.run).values(), "frame")
        keep("mode", lambda v: v in opts("levelmodes", None).values(), "mode")
        keep("cmap", lambda v: v in CMAPS, "cmap")
        if o.kind == "xsec":  # (a section's fields: those with heights)
            keep("field", lambda v: F[v].ndim == 3, "var")
            return lay
        if "z" in lay and lay.get("mode") not in ("colmax", "colmin", None) \
                and o.role != "vectors":
            lo, hi, _, _ = level_range(self.run, lay["mode"])
            lay["z"] = min(max(float(lay["z"] or 0.0), lo), hi)
        elif "z" in lay and o.role == "vectors":
            lay["z"] = min(max(float(lay["z"] or 0.0), 0.0), float(int(self.run.ztop)))
        return lay

    def _put_layer(self, o, d, skipped):
        """Layer o set from a session's layer d (FORMAT 3: what d has over what o has; a
        difference "minus": None is none)."""
        lay = copy.deepcopy(o.lay)
        lay.update(copy.deepcopy(d))
        if "minus" in lay and lay["minus"] is None:
            del lay["minus"]
        lay = self._checked_layer(o, lay, skipped)
        o.lay.clear()
        o.lay.update(lay)
        o.drawer.refresh()

    def _put_map_fill(self, d, put, skipped):
        """The first fill from a session: its field and level to the toolbar (which writes
        them to it), the rest to it."""
        op, base = split_deriv(d["field"]) if d.get("field") else (None, None)
        for name, w, v in (("var", self.fill_var, base), ("op", self.fill_op, op),
                           ("mode", self.fill_mode, d.get("mode")),
                           ("level", self.fill_lvl, d.get("z"))):
            put(w, v, name)
        o = self.map_fill
        o.lay.update(field=self._fill_name(), mode=self.fill_mode.value,
                     z=float(self.fill_lvl.value or 0))
        self._put_layer(o, {k: v for k, v in d.items() if k not in ("field", "mode", "z")},
                        skipped)

    def _put_layers(self, rows, have, add, skipped):
        """As many layer rows as the session has, each set from it."""
        if rows is None:
            return
        while len(have) > len(rows):
            self._drop_layer(have[-1])
        while len(have) < len(rows):
            n = len(have)
            add()
            if len(have) == n:  # (at the most there can be)
                break
        for o, r in zip(have, rows):
            self._put_layer(o, r, skipped)

    def _put_xs_main(self, d, skipped):
        """The section's first fill from a session: its field is the toolbar's (put there
        first, which writes it to it), the rest to it."""
        o = self.xs_main
        o.lay["field"] = self.xs_fill.value
        self._put_layer(o, {k: v for k, v in d.items() if k != "field"}, skipped)
