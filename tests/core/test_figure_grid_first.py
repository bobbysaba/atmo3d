"""The grid as the editor (docs-dev/figures-ui-plan.md, Phase 4; figures/ui/lines.py, gridfirst.py):
rows and columns picked like panels, their edits written to each of their panels; what the grid
varies; a panel's own changes and "Use the shared ones"; the layer chips; a panel added beside
others starting as a copy of them.  First without a viewer, then on the demo run."""

import copy

import pytest

from atmo3d.figures.schema import where as W
from atmo3d.figures.schema.where import Where
from atmo3d.figures.shell import docedit as de, nodes
from atmo3d.figures.ui import gridfirst, levels, lines, samples


def grid2x2():
    """Plan views a b / c d: rows are runs r0, r1; columns times 3600, 4800 s; they share a
    fill and contours; b changes the fill's colours."""
    base = samples.every_kind()
    doc = dict(base, grid=dict(rows=2, cols=2), annotations=[],
               panels=[dict(id=i, kind="plan", cell=[r, c, 1, 1], run=run, time_s=t,
                            layers=[dict(ref="l0", over={}), dict(ref="l1", over={})])
                       for i, (r, c, run, t) in enumerate([(0, 0, "r0", 3600.0),
                                                           (0, 1, "r0", 4800.0),
                                                           (1, 0, "r1", 3600.0),
                                                           (1, 1, "r1", 4800.0)])])
    doc["panels"][1]["layers"][0]["over"] = dict(cmap="Reds")
    return copy.deepcopy(doc)


# ------------------------------------------------------------ no viewer
def test_rows_and_columns_and_what_they_vary():
    doc = grid2x2()
    assert [p["id"] for p in lines.panels_in(doc, "row", 1)] == [2, 3]
    assert lines.members(doc, "col:1") == [1, 3]
    assert lines.varies(doc) == {"row": ["run"], "col": ["time"]}
    assert lines.label(doc, "row:1", ["run"]) == "B"
    assert lines.label(doc, "col:1", ["time"]) == "80 min"
    assert nodes.still_there(doc, "col:1") and not nodes.still_there(doc, "col:2")
    assert nodes.scope(doc, "col:1") == "Applies to column 2: panels b, d"
    assert nodes.outlined(doc, "row:0") == [0, 1]
    # (a panel of another kind in it: not reached, and said)
    doc["panels"][3]["kind"] = "xsec"
    assert lines.members(doc, "col:1") == [1] and "not d" in nodes.scope(doc, "col:1")


def test_the_switch_and_the_places_of_a_line():
    doc = grid2x2()
    assert levels.where_of(doc, "col:1") == Where("panel", "plan", 1)
    assert levels.spread(doc, "col:1") == [Where("panel", "plan", 1), Where("panel", "plan", 3)]
    assert levels.ladder(doc, "col:1")[-1] == ("Column 2 · b, d", "col:1")
    # (up to All plan views: the column stays offered, to go back down)
    assert levels.ladder(doc, "kind:plan", "col:1")[-1][1] == "col:1"


def test_the_headers_sit_over_their_panels():
    doc = grid2x2()
    boxes = {0: [0.0, 0.45, 0.0, 0.45], 1: [0.5, 0.95, 0.0, 0.45],
             2: [0.0, 0.45, 0.5, 0.95], 3: [0.5, 0.95, 0.5, 0.95]}
    hs = {h[0]: h for h in lines.heads(doc, boxes, picked="col:1")}
    assert set(hs) == {"row:0", "row:1", "col:0", "col:1"}
    assert hs["col:1"][1:] == ["80 min", 0.5, 0.95, "col", True]
    assert hs["row:1"][1:] == ["B", 0.5, 0.95, "row", False]
    one = dict(doc, grid=dict(rows=1, cols=2), panels=doc["panels"][:2])
    assert {h[0] for h in lines.heads(one, boxes)} == {"col:0", "col:1"}  # (no row headers)


