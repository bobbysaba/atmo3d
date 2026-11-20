"""The field tables (atmo3d_cm1.outputs, atmo3d_wofs.outputs) and the catalog's look for
fields no table names (Phase 2b, step 1)."""

import pytest

from atmo3d.core import catalog as C
from atmo3d_cm1 import outputs as cm1_outputs
from atmo3d_wofs import outputs as wofs_outputs
from atmo3d.core.fields import CMAPS, GROUP_ORDER


@pytest.mark.parametrize("table", [cm1_outputs.OUTPUTS, wofs_outputs.OUTPUTS],
                         ids=["cm1", "wofs"])
def test_table_entries_are_well_formed(table):
    for name, e in table.items():
        assert len(e) == 7, name
        label, units, scale, cmap, vr, div, group = e
        assert label and not (label.isupper() and len(label) > 6), name  # (no raw WRF)
        assert cmap in CMAPS, (name, cmap)
        assert scale > 0, name
        assert vr is None or (len(vr) == 2 and vr[0] < vr[1]), name
        assert group in GROUP_ORDER, (name, group)
        assert " s-1" not in units and "m-2" not in units, (name, units)  # plain units


def test_cm1_table_has_every_field_cm1_writes():
    # a sample from each block of writeout.F / param.F (r19.5 and r21.1)
    for n in ("rain", "prate", "cpc", "thflux", "tslb5", "lwcf", "u10", "hpbl", "pwat",
              "wa500", "zh", "zhval", "thpert", "prspert", "qvpert", "buoyancy", "pv",
              "pi0", "th0", "prs0", "qv0", "u0", "v0", "kmh", "dissten", "qke", "xkzh",
              "swten", "effc", "thcuten", "pipb", "pgradc", "vtr", "thtavg", "wsptavg",
              "ptb_hadv", "qvb_mp", "ub_cor", "wb_buoy", "tt_cond", "qt_subl",
              "td_efall", "qhl", "ccw", "vhl", "zhl", "qni", "qir", "qzi", "ai1",
              "di3d_2", "p3_rhopo2"):
        assert n in cm1_outputs.OUTPUTS, n
    # budget terms CM1 does not write are not listed
    assert "wb_mp" not in cm1_outputs.OUTPUTS and "qvb_cor" not in cm1_outputs.OUTPUTS


def test_cm1_numbered_fields():
    d = cm1_outputs.describe
    assert d("pt3")[0] == "Passive tracer 3" and d("pt3")[1] == "g/kg"
    assert d("out2d1")[0] == "User 2D output 1"
    assert d("out12")[0] == "User 3D output 12"
    assert d("output") is None and d("qv") is None
    cat = C.of_model("cm1")
    assert cat.look("pt2")[0] == "Passive tracer 2"
    assert cat.group("out4", 3) == "Other model fields"


@pytest.mark.parametrize("key", ["cm1", "wofs"])
def test_base_state_looks_like_its_field(key):
    """A3: a base-state field shows in its full field's units, scale and colours."""
    cat = C.of_model(key)
    for full, base in (("theta", "theta0"), ("pres", "pres0"), ("qv", "qv0"),
                       ("u", "u0"), ("v", "v0")):
        f, b = cat.look(cat.name(full)), cat.look(cat.name(base))
        assert f[1:] == b[1:], (full, f, b)
        assert b[0].startswith("Base-state")
        assert cat.group(cat.name(base), 3) == "Base state"
    if key == "wofs":  # A5: the change since the first time
        assert cat.look("PRES0")[0].endswith("(first time)")


def test_wofs_heights_group():
    """A6 (and zagl was in Microphysics before)."""
    cat = C.of_model("wofs")
    for n in ("zagl", "zmsl"):
        assert cat.group(n, 3) == "Heights"
        assert cat.look(n)[1:3] == ("km", 0.001)


def test_unnamed_field_group_is_not_microphysics():
    assert C.of_model("cm1").group("somethingnew", 3) == "Other model fields"
    assert C.of_model("wofs").group("NEWFIELD", 3) == "Other model fields"


