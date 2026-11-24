"""The figure editor's settings inventory (docs-dev/figures-ui-plan.md, Phase 0), checked against
the settings schema (Phase 2.4): nothing the old editor offered goes missing.

Each part (a kind of figure, and the Export and New dialogs) was collected from the old editor
with the document keys each control writes, into tests/core/figure_inventory/<part>.json.  Every
key a control wrote is a schema row at that control's level, for its kind and layer type; every
control that wrote none is a row of its label, or a tool or dialog setting the new shell offers
(figure_inventory.OFFERED_AS, Phase 3's checklist).  No viewer needed.

The old editor is gone (Phase 3.3): the stored parts are final.
`python tests/core/figure_inventory.py` writes docs-dev/figures-inventory.md from them."""

import pytest

import figure_inventory as fi


@pytest.mark.parametrize("name", fi.PARTS)
def test_no_setting_goes_missing(name):
    recs = fi.load_part(name)["records"]
    assert len(recs) > 20
    gaps = fi.schema_gaps(recs)
    assert not gaps, f"{name}: {len(gaps)} settings the schema does not offer: {gaps[:20]}"


def test_the_check_finds_a_setting_gone(monkeypatch):
    from atmo3d.figures import schema as S
    recs = fi.load_part("plan")["records"]
    assert not fi.schema_gaps(recs)
    gone = ("look.axes.xstep", ("layer.clabel", "contour"))
    monkeypatch.setattr(S, "BY_KEY", {k: r for k, r in S.BY_KEY.items() if k != gone[0]})
    monkeypatch.setattr(S, "_OF_TYPE", {k: r for k, r in S._OF_TYPE.items() if k != gone[1]})
    monkeypatch.setattr(S, "ROWS", tuple(r for r in S.ROWS if r.key not in
                                         (gone[0], gone[1][0])))
    gaps = dict(fi.schema_gaps(recs))
    assert gaps.get("look.axes.xstep") == "no row" and gaps.get("layer.clabel") == "no row"
