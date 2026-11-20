"""CM1's field table (atmo3d_cm1.outputs) and its catalog: every field CM1 writes, the
numbered ones, units per hour, tiers, and which winds play u, v, w."""
from atmo3d.core import catalog as C
from atmo3d_cm1 import outputs as cm1_outputs
from catalog_checks import base_state_looks_like_its_field, fake_fields, table_well_formed


def test_table_entries_are_well_formed():
    table_well_formed(cm1_outputs.OUTPUTS)


def test_base_state_looks_like_its_field():
    base_state_looks_like_its_field("cm1")


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

        def offers(self, name):  # (the data type offers no tools: pdecomp adds no fields)
            return False

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


def test_staggered_winds_play_the_roles_without_interpolated_ones():
    """A CM1 run with only staggered u, v, w: those play u, v, w (and are listed in the
    main lists); with uinterp... the interpolated ones do."""
    cat = C.of_model("cm1")
    only = cat.resolved({"u", "v", "w", "th"})
    assert (only.name("u"), only.name("v"), only.name("w")) == ("u", "v", "w")
    assert only.is_role("w", "w") and cat.name("w") == "winterp"
    assert cat.resolved({"uinterp", "vinterp", "winterp", "u", "v", "w"}) is cat
    F = fake_fields("cm1", ("u", "v", "w", "th", "th0", "qv", "qv0", "prs"))
    assert F.role("w") == "w" and F["w"].tier == "main" and "hdiv" in F
