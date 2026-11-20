"""The worked example data type (packages/example): it passes the contract check, and
reads its synthetic run (atmo3d_example.synthetic) with the answers known in closed form.

It runs on every core change (CI), so a core change that breaks the example, the
pattern new data types are copied from, fails here.  The example is not installed with
atmo3d (it is no part of the app): these tests register it themselves, as its entry
point would, and take it out again afterwards."""
import os
import tomllib

import numpy as np
import pytest

from atmo3d.core import catalog, models
from atmo3d.testing import check_datatype

HERE = os.path.dirname(os.path.abspath(__file__))
PACKAGE = os.path.join(os.path.dirname(HERE), "packages", "example")


@pytest.fixture(scope="module")
def registered():
    import atmo3d_example
    models.MODELS.get("cm1")  # (load the installed data types first, so they stay)
    before = dict.get(models.MODELS, "example")
    atmo3d_example.register()
    yield
    if before is None:
        dict.pop(models.MODELS, "example", None)
        catalog.CATALOGS.pop("example", None)


@pytest.fixture(scope="module")
def folder(registered, tmp_path_factory):
    from atmo3d_example import synthetic
    d = str(tmp_path_factory.mktemp("example") / "run")
    synthetic.write(d)
    return d


@pytest.fixture(scope="module")
def run(folder):
    from atmo3d.core.fields import Fields
    r = models.open_run(folder, "example", cache_gb=0.5, workers=1)
    return r, Fields(r)


def test_contract(folder):
    rep = check_datatype("example", folder)
    assert any(n.startswith("map of") for n in rep.notes)
    assert any(n.startswith("cross-section of") for n in rep.notes)


def test_entry_point_names_register():
    with open(os.path.join(PACKAGE, "pyproject.toml"), "rb") as f:
        meta = tomllib.load(f)
    eps = meta["project"]["entry-points"][models.GROUP]
    assert eps == {"example": "atmo3d_example:register"}


def test_times_across_files(run):
    from atmo3d_example import synthetic as S
    r, _ = run
    assert r.times.tolist() == [0.0, 300.0, 600.0, 900.0]
    assert [os.path.basename(f) for f in r.files] == [n for n in S.FILES for _ in (0, 1)]
    assert r.time_label(3) == "2026-05-20 21:15 UTC"


def test_grid_in_km(run):
    from atmo3d_example import synthetic as S
    r, _ = run
    x, y, z, zf = S.coords()
    assert np.allclose(r.xh, x) and np.allclose(r.yh, y)
    assert np.allclose(r.z, z) and np.allclose(r.zf, zf)
    assert (r.ni, r.nj, r.nk) == (S.NX, S.NY, S.NZ) and r.dx == pytest.approx(1000.0)


@pytest.mark.parametrize("t", [0, 1, 3])
def test_reads_the_right_time(run, t):
    """Each time of a file of two: the bubble has moved (w, theta), and the second time
    in a file is not its first."""
    from atmo3d_example import synthetic as S
    r, _ = run
    want = S.fields(r.times[t])
    th = r.volume("theta", t)
    assert th.shape == (S.NZ, S.NY, S.NX) and th.dtype == np.float32
    assert np.allclose(th, want["theta"], atol=1e-4)
    # w: averaged from the staggered levels onto the scalar ones
    wz = 0.5 * (want["w"][:-1] + want["w"][1:])
    assert np.allclose(r.volume("w", t), wz, atol=1e-4)
    assert r.vars["w"].stag == "z" and r.vars["theta"].stag is None


def test_reader_processes(folder):
    """Reads in the reader processes (workers > 1) open the file at the right time
    (TimeSource pickles; each time of a file is kept open under its own key)."""
    from atmo3d_example import synthetic as S
    r = models.open_run(folder, "example", cache_gb=0.5, workers=2)
    assert r.load_volumes(["theta", "qv"], 3) and r.load_volumes(["theta"], 2)
    assert np.allclose(r.volume("theta", 3), S.fields(900.0)["theta"], atol=1e-4)
    assert np.allclose(r.volume("theta", 2), S.fields(600.0)["theta"], atol=1e-4)
    assert np.allclose(r.volume("qv", 3), S.fields(900.0)["qv"] * 1e-3, rtol=1e-6)


def test_units_converted_and_fill_is_nan(run):
    from atmo3d_example import synthetic as S
    r, _ = run
    assert r.vars["qv"].units == "kg/kg"
    assert np.allclose(r.volume("qv", 0), S.fields(0)["qv"] * 1e-3, rtol=1e-6)
    dbz, raw = r.volume("dbz", 2), S.fields(600.0)["dbz"]
    assert np.array_equal(np.isnan(dbz), raw == S.FILL)
    assert np.isnan(dbz).any() and np.allclose(dbz[raw != S.FILL], raw[raw != S.FILL])


def test_field_in_some_files_only(run):
    r, _ = run
    assert r.var_times["tke"] == frozenset({2, 3}) and "theta" not in r.var_times
    assert not r.in_file("tke", 0) and r.in_file("tke", 2)


def test_2d_field(run):
    from atmo3d_example import synthetic as S
    r, _ = run
    assert r.vars["rain"].ndim == 2
    assert np.allclose(r.read_level("rain", 1), S.fields(300.0)["rain"], atol=1e-5)


def test_roles_give_derived_fields_and_capabilities(run):
    r, F = run
    assert r.role("refl") == "dbz" and r.role("w") == "w"
    assert r.can("soundings") and r.can("tracking")
    # vertical vorticity from u and v (here 0: u depends on z only, v too)
    assert "zvort" in F.defs and np.allclose(F.volume("zvort", 0), 0.0, atol=1e-6)


def test_demo(registered, tmp_path):
    m = models.MODELS["example"]
    path = m.make_demo(str(tmp_path))
    assert m.is_demo(path) and models.detect(path) is m
    assert m.summary(path) == "2 files" and m.count(path) == 4
