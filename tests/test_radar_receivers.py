"""Several bistatic receivers (atmo3d_radar.catalog): the receiver network's fields carry
the receiver's site as a suffix (beta_nwc), so a second receiver's fields are read, grouped,
labelled and listed like the first's.  Synthetic volumes with a second receiver added."""
import netCDF4
import numpy as np
import pytest

import synthetic_radar as S
from atmo3d.core import models

atmo3d_radar = pytest.importorskip("atmo3d_radar")
from atmo3d_radar import catalog as RC  # noqa: E402

NWC_BETA, XYZ_BETA, XYZ_VEL = 60.0, 120.0, 7.0


@pytest.fixture(scope="module")
def two_receivers(tmp_path_factory):
    d = tmp_path_factory.mktemp("radar2rx")
    for path in S.write(str(d)):
        with netCDF4.Dataset(path, "a") as f:
            n = len(f.dimensions["time"])
            for name, val in (("beta_nwc", NWC_BETA), ("beta_xyz", XYZ_BETA),
                              ("bistatic_velocity_xyz", XYZ_VEL),
                              ("receiver_ncp_xyz", 1.0)):
                v = f.createVariable(name, "f4", ("time", "range"))
                v[:] = np.full((n, len(f.dimensions["range"])), val, np.float32)
    return models.open_run(str(d), workers=1, cache_gb=0.5)


def test_receiver_field_names_are_read_by_rule():
    assert RC.receiver_field("beta_nwc") == ("beta", "nwc")
    assert RC.receiver_field("beta_cutoff_xyz") == ("beta_cutoff", "xyz")  # (not beta)
    assert RC.receiver_field("original_bistatic_velocity_nwc") == (
        "original_bistatic_velocity", "nwc")
    assert RC.receiver_field("bistatic_velocity_unsmoothed_a_b") == (
        "bistatic_velocity_unsmoothed", "a_b")
    for other in ("beta", "beta_", "velocity", "u", "receiver_ncp", "reflectivity"):
        assert RC.receiver_field(other) is None


def test_each_receiver_is_labelled_grouped_and_listed_alike(two_receivers):
    cat = two_receivers.catalog
    for rx in ("nwc", "xyz"):
        label, units, _, _, rng, div, = cat.look(f"bistatic_velocity_{rx}")
        assert label == f"Bistatic velocity ({rx.upper()})" and units == "m/s"
        assert rng == (-30, 30) and div
        assert cat.group(f"bistatic_velocity_{rx}", 3) == "Bistatic"
        assert cat.tier(f"bistatic_velocity_{rx}", "Bistatic") == "main"
        assert cat.look(f"beta_{rx}")[0] == f"Bistatic angle β ({rx.upper()})"
        assert cat.tier(f"beta_{rx}", "Bistatic") == "other"
        assert cat.group(f"receiver_ncp_{rx}", 3) == "Bistatic QC"
        assert cat.tier(f"receiver_ncp_{rx}", "Bistatic QC") == "other"
        assert cat.look(f"receiver_ncp_{rx}")[0] == f"receiver_ncp_{rx}"  # (raw: stopgap)
    # the radar's own fields and the combined retrieval are unaffected
    assert cat.look("velocity")[0] == "Radial velocity"
    assert cat.tier("u", "Retrieved winds") == "main"


def test_a_second_receivers_fields_are_read(two_receivers):
    run = two_receivers
    for n in ("beta_nwc", "beta_xyz", "bistatic_velocity_xyz", "receiver_ncp_xyz"):
        assert n in run.vars, n
    vol = run.volume("beta_xyz", 0)
    assert vol.shape == (3, S.NRAY, S.NG) and np.allclose(vol, XYZ_BETA)
    assert np.allclose(run.volume("beta_nwc", 0), NWC_BETA)
    assert np.allclose(run.volume("bistatic_velocity_xyz", 0), XYZ_VEL)
