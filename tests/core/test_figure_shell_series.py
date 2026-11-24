"""Cross-sections, time-height panels and time series in the figure editor's new layout: sections
as shared geometry, a new cross-section, one per run, a time-height panel's run, hand edits when a
run goes, automatic sizes, the look rows of these kinds, and the panes driven by their widgets."""
import copy
import time

import pytest

from conftest import at_tool, control, drawer_text, every_node, fresh_shell, press

from atmo3d.figures import spec as fg
from atmo3d.figures.shell import docedit as de, nodes
from atmo3d.figures.ui.grid import ADDABLE


def series(run="r0", **more):
    return dict(type="series", on=True, recipe=dict(field="w"), runs=[run], label="w", **more)


def section_doc():
    """A plan view with a section line, in a figure of two runs."""
    return dict(
        version=3, size=[9.0, 3.0], grid=dict(rows=1, cols=3),
        style=dict(letters=dict(on=True, auto=True)), kinds=dict(plan=dict(axes={})),
        runs=[dict(id="r0", path="/x/one"), dict(id="r1", path="/x/two", label="Two")],
        sections=dict(s0=dict(label="", orient="x", pos="storm", half=10.0)),
        layers=dict(l0=dict(type="fill", on=True, field="dbz"), l1=dict(type="line", on=True)),
        panels=[dict(id=0, kind="plan", cell=[0, 0, 1, 1], run="r0", time_s=600.0, title="",
                     section="s0", layers=[dict(ref="l0", over={}), dict(ref="l1", over={})])])


def series_doc(kind="th", layers=None):
    doc = section_doc()
    doc["panels"] = [dict(id=0, kind=kind, cell=[0, 0, 1, 1], run=None, time_s=None, title="",
                          layers=list(layers or []))]
    doc["grid"] = dict(rows=1, cols=1)
    return doc


# ------------------------------------------------------------------ a new cross-section
def test_the_first_cross_section_takes_after_the_last_plan_view():
    doc = section_doc()
    p = de.xsec_panel(doc, (0, 1), "r1", 1.0)
    assert (p["run"], p["time_s"], p["section"]) == ("r0", 600.0, "s0")
    assert [x["ref"] for x in p["layers"]] == ["l0"]  # (a section draws no section line)


def test_the_first_cross_section_of_a_figure_with_no_map_brings_what_it_needs():
    doc = series_doc("line")
    doc.update(layers={}, sections={})
    p = de.xsec_panel(doc, (0, 1), "r1", 60.0, [dict(type="fill", field="dbz")],
                      dict(orient="y", run=0, time_s=None, panel=3))
    assert (p["run"], p["time_s"]) == ("r1", 60.0)
    assert list(doc["sections"]) == [p["section"]] and doc["sections"][p["section"]] == dict(orient="y")
    assert [x["ref"] for x in p["layers"]] == list(doc["layers"])


def test_the_next_cross_section_is_like_the_last_with_a_twin_section():
    doc = section_doc()
    a = de.xsec_panel(doc, (0, 1), "r0", 1.0)
    b = de.xsec_panel(doc, (0, 2), "r0", 1.0)
    assert b["section"] != a["section"] and doc["sections"][b["section"]]["orient"] == "y"
    assert b["layers"] == a["layers"] and b["run"] == a["run"]


# ------------------------------------------------------------------ sections
def test_a_section_shared_by_panels_can_be_kept_apart():
    doc = section_doc()
    a = de.xsec_panel(doc, (0, 1), "r0", 1.0)
    b = de.copy_panel(doc, a["id"], (0, 2))
    assert [p["id"] for p in de.section_panels(doc, "s0")] == [a["id"], b["id"]]
    sid = de.split_section(doc, b["id"])
    assert sid != "s0" and doc["sections"][sid] == doc["sections"]["s0"]
    de.write_section(doc, sid, dict(half=3.0))
    assert doc["sections"]["s0"]["half"] == 10.0  # (its own now)


def test_a_section_goes_only_when_no_cross_section_shows_it():
    doc = section_doc()
    assert "keeps one" in de.remove_section(doc, "s0")
    de.xsec_panel(doc, (0, 1), "r0", 1.0)
    new = de.add_section(doc, dict(orient="y"))
    assert "b shows it" in de.remove_section(doc, "s0")
    doc["panels"][0]["section"] = new
    assert de.remove_section(doc, new) is None
    assert doc["panels"][0]["section"] == "s0"  # (the plan view that named it: the first left)