@pytest.mark.parametrize("raw, plain", [
    ("m s-1", "m/s"), ("kg m-2 s-1", "kg/m²/s"), ("m2 s-2", "m²/s²"), ("W m-2", "W/m²"),
    ("s-1", "1/s"), ("  kg(-1)", "#/kg"), ("m(3) kg(-1)", "m³/kg"), ("K", "K"),
    ("degree_north", "°N"), ("nondimensional", ""), ("-", ""), ("m^2/s", "m²/s"),
    ("flashes km-2 5min-1", "flashes km-2 5min-1"),  # (not understood: as it was)
])
def test_tidy_units(raw, plain):
    assert C.tidy_units(raw) == plain


def test_heat_and_moisture_budgets_per_hour():
    """θ / qv budgets and tendencies per hour, like the heating rates; u/v/w in m/s²."""
    o = cm1_outputs.OUTPUTS
    assert o["ptb_mp"][1:3] == ("K/h", 3600) and o["tt_cond"][1:3] == ("K/h", 3600)
    assert o["qvb_hadv"][1:3] == ("g/kg/h", 3.6e6) and o["swten"][1] == "K/h"
    assert o["wb_buoy"][1:3] == ("m/s²", 1)


def test_file_field_wins_over_same_derived():
    """A run whose files hold thpert / prspert lists theirs, not the derived ones;
    without them the derived ones are listed."""
    from atmo3d.core.fields import Fields
    from atmo3d.core.run import VarInfo

    class FakeRun:
        model, dx, dy, umove, vmove, storm_relative = "cm1", 1000.0, 1000.0, 0.0, 0.0, True
        catalog = C.of_model("cm1")

        def __init__(self, names):
            self.vars = {n: VarInfo(n, n, "", 3, None) for n in names}

        def has(self, n):
            return n in self.vars

    base = ("th", "th0", "prs", "prs0", "qv", "qv0")
    F = Fields(FakeRun(base + ("thpert", "prspert")))
    assert not F["thpert"].derived and not F["prspert"].derived
    assert F["thpert"].label == "θ′" and F["prspert"].units == "hPa"
    F = Fields(FakeRun(base))
    assert F["thpert"].derived and F["prspert"].derived


def test_wspd_renamed_in_files_saved_before():
    """The derived 3D wind speed is wspd3d (CM1's own wspd is 2D, the surface layer's).
    A figure or session saved before (no field_names) meant the derived one by wspd;
    one saved since means CM1's, and is left alone."""
    from atmo3d.figures.spec import bundle
    from atmo3d.viewer import session

    assert C.derived_renames({}) == {"wspd": "wspd3d"}
    assert C.derived_renames({"field_names": C.FIELD_NAMES}) == {}

    old = {"version": 3, "panels": [{"layers": [{"field": "wspd"}, {"field": "ddz.wspd"},
                                                {"cvar": "@wspd"}]}]}
    bundle.upgrade_names(old)
    assert [lay.get("field") or lay.get("cvar") for lay in old["panels"][0]["layers"]] \
        == ["wspd3d", "ddz.wspd3d", "@wspd3d"]
    assert old["field_names"] == C.FIELD_NAMES
    bundle.upgrade_names(old)  # (again: nothing changes)
    assert old["panels"][0]["layers"][0]["field"] == "wspd3d"

    new = {"version": 3, "field_names": C.FIELD_NAMES,
           "panels": [{"layers": [{"field": "wspd"}]}]}
    bundle.upgrade_names(new)
    assert new["panels"][0]["layers"][0]["field"] == "wspd"

    s = {"atmo3d_session": 2, "fill": {"field": "wspd"}, "figure": {"doc": old}}
    session.upgrade(s)
    assert s["fill"]["field"] == "wspd3d" and s["field_names"] == C.FIELD_NAMES
    s = {"atmo3d_session": 2, "field_names": C.FIELD_NAMES, "fill": {"field": "wspd"}}
    session.upgrade(s)
    assert s["fill"]["field"] == "wspd"


