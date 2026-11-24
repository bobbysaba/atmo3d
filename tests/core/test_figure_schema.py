"""The settings schema (figures/schema, docs-dev/figures-ui-plan.md Phase 2): its rows are well
formed, and a row written at a level reads back, is that level's own and can be taken back, on
documents of every level; a new figure's defaults.  No viewer needed."""

import copy
import json

import pytest

from atmo3d.figures import schema as S
from atmo3d.figures.schema import KEEP, where as W
from atmo3d.figures.schema.where import Where


def test_rows_are_well_formed():
    assert len(S.ROWS) == len(S.BY_KEY)
    for r in S.ROWS:
        assert r.label and r.section, r.key
        assert set(r.levels) <= set(S.LEVELS), r.key
        assert set(r.kinds) <= set(S.ALL) and r.kinds, r.key
        assert not S.when_problems(r), (r.id, S.when_problems(r))
        if r.control.kind in ("choice", "multi"):
            assert r.control.options, r.key
        if r.default is not KEEP and not r.packed and r.key.startswith("look."):  # (as itself)
            back = r.as_.read(r.as_.show(r.default))
            assert json.dumps(back, default=float) == json.dumps(r.default, default=float) or \
                r.default in (None, ""), r.key


def test_search_finds_rows_by_label_and_section():
    keys = [r.key for r in S.search("tick every")]
    assert keys == ["look.axes.xstep", "look.axes.ystep"]
    assert {r.section for r in S.search("hodograph") if not r.types} <= \
        {"Hodograph", "Sounding panels"}
    assert all(r.kinds == ("scene",) for r in S.search("camera", kinds=("scene",)))
    assert S.search("") == []


def _doc():
    """A document with a value of each look block at every level: style, two kinds, two plan
    panels (one with an inset of its own) and a sounding."""
    return dict(
        version=3, size=[8.0, 6.0], grid=dict(rows=1, cols=3), runs=[],
        style=dict(font=dict(size=11.0, tick=8.0), letters=dict(on=True, auto=True, fmt="({a})"),
                   colorbar=dict(mode="shared", location="right", shrink=0.6),
                   legend=dict(where="panel", loc="lower left"), label_fit=True,
                   time_label=dict(on=True, fmt="", loc="lower right")),
        kinds=dict(plan=dict(axes=dict(xlabel="x (km)", ticks=True, xstep=5.0,
                                       title_bold=False),
                             domain=dict(mode="storm", half=15.0), coords="storm",
                             colorbar=dict(shrink=0.8)),
                   sounding=dict(axes=dict(xlabel="T"), skewt=dict(pmax=1000.0, layout="inset",
                                                                   hodo_marks=["rm"]))),
        layers={}, sections={},
        panels=[dict(id=0, kind="plan", cell=[0, 0, 1, 1], layers=[],
                     opts=dict(axes=dict(xlabel="own"), letters=dict(bold=False)),
                     insets=[dict(id=5, opts=dict(domain=dict(mode="box", box=[0, 1, 0, 1]),
                                                  coords="grid"))]),
                dict(id=1, kind="plan", cell=[0, 1, 1, 1], layers=[]),
                dict(id=2, kind="sounding", cell=[0, 2, 1, 1], layers=[],
                     opts=dict(skewt=dict(pmax=950.0)))])


PLACES = [Where("figure"), Where("kind", "plan"), Where("kind", "sounding"),
          Where("panel", "plan", 0), Where("panel", "plan", 1), Where("panel", "sounding", 2),
          Where("inset", "plan", 0, 5)]


def _look_rows():
    """The look rows a place's drawer writes through where.py (not a scene's: docedit's)."""
    return [r for r in S.ROWS if r.key.startswith("look.") and r.writer != "scene"]


@pytest.mark.parametrize("w", PLACES, ids=lambda w: f"{w.level}-{w.kind}-{w.pid}-{w.iid}")
def test_a_row_written_at_a_place_reads_back_and_is_taken_back(w):
    """Each look row written at each place it is offered: it reads back as written; below the
    figure it is the place's own, and taking it back leaves what the place inherited (when it
    had none of its own)."""
    bad = []
    for r in _look_rows():
        if not r.at(w.level) or (w.kind and w.kind not in r.kinds) or not S.when_ok(r, _doc(), w):
            continue
        doc = _doc()
        before, had = W.value(doc, r, w), w.level != "figure" and W.own(doc, r, w)
        shown = _changed(r, _sample(r) if before is KEEP else before)
        W.write(doc, r, w, shown)
        got = W.value(doc, r, w)
        if json.dumps(got, default=str) != json.dumps(shown, default=str):
            bad.append((r.key, "reads back", shown, got))
            continue
        if w.level in ("panel", "inset"):
            if not W.own(doc, r, w):
                bad.append((r.key, "own", False))
                continue
            W.take_back(doc, r, w)
            if not had and json.dumps(W.value(doc, r, w), default=str) != \
                    json.dumps(before, default=str):
                bad.append((r.key, "take back", before, W.value(doc, r, w)))
    assert not bad, bad[:5]


