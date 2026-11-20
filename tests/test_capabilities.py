"""Characterization of the capability flags and gates per data type (CM1 demo run, synthetic
WoFS run): docs-dev/hardcoded-names.md, "Model gates", sections A and B.

Phase 3 replaces the data-type tests with capability checks; these tests pin what each
type has now, so that the replacement changes nothing for CM1 and WoFS."""
import os

import pytest

from atmo3d_cm1 import pdecomp
from atmo3d_cm1 import parcels
from atmo3d.registry import Registry
from test_wofs import make_wofs


@pytest.fixture(scope="module")
def wofs_run(tmp_path_factory):
    root = make_wofs(str(tmp_path_factory.mktemp("exp") / "exp" / "20220523"))
    return Registry(os.path.dirname(root), 4, 2).get()[0]


def test_cm1_flags(reg):
    run = reg.get()[0]
    assert run.model == "cm1" and run.model_label == "CM1"
    assert run.terrain is False and run.traced_parcels is False
    assert run.storm_relative is True and run.geo is None


def test_wofs_flags(wofs_run):
    run = wofs_run
    assert run.model == "wofs" and run.model_label == "WoFS"
    assert run.terrain is True and run.traced_parcels is True
    assert run.storm_relative is False and run.geo is not None


def test_pressure_decomposition_is_cm1_only(wofs_run):
    assert pdecomp.can_compute(wofs_run) is False


def test_no_parcels_for_wofs(wofs_run):
    # (Bobby 2026-11-19: WoFS has no parcels, traced or otherwise)
    assert parcels.offered(wofs_run) is False and parcels.for_run(wofs_run) is None


def test_parcels_of_the_cm1_demo_come_from_files(reg):
    run = reg.get()[0]
    assert parcels.offered(run) == bool(parcels.find_files(run.path))


def test_members_only_for_wofs(reg, wofs_run):
    from atmo3d.core import models
    assert models.parts(reg.get()[0].path) == []
    assert len(models.parts(os.path.dirname(os.path.dirname(wofs_run.path)))) >= 1 \
        or models.root_of(wofs_run.path) != wofs_run.path


def test_model_registry_keys():
    from atmo3d.core import models
    assert {"cm1", "wofs"} <= set(models.MODELS)


# ---- Phase 3: capabilities (core.capabilities) and the panel registry (viewer.panels)

def test_capabilities_cm1(reg):
    from atmo3d.core import capabilities, track
    run = reg.get()[0]
    assert run.offers("soundings") and run.offers("pdecomp") and run.offers("tracking")
    assert not run.offers("terrain") and not run.offers("geo")
    assert not run.offers("native_polar")
    assert run.can("pdecomp") == pdecomp.can_compute(run)
    assert run.can("parcels") == parcels.offered(run)
    assert run.can("tracking") == track.available(run)
    assert run.can("storm_relative") and not run.can("traced_parcels")
    assert capabilities.of(run) == {n for n in capabilities.CAPS if run.can(n)}


def test_capabilities_wofs(wofs_run):
    run = wofs_run
    assert not run.offers("pdecomp") and not run.can("pdecomp")
    assert run.can("terrain") and run.can("geo")
    assert not run.offers("parcels") and not run.can("parcels")
    assert not run.can("storm_relative")
    assert run.offers("soundings") and run.offers("tracking")


def test_unknown_capability(reg):
    with pytest.raises(KeyError):
        reg.get()[0].can("no such thing")


def test_registry_order_is_the_saved_tab_number():
    from atmo3d.viewer import panels
    keys = ["Sounding", "Cross-section", "Track", "Series", "Distribution", "Parcels"]
    assert [panels.index(k) for k in keys] == list(range(6))
    assert [panels.at(i) for i in range(6)] == keys
    assert panels.index("3D region") is None  # (a tool with no panel)
    assert panels.tool_of("Area sounding") == "Sounding"
    assert panels.tool_of("Seed box") == "3D region" and panels.panel_of("Seed box") is None
    assert panels.panel_of("Parcel box") == "Parcels" and panels.panel_of(None) is None


@pytest.mark.parametrize("which", ["cm1", "wofs"])
def test_panels_and_rail_per_data_type(which, reg, wofs_run):
    from atmo3d.core import track
    from atmo3d.viewer import panels
    run = reg.get()[0] if which == "cm1" else wofs_run
    built, rail = panels.for_run(run)
    # the built-in panels, in their registry order (WoFS: no parcels)
    assert [t.key for t in built] == ["Sounding", "Cross-section", "Track", "Series",
                                      "Distribution"] + (["Parcels"] if which == "cm1" else [])
    # Track and Parcels only when the run has them (parcels.offered: False for WoFS)
    want = ["Sounding", "Cross-section"] + (["Track"] if track.available(run) else []) \
        + ["Series", "Distribution"] + (["Parcels"] if parcels.offered(run) else []) \
        + ["3D region"]
    assert [t.key for t in rail] == want


def test_a_data_type_panel_is_built_only_where_offered(reg):
    from atmo3d.viewer import panels
    run = reg.get()[0]
    before = panels.tools()
    try:
        panels.register(panels.Tool("PPI", "PPI", "radar", "Native radar sweeps",
                                    layout=lambda v: None, needs="native_polar"))
        built, rail = panels.for_run(run)
        assert "PPI" not in [t.key for t in built] + [t.key for t in rail]
        assert panels.index("PPI") == 6  # after the built-in panels
    finally:
        panels._TOOLS[:] = before


def test_viewer_panels_by_key(viewer):
    v = viewer
    assert v.panel_keys[:6] == ["Sounding", "Cross-section", "Track", "Series",
                                "Distribution", "Parcels"]
    v._show_panel(True, "Series")
    assert v.tabs.active == 3 and v._panel_open("Series") and v.mode.value == "Series"
    v._show_panel(True, 1)  # a saved session's tab number
    assert v._panel() == "Cross-section" and v.mode.value == "Cross-section"
    v._show_panel(True, "No such panel")  # ignored
    assert v._panel() == "Cross-section"


def test_session_records_the_panel_key(viewer):
    v = viewer
    v._show_panel(True, "Series")
    p = v.session_state()["panel"]
    assert p["key"] == "Series" and p["tab"] == 3
    # a session from before keys: by its registry place
    v._show_panel(False)
    v._put_tool("Cross-section", {"open": True, "tab": 1})
    assert v._panel_open("Cross-section")
    # a key this viewer has no panel for (its package not installed): stays closed
    v._show_panel(False)
    v._put_tool(None, {"open": True, "tab": 6, "key": "PPI"})
    assert not v.panel_col.visible
