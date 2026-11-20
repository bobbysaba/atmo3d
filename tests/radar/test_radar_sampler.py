"""The radar sampler and the views built on it (Phase 6 step 4): values at any x, y, z
(atmo3d_radar.sampler), constant-height and column-max maps, cross-sections, the column
under a click, and 3D isosurfaces in index space (atmo3d_radar.scene), on the synthetic
volumes of tests/synthetic_radar.py, whose reflectivity is linear in azimuth, gate and
elevation: the sampler, linear in each, must give it back exactly between the gates."""
import re
import time

import numpy as np
import pytest

import synthetic_radar as S
from atmo3d.core import render, volume3d

atmo3d_radar = pytest.importorskip("atmo3d_radar")
from atmo3d_radar import beam, panel, ppi, sampler, scene  # noqa: E402


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


def _points(run, t, n, seed=0, margin=0.02):
    """n random points inside the sweeps of time t (azimuth, elevation, range), away from
    north (where ray azimuths wrap) and from the missing gates (multiples of 7) and
    their neighbours: x, y, z and their (az, el, g)."""
    sw = run.sweeps(t)
    rng = np.random.default_rng(seed)
    az = rng.uniform(5.0, 350.0, 4 * n)
    el = rng.uniform(sw.elev[0] + margin, sw.elev[-1] - margin, 4 * n)
    g = rng.uniform(1.0, S.NG - 2.0, 4 * n)
    ok = (np.floor(g) % 7 != 0) & (np.ceil(g) % 7 != 0)
    az, el, g = az[ok][:n], el[ok][:n], g[ok][:n]
    h, s = beam.gate_position(S.R0 + g * S.DR, el)
    x, y = s * np.sin(np.radians(az)), s * np.cos(np.radians(az))
    return x, y, h, (az, el, g)


# ------------------------------------------------------------------ the sampler
def test_sampler_gives_back_a_linear_field(rf):
    run, _ = rf
    x, y, z, (az, el, g) = _points(run, 0, 3000)
    got = sampler.sample(run, run.volume("reflectivity", 0), 0, x, y, z)
    assert np.allclose(got, S.refl(az, g, el), atol=2e-3)


def test_sampler_heights(rf):
    run, _ = rf
    x, y, z, _ = _points(run, 0, 2000, seed=1)
    got = sampler.sample(run, run.volume("beam_height", 0), 0, x, y, z)
    assert np.nanmax(np.abs(got - z)) < 1e-3  # (km: under a metre)


def test_sampler_beyond_the_sweeps(rf):
    run, _ = rf
    sw = run.sweeps(0)
    vol = run.volume("velocity", 0)
    r = 10.0
    half = beam.BEAMWIDTH / 2
    for e, want in ((sw.elev[-1] + 0.8 * half, True), (sw.elev[-1] + 1.5 * half, False),
                    (sw.elev[0] - 0.8 * half, True), (sw.elev[0] - 1.5 * half, False)):
        h, s = beam.gate_position(r, e)
        v = sampler.sample(run, vol, 0, s * np.sin(1.0), s * np.cos(1.0), h)
        assert np.isfinite(v) == want, e


def test_sampler_nearest_and_max_gap(rf):
    run, _ = rf
    vol = run.volume("reflectivity", 0)
    sw = run.sweeps(0)
    # nearest: on sweep 1's beam, near gate 12 and ray 40.5 deg, the gate's value
    h, s = beam.gate_position(S.R0 + 12.2 * S.DR, sw.elev[1])
    a = np.radians(41.0)
    v = sampler.sample(run, vol, 0, s * np.sin(a), s * np.cos(a), h, method="nearest")
    assert np.isclose(v, S.refl(40.5, 12, sw.elev[1]), atol=1e-4)
    # max gap: midway between two sweeps, NaN once the gap there is over it
    e = 0.5 * (sw.elev[0] + sw.elev[1])
    h, s = beam.gate_position(15.0, e)
    gap = 15.0 * np.radians(sw.elev[1] - sw.elev[0])
    assert np.isfinite(sampler.sample(run, vol, 0, s * np.sin(a), s * np.cos(a), h))
    assert np.isfinite(sampler.sample(run, vol, 0, s * np.sin(a), s * np.cos(a), h,
                                      max_gap_km=1.1 * gap))
    assert np.isnan(sampler.sample(run, vol, 0, s * np.sin(a), s * np.cos(a), h,
                                   max_gap_km=0.9 * gap))


def test_sampler_settings(rf, monkeypatch):
    from atmo3d import config
    run, _ = rf
    assert run.sampling() == ("linear", 0.0)
    monkeypatch.setitem(config._state["cli"], "radar_max_gap_km", (0.5, "test"))
    monkeypatch.setitem(config._state["cli"], "radar_sampling", ("nearest", "test"))
    assert run.sampling() == ("nearest", 0.5)
    assert "nearest" in run.view_note() and "0.5 km" in run.view_note()


