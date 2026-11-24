"""The layer rows of the settings schema (figures/schema/layer.py, docs-dev/figures-ui-plan.md
Phase 2.1b): well formed; read from the layer as a panel draws it; written through docedit as the
old layer cards wrote (a shared layer, a panel's change of it, a layer of the panel's own); shown
under the conditions the old cards' show() had; and what they fill in beside themselves.  That
nothing the old editor offered is lost: test_figure_inventory.py.  No viewer needed."""

import copy
import json

import pytest

from atmo3d.figures import schema as S
from atmo3d.figures.schema import KEEP, fills, where as W
from atmo3d.figures.schema.where import Where
from atmo3d.figures.shell import docedit as de

TYPES = {"fill", "contour", "shade", "vectors", "track", "line", "sector", "parcels",
         "boundaries", "series", "series:parcels", "series:table", "sounding", "dist",
         "profile", "profile:table", "joint", "azim", "table"}


def _doc():
    """Plan panels sharing a fill and contours (panel 1 changes the fill's colormap; panel 0
    has vectors of its own), a cross-section, and one panel of each kind with entries."""
    fill = dict(type="fill", on=True, field="dbz", mode="height", z=1.0, units="dBZ",
                cmap="viridis", reverse=False, white_first=False, vmin=0.0, vmax=60.0,
                nlevels=0, style="mesh", mask_below=None, extend="auto")
    cont = dict(type="contour", on=True, field="w", mode="height", z=3.0, levels="5, 10",
                color="k", lw=0.75, neg_dashed=True, clabel=False, legend="")
    vec = dict(type="vectors", on=True, vector="wind", z=0.0, spacing=2.0, zspacing=0.5,
               frame="ground", scale=250.0, width=0.002, color="k", key=0.0, style="arrows",
               density=1.5, slw=0.8, arrowsize=1.0, barb_len=5.5, barb_units="kt")
    series = dict(type="series", recipe=dict(field="w", vmode="layer", region="domain",
                                             reduce="max", z0=0.0, z1=10.0),
                  label="max w", op="", units="m/s", base_units="m/s", color="C0", lw=1.5,
                  ls="-", marker="", axis="auto", ylabel="", runs=None, ens="")
    psers = dict(type="series", source="parcels", recipe={}, runs=["r0"], name="up", var="w",
                 op="", ens="", ens_mid="mean", each=0, label="up: w")
    mine = dict(type="series", source="table", recipe={}, runs=[], table=dict(t=[0], v=[1]),
                label="My data", units="", base_units="")
    return dict(
        version=3, size=[8.0, 6.0], grid=dict(rows=2, cols=5),
        runs=[dict(id="r0", path="/a"), dict(id="r1", path="/b")], style={}, kinds={},
        layers=dict(l0=fill, l1=cont), sections={},
        panels=[
            dict(id=0, kind="plan", cell=[0, 0, 1, 1],
                 layers=[dict(ref="l0", over={}), dict(ref="l1", over={}), vec]),
            dict(id=1, kind="plan", cell=[0, 1, 1, 1],
                 layers=[dict(ref="l0", over=dict(cmap="Reds")), dict(ref="l1", over={})]),
            dict(id=2, kind="xsec", cell=[0, 2, 1, 1], layers=[copy.deepcopy(vec)]),
            dict(id=3, kind="line", cell=[0, 3, 1, 1], layers=[series, psers, mine]),
            dict(id=4, kind="dist", cell=[0, 4, 1, 1], layers=[dict(
                type="dist", run="r0", time_s=60.0, label="", color="",
                recipe=dict(field="w", vmode="height", region="domain", z=1.0, lo=None,
                            hi=None))]),
            dict(id=5, kind="table", cell=[1, 0, 1, 1], layers=[dict(
                type="table", what="sounding", runs=None, times_s=[60.0], params=[],
                where=dict(kind="trk", x=0.0, y=0.0, avg=0.0), stats=[],
                recipe=dict(field="w", vmode="height", region="domain", z=1.0))])])


SHARED = Where("kind", "plan", layer="l0")
P0, P1 = Where("panel", "plan", 0, layer=0), Where("panel", "plan", 1, layer=0)


