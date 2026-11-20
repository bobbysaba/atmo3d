"""The radar map and PPI panel (Phase 6 step 3): a sweep drawn on the map's pixels
(atmo3d_radar.ppi), Fields on a run with no grid, the shared viewer on a radar run, on the
synthetic volumes of tests/synthetic_radar.py."""
import re
import time

import numpy as np
import pytest

import synthetic_radar as S
from atmo3d.core import render
from atmo3d.core.run import MissingAtTime

atmo3d_radar = pytest.importorskip("atmo3d_radar")
from atmo3d_radar import beam, ppi  # noqa: E402


@pytest.fixture(scope="module")
def rreg(tmp_path_factory):
    from atmo3d.registry import Registry
    d = tmp_path_factory.mktemp("radar")
    S.write(str(d))
    return Registry(str(d), 0.5, 1)


@pytest.fixture(scope="module")
def rf(rreg):
    return rreg.get()  # (PolarRun, Fields)


@pytest.fixture
def rv(rreg):
    from atmo3d.viewer import app as A
    run, F = rreg.get()
    v = A.Viewer(run, F, reg=rreg)
    v.main()
    yield v
    v.close()


def txt(h):
    return re.sub(r"\s+", " ", re.sub("<[^>]+>", " ", h or "")).strip()


def _gate_want(run, t, k, x, y):
    """The analytic reflectivity of the gate under x, y (nearest ray and gate by hand)."""
    sw = run.sweeps(t)
    az = sw.az[k][np.isfinite(sw.az[k])]
    paz = np.degrees(np.arctan2(x, y)) % 360.0
    a = az[np.argmin(np.abs((az - paz + 180.0) % 360.0 - 180.0))]
    _, sg = beam.gate_position(run.ranges, sw.elev[k])
    g = int(np.argmin(np.abs(sg - np.hypot(x, y))))
    return np.nan if g % 7 == 0 else S.refl(a, g, sw.elev[k])


# ------------------------------------------------------------------ the map's pixels
def test_raster_takes_the_nearest_ray_and_gate(rf):
    run, F = rf
    win = ppi.window(run, run.extent, 200)
    x, y, img = ppi.raster(run, run.read_sweep("reflectivity", 0, 1), 0, 1, win)
    assert img.shape == (len(y), len(x))
    rng = np.random.default_rng(1)
    for j, i in zip(rng.integers(0, len(y), 60), rng.integers(0, len(x), 60)):
        s = np.hypot(x[i], y[j])
        if not run.ranges[0] + 0.3 < s < run.ranges[-1] - 0.3:
            continue
        want = _gate_want(run, 0, 1, x[i], y[j])
        assert np.allclose(img[j, i], want, atol=1e-3, equal_nan=True)


def test_raster_is_empty_outside_the_gates(rf):
    run, _ = rf
    win = ppi.window(run, run.extent, 200)
    x, y, img = ppi.raster(run, run.read_sweep("velocity", 0, 0), 0, 0, win)
    X, Y = np.meshgrid(x, y)
    s = np.hypot(X, Y)
    assert np.isnan(img[s > run.ranges[-1] + 0.5]).all()  # (the corners)
    assert np.isnan(img[s < run.ranges[0] - 0.5]).all()  # (over the radar)
    assert np.isfinite(img[(s > run.ranges[0] + 0.5) & (s < run.ranges[-1] - 0.5)]).all()


def test_raster_leaves_a_missing_sector_empty(rf):
    run, _ = rf
    a = run.read_sweep("velocity", 0, 0).copy()
    sw = run.sweeps(0)
    win = ppi.window(run, run.extent, 200)
    # (drop rays 90-150 deg: the index sees the sweep's azimuths only, so fake a sweep)
    keep = ~((sw.az[0] > 90) & (sw.az[0] < 150))
    old = sw.az[0].copy()
    try:
        sw.az[0] = np.concatenate([old[keep], np.full((~keep).sum(), np.nan)])
        ppi._INDEX.clear()
        x, y, img = ppi.raster(run, a[np.r_[np.where(keep)[0], np.where(~keep)[0]]],
                               0, 0, win)
    finally:
        sw.az[0] = old
        ppi._INDEX.clear()
    X, Y = np.meshgrid(x, y)
    paz = np.degrees(np.arctan2(X, Y)) % 360.0
    s = np.hypot(X, Y)
    inner = (s > run.ranges[0] + 1) & (s < run.ranges[-1] - 1)
    assert np.isnan(img[inner & (paz > 105) & (paz < 135)]).all()
    assert np.isfinite(img[inner & (paz > 10) & (paz < 70)]).all()


def test_window_stride_and_clip(rf):
    run, _ = rf
    x0, x1, y0, y1, stride, n = ppi.window(run, (-100, 100, -5, 5), 900)
    e = run.extent[1]
    assert (x0, x1) == (-e, e) and (y0, y1) == (-5, 5)
    assert stride == 1 and n <= 900  # (at most half a gate per pixel: full res)
    assert ppi.window(run, run.extent, 20)[4] > 1  # (coarse: the title says 1/n res)


