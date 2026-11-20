"""Checks on your own radar folder (CfRadial volumes, one file per time): it opens, its sweep
tables make sense, the sampler gives back the beam model's heights on its real geometry,
and each view (PPI, constant height, column max, section, column, 3D, a small regrid)
comes out.  Reads only (never writes into the folder); the regrid's cache files go to
the test session's own cache folder.  Reads a few fields at the first time (a minute or
so on 4 CPUs).

  ATMO3D_RADAR_ROOT=/path/to/folder pytest -m real tests/radar/test_real_radar.py
"""
import os

import numpy as np
import pytest

ROOT = os.environ.get("ATMO3D_RADAR_ROOT")
pytestmark = [pytest.mark.real,
              pytest.mark.skipif(not ROOT, reason="set ATMO3D_RADAR_ROOT to a radar folder")]


@pytest.fixture(scope="module")
def rf():
    from atmo3d.registry import Registry
    reg = Registry(os.path.abspath(os.path.expanduser(ROOT)), 4, 1)
    run, F = reg.get()
    yield run, F
    run.clear_cache()


def test_opens_and_its_sweep_tables(rf):
    run, F = rf
    assert run.model == "radar" and not run.grid and run.sampled
    assert len(run.times) >= 1 and (np.diff(run.times) > 0).all()
    assert run.geo is not None and np.isfinite(run.site).all()
    for t in range(len(run.times)):
        sw = run.sweeps(t)
        assert len(sw) >= 1 and (np.diff(sw.elev) >= 0).all(), t
        assert all(np.isfinite(sw.az[k]).sum() > 10 for k in range(len(sw))), t
    assert "reflectivity" in F and F.role("refl") == "reflectivity"


def test_sampler_gives_back_the_beam_heights(rf):
    # (docs-dev/radar-spike.md section 2: within 9 m on these files)
    from atmo3d_radar import beam, sampler
    run, _ = rf
    sw = run.sweeps(0)
    rng = np.random.default_rng(0)
    n = 50_000
    az = rng.uniform(0, 360, n)
    el = rng.uniform(sw.elev[0] + 0.05, sw.elev[-1] - 0.05, n)
    r = rng.uniform(run.ranges[0] + 1, min(run.ranges[-1] - 1, 150.0), n)
    h, s = beam.gate_position(r, el)
    x, y = s * np.sin(np.radians(az)), s * np.cos(np.radians(az))
    got = sampler.sample(run, run.volume("beam_height", 0), 0, x, y, h)
    ok = np.isfinite(got)
    assert ok.mean() > 0.95  # (the rest: sectors a sweep lacks)
    assert np.max(np.abs(got[ok] - h[ok])) < 0.010


def _storm(run, F):
    """(x, y) km of the strongest echo in the lowest sweep at the first time."""
    from atmo3d_radar import ppi
    win = ppi.window(run, (-150, 150, -150, 150), 300)
    x, y, img = run.map_plane(F, "reflectivity", 0, "sweep", 0, win)
    j, i = np.unravel_index(np.nanargmax(img), img.shape)
    return float(x[i]), float(y[j])


def test_the_views(rf):
    from atmo3d.core import render
    from atmo3d_radar import panel, ppi, scene
    run, F = rf
    xc, yc = _storm(run, F)
    view = (xc - 40, xc + 40, yc - 40, yc + 40)
    win = ppi.window(run, view, 400)
    for mode, level in (("sweep", 0), ("height", 2.0), ("colmax", 0)):
        img = run.map_plane(F, "reflectivity", 0, mode, level, win)[2]
        assert np.isfinite(img).mean() > 0.05, mode
    s, x, y, _ = render.section_coords(run, (xc - 30, yc), (xc + 30, yc))
    sec = render.section_field(F, "reflectivity", 0, x, y, np.linspace(0, 15, 100))
    assert np.isfinite(sec).any() and np.nanmax(sec) > 30
    line, pts = panel.column(run, F, 0, xc, yc, "reflectivity")
    assert np.isfinite(line["v"]).any() and len(pts["z"]) >= 1
    m = scene.isosurface(run, 0, run.volume("reflectivity", 0), view, 30.0,
                         scene.auto_stride(run, 0, view), 0.75, 15.0)
    assert m is not None and len(m["faces"]) > 100


def test_a_small_regrid(rf):
    from atmo3d_radar import regrid, sampler
    run, F = rf
    s = regrid.Settings("linear", 1.0, 0.5, 40.0, 0.0)
    g = regrid.RegriddedRun(regrid.path_of(run.path, s), 4, 1)
    a = g.volume("reflectivity", 0)
    assert a.shape == (g.nk, 81, 81) and np.isfinite(a).any()
    X, Y = np.meshgrid(g.xh, g.yh)
    want = sampler.sample(run, run.volume("reflectivity", 0), 0, X, Y, g.z[4], "linear")
    want[np.hypot(X, Y) > 40.0] = np.nan
    assert np.array_equal(a[4], want, equal_nan=True)
    assert os.path.isfile(g.cache_path("reflectivity", 0))
    g.clear_cache()
