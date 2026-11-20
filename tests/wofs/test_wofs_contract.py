"""WoFS passes the data-type conformance check (atmo3d.testing.check_datatype) on the
synthetic run of tests/synthetic_wofs.py."""
import os

from atmo3d.testing import check_datatype
from synthetic_wofs import make_wofs


def test_check_wofs(tmp_path):
    exp = os.path.dirname(make_wofs(str(tmp_path / "exp" / "20220523")))
    rep = check_datatype("wofs", exp)
    assert any("parts" in n for n in rep.notes)  # (members and mean)