def test_a_new_section_is_geometry_only():
    doc = section_doc()
    sid = de.add_section(doc, dict(orient="y", run=1, time_s=60.0, panel=2))
    assert doc["sections"][sid] == dict(orient="y")


@pytest.mark.parametrize("was,now", [("x", "y"), ("y", "x"), ("along", "across"), ("angle", "angle")])
def test_a_twin_section_turns(was, now):
    assert de.twin_section(dict(orient=was, label="Mine")) == dict(orient=now, label="")


def test_keep_apart_works_from_the_cross_sections_side():
    doc = section_doc()
    p = de.xsec_panel(doc, (0, 1), "r0", 1.0)
    assert [q["id"] for q in de.other_kinds_with(doc, "xsec", "l0")] == [0]
    new = de.split_shared(doc, "xsec", "l0")
    assert p["layers"][0]["ref"] == new and doc["panels"][0]["layers"][0]["ref"] == "l0"


# ------------------------------------------------------------------ one per run
def test_one_per_run_copies_a_cross_section_down_its_column():
    doc = section_doc()
    doc["panels"][0].update(kind="xsec", layers=[dict(ref="l0", over={})])
    doc["grid"] = dict(rows=1, cols=1)
    assert de.panel_per_run(doc, 0, dict(r1=660.0)) == 1
    new = doc["panels"][1]
    assert (new["run"], new["time_s"], new["cell"], new["section"]) == ("r1", 660.0, [1, 0, 1, 1], "s0")
    assert doc["grid"]["rows"] == 2
    assert de.panel_per_run(doc, 0) == 0  # (every run has it now)


def test_one_per_run_of_a_time_height_panel_moves_its_series_too():
    doc = series_doc("th", [series()])
    doc["panels"][0]["run"] = "r0"
    assert de.panel_per_run(doc, 0) == 1
    assert doc["panels"][1]["run"] == "r1" and doc["panels"][1]["layers"][0]["runs"] == ["r1"]
    assert doc["panels"][0]["layers"][0]["runs"] == ["r0"]


def test_a_series_of_every_run_splits_a_line_per_run():
    doc = series_doc("line", [dict(series(), runs=None, ens="p10p90", color="k")])
    p = doc["panels"][0]
    assert de.series_per_run(doc, p, 0) == 2
    assert [x["runs"] for x in p["layers"]] == [["r0"], ["r1"]]
    assert p["layers"][0]["ens"] == "" and p["layers"][0]["color"] != p["layers"][1]["color"]
    assert de.series_per_run(doc, p, 0) == 0  # (one run, and the other is there)


def test_a_series_of_one_run_gets_a_copy_for_the_other():
    doc = series_doc("line", [series()])
    p = doc["panels"][0]
    assert de.series_per_run(doc, p, 0) == 1
    assert [x["runs"] for x in p["layers"]] == [["r0"], ["r1"]]


# ------------------------------------------------------------------ a time-height panel's run
def test_a_time_height_panel_has_the_run_of_its_series():
    doc = series_doc("th")
    p = doc["panels"][0]
    de.add_series(p, series("r0"))
    assert p["run"] == "r0"
    de.write_panel(doc, p, 0, dict(runs=["r1"]))
    assert p["run"] == "r1"
    res = fg.one_panel(doc, 0)
    assert res["series"][0]["runs"] == [1]
    de.remove_in_panel(doc, p, 0)
    assert p["run"] is None


def test_a_time_series_panel_has_no_run_of_its_own():
    doc = series_doc("line", [series()])
    p = doc["panels"][0]
    de.write_panel(doc, p, 0, dict(runs=["r1"]))
    assert p["run"] is None


# ------------------------------------------------------------------ hand edits by run place
def test_hand_edits_follow_their_runs_when_one_goes():
    doc = series_doc("line", [dict(series(), runs=["r0", "r1"], edits={"0": {"60": 1.0}, "1": {
        "120": 2.0}}, added={"0": {"90": 3.0}, "1": {"150": 4.0}})])
    assert de.remove_run(doc, "r0") == []
    assert [r["id"] for r in doc["runs"]] == ["r1"]
    lay = doc["panels"][0]["layers"][0]
    assert lay["runs"] == ["r1"]
    assert lay["edits"] == {"0": {"120": 2.0}} and lay["added"] == {"0": {"150": 4.0}}