# ------------------------------------------------------------------ maps
def _spec(run, t, var, mode, level):
    fill = dict(var=var, mode=mode, level=float(level), style="image", nlev=12,
                cmap="viridis", rev=False, auto=True, vmin=0, vmax=1, minus=None)
    return dict(t=t, view=run.extent, maxpix=120, fill=fill, fills=[], ov=[], vecs=[],
                storm=None, fstorm=None)


def _image(res):
    f = res["fill"]["image"]
    vals = render.decode_image(f)
    return vals, (f["hi"][0] - f["lo"][0]) / 6e4


def test_constant_height_map(rf):
    run, F = rf
    res = render.compute_map(F, _spec(run, 0, "reflectivity", "height", 0.3))
    vals, tol = _image(res)
    x, y = ppi.pixels(res["win"])
    X, Y = np.meshgrid(x, y)
    want = sampler.sample(run, run.volume("reflectivity", 0), 0, X, Y, 0.3)
    lo, hi = res["fill"]["image"]["lo"][0], res["fill"]["image"]["hi"][0]
    assert np.isfinite(want).any()
    assert np.allclose(vals, np.clip(want, lo, hi), atol=tol, equal_nan=True)


def test_column_max_map(rf):
    run, F = rf
    res = render.compute_map(F, _spec(run, 0, "reflectivity", "colmax", 0))
    vals, tol = _image(res)
    vol = run.volume("reflectivity", 0)
    stack = np.stack([ppi.raster(run, vol[k], 0, k, res["win"])[2] for k in range(3)])
    want = np.where(np.isfinite(stack).any(axis=0),
                    np.nanmax(np.where(np.isfinite(stack), stack, -np.inf), axis=0), np.nan)
    lo, hi = res["fill"]["image"]["lo"][0], res["fill"]["image"]["hi"][0]
    assert np.allclose(vals, np.clip(want, lo, hi), atol=tol, equal_nan=True)


def test_map_vectors_at_a_height(rf):
    run, F = rf
    spec = _spec(run, 0, "reflectivity", "sweep", 0)
    spec["vecs"] = [dict(on=True, q="wind", level=0.3, frame="ground", density=10,
                         ref=20.0, style="arrows")]
    spec["storm"] = None
    arrows = render.compute_map(F, spec)["vecs"][0]["vec"]
    assert len(arrows["x0"]) > 10
    # u = 10, v = -5 everywhere they are: every arrow points east-south-east
    ang = np.arctan2(np.subtract(arrows["y1"], arrows["y0"]),
                     np.subtract(arrows["x1"], arrows["x0"]))
    assert np.allclose(ang, np.arctan2(-5.0, 10.0), atol=1e-3)


def test_map_title_levels(rf):
    run, _ = rf
    assert run.level_text(0, "height", 2.0) == " @ 2 km"
    assert "column max" in run.level_text(0, "colmax", 0)
    assert run.level_text(0, "sweep", 0) == f" @ {run.sweeps(0).label(0)} sweep"


# ------------------------------------------------------------------ sections
def test_section_is_the_sampler_along_the_line(rf):
    run, F = rf
    A, B = (-15.0, -5.0), (15.0, 8.0)
    s, x, y, (ex, ey) = render.section_coords(run, A, B)
    assert np.isclose(s[-1], np.hypot(30.0, 13.0)) and np.allclose(x[[0, -1]], [-15, 15])
    assert np.isclose(np.hypot(ex, ey), 1.0)
    zq = np.linspace(0.0, 0.8, 40)
    got = render.section_field(F, "reflectivity", 0, x, y, zq)
    want = sampler.sample(run, run.volume("reflectivity", 0), 0, x[None], y[None],
                          zq[:, None])
    assert got.shape == (zq.size, s.size)
    assert np.array_equal(got, want, equal_nan=True) and np.isfinite(got).any()
    # a difference of two times of the same run: on the same points
    d = render.minus_section(F, F, "velocity", 1, A, B, s, zq)
    assert d.shape == got.shape


def test_section_in_the_viewer(rv):
    v = rv
    v.mode.set("Cross-section")
    v.xs_pts = [(-15.0, -5.0), (15.0, 8.0)]
    v.gen["xs"] += 1
    v._xs_job(v.xs_spec(), v.gen["xs"])
    t0 = time.time()
    while "long" not in txt(v.xs_status.object) and time.time() - t0 < 30:
        time.sleep(0.02)
    h = txt(v.xs_status.object)
    assert "32.7 km long" in h and "native, linear between sweeps" in h
    assert v.xs_fig.yaxis[0].axis_label == "Height (km above the radar)"


