"""The new Figure workspace's frame (figures/ui/frame.py, docs-dev/figures-ui-plan.md Phase 3.1-3.3):
the level switch (levels.py) and which tool shows a setting (tools.py) without a viewer; then on
the demo run, a figure of two plan views: every tool at every level shows, the switch follows
what is picked, and an edit in a drawer reaches the panels it says, with undo."""

import pytest

from atmo3d.figures import draw as figdraw, schema as S
from atmo3d.figures.schema import where as W
from atmo3d.figures.schema.where import Where
from atmo3d.figures.shell import docedit as de
from atmo3d.figures.ui import levels, samples, tools


# ------------------------------------------------------------ no viewer
def test_where_of_each_node():
    doc = samples.every_kind()
    assert levels.where_of(doc, "figure") == Where()
    assert levels.where_of(doc, "runs") == Where()
    assert levels.where_of(doc, "kind:plan") == Where("kind", "plan")
    assert levels.where_of(doc, "panel:2") == Where("panel", "xsec", 2)
    assert levels.where_of(doc, "inset:0:7") == Where("inset", "plan", 0, 7)
    assert levels.where_of(doc, "layer:1:0") == Where("panel", "plan", 1, layer=0)


def test_the_ladder_keeps_the_last_panel():
    doc = samples.every_kind()
    top = levels.ladder(doc, "figure")
    assert top[0] == ("Figure", "figure")
    kinds = [n for _, n in top[1:]]
    assert kinds[:3] == ["kind:plan", "kind:xsec", "kind:th"] and len(kinds) == 11
    low = levels.ladder(doc, "layer:0:0")
    assert [n for _, n in low[-2:]] == ["panel:0", "layer:0:0"]
    assert low[-1][0].startswith("Layer: ")
    # (up to All plan views: the panel and its layer stay offered, to go back down)
    assert levels.ladder(doc, "kind:plan", "layer:0:0")[-2:] == low[-2:]
    assert levels.ladder(doc, "inset:0:7")[-1] == ("Inset 1", "inset:0:7")
    gone = dict(doc, panels=[p for p in doc["panels"] if p["id"] != 0])
    assert levels.ladder(gone, "figure", "layer:0:0")[-1][1].startswith("kind:")


def test_every_setting_is_in_one_tool():
    """Each schema row is shown by one tool, or the Export dialog's; layers' in Layers."""
    for r in S.ROWS:
        t = tools.tool_of(r)
        assert t in tools.TITLES or (t is None and r.section in tools.ELSEWHERE), r.id
        if r.types:
            assert t == "layers", r.id
    assert tools.tool_of(S.BY_KEY["panels[].time_s"]) == "times"
    assert tools.tool_of(S.BY_KEY["size"]) == "layout"


def _plan_places(doc):
    out = [Where(), Where("kind", "plan")]
    for p in doc["panels"]:
        if p["kind"] != "plan":
            continue
        out.append(Where("panel", "plan", p["id"]))
        out += [Where("inset", "plan", p["id"], i["id"]) for i in p.get("insets") or []]
    return out


def test_the_tools_offer_every_plan_view_setting():
    """Nothing lost (plan views): every row of a plan view's places, but the Export dialog's, is
    in the tool its section says, at that place (layers: at each layer's)."""
    doc = samples.every_kind()
    from atmo3d.figures.ui import drawer as D
    for where in _plan_places(doc):
        shown = set()
        for t in tools.TITLES:
            shown |= {r.id for r in tools.rows_for(doc, where, t)}
        want = {r.id for r in D.rows_at(doc, where) if tools.tool_of(r) is not None}
        assert want <= shown, (where, want - shown)
    p = de.panel_by_id(doc, 0)
    for j, _ in enumerate(figdraw.panel_layers(doc, p)):
        w = Where("panel", "plan", 0, layer=j)
        assert D.rows_at(doc, w) and all(tools.tool_of(r) == "layers"
                                         for r in D.rows_at(doc, w))


# ------------------------------------------------------------ on the demo run
def _texts(obj):
    import panel as pn
    out = []
    for o in obj.select(pn.pane.HTML):
        out.append(str(o.object or ""))
    return " ".join(out)


def _two(doc):
    """The first two panels, in reading order."""
    from atmo3d.figures.shell import nodes
    return [p["id"] for p in nodes.in_order(doc)][:2]


def _open_all(obj):
    import panel as pn
    for c in obj.select(pn.Card):
        c.collapsed = False


NODES = ("figure", "kind:plan", "panel:{a}", "layer:{a}:0", "panel:{b}")


@pytest.mark.parametrize("tool", [k for k, *_ in tools.TOOLS])
def test_every_tool_shows_at_every_level(two_plans, tool):
    sh = two_plans
    fr = sh.frame
    assert sh.panel is fr.panel
    a, b = _two(sh.doc)
    if fr.tool != tool:
        fr.open_tool(tool)
    for node in NODES:
        sh.select(node.format(a=a, b=b))
        _open_all(fr.body)
        said = _texts(fr.body)
        assert "Could not show" not in said, (tool, node, said)
        assert fr.body.objects, (tool, node)
    assert fr.levels.buttons.value == f"panel:{b}"


def test_the_switch_follows_the_pick(two_plans):
    sh = two_plans
    a, b = _two(sh.doc)
    sh.select(f"layer:{a}:0")
    opts = sh.frame.levels.buttons.options
    assert list(opts.values())[:2] == ["figure", "kind:plan"]
    assert sh.frame.levels.buttons.value == f"layer:{a}:0"
    sh.frame.levels.buttons.value = "kind:plan"  # (a click on All plan views)
    assert sh.node == "kind:plan"
    assert f"layer:{a}:0" in sh.frame.levels.buttons.options.values()  # (back down: one click)
    assert "All plan views" in sh.frame.levels.said.object or "plan" in \
        sh.frame.levels.said.object


