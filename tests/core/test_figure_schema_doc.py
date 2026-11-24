"""The document's own rows of the settings schema (figures/schema/doc.py,
docs-dev/figures-ui-plan.md Phase 2.1c): the figure's, a run's, a panel's, an inset's, a section's and an annotation's
settings, read where they are and written as the old editor wrote them (through docedit where it
has a change of its own), and shown under the old cards' conditions.  That nothing the old editor
offered is lost: test_figure_inventory.py.  No viewer needed."""

import pytest

from atmo3d.figures import schema as S
from atmo3d.figures.schema import where as W
from atmo3d.figures.schema.where import Where
from atmo3d.figures.shell import docedit as de
from atmo3d.figures.spec.sections import section_defaults


def _doc():
    return dict(
        version=3, size=[8.0, 3.0], size_auto=True, grid=dict(rows=1, cols=2),
        runs=[dict(id="r0", path="/a", label="one"), dict(id="r1", path="/b")],
        style={}, kinds={}, layers={},
        sections=dict(s0=section_defaults(orient="x", pos="storm")),
        panels=[dict(id=0, kind="plan", cell=[0, 0, 1, 1], run="r0", time_s=60.0, layers=[],
                     insets=[dict(id=5, loc="upper right", size=0.4)]),
                dict(id=1, kind="xsec", cell=[0, 1, 1, 1], run="r0", time_s=60.0, layers=[],
                     section="s0")],
        annotations=[dict(kind="text", panel=-1, coords="axes", x=0.5, y=0.5, text="A")])


DOC_ROWS = [r for r in S.ROWS if W.is_doc(r)]


def test_document_rows_are_well_formed():
    assert len(DOC_ROWS) > 60
    for r in DOC_ROWS:
        assert r.label and r.section, r.id
        assert set(r.levels) <= set(S.LEVELS) and r.kinds, r.id
        assert not r.writer or r.writer in W.WRITERS, r.id
        if r.control.kind in ("choice", "multi"):
            assert r.control.options, r.id
        assert not S.when_problems(r), (r.id, S.when_problems(r))


def test_the_figures_own_settings():
    doc = _doc()
    W.write(doc, S.row("suptitle"), W.FIGURE, "  Storms ")
    W.write(doc, S.row("size"), W.FIGURE, [6.5, 4.0])
    assert doc["suptitle"] == "Storms" and doc["size"] == [6.5, 4.0] and not doc["size_auto"]
    fit = S.row("export.fit")
    assert W.value(doc, fit, W.FIGURE) == "trim"
    W.write(doc, fit, W.FIGURE, "width")
    assert doc["export"] == dict(tight=True, exact_width=True)
    assert S.offered(S.row("export.pad"), doc, W.FIGURE)
    W.write(doc, fit, W.FIGURE, "full")
    assert not S.offered(S.row("export.pad"), doc, W.FIGURE)
    W.write(doc, S.row("export.dpi"), W.FIGURE, None)
    assert doc["export"]["dpi"] == 250
    W.write(doc, S.row("code.on"), W.FIGURE, True)
    assert doc["code"] == dict(on=True)


def test_the_grid_is_written_through_docedit():
    doc, want = _doc(), _doc()
    W.write(doc, S.row("grid.rows"), W.FIGURE, 2)
    de.set_grid(want, 2, 2)
    assert doc == want
    W.write(doc, S.row("grid.widths"), W.FIGURE, "2, 1")
    de.set_shares(want, "widths", [2.0, 1.0])
    assert doc == want and W.value(doc, S.row("grid.widths"), W.FIGURE) == "2, 1"
    with pytest.raises(ValueError):
        W.write(doc, S.row("grid.widths"), W.FIGURE, "1, 2, 3")


def test_a_runs_settings():
    doc, want = _doc(), _doc()
    at = Where("figure", item="r1")
    W.write(doc, S.row("runs[].t0_min"), at, 10.0)
    de.set_t0(want, "r1", 10.0)
    assert doc == want
    W.write(doc, S.row("runs[].label"), at, "two")
    assert doc["runs"][1]["label"] == "two"
    assert W.value(doc, S.row("runs[].label"), Where("figure", item="r0")) == "one"
    with pytest.raises(IndexError):
        W.write(doc, S.row("runs[].label"), Where("figure", item="gone"), "x")


def test_a_panels_settings():
    doc, want = _doc(), _doc()
    p0 = Where("panel", "plan", 0)
    W.write(doc, S.row("panels[].z"), p0, 2.0)
    de.set_height(want, de.panel_by_id(want, 0), 2.0, "height")
    assert doc == want
    W.write(doc, S.row("panels[].colorbar.show"), p0, False)
    de.set_panel_colorbar(want, 0, show=False)
    assert doc == want and W.value(doc, S.row("panels[].colorbar.show"), p0) is False
    W.write(doc, S.row("panels[].rowlabel"), p0, "  ")
    assert "rowlabel" not in doc["panels"][0]
    W.write(doc, S.row("panels[].run"), p0, "r1")
    assert doc["panels"][0]["run"] == "r1" and doc["panels"][0]["time_s"] == 60.0
    assert not S.offered(S.row("panels[].section"), doc, Where("panel", "xsec", 1))
    assert not S.offered(S.row("panels[].z"), doc, Where("panel", "xsec", 1))


def test_an_insets_settings():
    doc = _doc()
    at = Where("inset", "plan", 0, 5)
    assert not S.offered(S.row("insets[].x"), doc, at)
    W.write(doc, S.row("insets[].loc"), at, "custom")
    assert S.offered(S.row("insets[].x"), doc, at)
    assert W.value(doc, S.row("insets[].mark"), at) is True  # (a new inset's)
    W.write(doc, S.row("insets[].h"), at, 0.3)
    W.write(doc, S.row("insets[].h"), at, None)
    assert "h" not in doc["panels"][0]["insets"][0]


def test_a_section_is_written_through_docedit_and_shows_what_its_orientation_uses():
    doc, want = _doc(), _doc()
    at = Where("panel", "xsec", 1)  # (the panel's section)
    half = S.row("sections[].half")
    assert S.offered(half, doc, at) and not S.offered(S.row("sections[].x0"), doc, at)
    W.write(doc, half, at, 12.0)
    de.write_section(want, "s0", dict(half=12.0))
    assert doc == want
    W.write(doc, S.row("sections[].pos"), Where("kind", "xsec", item="s0"), "fixed")
    assert S.offered(S.row("sections[].x0"), doc, at) and not S.offered(half, doc, at)


def test_an_annotation_shows_what_its_kind_uses():
    doc = _doc()
    at = Where("figure", item=0)
    off = {r.key.rpartition(".")[2] for r in DOC_ROWS
           if r.key.startswith("annotations[]") and not S.offered(r, doc, at)}
    assert off == {"x2", "y2", "r", "lw", "ls", "marker", "look", "alpha"}
    W.write(doc, S.row("annotations[].kind"), at, "legend")
    W.write(doc, S.row("annotations[].look"), at, "marker")
    assert S.offered(S.row("annotations[].marker"), doc, at)
    assert not S.offered(S.row("annotations[].ls"), doc, at)
    W.write(doc, S.row("annotations[].panel"), at, "a, c-d")
    assert doc["annotations"][0]["panel"] == [0, 2, 3]
    assert W.value(doc, S.row("annotations[].panel"), at) == "a, c-d"
