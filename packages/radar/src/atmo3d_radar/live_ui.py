"""Following a folder of NEXRAD volumes live, in the viewer: a Viewer mixin
(registered by atmo3d_radar.register).

Every CHECK seconds a page showing a native Level II run looks at its folder, when the
folder is followed (atmo3d_radar.live: a follower in this process fills it, or "Follow
new volumes" in the PPI panel is on).  New volumes there: a page showing the newest
time opens the run again at the newest (the view kept, through the core's
reopen-with-view, as ↻ Reload does); a page showing an earlier time stays there and
says how many came, for ↻ Reload.  The PPI panel has the switch, the follower's state
and a button that stops the fetching.
"""
import html

import panel as pn

from atmo3d.viewer.ui import _html

from . import level2, live

CHECK = 20.0  # s between looks at the folder


def _level2_run(run):
    """Whether run is a native Level II run (a folder that grows as volumes come)."""
    return (getattr(run, "model", None) == "radar" and
            getattr(run, "format", None) == "level2" and hasattr(run, "files"))


class LiveFollow:
    _live_told = None  # (folder, volumes) last said to be waiting
    _live_built = False

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        if getattr(self, "doc", None) is not None:
            pn.state.add_periodic_callback(self._live_tick, period=int(CHECK * 1000))

    # ---- the PPI panel's part
    def _live_widgets(self):
        """The switch, the follower's line and its Stop (in the PPI panel)."""
        if not _level2_run(self.run):
            return None
        if not self._live_built:
            self.live_follow = pn.widgets.Checkbox(
                name="Follow new volumes", value=live.following(self.run.path),
                margin=(8, 5, 2, 5))
            self.live_follow.param.watch(self._live_switch, "value")
            self.live_line = _html(sizing_mode="stretch_width")
            self.live_stop = pn.widgets.Button(
                name="Stop live fetching", button_type="light", button_style="outline",
                width=150, visible=False)
            self.live_stop.on_click(self._live_stop)
            self._live_built = True
        self._live_show()
        return pn.Column(pn.Row(self.live_follow, self.live_stop, margin=0),
                         self.live_line, sizing_mode="stretch_width", margin=0)

    def _live_switch(self, ev):
        live.follow(self.run.path, bool(ev.new))
        self._live_show()
        if ev.new:
            self._live_tick()

    def _live_stop(self, ev=None):
        live.stop(self.run.path)
        self._live_show()

    def _live_show(self):
        if not self._live_built:
            return
        f = live.running(self.run.path)
        self.live_stop.visible = f is not None
        if f is not None:
            text = f.status()
        elif self.live_follow.value:
            text = ("Following the folder: new volumes put there (e.g. by "
                    "<code>atmo3d-nexrad SITE --live</code>) are shown as they come")
        else:
            text = ("Off: the reload button (↻, by the run's name) adds the volumes put "
                    "in the folder since it opened (“Live” in the run picker's NEXRAD "
                    "from AWS… fetches them as they come)")
        self.live_line.object = f'<div class="cv-hint">{text}</div>'

    # ---- the check
    def _live_tick(self):
        run = self.run
        if not _level2_run(run) or not live.following(run.path):
            return
        self._live_show()
        try:
            found = level2.files_in(run.path)
        except OSError:
            return
        new = len(found) - len(run.times)
        if new <= 0 or getattr(self, "reg", None) is None:
            return
        many = f"{new} new volume{'s' * (new != 1)}"
        if self.t != len(run.times) - 1:  # (looking back: say so, once per arrival)
            if self._live_told != (run.path, len(found)):
                self._live_told = (run.path, len(found))
                self._set_status(f"{many} in the folder: reload (↻) adds them (this view "
                                 f"stays at the time it shows; at the newest time it "
                                 f"follows them)")
            return
        s = self.session_state()
        try:
            newer, _ = self.reg.reopen(run.path)
        except Exception as e:  # noqa: BLE001
            self._set_status(f"Live: could not open the new volumes: {html.escape(str(e))}")
            return
        s["time_s"] = float(newer.times[-1])
        self._set_status(f"{many}: going to {newer.time_label(len(newer.times) - 1)}")
        self._open_with_view(newer.path, s)
