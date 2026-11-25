"""The NEXRAD Level II decoder (atmo3d_radar.level2) and Level II folders as a PolarRun, on
synthetic volumes with known values (tests/synthetic_level2.py), each checked against
MetPy's parser (metpy.io.Level2File) as well."""
import datetime as dt
import logging
import os

import numpy as np
import pytest

import synthetic_level2 as S
from atmo3d.core import models

atmo3d_radar = pytest.importorskip("atmo3d_radar")
from atmo3d_radar import level2 as L  # noqa: E402

T0 = dt.datetime(2013, 5, 20, 19, 51, 11)


@pytest.fixture(scope="module", params=["bz2", "gzip", "none"])
def path(request, tmp_path_factory):
    d = tmp_path_factory.mktemp(f"l2-{request.param}")
    return S.write(str(d), [T0], compress=request.param)[0]


@pytest.fixture(scope="module")
def vol(path):
    return L.Volume(path)


# ---------------------------------------------------------------------- names, headers
def test_names():
    assert L.name_time("KTLX20130520_195111_V06.gz") == T0
    assert L.name_time("KTLX20230227_040142_V06") == dt.datetime(2023, 2, 27, 4, 1, 42)
    assert L.name_time("/x/KTLX20130520_195111") == T0
    assert not L.candidate("KTLX20130520_195111_MDM")  # (the archive's metadata files)
    assert not L.candidate("cfrad.20260404_010635.000_to_20260404_011200.000_X.nc")
    assert not L.candidate("cm1out_000001.nc")


def test_is_level2(path, tmp_path):
    assert L.is_level2(path)
    other = tmp_path / "KTLX20130520_195111_V06"
    other.write_bytes(b"CDF\x01" + b"\0" * 40)
    assert not L.is_level2(str(other))
    assert L.files_in(str(tmp_path)) == []


def test_no_radials(tmp_path):
    p = tmp_path / "KTLX20130520_195111_V06"
    p.write_bytes(S.volume_bytes(T0, cuts=[], compress="none"))
    with pytest.raises(ValueError, match="no Message 31"):
        L.Volume(str(p))


# ---------------------------------------------------------------------- the sweep table
def test_sweep_table(vol):
    # five cuts, two split pairs merged: 0.5 (cuts 1+2), 0.5 again (4+5), 1.5 (3)
    assert len(vol) == 3 and vol.cuts == [(1, 2), (4, 5), (3,)]
    assert np.allclose(vol.elev, [0.5, 0.5, 1.5], atol=0.02)
    assert (np.diff(vol.elev) >= -0.02).all()
    assert vol.station == "KTLX" and vol.vcp == S.VCP
    assert np.allclose(vol.site[:2], S.SITE[:2]) and vol.site[2] == S.SITE[2] + S.SITE[3]
    assert np.allclose(vol.nyquist, S.NYQ)
    assert np.allclose(vol.fixed, [0.5, 0.5, 1.5], atol=0.01)  # (Message 5's angles)
    assert vol.nr == S.NRAY
    assert (np.diff(vol.az, axis=1) > 0).all() and np.isclose(vol.az[0, 0], 0.5)
    # SAILS: the repeated elevation's sweeps are labelled with their times
    assert vol.label(0) == "0.5° 19:51:11" and vol.label(1) == "0.5° 19:52:11"
    assert vol.label(2) == "1.5°"
    assert vol.times[2] == T0 + dt.timedelta(seconds=40)
    # the data-free table says the same
    t = vol.table
    assert len(t) == 3 and t.label(1) == vol.label(1) and t.az is vol.az


def test_ranges(vol):
    assert np.isclose(vol.ranges[0], S.FIRST / 1000) and len(vol.ranges) == 40
    assert np.allclose(np.diff(vol.ranges), S.GAP / 1000)


# ---------------------------------------------------------------------- values
def _expect(code, cut, ng, nall):
    s, o = S._scale(code)
    out = np.full((S.NRAY, nall), np.nan)
    for j, az in enumerate(np.arange(S.NRAY) + 0.5):
        key = S.ray_key(az)
        out[j, :ng] = [S.value(S.raw_of(code, key, g, cut), s, o) for g in range(ng)]
    return out


