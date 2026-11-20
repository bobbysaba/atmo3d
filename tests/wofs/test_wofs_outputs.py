"""WoFS's field table (atmo3d_wofs.outputs) and its catalog: the Heights group, tiers
(Other and hidden), and the field lists by tier."""
from atmo3d.core import catalog as C
from atmo3d_wofs import outputs as wofs_outputs
from catalog_checks import base_state_looks_like_its_field, fake_fields, table_well_formed


def test_table_entries_are_well_formed():
    table_well_formed(wofs_outputs.OUTPUTS)


def test_base_state_looks_like_its_field():
    base_state_looks_like_its_field("wofs")
    cat = C.of_model("wofs")
    assert cat.look("PRES0")[0].endswith("(first time)")  # A5: the change since the first time


def test_wofs_heights_group():
    """A6 (and zagl was in Microphysics before)."""
    cat = C.of_model("wofs")
    for n in ("zagl", "zmsl"):
        assert cat.group(n, 3) == "Heights"
        assert cat.look(n)[1:3] == ("km", 0.001)


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
    F = fake_fields("wofs", ("THETA", "W", "H_DIABATIC", "XLAT", "UH"))
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