def test_layer_rows_are_well_formed():
    ids = [r.id for r in S.ROWS]
    assert len(ids) == len(set(ids))
    for r in S.ROWS:
        if not r.types:
            continue
        assert r.key.startswith("layer."), r.id
        assert set(r.types) <= TYPES, r.id
        assert set(r.levels) <= {"kind", "panel", "inset"}, r.id
        if r.control.kind in ("choice", "multi"):
            assert r.control.options, r.id
        if r.default is not KEEP and not r.packed:  # (a default reads back as itself, or as
            back = r.as_.read(r.as_.show(r.default))  # no key: a box only saved when ticked)
            assert back is de.MISSING or r.default in (None, "", False) or \
                json.dumps(back, default=float) == json.dumps(r.default, default=float), r.id
        assert not S.when_problems(r), (r.id, S.when_problems(r))
    assert len([r for r in S.ROWS if r.types]) > 200


def test_a_key_has_a_row_per_meaning():
    assert S.row_for("layer.cmap", "fill").id == "layer.cmap~fill"
    assert S.row_for("layer.cmap", "parcels").when == "cvar"
    assert S.row_for("layer.op", "series").control.options != \
        S.row_for("layer.op", "series:parcels").control.options
    assert S.row_for("layer.levels", "contour").control.kind == "levels"
    assert [r.key for r in S.layer_rows("contour", "plan", "kind")][:3] == \
        ["layer.on", "layer.run", "layer.field"]


def test_a_layer_is_read_as_a_panel_draws_it():
    doc, cmap = _doc(), S.row_for("layer.cmap", "fill")
    assert W.value(doc, cmap, SHARED) == "viridis"
    assert W.value(doc, cmap, P0) == "viridis"
    assert W.value(doc, cmap, P1) == "Reds"
    assert not W.own(doc, cmap, P0) and W.own(doc, cmap, P1) and not W.own(doc, cmap, SHARED)
    z = S.row_for("layer.recipe.z0", "series")
    assert W.value(doc, z, Where("panel", "line", 3, layer=0)) == 0.0
    assert W.value(doc, S.row_for("layer.recipe.pct", "series"),
                   Where("panel", "line", 3, layer=0)) == 99.0  # (none saved: its default)


@pytest.mark.parametrize("key,shown", [("layer.cmap", "Blues"), ("layer.vmax", 50.0),
                                       ("layer.on", False), ("layer.levels", "1, 2"),
                                       ("layer.z", 2.0)])
@pytest.mark.parametrize("at", [SHARED, P0, P1, Where("kind", "plan", layer="l1"),
                                Where("panel", "plan", 1, layer=1)])
def test_writing_a_layer_row_is_docedits_write(key, shown, at):
    doc = _doc()
    lay = W.layer_at(doc, at)
    r = S.row_for(key, lay["type"])
    if r is None:
        return
    want = _doc()
    if at.level == "kind":
        de.write_shared(want, at.layer, {r.key.split(".")[1]: r.as_.read(shown)})
    else:
        de.write_panel(want, de.panel_by_id(want, at.pid), at.layer,
                       {r.key.split(".")[1]: r.as_.read(shown)})
    W.write(doc, r, at, shown)
    assert doc == want
    assert W.value(doc, r, at) == shown


def test_a_panels_change_is_taken_back():
    doc, cmap = _doc(), S.row_for("layer.cmap", "fill")
    W.take_back(doc, cmap, P1)
    assert W.value(doc, cmap, P1) == "viridis" and not W.own(doc, cmap, P1)
    W.write(doc, cmap, P0, "viridis")  # (the shared layer's: no change of its own)
    assert de.places(doc, de.panel_by_id(doc, 0))[0]["over"] == {}


