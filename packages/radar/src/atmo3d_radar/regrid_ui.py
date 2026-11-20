"""The Native / Regridded switch of a radar run, and the dialog that confirms the regrid
settings before a regridded run opens (atmo3d-plan.md Phase 6 step 5).

The switch is the toolbar's parts selector (core.models parts: the folder's native run
and its regridded one, atmo3d_radar.model).  Choosing Regridded does not open it: a
dialog shows the settings (method, horizontal and vertical spacing, maximum range, the
widest gap bridged) with the grid's size, and only its Regrid button opens the
regridded run (the page reopens on it, the view kept, as for a WoFS member on another
grid).  The settings confirmed are saved (radar_regrid_* in core.config) and named in
the regridded run's path (atmo3d_radar.regrid).

A mixin of the Viewer (registered by atmo3d_radar.register): it changes nothing on runs
of other data types.
"""
import html

import panel as pn

from atmo3d.viewer.numinput import FloatInput
from atmo3d.viewer.ui import _html

from . import regrid

INTRO = ('<div class="cv-maptitle" style="font-size:16px"><b>Regrid the radar volumes?'
         '</b></div><div class="cv-hint" style="margin:6px 0 10px">Every view then '
         'samples a regular grid made from the sweeps, and is labelled "regridded". Each '
         'field is regridded at each time when first shown (kept for later). Native '
         'sweeps stay the source: switch back with <b>Native sweeps</b> in the toolbar.'
         '</div>')


def _level_of(mode, level):
    """A map layer's level mode and level on the other kind of radar run: a sweep (or
    a model level) becomes 1 km up; heights and column extremes stay."""
    if mode in ("height", "colmax", "colmin"):
        return mode, level
    return "height", 1.0


def for_other(state):
    """A session state of one kind of radar run (native or regridded) made to fit the
    other: the map layers' level modes (sweeps exist only natively, model levels only on
    the grid)."""
    s = dict(state)
    f = dict(s.get("fill") or {})
    if "mode" in f:
        f["mode"], f["level"] = _level_of(f["mode"], f.get("level", 1.0))
    s["fill"] = f
    for key in ("fills", "contours"):
        rows = []
        for o in s.get(key) or []:
            o = dict(o)
            if "mode" in o:
                o["mode"], o["level"] = _level_of(o["mode"], o.get("level", 1.0))
            rows.append(o)
        s[key] = rows
    return s


class RegridSwitch:
    _rg_modal = None

    def _is_radar(self):
        return getattr(self.run, "model", None) == "radar"

    # ---- the dialog
    def _rg_build(self):
        s = regrid.from_config()
        self.rg_method = pn.widgets.Select(name="Within a sweep",
                                           options={"Linear": "linear", "Nearest gate":
                                                    "nearest"}, value=s.method, width=150)
        lo = regrid.LIMITS
        self.rg_dx = FloatInput(name="Horizontal spacing (km)", value=s.dx, start=lo["dx"][0],
                                end=lo["dx"][1], step=0.1, width=150)
        self.rg_dz = FloatInput(name="Vertical spacing (km)", value=s.dz, start=lo["dz"][0],
                                end=lo["dz"][1], step=0.05, width=150)
        self.rg_range = FloatInput(name="Maximum range (km)", value=s.range,
                                   start=lo["range"][0], end=lo["range"][1], step=10,
                                   width=150)
        self.rg_gap = FloatInput(name="Widest gap bridged (km; 0: all)", value=s.gap,
                                 start=lo["gap"][0], end=lo["gap"][1], step=0.5, width=200)
        self.rg_info = _html()
        self.rg_go = pn.widgets.Button(name="Regrid", button_type="primary", width=120)
        self.rg_no = pn.widgets.Button(name="Cancel", button_type="light",
                                       button_style="outline", width=90)
        self.rg_go.on_click(lambda e: self._rg_confirm())
        self.rg_no.on_click(lambda e: self._rg_modal.hide())
        for w in (self.rg_method, self.rg_dx, self.rg_dz, self.rg_range, self.rg_gap):
            w.param.watch(lambda e: self._rg_describe(), "value")
        from atmo3d.theme import DIALOG_DARK
        self._rg_modal = pn.Modal(
            _html(INTRO), pn.Row(self.rg_method, self.rg_dx, self.rg_dz, margin=0),
            pn.Row(self.rg_range, self.rg_gap, margin=0), self.rg_info,
            pn.Row(self.rg_go, self.rg_no), width=600, margin=10,
            stylesheets=[DIALOG_DARK])
        self._rg_describe()

    def _rg_settings(self):
        """The dialog's Settings (ValueError when one is out of range)."""
        return regrid.Settings(self.rg_method.value, float(self.rg_dx.value or 0),
                               float(self.rg_dz.value or 0), float(self.rg_range.value or 0),
                               float(self.rg_gap.value or 0))

    def _rg_describe(self):
        try:
            s = self._rg_settings()
        except ValueError as e:
            self.rg_info.object = (f'<div class="cv-status" style="color:#f87171">'
                                   f'{html.escape(str(e))}</div>')
            self.rg_go.disabled = True
            return
        native = getattr(self.run, "native", self.run)
        ni, nk, mb = s.sizes(native.ztop)
        self.rg_go.disabled = False
        self.rg_info.object = (
            f'<div class="cv-hint">{ni} × {ni} × {nk} points: {mb:,.0f} MB per field per '
            f'time in memory (and in the cache folder, up to {regrid.DISK_GB:g} GB). '
            f'Labelled <b>regridded: {html.escape(s.label)}</b>.</div>')

    def _rg_ask(self, folder):
        """Show the dialog for the folder's regridded run."""
        self._rg_folder = folder
        if self._rg_modal is None:
            self._rg_build()
        self._rg_describe()
        self._rg_modal.show()

    def _rg_confirm(self):
        """Regrid with the dialog's settings: save them, open the regridded run."""
        try:
            s = self._rg_settings()
        except ValueError:
            return
        from atmo3d import config
        try:
            config.save(regrid.to_config(s))
        except (OSError, ValueError):
            pass  # (the path holds them anyway)
        self._rg_modal.hide()
        path = regrid.path_of(self._rg_folder, s)
        state = self.session_state()
        state["run"] = path
        if not self.swap_run(path, for_other(state)):
            self._open_with_view(path, state)

    def _ext_modals(self):
        mods = tuple(super()._ext_modals())
        if not self._is_radar():
            return mods
        if self._rg_modal is None:
            self._rg_build()
        return mods + (self._rg_modal,)

    # ---- the shared viewer's hooks (other runs: as they were)
    def _switch_part(self, e):
        got = regrid.parse(e.new) if self._is_radar() and e.new else None
        if got is None or getattr(self, "_part_hold", False) or e.new == self.run.path:
            return super()._switch_part(e)
        # (not yet: the selector goes back until the dialog's Regrid)
        self._part_hold = True
        try:
            self.part_sel.value = e.old
        finally:
            self._part_hold = False
        self._rg_ask(got[0])

    def _open_with_view(self, path, s):
        if self._is_radar() and (regrid.parse(path) is None) != (regrid.parse(
                self.run.path) is None):
            s = for_other(s)  # (native <-> regridded: the level modes)
        return super()._open_with_view(path, s)
