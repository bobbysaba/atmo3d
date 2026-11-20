"""CM1 passes the data-type conformance check (atmo3d.testing.check_datatype) on the
synthetic demo run."""
from atmo3d.testing import check_datatype


def test_check_cm1(demo_run):
    rep = check_datatype("cm1", demo_run)
    assert rep.ok and any(n.startswith("map of") for n in rep.notes)
    assert any(n.startswith("cross-section of") for n in rep.notes)
