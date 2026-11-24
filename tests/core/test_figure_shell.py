"""The figure editor's layout (figures/shell, figures/ui): the nodes of a document, picking them
in the level switch and the preview, edits, undo, the Runs tool."""
import pytest

from conftest import at_tool, control, drawer_text, every_node, fresh_shell

from atmo3d.figures.shell import nodes


def small_doc():
    fill = dict(type="fill", field="dbz", run=None)
    return dict(
        version=3, size=[8.0, 6.0], grid=dict(rows=1, cols=3), style={}, kinds={}, sections={},
        runs=[dict(id="r0", path="/x/one"), dict(id="r1", path="/x/two", label="Two"),
              dict(id="r2", path="/x/three")],
        layers={"l0": fill},
        panels=[
            dict(id=7, kind="sounding", cell=[0, 2, 1, 1], run=None, time_s=None, title="",
                 layers=[dict(type="sounding", label="Inflow", run="r0")]),
            dict(id=0, kind="plan", cell=[0, 0, 1, 1], run="r0", time_s=600.0, title="Early",
                 layers=[dict(ref="l0", over=dict(field="w"))]),
            dict(id=1, kind="plan", cell=[0, 1, 1, 1], run="r1", time_s=1200.0, title="",
                 layers=[dict(ref="l0", over={})], letter=25)])


def test_the_places_of_a_figure_in_words():
    from atmo3d.figures import draw as figdraw
    doc = small_doc()
    assert every_node(doc) == ["figure", "runs", "kind:plan", "panel:0", "layer:0:0", "panel:1",
                               "layer:1:0", "kind:sounding", "panel:7", "layer:7:0"]
    assert nodes.kind_name("plan", 2) == "plan views (2)"
    lays = {p["id"]: figdraw.panel_layers(doc, p)[0][1] for p in doc["panels"]}
    assert nodes.layer_name(lays[0]) == "Fill · w"  # (what differs in this panel)
    assert nodes.layer_name(lays[7]) == "Sounding · Inflow"


def test_letters_follow_the_reading_order_not_the_list():
    assert nodes.letters(small_doc()) == {0: "a", 1: "z", 7: "c"}


def test_what_a_node_speaks_for():
    doc = small_doc()
    assert nodes.outlined(doc, "figure") == nodes.outlined(doc, "runs") == []
    assert sorted(nodes.outlined(doc, "kind:plan")) == [0, 1]
    assert nodes.outlined(doc, "panel:7") == nodes.outlined(doc, "layer:7:0") == [7]
    assert nodes.scope(doc, "kind:plan") == "Applies to all plan views (2)"
    assert nodes.scope(doc, "panel:0") == "Applies to panel a only"
    assert nodes.scope(doc, "layer:1:0") == "Applies to panel z only"
    assert nodes.scope(doc, "figure") == "Applies to the whole figure"


@pytest.mark.parametrize("node, there", [
    ("figure", True), ("runs", True), ("kind:plan", True), ("kind:th", False), ("panel:7", True),
    ("panel:8", False), ("layer:0:0", True), ("layer:0:1", False), ("layer:8:0", False)])
def test_still_there(node, there):
    assert nodes.still_there(small_doc(), node) is there


def test_runs_used_by_panels_and_their_layers():
    doc = small_doc()
    doc["panels"][2]["layers"][0]["over"] = dict(minus=dict(run="r2"))
    assert nodes.runs_used(doc) == {"r0": [7, 0], "r1": [1], "r2": [1]}


def test_pick_at():
    boxes = {3: [0.0, 0.4, 0.0, 1.0], 4: [0.6, 1.0, 0.0, 1.0]}
    assert nodes.pick_at(boxes, 0.2, 0.5) == 3
    assert nodes.pick_at(boxes, 0.7, 0.5) == 4
    assert nodes.pick_at(boxes, 0.5, 0.5) is None  # (between them)


def test_grid_map_shows_spans_and_empty_cells():
    from atmo3d.figures.ui.grid import grid_map
    doc = small_doc()
    doc["grid"] = dict(rows=2, cols=3)
    doc["panels"][1]["cell"] = [0, 0, 2, 1]
    text = grid_map(doc).object
    assert 'rowspan="2"' in text
    assert text.count("<tr>") == 2
    assert text.count("<td") == 5 and text.count(">·<") == 2  # (a spans two rows; two empty)


def test_a_preview_doc_only_touches_a_scene():
    from atmo3d.figures.shell.frame import preview_doc, preview_dpi
    doc = small_doc()
    assert preview_doc(doc, 100.0) is doc
    doc["kinds"] = dict(scene=dict(scene3d=dict(zoom=1.0)))
    out = preview_doc(doc, 100.0)
    assert out["kinds"]["scene"]["scene3d"] == dict(zoom=1.0, dpi=100.0)
    assert doc["kinds"]["scene"]["scene3d"] == dict(zoom=1.0)
    assert preview_dpi(dict(size=[8.0, 6.0], export=dict(dpi=100))) == 100.0
    assert preview_dpi(dict(size=[1.0, 1.0], export=dict(dpi=2000))) == 1100.0


# ------------------------------------------------------------------ on the demo run


@pytest.fixture
def shell(shell_viewer):
    """The new layout showing the demo's example figure, drawing as it is asked (not in the
    background)."""
    return fresh_shell(shell_viewer)


def _new_figure(shell, kind):
    ed = shell.ed
    ed.open_quick()
    ed.qs_kind.value = kind
    ed._quick_make()