def test_gate_at(rf):
    run, _ = rf
    g = ppi.gate_at(run, 0, 2, 5.0, 8.0)
    assert g["az"] == 30.5 and g["gate"] == 15 and abs(g["range"] - 9.5) < 1e-9
    assert ppi.gate_at(run, 0, 2, 0.1, 0.1) is None  # (inside the first gate)
    assert ppi.gate_at(run, 1, 2, 5.0, 8.0) is None  # (no third sweep then)


# ------------------------------------------------------------------ Fields, compute_map
def test_fields_on_a_run_with_no_grid(rf):
    run, F = rf
    assert not run.grid and F.ctx["dx"] is None
    assert np.array_equal(F.plane("reflectivity", 0, "sweep", 1),
                          run.read_sweep("reflectivity", 0, 1), equal_nan=True)
    # only pointwise derived fields: no derivatives or columns
    assert all(d.pointwise and not d.column for d in F.defs.values() if d.derived)


def _spec(F, t, var, k, view=None, minus=None):
    run = F.run
    fill = dict(var=var, mode="sweep", level=float(k), style="image", nlev=12,
                cmap="viridis", rev=False, auto=True, vmin=0, vmax=1, minus=minus)
    return dict(t=t, view=view or run.extent, maxpix=200, fill=fill, fills=[], ov=[],
                vecs=[], storm=None, fstorm=None)


def test_compute_map_draws_the_sweep(rf):
    run, F = rf
    res = render.compute_map(F, _spec(F, 0, "reflectivity", 2))
    vals = render.decode_image(res["fill"]["image"])
    x, y, img = ppi.raster(run, run.read_sweep("reflectivity", 0, 2), 0, 2, res["win"])
    lo, hi = res["fill"]["image"]["lo"][0], res["fill"]["image"]["hi"][0]
    assert vals.shape == img.shape
    assert np.allclose(vals, np.clip(img, lo, hi), atol=(hi - lo) / 6e4, equal_nan=True)
    assert res["win"][4] >= 1


def test_compute_map_difference_on_the_pixels(rf):
    run, F = rf
    res = render.compute_map(F, _spec(F, 1, "velocity", 0, minus=dict(F=F, t=0, label="")))
    d = render.decode_image(res["fill"]["image"])
    # (the same analytic field at both times: zero where both have a gate)
    assert np.nanmax(np.abs(d)) < 1e-3 and np.isfinite(d).any()


def test_compute_map_sweep_missing_at_a_time(rf):
    _, F = rf
    with pytest.raises(MissingAtTime):
        render.compute_map(F, _spec(F, 1, "reflectivity", 2))


# ------------------------------------------------------------------ the viewer
def test_viewer_on_a_radar_run(rv):
    v = rv
    # (its sampler brings sections and 3D: tests/test_radar_sampler.py)
    assert list(v.mode.btns) == ["Cross-section", "3D region", "PPI"]
    assert v.workspace.visible and v.workspace.options == ["Map", "3D"]
    assert v.extent == tuple(v.run.extent)
    assert v.fill_mode.value == "sweep" and v.fill_lvl.end == 2
    assert v.fill_var.value == "reflectivity"
    assert "PPI" in txt(v.hint.object)
    spec = v._map_spec()
    v._apply_map(render.compute_map(v.F, spec), spec, v.gen["map"])
    assert "Reflectivity @ 0.5° sweep" in txt(v.map_title.object)


def test_ppi_panel_picks_the_sweep_and_follows_time(rv):
    v = rv
    v.mode.set("PPI")
    assert v._ppi_built and list(v.ppi_table.value["Sweep"]) == [0, 1, 2]
    assert np.allclose(v.ppi_table.value["Elevation (°)"],
                       np.round(sorted(f + o for f, o in zip(S.FIXED, S.OFFSET)), 2))
    v.ppi_table.selection = [2]
    assert v.fill_lvl.value == 2
    v.fill_lvl.value = 1
    assert v.ppi_table.selection == [1]
    v.tslider.value = 1
    assert len(v.ppi_table.value) == 2 and "2 sweeps here, 3 in the first" in \
        txt(v.ppi_head.object)


def test_ppi_click_shows_the_gate(rv):
    v = rv
    v.mode.set("PPI")
    v.fill_lvl.value = 2
    v._on_tap(type("E", (), {"x": 5.0, "y": 8.0, "modifiers": {}})())
    t0 = time.time()
    while "Gate 15" not in txt(v.ppi_gate.object) and time.time() - t0 < 30:
        time.sleep(0.02)
    h = txt(v.ppi_gate.object)
    want = S.refl(30.5, 15, v.run.sweeps(0).elev[2])
    got = float(re.search(r"Reflectivity ([-\d.]+) dBZ", h).group(1))
    assert "Azimuth 30.5°" in h and abs(got - want) < 0.01
    assert "Lat, lon" in h


def test_grid_only_tools_stay_off_a_radar_run(rf):
    # (CM1 and WoFS keep theirs: test_capabilities.test_panels_and_rail_per_data_type)
    from atmo3d.viewer import panels
    run, _ = rf
    built, rail = panels.for_run(run)
    assert [t.key for t in rail] == ["Cross-section", "3D region", "PPI"]
    assert "Series" not in [t.key for t in built] and \
        "Distribution" not in [t.key for t in built]
    assert not run.can("grid") and run.can("sampled") and run.can("native_polar")