def test_own_changes_and_use_the_shared_ones():
    doc = grid2x2()
    rows = gridfirst.look_rows(doc)
    assert lines.own_changes(doc, 0, None, rows) == []
    got = lines.own_changes(doc, 1, None, rows)
    assert [(how, j) for _, how, j in got] == [("over", 0)] and "cmap" in got[0][0]
    W.write(doc, next(r for r in rows(Where("panel", "plan", 1)) if r.id == "look.axes.xstep"),
            Where("panel", "plan", 1), 5.0)
    doc["panels"][1]["layers"].append(copy.deepcopy(samples.SHADE))
    hows = [how for _, how, _ in lines.own_changes(doc, 1, None, rows)]
    assert hows == ["over", "own", "look"]
    assert set(gridfirst.dots(doc, {0: [0, .4, 0, .4], 1: [.5, .9, 0, .4]})) == {"1"}
    lines.use_shared(doc, 1, rows)
    assert [how for _, how, _ in lines.own_changes(doc, 1, None, rows)] == ["own"]
    assert de.overrides(doc["panels"][1]["layers"][0]) == {}


def test_a_panel_added_beside_others_copies_them():
    """Decision 2: a new panel in a row starts as a copy of its neighbour there, with what the
    columns vary in taken from its own column."""
    doc = grid2x2()
    doc["grid"]["cols"] = 3
    doc["panels"][1]["time_s"] = 6000.0  # (b: a third time, so the columns read 60, 100)
    doc["panels"][3]["time_s"] = 6000.0
    gone = doc["panels"].pop(3)  # (d's cell empty)
    doc["panels"].append(dict(gone, id=7, cell=[0, 2, 1, 1], time_s=7200.0))  # (row 1, col 3)
    new = lines.copy_from(doc, "plan", (1, 1))
    assert new["cell"] == [1, 1, 1, 1] and new["run"] == "r1"  # (its row's run: c's)
    assert new["time_s"] == 6000.0  # (its column's time: b's)
    assert "title" not in new and new["id"] not in (0, 1, 2, 7)
    assert lines.copy_from(doc, "sounding", (1, 2)) is None  # (no sounding beside it)


# ------------------------------------------------------------ on the demo run
@pytest.fixture
def grid(two_plans):
    """two_plans (the New dialog's 2 × 3 plan views stepping in time, and one added) made a
    2 × 2 grid whose columns are at two times; its last panel removed and added again (a copy
    of the panels beside it)."""
    sh = two_plans
    times = list(sh.time_opts(0).values())

    def to_grid(d):
        keep = [p for p in d["panels"] if p["cell"][1] < 2]
        d["panels"] = keep
        d["grid"].update(rows=2, cols=2)
        for p in keep:
            p["time_s"] = times[2 + 4 * p["cell"][1]]
        de.letters_in_order(d)
    sh.edit(to_grid, node=nodes.FIGURE)
    last = nodes.in_order(sh.doc)[-1]["id"]
    sh.edit(lambda d: de.remove_panel(d, last), node=nodes.FIGURE)
    sh.grid.add_panel("plan", (1, 1))
    return sh


def test_rows_columns_and_new_panels_on_the_demo(grid):
    sh = grid
    doc = sh.doc
    assert de.grid_shape(doc) == (2, 2) and len(doc["panels"]) == 4
    assert lines.varies(doc)["col"] == ["time"]
    c, d = [p for p in nodes.in_order(doc)][2:]
    a, b = [p for p in nodes.in_order(doc)][:2]
    assert c["time_s"] == a["time_s"] and d["time_s"] == b["time_s"]


def test_a_header_click_picks_its_column(grid):
    sh = grid
    sh.image.head = ["col:1", 1]
    assert sh.node == "col:1"
    assert sh.frame.levels.buttons.value == "col:1"
    assert "column 2" in sh.frame.levels.said.object
    sh._boxes = {p["id"]: [0.1 * k, 0.1 * k + 0.05, 0.0, 0.4]
                 for k, p in enumerate(nodes.in_order(sh.doc))}
    sh._mark()
    lit = [h[0] for h in sh.image.heads if h[5]]
    assert lit == ["col:1"] and set(sh.image.marks) == {str(i) for i in
                                                         lines.members(sh.doc, "col:1")}


