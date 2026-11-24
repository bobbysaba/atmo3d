"""Session files: what the viewer shows saved to JSON and put back."""

import json
import os

import pytest

from atmo3d.viewer.session import FORMAT
from conftest import wait


def w(o, key):
    """The widget of a map layer's control of `key` (its drawer: figures/ui/layer.py)."""
    return o.drawer.ctl(key).widget


def _set_up(v):
    """A viewer state away from the defaults in every part a session keeps."""
    v.tslider.value = 3
    v.fill_var.value = "winterp"
    v.fill_lvl.value = 2.5
    f = v.map_fill
    w(f, "minus").value = True
    w(f, "minus.time_s").value = "prev"
    w(f, "auto").value = False
    w(f, "vmin").value, w(f, "vmax").value = -7.0, 7.0
    v._add_fill()
    w(v.fills[0], "field").value = "thpert"
    v._add_overlay()
    w(v.ovs[1], "levels").value = "1, 2"
    o = v.vecs[0]
    w(o, "on").value = True
    w(o, "vector").value = list(w(o, "vector").options.values())[1]
    w(o, "ref").value = 12.5
    v.view = (10.0, 40.0, 5.0, 35.0)
    v.fixes = {2: dict(x=20.0, y=21.0, value=float("nan"), source="clicked"),
               3: dict(x=22.0, y=22.0, value=1.0, source="loaded")}
    v.mode.set("Cross-section")


def test_session_round_trip(viewer, reg, tmp_path):
    """Saved, then loaded into a fresh viewer: the same state, one redraw with the
    difference and the extra layers, the view kept for the browser's re-fit."""
    from atmo3d.viewer import app as A
    v = viewer
    _set_up(v)
    s1 = v.session_state()
    assert s1["atmo3d_session"] == FORMAT and s1["run"] == os.path.abspath(v.run.path)
    assert s1["track"]["fixes"][0][1]["value"] is None  # NaN as JSON null
    path = str(tmp_path / "s" / "session.json")
    v._save_session(path)
    assert "Saved" in v.ses_msg.object
    json.load(open(path))  # strict JSON

    run, F = reg.get()
    v2 = A.Viewer(run, F, reg=reg)
    v2.main()
    try:
        v2.ses_path.value = path
        v2._on_load_session(None)
        assert "Loaded" in v2.ses_msg.object and "not in this run" not in v2.ses_msg.object
        assert v2.session_state() == s1
        assert v2.t == 3 and v2.view == (10.0, 40.0, 5.0, 35.0)
        assert "fitted" in v2.fig.x_range.tags and v2.fig.tags  # the browser re-fits
        assert len(v2.fills) == 1 and len(v2.ovs) == 2
        assert v2.mode.value == "Cross-section"
        assert sorted(v2.fixes) == [2, 3] and v2.fixes[2]["value"] != v2.fixes[2]["value"]
        wait(lambda: "minus" in (v2.map_title.object or ""), msg="map with the difference")
    finally:
        v2.close()


def test_session_drops_extra_rows_and_skips_what_the_run_lacks(viewer):
    """Fewer rows than shown: the extra ones go; a field, time or tool the run cannot
    take is left as it was and named."""
    v = viewer
    v._add_overlay()
    v._add_fill()
    s = v.session_state()
    s["contours"] = s["contours"][:1]
    s["fills"] = []
    s["fill"]["field"] = "no_such_field"
    s["contours"][0]["z"] = 1e6  # clamped to the top
    s["tool"] = "Nonexistent tool"
    keep = v.fill_var.value
    skipped = v.apply_session(s)
    assert len(v.ovs) == 1 and v.fills == []
    assert v.fill_var.value == keep and any("no_such_field" in x for x in skipped)
    assert v.ovs[0]["z"] == w(v.ovs[0], "z").end
    assert v.mode.value is None


