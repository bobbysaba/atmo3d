"""The real demo run atmo3d --demo opens (atmo3d/demo.py, demo_data/supercell, built by
tools/make_real_demo.py): copied once into the cache, a demo run however new its files,
and readable as a CM1 run with its packed fields, stretched levels and parcels.  Skipped
where the shipped copy is missing (a pip install)."""
import os

import numpy as np
import pytest

from atmo3d import demo
from atmo3d.core import models, run as run_mod
from atmo3d_cm1 import parcels as P

needs_data = pytest.mark.skipif(demo.shipped() is None, reason="no demo_data/ (pip install)")


@pytest.fixture(scope="module")
def real(tmp_path_factory):
    return demo.make(str(tmp_path_factory.mktemp("real-demo")))


@pytest.fixture(scope="module")
def run(real):
    return models.open_run(real, workers=1)


@needs_data
def test_copied_once_and_a_demo_run(real, monkeypatch):
    root = os.path.dirname(real)
    assert os.path.basename(real) == demo.RUN
    assert sorted(os.listdir(real)) == sorted(os.listdir(demo.shipped()))
    first = os.stat(os.path.join(real, "cm1out_000001.nc")).st_mtime_ns
    assert demo.make(root) == real  # (up to date: not copied again)
    assert os.stat(os.path.join(real, "cm1out_000001.nc")).st_mtime_ns == first
    assert demo.is_demo(real)
    # finished however new its files: never "still being written"
    monkeypatch.setenv("ATMO3D_SETTLE_SECONDS", "100000000")
    files = sorted(f for f in os.listdir(real) if f.startswith("cm1out_0"))
    assert run_mod.finished(files, real) == len(files)


def test_copy_redone_when_the_shipped_one_changes(tmp_path, monkeypatch):
    data = tmp_path / "demo_data"
    (data / demo.RUN).mkdir(parents=True)
    (data / demo.RUN / "namelist.input").write_text(" &param1\n nx = 4,\n /\n", encoding="utf-8")
    monkeypatch.setattr(demo, "DATA", str(data))
    root = str(tmp_path / "cache")
    run = demo.make(root)
    assert open(os.path.join(run, "namelist.input"), encoding="utf-8").read().count("nx = 4")
    (data / demo.RUN / "namelist.input").write_text(" &param1\n nx = 8,\n /\n", encoding="utf-8")
    (data / demo.RUN / "cm1out_000001.nc").write_bytes(b"new")
    assert demo.make(root) == run
    assert sorted(os.listdir(run)) == ["cm1out_000001.nc", "namelist.input"]
    assert open(os.path.join(run, "namelist.input"), encoding="utf-8").read().count("nx = 8")
    assert not os.path.exists(run + ".part")


def test_no_shipped_copy_says_where_to_get_it(tmp_path, monkeypatch):
    monkeypatch.setattr(demo, "DATA", str(tmp_path / "nothing"))
    assert demo.shipped() is None
    with pytest.raises(FileNotFoundError, match="repository"):
        demo.make(str(tmp_path / "cache"))


@needs_data
def test_opens_as_a_cm1_run(run):
    assert run.model == "cm1"
    assert np.allclose(run.times, np.arange(0.0, 7201.0, 600.0))
    assert (run.ni, run.nj, run.nk) == (80, 80, 44)
    assert np.allclose(np.diff(run.xh), 1.0) and np.allclose(np.diff(run.yh), 1.0)
    dz = np.diff(run.zf)
    assert dz[0] == pytest.approx(0.1, abs=0.01) and dz[-1] == pytest.approx(0.5, abs=0.01)
    assert (np.diff(dz) > -1e-4).all()  # stretched upwards, then constant
    assert (run.umove, run.vmove) == (12.5, 3.0)
    assert {"th", "prs", "qv", "qr", "dbz", "uinterp", "vinterp", "winterp", "zvort",
            "th0", "prs0", "qv0", "u0", "v0", "uh", "cref", "sws"} <= set(run.vars)
    assert not {"u", "v", "w"} & set(run.vars)  # (left out: atmo3d uses uinterp...)


@needs_data
def test_packed_fields_read_as_floats(run):
    last = len(run.times) - 1
    k5 = int(np.argmin(np.abs(run.z - 5.0)))
    w = run.read_level("winterp", last, k5)
    assert w.dtype == np.float32 and np.isfinite(w).all()
    assert w.max() > 20.0  # the supercell's updraft
    assert run.read_level("dbz", last, 0).max() > 50.0
    th = run.read_level("th", 0, 0)  # t = 0: the undisturbed base state
    assert np.ptp(th) < 0.02 and 295.0 < th.mean() < 305.0


@needs_data
def test_derived_fields_stand_in_for_the_ones_left_out(real):
    from atmo3d.registry import Registry
    run, F = Registry(real, 2, 1).get(real)
    assert {"thpert", "prspert", "buoy"} <= set(F.defs)


@needs_data
def test_parcels(run, tmp_path, monkeypatch):
    monkeypatch.setattr(P, "CACHE_DIR", str(tmp_path / "cache"))
    pf = P.ParcelFile(P.find_files(run.path))
    assert pf.n == 1500
    assert np.allclose(pf.times, np.arange(0.0, 7201.0, 60.0))  # finer than the 3D output
    x = pf.read("x")
    assert not np.isnan(x[0]).any()  # all inside the box at the start
    gone = np.isnan(x)
    assert (gone[:-1] <= gone[1:]).all()  # ... and gone for good once they leave it
    assert np.nanmin(x) >= run.xh[0] - 0.5 and np.nanmax(x) <= run.xh[-1] + 0.5
    assert np.nanmax(pf.read("w")) > 20.0  # (most were picked for reaching the updraft)
