"""A figure of a WoFS run as it is written today (CM1-style field names), kept as a
fixture for Phase 2.4 of the atmo3d plan: when WoFS fields become WRF names, an old file
like this one must still open, its names mapped through an explicit table.

Until then this records that the file names the fields it does, and survives a JSON trip."""
import json
import os

from atmo3d.figures import draw as figdraw, spec as fg
from atmo3d.registry import Registry
from test_wofs import make_wofs


def test_wofs_figure_document_names_cm1_style_fields(tmp_path):
    root = make_wofs(str(tmp_path / "exp" / "20220523"))
    run, F = Registry(os.path.dirname(root), 4, 2).get()
    doc = fg.to_doc(fg.default_spec(run, F))
    again = json.loads(json.dumps(doc))
    v3, _ = figdraw.upgrade(again)
    assert v3["version"] == 3 or v3["version"] == 2
    text = json.dumps(again)
    for name in ("winterp",):
        assert name in text or name not in F