def test_hand_edits_of_the_only_run_that_goes_go_too():
    doc = series_doc("line", [dict(series(), edits={"1": {"120": 2.0}})])
    de.remove_run(doc, "r1")
    assert "edits" not in doc["panels"][0]["layers"][0]


# ------------------------------------------------------------------ a run in use goes
def test_a_runs_panels_go_with_it_and_others_stay():
    doc = section_doc()
    doc["panels"].append(dict(id=1, kind="plan", cell=[0, 1, 1, 1], run="r1", time_s=600.0,
                              title="", layers=[dict(ref="l0", over={})]))
    assert de.panels_of_run(doc, "r1") == [1]
    assert len(doc["panels"]) == 2 and len(doc["runs"]) == 2  # (only asked)
    assert de.remove_run(doc, "r1") == [1]
    assert [p["id"] for p in doc["panels"]] == [0]
    assert [r["id"] for r in doc["runs"]] == ["r0"] and "l0" in doc["layers"]


def test_a_panels_layers_of_the_run_go_with_it():
    doc = section_doc()
    doc["layers"]["l2"] = dict(type="fill", on=True, field="w", minus=dict(run="r1"))
    doc["panels"][0]["layers"] += [dict(ref="l2", over={}), dict(ref="l1", over=dict(run="r1")),
                                   dict(type="line", on=True, run="r1")]
    assert de.remove_run(doc, "r1") == []
    assert doc["panels"][0]["layers"] == [dict(ref="l0", over={}), dict(ref="l1", over={})]
    assert "l2" not in doc["layers"]


def test_a_panel_of_series_of_the_run_alone_goes_with_it():
    doc = series_doc("line", [series("r1")])
    doc["panels"].append(dict(id=1, kind="line", cell=[0, 1, 1, 1], run=None, time_s=None,
                              title="", layers=[series("r0"), series("r1")]))
    assert de.remove_run(doc, "r1") == [0]
    assert [p["id"] for p in doc["panels"]] == [1]
    assert [x["runs"] for x in doc["panels"][0]["layers"]] == [["r0"]]


def test_a_time_height_panel_follows_the_series_left():
    doc = series_doc("th", [series("r1"), series("r0")])
    doc["panels"][0]["run"] = None
    assert de.remove_run(doc, "r1") == []
    assert doc["panels"][0]["run"] == "r0"


# ------------------------------------------------------------------ words
def test_a_series_in_words():
    assert nodes.layer_name(dict(type="series", label="w max")) == "Series · w max"
    assert nodes.layer_name(dict(type="series", source="table", label="obs")) == "Your data · obs"
    assert nodes.layer_name(dict(type="series", source="parcels", label="p: w")) == "Parcels · p: w"


def test_titles_from_what_each_shows():
    doc = section_doc()
    doc["panels"][0]["kind"] = "xsec"
    doc["panels"].append(dict(copy.deepcopy(doc["panels"][0]), id=1, run="r1", cell=[0, 1, 1, 1]))
    de.entry_titles(doc, "xsec")
    assert doc["panels"][1]["title"] == "Two – x–z through the storm"
    assert doc["style"]["run_label"]["on"] is False  # (the titles name the runs)
    doc = series_doc("line", [series(), dict(series(), label="b")])
    de.entry_titles(doc, "line")
    assert doc["panels"][0]["title"] == "w / b" and "run_label" not in doc["style"]


# ------------------------------------------------------------------ automatic sizes
def test_a_figure_of_series_has_an_automatic_size_for_its_grid():
    doc = series_doc("th", [series()])
    assert de.kind_size(doc) == pytest.approx((5.5, 3.4))
    de.set_grid(doc, 1, 2)
    assert de.kind_size(doc) == pytest.approx((10.0, 3.4))
    doc["panels"].append(dict(doc["panels"][0], id=1, kind="plan"))
    assert de.kind_size(doc) is None


