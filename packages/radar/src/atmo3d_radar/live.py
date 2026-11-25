"""Live NEXRAD: keep fetching a site's new Level II volumes from the AWS archive into a
folder, as the radar finishes them (one about every 4 to 10 minutes, on the archive a
few minutes after the volume ends).

A Follower is a thread that asks the archive every EVERY seconds for the site's volumes
newer than the last one it has, and fetches them into the folder (atmo3d_radar.aws:
.part then renamed, so a radar run reading the folder never sees half a file).  It goes
on through midnight (into the same folder) and past a failed request (it tries again at
the next check, and says why in .error) until stopped.  One follower per folder in a
process:

  start(site, folder, since)   a follower for the folder (the running one, if any)
  running(folder)              the folder's follower, or None
  stop(folder)

The viewer follows a folder (atmo3d_radar.live_ui) when a follower in its own process
fills it, or when asked to (follow(folder)): the fetching may happen elsewhere, e.g.
`atmo3d-nexrad SITE --live` on a login node while the viewer runs on a compute node,
which has no internet.
"""
import datetime as dt
import os
import threading

from . import aws, level2

EVERY = 60.0  # s between checks of the archive
LOOK_BACK = dt.timedelta(hours=1)  # a follower started without `since`: from an hour ago


def _now():
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


def newest_in(folder):
    """The time of the newest Level II volume in folder, or None."""
    found = level2.files_in(folder)
    return found[-1][0] if found else None


class Follower(threading.Thread):
    """Fetches site's volumes newer than `since` (UTC) into `folder` until stop().

    last      the newest volume's time fetched (or found in the folder)
    fetched   volumes fetched so far
    checked   when the archive was last asked (UTC), or None
    error     why the last check failed ("" when it did not)"""

    def __init__(self, site, folder, since=None, every=EVERY, on_new=None):
        super().__init__(daemon=True, name=f"nexrad-live-{os.path.basename(folder)}")
        self.site, self.folder = aws.check_site(site), os.path.abspath(folder)
        self.every, self.on_new = float(every), on_new
        have = newest_in(self.folder) if os.path.isdir(self.folder) else None
        self.last = max(t for t in (since, have) if t is not None) if (since or have) \
            else _now() - LOOK_BACK
        self.fetched, self.checked, self.error = 0, None, ""
        self._halt = threading.Event()

    def stop(self):
        self._halt.set()

    @property
    def stopped(self):
        return self._halt.is_set()

    def check(self):
        """Ask the archive once and fetch what is new: the paths fetched."""
        now = _now()
        self.checked = now
        vols = [v for v in aws.volumes(self.site, self.last, now + dt.timedelta(hours=1))
                if v.time > self.last]
        if not vols:
            return []
        paths = aws.fetch(vols, self.folder, cancelled=self._halt.is_set)
        got = [p for p in paths if level2.name_time(p) is not None]
        if got:
            self.last = max(level2.name_time(p) for p in got)
            self.fetched += len(got)
        return got

    def run(self):
        while not self._halt.is_set():
            try:
                got = self.check()
                self.error = ""
            except (aws.Offline, OSError, ValueError) as e:
                got, self.error = [], str(e)
            if got and self.on_new is not None:
                try:
                    self.on_new(got)
                except Exception:  # noqa: BLE001  (a listener's trouble is not ours)
                    pass
            self._halt.wait(self.every)

    def status(self):
        """A line about the follower, for the page."""
        if self.stopped:
            return f"Live fetching of {self.site} stopped ({self.fetched} new volumes)"
        when = f", last checked {self.checked:%H:%M:%S} UTC" if self.checked else ""
        if self.error:
            return f"Live {self.site}: the last check failed ({self.error}){when}"
        return (f"Live {self.site}: newest volume {self.last:%H:%M:%S} UTC, "
                f"{self.fetched} fetched since it started{when}; checks every "
                f"{self.every:g} s")


_LOCK = threading.Lock()
_RUNNING = {}  # folder -> Follower
_FOLLOW = set()  # folders the viewer follows (besides those a follower fills)


def _key(folder):
    return os.path.normcase(os.path.abspath(folder)).rstrip("/\\")


def start(site, folder, since=None, every=EVERY):
    """The folder's follower, started (or the one already running there)."""
    k = _key(folder)
    with _LOCK:
        f = _RUNNING.get(k)
        if f is not None and f.is_alive() and not f.stopped:
            return f
        f = _RUNNING[k] = Follower(site, folder, since, every)
        _FOLLOW.add(k)
    f.start()
    return f


def running(folder):
    """The follower filling folder (running), or None."""
    with _LOCK:
        f = _RUNNING.get(_key(folder))
    return f if f is not None and f.is_alive() and not f.stopped else None


def stop(folder):
    with _LOCK:
        f = _RUNNING.pop(_key(folder), None)
    if f is not None:
        f.stop()


def follow(folder, on=True):
    """Whether viewers of folder go to its new volumes as they come."""
    with _LOCK:
        (_FOLLOW.add if on else _FOLLOW.discard)(_key(folder))


def following(folder):
    with _LOCK:
        return _key(folder) in _FOLLOW
