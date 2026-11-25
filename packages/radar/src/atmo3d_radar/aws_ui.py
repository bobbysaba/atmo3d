"""The run picker's "NEXRAD from AWS…" panel: a site, a day and a time window (UTC),
the volumes the archive has in it, and Fetch and open (atmo3d_radar.aws: downloaded into
<radar_nexrad_dir>/<SITE>_<yyyymmdd>, then that folder opens as a radar run).  Live:
the site's last LIVE_HOURS, opened, and a follower (atmo3d_radar.live) that keeps
fetching its new volumes while the server runs; the viewer goes to each as it comes
(atmo3d_radar.live_ui).

Registered with the core picker (viewer.picker.register_source) by atmo3d_radar.register.
Listing and downloading run in a thread; the page is updated on its own thread.
"""
import datetime as dt
import html
import re
import threading

import panel as pn

from atmo3d.viewer.ui import _html

from . import aws, live

LABEL = "NEXRAD from AWS…"
TIP = ("Download NEXRAD Level II volumes from the public archive on AWS (a site, a day "
       "and a time window) and open them. Needs internet: compute nodes often have none.")
MAX_HOURS = 24.0
LIVE_HOURS = 1.0
_HHMM = re.compile(r"^\s*(\d{1,2}):?(\d{2})\s*$")
OK, ERR = "#4ade80", "#f87171"


def parse_window(day, start, end):
    """(start, end) UTC datetimes of a day and two "HH:MM" times (an end before the
    start is on the next day).  ValueError if a time does not read or the window is
    longer than MAX_HOURS."""
    def hm(text, what):
        m = _HHMM.match(text or "")
        if not m or int(m.group(1)) > 23 or int(m.group(2)) > 59:
            raise ValueError(f"the {what} time is HH:MM (UTC), not {text!r}")
        return dt.time(int(m.group(1)), int(m.group(2)))
    t0 = dt.datetime.combine(day, hm(start, "start"))
    t1 = dt.datetime.combine(day, hm(end, "end"))
    if t1 <= t0:
        t1 += dt.timedelta(days=1)
    if (t1 - t0).total_seconds() > MAX_HOURS * 3600:
        raise ValueError(f"at most {MAX_HOURS:g} hours at once")
    return t0, t1


def _mb(n):
    return f"{n / 1e6:,.0f} MB" if n < 1e9 else f"{n / 1e9:,.2f} GB"


