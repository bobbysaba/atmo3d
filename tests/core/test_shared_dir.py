"""The reader processes hand their reads back through files in a shared folder: tmpfs
(/dev/shm) on Linux, the system's temporary folder (on disk) on macOS and Windows.
These run the on-disk route on any OS by pointing a run at a temporary folder."""
import os

import numpy as np

from atmo3d import config
from atmo3d.core import run as R


def test_shared_volume_on_disk_reads_back_and_leaves_nothing(tmp_path):
    sv = R._SharedVolume(str(tmp_path), (3, 4, 5))
    assert not sv.mapped
    a = np.arange(60, dtype=np.float32).reshape(3, 4, 5)
    R._write_rows(sv.path, a[1:], 1)
    R._write_rows(sv.path, a[:1], 0)
    got = sv.array()
    np.testing.assert_array_equal(got, a)
    got[0, 0, 0] = -1  # (a writable array of its own)
    assert os.listdir(tmp_path) == []
    R._write_rows(sv.path, a, 0)  # (a cancelled read's file is gone: skipped)
    assert os.listdir(tmp_path) == []


def test_a_file_still_open_elsewhere_is_removed_later(tmp_path, monkeypatch):
    """(Windows refuses to remove a file a reader still has open.)"""
    p = tmp_path / "x.vol"
    p.write_bytes(b"0")
    real = os.remove

    def refuse(path):
        raise PermissionError(path)

    monkeypatch.setattr(os, "remove", refuse)
    R._unlink(str(p))
    assert p.exists() and str(p) in R._leftover
    monkeypatch.setattr(os, "remove", real)
    R._SharedVolume(str(tmp_path), (1, 1, 1)).discard()  # (a new volume sweeps)
    assert not p.exists() and not R._leftover


def test_parallel_reads_through_a_folder_on_disk(demo_run, tmp_path, monkeypatch):
    """Whole volumes, levels and column maxima read by the reader processes through
    files on disk are the values read in this process, and leave no files."""
    from atmo3d_cm1.run import CM1Run

    T, ks, names = 4, [2, 3, 7], ["th", "u", "w"]
    here = CM1Run(demo_run, cache_gb=1, workers=1)
    run = CM1Run(demo_run, cache_gb=1, workers=2)
    run._shm = str(tmp_path)
    monkeypatch.setattr(R, "BLOCK_BYTES", 0)  # (every read worth the readers)
    got = run.read_levels(names, T, ks)
    assert run._pool_uses > 0
    for n in names:
        np.testing.assert_allclose(
            got[n], np.stack([here.read_level(n, T, k) for k in ks]), rtol=1e-6)
    np.testing.assert_allclose(run.reduce_levels("w", T, "max"),
                               here.volume("w", T).max(axis=0), rtol=1e-6)
    run.load_volumes(names, T)
    for n in names:
        np.testing.assert_allclose(run.cached(n, T), here.volume(n, T), rtol=1e-6)
    assert os.listdir(tmp_path) == []


def test_machine_memory_and_peak_memory_known():
    from atmo3d import bench

    assert config.machine_memory() > 1024**3
    assert 0 < bench._peak_rss_gb() < config.machine_memory() / 1024**3
