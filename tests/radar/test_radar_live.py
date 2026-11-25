"""Live NEXRAD (atmo3d_radar.live, live_ui, the AWS panel's Live and atmo3d-nexrad
--live), without the network: the archive is a list of Remote volumes, and a fetch
writes synthetic Level II files (tests/synthetic_level2.py)."""
import datetime as dt
import os
import time

import pytest

import synthetic_level2 as S

atmo3d_radar = pytest.importorskip("atmo3d_radar")
from atmo3d_radar import aws, live  # noqa: E402

D = dt.datetime
T = [D(2013, 5, 20, 19, 51, 11), D(2013, 5, 20, 19, 55, 27), D(2013, 5, 20, 19, 59, 41),
     D(2013, 5, 20, 20, 3, 56)]


def _remote(t):
    return aws.Remote(t, f"{t:%Y/%m/%d}/KTLX/{S.name(t)}", 1)


@pytest.fixture
def archive(monkeypatch):
    """The archive's volumes (a list to add to), fetched as synthetic files; .asked
    counts the listings, .fail makes the next one fail."""
    class A:
        vols = [_remote(t) for t in T[:2]]
        asked, fail = 0, None

    def volumes(site, start, end):
        A.asked += 1
        if A.fail:
            e, A.fail = A.fail, None
            raise e
        return [v for v in A.vols if start <= v.time <= end]

    def fetch(vols, folder, progress=None, cancelled=None):
        os.makedirs(folder, exist_ok=True)
        have = set(os.listdir(folder))
        for v in vols:
            if v.name not in have:
                S.write(folder, [v.time])
        return [os.path.join(folder, v.name) for v in vols]

    monkeypatch.setattr(aws, "volumes", volumes)
    monkeypatch.setattr(aws, "fetch", fetch)
    return A


@pytest.fixture(autouse=True)
def _clean():
    yield
    for k in list(live._RUNNING):
        live._RUNNING.pop(k).stop()
    live._FOLLOW.clear()


def test_follower_fetches_only_newer(archive, tmp_path):
    f = live.Follower("ktlx", str(tmp_path), since=T[0])
    assert f.site == "KTLX" and f.last == T[0]
    got = f.check()
    assert [os.path.basename(p) for p in got] == [S.name(T[1])]  # (not T[0]: not newer)
    assert f.last == T[1] and f.fetched == 1
    assert f.check() == []  # (nothing new)
    archive.vols.append(_remote(T[2]))
    assert [os.path.basename(p) for p in f.check()] == [S.name(T[2])]
    assert f.fetched == 2 and live.newest_in(str(tmp_path)) == T[2]
    assert "newest volume 19:59:41" in f.status()


def test_follower_starts_from_the_folder(archive, tmp_path):
    S.write(str(tmp_path), [T[1]])
    f = live.Follower("KTLX", str(tmp_path), since=T[0])
    assert f.last == T[1]  # (what the folder has is not fetched again)
    assert f.check() == []


def test_follower_thread_survives_a_failed_check_and_stops(archive, tmp_path):
    archive.fail = aws.Offline("no route to the archive")
    seen = []
    f = live.Follower("KTLX", str(tmp_path), since=T[0], every=0.05, on_new=seen.append)
    f.start()
    deadline = time.monotonic() + 10
    while not seen and time.monotonic() < deadline:
        time.sleep(0.02)
    assert seen and os.path.basename(seen[0][0]) == S.name(T[1])  # (after the failure)
    assert archive.asked >= 2 and f.error == ""
    f.stop()
    f.join(5)
    assert not f.is_alive() and "stopped" in f.status()


def test_failed_check_says_why(archive, tmp_path):
    archive.fail = aws.Offline("no route to the archive")
    f = live.Follower("KTLX", str(tmp_path), since=T[0], every=60)
    f.start()
    deadline = time.monotonic() + 10
    while not f.error and time.monotonic() < deadline:
        time.sleep(0.02)
    assert "no route" in f.error and "failed" in f.status()
    f.stop()


def test_start_running_stop_follow(archive, tmp_path):
    folder = str(tmp_path / "KTLX_20130520")
    f = live.start("KTLX", folder, since=T[0], every=60)
    assert live.start("KTLX", folder + "/") is f  # (one per folder)
    assert live.running(folder) is f and live.following(folder)
    live.stop(folder)
    assert live.running(folder) is None and f.stopped
    assert live.following(folder)  # (the viewer still looks: another fetcher may fill it)
    live.follow(folder, False)
    assert not live.following(folder)