def test_saved_figures_carry_field_names(tmp_path):
    import json
    from atmo3d.figures.spec import bundle
    p = bundle.write_spec({"version": 3}, {"version": 2}, str(tmp_path / "f.json"))
    with open(p) as f:
        assert json.load(f)["form"]["field_names"] == C.FIELD_NAMES


def test_tidy_label_and_mixing_ratio():
    assert C.tidy("X", "UPWARD HEAT FLUX AT THE SURFACE", "W m-2")[:2] == \
        ("Upward heat flux at the surface", "W/m²")
    assert C.tidy("qxyz", "a mixing ratio", "kg kg-1")[1:3] == ("g/kg", 1000.0)
    lab, _, _, cmap, _, div = C.tidy("newvort", "", "s-1")
    assert lab == "Newvort" and div and cmap == "RdBu_r"


# ---- field tiers: main lists, "Other", hidden (Phase 2b field audit, 2026-11-18)
def _fake_fields(model, names):
    from atmo3d.core.fields import Fields
    from atmo3d.core.run import VarInfo

    class FakeRun:
        dx, dy, umove, vmove, storm_relative = 1000.0, 1000.0, 0.0, 0.0, True
        var_times = {}  # (pdecomp.register adds its fields here)

        def __init__(self):
            self.model = model
            self.vars = {n: VarInfo(n, n, "", 2 if n.isupper() and n not in
                                    ("U", "V", "W", "THETA", "PRES", "QVAPOR")
                                    else 3, None) for n in names}

        @property
        def catalog(self):
            return C.of_model(model).resolved(self.vars)

        def has(self, n):
            return n in self.vars

    return Fields(FakeRun())


def test_cm1_tiers():
    """CM1: pi, tke and the eddy coefficients, budgets, cref, rain and the swaths go
    under Other; the staggered winds too when the run has the interpolated ones."""
    cat = C.of_model("cm1")
    for n, g in (("pi", "Thermodynamics"), ("tke", "Turbulence"), ("kmh", "Turbulence"),
                 ("ub_hadv", "Budgets"), ("cref", "Swaths & 2D"), ("rain2", "Swaths & 2D"),
                 ("sws", "Swaths & 2D"), ("shs2", "Swaths & 2D")):
        assert cat.tier(n, g) == "other", n
    for n, g in (("th", "Thermodynamics"), ("dbz", "Radar"), ("cape", "Swaths & 2D")):
        assert cat.tier(n, g) == "main", n
    assert cat.tier("w", "Kinematics", {"w", "winterp"}) == "other"
    assert cat.tier("w", "Kinematics", {"w"}) == "main"
    assert "500 m mixed layer" in cm1_outputs.OUTPUTS["cape"][0]


def test_wofs_tiers():
    """WoFS: the audit's Other rows, the hidden blocks, and WRF fields the catalog does
    not name hidden too; REL_VORT is the vertical-vorticity role (2026-11-19)."""
    cat = C.of_model("wofs")
    for n in ("H_DIABATIC", "QNDROP", "PH", "REFD_MAX", "UP_HELI_MAX",
              "W_UP_MAX", "T2", "PSFC", "RAINNC", "PBLH", "RSCGHIS_2D"):
        assert cat.tier(n, "") == "other", n
    for n in ("XLAT", "MU", "RAINC", "SNOWH", "COSZEN", "NCI_W", "WSPD10UMAX",
              "SOME_NEW_WRF_FIELD"):
        assert cat.tier(n, "") == "hidden", n
    for n in ("THETA", "W", "REFL_10CM", "COMPOSITE_REFL_10CM", "UH", "HGT", "zagl",
              "REL_VORT"):
        assert cat.tier(n, "") == "main", n
    assert cat.name("zvort") == "REL_VORT" and cat.name("cref") == "COMPOSITE_REFL_10CM"
    assert (cat.name("fcor"), cat.name("u10"), cat.name("uh25")) == ("F", "U10", "UH")
    assert cat.kappa == 2.0 / 7.0 and C.of_model("cm1").kappa == 287.04 / 1005.7
    # CM1 lists a field it does not name (its namelist chose it)
    assert C.of_model("cm1").tier("some_new_field", "Other model fields") == "main"


