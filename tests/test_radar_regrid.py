"""The optional radar regrid (Phase 6 step 5): settings named in the regridded run's path,
the regridded run (a grid Run every grid feature works on), its cache files, the
Native / Regridded switch and the dialog that confirms the settings, the "regridded:"
label, and the settings in exports; on the synthetic volumes of tests/synthetic_radar.py
(atmo3d_radar.regrid, regrid_ui)."""
import os
import pickle
import re
import time

import netCDF4
import numpy as np
import pytest

import synthetic_radar as S
from atmo3d.core import models, render

atmo3d_radar = pytest.importorskip("atmo3d_radar")
from atmo3d_radar import regrid, regrid_ui, sampler  # noqa: E402

# (the synthetic volumes top out under 1 km: thin layers, a small grid)
SET = regrid.Settings("linear", 0.5, 0.1, 20.0, 0.0)


@pytest.fixture(scope="module")
def folder(tmp_path_factory):
    d = tmp_path_factory.mktemp("radar")
    S.write(str(d))
    return str(d)


@pytest.fixture(scope="module")
def rreg(folder):
    from atmo3d.registry import Registry
    return Registry(folder, 0.5, 1)


@pytest.fixture(scope="module")
def gf(rreg, folder):
    return rreg.get(regrid.path_of(folder, SET))  # (RegriddedRun, Fields)


def txt(h):
    return re.sub(r"\s+", " ", re.sub("<[^>]+>", " ", h or "")).strip()


def _viewer(rreg, path):
    from atmo3d.viewer import app as A
    run, F = rreg.get(path)
    v = A.Viewer(run, F, reg=rreg)
    v.main()
    return v


# ------------------------------------------------------------------ settings and paths
def test_settings_in_the_path(folder):
    p = regrid.path_of(folder, SET)
    assert os.path.basename(p) == "regrid_linear_dx0.5_dz0.1_r20_gap0"
    assert regrid.parse(p) == (os.path.abspath(folder), SET)
    assert regrid.parse(folder) is None
    assert regrid.parse(os.path.join(folder, "regrid_cubic_dx1_dz1_r10_gap0")) is None
    assert regrid.parse(os.path.join(folder, "regrid_linear_dx0_dz1_r10_gap0")) is None
    with pytest.raises(ValueError):
        regrid.Settings("linear", 0.5, 0.5, 2000.0, 0.0)
    assert SET.label == "linear, 0.5 km × 0.1 km"
    assert regrid.Settings().sizes(20.0) == (601, 40, pytest.approx(57.8, abs=0.1))


def test_settings_from_and_to_config(monkeypatch):
    from atmo3d import config
    assert regrid.from_config() == regrid.Settings()
    vals = regrid.to_config(SET)
    for k, v in vals.items():
        monkeypatch.setitem(config._state["cli"], k, (v, "test"))
    assert regrid.from_config() == SET


def test_the_folder_and_its_parts(folder):
    p = regrid.path_of(folder, SET)
    native = os.path.abspath(folder)
    assert models.parts(folder, "radar") == [native,
                                            regrid.path_of(folder, regrid.Settings())]
    assert models.siblings(p) == [native, p]  # (its own settings, whatever config says)
    assert models.exists(p) and models.root_of(p) == native
    assert models.part_label(p) == "Regridded (linear, 0.5 km × 0.1 km)"
    assert models.part_label(folder) == "Native sweeps"
    assert models.count(p, "radar") == 2


# ------------------------------------------------------------------ the regridded run
def test_regridded_run_is_a_grid(gf):
    run, F = gf
    assert type(run).__name__ == "RegriddedRun" and run.grid and run.model == "radar"
    assert np.allclose(run.xh, np.arange(-40, 41) * 0.5) and np.array_equal(run.xh, run.yh)
    assert np.allclose(run.zf, np.arange(run.nk + 1) * 0.1)
    assert np.allclose(run.z, run.zf[:-1] + 0.05)
    assert run.dx == 500.0 and not run.terrain and run.geo is not None
    assert "beam_height" not in run.vars and "reflectivity" in run.vars
    assert run.view_note() == "regridded: linear, 0.5 km × 0.1 km"
    # D2: the wind's derived fields (vertical vorticity too) on the grid
    assert {"zvort", "hdiv", "xvort", "hvort"} <= set(F.defs)


def test_regridded_values_are_the_samplers(gf):
    run, F = gf
    a = run.volume("reflectivity", 0)
    X, Y = np.meshgrid(run.xh, run.yh)
    nat = run.native
    want = sampler.sample(nat, nat.volume("reflectivity", 0), 0, X, Y, run.z[3])
    want[np.hypot(X, Y) > SET.range] = np.nan
    assert np.array_equal(a[3], want, equal_nan=True) and np.isfinite(a[3]).any()
    # u = 10, v = -5 everywhere: no vorticity, no divergence where the winds are
    z = F.plane("zvort", 0, "height", 0.3)
    d = F.plane("hdiv", 0, "height", 0.3)
    assert np.isfinite(z).any() and np.nanmax(np.abs(z)) < 1e-6
    assert np.nanmax(np.abs(d)) < 1e-3