class AWSPanel:
    """The panel (`.body`).  done(path) opens a folder; back() returns to the list."""

    def __init__(self, done, back):
        self.done, self.back = done, back
        self.doc = pn.state.curdoc
        now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
        self.site = pn.widgets.TextInput(name="Site", value="KTLX", width=90,
                                         description="The radar's four-letter ID (KTLX: "
                                                     "Oklahoma City)")
        self.day = pn.widgets.DatePicker(name="Day (UTC)", value=now.date(), width=140)
        self.t0 = pn.widgets.TextInput(name="From (UTC)", value=f"{max(now.hour - 1, 0):02d}:00",
                                       width=90)
        self.t1 = pn.widgets.TextInput(name="To (UTC)", value=f"{now:%H:%M}", width=90)
        self.find = pn.widgets.Button(name="Find volumes", button_type="primary", width=120,
                                      margin=(24, 5, 5, 10))
        self.fetch = pn.widgets.Button(name="Fetch and open", button_type="primary",
                                       width=140, disabled=True)
        self.live = pn.widgets.Button(
            name="Live", button_type="success", button_style="outline", width=90,
            description=f"The site's last {LIVE_HOURS:g} hour, opened, then each new volume "
                        f"as the archive gets it (fetched while this server runs; the "
                        f"view goes to it)")
        self.cancel = pn.widgets.Button(name="Cancel", button_type="light",
                                        button_style="outline", width=90, visible=False)
        self.back_btn = pn.widgets.Button(name="← Runs", button_type="light",
                                          button_style="outline", width=90)
        self.bar = pn.indicators.Progress(value=0, max=100, width=400, visible=False,
                                          margin=(10, 5))
        self.msg = _html()
        self.root = aws.default_root()
        self.where = _html(f'<div class="cv-hint">Saved under {html.escape(self.root)} '
                           f'(⚙ Settings: Radar: NEXRAD downloads)</div>')
        self.vols, self.folder = [], ""
        self._going_live = None  # (site, end of the window) while Live fetches
        self._stop = threading.Event()
        self._busy = False
        self.find.on_click(lambda e: self._find())
        self.fetch.on_click(lambda e: self._fetch())
        self.live.on_click(lambda e: self._live())
        self.cancel.on_click(lambda e: self._stop.set())
        self.back_btn.on_click(lambda e: self.back())
        for w in (self.site, self.day, self.t0, self.t1):
            w.param.watch(lambda e: self._changed(), "value")
        self.body = pn.Column(
            _html('<div class="cv-hint" style="margin-bottom:4px">NEXRAD Level II volumes '
                  'from the public archive on AWS: pick a site, a day and a time window '
                  '(UTC).</div>'),
            pn.Row(self.site, self.day, self.t0, self.t1, self.find, margin=0),
            self.msg, self.bar, pn.Row(self.fetch, self.live, self.cancel, pn.Spacer(),
                                       self.back_btn, margin=(5, 0)),
            self.where, margin=0, sizing_mode="stretch_width")

    # ---- threads -> page
    def _later(self, fn):
        if self.doc is not None and getattr(self.doc, "session_context", None):
            self.doc.add_next_tick_callback(fn)
        else:
            fn()

    def _say(self, text, color=None):
        style = f' style="color:{color}"' if color else ""
        self.msg.object = f'<div class="cv-hint"{style}>{text}</div>'

    def _changed(self):
        if not self._busy and self._going_live is None:
            self.vols = []
            self.fetch.disabled = True

    # ---- find
    def _window(self):
        site = aws.check_site(self.site.value)
        t0, t1 = parse_window(self.day.value, self.t0.value, self.t1.value)
        return site, t0, t1

    def _find(self):
        try:
            site, t0, t1 = self._window()
        except ValueError as e:
            return self._say(html.escape(str(e)), ERR)
        self._busy, self.find.disabled, self.fetch.disabled = True, True, True
        self._say(f"Looking for {site} volumes {t0:%Y-%m-%d %H:%M}–{t1:%H:%M} UTC…")

        def work():
            try:
                vols, err = aws.volumes(site, t0, t1), None
            except (aws.Offline, ValueError) as e:
                vols, err = [], str(e)
            self._later(lambda: self._found(site, t0, t1, vols, err))
        threading.Thread(target=work, daemon=True).start()

    def _found(self, site, t0, t1, vols, err):
        self._busy, self.find.disabled = False, False
        if err:
            return self._say(html.escape(err), ERR)
        self.vols, self.folder = vols, aws.folder_for(self.root, site, t0)
        if not vols:
            return self._say(f"The archive has no {site} volumes {t0:%Y-%m-%d %H:%M}–"
                             f"{t1:%H:%M} UTC.", ERR)
        size = sum(v.size for v in vols)
        self._say(f'<span style="color:{OK}">✓</span> {len(vols)} volume'
                  f'{"s" * (len(vols) != 1)}, {vols[0].time:%H:%M:%S}–'
                  f'{vols[-1].time:%H:%M:%S} UTC, {_mb(size)}, into '
                  f'{html.escape(self.folder)} (files already there are not fetched '
                  f'again)')
        self.fetch.disabled = False

    # ---- live
    def _live(self):
        """The site's last LIVE_HOURS: found, fetched and opened, a follower started."""
        if self._busy:
            return
        try:
            site = aws.check_site(self.site.value)
        except ValueError as e:
            return self._say(html.escape(str(e)), ERR)
        now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None, second=0,
                                                        microsecond=0)
        t0 = now - dt.timedelta(hours=LIVE_HOURS)
        self._going_live = (site, now)
        # (the window shown is the one fetched)
        self.day.value, self.t0.value, self.t1.value = t0.date(), f"{t0:%H:%M}", \
            f"{now:%H:%M}"
        self._busy = True
        self.find.disabled = self.fetch.disabled = self.live.disabled = True
        self._say(f"Live {site}: looking for the last {LIVE_HOURS:g} hour of volumes…")

        def work():
            try:
                vols, err = aws.volumes(site, t0, now + dt.timedelta(minutes=10)), None
            except (aws.Offline, ValueError) as e:
                vols, err = [], str(e)
            self._later(lambda: self._live_found(site, t0, vols, err))
        threading.Thread(target=work, daemon=True).start()

    def _live_found(self, site, t0, vols, err):
        self._busy = False
        self.find.disabled = self.live.disabled = False
        if err or not vols:
            self._going_live = None
            return self._say(html.escape(err) if err else
                             f"The archive has no {site} volumes in the last "
                             f"{LIVE_HOURS:g} hour: is the radar up?", ERR)
        self.vols, self.folder = vols, aws.folder_for(self.root, site, t0)
        self._fetch()

    # ---- fetch
    def _fetch(self):
        if not self.vols or self._busy:
            return
        vols, folder = list(self.vols), self.folder
        self._stop.clear()
        self._busy = True
        self.find.disabled = self.fetch.disabled = self.live.disabled = True
        self.cancel.visible = self.bar.visible = True
        self.bar.value = 0
        last = [0.0]

        def progress(done, total, name):
            import time
            now = time.monotonic()
            if now - last[0] < 0.25 and done < total:
                return
            last[0] = now
            pct = int(100 * done / max(total, 1))
            self._later(lambda: self._progress(pct, done, total, name))

        def work():
            try:
                paths, err = aws.fetch(vols, folder, progress, self._stop.is_set), None
            except (aws.Offline, OSError) as e:
                paths, err = [], str(e)
            self._later(lambda: self._fetched(vols, folder, paths, err))
        threading.Thread(target=work, daemon=True).start()

    def _progress(self, pct, done, total, name):
        self.bar.value = pct
        self._say(f"Fetching {html.escape(name)}: {_mb(done)} of {_mb(total)}")

    def _fetched(self, vols, folder, paths, err):
        self._busy = False
        self.find.disabled = self.live.disabled = False
        self.cancel.visible = self.bar.visible = False
        going, self._going_live = self._going_live, None
        if err:
            self.fetch.disabled = False
            return self._say(html.escape(err), ERR)
        if len(paths) < len(vols):
            self.fetch.disabled = False
            return self._say(f"Stopped: {len(paths)} of {len(vols)} volumes in "
                             f"{html.escape(folder)}. Fetch again to get the rest.")
        if going is not None:  # (Live: a follower from the newest volume on)
            site, _ = going
            live.start(site, folder, since=max(v.time for v in vols))
        self._say(f'<span style="color:{OK}">✓</span> {len(paths)} volumes in '
                  f'{html.escape(folder)}: opening…'
                  + (" (live: new volumes follow)" if going is not None else ""))
        self.done(folder)


def build(done, back):
    """The panel for viewer.picker.register_source."""
    return AWSPanel(done, back).body
