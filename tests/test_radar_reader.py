"""The radar reader (atmo3d_radar): CfRadial volumes as a PolarRun, on synthetic volumes
with analytic fields (tests/synthetic_radar.py)."""
import numpy as np
import pytest

import synthetic_radar as S
from atmo3d.core import models
from atmo3d.core.run import MissingAtTime, Run, Source

atmo3d_radar = pytest.importorskip("atmo3d_radar")
from atmo3d_radar import beam, cfradial  # noqa: E402
from atmo3d_radar.run import PolarRun  # noqa: E402


@pytest.fixture(scope="module")
def folder(tmp_path_factory):
    d = tmp_path_factory.mktemp("radar")
    S.write(str(d))
    return str(d)


@pytest.fixture(scope="module")
def run(folder):
    return models.open_run(folder, workers=1, cache_gb=0.5)


def test_detected_as_radar_and_not_as_another_type(folder):
    m = models.detect(folder)
    assert m is not None and m.key == "radar"
    import os
    entries = list(os.scandir(folder))
    assert models.MODELS["radar"].looks(entries)
    assert not models.MODELS["cm1"].looks(entries)
    assert models.summary(folder) == "2 volumes"


def test_a_polar_run_is_a_source_not_a_grid_run(run):
    assert isinstance(run, PolarRun) and isinstance(run, Source)
    assert not isinstance(run, Run)
    assert run.can("native_polar") and not run.can("soundings")
    assert run.catalog.key == "radar" and run.role("refl") == "reflectivity"


def test_times_come_from_the_file_names_in_time_order(run):
    # (name order would put _10_ first)
    assert [f.rsplit("_", 3)[1] for f in run.files] == ["9", "10"]
    assert run.time_label(0) == "02:00:40 UTC" and run.time_label(1) == "02:07:33 UTC"
    assert np.allclose(run.times, [0.0, 413.0])


def test_name_time():
    assert str(cfradial.name_time("combined_radar_object_advcor_9_20260404_020040.nc")) \
        == "2026-04-04 02:00:40"
    assert str(cfradial.name_time("cfrad.20260404_010635.000_to_20260404_011200.000_X.nc")) \
        == "2026-04-04 01:06:35"
    assert cfradial.name_time("cm1out_000001.nc") is None


def test_sweep_table_sorted_by_measured_elevation(run):
    sw = run.sweeps(0)
    assert len(sw) == 3 and sw.nr == S.NRAY
    want = sorted(f + o for f, o in zip(S.FIXED, S.OFFSET))
    assert np.allclose(sw.elev, want, atol=1e-6)
    assert np.allclose(sw.fixed, sorted(S.FIXED))
    assert np.all(np.diff(sw.az, axis=1) > 0)  # rays by azimuth
    assert len(run.sweeps(1)) == 2  # (the second volume is a sweep short)


def test_volume_matches_the_analytic_field(run):
    vol = run.volume("reflectivity", 0)
    sw = run.sweeps(0)
    assert vol.shape == (3, S.NRAY, S.NG) and vol.dtype == np.float32
    g = np.arange(S.NG)
    for k in range(3):
        want = S.refl(sw.az[k][:, None], g[None, :], sw.elev[k])
        want[:, g % 7 == 0] = np.nan
        assert np.allclose(vol[k], want, atol=1e-4, equal_nan=True)
    v = run.volume("velocity", 0)
    want = S.vel(sw.az[1][:, None], g[None, :], sw.elev[1])
    assert np.allclose(v[1], want, atol=1e-4)


def test_padding_rays_are_never_read(run):
    assert np.isfinite(run.volume("velocity", 0)).all()


def test_default_fill_is_missing(run):
    u = run.volume("u", 0)
    assert np.isnan(u[..., :5]).all() and np.allclose(u[..., 5:], 10.0)


def test_read_sweep_is_the_volumes_sweep(folder):
    r = models.open_run(folder, workers=1, cache_gb=0.5)
    s = r.read_sweep("reflectivity", 0, 2)  # (read alone: nothing cached yet)
    assert r.cached("reflectivity", 0) is None
    assert np.array_equal(s, r.volume("reflectivity", 0)[2], equal_nan=True)


def test_volume_shape_follows_each_times_sweeps(run):
    assert run.volume("reflectivity", 1).shape == (2, S.NRAY, S.NG)


def test_a_field_missing_at_one_time(run):
    assert run.volume("w", 0).shape == (3, S.NRAY, S.NG)
    with pytest.raises(MissingAtTime):
        run.volume("w", 1)


def test_geometry_fields_follow_the_beam_model(run):
    sw = run.sweeps(0)
    h = run.read_sweep("beam_height", 0, 2)
    want, _ = beam.gate_position(run.ranges, sw.elev[2])
    assert np.allclose(h, want[None, :], atol=1e-5)
    az = run.volume("ray_azimuth", 0)
    assert np.allclose(az[0, :, 0], sw.az[0])
    assert run.catalog.tier("beam_height", "Geometry") == "hidden"


def test_site_geo_and_neutral_facts(run):
    assert np.allclose(run.ranges[[0, -1]], [S.R0, S.R0 + S.DR * (S.NG - 1)])
    lon, lat = run.geo.lonlat(0.0, 0.0)
    assert abs(lat - S.SITE[0]) < 1e-9 and abs(lon - S.SITE[1]) < 1e-9
    x, y = run.geo.xy(S.SITE[1], S.SITE[0] + 0.1)  # 0.1 deg north: ~11.1 km
    assert abs(x) < 1e-6 and abs(y - 11.09) < 0.02
    x0, x1, y0, y1 = run.extent
    assert x0 == -x1 and y0 == -y1 and abs(x1 - run.ranges[-1]) < 0.01
    assert run.size_label == f"3 sweeps × {S.NRAY} rays × {S.NG} gates"
    assert run.field_bytes == 4 * 3 * S.NRAY * S.NG
    assert 0 < run.ztop <= 20.0


def test_beam_model_round_trip():
    r = np.array([5.0, 100.0, 300.0])
    for e in (0.5, 4.0, 19.5):
        h, s = beam.gate_position(r, e)
        az, el, rr = beam.polar_of(s * np.sin(np.radians(30.0)),
                                   s * np.cos(np.radians(30.0)), h)
        assert np.allclose(el, e, atol=1e-9) and np.allclose(rr, r, atol=1e-6)
        assert np.allclose(az, 30.0)
    # 4/3 earth: a 0.5 deg beam is about 1.4 km up at 100 km
    assert abs(beam.gate_position(100.0, 0.5)[0] - 1.46) < 0.05