def test_a_format_2_session_opens(viewer):
    """A session 1.1.0 saved (FORMAT 2: the layers as their widgets' values, the first fill's
    difference beside it) opens: its layers as dicts, what it lacks left as it was."""
    from atmo3d.viewer import session
    v = viewer
    old = dict(
        atmo3d_session=2, run=os.path.abspath(v.run.path), field_names=2,
        fill=dict(var="winterp", op="", mode="height", level=2.5, style="contourf",
                  cmap="viridis", rev=True, auto=False, vmin=-7.0, vmax=7.0, nlev=12,
                  alpha=0.8),
        diff=dict(on=True, run="", time="prev"),
        fills=[dict(on=True, var="thpert", mode="height", level=1.0, style="image",
                    cmap="RdBu_r", rev=False, auto=True, vmin=-5.0, vmax=5.0, alpha=0.6,
                    clip=False)],
        contours=[dict(on=True, var="winterp", mode="level", level=3, levels="5, 10",
                       color="#60a5fa", width=2.0, negdash=False)],
        vectors=[dict(on=True, q="wind", level=1.5, frame="ground", style="streamlines",
                      density=30, ref=15.0, color="#fbbf24")],
        section=dict(points=[[10.0, 10.0], [40.0, 30.0]], var="thpert", style="image",
                     cmap="magma", rev=False, auto=True, vmin=0.0, vmax=1.0, nlev=15,
                     ztop=12.0, diff=dict(on=False, run="", time=""),
                     contours=[dict(on=True, var="winterp", levels="auto", color="#ffffff",
                                    width=1.4, negdash=True)],
                     vectors=[dict(on=True, q="wind", frame="ground", density=40, ref=20.0,
                                   color="#e5e7eb")]))
    up = session.upgrade(json.loads(json.dumps(old)))
    assert up["atmo3d_session"] == FORMAT and "diff" not in up
    assert up["fill"]["field"] == "winterp" and up["fill"]["z"] == 2.5
    assert up["fill"]["minus"] == dict(run=None, time_s="prev")
    assert up["vectors"][0]["stream_n"] == 30 and up["contours"][0]["lw"] == 2.0
    assert up["section"]["fill"]["field"] == "thpert" and up["section"]["fill"]["minus"] is None
    assert v.apply_session(old) == []
    f = v.map_fill
    assert v.fill_var.value == "winterp" and float(v.fill_lvl.value) == 2.5
    assert (f["style"], f["cmap"], f["reverse"], f["auto"], f["vmin"], f["nlevels"]) == \
        ("contourf", "viridis", True, False, -7.0, 12)
    assert f["minus"]["time_s"] == "prev"
    assert v.fills[0]["field"] == "thpert" and v.fills[0]["clip"] is False
    o = v.ovs[0]
    assert (o["mode"], o["z"], o["levels"], o["neg_dashed"]) == ("level", 3, "5, 10", False)
    assert v.vecs[0]["style"] == "streamlines" and v.vecs[0]["stream_n"] == 30
    assert v.xs_fill.value == "thpert" and v.xs_main["cmap"] == "magma"
    assert "minus" not in v.xs_main.lay and v.xs_vecs[0]["across"] == 40


def test_session_of_another_run_reopens_the_page(viewer, demo_root, tmp_path):
    """Loading a session saved on another run sends the browser there (?session=)."""
    v = viewer
    s = v.session_state()
    s["run"] = os.path.join(demo_root, "demo", "supercell_weak")
    path = tmp_path / "weak.json"
    path.write_text(json.dumps(s))
    v.ses_path.value = str(path)
    v._on_load_session(None)
    assert v.ses_go.value == str(path)


def test_not_a_session_file(viewer, tmp_path):
    from atmo3d.viewer import session
    p = tmp_path / "x.json"
    p.write_text('{"a": 1}')
    with pytest.raises(ValueError):
        session.read(str(p))
    viewer.ses_path.value = str(p)
    viewer._on_load_session(None)
    assert "Could not load" in viewer.ses_msg.object


PARTS = ("soundings", "section", "view3d", "series", "distributions")


def _fresh(reg):
    from atmo3d.viewer import app as A
    run, F = reg.get()
    v = A.Viewer(run, F, reg=reg)
    v.main()
    return v


