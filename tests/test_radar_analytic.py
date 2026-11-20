"""The radar sampler, regrid and 3D against answers worked out by hand (Phase 6 step 6),
on the synthetic volumes of tests/synthetic_radar.py: reflectivity
refl(a, g, e) = 10 + 0.5 g + 0.01 a + e is linear in azimuth, gate and elevation, with
every 7th gate missing; rays every 10 degrees at 0.5, 10.5, ... 350.5; the second volume
lacks its top sweep.  The edge cases: across north, the missing-data rule (valid
neighbours need half the weight), a sector a sweep lacks, sweeps with different ray
counts, a volume cut short, and the regrid's grid points."""
import numpy as np
import pytest

import synthetic_radar as S

atmo3d_radar = pytest.importorskip("atmo3d_radar")
from atmo3d_radar import beam, ppi, regrid, sampler, scene  # noqa: E402


@pytest.fixture(scope="module")
def folder(tmp_path_factory):
    d = tmp_path_factory.mktemp("radar")
    S.write(str(d))
    return str(d)


@pytest.fixture(scope="module")
def run(folder):
    from atmo3d_radar.run import PolarRun
    return PolarRun(folder, 0.5, 1)


def at(run, t, k, az, g, dz=0.0):
    """x, y, z of azimuth az (deg) and fractional gate g on sweep k's beam at time t
    (dz km above it)."""
    h, s = beam.gate_position(S.R0 + np.asarray(g, float) * S.DR, run.sweeps(t).elev[k])
    a = np.radians(az)
    return s * np.sin(a), s * np.cos(a), h + dz


def value(run, t, x, y, z, name="reflectivity", **kw):
    return sampler.sample(run, run.volume(name, t), t, x, y, z, **kw)


def test_on_a_sweep_between_rays_and_gates(run):
    e = run.sweeps(0).elev[1]
    for az, g in ((40.5, 12.0), (45.5, 12.0), (42.0, 12.3), (200.25, 30.5)):
        assert np.isclose(value(run, 0, *at(run, 0, 1, az, g)), S.refl(az, g, e), atol=1e-4)


def test_across_north(run):
    # (halfway between the rays at 350.5 and 0.5: the mean of their values; the
    # azimuth jumps there, so not refl(355.5, ...))
    e = run.sweeps(0).elev[0]
    got = value(run, 0, *at(run, 0, 0, 355.5, 10.0))
    want = 0.5 * (S.refl(350.5, 10, e) + S.refl(0.5, 10, e))
    assert np.isclose(got, want, atol=1e-4)
    a = value(run, 0, *at(run, 0, 0, 359.0, 10.0))  # (0.15 of the way back to 350.5)
    assert np.isclose(a, 0.15 * S.refl(350.5, 10, e) + 0.85 * S.refl(0.5, 10, e),
                      atol=1e-4)


def test_missing_gate_needs_half_the_weight(run):
    # gate 7 is missing: between 6 and 7 a point takes gate 6's value while it carries
    # at least half the weight, then none
    e = run.sweeps(0).elev[1]
    assert np.isclose(value(run, 0, *at(run, 0, 1, 40.5, 6.4)), S.refl(40.5, 6, e),
                      atol=1e-4)
    assert np.isclose(value(run, 0, *at(run, 0, 1, 40.5, 6.5)), S.refl(40.5, 6, e),
                      atol=1e-4)
    assert np.isnan(value(run, 0, *at(run, 0, 1, 40.5, 6.6)))
    # and the same between sweeps: sweep 1 missing at gate 7, sweep 0 there too
    assert np.isnan(value(run, 0, *at(run, 0, 1, 40.5, 7.0)))


def test_between_sweeps_linear_in_elevation(run):
    sw = run.sweeps(0)
    for w in (0.25, 0.5, 0.9):
        el = (1 - w) * sw.elev[0] + w * sw.elev[1]
        r = S.R0 + 15.0 * S.DR
        h, s = beam.gate_position(r, el)
        a = np.radians(120.5)
        got = value(run, 0, s * np.sin(a), s * np.cos(a), h)
        assert np.isclose(got, S.refl(120.5, 15.0, el), atol=1e-4)