def test_a_nested_key_writes_its_block_whole():
    doc, at = _doc(), Where("panel", "line", 3, layer=0)
    W.write(doc, S.row_for("layer.recipe.region", "series"), at, "track")
    r = doc["panels"][3]["layers"][0]["recipe"]
    assert r["region"] == "track" and r["radius"] == 5.0 and r["offset"] == [0.0, 0.0]
    assert r["z0"] == 0.0 and r["field"] == "w"  # (the recipe's other keys stay)
    W.write(doc, S.row_for("layer.recipe.offset", "series"), at, "2, -3")
    assert doc["panels"][3]["layers"][0]["recipe"]["offset"] == [2.0, -3.0]
    W.write(doc, S.row_for("layer.recipe.region", "series"), at, "domain")
    assert "radius" not in doc["panels"][3]["layers"][0]["recipe"]  # (normal form)


def _offered(doc, key, at):
    lay = W.layer_at(doc, at)
    r = S.row_for(key, W.layer_type(lay))
    return r is not None and S.offered(r, doc, at)


def test_a_row_shows_when_the_old_card_showed_it():
    doc = _doc()
    cont = Where("kind", "plan", layer="l1")
    assert not _offered(doc, "layer.clabel_size", cont)
    W.write(doc, S.row_for("layer.clabel", "contour"), cont, True)
    assert _offered(doc, "layer.clabel_size", cont)
    vec, xvec = Where("panel", "plan", 0, layer=2), Where("panel", "xsec", 2, layer=0)
    for at in (vec, xvec):
        W.write(doc, S.row_for("layer.style", "vectors"), at, "barbs")
    assert _offered(doc, "layer.barb_len", vec) and not _offered(doc, "layer.scale", vec)
    assert not _offered(doc, "layer.barb_len", xvec) and _offered(doc, "layer.scale", xvec)
    assert _offered(doc, "layer.zspacing", xvec) and not _offered(doc, "layer.zspacing", vec)
    assert _offered(doc, "layer.z", vec)
    doc["panels"][0]["z"] = 2.0  # (a panel at its own height: the layer's is the panel's)
    assert not _offered(doc, "layer.z", vec) and _offered(doc, "layer.z_fixed", vec)
    assert _offered(doc, "layer.run", SHARED)
    W.write(doc, S.row_for("layer.ens", "fill"), SHARED, True)
    assert not _offered(doc, "layer.run", SHARED) and _offered(doc, "layer.ens.stat", SHARED)
    assert not _offered(doc, "layer.cmap", Where("kind", "plan", layer="l1"))  # (not a fill's)
    tab = Where("panel", "table", 5, layer=0)
    assert _offered(doc, "layer.where.x", tab) and not _offered(doc, "layer.stats", tab)
    W.write(doc, S.row_for("layer.what", "table"), tab, "field")
    assert not _offered(doc, "layer.where.x", tab) and _offered(doc, "layer.stats", tab)
    assert _offered(doc, "layer.recipe.z", tab)


def test_a_colorbar_setting_of_a_panels_layer_is_in_its_colorbar_section():
    doc = _doc()
    assert not _offered(doc, "layer.cbar_label", P0)  # (the panel's Colorbar section has it)
    assert _offered(doc, "layer.cmap", P0)


def test_what_a_change_fills_in():
    doc = _doc()
    reduce = S.row_for("layer.reduce.op", "fill")
    W.write(doc, reduce, SHARED, "max")
    assert doc["layers"]["l0"]["reduce"] == dict(op="max", t0=None, t1=None, every=1)
    W.write(doc, S.row_for("layer.reduce.every", "fill"), SHARED, 3)
    W.write(doc, reduce, SHARED, "")
    assert "reduce" not in doc["layers"]["l0"]
    vec = Where("panel", "plan", 0, layer=2)
    W.write(doc, S.row_for("layer.vector", "vectors"), vec, "vort")
    from atmo3d.core import vectors
    if "vort" in vectors.VECTORS:
        assert doc["panels"][0]["layers"][2]["scale"] == \
            vectors.FIG_SCALE * vectors.VECTORS["vort"].ref
    W.write(doc, S.row_for("layer.minus", "fill"), SHARED, True)
    lay = doc["layers"]["l0"]
    assert lay["minus"] == dict(run=None, time_s=None, grid="ask")
    assert lay["cmap"] == "RdBu" and lay["vmin"] == -lay["vmax"]
    W.write(doc, S.row_for("layer.ens", "fill"), SHARED, True)
    assert "minus" not in doc["layers"]["l0"]  # (an ensemble: no difference beside it)
    W.write(doc, S.row_for("layer.ens.stat", "fill"), SHARED, "prob")
    assert doc["layers"]["l0"]["vmax"] == 100.0 and doc["layers"]["l0"]["cmap"] == "Blues"
    W.write(doc, S.row_for("layer.ens", "fill"), SHARED, False)
    assert "ens" not in doc["layers"]["l0"]


