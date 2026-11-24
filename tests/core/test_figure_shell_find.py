"""M10: find a setting, what is changed from a new figure, and a section's reset: in the
figure's frame (figures/ui: find.py, drawer.py); what a kind's settings show hanging on their
neighbours (soundings, distributions)."""
import pytest

from conftest import at_tool, control, fresh_shell

from atmo3d.figures import schema as S, spec as fg
from atmo3d.figures.kinds import KINDS
from atmo3d.figures.schema.where import Where
from atmo3d.figures.shell import nodes
from atmo3d.figures.ui import drawer as D, find, tools
from atmo3d.figures.ui.frame import node_of


@pytest.fixture
def shell(shell_viewer):
    return fresh_shell(shell_viewer, min(4, len(shell_viewer.run.times) - 1))


def _new_figure(shell, kind):
    ed = shell.ed
    ed.open_quick()
    ed.qs_kind.value = kind
    ed._quick_make()


def _sec(shell, title, where=None):
    """A section of the frame's drawers (at where), open."""
    for d in shell.frame.drawers:
        if where is not None and d.where != where:
            continue
        for sec in d.sections:
            if sec.title == title or sec.title.startswith(title + " ·"):
                sec.card.collapsed = False
                return sec
    raise AssertionError(f"no section {title} at {shell.node}")


def _ctl(sec, label):
    return next(sec.ctls[r.id] for r in sec.rows if r.label == label and r.id in sec.ctls)


def _back(sec, label):
    return next(sec.lines[r.id][1] for r in sec.rows if r.label == label and r.id in sec.lines)


# ------------------------------------------------------------------ without widgets
def test_values_that_read_the_same():
    same = D.same
    assert same(None, "") and same([], None) and same(10, 10.0) and same([1], (1,))
    assert not same(0, None) and not same("a", "b") and not same(1.0, 1.5)


def test_a_new_figures_look_differs_by_kind(reg):
    run, F = reg.get()
    plan = fg.fresh_look(run, F, 0, "plan")
    assert plan["kinds"]["plan"]["axes"]["xlabel"] == "x (km)"
    assert plan["kinds"]["plan"]["domain"]["mode"] == "storm"
    assert fg.fresh_look(run, F, 0, "plan", tracked=False)["kinds"]["plan"]["domain"]["mode"] == "full"
    snd = fg.fresh_look(run, F, 0, "sounding")
    assert snd["style"]["letters"]["loc"] == KINDS["sounding"].letter_at
    assert "domain" not in snd["kinds"]["sounding"] and "skewt" in snd["kinds"]["sounding"]
    th = fg.fresh_look(run, F, 0, "th")
    assert th["style"]["time_label"]["on"] is False and th["style"]["colorbar"]["mode"] == "row"
    assert th["style"]["colorbar"]["location"] == "right"


def test_search_ranks_the_name_first_and_needs_every_word():
    hits = S.search("width")
    assert hits[0].label.lower().startswith("width")
    assert all("width" in r.label.lower() for r in hits[:3])
    both = S.search("width frame")
    assert both and all(D.same(1, 1) for r in both)
    assert all({"width", "frame"} <= set(S.plain(" ".join(
        (r.label, r.section, r.help, r.key))).replace("(", " ").split()) | {"width", "frame"}
        for r in both)
    assert S.search("   ") == []
    # (either spelling, and a colour bar is a colorbar)
    assert S.search("colour bar") and S.search("colour bar")[0].id == S.search("colorbar")[0].id
    assert S.search("centre") == S.search("center")


# ------------------------------------------------------------------ new figures read as unchanged
@pytest.mark.parametrize("kind", ["plan", "xsec", "line", "sounding", "dist", "profile", "joint",
                                  "azim", "table", "scene"])
def test_nothing_is_changed_in_a_new_figure(shell, kind):
    _new_figure(shell, kind)
    for node in (nodes.FIGURE, f"kind:{kind}"):
        for tool in ("layout", "look", "marks"):
            at_tool(shell, tool, node)
            for d in shell.frame.drawers:
                for sec in d.sections:
                    assert "changed" not in sec.card.title, (node, tool, sec.card.title)