def test_open_shows_the_figure_there(shell):
    assert shell.showing and shell.panel.visible
    assert shell.doc["version"] == 3
    assert shell.image.src.startswith("data:image/png")
    assert "6 panels" in shell.status.object
    assert set(shell._boxes) == {p["id"] for p in shell.doc["panels"]}
    assert shell.node == "figure" and shell.image.marks == {}


def test_a_click_in_the_preview_picks_the_panel(shell):
    x0, x1, y0, y1 = shell._boxes[4]
    shell.image.click = [0.5 * (x0 + x1), 0.5 * (y0 + y1), 1]
    assert shell.node == "panel:4"
    assert shell.image.marks == {"4": shell._boxes[4]}
    assert "panel e only" in shell.frame.levels.said.object
    shell.image.click = [0.0, 0.999, 2]  # (off every panel: the figure)
    assert shell.node == "figure" and shell.image.marks == {}


def test_picking_a_node_outlines_its_panels(shell):
    shell.frame.pick("kind:plan")
    assert shell.node == "kind:plan" and len(shell.image.marks) == 6
    shell.frame.pick("runs")
    assert shell.image.marks == {}


def test_every_node_shows(shell):
    for node in every_node(shell.doc):
        at_tool(shell, "layout", node)
        assert shell.frame.body.objects, node
        assert "Could not show" not in drawer_text(shell), node


def test_edits_undo_and_redo_with_what_was_picked(shell):
    from conftest import control
    control(shell, "Title", "layout", "panel:1").value = " North "
    pan = next(p for p in shell.doc["panels"] if p["id"] == 1)
    assert pan["title"] == "North"
    assert not shell.undo_btn.disabled and shell.redo_btn.disabled
    shell.select("figure")
    shell.undo()
    assert next(p for p in shell.doc["panels"] if p["id"] == 1)["title"] == ""
    assert shell.node == "panel:1"  # (where the edit was made)
    assert shell.undo_btn.disabled and not shell.redo_btn.disabled
    assert control(shell, "Title", "layout").value == ""
    shell.redo()
    assert next(p for p in shell.doc["panels"] if p["id"] == 1)["title"] == "North"
    assert control(shell, "Title", "layout").value == "North"


def test_figure_size_and_title(shell):
    control(shell, "Width (in)", "layout", "figure").value = 5.0
    assert shell.doc["size"][0] == 5.0 and shell.doc["size_auto"] is False
    control(shell, "Figure title").value = "Storm"
    assert shell.doc["suptitle"] == "Storm"
    assert shell._png[1][0] / shell._png[2] < 5.5  # (drawn at that width)


def test_the_runs_tool(shell):
    control(shell, "Label", "runs").value = "Control"
    assert shell.doc["runs"][0]["label"] == "Control"
    control(shell, "Time zero (min)").value = 5.0
    assert shell.doc["runs"][0]["t0_min"] == 5.0
    rm = next(w for w in shell.frame.body.select() if getattr(w, "name", "") == "✕")
    assert rm.disabled  # (in use, and the only one)
    assert "outputs" in drawer_text(shell)  # (what the run holds)


def test_add_and_remove_a_run(shell, demo_run):
    import os
    other = os.path.join(os.path.dirname(demo_run), "supercell_weak")
    at_tool(shell, "runs", "runs")
    shell.add_run(other, node="runs")
    assert [r["path"] for r in shell.doc["runs"]][-1] == other
    assert len(shell.doc["runs"]) == 2
    assert shell.node == "runs"
    at_tool(shell, "runs")
    rms = [w for w in shell.frame.body.select() if getattr(w, "name", "") == "✕"]
    assert [b.disabled for b in rms] == [True, False]  # (the first in use)
    rms[1].clicks += 1
    assert len(shell.doc["runs"]) == 1


def test_leaving_the_workspace_and_returning_keeps_the_edits(shell):
    shell.edit(lambda d: d.update(suptitle="Kept"))
    shell.open()
    assert shell.doc["suptitle"] == "Kept"


def test_what_the_data_asks_of_the_editor_reaches_the_shell(shell):
    gen = shell.v.gen["fig"]
    shell.ed.request(force=True, delay=False)  # (a series coming in)
    assert shell.v.gen["fig"] == gen + 1
    shell.ed._status("from the data")
    assert "from the data" in shell.status.object


def test_live_off_waits_for_redraw(shell):
    shell.auto.value = False
    src = shell.image.src
    shell.edit(lambda d: d.update(suptitle="Later"))
    assert shell.image.src == src
    shell.update.clicks += 1
    assert shell.image.src != src


def test_panel_boxes_are_the_panels_places_in_the_image(shell):
    b = shell._boxes
    assert all(0.0 <= x[0] < x[1] <= 1.0 and 0.0 <= x[2] < x[3] <= 1.0 for x in b.values())
    assert b[0][1] < b[1][0] < b[1][1] < b[2][0]  # (a b c, left to right)
    assert b[0][3] < b[3][2]  # (d under a)
    assert abs(b[0][0] - b[3][0]) < 1e-6


def test_every_kind_opens_and_every_node_shows(shell):
    for kind in ("xsec", "sounding", "profile", "dist", "joint", "azim", "table", "line", "th"):
        _new_figure(shell, kind)
        assert shell.doc["panels"] or kind == "th", kind
        assert "Could not draw" not in shell.status.object, kind
        for tool in ("layout", "layers", "look", "times"):
            for node in every_node(shell.doc):
                at_tool(shell, tool, node)
                assert shell.frame.body.objects, (kind, tool, node)
                assert "Could not show" not in drawer_text(shell), (kind, tool, node)
