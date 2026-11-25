"""The PPI panel: a radar run's sweeps at the shown time, and what is under a map click.

The map itself shows a sweep (Fields.plane's "sweep" mode, atmo3d_radar.ppi on the
map's pixels), a height or a column extreme (run.map_plane); this panel lists the
volume's sweeps (by elevation: measured, fixed, Nyquist velocity, rays, the beam's
height at the last gate), picks the one the map shows, and for a clicked point says
what is at its gate in the shown sweep (where it is, and the fields' values there) and
draws the shown field's column there: the sampler's values from the ground up
(atmo3d_radar.sampler) and each sweep's own gate value at its beam's height.

A mixin of the Viewer (atmo3d/viewer/app.py, registered by atmo3d_radar.register): its
methods use the Viewer's widgets and state, and do nothing on runs without native sweeps.
"""
import html

import numpy as np
import pandas as pd
import panel as pn
from bokeh.models import ColumnDataSource, HoverTool
from bokeh.plotting import figure

from atmo3d.theme import MUTED
from atmo3d.viewer.ui import _bokeh, _html, style_fig

from . import beam, ppi

COLUMNS = ("Sweep", "Elevation (°)", "Fixed angle (°)", "Nyquist (m/s)", "Rays",
           "Top at last gate (km)")
HINT = ('<div class="cv-hint">The map shows one sweep of the volume at the shown time '
        '(or a height, or the column max, chosen above the map). Pick the sweep here; '
        'click the map to see the gate there and the column above it. Heights are above '
        'the radar.</div>')
EMPTY_GATE = '<div class="cv-empty">Click the map to see the gate there.</div>'
COLUMN_DZ = 0.05  # km between the column's sampled heights
EMPTY_COL = dict(v=[], z=[])
EMPTY_PTS = dict(v=[], z=[], sweep=[])


def sweep_table(run, t):
    """The sweeps of time t as a table (COLUMNS)."""
    sw = run.sweeps(t)
    top = beam.gate_position(run.ranges[-1], sw.elev)[0] if len(run.ranges) else \
        np.full(len(sw), np.nan)
    return pd.DataFrame({
        COLUMNS[0]: np.arange(len(sw)),
        COLUMNS[1]: np.round(sw.elev, 2),
        COLUMNS[2]: np.round(sw.fixed, 2),
        COLUMNS[3]: np.round(sw.nyquist, 1),
        COLUMNS[4]: [int(np.isfinite(sw.az[k]).sum()) for k in range(len(sw))],
        COLUMNS[5]: np.round(np.atleast_1d(top), 1)})


def gate_html(run, F, t, k, x, y, names):
    """What is at the gate of sweep k under map point x, y: where, and fields `names`'
    values there (F.plane's sweeps, cached as the map's are)."""
    sw = run.sweeps(t)
    if not 0 <= k < len(sw):
        return (f'<div class="cv-hint">The volume at {run.time_label(t)} has {len(sw)} '
                f'sweeps: no sweep {k}.</div>')
    g = ppi.gate_at(run, t, k, x, y)
    if g is None:
        return f'<div class="cv-hint">No gate there in the {sw.label(k)} sweep.</div>' 
    rows = [("Azimuth", f'{g["az"]:.1f}°'), ("Slant range", f'{g["range"]:.2f} km'),
            ("Ground distance", f'{g["ground"]:.2f} km'),
            ("Beam height", f'{g["height"]:.2f} km above the radar')]
    if run.geo is not None:
        lon, lat = run.geo.lonlat(x, y)
        rows.append(("Lat, lon", f"{float(lat):.4f}, {float(lon):.4f}"))
    for n in names:
        if n not in F:
            continue
        d = F[n]
        try:
            a = F.plane(n, t, "sweep", k)
            v = float(a[g["ray"], g["gate"]])
            val = "missing" if not np.isfinite(v) else f"{v:.4g} {d.units}".strip()
        except LookupError as e:  # (not at this time)
            val = html.escape(str(e))
        rows.append((d.label, val))
    body = "".join(f"<tr><td style='opacity:0.75;padding-right:12px'>{html.escape(a)}</td>"
                   f"<td>{b}</td></tr>" for a, b in rows)
    return (f'<div class="cv-h">Gate {g["gate"]} of ray {g["ray"]} · '
            f'{run.sweeps(t).label(k)} sweep</div><table>{body}</table>')