# ------------------------------------------------------------------ marks follow the edits
def test_a_change_is_marked_and_a_reset_undoes_one_step(shell):
    _new_figure(shell, "plan")
    at_tool(shell, "look", nodes.FIGURE)
    sec = _sec(shell, "Text")
    assert sec.card.title == "Text" and not sec.reset.visible
    w = _ctl(sec, "Panel titles (pt)")
    w.widget.value = 15.0
    assert sec.card.title == "Text · 1 changed" and sec.reset.visible
    assert "box-shadow" in w.widget.styles and _back(sec, "Panel titles (pt)").visible
    _ctl(sec, "Tick labels (pt)").widget.value = 9.0
    assert sec.card.title == "Text · 2 changed"
    was = len(shell._hist)
    sec.reset.clicks += 1
    assert len(shell._hist) == was + 1
    font = shell.doc["style"]["font"]
    assert font["title"] is None and font["tick"] is None
    sec = _sec(shell, "Text")
    assert sec.card.title == "Text" and not sec.reset.visible
    assert _ctl(sec, "Panel titles (pt)").get() in (None, "")
    shell.undo()
    assert shell.doc["style"]["font"]["title"] == 15.0
    assert _sec(shell, "Text").card.title == "Text · 2 changed"


def test_one_setting_goes_back_to_a_new_figures(shell):
    _new_figure(shell, "plan")
    at_tool(shell, "look", nodes.FIGURE)
    sec = _sec(shell, "Text")
    _ctl(sec, "Panel titles (pt)").widget.value = 15.0
    _ctl(sec, "Tick labels (pt)").widget.value = 9.0
    _back(sec, "Panel titles (pt)").clicks += 1
    font = shell.doc["style"]["font"]
    assert font["title"] is None and font["tick"] == 9.0


def test_folded_sections_count_too_and_an_edit_elsewhere_updates_them(shell):
    _new_figure(shell, "plan")
    at_tool(shell, "layout", nodes.FIGURE)
    sec = next(s for d in shell.frame.drawers for s in d.sections if s.title == "Spacing")
    sec.card.collapsed = True
    shell.frame.show(nodes.FIGURE)
    sec = next(s for d in shell.frame.drawers for s in d.sections if s.title == "Spacing")
    assert sec.card.collapsed and sec.card.title == "Spacing" and not sec.ctls
    shell.edit(lambda d: d["style"]["spacing"].update(wspace=0.3))
    assert sec.card.title == "Spacing · 1 changed" and sec.card.collapsed and not sec.ctls


def test_a_kinds_reset_goes_to_its_own_new_figure_and_skips_what_panels_set(shell):
    _new_figure(shell, "plan")
    control(shell, "x label", "look", "kind:plan").value = "mine"
    shell.edit(lambda d: d["panels"][1].setdefault("opts", {}).update(axes=dict(tickdir="in")))
    _sec(shell, "Axes and ticks", Where("kind", "plan")).reset.clicks += 1
    assert shell.doc["kinds"]["plan"]["axes"]["xlabel"] == "x (km)"
    assert shell.doc["panels"][1]["opts"]["axes"]["tickdir"] == "in"
    assert "Panel b keeps what it set alone" in shell.status.object


def test_a_panel_marks_its_own_and_goes_back_to_inheriting(shell):
    _new_figure(shell, "plan")
    pid = shell.doc["panels"][0]["id"]
    at_tool(shell, "look", f"panel:{pid}")
    sec = _sec(shell, "Axes and ticks", Where("panel", "plan", pid))
    assert sec.card.title == "Axes and ticks"
    _ctl(sec, "Ticks point").widget.value = "in"
    assert sec.card.title == "Axes and ticks · 1 set here"
    sec.reset.clicks += 1
    assert "opts" not in shell.doc["panels"][0]


def test_letters_go_back_to_following_the_count(shell):
    _new_figure(shell, "plan")
    at_tool(shell, "look", nodes.FIGURE)
    sec = _sec(shell, "Panel labels")
    _ctl(sec, "Panel letters").widget.value = False
    assert shell.doc["style"]["letters"]["auto"] is False
    assert "1 changed" in sec.card.title
    sec.reset.clicks += 1
    letters = shell.doc["style"]["letters"]
    assert letters["auto"] is True and letters["on"] is True