def test_session_soundings_section_and_3d(viewer, reg):
    """Soundings (a point, a box, a pinned time), the section with a contour and
    limits, and the 3D setup come back; the soundings and section are drawn again,
    the 3D scene only when the session is on the 3D workspace."""
    v = viewer
    v._add_sounding(20.0, 25.0, False)
    v._add_sounding(30.0, 30.0, True, (2.0, 2.0))
    v._pin_time()
    v.parcel.value = "mu"
    v.ps["tmin"].value = -30.0
    v.snd_lim["prof_x"] = {0: (1.0, 2.0)}
    v.xs_pts = [(10.0, 10.0), (40.0, 35.0)]
    v._draw_xs()
    v.xs_fill.value = "thpert"
    v._xs_add_contour()
    v.xs_smin.value = 5.0
    v._set_box((5.0, 20.0, 5.0, 20.0))
    v._set_seed_box((8.0, 12.0, 8.0, 12.0))
    v.v3_exag.value = 3.0
    v.isos[0]["val"].value = 7.0
    v._add_sv()
    v.st_on.value = True
    s1 = v.session_state()
    assert s1["soundings"]["zoom"]["prof_x"] == {"0": [1.0, 2.0]}  # (JSON keys)
    s1 = json.loads(json.dumps(s1))  # (as from a file)

    v2 = _fresh(reg)
    try:
        assert v2.apply_session(s1) == []
        s2 = v2.session_state()
        for k in PARTS[:3]:
            assert s2[k] == s1[k], k
        assert v2.points[2][2] == v.t and len(v2.points[1][1]) == 4
        assert v2.snd_lim["prof_x"] == {0: (1.0, 2.0)}
        assert len(v2.xs_ovs) == len(v.xs_ovs) and v2.xs_smin.value == 5.0
        assert v2.box == v.box and v2.seed_box == v.seed_box
        assert [e[0] for e in v2._item_entries()].count("snd") == 3
        wait(lambda: v2.snd_tabs.visible or v2.skew_png.visible, msg="soundings drawn")
        wait(lambda: "A (10.0, 10.0)" in (v2.xs_status.object or ""), msg="section drawn")
        assert v2.gen["3d"] == 0  # (on the Map workspace: not rendered)
    finally:
        v2.close()


def test_session_series_and_distributions(viewer, reg):
    """Series come back from the cache without a recompute; distributions are
    computed again at their times, in their order, the chosen one chosen."""
    v = viewer
    v.ser_field.value = "winterp"
    v.ser_reduce.value = "max"
    v._on_ser_compute(None)
    wait(lambda: not v.ser_go.disabled, tmax=300, msg="series")
    v.ser_y0.value = 1.0
    v.dist_field.value = "winterp"
    v._dist_request()
    wait(lambda: len(v.dists) == 1, msg="distribution 1")
    v.tslider.value = 2
    v.dist_z.value = 2.0
    v._dist_request()
    wait(lambda: len(v.dists) == 2, msg="distribution 2")
    v.dist_kind.value = "ecdf"
    v.dist_pick.value = next(iter(v.dists))
    s1 = json.loads(json.dumps(v.session_state()))

    v2 = _fresh(reg)
    try:
        assert v2.apply_session(s1) == []
        (k, s), = v2.series.items()
        assert int(s["ds"]["computed"].sum()) == len(v2.run.times)  # from the cache
        assert not v2.ser_go.disabled and "1 series" in v2.ser_status.object
        assert v2.ser_y0.value == 1.0 and v2.ser_pick.value == k
        wait(lambda: "from the session" in (v2.dist_status.object or ""),
             msg="distributions computed again")
        assert list(v2.dists) == list(v.dists)
        assert v2.dist_pick.value == next(iter(v.dists)) and v2.dist_kind.value == "ecdf"
        assert [d["color"] for d in v2.dists.values()] == \
            [d["color"] for d in v.dists.values()]
        assert v2.session_state()["series"] == s1["series"]
    finally:
        v2.close()


def test_session_of_the_map_only_keeps_the_rest(viewer):
    """A session without soundings, section, 3D, series or distributions (saved by
    the first version) leaves them as they are."""
    v = viewer
    v._add_sounding(20.0, 25.0, False)
    v.xs_pts = [(10.0, 10.0), (40.0, 35.0)]
    v._draw_xs()
    s = {k: x for k, x in v.session_state().items() if k not in PARTS}
    before = {k: v.session_state()[k] for k in PARTS}
    assert v.apply_session(s) == []
    assert {k: v.session_state()[k] for k in PARTS} == before