def test_cache_files(gf, monkeypatch):
    run, _ = gf
    fn = run.cache_path("velocity", 0)
    assert SET.name in fn and os.path.basename(fn).startswith("velocity.t000.")
    a = run.regridded("velocity", 0)
    assert os.path.isfile(fn) and np.array_equal(np.load(fn), a, equal_nan=True)
    os.remove(fn)
    monkeypatch.setattr(regrid, "DISK_GB", 0.0)  # (a full cache: in memory only)
    assert np.array_equal(run.regridded("velocity", 0), a, equal_nan=True)
    assert not os.path.exists(fn)


def test_source_regrids_in_a_reader_process(gf):
    run, _ = gf
    src = pickle.loads(pickle.dumps(run.source(1)))  # (what a time series sends)
    assert src.run is None
    with src.open() as d:
        got = d["velocity"][0]
    assert np.array_equal(got, run.volume("velocity", 1), equal_nan=True)


def test_isosurface_through_empty_points(gf):
    from atmo3d.core import volume3d
    run, F = gf
    vol = run.volume("reflectivity", 0)
    keep = vol.copy()
    m = volume3d.isosurface(run, vol, run.extent, 25.0, 1, 0.0, 0.9)
    assert m is not None and len(m["faces"]) > 10
    assert np.array_equal(vol, keep, equal_nan=True)  # (the cached volume untouched)


def test_export_names_the_regrid(gf, tmp_path):
    from atmo3d.core import export as ex
    run, F = gf
    p = ex.plan(run, F, ["reflectivity"], [0], heights=[0.3])
    out = str(tmp_path / "r.nc")
    ex.write(run, F, out, p)
    with netCDF4.Dataset(out) as d:
        assert d.atmo3d_regrid == "regridded: linear, 0.5 km × 0.1 km"
        assert "out to 20 km" in d.atmo3d_regrid_settings
        assert SET.name in d.atmo3d_run


# ------------------------------------------------------------------ the viewer
def test_viewer_on_the_regridded_run(rreg, folder):
    v = _viewer(rreg, regrid.path_of(folder, SET))
    try:
        assert {"Series", "Distribution", "Cross-section", "3D region"} <= set(v.mode.btns)
        assert "PPI" not in v.mode.btns and v.workspace.options == ["Map", "3D", "Figure"]
        assert list(v.part_sel.options) == ["Native sweeps",
                                            "Regridded (linear, 0.5 km × 0.1 km)"]
        v.fill_lvl.value = 0.3
        spec = v._map_spec()
        v._apply_map(render.compute_map(v.F, spec), spec, v.gen["map"])
        assert "regridded: linear, 0.5 km × 0.1 km" in txt(v.map_title.object)
        v.mode.set("Cross-section")
        v.xs_pts = [(-15.0, -5.0), (15.0, 8.0)]
        v.gen["xs"] += 1
        v._xs_job(v.xs_spec(), v.gen["xs"])
        t0 = time.time()
        while "long" not in txt(v.xs_status.object) and time.time() - t0 < 30:
            time.sleep(0.02)
        assert "regridded: linear" in txt(v.xs_status.object)
        s = v.session_state()
        assert s["run"] == regrid.path_of(folder, SET)  # (the settings travel with it)
    finally:
        v.close()


def test_the_switch_asks_before_regridding(rreg, folder, monkeypatch):
    from atmo3d import config
    v = _viewer(rreg, folder)
    try:
        assert list(v.part_sel.options) == ["Native sweeps",
                                            "Regridded (linear, 0.5 km × 0.5 km)"]
        opened, saved = {}, {}
        base = next(c for c in type(v).__mro__[1:] if "_open_with_view" in c.__dict__
                    and c is not regrid_ui.RegridSwitch)
        monkeypatch.setattr(base, "_open_with_view",
                            lambda self, p, s: opened.update(p=p, s=s))
        monkeypatch.setattr(config, "save", lambda vals: saved.update(vals))
        v.part_sel.value = list(v.part_sel.options.values())[1]
        # not yet: the dialog first, the switch back on the native run
        assert v.part_sel.value == os.path.abspath(folder) and not opened
        assert "601 × 601 × 2 points" in txt(v.rg_info.object)
        v.rg_range.value = 500.0
        v._rg_describe()
        assert v.rg_go.disabled is False
        v.rg_range.value = 5000.0  # (out of range: no Regrid)
        v._rg_describe()
        assert v.rg_go.disabled and "range" in txt(v.rg_info.object)
        v.rg_range.value, v.rg_dz.value = 20.0, 0.1
        v._rg_confirm()
        assert opened["p"] == regrid.path_of(folder, SET)
        assert saved == regrid.to_config(SET)
        # the map's sweep becomes a height (no sweeps on the grid)
        assert opened["s"]["fill"]["mode"] == "height"
    finally:
        v.close()


def test_level_modes_cross_over():
    s = dict(fill=dict(mode="sweep", level=3.0), fills=[dict(mode="level", level=4.0)],
             contours=[dict(mode="colmax", level=0.0), dict(mode="height", level=2.0)])
    o = regrid_ui.for_other(s)
    assert (o["fill"]["mode"], o["fill"]["level"]) == ("height", 1.0)
    assert o["fills"][0]["mode"] == "height"
    assert [c["mode"] for c in o["contours"]] == ["colmax", "height"]
    assert o["contours"][1]["level"] == 2.0 and s["fill"]["mode"] == "sweep"