def test_field_lists_by_tier(monkeypatch):
    """groups(): main groups, then "Other · <group>", then "Hidden · <group>" only with
    the show_hidden_fields setting; a hidden field stays known (a saved figure still
    draws it) and the fields are ordered main, Other, hidden."""
    from atmo3d import config
    from atmo3d.core import fields as FF
    F = _fake_fields("wofs", ("THETA", "W", "H_DIABATIC", "XLAT", "UH"))
    monkeypatch.setattr(FF, "show_hidden", lambda: False)
    g = F.groups()
    names = {n for v in g.values() for n in v.values()}
    assert "XLAT" not in names and "XLAT" in F and F["XLAT"].tier == "hidden"
    assert any(k.startswith(FF.OTHER_PREFIX) and "H_DIABATIC" in v.values()
               for k, v in g.items())
    assert not any(k.startswith(FF.HIDDEN_PREFIX) for k in g)
    keys = list(g)
    assert max(i for i, k in enumerate(keys) if not k.startswith(FF.OTHER_PREFIX)) < \
        min(i for i, k in enumerate(keys) if k.startswith(FF.OTHER_PREFIX))
    tiers = [F[n].tier for n in F.defs]
    assert tiers == sorted(tiers, key=["main", "other", "hidden"].index)
    monkeypatch.setattr(FF, "show_hidden", lambda: True)
    assert any(k.startswith(FF.HIDDEN_PREFIX) and "XLAT" in v.values()
               for k, v in F.groups().items())
    assert config.BY_NAME["show_hidden_fields"].default is False


def test_staggered_winds_play_the_roles_without_interpolated_ones():
    """A CM1 run with only staggered u, v, w: those play u, v, w (and are listed in the
    main lists); with uinterp... the interpolated ones do."""
    cat = C.of_model("cm1")
    only = cat.resolved({"u", "v", "w", "th"})
    assert (only.name("u"), only.name("v"), only.name("w")) == ("u", "v", "w")
    assert only.is_role("w", "w") and cat.name("w") == "winterp"
    assert cat.resolved({"uinterp", "vinterp", "winterp", "u", "v", "w"}) is cat
    F = _fake_fields("cm1", ("u", "v", "w", "th", "th0", "qv", "qv0", "prs"))
    assert F.role("w") == "w" and F["w"].tier == "main" and "hdiv" in F


def test_new_shear_and_helicity_layers():
    from atmo3d.core.fields import _sounding_kinematics
    got = {d.name: d.layer for d in _sounding_kinematics()}
    assert got["shear0250"] == (0.0, 0.25) and got["shear0500"] == (0.0, 0.5)
    assert got["shear03"] == (0.0, 3.0) and got["shear01"] == (0.0, 1.0)
    assert got["srh0250"] == (0.0, 0.25) and got["srh0500"] == (0.0, 0.5)
    assert got["srh01"] == (0.0, 1.0) and got["srh03"] == (0.0, 3.0)


def test_derivative_units_per_metre():
    from atmo3d.core.fields import FieldDef, deriv_def
    w = FieldDef("w", "w", "m/s", "Kinematics", vrange=(-20, 20))
    th = FieldDef("th", "θ", "K", "Thermodynamics")
    assert deriv_def("ddz", w).units == "1/s" and deriv_def("ddz", w).vrange == (-0.01, 0.01)
    assert deriv_def("ddx", th).units == "K/m"
    assert deriv_def("ddx", FieldDef("q", "q", "g/kg", "Microphysics")).units == "(g/kg)/m"