def test_a_volume_cut_short(run):
    # the second volume lacks the 1.3 degree sweep: 0.5 to 2.4 degrees is bridged there,
    # linear in elevation (velocity is: the answer is exact)
    sw0, sw1 = run.sweeps(0), run.sweeps(1)
    assert len(sw1) == 2 and np.allclose(sw1.elev, sw0.elev[[0, 2]])
    a, r = 70.5, S.R0 + 20.0 * S.DR  # (on a ray: vel is not linear in azimuth)
    h, s = beam.gate_position(r, sw0.elev[1])
    got = value(run, 1, s * np.sin(np.radians(a)), s * np.cos(np.radians(a)), h,
                name="velocity")
    assert np.isclose(got, S.vel(a, 20.0, sw0.elev[1]), atol=1e-4)
    # above its top sweep (plus half a beamwidth): none
    h, s = beam.gate_position(10.0, sw1.elev[-1] + 0.8 * beam.BEAMWIDTH)
    assert np.isnan(value(run, 1, s * 0.6, s * 0.8, h, name="velocity"))
    # and with a gap setting narrower than that gap there: none either
    h, s = beam.gate_position(r, sw0.elev[1])
    assert np.isnan(value(run, 1, s * np.sin(np.radians(a)), s * np.cos(np.radians(a)), h,
                          name="velocity", max_gap_km=0.3))


@pytest.fixture
def sector(run):
    """Time 0's sweep 0 without its rays between 90 and 150 degrees (a sector it lacks,
    leaving it 30 rays to the others' 36): a function giving a field's volume with its
    rays moved to match."""
    sw = run.sweeps(0)
    old = sw.az.copy()
    keep = ~((old[0] > 90) & (old[0] < 150))
    order = np.r_[np.where(keep)[0], np.where(~keep)[0]]

    def vol(name):
        v = run.volume(name, 0).copy()
        v[0] = v[0][order]
        v[0][keep.sum():] = np.nan
        return v

    sw.az[0] = np.concatenate([old[0][keep], np.full((~keep).sum(), np.nan)])
    sampler._GEOM.clear()
    ppi._INDEX.clear()
    yield vol
    sw.az[:] = old
    sampler._GEOM.clear()
    ppi._INDEX.clear()


def test_missing_sector_is_empty(run, sector):
    x, y, z = at(run, 0, 0, np.array([120.5, 100.0, 60.5, 85.0]), 20.0)
    v = sampler.sample(run, sector("velocity"), 0, x, y, z)  # (on sweep 0's beam)
    # inside the hole: NaN; by its edge, the nearer ray up to 1.5 spacings (as the PPI)
    assert np.isnan(v[0]) and np.isnan(v[1])
    assert np.isfinite(v[2]) and np.isfinite(v[3])


def test_isosurface_with_sweeps_of_different_ray_counts(run, sector):
    # sweep 0 has 30 rays, the others 36: the shared azimuth grid puts each sweep's
    # nearest ray at each azimuth, so the surface is still on the value, and none lies
    # in the hole of sweep 0 below sweep 1
    box = (-18.0, 18.0, -18.0, 18.0)
    vol = sector("reflectivity")
    m = scene.isosurface(run, 0, vol, box, 25.0, 1, 0.0, 15.0)
    assert m is not None
    x, y, z = m["x"], m["y"], m["z"]
    az, el, r = beam.polar_of(x, y, z)
    sw = run.sweeps(0)
    assert not ((az > 105) & (az < 135) & (el < sw.elev[0] + 0.05)).any()
    g = (r - S.R0) / S.DR
    v = sampler.sample(run, vol, 0, x, y, z)
    ok = ((az > 12) & (az < 348) & ~((az > 80) & (az < 160)) & np.isfinite(v)
          & (np.abs(g - 7 * np.round(g / 7)) > 1.05))
    assert ok.sum() > 20 and np.allclose(v[ok], 25.0, atol=0.05)


def test_regrid_at_its_grid_points(folder, run):
    s = regrid.Settings("linear", 1.0, 0.1, 20.0, 0.0)
    g = regrid.RegriddedRun(regrid.path_of(folder, s), 0.5, 1)
    a = g.regridded("reflectivity", 0)
    X, Y = np.meshgrid(g.xh, g.yh)
    for k in range(g.nk):
        az, el, r = beam.polar_of(X, Y, np.full(X.shape, g.z[k]))
        gate = (r - S.R0) / S.DR
        sw = run.sweeps(0)
        inside = ((el > sw.elev[0] + 0.01) & (el < sw.elev[-1] - 0.01) & (gate > 1)
                  & (gate < S.NG - 2) & (az > 1) & (az < 350) & (np.hypot(X, Y) <= 20.0)
                  & (np.abs(gate - 7 * np.round(gate / 7)) > 1.05))
        if inside.any():
            assert np.allclose(a[k][inside], S.refl(az, gate, el)[inside], atol=1e-3)
    # beyond the maximum range: empty
    assert np.isnan(a[:, np.hypot(X, Y) > 20.0]).all()
    # a wider gap setting than the sweeps' leaves the same; a narrow one empties them
    tight = regrid.RegriddedRun(regrid.path_of(folder, regrid.Settings(
        "linear", 1.0, 0.1, 20.0, 0.01)), 0.5, 1).regridded("reflectivity", 0)
    assert np.isfinite(tight).sum() < 0.5 * np.isfinite(a).sum()