@pytest.mark.parametrize("tool", ["layout", "layers", "look", "marks", "times", "runs"])
def test_every_tool_shows_at_a_row_and_a_column(grid, tool):
    from conftest import at_tool, drawer_text
    for node in ("row:0", "col:1"):
        at_tool(grid, tool, node)
        assert grid.frame.body.objects, (tool, node)
        assert "Could not show" not in drawer_text(grid), (tool, node)


def test_a_column_edit_reaches_each_of_its_panels(grid):
    from conftest import at_tool, row_ctl
    sh = grid
    at_tool(sh, "look", "col:1")
    b, d = lines.members(sh.doc, "col:1")
    a, c = lines.members(sh.doc, "col:0")
    steps = len(sh._hist)
    ctl, back = row_ctl(sh, "look.axes.xstep")
    ctl.set(7.0)  # (as typed)
    row = next(r for d_ in sh.frame.drawers for s in d_.sections for r in s.rows
               if r.id == "look.axes.xstep")
    for pid in (b, d):
        assert W.value(sh.doc, row, Where("panel", "plan", pid)) == 7.0
    for pid in (a, c):
        assert not W.own(sh.doc, row, Where("panel", "plan", pid))
    assert len(sh._hist) == steps + 1  # (one undo step)
    at_tool(sh, "look", "col:1")
    ctl, back = row_ctl(sh, "look.axes.xstep")
    assert back.visible
    back.clicks += 1
    assert not any(W.own(sh.doc, row, Where("panel", "plan", pid)) for pid in (b, d))


def test_a_column_time_and_share(grid):
    import panel as pn
    from conftest import at_tool
    sh = grid
    times = list(sh.time_opts(0).values())
    at_tool(sh, "layout", "col:0")
    a, c = lines.members(sh.doc, "col:0")
    sel = next(w for w in sh.frame.body.select(pn.widgets.Select) if w.name == "Time")
    sel.value = times[1]
    assert de.panel_by_id(sh.doc, a)["time_s"] == de.panel_by_id(sh.doc, c)["time_s"] \
        == times[1]
    share = next(w for w in sh.frame.body.select(pn.widgets.FloatInput)
                 if w.name.startswith("Its share"))
    share.value = 2.0
    assert sh.doc["grid"]["widths"] == [2.0, 1.0]
    share.value = 1.0
    assert sh.doc["grid"]["widths"] == []


def test_what_the_grid_varies_in_the_layout(grid):
    import panel as pn
    from conftest import at_tool, drawer_text
    sh = grid
    at_tool(sh, "layout", "figure")
    said = drawer_text(sh)
    assert "Columns differ in</b>: Time" in said
    sels = [w for w in sh.frame.body.select(pn.widgets.Select)
            if w.name.startswith("Column ")]
    assert [w.name for w in sels] == ["Column 1: time", "Column 2: time"]
    times = list(sh.time_opts(0).values())
    sels[1].value = times[2]
    b, d = lines.members(sh.doc, "col:1")
    assert de.panel_by_id(sh.doc, d)["time_s"] == times[2]


def test_own_changes_listed_and_taken_back(grid):
    import panel as pn
    from conftest import at_tool, drawer_text, press
    sh = grid
    b, d = lines.members(sh.doc, "col:1")
    sh.edit(lambda doc: de.panel_by_id(doc, d)["layers"][0].setdefault("over", {}).update(
        cmap="Reds"))
    assert str(d) in gridfirst.dots(sh.doc, {d: [0, .5, 0, .5]})
    at_tool(sh, "layers", "col:1")
    assert "its own cmap" in drawer_text(sh)
    press(sh, "Use the shared ones")
    assert de.overrides(de.panel_by_id(sh.doc, d)["layers"][0]) == {}
    assert "None: they draw the shared layers" in drawer_text(sh)
    assert pn  # (imported for select)


def test_the_chips_open_a_shared_layer(grid):
    sh = grid
    fr = sh.frame
    lid = de.shared_ids(sh.doc, "plan")[0]
    fr.chips.show(sh.doc, sh.node)
    names = [b.name for b in fr.chips.row.objects[1:]]
    assert names[-1] == "+ Layer" and len(names) == len(de.shared_ids(sh.doc, "plan")) + 1
    fr.chips.row.objects[1].clicks += 1
    assert sh.node == "kind:plan" and fr.tool == "layers" and fr.folds[f"s:{lid}"]