# ---------------------------------------------------------------------- the command line
def test_cli_live(archive, tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(aws, "LIVE_MIN_EVERY", 0.0)
    calls = []
    real = live.Follower.check

    def check(self):
        calls.append(1)
        if len(calls) == 1:
            archive.vols.append(_remote(T[2]))
            return real(self)
        raise KeyboardInterrupt
    monkeypatch.setattr(live.Follower, "check", check)
    assert aws.main(["KTLX", "2013-05-20T19:50", "--live", "--every", "0",
                     "--into", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    folder = tmp_path / "KTLX_20130520"
    assert "2 volumes" in out and "Live: checking" in out and S.name(T[2]) in out
    assert "Stopped: 1 new volumes" in out
    assert sorted(os.listdir(folder)) == [S.name(t) for t in T[:3]]


def test_cli_live_takes_no_end_and_plain_needs_both():
    with pytest.raises(SystemExit) as e:
        aws.main(["KTLX", "2013-05-20T19:50", "2013-05-20T20:00", "--live"])
    assert e.value.code == 2
    with pytest.raises(SystemExit) as e:
        aws.main(["KTLX", "2013-05-20T19:50"])
    assert e.value.code == 2


# ---------------------------------------------------------------------- the AWS panel
def test_panel_live_fetches_opens_and_starts(archive, tmp_path, monkeypatch):
    pytest.importorskip("panel")
    from atmo3d_radar import aws_ui
    now = T[1] + dt.timedelta(minutes=2)

    class Now(dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return now.replace(tzinfo=tz)
    monkeypatch.setattr(aws_ui.dt, "datetime", Now)
    started = []
    monkeypatch.setattr(live, "start", lambda site, folder, since=None, every=None:
                        started.append((site, folder, since)))
    done = []
    p = aws_ui.AWSPanel(done.append, lambda: None)
    p.root = str(tmp_path)
    p.site.value = "ktlx"
    p._live()
    deadline = time.monotonic() + 10
    while not done and time.monotonic() < deadline:
        time.sleep(0.02)
    folder = str(tmp_path / "KTLX_20130520")
    assert done == [folder]
    assert started == [("KTLX", folder, T[1])]
    assert sorted(os.listdir(folder)) == [S.name(t) for t in T[:2]]
    assert (p.t0.value, p.t1.value) == ("18:57", "19:57")  # (the window fetched)


# ---------------------------------------------------------------------- the viewer
@pytest.fixture
def lv(tmp_path):
    pytest.importorskip("panel")
    from atmo3d.registry import Registry
    from atmo3d.viewer import app as A
    folder = tmp_path / "KTLX_20130520"
    folder.mkdir()
    S.write(str(folder), T[:2])
    reg = Registry(str(folder), 0.5, 1)
    run, F = reg.get()
    v = A.Viewer(run, F, reg=reg)
    v.main()
    opened = []
    v._open_with_view = lambda path, s: opened.append((path, s))
    yield v, str(folder), opened
    v.close()


def test_viewer_follows_new_volumes_at_the_newest_time(lv):
    v, folder, opened = lv
    v._live_tick()  # (not followed: nothing)
    S.write(folder, [T[2]])
    v.tslider.value = len(v.run.times) - 1
    v._live_tick()
    assert opened == []
    live.follow(folder)
    v._live_tick()
    assert len(opened) == 1
    path, s = opened[0]
    assert path == v.run.path and s["time_s"] == (T[2] - T[0]).total_seconds()


def test_viewer_looking_back_is_told(lv):
    v, folder, opened = lv
    live.follow(folder)
    v.tslider.value = 0
    S.write(folder, [T[2], T[3]])
    v._live_tick()
    assert opened == [] and "2 new volumes" in v.status.object


def test_ppi_panel_switch(lv):
    v, folder, _ = lv
    col = v._live_widgets()
    assert col is not None and not v.live_follow.value
    assert "reload" in v.live_line.object
    v.live_follow.value = True
    assert live.following(folder) and "Following the folder" in v.live_line.object
    v.live_follow.value = False
    assert not live.following(folder)