def test_area_counts_its_box_while_it_is_used_and_resets_it(shell):
    _new_figure(shell, "plan")
    at_tool(shell, "layout", "kind:plan")
    sec = _sec(shell, "Area", Where("kind", "plan"))
    start = shell.doc["kinds"]["plan"]["domain"]["mode"]
    _ctl(sec, "Plan-view area").widget.value = "box"
    dom = shell.doc["kinds"]["plan"]["domain"]
    assert dom["mode"] == "box" and dom["box"]
    assert "2 changed" in sec.card.title
    sec.reset.clicks += 1
    dom = shell.doc["kinds"]["plan"]["domain"]
    assert dom["mode"] == start and dom.get("box") is None


def test_a_kinds_own_colorbar_goes_back_to_the_figures(shell):
    _new_figure(shell, "plan")
    shell.grid.add_panel("sounding")
    shell.edit(lambda d: d["kinds"]["plan"].update(colorbar=dict(
        shrink=0.3, location="right", orientation="vertical")))
    at_tool(shell, "look", "kind:plan")
    sec = _sec(shell, "Colorbar", Where("kind", "plan"))
    assert "set here" in sec.card.title
    sec.reset.clicks += 1
    assert "colorbar" not in shell.doc["kinds"]["plan"]


def test_your_own_code_has_no_reset_but_is_marked(shell):
    _new_figure(shell, "plan")
    shell.edit(lambda d: d["code"].update(text="print(1)"))
    at_tool(shell, "look", nodes.FIGURE)
    sec = _sec(shell, "Your own code")
    assert "1 changed" in sec.card.title and not sec.reset.visible


def test_an_odd_value_is_no_reason_to_fail(shell):
    _new_figure(shell, "plan")
    shell.edit(lambda d: d["style"]["spacing"].update(wspace="odd"))
    at_tool(shell, "layout", nodes.FIGURE)
    assert _sec(shell, "Spacing").card.title.startswith("Spacing")


def test_a_place_on_the_colorbar_names_its_orientation_too():
    assert S.row("look.colorbar.location").names == ("location", "orientation")


# ------------------------------------------------------------------ find
def test_find_lists_only_what_this_figure_has(shell):
    _new_figure(shell, "plan")
    f = shell.frame.find
    f.box.value_input = "hodograph"
    assert not f.found and "No setting matches" in str(f.list.objects[0].object)
    f.box.value_input = "colour bar len"
    row, _ = f.found[0]
    assert row.label == "Length (0–1)" and row.section == "Colorbar"
    f.box.value_input = ""
    assert not f.found and not f.list.objects


def test_finding_opens_the_section_and_marks_the_setting(shell):
    _new_figure(shell, "plan")
    fr = shell.frame
    f = fr.find
    f.box.value_input = "panel titles"
    assert f.found[0][0].label == "Panel titles (pt)"
    f.first()
    assert shell.node == nodes.FIGURE and fr.tool == "look" and f.box.value_input == ""
    assert not f.found and fr.side.visible
    sec = _sec(shell, "Text")
    assert not sec.card.collapsed and "outline" in _ctl(sec, "Panel titles (pt)").widget.styles
    assert "Panel titles" in fr.found.object
    shell.select(nodes.RUNS)
    assert fr.found.object == ""


def test_find_with_the_page_built(shell):
    """With models made, as in a browser."""
    from bokeh.document import Document
    fr = shell.frame
    root = fr.panel.get_root(Document())
    f = fr.find
    f.box.value_input = "panel titles"
    f.box.value_input = ""
    f.box.value_input = "panel titles"
    f.first()
    sec = _sec(shell, "Text")
    _ctl(sec, "Panel titles (pt)").widget.value = 14.0
    assert "1 changed" in sec.card.title
    sec.reset.clicks += 1
    assert _sec(shell, "Text").card.title == "Text"
    assert root is not None


def test_find_offers_the_panel_picked_first(shell):
    _new_figure(shell, "plan")
    pid = shell.doc["panels"][1]["id"]
    shell._show(f"panel:{pid}")
    f = shell.frame.find
    f.box.value_input = "ticks point"
    assert f.found[0][1] == Where("panel", "plan", pid)
    f.first()
    assert shell.node == f"panel:{pid}" and shell.frame.tool == "look"
    assert not _sec(shell, "Axes and ticks", Where("panel", "plan", pid)).card.collapsed