def test_an_entrys_runs_and_units_follow():
    doc = _doc()
    tab = Where("panel", "table", 5, layer=0)
    W.write(doc, S.row_for("layer.runs", "table"), tab, ["r1"])
    assert doc["panels"][5]["layers"][0]["run"] == "r1"
    ser = Where("panel", "line", 3, layer=0)
    W.write(doc, S.row_for("layer.op", "series"), ser, "ddz")
    from atmo3d.figures import spec as fg
    assert doc["panels"][3]["layers"][0]["units"] == fg.op_units("m/s", "ddz") != "m/s"
    mine = Where("panel", "line", 3, layer=2)
    W.write(doc, S.row_for("layer.units", "series:table"), mine, " mm ")
    assert doc["panels"][3]["layers"][2]["base_units"] == "mm"
    par = Where("panel", "line", 3, layer=1)
    assert W.value(doc, S.row_for("layer.runs", "series:parcels"), par) == "r0"
    W.write(doc, S.row_for("layer.runs", "series:parcels"), par, "r1")
    assert doc["panels"][3]["layers"][1]["runs"] == ["r1"]


def test_a_parcel_set_picked_brings_its_rule():
    doc = _doc()
    picked = dict(name="down", color="#123456", rule=dict(w_lt=-5), ids=None)
    ctx = fills.Context(pick=lambda c: picked if c == "v:down" else None)
    par = Where("panel", "line", 3, layer=1)
    W.write(doc, S.row_for("layer.name", "series:parcels"), par, "v:down", ctx)
    lay = doc["panels"][3]["layers"][1]
    assert lay["name"] == "down" and lay["rule"] == dict(w_lt=-5)
    W.write(doc, S.row_for("layer.name", "series:parcels"), par, "v:gone", ctx)
    assert doc["panels"][3]["layers"][1]["name"] == "down"  # (nothing to take: unchanged)


def test_own_line_looks_of_a_sounding():
    doc = _doc()
    doc["panels"][4] = dict(id=4, kind="sounding", cell=[0, 4, 1, 1], layers=[dict(
        type="sounding", run="r0", time_s=0.0, where=dict(kind="trk"), label="", color="")])
    at = Where("panel", "sounding", 4, layer=0)
    own = S.row_for("layer.own_looks", "sounding")
    assert W.value(doc, own, at) is False and not _offered(doc, "layer.T_color", at)
    W.write(doc, own, at, True)
    assert doc["panels"][4]["layers"][0]["T_color"] == "#d62728"
    assert W.value(doc, own, at) is True and _offered(doc, "layer.T_color", at)
    W.write(doc, own, at, False)
    assert not any(k.startswith(("T_", "Td_", "Tp_")) for k in doc["panels"][4]["layers"][0])


def test_a_source_of_its_own_is_a_type_of_its_own():
    doc = _doc()
    mine, par = Where("panel", "line", 3, layer=2), Where("panel", "line", 3, layer=1)
    assert _offered(doc, "layer.table", mine) and _offered(doc, "layer.var", par)
    assert not S.offered(S.row_for("layer.recipe.field", "series"), doc, mine)
    assert not S.offered(S.row_for("layer.table", "series:table"), doc,
                         Where("panel", "line", 3, layer=0))


def test_no_layer_there_is_an_error():
    with pytest.raises(IndexError):
        W.write(_doc(), S.row_for("layer.on", "fill"), Where("panel", "plan", 1, layer=7), True)
    assert W.value(_doc(), S.row_for("layer.on", "fill"),
                   Where("panel", "plan", 1, layer=7)) is True  # (its default)