def test_a_new_figure_is_filled_with_the_defaults_it_lacks():
    s = S.filled(dict(axes=dict(xstep=2.0)))
    assert s["axes"]["xstep"] == 2.0 and s["axes"]["ystep"] == S.row("look.axes.ystep").default
    assert s["export"]["dpi"] == S.row("export.dpi").default and s["background"] == "white"
    assert "scene3d" not in s and "legend" not in s["ts"]  # (made whole / following the figure's)
    assert "layer" not in s["contour_key"] and "box" not in s["domain"]
    assert S.filled(copy.deepcopy(s)) == s


def _sample(r):
    k = r.control.kind
    if k == "choice":
        opts = r.control.options
        return list(opts.values())[0] if isinstance(opts, dict) else list(opts)[0]
    return {"toggle": False, "number": 1.0, "int": 2, "text": "t", "multi": []}.get(k, "x")


def _changed(r, shown):
    """Another value of its control than `shown`."""
    k = r.control.kind
    if k == "toggle":
        return not shown
    if k in ("number",):
        return (float(shown) if shown not in (None, "") else 0.0) + 1.0
    if k == "int":
        return int(shown or 1) + 1
    if k == "choice":
        opts = r.control.options
        vals = list(opts.values()) if isinstance(opts, dict) else list(opts)
        return next((v for v in vals if v != shown), shown)
    if k == "multi":
        opts = r.control.options
        return list(opts.values())[:1] if isinstance(opts, dict) else list(opts)[:1]
    if k in ("text", "longtext", "panels", "xy"):
        return {"panels": "a, b", "xy": "1.02, 1"}.get(k, f"{shown or ''}x")
    if k == "panel":
        return int(shown or 1) + 1
    if k == "layer":
        return 0
    if k == "box":
        return [0.0, 2.0, 0.0, 2.0]
    return shown


def test_a_panel_inherits_until_it_has_its_own():
    doc = _doc()
    xl = S.row("look.axes.xlabel")
    p1, k = Where("panel", "plan", 1), Where("kind", "plan")
    assert W.value(doc, xl, p1) == "x (km)" and not W.own(doc, xl, p1)
    W.write(doc, xl, p1, "mine")
    assert doc["panels"][1]["opts"] == {"axes": {"xlabel": "mine"}} and W.own(doc, xl, p1)
    W.write(doc, xl, k, "all")
    assert W.value(doc, xl, p1) == "mine" and W.value(doc, xl, Where("panel", "plan", 0)) == "own"
    W.take_back(doc, xl, p1)
    assert "opts" not in doc["panels"][1] and W.value(doc, xl, p1) == "all"


def test_letters_set_by_hand_are_no_longer_counted():
    doc = _doc()
    W.write(doc, S.row("look.letters.on"), Where(), False)
    assert doc["style"]["letters"] == dict(on=False, auto=False, fmt="({a})")
    W.write(doc, S.row("look.letters.on"), Where("panel", "plan", 1), True)
    assert doc["style"]["letters"]["auto"] is False and \
        doc["panels"][1]["opts"] == {"letters": {"on": True}}


def test_a_kind_has_its_own_colorbar_only_beside_another_kind():
    doc, r = _doc(), S.row("look.colorbar.shrink")
    assert S.offered(r, doc, Where("kind", "plan"))
    one = dict(doc, panels=doc["panels"][:2])
    assert not S.offered(S.row("look.colorbar.mode"), one, Where("kind", "plan"))
    assert W.own(doc, r, Where("kind", "plan")) and W.value(doc, r, Where("kind", "plan")) == 0.8
    W.take_back(doc, r, Where("kind", "plan"))
    assert "colorbar" not in doc["kinds"]["plan"]


def test_a_colorbar_place_writes_its_orientation_too():
    doc, r = _doc(), S.row("look.colorbar.location")
    assert W.value(doc, r, Where()) == "right"
    W.write(doc, r, Where(), "top")
    assert doc["style"]["colorbar"]["location"] == "top" and \
        doc["style"]["colorbar"]["orientation"] == "horizontal"


