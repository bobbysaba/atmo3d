"""The PPI panel: a radar run's sweeps at the shown time, and the gate under a map click.

The map itself shows the sweep (Fields.plane's "sweep" mode, atmo3d_radar.ppi on the
map's pixels); this panel lists the volume's sweeps (by elevation: measured, fixed,
Nyquist velocity, rays, the beam's height at the last gate), picks the one the map
shows, and says what is at a clicked gate (where it is, and the shown fields' values
there).

A mixin of the Viewer (atmo3d/viewer/app.py, registered by atmo3d_radar.register): its
methods use the Viewer's widgets and state, and do nothing on runs without native sweeps.
"""
import html

import numpy as np
import pandas as pd
import panel as pn

from atmo3d.viewer.ui import _html

from . import beam, ppi

COLUMNS = ("Sweep", "Elevation (°)", "Fixed angle (°)", "Nyquist (m/s)", "Rays",
           "Top at last gate (km)")
HINT = ('<div class="cv-hint">The map shows one sweep of the volume at the shown time. '
        'Pick it here (or with the number beside <b>Sweep</b> above the map); click the '
        'map to see the gate there. Heights are above the radar.</div>')
EMPTY_GATE = '<div class="cv-empty">Click the map to see the gate there.</div>'


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
        self.fill_lvl.param.watch(lambda e: self._ppi_update(), "value")
        self.fill_var.param.watch(lambda e: self._ppi_show_gate(), "value")
        self._ppi_built = True
        self._ppi_update()

    def _ppi_layout(self):
        """The PPI panel."""
        self._ppi_build()
        return pn.Column(_html(HINT, sizing_mode="stretch_width"), self.ppi_site,
                         self.ppi_head, self.ppi_table, self.ppi_gate,
                         sizing_mode="stretch_width")

    def _ppi_sweep(self):
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
            self.ppi_table.selection = [k] if 0 <= k < len(sw) else []
        finally:
            self._ppi_hold = False
        self._ppi_show_gate()

    def _ppi_on_select(self, ev):
        if self._ppi_hold or not ev.new:
            return
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
            return
        F, run = self.F, self.run
        names = [self._fill_name()] + [n for n in (F.role("refl"), F.role("u"), F.role("v"),
                                                  F.role("w"), "velocity") if n]
        names = list(dict.fromkeys(n for n in names if n))
        # (read off the page thread: the radar has no soundings, so their pool is free)
        self.gen["snd"] += 1
        g, t, k, pt = self.gen["snd"], self.t, self._ppi_sweep(), self._ppi_pt

        def job():
            try:
                out = gate_html(run, F, t, k, *pt, names)
            except Exception as e:  # noqa: BLE001
                out = f'<div class="cv-hint">Gate: {html.escape(str(e))}</div>'
            if g == self.gen["snd"]:
                self._schedule(lambda: setattr(self.ppi_gate, "object", out))

        self.pools["snd"].submit(job)

    # ---- the shared viewer's hooks (other runs: as they were)
    def _on_time(self, ev):
        super()._on_time(ev)
        if self._ppi_built:
            self._ppi_update()