def test_values_of_the_surveillance_cut(vol):
    got = vol.sweep("REF", 0)
    assert got.dtype == np.float32 and got.shape == (S.NRAY, 40)
    np.testing.assert_allclose(got, _expect("REF", 0, 40, 40), equal_nan=True)
    assert np.isnan(got[[S.ray_key(a) for a in np.arange(360) + 0.5].index(7), 3])  # raw 0
    zdr = vol.sweep("ZDR", 0)  # (30 gates: NaN past them)
    np.testing.assert_allclose(zdr, _expect("ZDR", 0, 30, 40), equal_nan=True)


def test_doppler_moments_come_from_the_doppler_cut(vol):
    # cut 2's rays are 0.3 deg on from cut 1's: each surveillance ray takes the nearest
    np.testing.assert_allclose(vol.sweep("VEL", 0), _expect("VEL", 1, 30, 40),
                               equal_nan=True)
    np.testing.assert_allclose(vol.sweep("VEL", 1), _expect("VEL", 4, 30, 40),
                               equal_nan=True)
    np.testing.assert_allclose(vol.sweep("REF", 2), _expect("REF", 2, 36, 40),
                               equal_nan=True)
    assert not vol.has("ZDR", 2) and np.isnan(vol.sweep("ZDR", 2)).all()
    v = vol.volume("VEL")
    assert v.shape == (3, S.NRAY, 40)
    np.testing.assert_array_equal(v[2], vol.sweep("VEL", 2))


def test_nearest_rays():
    have = np.array([0.8, 1.8, 2.8, 359.8])
    got = L.Volume._nearest(np.array([0.5, 2.5, 359.5, 180.0]), have)
    assert got[:3] == [0, 2, 3] and got[3] == -1  # (none near 180: left empty)


def test_same_as_metpy(path, vol):
    """Every ray and gate of every moment as MetPy reads it (its cut, its nearest ray)."""
    metpy = pytest.importorskip("metpy.io")
    logging.getLogger("metpy").setLevel(logging.ERROR)
    m = metpy.Level2File(path)
    assert len(m.sweeps) == len(S.CUTS)
    vc = m.sweeps[0][0].vol_consts
    assert np.isclose(vc.lat, vol.site[0]) and vc.site_amsl + vc.feedhorn_agl == vol.site[2]
    checked = 0
    for k in range(len(vol)):
        for code in vol.codes:
            if not vol.has(code, k):
                continue
            src = vol._sweeps[k]["src"][code]
            rays = m.sweeps[src.num - 1]
            az = np.array([r.header.az_angle for r in rays])
            ours = vol.sweep(code, k)
            for j, a in enumerate(vol.az[k]):
                i = int(np.argmin(L._ang_diff(az, a)))
                mom = rays[i].moments
                _, vals = mom[code] if code in mom else mom[code.encode()]
                np.testing.assert_allclose(ours[j, :len(vals)], vals, rtol=1e-6,
                                           equal_nan=True)
                assert np.isnan(ours[j, len(vals):]).all()
                checked += 1
    assert checked == 10 * S.NRAY  # (2 merged sweeps x 4 moments, 1 sweep x 2)


def test_decoded_volumes_are_kept(path):
    assert L.volume(path) is L.volume(path)


# ---------------------------------------------------------------------- as a run
@pytest.fixture(scope="module")
def folder(tmp_path_factory):
    d = str(tmp_path_factory.mktemp("l2run"))
    S.write(d, [T0])
    # a later volume whose reflectivity reaches less far (36 gates)
    S.write(d, [T0 + dt.timedelta(minutes=4, seconds=16)], ref_gates=36)
    with open(os.path.join(d, "KTLX20130520_195111_MDM"), "wb") as f:
        f.write(b"not a volume")
    return d


@pytest.fixture(scope="module")
def run(folder):
    return models.open_run(folder, workers=1, cache_gb=0.5)


def test_detected_as_radar(folder):
    m = models.detect(folder)
    assert m is not None and m.key == "radar"
    assert m.count(folder) == 2 and m.summary(folder) == "2 volumes"


def test_run(run):
    assert run.format == "level2" and run.model == "radar" and run.instrument == "KTLX"
    assert list(run.times) == [0.0, 256.0]
    assert {"reflectivity", "velocity", "spectrum_width",
            "differential_reflectivity"} <= set(run.vars)
    assert run.vars["velocity"].attrs["level2_moment"] == "VEL"
    assert np.isclose(run.ranges[0], 2.125) and len(run.ranges) == 40
    assert run.nsweeps == 3 and run.sweeps(1).label(2) == "1.5°"
    assert run.geo is not None and np.isfinite(run.site).all()