def test_a_scene_setting_goes_to_its_kind_until_scenes_differ():
    doc = dict(_doc(), panels=[dict(id=3, kind="scene", cell=[0, 0, 1, 1], layers=[])],
               kinds=dict(scene=dict(scene3d=dict(camera=dict(preset="top")))))
    az, exag = S.row("look.scene3d.camera.azimuth"), S.row("look.scene3d.exag")
    at = Where("panel", "scene", 3)
    assert W.value(doc, az, at) is None and W.value(doc, exag, at) == 2.0
    W.write(doc, az, at, 120.0)  # (the only scene: the kind's, its camera whole)
    assert doc["kinds"]["scene"]["scene3d"]["camera"] == dict(preset="top", azimuth=120.0)
    assert "opts" not in doc["panels"][0] and not W.own(doc, az, at)
    two = copy.deepcopy(doc)
    two["panels"].append(dict(id=4, kind="scene", cell=[0, 1, 1, 1], layers=[]))
    W.write(two, exag, Where("panel", "scene", 4), 3.0)
    assert two["panels"][1]["opts"] == {"scene3d": {"exag": 3.0}}
    assert W.value(two, exag, Where("panel", "scene", 3)) == 2.0
    W.take_back(two, exag, Where("panel", "scene", 4))
    assert "opts" not in two["panels"][1]


def test_a_new_figures_look_fills_in_what_a_figure_lacks():
    doc, r = _doc(), S.row("look.skewt.pmin")
    at = Where("panel", "sounding", 2)
    assert W.value(doc, r, at) is KEEP
    fresh = dict(kinds=dict(sounding=dict(skewt=dict(pmin=100.0))))
    assert W.value(doc, r, at, fallback=fresh) == 100.0
    assert W.value(doc, S.row("look.skewt.pmax"), at, fallback=fresh) == 950.0


def test_a_scene_list_item_is_read_and_written_in_its_list():
    doc = dict(_doc(), panels=[dict(id=3, kind="scene", cell=[0, 0, 1, 1], layers=[])],
               kinds=dict(scene=dict(scene3d=dict(isos=[dict(var="dbz", val=30.0),
                                                        dict(var="w", val=10.0)]))))
    val, col = S.row("look.scene3d.isos[].val"), S.row("look.scene3d.isos[].color")
    second = Where("kind", "scene", item=1)
    assert W.value(doc, val, second) == 10.0 and W.value(doc, col, second) == "#7dd3fc"
    W.write(doc, val, second, 12.5)
    assert doc["kinds"]["scene"]["scene3d"]["isos"] == [dict(var="dbz", val=30.0),
                                                        dict(var="w", val=12.5)]
    with pytest.raises(IndexError):
        W.write(doc, val, Where("kind", "scene", item=2), 1.0)


def test_a_scene_items_change_fills_in_the_rest_of_it():
    from atmo3d.core import vectors
    from atmo3d.figures.schema import fills
    doc = dict(_doc(), panels=[dict(id=3, kind="scene", cell=[0, 0, 1, 1], layers=[])],
               kinds=dict(scene=dict(scene3d=dict(
                   vecs=[dict(q="wind", ref=20.0)],
                   parcels=[dict(name="up", cvar="", color="#d62728", rule=dict(w_gt=5))]))))
    at = Where("kind", "scene", item=0)
    other = next(q for q in vectors.VECTORS if q != "wind")
    W.write(doc, S.row("look.scene3d.vecs[].q"), at, other)
    assert doc["kinds"]["scene"]["scene3d"]["vecs"][0]["ref"] == vectors.VECTORS[other].ref
    assert not S.offered(S.row("look.scene3d.parcels[].cmap"), doc, at)
    ctx = fills.Context(parcel_units=lambda v: "K" if v == "theta" else "",
                        pick=lambda c: dict(name="down", rule=dict(w_lt=-5), ids=None))
    W.write(doc, S.row("look.scene3d.parcels[].cvar"), at, "theta", ctx)
    par = doc["kinds"]["scene"]["scene3d"]["parcels"][0]
    assert par["units"] == "K" and par["vmin"] is None
    assert S.offered(S.row("look.scene3d.parcels[].cmap"), doc, at)
    W.write(doc, S.row("look.scene3d.parcels[].name"), at, "v:down", ctx)
    par = doc["kinds"]["scene"]["scene3d"]["parcels"][0]
    assert par["name"] == "down" and par["rule"] == dict(w_lt=-5)
