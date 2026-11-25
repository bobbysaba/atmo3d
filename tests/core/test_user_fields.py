"""User-defined derived fields (core/userfields.py; docs/guide/user-fields.md): the
restricted evaluator and its escape suite, definitions read from the fields file,
analytic answers on the demo run (display units, built-in and user fields as inputs,
derivatives), why a field is left out, the menus, the series worker's binding, figures
and sessions that record and reuse a definition, and the export's attributes."""
import time

import numpy as np
import pytest

from atmo3d.core import userfields as U

T, K = 4, 3

FILE = """
[fields.tempf]
label = "Temperature"
units = "°F"
expr = "tempc * 9/5 + 32"
vrange = [20, 100]
note = "From tempc."

[fields.qv2]
label = "Twice qv"
units = "g/kg"
group = "Mine"
expr = "2 * qv"

[fields.tempf_k]
expr = "(tempf - 32) * 5/9 + 273.15"

[fields.stretch]
expr = "zvort * ddz.w"

[fields.ratio]
expr = "where(qv > 0, rh / qv, nan)"

[fields.mixed]
expr = "theta + 0 * sws"

[fields.gone]
expr = "qhail * 2"

[fields.loop_a]
expr = "loop_b + 1"

[fields.loop_b]
expr = "loop_a + 1"

[fields.rh]
expr = "qv"

[fields.colin]
expr = "uh25 * 2"

[fields.dderiv]
expr = "ddz.tempc"

[fields.evil]
expr = "().__class__"
"""


@pytest.fixture
def fields_file(tmp_path, monkeypatch):
    """A fields file with FILE in it, in use (the setting by its environment variable)."""
    p = tmp_path / "fields.toml"
    p.write_text(FILE, encoding="utf-8")
    monkeypatch.setenv("ATMO3D_FIELDS_FILE", str(p))
    U.reset()
    yield p
    U.reset()


@pytest.fixture
def F(reg, fields_file):
    from atmo3d.core.fields import Fields
    return Fields(reg.get()[0])


def off(F):
    return {u["name"]: why for u, why in F.user_off}


# ------------------------------------------------------------------ the evaluator
@pytest.mark.parametrize("text", [
    "__import__('os')", "().__class__", "tempc.__class__", "open('x')", "'a' * 10",
    "[x for x in tempc]", "lambda: 1", "tempc[0]", "f'{tempc}'", "np.sum(tempc)",
    "sqrt(x=1)", "(lambda: 0)()", "sqrt(*tempc)", "__builtins__", "_x + 1",
    "getattr(tempc, 'x')", "eval('1')", "exec('1')", "tempc if tempc else 0",
    "tempc and qv", "not tempc", "x := 1", "{1: 2}", "(1, 2)", "True", "None", "...",
    "sqrt", "a__d__b", "1; 2", "import os", "x" * 501,
])
def test_the_evaluator_refuses_what_is_not_arithmetic(text):
    with pytest.raises(U.Unsafe):
        U.compile_expr(text)


def test_numbers_are_floats_so_a_huge_power_does_not_hang():
    code, names = U.compile_expr("9**9**9**9 + 0 * a")
    t0 = time.time()
    with np.errstate(all="ignore"):
        v = U.evaluate(code, lambda n: np.zeros(3))
    assert time.time() - t0 < 1 and np.all(np.isinf(v)) and names == ("a",)


def test_inputs_and_derivatives_are_named():
    code, names = U.compile_expr("where(ddz.w > 0, sqrt(abs(theta)) * pi, nan) + gradh.qv")
    assert set(names) == {"ddz.w", "theta", "gradh.qv"}
    got = U.evaluate(code, lambda n: np.array([1.0, -1.0]) if n == "ddz.w" else np.ones(2))
    assert np.allclose(got[0], np.pi + 1) and np.isnan(got[1])