def column(run, F, t, x, y, name, storm=None):
    """Field `name`'s column at map point x, y at time t: dict(z, v) sampled every
    COLUMN_DZ km up to run.ztop (atmo3d_radar.sampler), and dict(z, v, sweep) of each
    sweep's own gate there (its beam's height; sweeps with no gate there left out)."""
    zq = np.arange(0.0, run.ztop + COLUMN_DZ / 2, COLUMN_DZ)
    sw = run.sweeps(t)
    gates = [(k, ppi.gate_at(run, t, k, x, y)) for k in range(len(sw))]
    gates = [(k, g) for k, g in gates if g is not None]

    def both(vol):
        col = run.sample(vol, t, np.full(zq.shape, float(x)), np.full(zq.shape, float(y)),
                         zq)
        pts = np.array([vol[k, g["ray"], g["gate"]] for k, g in gates], np.float32)
        return np.concatenate([col, pts])

    a = np.asarray(F.take(name, t, both, storm), np.float64)
    col, pts = a[:zq.size], a[zq.size:]
    return (dict(z=zq, v=col),
            dict(z=np.array([g["height"] for _, g in gates]), v=pts,
                 sweep=[sw.label(k) for k, _ in gates]))


class PPIPanel:
    _ppi_built = False
    _ppi_hold = False  # (the table's selection set from the sweep number: no echo)
    _ppi_pt = None  # the map point last clicked (x, y km): its gate follows time, sweep

    def _ppi_build(self):
        run = self.run
        lat, lon, alt = run.site
        self.ppi_head = _html(sizing_mode="stretch_width")
        self.ppi_site = _html(
            f'<div class="cv-hint">{html.escape(run.instrument)} at {lat:.4f}, {lon:.4f}, '
            f'{alt:.0f} m above sea level · gates every '
            f'{1000 * float(np.median(np.diff(run.ranges))):.0f} m to '
            f'{run.ranges[-1]:.0f} km</div>', sizing_mode="stretch_width")
        self.ppi_table = pn.widgets.Tabulator(
            sweep_table(run, self.t), disabled=True, show_index=False, selectable=1,
            theme="midnight", height=360, sizing_mode="stretch_width",
            layout="fit_data_fill")
        self.ppi_table.param.watch(self._ppi_on_select, "selection")
        self.ppi_gate = _html(EMPTY_GATE, sizing_mode="stretch_width")
        # the column under the click: the sampler's line, each sweep's gate as a dot
        fig = figure(height=320, sizing_mode="stretch_width", tools="pan,wheel_zoom,reset",
                     toolbar_location="above", y_axis_label=f"Height ({run.height_units})",
                     x_axis_label="")
        style_fig(fig)
        self.ppi_col_src = ColumnDataSource(dict(EMPTY_COL))
        self.ppi_pts_src = ColumnDataSource(dict(EMPTY_PTS))
        fig.line("v", "z", source=self.ppi_col_src, line_color="#38bdf8", line_width=2)
        dots = fig.scatter("v", "z", source=self.ppi_pts_src, size=7, color="#fbbf24",
                           line_color=MUTED)
        fig.add_tools(HoverTool(renderers=[dots], tooltips=[
            ("sweep", "@sweep"), ("height", "@z{0.00} km"), ("value", "@v{0.00}")]))
        self.ppi_col_fig = fig
        self.ppi_col = _bokeh(fig, sizing_mode="stretch_width", visible=False)
        self.fill_lvl.param.watch(lambda e: self._ppi_update(), "value")
        self.fill_mode.param.watch(lambda e: self._ppi_update(), "value")
        self.fill_var.param.watch(lambda e: self._ppi_show_gate(), "value")
        self._ppi_built = True
        self._ppi_update()

    def _ppi_layout(self):
        """The PPI panel."""
        self._ppi_build()
        live = getattr(self, "_live_widgets", None)  # (atmo3d_radar.live_ui)
        live = live() if live is not None else None
        return pn.Column(_html(HINT, sizing_mode="stretch_width"), self.ppi_site,
                         *([live] if live is not None else []), self.ppi_head,
                         self.ppi_table, self.ppi_gate, self.ppi_col,
                         sizing_mode="stretch_width")

    def _ppi_sweep(self):
        """The sweep the map shows (None: it shows a height or a column extreme)."""
        if self.fill_mode.value != "sweep":
            return None
        return int(round(float(self.fill_lvl.value or 0)))

    def _ppi_update(self):
        """The table, its heading and the marked sweep for the shown time and sweep."""
        if not self._ppi_built:
            return
        run, t, k = self.run, self.t, self._ppi_sweep()
        sw = run.sweeps(t)
        df = sweep_table(run, t)
        if len(df) != len(self.ppi_table.value) or not df.equals(self.ppi_table.value):
            self.ppi_table.value = df
        short = (f' · <span style="color:#fbbf24">{len(sw)} sweeps here, '
                 f'{run.nsweeps} in the first volume</span>' if len(sw) != run.nsweeps else "")
        self.ppi_head.object = (f'<div class="cv-h">Volume at {run.time_label(t)} · '
                                f'{len(sw)} sweeps{short}</div>')
        self._ppi_hold = True
        try:
            self.ppi_table.selection = [k] if k is not None and 0 <= k < len(sw) else []
        finally:
            self._ppi_hold = False
        self._ppi_show_gate()

    def _ppi_on_select(self, ev):
        if self._ppi_hold or not ev.new:
            return
        if self.fill_mode.value != "sweep":  # (back to sweeps: the one picked)
            self.fill_mode.value = "sweep"
        self.fill_lvl.value = float(ev.new[0])  # (the map follows: request_map)

    def _ppi_click(self, x, y):
        self._ppi_pt = (float(x), float(y))
        self._show_panel(True, "PPI")
        self._ppi_show_gate()

    def _ppi_show_gate(self):
        if not self._ppi_built:
            return
        if self._ppi_pt is None:
            self.ppi_gate.object = EMPTY_GATE
            self.ppi_col.visible = False
            return
        F, run = self.F, self.run
        shown = self._fill_name()
        names = [shown] + [n for n in (F.role("refl"), F.role("u"), F.role("v"),
                                       F.role("w"), "velocity", "velocity_dealiased") if n]
        names = list(dict.fromkeys(n for n in names if n and n in F))
        # (read off the page thread: the radar has no soundings, so their pool is free)
        self.gen["snd"] += 1
        g, t, k, pt = self.gen["snd"], self.t, self._ppi_sweep(), self._ppi_pt
        level = run.level_text(t, self.fill_mode.value, float(self.fill_lvl.value or 0))

        def job():
            try:
                if k is None:
                    out = (f'<div class="cv-hint">The map shows the field{html.escape(level)}'
                           f'; pick a sweep to see the gate under the click.</div>')
                else:
                    out = gate_html(run, F, t, k, *pt, names)
            except Exception as e:  # noqa: BLE001
                out = f'<div class="cv-hint">Gate: {html.escape(str(e))}</div>'
            try:
                col = column(run, F, t, *pt, shown) if shown in F else None
            except LookupError:  # (not at this time)
                col = None
            except Exception as e:  # noqa: BLE001
                col = None
                out += f'<div class="cv-hint">Column: {html.escape(str(e))}</div>'
            if g == self.gen["snd"]:
                self._schedule(lambda: self._ppi_put(out, col, shown, pt))

        self.pools["snd"].submit(job)

    def _ppi_put(self, out, col, name, pt):
        self.ppi_gate.object = out
        if col is None:
            self.ppi_col.visible = False
            return
        line, pts = col
        self.ppi_col_src.data = dict(v=line["v"], z=line["z"])
        self.ppi_pts_src.data = dict(v=pts["v"], z=pts["z"], sweep=pts["sweep"])
        d = self.F[name]
        fig = self.ppi_col_fig
        fig.xaxis.axis_label = f"{d.label} ({d.units})" if d.units else d.label
        fig.title.text = (f"Column at {pt[0]:.1f}, {pt[1]:.1f} km · "
                          f"{self.run.view_note()} · dots: each sweep's gate")
        fig.title.text_color = MUTED
        self.ppi_col.visible = True

    # ---- the shared viewer's hooks (other runs: as they were)
    def _on_time(self, ev):
        super()._on_time(ev)
        if self._ppi_built:
            self._ppi_update()
