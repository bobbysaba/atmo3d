"""Radar passes the data-type conformance check (atmo3d.testing.check_datatype) on the
synthetic volumes of tests/synthetic_radar.py."""
import synthetic_radar as S
from atmo3d.testing import check_datatype


def test_check_radar(tmp_path):
    S.write(str(tmp_path))
    rep = check_datatype("radar", str(tmp_path))
    assert any("sweep" in n for n in rep.notes)