@pytest.mark.parametrize("raw, why", [
    ({"expr": "1", "colour": "red"}, "unknown setting colour"),
    ({"label": "x"}, "expr is missing"),
    ({"expr": "a", "vrange": [1]}, "vrange is two numbers"),
    ({"expr": "a.b"}, "attribute"),
])
def test_bad_definitions_say_why(raw, why):
    assert why in U.normalize("ok", raw, "file")["error"]


def test_bad_names_are_refused():
    for name in ("_x", "9a", "sqrt", "a-b"):
        assert U.normalize(name, {"expr": "1"}, "file")["error"]


def test_a_broken_file_is_a_problem_not_a_crash(tmp_path, monkeypatch):
    p = tmp_path / "fields.toml"
    p.write_text("[fields.x\nexpr = ", encoding="utf-8")
    monkeypatch.setenv("ATMO3D_FIELDS_FILE", str(p))
    U.reset()
    try:
        assert U.loaded() == [] and "fields.toml" in U.problems()[0]
    finally:
        U.reset()


def test_a_broken_file_is_one_greyed_entry_in_the_menus(reg, tmp_path, monkeypatch):
    from atmo3d.core.fields import Fields
    p = tmp_path / "fields.toml"
    p.write_text("[fields.x\nexpr = ", encoding="utf-8")
    monkeypatch.setenv("ATMO3D_FIELDS_FILE", str(p))
    U.reset()
    try:
        g = Fields(reg.get()[0]).groups()
        (grp, text, why), = g.off
        assert text == U.NOT_READ and grp.startswith("User") and "fields.toml" in why
    finally:
        U.reset()


def test_the_file_defaults_to_beside_the_settings(monkeypatch):
    import os

    from atmo3d import config
    monkeypatch.delenv("ATMO3D_FIELDS_FILE", raising=False)
    assert U.fields_path() == os.path.join(os.path.dirname(config.config_path()),
                                           "fields.toml")


# ------------------------------------------------------------------ on a run
def test_analytic_answers_on_the_demo_run(F):
    p = lambda n: F.plane(n, T, "level", K)  # noqa: E731
    assert np.nanmax(np.abs(p("tempf") - (p("tempc") * 9 / 5 + 32))) < 1e-4
    # inputs in display units: qv in g/kg, as the viewer shows it
    assert F["qv"].scale != 1 and np.nanmax(np.abs(p("qv2") - 2 * p("qv"))) < 1e-5
    # a user field of a user field
    assert np.nanmax(np.abs(p("tempf_k") - (p("tempc") + 273.15))) < 1e-3
    # a derivative input
    ref = p("zvort") * p("ddz.winterp")
    assert np.nanmax(np.abs(p("stretch") - ref)) <= 1e-6 * np.nanmax(np.abs(ref)) + 1e-12
    # 2D and 3D inputs broadcast; the field is 3D
    assert F["mixed"].ndim == 3 and np.nanmax(np.abs(p("mixed") - p("th"))) < 1e-4
    # the volume agrees with the level
    assert np.nanmax(np.abs(F.volume("tempf", T)[K] - p("tempf"))) < 1e-4


def test_a_field_that_cannot_be_made_says_why(F):
    o = off(F)
    assert "qhail" in o["gone"]
    assert "loop_a" in o["loop_a"] and "loop_b" in o["loop_b"]
    assert "shadows the built-in field rh" in o["rh"]
    assert "column field" in o["colin"]
    assert "derivatives of derived fields" in o["dderiv"]
    assert "attribute" in o["evil"]
    assert set(o) & set(F.defs) == {"rh"}  # (the built-in rh, not the user's)
    assert F["rh"].user is None  # (the built-in one wins)


def test_user_fields_are_listed_apart_and_marked(F):
    from atmo3d.viewer.fieldmenu import menu_tree
    g = F.groups(3)
    assert g["User · "]["Temperature [tempf] (user)"] == "tempf"
    assert g["User · Mine"]["Twice qv [qv2] (user)"] == "qv2"
    assert not any("tempf" in opts.values() for k, opts in g.items() if not k.startswith("User"))
    assert "= tempc * 9/5 + 32" in g.tips["tempf"] and "not reviewed" in g.tips["tempf"]
    assert not F["tempf"].confirmed and F["tempf"].tier == "main"
    user = next(n for n in menu_tree(g) if n.get("l") == "User")
    names = [c.get("v") for c in user["c"]]
    assert "tempf" in names and any(c.get("l") == "Mine" for c in user["c"])
    greyed = {c["l"]: c["off"] for c in user["c"] if "off" in c}
    assert "qhail" in greyed["gone [gone]"]


