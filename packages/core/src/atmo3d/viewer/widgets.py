"""Widgets: the side drawers' controls (field, level, time, tools,
options) and the run picker.

A mixin of the Viewer (atmo3d/viewer/app.py): its methods use the Viewer's widgets and state."""

import html
import json
import os

import numpy as np
import panel as pn

from .. import config
from ..core.services import pdecomp
from ..core import models, sounding_plot as sp, vectors
from ..core.run import busy_note
from ..core.fields import deriv_options
from .numinput import FloatInput
from .picker import RunPicker
from .settings import ConfirmOverwrite, Settings
from .ui import LEVEL_MODES, ON, SWEEP_MODES, TERRAIN_LEVEL_MODES, TIME_BAR, ToolRail, _html
from .fieldmenu import FieldSelect
from . import panels


class Widgets:
    _sv_wired = False  # (Viewer._wire wires the 3D vectors there at first)

    def _vec_row(self, rows, colors, on, level, density, dens_range):
        """The widgets of one more 3D vector layer: the wind first, then a vector not shown
        yet.  (The map's and the section's: layers.py.)"""
        opts = vectors.options(self.F)
        used = {o["q"].value for o in rows}
        q = "wind" if not rows else next((k for k in opts.values() if k not in used), "wind")
        taken = {o["color"].value for o in rows}
        color = next((c for c in colors if c not in taken), colors[0])
        run = self.run
        o = dict(
            on=pn.widgets.Checkbox(value=on, width=18, margin=(5, 0, 14, 8)),
            q=pn.widgets.Select(name="Vector", options=opts, value=q, width=190),
            level=pn.widgets.FloatSlider(name="Height (km AGL)", start=0.0,
                                         end=float(np.floor(run.ztop)), step=0.05,
                                         value=level, width=190),
            frame=pn.widgets.Select(name="Frame", options=vectors.frames(run),
                                    value=vectors.frame_of(
                                        run, "grid" if (run.umove or run.vmove) else "ground"),
                                    width=150),
            density=pn.widgets.IntSlider(name="Arrows across", start=dens_range[0],
                                         end=dens_range[1], value=density, width=170),
            ref=FloatInput(name="", value=vectors.VECTORS[q].ref, width=120),
            color=pn.widgets.ColorPicker(name="Color", value=color, width=60),
            drop=_drop_btn("Remove these vectors"),
        )
        self._vec_vis(o)
        return o

    @staticmethod
    def _vec_vis(o, ev=None):
        """The frame for the wind only; the reference arrow in the vector's units.  On a new
        vector: its typical magnitude as the reference."""
        d = vectors.VECTORS[o["q"].value]
        if ev is not None and ev.name == "value" and ev.obj is o["q"]:
            o["ref"].value = d.ref
        o["frame"].visible = d.framed
        o["ref"].name = f"Ref. arrow ({d.units})"

    def _add_sv(self, on=True):
        """One more 3D vector layer: its row in the Vectors drawer (arrows at a
        height in the scene)."""
        if len(self.svs) >= self.VEC_MAX:
            return
        o = self._vec_row(self.svs, ("#f8fafc", "#fbbf24", "#22d3ee"), on, 0.0, 16, (6, 40))
        o["level"].param.update(name="Height (km AGL)", end=min(10.0, o["level"].end))
        o["density"].name = "Arrows across region"
        o["row"] = _layer_row(len(self.svs), o["on"], o["q"], o["level"], o["frame"],
                              o["density"], o["ref"], o["color"], o["drop"])
        o["drop"].on_click(lambda e: self._drop_sv(o))
        self.svs.append(o)
        self.sv_list.append(o["row"])
        self.sv_add.disabled = len(self.svs) >= self.VEC_MAX
        if self._sv_wired:  # added from the page: wired, and drawn if shown
            self._wire_sv(o)
            self._update_3d_labels()
            if on and self.gen["3d"]:
                self.request_3d()

    def _drop_sv(self, o):
        was_on = o["on"].value
        self.svs.remove(o)
        _unlist(self.sv_list, self.svs, o)
        self.sv_add.disabled = False
        self._update_3d_labels()
        if was_on and self.gen["3d"]:
            self.request_3d()

    def _level_pair(self, mode="height", value=1.0):
        """The toolbar's level-mode select + level (an unlabelled number box: arrow keys /
        wheel step through levels).  A run whose levels follow the terrain has heights above
        sea level too (from 0 up to the top over the highest ground)."""
        run = self.run
        if not run.grid:
            return self._sweep_pair()
        ztop = float(np.floor(run.ztop * 10) / 10)
        modes, ground, gtop = LEVEL_MODES, 0.0, 0.0
        if getattr(run, "terrain", False):
            hgt = run.terrain_height()
            modes, ground, gtop = TERRAIN_LEVEL_MODES, float(np.mean(hgt)), float(np.max(hgt))
        mode_w = pn.widgets.Select(options=modes, value=mode, width=140, height=32,
                                   margin=(4, 2))
        lvl = FloatInput(start=0.0, end=ztop, step=0.25, value=value, width=70, height=32,
                         margin=(4, 4))

        def agl(m, v):  # (a height of mode m as km AGL: MSL less the mean ground)
            return v - ground if m == "msl" else v

        def on_mode(ev):
            if ev.new == "level":
                k = run.level_weights(agl(ev.old, lvl.value))[0] \
                    if ev.old in ("height", "msl") else 0
                lvl.param.update(start=0, end=run.nk - 1, step=1, value=float(k))
            elif ev.new in ("height", "msl"):
                msl = ev.new == "msl"
                z = float(run.z[int(lvl.value)]) if ev.old == "level" else \
                    agl(ev.old, lvl.value) if ev.old in ("height", "msl") else 1.0
                end = float(np.floor((ztop + gtop) * 10) / 10) if msl else ztop
                lvl.param.update(start=0.0, end=end, step=0.25,
                                 value=round(min(max(z + ground * msl, 0.0), end), 2))
            lvl.disabled = ev.new in ("colmax", "colmin")

        mode_w.param.watch(on_mode, "value")
        return mode_w, lvl

    def _sweep_pair(self):
        """_level_pair of a radar run: a sweep's number (0: the lowest; a volume's
        sweeps by elevation, atmo3d_radar.cfradial), a height above the radar (km,
        through its sampler), or the column max / min of the sweeps."""
        run = self.run
        n = max(1, int(getattr(run, "nsweeps", 1)))
        ztop = float(np.floor(run.ztop * 10) / 10)
        mode_w = pn.widgets.Select(options=SWEEP_MODES, value="sweep", width=140,
                                   height=32, margin=(4, 2))
        lvl = FloatInput(start=0, end=n - 1, step=1, value=0, width=70, height=32,
                         margin=(4, 4))

        def on_mode(ev):
            if ev.new == "sweep":
                lvl.param.update(start=0, end=n - 1, step=1, value=0.0)
            elif ev.new == "height":
                lvl.param.update(start=0.0, end=ztop, step=0.25,
                                 value=min(1.0 if ev.old != "height" else lvl.value, ztop))
            lvl.disabled = ev.new in ("colmax", "colmin")

        mode_w.param.watch(on_mode, "value")
        return mode_w, lvl

    def _build_widgets(self):
        run, F = self.run, self.F
        g_all, g3 = F.groups(), F.groups(ndim=3)
        default_fill = F.role("cref") or F.role("refl") or next(iter(F.defs))

        t0 = 0
        try:  # ?t=<index> in the URL opens at that time
            t0 = int(pn.state.session_args.get("t", [b"0"])[0])
            t0 = min(max(t0, 0), len(run.times) - 1)
        except (AttributeError, TypeError, ValueError):
            pass
        self.tslider = pn.widgets.IntSlider(name="", start=0, end=len(run.times) - 1,
                                            value=t0, show_value=False, min_width=120,
                                            sizing_mode="stretch_width", margin=(4, 12),
                                            align="center", stylesheets=[TIME_BAR])
        btn = dict(button_type="light", button_style="outline", width=34, height=32,
                   name="", icon_size="1.1em", margin=(4, 1))
        self.t_prev = pn.widgets.Button(icon="player-track-prev", **btn)
        self.t_play = pn.widgets.Button(icon="player-play", **btn)
        self.t_next = pn.widgets.Button(icon="player-track-next", **btn)
        self.t_speed = pn.widgets.Select(options={"0.5×": 2400, "1×": 1200, "2×": 600,
                                                  "4×": 300}, value=1200, width=66, height=32,
                                         margin=(4, 4))
        self.playing = False
        self._play_cb = None
        self.time_html = _html(margin=(0, 8, 0, 4), align="center")

        self.workspace = pn.widgets.RadioButtonGroup(
            options=["Map", "3D", "Figure"], value="Map", button_type="primary",
            button_style="outline", width=190, height=32, margin=(4, 2),
            # (a run with no grid, a radar's: Map and 3D (its sampler); figures come later)
            visible=bool(run.grid or run.sampled))
        if not run.grid:
            self.workspace.options = ["Map", "3D"] if run.sampled else ["Map"]
            self.workspace.width = 130
        # the registered tools this run gets (viewer.panels: gated on its capabilities)
        self.mode = ToolRail(panels.for_run(run)[1])
        self.hint = _html()
        # the Sounding tool's click: a point, or a dragged box (area mean). snd_pick holds
        # the choice (not shown); the two buttons below set it and light up when chosen
        self.snd_pick = pn.widgets.RadioButtonGroup(
            options={"Click a point": "Sounding", "Drag a box (area mean)": "Area sounding"},
            value="Sounding")
        self.snd_point_btn = pn.widgets.Button(
            name="Click a point", button_type="primary", button_style="solid", height=32,
            margin=(5, 4, 8, 4), description="A click on the map drops a sounding there")
        self.snd_box_btn = pn.widgets.Button(
            name="Drag a box (area mean)", button_type="primary", button_style="outline",
            height=32, margin=(5, 10, 8, 4),
            description="Drag a box on the map: the sounding is averaged over it")
        # the storm track, for everything storm-relative (shown in the top bar)
        self.storm_btn = pn.widgets.Button(
            name="No storm track", icon="tornado", button_type="light",
            button_style="outline", height=32, margin=(4, 2), visible=run.can("tracking"),
            stylesheets=[ON, ":host(.cv-warn) .bk-btn { color: #fbbf24 !important; }"],
            description="The tracked storm: storm-relative soundings, tracked storm "
                        "motion, series around the storm, figures centred on it. Click to "
                        "make, load or edit the track.")

        # ---- fill layer
        fd = F[default_fill]
        self.fill_var = FieldSelect(groups=g_all, value=default_fill, width=220,
                                     height=32, margin=(4, 2))
        self.fill_op = pn.widgets.Select(
            options=deriv_options(fd), value="", width=80, height=32, margin=(4, 2),
            description="A derivative of the field (per m): ∂/∂z on the model levels, "
                        "∂/∂x, ∂/∂y or the horizontal gradient's size")
        self.fill_mode, self.fill_lvl = self._level_pair("height", 1.0)
        self._build_map_fill(default_fill)  # (its Style drawer: layers.py)

        # ---- more fills, over the first: a row each in the More fills drawer
        self.fills = []
        self.fill_list = pn.Column(margin=0, sizing_mode="stretch_width")
        self.fill_add = pn.widgets.Button(name="Add fill", icon="plus", button_type="primary",
                                          button_style="outline", height=32,
                                          margin=(6, 4, 8, 4))
        self.fill_add.on_click(lambda e: self._add_fill())

        # ---- contour overlays: a row each in the Contours drawer, "Add contour" adds one
        self._ov_next = [(F.role("w"), "height", 3.0, "5, 15, 25") if F.role("w")
                         else (default_fill, "height", 1.0, "auto"),
                         ("thpert", "level", 0.0, "-6, -4, -2, -1") if "thpert" in F
                         else (default_fill, "height", 1.0, "auto")]
        self._ov_default = (default_fill, "height", 1.0, "auto")
        self.ovs = []
        self.ov_list = pn.Column(margin=0, sizing_mode="stretch_width")
        self.ov_add = pn.widgets.Button(name="Add contour", icon="plus", button_type="primary",
                                        button_style="outline", height=32,
                                        margin=(6, 4, 8, 4))
        self.ov_add.on_click(lambda e: self._add_overlay())
        self._add_overlay()

        # ---- vectors: wind, horizontal vorticity, ... (core/vectors.py), each in a row
        self.vecs = []
        self.vec_list = pn.Column(margin=0, sizing_mode="stretch_width")
        self.vec_add = pn.widgets.Button(name="Add vectors", icon="plus", button_type="primary",
                                         button_style="outline", height=32,
                                         margin=(6, 4, 8, 4))
        self.vec_add.on_click(lambda e: self._add_vec())
        self._add_vec(on=False)

        # ---- sounding options
        self.storm = pn.widgets.Select(
            name="Storm motion", options={"Bunkers right-mover": "rm",
                                          "Bunkers left-mover": "lm",
                                          "0–6 km mean wind": "mean",
                                          "Domain motion (umove, vmove)": "domain",
                                          "Tracked meso motion": "track",
                                          "Custom": "custom"},
            value="rm", width=210)
        self.storm_u = FloatInput(name="u (m/s)", value=run.umove, width=80,
                                             visible=False)
        self.storm_v = FloatInput(name="v (m/s)", value=run.vmove, width=80,
                                             visible=False)
        self.parcel = pn.widgets.RadioButtonGroup(
            options={"SB": "sb", "ML": "ml", "MU": "mu"}, value="ml",
            button_type="primary", button_style="outline", width=140, margin=(5, 10, 8, 10))
        self.wunits = pn.widgets.RadioButtonGroup(options=["m/s", "kt"], value="m/s",
                                                  button_type="primary",
                                                  button_style="outline", width=100,
                                                  margin=(5, 10, 8, 10))
        self.avg = pn.widgets.Select(
            name="Column average", options={"Single column": 0.0, "1 km box": 1.0,
                                            "2 km box": 2.0, "5 km box": 5.0,
                                            "10 km box": 10.0},
            value=0.0, width=130)
        self.prof_top = pn.widgets.Select(options=[1, 3, 6, 10, 15], value=6, width=70,
                                          height=30, margin=(2, 6))
        self.compare = pn.widgets.RadioButtonGroup(
            options={"Line styles": "lines", "Colors": "colors", "Tabs": "tabs"},
            value="lines", button_type="primary", button_style="outline", width=230,
            margin=(5, 10, 8, 10), description="How several soundings are shown")
        self.mean_btn = pn.widgets.Button(
            name="Domain mean", button_type="primary", button_style="outline", height=32,
            margin=(5, 4, 8, 10), description="Show the domain-mean sounding (follows time)")
        self.pin_btn = pn.widgets.Button(
            name="📌 Pin this time", button_type="primary", button_style="outline",
            height=32, margin=(5, 4, 8, 4),
            description="Freeze sounding 1 at the current time (the domain mean if there is "
                        "none); move the time slider and sounding 1 follows, so you can "
                        "compare times")
        self.storm_follow = pn.widgets.Checkbox(
            name="Move with tracked storm", value=False, margin=(5, 10, 14, 10),
            disabled=True)  # clicked soundings keep their offset from the tracked meso
        self.snd_clear = pn.widgets.Button(name="Clear", button_type="light",
                                           button_style="outline", height=32,
                                           margin=(5, 4, 8, 4))
        self.base_on = pn.widgets.Checkbox(name="Base state", value=True,
                                           margin=(5, 10, 14, 10))
        self.follow = pn.widgets.Checkbox(name="Follow time", value=True,
                                          margin=(5, 10, 14, 10))

        # ---- sounding plot style (redraws only) and zoom limits
        st = sp.STYLE
        ck = dict(margin=(5, 10, 14, 10))
        self.ps = dict(
            t=pn.widgets.ColorPicker(name="Temperature", value=st["t_color"], width=86),
            td=pn.widgets.ColorPicker(name="Dewpoint", value=st["td_color"], width=86),
            parcel=pn.widgets.ColorPicker(name="Parcel", value=st["parcel_color"], width=86),
            base=pn.widgets.ColorPicker(name="Base state", value=st["base_color"], width=86),
            lw=pn.widgets.FloatSlider(name="T / Td width", start=0.5, end=5, step=0.1,
                                      value=st["lw"], width=130),
            parcel_lw=pn.widgets.FloatSlider(name="Parcel width", start=0.5, end=4, step=0.1,
                                             value=st["parcel_lw"], width=130),
            hodo_lw=pn.widgets.FloatSlider(name="Hodograph width", start=0.5, end=5, step=0.1,
                                           value=st["hodo_lw"], width=130),
            prof_lw=pn.widgets.FloatSlider(name="Profile width", start=0.5, end=4, step=0.1,
                                           value=st["prof_lw"], width=130),
            ptop=pn.widgets.Select(name="Skew-T top (hPa)", value=100,
                                   options=[100, 150, 200, 250, 300, 400, 500, 600, 700],
                                   width=110),
            tmin=FloatInput(name="T left (°C)", value=None, placeholder="auto",
                                       width=90),
            tmax=FloatInput(name="T right (°C)", value=None, placeholder="auto",
                                       width=90),
            ring=pn.widgets.Select(name="Hodograph rings", value=0,
                                   options={"Auto": 0, "5": 5, "10": 10, "20": 20}, width=110),
            htop=pn.widgets.Select(name="Hodograph top (km)", value=12,
                                   options=[3, 6, 9, 12, 15], width=120),
            hheights=pn.widgets.TextInput(name="Hodograph heights (km)",
                                          value=st["hodo_heights"], width=150,
                                          description="Heights marked along the hodograph, "
                                                      "e.g. 0.5, 1, 3, 6 (blank: none)"),
            shade=pn.widgets.Checkbox(name="CAPE / CIN shading", value=st["shade"], **ck),
            barbs=pn.widgets.Checkbox(name="Wind barbs", value=st["barbs"], **ck),
            guides=pn.widgets.Checkbox(name="Adiabats & mixing lines", value=st["guides"], **ck),
        )
        self.ps_reset = pn.widgets.Button(name="Default style", button_type="light",
                                          button_style="outline", height=32,
                                          margin=(5, 4, 8, 10))
        self.snd_lim = {}  # zoom: skew, hodo, prof_z, prof_x (see _on_zoom_box)

        self.status = _html()
        # pressure decomposition for the shown time (map caption / cross-section tab)
        pdb = dict(button_type="warning", button_style="outline", height=30,
                   description=f"Run {pdecomp.script_name()} on this output time "
                               "in a separate process (on a 1280 x 1280 x 115 grid: "
                               "~2 min and ~45 GB with 4 CPUs, longer on one)")
        self.pd_write = pn.widgets.Checkbox(
            name="Write into the output file", value=pdecomp.writes_allowed(),
            disabled=not pdecomp.writes_allowed(), margin=(10, 4, 0, 10),
            styles={"pointer-events": "auto"})  # with the script's own write_data
        self.pd_btn = pn.widgets.Button(margin=(4, 0, 6, 0),
                                        styles={"pointer-events": "auto"}, **pdb)
        self.pd_row = pn.Row(self.pd_btn, self.pd_write, margin=0, visible=False)
        self.xs_pd_btn = pn.widgets.Button(margin=(4, 4), visible=False, **pdb)
        self.cache_html = _html()
        self.clear_btn = pn.widgets.Button(name="Clear cache", button_type="default",
                                           button_style="outline", width=100, height=28,
                                           margin=(2, 6))
        self.clear_pts = pn.widgets.Button(name="", icon="eraser", button_type="light",
                                           button_style="outline", width=40, height=32,
                                           margin=(4, 2),
                                           description="Clear map markers (soundings, "
                                                       "section, 3D region)")
        self.full = False  # analysis panel expanded over the whole window
        self.full_btn = pn.widgets.Button(name="", icon="arrows-maximize", button_type="light",
                                          button_style="outline", height=32, margin=(4, 2),
                                          description="Expand the analysis panel to the full "
                                                      "window (sounding graphics become "
                                                      "zoomable)")
        self.panel_btn = pn.widgets.Button(name="", icon="x", button_type="light",
                                           button_style="outline", width=40, height=32,
                                           margin=(4, 2),
                                           description="Close the panel (the tool stays "
                                                       "on; its button reopens it)")
        self.panel_title = _html(margin=(0, 4), align="center")
        self._build_run_picker()

    def _switch_part(self, e):
        """Another member (or the mean) of this run: shown in place, keeping what the
        viewer shows (swap_run); one that does not fit this page reopens the page on it
        (a session written to the cache, opened with ?session=)."""
        if getattr(self, "_part_hold", False) or not e.new or e.new == self.run.path:
            return
        s = self.session_state()
        s["run"] = e.new
        # a track file per member: the other member loads the same storm from its own
        s["track"] = dict(member=True, storm=self.trk_storm.value, load=bool(self.fixes))
        if self.swap_run(e.new, s):
            return
        self._open_with_view(e.new, s)

    def _open_with_view(self, path, s):
        """Reopen the page on run `path`, putting back the view `s` (a session written
        to the cache, opened with ?session=)."""
        fn = config.cache_dir("switch", config.run_key(path) + ".json")
        try:
            os.makedirs(os.path.dirname(fn), mode=0o755, exist_ok=True)
            with open(fn, "w", encoding="utf-8") as f:
                json.dump(s, f, indent=1)
        except OSError:  # (no view kept: just open it)
            self.picker.go.value = json.dumps([path, self.run.model])
            return
        self.ses_go.value = fn

    def _reload_run(self, e=None):
        """Open the run again for the output written since it opened (a run still
        going), keeping the view: in place when nothing changed, else the page reopens
        on it."""
        if self.reg is None:
            return
        old = self.run
        s = self.session_state()
        try:
            run, _ = self.reg.reopen(old.path)
        except Exception as ex:  # noqa: BLE001
            self._set_status(f"Reload failed: {html.escape(str(ex))}")
            return
        added = len(run.times) - len(old.times)
        if added <= 0 and self.swap_run(run.path, s):
            self._set_status("No new output since the run opened"
                             + (f" ({html.escape(busy_note(run.busy))})" if run.busy else ""))
            return
        self._set_status(f"{added} new time{'s' if added != 1 else ''}: reopening")
        self._open_with_view(run.path, s)

    def _run_info_html(self):
        """The run picker's "This run" box."""
        run = self.run
        root = models.root_of(run.path)
        part = f" · {models.part_label(run.path)}" if root != run.path else ""
        return (f'<div class="cv-h" style="margin-top:14px">This run</div>'
                f'<div class="cv-run"><b>{root}</b><br>{run.model_label}{part} · '
                + (f'{run.ni}×{run.nj}×{run.nk} · '
                   f'Δx {run.dx:.0f} m · {len(run.times)} times · domain motion '
                   f'({run.umove:g}, {run.vmove:g}) m/s' if run.grid else
                   f'{run.size_label} · {len(run.times)} times')
                + (f'<br><span style="opacity:0.8">{run.note}</span>' if run.note else '')
                + (f'<br><span style="color:#f59e0b">{html.escape(busy_note(run.busy))}'
                   f'</span>' if run.busy else '')
                + '</div>')

    def _build_run_picker(self):
        run = self.run
        self.run_btn = pn.widgets.Button(name=run.name, button_type="light",
                                         button_style="outline", height=32,
                                         icon="folder-open", margin=(4, 2),
                                         description=f"{run.path}: open another run",
                                         stylesheets=[".bk-btn { max-width: 260px; "
                                                      "overflow: hidden; white-space: nowrap; "
                                                      "text-overflow: ellipsis; }"])
        root = models.root_of(run.path)
        self._run_info = _html(self._run_info_html())
        self.picker = RunPicker(root, extra=(
            self._run_info,
            pn.Row(self.cache_html, self.clear_btn)))
        p = self.picker
        self.rp_modal = p.modal
        self.run_btn.on_click(lambda e: p.show())
        self.reload_btn = pn.widgets.Button(
            name="", icon="refresh", button_type="light", button_style="outline",
            width=40, height=32, margin=(4, 2), visible=self.reg is not None,
            description="Reload run: add the output written since it opened (a run "
                        "still going); the view is kept")
        self.reload_btn.on_click(self._reload_run)
        # a run read as several (WoFS: its members and their mean; a radar folder: its
        # native sweeps and regridded): which one
        parts = models.siblings(run.path) or models.parts(run.path, run.model)
        if run.path not in parts:
            parts = []
        if parts:
            self.run_btn.name = os.path.basename(models.root_of(run.path))
            self.run_btn.description = (f"{models.root_of(run.path)}: open another run")
        self.part_sel = pn.widgets.Select(
            options={models.part_label(q): q for q in parts}, value=run.path if parts else None,
            width=150, height=32, margin=(4, 2), visible=bool(parts),
            description=getattr(models.get(run.model), "parts_tip", None) or
            "Ensemble member shown (the view is kept). "
            "The member a run opens on: wofs_member in ⚙ Settings.")
        self.part_sel.param.watch(self._switch_part, "value")
        self.gear_btn = pn.widgets.Button(
            name="", icon="settings", button_type="light", button_style="outline", width=40,
            height=32, margin=(4, 2), description="Settings: where runs live, where figures "
                                                  "and saved data go, ...")
        self.settings = Settings(run.path)
        self.confirm = ConfirmOverwrite()
        self.gear_btn.on_click(lambda e: self.settings.show())
        self._on_config = lambda: self._schedule(self._config_changed)
        config.on_change(self._on_config)


def _layer_row(n, *widgets):
    """A map layer's controls in its drawer, a rule above every row but the first."""
    return pn.FlexBox(*widgets, flex_wrap="wrap", align_items="flex-end", gap="2px 14px",
                      sizing_mode="stretch_width",
                      styles={"border-top": "1px solid rgba(148,163,184,.18)"} if n else {})


def _unlist(column, layers, o):
    """Take layer o's row out of its drawer list (layers: those left)."""
    column.remove(o["row"])
    if layers:  # the first row has no rule above it
        layers[0]["row"].styles = {}


def _drop_btn(tip):
    return pn.widgets.Button(name="", icon="x", button_type="light", width=36, height=32,
                             margin=(5, 4, 8, 4), description=tip)
