"""The field catalog (atmo3d.core.catalog): the look of fields no table names, tidied
units and labels, renamed fields in saved files, and derived fields' layers and units.
(Each data type's own table: tests/<type>/test_<type>_outputs.py.)"""
import pytest

from atmo3d.core import catalog as C


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