def test_the_series_worker_binds_them_from_the_task(F):
    from atmo3d.core import series
    run = F.run
    d = series._field_def("tempf_k", sorted(run.vars), run.model, F.user_task())
    assert d is not None and d.user["name"] == "tempf_k"
    assert set(d.natives) == set(F["tempf_k"].natives)
    rng = np.random.default_rng(0)
    vals = {n: rng.uniform(1, 2, 5) for n in d.deps}
    f = lambda n: vals[n]  # noqa: E731
    assert np.allclose(d.func(f, F.ctx), F["tempf_k"].func(f, F.ctx))
    # without the task it is not known there (the worker does not read the file)
    assert series._field_def("tempf_k", sorted(run.vars), run.model) is None


# ------------------------------------------------------------------ figures, exports
def _doc(field):
    return {"layers": [{"type": "fill", "field": field}], "runs": []}


def test_a_figure_records_its_user_fields(F):
    rec = U.record(_doc("tempf"))
    assert rec == {"tempf": {"label": "Temperature", "units": "°F",
                             "expr": "tempc * 9/5 + 32", "cmap": "viridis",
                             "vrange": [20.0, 100.0], "note": "From tempc."}}
    assert U.record(_doc("ddz.tempf")) == rec  # (a derivative of one too)
    assert U.record(_doc("rh")) == {}


def test_a_figure_brings_a_definition_the_user_lacks(reg, monkeypatch, tmp_path):
    from atmo3d.core.fields import Fields
    monkeypatch.setenv("ATMO3D_FIELDS_FILE", str(tmp_path / "none.toml"))
    U.reset()
    try:
        F = Fields(reg.get()[0])
        assert "tempf" not in F
        doc = dict(_doc("tempf"), user_fields={"tempf": {"expr": "tempc * 9/5 + 32",
                                                         "units": "°F"}})
        assert U.adopt(doc) == [] and doc["layers"][0]["field"] == "tempf"
        assert "tempf" in F and F["tempf"].user["source"] == "figure"
        # (no label recorded: its name)
        assert "tempf [tempf] (user) (from figure)" in F.groups()["User · "]
    finally:
        U.reset()


def test_a_figure_with_a_different_definition_keeps_its_own(F):
    same = dict(_doc("tempf"), user_fields={"tempf": {"expr": "tempc*9/5 + 32",
                                                      "units": "°F"}})
    assert U.adopt(same) == [] and same["layers"][0]["field"] == "tempf"
    doc = dict(_doc("tempf"), user_fields={"tempf": {"expr": "tempc * 2", "units": "°F"}})
    notes = U.adopt(doc)
    new = doc["layers"][0]["field"]
    assert new.startswith("tempf_") and new != "tempf" and list(doc["user_fields"]) == [new]
    assert "differs" in notes[0] and new in notes[0] and U.take_notes() == notes
    p = lambda n: F.plane(n, T, "level", K)  # noqa: E731
    assert np.nanmax(np.abs(p(new) - 2 * p("tempc"))) < 1e-4
    assert np.nanmax(np.abs(p("tempf") - (p("tempc") * 9 / 5 + 32))) < 1e-4


def test_a_saved_spec_carries_the_definitions(F, tmp_path):
    import json

    from atmo3d.figures.spec import bundle
    path = bundle.write_spec(_doc("tempf"), {"version": 2}, str(tmp_path / "f" / "s.json"))
    with open(path, encoding="utf-8") as f:
        saved = json.load(f)
    assert saved["user_fields"]["tempf"]["expr"] == "tempc * 9/5 + 32"
    assert saved["form"]["user_fields"] == saved["user_fields"]