def test_session_keeps_the_figure(viewer, reg, tmp_path):
    """A figure of the user's goes in the session and comes back, with its save path and
    without running its code; only the example stays out."""
    from atmo3d.viewer import app as A
    v = viewer
    assert "figure" not in v.session_state()  # the example alone
    ed = v.figed

    def mine(d):
        d["suptitle"] = "kept"
        d["code"] = dict(d.get("code") or {}, on=True, text="x = 1")
    ed.shell.auto.value = False
    ed.shell.edit(mine)
    ed.path.value = str(tmp_path / "mine")
    s = json.loads(json.dumps(v.session_state()))
    assert s["figure"]["doc"]["suptitle"] == "kept" and "spec" not in s["figure"]

    run, F = reg.get()
    v2 = A.Viewer(run, F, reg=reg)
    v2.main()
    try:
        before = v2.gen["fig"]
        assert v2.apply_session(s) == []
        e2 = v2.figed
        doc = e2.shell.doc
        assert doc["suptitle"] == "kept" and e2.path.value == str(tmp_path / "mine")
        assert doc["code"]["text"] == "x = 1" and not doc["code"]["on"]
        assert e2.shell.auto.value and v2.gen["fig"] == before  # drawn when the workspace opens
        again = json.loads(json.dumps(v2.session_state()))["figure"]
        assert again["doc"]["suptitle"] == "kept"
    finally:
        v2.close()


def test_a_session_from_an_earlier_version_opens(viewer):
    """Sessions and autosaves used to hold the older form of the figure, under "spec"."""
    from conftest import new_spec
    ed = viewer.figed
    form = dict(new_spec(ed), suptitle="older")
    assert ed.open_state(dict(spec=form, part=0, save_as="/a/b"), "note") is None
    assert ed.shell.doc["version"] == 3 and ed.shell.doc["suptitle"] == "older"
    assert ed.path.value == "/a/b"


def _autosaved(ed):
    with open(ed._auto_path()) as f:
        return json.load(f)


def test_autosave_keeps_changes_and_the_earlier_figure(viewer, reg):
    """Nothing is written for the example; a changed figure is; a new page offers it and
    its first write keeps it to one side."""
    from atmo3d.viewer import app as A
    ed = viewer.figed
    for name in (ed._auto_path(), ed._auto_path("figure_earlier.json")):
        if os.path.exists(name):
            os.remove(name)
    ed.shell.auto.value = False
    ed.shell.showing = True  # (the workspace open: Auto-redraw off, an edit is kept at once)
    ed.shell._keep_figure()
    assert not os.path.exists(ed._auto_path())  # the example alone

    def title(text):
        return lambda d: d.update(suptitle=text)

    ed.shell.edit(title("first"))
    assert _autosaved(ed)["doc"]["suptitle"] == "first"
    assert ed._auto_earlier() is None  # this page's own is not offered back

    run, F = reg.get()
    v2 = A.Viewer(run, F, reg=reg)
    v2.main()
    try:
        e2 = v2.figed
        e2.shell.auto.value = False
        e2.shell.showing = True
        assert e2._auto_earlier()[0]["doc"]["suptitle"] == "first"
        e2.open_quick()
        assert e2.qs_earlier_row.visible
        e2.quick.hide()
        e2.shell.edit(title("second"))  # the example, changed: a figure of this page's
        assert _autosaved(e2)["doc"]["suptitle"] == "second"
        assert e2._auto_earlier()[0]["doc"]["suptitle"] == "first"
        e2._earlier = e2._auto_earlier()
        e2._quick_earlier()
        assert e2.shell.doc["suptitle"] == "first" and not e2.quick.open
    finally:
        v2.close()


def test_autosave_failure_is_said_once(viewer, monkeypatch):
    ed = viewer.figed

    def fail(*a, **k):
        raise OSError("no room")
    monkeypatch.setattr(os, "replace", fail)
    ed._autosave()
    assert "no room" in ed.msg.object
    ed.msg.object = ""
    ed._autosave()
    assert ed.msg.object == "" and ed._auto_failed
    assert not [n for n in os.listdir(os.path.dirname(ed._auto_path())) if n.endswith(".tmp")]




def test_cm1_map_has_no_boundaries(viewer):
    """An idealized run is not on the Earth: no Boundaries pill, no lat, lon in the
    hover, nothing in its session."""
    v = viewer
    assert v.geo is None and "geo" not in v.map_drawer.items
    assert "boundaries" not in v.session_state()
    hover = [t for t in v.fig.tools if type(t).__name__ == "HoverTool"
             and v.img_r in t.renderers][0]
    assert all(k != "lat, lon" for k, _ in hover.tooltips)
