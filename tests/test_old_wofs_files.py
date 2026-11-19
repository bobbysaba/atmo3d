"""Saved files from before the field catalogs (atmo3d plan, Phase 2.4) still open.

The fixtures in tests/data/old_files were written by the code before Phase 2 (session
format 1; figures as the editor holds them, a plan figure and a time-height one), for
the demo CM1 run and a synthetic WoFS run, with the run's path replaced by @RUN@ and
track files left out.  Then, WoFS's fields were renamed to CM1's names on read
(winterp, dbz, th, ...); now they keep their WRF names (W, REFL_10CM, THETA, ...), and
loading maps the old names through core.wofs_catalog.OLD_NAMES.  CM1 files load
unchanged."""
import copy
import json
import os

import pytest

from atmo3d.core.catalog import FIELD_KEYS, rename_fields, renames_for
from atmo3d.core.wofs_catalog import OLD_NAMES
from atmo3d.figures import spec as fg
from atmo3d.registry import Registry
from atmo3d.viewer import session as ses
from test_wofs import make_wofs

HERE = os.path.join(os.path.dirname(__file__), "data", "old_files")


def _load(name, run_path):
    with open(os.path.join(HERE, name + ".json")) as f:
        return json.loads(f.read().replace("@RUN@", run_path))


def _walk(obj, want, out):
    """Strings under keys `want` (a set) anywhere in a saved file, into out."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in want and isinstance(v, str):
                out.append(v)
            elif k in want and isinstance(v, list):
                out += [x for x in v if isinstance(x, str)]
            else:
                _walk(v, want, out)
    elif isinstance(obj, list):
        for v in obj:
            _walk(v, want, out)
    return out


def _fields(obj):
    return _walk(obj, FIELD_KEYS, [])


def _kinds(obj):
    return _walk(obj, {"kind"}, [])


def _old(name):
    """Whether a saved field value is a CM1-style WoFS name."""
    return name.removeprefix("@").partition(".")[2 if "." in name else 0] in OLD_NAMES


@pytest.fixture(scope="module")
def wofs_pair(tmp_path_factory):
    root = make_wofs(str(tmp_path_factory.mktemp("exp") / "exp" / "20220523"))
    return Registry(os.path.dirname(root), 4, 2).get()


# ---------------------------------------------------------------- the renaming itself
def test_rename_fields_only_under_field_keys():
    doc = dict(kind="th", label="dbz and winterp", title="th",
               layers=[dict(type="fill", field="dbz"),
                       dict(type="contour", field="ddz.winterp", color="k")],
               isos=[dict(var="winterp", color="#ffffff")], look=dict(color="@th"),
               fields=["qv", "thpert"], series=[dict(recipe=dict(field="th", op=""))])
    assert rename_fields(doc, OLD_NAMES) == 6
    assert doc["kind"] == "th" and doc["label"] == "dbz and winterp" and doc["title"] == "th"
    assert [x["field"] for x in doc["layers"]] == ["REFL_10CM", "ddz.W"]
    assert doc["layers"][1]["color"] == "k"
    assert doc["isos"][0] == dict(var="W", color="#ffffff")
    assert doc["look"]["color"] == "@THETA" and doc["fields"] == ["QVAPOR", "thpert"]
    assert doc["series"][0]["recipe"]["field"] == "THETA"
    assert rename_fields(doc, OLD_NAMES) == 0  # (again: nothing more)


def test_renames_for_one_data_type_only(reg, wofs_pair):
    cm1, wofs = reg.get()[0].path, wofs_pair[0].path
    assert renames_for([cm1]) == ({}, "")
    assert renames_for([wofs, wofs]) == (OLD_NAMES, "")
    table, note = renames_for([cm1, wofs])  # (one name cannot suit both)
    assert table == {} and "several data types" in note


# ---------------------------------------------------------------- CM1: unchanged
@pytest.mark.parametrize("name", ["cm1_figure_plan", "cm1_figure_th"])
def test_old_cm1_figures_load_unchanged(reg, name):
    run, _ = reg.get()
    doc = _load(name, run.path)
    was = copy.deepcopy(doc)
    fg.check_runs(doc)
    assert fg.upgrade_names(doc) == "" and doc == was


def test_old_cm1_session_loads_unchanged(reg):
    run, _ = reg.get()
    s = _load("cm1_session_v1", run.path)
    assert s["atmo3d_session"] == 1
    was = copy.deepcopy(s)
    assert ses.upgrade(s) == was


def test_old_cm1_session_applies(viewer):
    s = _load("cm1_session_v1", viewer.run.path)
    skipped = viewer.apply_session(s)
    assert not [x for x in skipped if x.split(" ")[0] in ("var", "field", "floor")], skipped
    assert not any(x.startswith("figure") for x in skipped), skipped
    assert viewer.fill_var.value == "cref" and viewer.v3_floor.value == "cref"


# ---------------------------------------------------------------- WoFS: renamed
@pytest.mark.parametrize("name", ["wofs_figure_plan", "wofs_figure_th"])
def test_old_wofs_figures_get_wrf_names(wofs_pair, name):
    run, F = wofs_pair
    doc = _load(name, run.path)
    assert any(_old(v) for v in _fields(doc))  # (the fixture names CM1-style fields)
    kinds = _kinds(doc)
    fg.check_runs(doc)  # (a WoFS member's path is a run, though not a folder)
    assert fg.upgrade_names(doc) == ""
    after = _fields(doc)
    assert not any(_old(v) for v in after), after
    assert "W" in after and "REFL_10CM" in after
    assert _kinds(doc) == kinds  # (a time-height panel's kind "th" is not a field)
    again = copy.deepcopy(doc)
    fg.upgrade_names(again)
    assert again == doc


def test_old_wofs_session_gets_wrf_names(wofs_pair):
    run, _ = wofs_pair
    s = _load("wofs_session_v1", run.path)
    assert s["atmo3d_session"] == 1
    figure = copy.deepcopy(s["figure"])
    ses.upgrade(s)
    rest = {k: v for k, v in s.items() if k != "figure"}
    assert not any(_old(v) for v in _fields(rest)), _fields(rest)
    assert s["fill"]["var"] == "REFL_10CM" and s["view3d"]["floor"] == "REFL_10CM"
    assert [c["var"] for c in s["contours"]] == ["W", "thpert", "REFL_10CM"]
    assert s["series"]["form"]["field"] == "W" and s["series"]["form"]["op"] == "ddz"
    assert s["figure"] == figure  # (left to the figure's own upgrade: fg.upgrade_names)


def test_old_wofs_session_applies(wofs_pair):
    from atmo3d.viewer import app as A
    reg = Registry(wofs_pair[0].path, 4, 2)
    run, F = reg.get()
    v = A.Viewer(run, F, reg=reg)
    try:
        v.main()
        skipped = v.apply_session(_load("wofs_session_v1", run.path))
        assert not [x for x in skipped if x.split(" ")[0] in ("var", "field", "floor")], \
            skipped
        assert not any(x.startswith("figure") for x in skipped), skipped
        assert v.fill_var.value == "REFL_10CM" and v.v3_floor.value == "REFL_10CM"
        assert v.ser_field.value == "W"
        assert [o["var"].value for o in v.ovs] == ["W", "thpert", "REFL_10CM"]
        layers = v.figed.shell.doc["layers"]
        assert sorted(lay.get("field") for lay in layers.values() if lay.get("field")) \
            == ["REFL_10CM", "W"]
    finally:
        v.close()


def test_new_sessions_are_format_2(viewer):
    assert viewer.session_state()["atmo3d_session"] == 2 == ses.FORMAT