def test_a_session_records_and_adopts(F):
    from atmo3d.viewer import session
    s = {"atmo3d_session": 3, "fill": {"var": "tempf"}, "figure": {"doc": _doc("tempf")}}
    s["user_fields"] = U.record(s)
    assert "tempf" in s["user_fields"]
    s["user_fields"]["tempf"]["expr"] = "tempc * 3"
    session.upgrade(s)
    new = s["fill"]["var"]
    assert new.startswith("tempf_") and s["figure"]["doc"]["layers"][0]["field"] == new


def test_an_export_says_what_the_field_was(F, tmp_path):
    import netCDF4

    from atmo3d.core import export as ex
    run = F.run
    p = ex.plan(run, F, ["tempf", "ddz.tempf"], [T], box=(-10, 10, -10, 10), ztop=4.0)
    r = ex.write(run, F, str(tmp_path / "u.nc"), p)
    with netCDF4.Dataset(r["path"]) as d:
        v = d["tempf"]
        assert v.atmo3d_expr == "tempc * 9/5 + 32" and v.atmo3d_inputs == "tempc"
        assert "user-defined" in v.comment
        assert "user-defined field tempf" in d["ddz_tempf"].comment


def test_a_series_of_a_user_field_runs_in_the_workers(F):
    """The reader processes are spawned: the task carries the definitions, and a changed
    definition is not answered from the cache."""
    from atmo3d.core import series as S
    run = F.run
    r = S.normalize(dict(field="tempf_k", vmode="height", z=1.0, region="domain",
                         reduce="max"))
    ds, skipped = S.compute(run, F, r, S.empty(run, r), times=[T], workers=1)
    assert not skipped
    ref = np.nanmax(F.plane("tempf_k", T, "height", 1.0))
    assert abs(ds.value.values[T] - ref) <= 1e-4 * abs(ref)
    before = S._cache_path(run, r)
    U._state["loaded"] = [dict(d, expr="tempc * 2") if d["name"] == "tempf" else d
                          for d in U._state["loaded"]]
    assert S._cache_path(run, r) != before  # (tempf_k uses tempf)


def test_the_docs_pages_examples_work(reg, tmp_path, monkeypatch):
    """Every field in docs/guide/user-fields.md's TOML blocks loads and is computed on
    the demo run."""
    import re
    import tomllib
    from pathlib import Path
    from atmo3d.core.fields import Fields
    page = (Path(__file__).resolve().parents[2] / "docs" / "guide"
            / "user-fields.md").read_text(encoding="utf-8")
    blocks = [b for b in re.findall(r"```toml\n(.*?)```", page, re.S) if "[fields." in b]
    text = "\n".join(blocks)
    names = list(tomllib.loads(text)["fields"])
    p = tmp_path / "fields.toml"
    p.write_text(text, encoding="utf-8")
    monkeypatch.setenv("ATMO3D_FIELDS_FILE", str(p))
    U.reset()
    try:
        F = Fields(reg.get()[0])
        F.sync_user()
        assert {u["name"]: why for u, why in F.user_off} == {}
        for n in names:
            v = F.plane(n, T, "level", K)
            assert np.isfinite(v).any(), n
    finally:
        U.reset()


# ------------------------------------------------------------------ layer functions
LAYERS = """
[fields.depth03]
expr = "layer_integral(0 * w + 1, 0, 3)"

[fields.thmean]
expr = "layer_mean(theta, 0.5, 3)"

[fields.wmax]
expr = "layer_max(w, 1, top)"

[fields.wmin]
expr = "layer_min(w, 1, 4)"

[fields.th1]
expr = "at_height(theta, 1.2)"

[fields.dth]
expr = "layer_mean(theta, 3, 6) - layer_mean(theta, 0, 1)"

[fields.lapse]
expr = "(at_height(tempc, 3) - at_height(tempc, 1)) / 2"

[fields.out]
expr = "layer_mean(w, 0, 3) - w"

[fields.lderiv]
expr = "layer_mean(ddz.w, 0, 3)"

[fields.l2d]
expr = "layer_mean(sws, 0, 3)"

[fields.uses_col]
expr = "thmean * 2"

[fields.nested]
expr = "layer_mean(layer_max(w, 0, 1), 0, 3)"

[fields.upside]
expr = "layer_mean(w, 3, 1)"

[fields.word]
expr = "layer_mean(w, 0, z)"
"""