# ------------------------------------------------------------------ the column
def test_column_under_a_click(rf):
    run, F = rf
    line, pts = panel.column(run, F, 0, 5.0, 8.0, "reflectivity")
    want = sampler.sample(run, run.volume("reflectivity", 0), 0, np.full(line["z"].shape, 5.0),
                          np.full(line["z"].shape, 8.0), line["z"])
    assert np.array_equal(line["v"], want, equal_nan=True)
    sw = run.sweeps(0)
    assert len(pts["z"]) == 3 and pts["sweep"] == [sw.label(k) for k in range(3)]
    g = ppi.gate_at(run, 0, 2, 5.0, 8.0)
    assert np.isclose(pts["z"][2], g["height"])
    assert np.isclose(pts["v"][2], S.refl(g["az"], g["gate"], sw.elev[2]), atol=0.01)


def test_ppi_click_draws_the_column(rv):
    v = rv
    v.mode.set("PPI")
    v.fill_mode.value = "height"
    v.fill_lvl.value = 0.3
    assert v.ppi_table.selection == []  # (no sweep on the map)
    v._ppi_click(5.0, 8.0)
    t0 = time.time()
    while not v.ppi_col.visible and time.time() - t0 < 30:
        time.sleep(0.02)
    assert v.ppi_col.visible and len(v.ppi_pts_src.data["z"]) == 3
    assert "pick a sweep" in txt(v.ppi_gate.object)
    v.ppi_table.selection = [1]  # (back to sweeps)
    assert v.fill_mode.value == "sweep" and v.fill_lvl.value == 1


# ------------------------------------------------------------------ 3D
def test_isosurface_vertices_lie_on_the_value(rf):
    run, _ = rf
    vol = run.volume("reflectivity", 0)
    box = (-18.0, 18.0, -18.0, 18.0)
    m = scene.isosurface(run, 0, vol, box, 25.0, 1, 0.0, 15.0)
    assert m is not None and len(m["faces"]) > 50
    x, y, z = m["x"], m["y"], m["z"]
    assert (x >= box[0]).all() and (x <= box[1]).all() and (z <= 15.0).all()
    assert m["faces"].max() < len(x)
    # (the surface is linear in sweep, azimuth and gate, as the sampler is): away from
    # north and from the missing gates (which the surface wraps: missing counts as
    # below), the volume at a vertex is the value
    az, _, r = beam.polar_of(x, y, z)
    g = (r - S.R0) / S.DR
    hole = np.abs(g - 7 * np.round(g / 7)) < 1.05
    v = sampler.sample(run, vol, 0, x, y, z)
    ok = (az > 12) & (az < 348) & np.isfinite(v) & ~hole
    assert ok.sum() > 20 and np.allclose(v[ok], 25.0, atol=0.05)


def test_isosurface_in_a_sector(rf):
    run, _ = rf
    vol = run.volume("reflectivity", 0)
    box = (5.0, 18.0, 5.0, 18.0)  # (north-east: not around the radar)
    full, a0, width = scene._sector(box)
    assert not full and 15 < a0 < 20 and 50 < width < 60
    m = scene.isosurface(run, 0, vol, box, 25.0, 1, 0.0, 15.0)
    assert m is not None
    assert (m["x"] >= 5.0).all() and (m["y"] >= 5.0).all()


def test_build_scene_on_radar(rf):
    run, F = rf
    spec = dict(t=0, box=(-18.0, 18.0, -18.0, 18.0), ztop=15.0, exag=2.0, smooth=0.0,
                res=0, isos=[dict(var="reflectivity", val=25.0, color="#f00", op=1.0),
                             dict(var="velocity", val=500.0, color="#0f0", op=1.0)],
                storm=None, fstorm=(None, ""), vecs=[],
                stream=dict(on=False),
                ground=dict(on=True, var="reflectivity", z=0.2, cmap="Field default",
                            rev=False, range="data", lo=0.0, hi=0.0))
    sc = volume3d.build_scene(run, F, spec)
    assert len(sc["meshes"]) == 1 and sc["stream"] is None and sc["vecs"] == []
    assert any("Doppler velocity = 500" in n or "= 500" in n for n in sc["notes"])
    g = sc["ground"]
    assert g["a"].shape == (len(g["y"]), len(g["x"])) and np.isfinite(g["a"]).any()
    assert "above the radar" in g["title"]


def test_3d_in_the_viewer(rv):
    v = rv
    v.workspace.value = "3D"
    v._set_box((-18.0, 18.0, -18.0, 18.0))
    v.isos[0]["on"].value = True
    v.isos[0]["var"].value = "reflectivity"
    v.isos[0]["val"].value = 25.0
    for d in v.isos[1:]:
        d["on"].value = False
    v.request_3d()
    t0 = time.time()
    while "triangles" not in txt(v.v3_status.object) and time.time() - t0 < 60:
        time.sleep(0.05)
    h = txt(v.v3_status.object)
    assert "triangles" in h and "heights above the radar" in h
    assert "auto res" in txt(v.v3_region.object)