# ------------------------------------------------------------------ look rows
def test_a_cross_sections_height_is_its_own():
    from atmo3d.figures import schema as S
    keys = {r.key for r in S.rows_of("Height and x axis", ["xsec"], level="panel")}
    assert keys == {"look.xsec.ztop", "look.xsec.coords"}
    plan = {r.key for sec in S.sections(["plan"], level="panel")
            for r in S.rows_of(sec, ["plan"], level="panel")}
    assert not plan & keys


def test_a_time_series_has_its_own_panel_legend():
    from atmo3d.figures import schema as S
    keys = {r.key for r in S.rows_of("Legend in the panel", ["line"])}
    assert keys == {"look.ts.legend", "look.ts.legend_loc", "look.ts.legend_ncol",
                    "look.ts.legend_frame"}


# ------------------------------------------------------------------ the panes, by their widgets


@pytest.fixture
def shell(shell_viewer):
    """The new layout showing the demo's example figure, drawing as it is asked."""
    return fresh_shell(shell_viewer, min(4, len(shell_viewer.run.times) - 1))


def _named(shell, name):
    """A control of the frame's drawer (its Layers tool's, unless another is open)."""
    at_tool(shell, shell.frame.tool or "layers")
    for w in shell.frame.body.select():
        if getattr(w, "name", None) == name and hasattr(w, "value"):
            return w
    raise AssertionError(f"no {name}")


def _click(shell, name):
    at_tool(shell, shell.frame.tool or "layers")
    for w in shell.frame.body.select():
        if getattr(w, "name", None) == name and hasattr(w, "clicks"):
            w.clicks += 1
            return
    raise AssertionError(f"no button {name}")


def _drew(shell):
    t0 = time.time()
    while shell.ed.series_pending() and time.time() - t0 < 60:
        time.sleep(0.05)
    shell.request(force=True, delay=False)
    assert "Could not draw" not in shell.status.object
    return shell.status.object


def test_these_kinds_can_be_added_to_any_figure():
    assert {"xsec", "th", "line"} <= set(ADDABLE)


def test_a_cross_section_joins_plan_views_and_edits_its_section(shell):
    p = shell.grid.add_panel("xsec", "new column")
    assert shell.node == f"panel:{p['id']}" and "Could not draw" not in _drew(shell)
    control(shell, "Half-length (km)", "layers").value = 5.0
    assert shell.doc["sections"][p["section"]]["half"] == 5.0
    _drew(shell)
    shell.undo()
    assert shell.doc["sections"][p["section"]]["half"] != 5.0


def test_a_cross_section_keeps_a_layer_apart_from_plan_views(shell):
    p = shell.grid.add_panel("xsec", "new column")
    was = p["layers"][0]["ref"]
    at_tool(shell, "layers", "kind:xsec")
    press(shell, "Keep apart")
    assert de.panel_by_id(shell.doc, p["id"])["layers"][0]["ref"] != was
    assert de.panels_of(shell.doc, "plan")[0]["layers"][0]["ref"] == was


def test_a_copied_cross_section_says_it_shares_and_can_part(shell):
    p = shell.grid.add_panel("xsec", "new column")
    c = shell.grid.copy_panel(p["id"])
    assert c["section"] == p["section"]
    at_tool(shell, "layers", f"panel:{c['id']}")
    assert "show this section too" in drawer_text(shell) or "shows this section too" in \
        drawer_text(shell)
    press(shell, "Keep apart")
    assert de.panel_by_id(shell.doc, c["id"])["section"] != p["section"]


def test_a_cross_section_height_is_set_for_all_and_for_one(shell):
    p = shell.grid.add_panel("xsec", "new column")
    control(shell, "Top (km)", "look", "kind:xsec").value = 8.0
    assert shell.doc["kinds"]["xsec"]["xsec"]["ztop"] == 8.0
    control(shell, "Top (km)", "look", f"panel:{p['id']}").value = 4.0
    assert de.panel_by_id(shell.doc, p["id"])["opts"]["xsec"]["ztop"] == 4.0
    _drew(shell)