@pytest.fixture
def LF(reg, tmp_path, monkeypatch):
    from atmo3d.core.fields import Fields
    p = tmp_path / "fields.toml"
    p.write_text(LAYERS, encoding="utf-8")
    monkeypatch.setenv("ATMO3D_FIELDS_FILE", str(p))
    U.reset()
    yield Fields(reg.get()[0])
    U.reset()


def _levels(run, z0, z1):
    """Each level's thickness (m) inside z0..z1 km and the levels that have some."""
    zf = np.asarray(run.zf, np.float64)
    top = zf[-1] if z1 is None else z1
    th = 1000 * (np.clip(zf[1:], z0, top) - np.clip(zf[:-1], z0, top))
    return th, th > 0


def test_layer_functions_are_column_fields(LF):
    for n in ("depth03", "thmean", "wmax", "wmin", "th1", "dth", "lapse"):
        assert LF[n].ndim == 2 and LF[n].column, n
    assert LF["thmean"].layer == (0.5, 3.0) and LF["wmax"].layer[1] is None
    assert LF["dth"].layer == (0.0, 6.0)


def test_layer_functions_analytic(LF):
    run = LF.run
    p = lambda n: LF.plane(n, T, "2d", 0)  # noqa: E731
    th, _ = _levels(run, 0, 3)
    assert np.allclose(p("depth03"), th.sum(), rtol=1e-6)
    # dz-weighted mean, max and min over the cells in the layer
    vol = lambda n: LF.volume(LF.role(n) or n, T).astype(np.float64)  # noqa: E731
    th, _ = _levels(run, 0.5, 3)
    ref = np.tensordot(th, vol("theta"), axes=1) / th.sum()
    assert np.nanmax(np.abs(p("thmean") - ref)) < 1e-3
    _, inl = _levels(run, 1, None)
    assert np.nanmax(np.abs(p("wmax") - vol("w")[inl].max(axis=0))) < 1e-5
    _, inl = _levels(run, 1, 4)
    assert np.nanmax(np.abs(p("wmin") - vol("w")[inl].min(axis=0))) < 1e-5
    # at_height: as the map's plane at that height
    assert np.nanmax(np.abs(p("th1") - LF.plane(LF.role("theta"), T, "height", 1.2))) < 1e-3
    lapse = (LF.plane("tempc", T, "height", 3) - LF.plane("tempc", T, "height", 1)) / 2
    assert np.nanmax(np.abs(p("lapse") - lapse)) < 1e-3
    # two layers side by side
    a, _ = _levels(run, 3, 6)
    b, _ = _levels(run, 0, 1)
    ref = (np.tensordot(a, vol("theta"), axes=1) / a.sum()
           - np.tensordot(b, vol("theta"), axes=1) / b.sum())
    assert np.nanmax(np.abs(p("dth") - ref)) < 1e-3


def test_layer_functions_that_cannot_be_made_say_why(LF):
    o = off(LF)
    assert "outside a layer function" in o["out"]
    assert "derivatives cannot be used inside layer functions" in o["lderiv"]
    assert "2D" in o["l2d"]
    assert "column field" in o["uses_col"]
    assert "nested" in o["nested"] or "inside another layer function" in o["nested"]
    assert "z1 above z0" in o["upside"]
    assert "numbers" in o["word"]


@pytest.mark.parametrize("text", ["layer_mean(w, 0)", "layer_mean(w, 0, 3, 4)",
                                  "layer_mean(1, 0, 3)", "at_height(w, top)",
                                  "layer_mean(w, -1, 3)", "layer_mean", "_L0(w)"])
