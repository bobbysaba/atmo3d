"""Characterization of what the viewer and figure code pick by default (field names,
isosurfaces, layers) on the CM1 demo run and a synthetic WoFS run.

Recorded before the atmo3d rebuild moved the names into per-data-type catalogs
(docs-dev/hardcoded-names.md, sections 1-4); since Phase 2 the code picks by role
(core.catalog) and WoFS's fields keep their WRF names.  A failure means a default
changed: fix the code if unintended, update the expected value if meant."""
import pytest

from atmo3d.figures import spec as fg
from atmo3d.figures.scene import next_iso
from atmo3d.registry import Registry
from test_wofs import make_wofs


@pytest.fixture(scope="module")
def wofs_pair(tmp_path_factory):
    root = make_wofs(str(tmp_path_factory.mktemp("exp") / "exp" / "20220523"))
    import os
    return Registry(os.path.dirname(root), 4, 2).get()


def _layers(run, F):
    s = fg.default_spec(run, F)
    return [(x["type"], x.get("field")) for x in s["layers"]]


def test_cm1_default_figure_layers(reg):
    run, F = reg.get()
    assert _layers(run, F) == [("fill", "dbz"), ("contour", "winterp"), ("vectors", "uinterp")] \
        or _layers(run, F)[:2] == [("fill", "dbz"), ("contour", "winterp")]
    assert not any(t == "boundaries" for t, _ in _layers(run, F))  # CM1 has no map


def test_wofs_default_figure_layers(wofs_pair):
    run, F = wofs_pair
    got = _layers(run, F)
    assert got[:3] == [("fill", "REFL_10CM"), ("contour", "W"), ("vectors", None)]
    assert got[-1][0] == "boundaries"  # a run with a map projection


def test_next_iso_order_cm1(reg):
    _, F = reg.get()
    isos = []
    for want in (("dbz", 30.0), ("winterp", 10.0), ("winterp", -5.0)):
        e = next_iso(F, isos)
        assert (e["var"], e["val"]) == want
        isos.append(e)


def test_next_iso_order_wofs(wofs_pair):
    _, F = wofs_pair
    isos = []
    for want in (("REFL_10CM", 30.0), ("W", 10.0), ("W", -5.0)):
        e = next_iso(F, isos)
        assert (e["var"], e["val"]) == want
        isos.append(e)


ROLES = ("u", "v", "w", "theta", "pres", "qv", "theta0", "pres0", "qv0", "u0", "v0", "refl")


def test_roles_name_each_data_types_own_fields(reg, wofs_pair):
    """The fields the viewer picks by role (hardcoded-names.md sections 1-5)."""
    want = dict(cm1=("uinterp", "vinterp", "winterp", "th", "prs", "qv", "th0", "prs0",
                     "qv0", "u0", "v0", "dbz"),
                wofs=("U", "V", "W", "THETA", "PRES", "QVAPOR", "THETA0", "PRES0",
                      "QVAPOR0", "U0", "V0", "REFL_10CM"))
    for run, F in (reg.get(), wofs_pair):
        assert tuple(F.role(r) for r in ROLES) == want[run.model], run.model
        assert tuple(run.role(r) for r in ROLES) == want[run.model], run.model
        assert run.catalog.sounding_names() == want[run.model][3:6] + want[run.model][:2]


def test_derived_fields_alike_in_both(reg, wofs_pair):
    """The core's derived fields are there for WoFS too, from WRF's names."""
    (_, F1), (_, F2) = reg.get(), wofs_pair
    for name in ("thpert", "prspert", "buoy", "thetae", "rh", "wspd", "hdiv", "sbcape"):
        assert name in F1 and name in F2, name
    assert F2["thpert"].deps == ("THETA", "THETA0")
    assert F1["thpert"].deps == ("th", "th0")
    assert F2["okubo"].deps == ("ddx.U", "ddy.U", "ddx.V", "ddy.V")