def _control(fr, row_id):
    for d in fr.drawers:
        for s in d.sections:
            if row_id in {r.id for r in s.rows}:
                s.card.collapsed = False
                return s.ctls[row_id]
    raise KeyError(row_id)


def test_a_shared_layer_edit_reaches_both_panels(two_plans):
    sh = two_plans
    fr = sh.frame
    fr.open_tool("layers") if fr.tool != "layers" else None
    sh.select("kind:plan")
    _open_all(fr.body)
    lid = de.shared_ids(sh.doc, "plan")[0]
    lay = dict(sh.doc["layers"][lid])
    assert lay["type"] == "fill"
    steps = len(sh._hist)
    _control(fr, "layer.vmax~fill").widget.value = 47.0
    assert sh.doc["layers"][lid]["vmax"] == 47.0
    for p in sh.doc["panels"]:
        assert W.layer_at(sh.doc, Where("panel", "plan", p["id"], layer=0))["vmax"] == 47.0
    assert len(sh._hist) == steps + 1
    sh.undo()
    assert sh.doc["layers"][lid]["vmax"] == lay["vmax"]


def test_a_panel_edit_stays_in_the_panel(two_plans):
    sh = two_plans
    fr = sh.frame
    a, b = _two(sh.doc)
    fr.open_tool("layers") if fr.tool != "layers" else None
    sh.select(f"layer:{a}:0")
    _open_all(fr.body)
    lid = de.shared_ids(sh.doc, "plan")[0]
    was = sh.doc["layers"][lid]["mask_below"]
    _control(fr, "layer.mask_below").widget.value = 15.0
    assert W.layer_at(sh.doc, Where("panel", "plan", a, layer=0))["mask_below"] == 15.0
    assert W.layer_at(sh.doc, Where("panel", "plan", b, layer=0))["mask_below"] == was
    assert sh.doc["layers"][lid]["mask_below"] == was
    # (it says so on the panel's list, and the shared settings take it back)
    sh.select(f"panel:{a}")
    first = fr.body.objects[2]
    assert "changed here" in first.title
    first.collapsed = False
    import panel as pn
    back = next(w for w in first.select(pn.widgets.Button) if "Use the shared" in w.name)
    back.clicks += 1
    assert W.layer_at(sh.doc, Where("panel", "plan", a, layer=0))["mask_below"] == was


def test_a_panel_colour_range_follows_its_shared_bar(two_plans):
    """A panel's colours changed under a shared colorbar: the panels sharing the bar follow (as
    the old editor did: shell/bars.py), the shared layer itself stays."""
    sh = two_plans
    a, b = _two(sh.doc)
    sh.frame.open_tool("layers") if sh.frame.tool != "layers" else None
    sh.select(f"layer:{a}:0")
    _open_all(sh.frame.body)
    lid = de.shared_ids(sh.doc, "plan")[0]
    was = sh.doc["layers"][lid]["vmax"]
    _control(sh.frame, "layer.vmax~fill").widget.value = 33.0
    for pid in (a, b):
        assert W.layer_at(sh.doc, Where("panel", "plan", pid, layer=0))["vmax"] == 33.0
    assert sh.doc["layers"][lid]["vmax"] == was


def test_adding_a_shared_layer(two_plans):
    sh = two_plans
    fr = sh.frame
    fr.open_tool("layers") if fr.tool != "layers" else None
    sh.select("kind:plan")
    n = len(de.shared_ids(sh.doc, "plan"))
    import panel as pn
    menu = next(w for w in fr.body.select(pn.widgets.MenuButton) if "Add a layer" in w.name)
    menu.clicked = "contour"
    ids = de.shared_ids(sh.doc, "plan")
    assert len(ids) == n + 1 and sh.doc["layers"][ids[-1]]["type"] == "contour"
    assert all(de.draws(sh.doc, p, ids[-1]) for p in sh.doc["panels"])
    assert fr.folds.get(f"s:{ids[-1]}")  # (open, to change it)


def test_look_at_a_panel_writes_its_own(two_plans):
    sh = two_plans
    fr = sh.frame
    a, b = _two(sh.doc)
    fr.open_tool("look") if fr.tool != "look" else None
    sh.select(f"panel:{a}")
    rows = tools.rows_for(sh.doc, Where("panel", "plan", a), "look")
    row = next(r for r in rows if r.control.kind == "toggle")
    _open_all(fr.body)
    ctl = _control(fr, row.id)
    now = bool(ctl.get())
    ctl.widget.value = not now
    assert W.own(sh.doc, row, Where("panel", "plan", a))
    assert not W.own(sh.doc, row, Where("panel", "plan", b))


def test_the_rail_closes_its_drawer(two_plans):
    fr = two_plans.frame
    fr.open_tool("marks") if fr.tool != "marks" else None
    assert fr.side.visible and fr.rail_btns["marks"].css_classes == ["cv-on"]
    fr.open_tool("marks")
    assert not fr.side.visible and fr.tool is None
    fr.open_tool("layout")
    assert fr.side.visible and fr.tool == "layout"


def test_marks_adds_an_annotation_open(two_plans):
    import panel as pn
    sh = two_plans
    fr = sh.frame
    fr.open_tool("marks") if fr.tool != "marks" else None
    sh.select("figure")
    n = len(sh.doc.get("annotations") or [])
    add = next(w for w in fr.body.select(pn.widgets.Button) if w.name == "+ Add")
    add.clicks += 1
    assert len(sh.doc["annotations"]) == n + 1
    card = next(c for c in fr.body.objects if isinstance(c, pn.Card) and
                c.title.startswith(f"{n + 1}. "))
    assert not card.collapsed and fr.drawers