def test_layer_functions_refuse_bad_arguments(text):
    with pytest.raises(U.Unsafe):
        U.compile_expr(text)


def test_the_series_worker_computes_a_layer_field(LF):
    from atmo3d.core import series as S
    run = LF.run
    r = S.normalize(dict(field="thmean", vmode="height", z=1.0, region="domain",
                         reduce="max"))
    ds, skipped = S.compute(run, LF, r, S.empty(run, r), times=[T], workers=1)
    assert not skipped
    ref = np.nanmax(LF.plane("thmean", T, "2d", 0))
    assert abs(ds.value.values[T] - ref) <= 1e-5 * abs(ref)


# ------------------------------------------------------------------ editing, reload
def test_reload_applies_a_changed_file_to_open_runs(F, fields_file):
    p = lambda n: F.plane(n, T, "level", K)  # noqa: E731
    before = p("qv2").copy()
    text = fields_file.read_text(encoding="utf-8").replace('expr = "2 * qv"',
                                                           'expr = "3 * qv"')
    text += '\n[fields.fresh]\nexpr = "layer_max(w, 0, 3)"\n'
    U.write_file(text)
    assert U.reload() == []
    assert "fresh" in F.defs and F["fresh"].column  # (no new Fields: the open one)
    assert np.nanmax(np.abs(p("qv2") - 1.5 * before)) < 1e-5  # (not the cached plane)


def test_write_file_refuses_what_atmo3d_could_not_read(fields_file):
    before = fields_file.read_text(encoding="utf-8")
    for bad in ("[fields.x\nexpr = 1", "fields = 3"):
        with pytest.raises(ValueError):
            U.write_file(bad)
    assert fields_file.read_text(encoding="utf-8") == before
    # a definition with an error is written: it is listed greyed out
    U.write_file('[fields.x]\nexpr = "w +"\n')
    defs, problem = U.parse_text(fields_file.read_text(encoding="utf-8"))
    assert not problem and defs[0]["error"]


def test_the_editor_saves_and_applies_on_the_page(viewer, fields_file):
    """Your fields (⚙ Settings): checked as typed, saved, then in the open page's menus
    and drawn, with no restart; the map showing a changed field is drawn anew."""
    from atmo3d.viewer.fieldsedit import report
    v, ed = viewer, viewer.settings.fields_ed
    v.settings.show_fields()
    assert v.settings.tabs.active == 2 and "tempf" in ed.text.value
    v.fill_var.value = "qv2"
    old = v.F.plane("qv2", 1, "level", 0).copy()
    text = ed.text.value.replace('expr = "2 * qv"', 'expr = "4 * qv"') + \
        '\n[fields.lowmax]\nlabel = "Low max w"\nexpr = "layer_max(w, 0, 2)"\n'
    ok, rows = report(text, v.F)
    assert ok and "lowmax" in rows and "column field" in rows
    ed.text.value = text
    ed._save()
    assert "applied" in ed.msg.object
    labels = {v_ for o in v.fill_var.groups.values() for v_ in o.values()}
    assert "lowmax" in v.F.defs, v.F.user_off
    assert "lowmax" in labels, getattr(v.fill_var.groups, "user_ndim", "-")
    assert v.fill_var.value == "qv2"
    assert np.nanmax(np.abs(v.F.plane("qv2", 1, "level", 0) - 2 * old)) < 1e-5
    # a 3D-only menu leaves the column field out
    assert "lowmax" not in {v_ for o in v.xs_fill.groups.values() for v_ in o.values()}
    # not TOML: not saved
    ed.text.value = "[fields.x\n"
    assert ed.save_btn.disabled and "not saved" in ed.check.object.lower()


def test_a_session_brings_its_fields_into_the_menus(viewer, fields_file):
    """The menus list a session's own fields once it is put back (no page reload)."""
    s = viewer.session_state()
    s["user_fields"] = {"brought": {"expr": "w * 3", "label": "Brought"}}
    viewer.apply_session(s)
    labels = {v_ for o in viewer.fill_var.groups.values() for v_ in o.values()}
    assert "brought" in labels