def test_run_reads(run):
    v = run.volume("reflectivity", 0)
    assert v.shape == (3, S.NRAY, 40)
    np.testing.assert_array_equal(run.read_sweep("velocity", 0, 1),
                                  run.volume("velocity", 0)[1])
    # the later volume on the run's gates: NaN past its own 36
    later = run.volume("reflectivity", 1)
    assert later.shape == v.shape and np.isnan(later[:, :, 36:]).all()
    assert np.isfinite(later[0, :, :36]).sum() > 0
    h = run.read_sweep("beam_height", 0, 2)
    assert h.shape == (S.NRAY, 40) and (np.diff(h[0]) > 0).all()


def test_section_on_a_run_without_winds(tmp_path):
    """Level II has no retrieved u, v: the section's wind vectors are left off, and the
    section is drawn (it failed with KeyError: 'u')."""
    import re
    import time
    pytest.importorskip("panel")
    from atmo3d.registry import Registry
    from atmo3d.viewer import app as A
    S.write(str(tmp_path))
    reg = Registry(str(tmp_path), 0.5, 1)
    run, F = reg.get()
    assert "u" not in F
    v = A.Viewer(run, F, reg=reg)
    v.main()
    try:
        v.mode.set("Cross-section")
        v.xs_pts = [(-5.0, -2.0), (6.0, 4.0)]
        v.gen["xs"] += 1
        spec = v.xs_spec()
        assert spec["vecs"] and not any(o["on"] for o in spec["vecs"])
        v._xs_job(spec, v.gen["xs"])
        t0 = time.time()
        while "long" not in v.xs_status.object and time.time() - t0 < 30:
            time.sleep(0.02)
        assert "km long" in re.sub("<[^>]+>", " ", v.xs_status.object)
    finally:
        v.close()


def test_no_vector_menus_without_winds(tmp_path):
    """Level II has no u, v: the map's and the section's Vectors menus, and the 3D
    box's Vectors and Streamlines, are not offered; a CfRadial run with retrieved winds
    keeps the map's and the section's."""
    pytest.importorskip("panel")
    import synthetic_radar
    from atmo3d.registry import Registry
    from atmo3d.viewer import app as A

    def menus(folder):
        reg = Registry(folder, 0.5, 1)
        run, F = reg.get()
        v = A.Viewer(run, F, reg=reg)
        v.main()
        try:
            v._xs_layout()
            shown = lambda d, k: d.items[k][0].visible  # noqa: E731
            return (shown(v.map_drawer, "vec"), shown(v.xs_drawer, "vec"),
                    shown(v.v3_drawer, "sv"), shown(v.v3_drawer, "st"))
        finally:
            v.close()
    (tmp_path / "l2").mkdir()
    (tmp_path / "cf").mkdir()
    S.write(str(tmp_path / "l2"))
    synthetic_radar.write(str(tmp_path / "cf"))
    assert menus(str(tmp_path / "l2")) == (False, False, False, False)
    # (a run with no grid draws no 3D vectors yet)
    assert menus(str(tmp_path / "cf")) == (True, True, False, False)


def test_3d_box_on_a_run_without_winds(tmp_path):
    """A 3D box on a page in a browser: the 3D workspace's first showing builds its
    widgets, and the 3D vectors' empty menu (no u, v) set its vector to None, which
    failed (KeyError: None) and lost the box."""
    from types import SimpleNamespace as NS
    pytest.importorskip("panel")
    from bokeh.document import Document
    from atmo3d.registry import Registry
    from atmo3d.viewer import app as A
    S.write(str(tmp_path))
    reg = Registry(str(tmp_path), 0.5, 1)
    run, F = reg.get()
    v = A.Viewer(run, F, reg=reg)
    page = v.main()
    try:
        page.get_root(Document())  # (the page's models, as a session's)
        v.mode.set("3D region")
        v._on_select(NS(final=True, geometry=dict(type="rect", x0=-5.0, x1=5.0,
                                                  y0=-4.0, y1=4.0)))
        assert v.box == (-5.0, 5.0, -4.0, 4.0)
        assert v.workspace.value == "3D" and v.v3_ws.visible
        assert not any(o["on"].value for o in v.svs)
    finally:
        v.close()