def test_a_cross_section_per_run_and_a_new_section_of_its_own(shell, demo_run):
    import os
    p = shell.grid.add_panel("xsec", "new column")
    shell.add_run(os.path.join(os.path.dirname(demo_run), "supercell_weak"),
                  node=f"panel:{p['id']}")
    at_tool(shell, "layout", f"panel:{p['id']}")
    n = len(shell.doc["panels"])
    press(shell, "One per run")
    assert len(shell.doc["panels"]) == n + 1
    other = shell.doc["panels"][-1]
    assert other["kind"] == "xsec" and other["run"] != p["run"]
    secs, was = len(shell.doc["sections"]), p["section"]
    at_tool(shell, "layers", f"panel:{p['id']}")
    press(shell, "+ Section")
    assert len(shell.doc["sections"]) == secs + 1
    assert de.panel_by_id(shell.doc, p["id"])["section"] not in (was, None)
    _drew(shell)


def test_all_cross_sections_list_the_sections(shell):
    p = shell.grid.add_panel("xsec", "new column")
    at_tool(shell, "layers", "kind:xsec")
    assert "Cross-section panels" in drawer_text(shell)
    n = len(shell.doc["sections"])
    press(shell, "+ Section")
    assert len(shell.doc["sections"]) == n + 1
    new = list(shell.doc["sections"])[-1]
    assert shell.frame.folds[f"sec:{new}"] is True
    fr = at_tool(shell, "layers")
    assert "No cross-section shows it" in drawer_text(shell)
    import panel as pn
    card = next(c for c in fr.body.objects if isinstance(c, pn.Card) and
                "No cross-section shows it" in " ".join(str(o.object) for o in
                                                         c.select(pn.pane.HTML)))
    next(b for b in card.select(pn.widgets.Button) if b.name == "✕").clicks += 1
    assert new not in shell.doc["sections"] and p["section"] in shell.doc["sections"]


def test_a_time_series_panel_takes_a_series_and_your_data(shell):
    p = shell.grid.add_panel("line", "new column")
    _click(shell, "+ Series")
    _click(shell, "+ Your data")
    q = de.panel_by_id(shell.doc, p["id"])
    assert q["layers"][0]["runs"] is None and q["layers"][1]["source"] == "table"
    at_tool(shell, "layers")
    box = next(w for w in shell.frame.body.select()
               if str(getattr(w, "name", "")).startswith("Your data: time"))
    box.value = "time_min,rain (mm)\n0,1\n30,5\n"
    q = de.panel_by_id(shell.doc, p["id"])
    assert q["layers"][1]["table"]["t"] == [0.0, 30.0] and q["layers"][1]["units"] == "mm"
    _drew(shell)


def test_a_series_moves_to_another_panel(shell):
    a = shell.grid.add_panel("line", "new column")
    at_tool(shell, "layers")
    _click(shell, "+ Series")
    b = shell.grid.add_panel("line", "new row")
    shell.select(f"layer:{a['id']}:0")
    _named(shell, "In panel").value = b["id"]
    assert not de.panel_by_id(shell.doc, a["id"])["layers"]
    assert len(de.panel_by_id(shell.doc, b["id"])["layers"]) == 1


def test_every_node_of_these_kinds_shows(shell):
    for kind in ("xsec", "th", "line"):
        p = shell.grid.add_panel(kind)
        if kind != "xsec":
            _click(shell, "+ Series")
        assert p["id"] in nodes.letters(shell.doc)
    _drew(shell)
    for tool in ("layout", "layers", "look", "times"):
        for node in every_node(shell.doc):
            at_tool(shell, tool, node)
            assert shell.frame.body.objects, node
            assert "Could not show" not in drawer_text(shell), (tool, node)


def test_a_time_height_panel_has_one_series_with_no_copy(shell, demo_run):
    import os
    p = shell.grid.add_panel("th", "new column")
    at_tool(shell, "layers")
    assert "Nothing is computed until there is one" in drawer_text(shell)
    _click(shell, "+ Series")
    q = de.panel_by_id(shell.doc, p["id"])
    assert len(q["layers"]) == 1 and q["layers"][0]["runs"] == [shell.doc["runs"][0]["id"]]
    at_tool(shell, "layers")
    assert "shows one series" in drawer_text(shell)
    names = {getattr(w, "name", "") for w in shell.frame.body.select()}
    assert "⧉" not in names and "In panel" not in names and "+ Series" not in names
    shell.add_run(os.path.join(os.path.dirname(demo_run), "supercell_weak"))
    _click(shell, "One per run")
    assert len(de.panels_of(shell.doc, "th")) == 2