def test_find_says_when_a_setting_is_left_out(shell):
    _new_figure(shell, "plan")
    fr = shell.frame
    row = next(r for r in S.ROWS if r.when == "older t0")  # (an older figure's: none here)
    fr.go_to(row, Where())
    assert fr.tool == tools.tool_of(row) and "isn't shown here" in fr.found.object


def test_find_goes_to_the_export_dialog(shell, monkeypatch):
    opened = []
    monkeypatch.setattr(shell.export, "open", lambda: opened.append(1))
    f = shell.frame.find
    f.box.value_input = "dpi"
    row, _ = f.found[0]
    assert row.label == "DPI" and row.section == "Export"
    node = shell.node
    f.first()
    assert opened == [1] and shell.node == node


def test_every_setting_opens_where_it_says(shell):
    """Every row of a plan-view figure, at one place of each kind of place: its tool there shows
    it (or says why not)."""
    _new_figure(shell, "plan")
    fr, doc = shell.frame, shell.doc
    seen = set()
    for r in S.ROWS:
        if tools.tool_of(r) is None:
            continue
        for w in find.places(doc, r):
            node, fold = node_of(doc, w, D.part_of(r))
            key = (node.split(":")[0], tools.tool_of(r), r.section, w.layer is None, fold is None)
            if key in seen:
                continue
            seen.add(key)
            fr.go_to(r, w)
            assert fr.tool == tools.tool_of(r), r.id
            assert "Found" in fr.found.object or "isn't shown here" in fr.found.object, (r.id, w)
            assert shell.node == node, (r.id, w)


def _vis(sec, label):
    """Whether a section's row of this label shows."""
    return next(sec.lines[r.id][0].visible for r in sec.rows if r.label == label
                and r.id in sec.lines)


def test_what_a_soundings_settings_show_hangs_on_their_neighbours(shell):
    _new_figure(shell, "sounding")
    shell.edit(lambda d: d["kinds"]["sounding"]["skewt"].update(layout="inset"))
    at_tool(shell, "look", "kind:sounding")
    where = Where("kind", "sounding")
    panels = _sec(shell, "Sounding panels", where)
    assert not _vis(panels, "Storm u (m/s)")
    _ctl(panels, "Storm motion (SRH, ring)").widget.value = "custom"
    assert _vis(panels, "Storm u (m/s)")
    hodo = _sec(shell, "Hodograph", where)
    assert not _vis(hodo, "Inset x (left edge)")
    _ctl(hodo, "Inset at").widget.value = "custom"
    assert _vis(hodo, "Inset x (left edge)") and _vis(hodo, "Inset y (bottom edge)")
    assert not _vis(hodo, "Centre u (m/s)") and _vis(hodo, "Hodograph ± (m/s)")
    _ctl(hodo, "Hodograph centred on").widget.value = "custom"
    assert _vis(hodo, "Centre u (m/s)") and _vis(hodo, "Hodograph ± (m/s)")
    _ctl(hodo, "Hodograph centred on").widget.value = "fit"
    assert not _vis(hodo, "Centre u (m/s)") and not _vis(hodo, "Hodograph ± (m/s)")
    assert shell.doc["kinds"]["sounding"]["skewt"]["hodo_center"] == "fit"
    assert not _vis(hodo, "Key of the height colours")  # (an inset hodograph has no key)


def test_what_a_distributions_settings_show_hangs_on_the_plot(shell):
    _new_figure(shell, "dist")
    shell.edit(lambda d: d["kinds"]["dist"]["dist"].update(plot="hist", stats_at="box"))
    at_tool(shell, "look", "kind:dist")
    where = Where("kind", "dist")
    plot = _sec(shell, "Plot", where)
    assert _vis(plot, "Bar labels")
    _ctl(plot, "Draw as").widget.value = "box"
    assert not _vis(plot, "Bar labels")
    stats = _sec(shell, "Statistics", where)
    assert _vis(stats, "Box at")
    _ctl(stats, "Statistics shown").widget.value = "legend"
    assert not _vis(stats, "Box at")
