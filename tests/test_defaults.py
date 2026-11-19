"""Characterization of what the viewer and figure code pick by default (field names,
isosurfaces, layers) on the CM1 demo run and a synthetic WoFS run.

These record today's behavior, before the atmo3d rebuild moves the names into per-data-type
catalogs (docs-dev/hardcoded-names.md, sections 1-4).  A failure after a later phase means a
default changed: fix the code if unintended, update the expected value if the phase meant it
(Phase 2 turns the WoFS names into WRF names, so the WoFS expectations will move then)."""
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
    assert got[0][0] == "fill" and got[0][1] in ("dbz", "cref")
    assert ("contour", "winterp") in got or "winterp" not in F
    assert got[-1][0] == "boundaries"  # a run with a map projection


def test_next_iso_order_cm1(reg):
    _, F = reg.get()
    isos = []
    for want in (("dbz", 30.0), ("winterp", 10.0), ("winterp", -5.0)):
        e = next_iso(F, isos)
        assert (e["var"], e["val"]) == want
        isos.append(e)


def test_next_iso_skips_names_a_run_lacks(wofs_pair):
    _, F = wofs_pair
    e = next_iso(F, [])
    assert e["var"] in F  # whichever it picks is a field the run has


def test_default_fields_exist_in_both_catalogs(reg, wofs_pair):
    """The names the viewer hardcodes as first choices (hardcoded-names.md sections 1-4)."""
    for run, F in (reg.get(), wofs_pair):
        for name in ("winterp", "uinterp", "vinterp", "th", "prs", "qv"):
            assert name in F or run.has(name), (run.model, name)
