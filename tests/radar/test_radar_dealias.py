"""Radial velocity dealiasing (atmo3d_radar.dealias) on folded analytic winds, and the
dealiased velocity a radar run offers (run.DEALIASED), on synthetic Level II and
CfRadial folders."""
import numpy as np
import pytest

atmo3d_radar = pytest.importorskip("atmo3d_radar")
pytest.importorskip("scipy")
from atmo3d_radar import dealias as D  # noqa: E402

N = 26.0
NR, NG = 360, 400


def fold(v, nyq=N):
    return (((v + nyq) % (2 * nyq)) - nyq).astype(np.float32)


def wind(peak=60.0, toward=225.0, noise=0.0, seed=0):
    """A uniform wind from `toward` growing with range to `peak` m/s, on NR x NG gates
    (rays 1 degree apart, gates 0.25 km): its radial velocity."""
    az = np.deg2rad(np.arange(NR) + 0.5)[:, None]
    r = 2.0 + 0.25 * np.arange(NG)
    v = np.minimum(peak, r / 1.5)[None, :] * np.cos(az - np.deg2rad(toward))
    if noise:
        v = v + np.random.default_rng(seed).normal(0.0, noise, v.shape)
    return v


def test_unfolds_a_wind_beyond_twice_nyquist():
    true = wind(peak=2.3 * N)  # (folded up to twice)
    out = D.dealias(fold(true), N)
    assert np.abs(fold(true) - true).max() > 2 * N  # (it was folded, twice)
    np.testing.assert_allclose(out, true, atol=1e-3)


def test_noise_and_missing_gates():
    true = wind(noise=2.0, seed=3)
    true[:, :10] = np.nan  # (no echo near the radar)
    true[100:110, 50:300] = np.nan  # (a hole)
    true[::17, ::23] = np.nan  # (scattered)
    out = D.dealias(fold(true), N)
    ok = np.isfinite(true)
    assert np.array_equal(np.isfinite(out), ok)  # (missing stays missing)
    assert np.mean(np.abs(out[ok] - true[ok]) < 1e-3) > 0.999


def test_echo_beyond_a_gap_in_range_follows_the_main_echo():
    true = wind(peak=2.0 * N)
    true[:, 200:230] = np.nan  # (a ring of no echo: what is beyond touches nothing)
    out = D.dealias(fold(true), N)
    ok = np.isfinite(true)
    np.testing.assert_allclose(out[ok], true[ok], atol=1e-3)


def test_fold_across_north():
    """The last ray touches the first: a fold line crossing azimuth 0."""
    true = wind(peak=1.8 * N, toward=0.0)
    np.testing.assert_allclose(D.dealias(fold(true), N), true, atol=1e-3)


def test_isolated_echo_left_as_measured():
    v = np.full((NR, NG), np.nan, np.float32)
    v[10:15, 50:60] = 20.0
    v[200:203, 300:310] = -25.0
    np.testing.assert_array_equal(D.dealias(v, N), v)


def test_no_nyquist_padding_and_empty():
    v = fold(wind())
    np.testing.assert_array_equal(D.dealias(v, np.nan), v)
    np.testing.assert_array_equal(D.dealias(v, 0.0), v)
    e = np.full((4, 5), np.nan, np.float32)
    assert np.isnan(D.dealias(e, N)).all()
    # padding rays (after nray) are left alone, and not taken as the first ray's
    # neighbours
    pad = np.vstack([v, np.full((5, NG), 99.0, np.float32)])
    out = D.dealias(pad, N, nray=NR)
    np.testing.assert_array_equal(out[NR:], pad[NR:])
    np.testing.assert_allclose(out[:NR], wind(), atol=1e-3)


def test_volume_uses_each_sweeps_nyquist():
    class Table:
        nyquist = np.array([N, 30.0, np.nan])
        az = np.tile(np.arange(NR, dtype=float), (3, 1))
    true = wind(peak=45.0)
    vol = np.stack([fold(true, N), fold(true, 30.0), true.astype(np.float32)])
    out = D.dealias_volume(vol, Table)
    np.testing.assert_allclose(out[0], true, atol=1e-3)
    np.testing.assert_allclose(out[1], true, atol=1e-3)
    np.testing.assert_array_equal(out[2], vol[2])  # (no Nyquist: as it is)


# ---------------------------------------------------------------------- the run's field
def test_level2_run_offers_dealiased_velocity(tmp_path):
    import synthetic_level2 as S
    from atmo3d_radar.run import DEALIASED, PolarRun
    S.write(str(tmp_path))
    run = PolarRun(str(tmp_path), cache_gb=0.5, workers=1)
    assert DEALIASED in run.vars and run.vars[DEALIASED].units == "m/s"
    sw = run.sweeps(0)
    for k in range(len(sw)):
        raw = run.read_sweep("velocity", 0, k)
        want = D.dealias(raw, sw.nyquist[k], int(np.isfinite(sw.az[k]).sum()))
        np.testing.assert_array_equal(run.read_sweep(DEALIASED, 0, k), want)
        np.testing.assert_array_equal(np.isfinite(want), np.isfinite(raw))
    vol = run.volume(DEALIASED, 1)
    assert vol.shape == run.volume("velocity", 1).shape
    assert run.in_file(DEALIASED, 1)


def test_cfradial_run_offers_dealiased_velocity(tmp_path):
    import synthetic_radar as S
    from atmo3d_radar.run import DEALIASED, PolarRun
    S.write(str(tmp_path))
    run = PolarRun(str(tmp_path), cache_gb=0.5, workers=1)
    assert DEALIASED in run.vars
    sw = run.sweeps(0)
    raw = run.read_sweep("velocity", 0, 0)
    np.testing.assert_array_equal(
        run.read_sweep(DEALIASED, 0, 0),
        D.dealias(raw, sw.nyquist[0], int(np.isfinite(sw.az[0]).sum())))


def test_catalog_label():
    from atmo3d.core.catalog import of_model
    cat = of_model("radar")
    assert "dealiased" in cat.natives["velocity_dealiased"][0].lower()
