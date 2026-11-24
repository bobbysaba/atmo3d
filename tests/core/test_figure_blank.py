"""New figures start empty (docs-dev/figures-ui-plan.md, Phase 3): the page's figure is one plan
view at the viewer's time drawing nothing; the New dialog's colour fill starts at None, and a
fill chosen there is the only layer; the first plan view added to a figure with no layers draws
nothing.  (The other tests' editors start as before: conftest._old_start.)"""

from atmo3d.figures import editor
from atmo3d.figures.quick import FigureQuick, NO_FILL
from atmo3d.figures.shell import docedit as de


def _editor(v):
    from conftest import fresh_editor
    ed = fresh_editor(v)
    v.figed = new = editor.FigureEditor(v)  # (as the page makes it: no _old_start)
    del ed
    return new


def test_the_page_starts_with_an_empty_plan_view(shell_viewer):
    ed = _editor(shell_viewer)
    doc = ed.shell.doc
    assert [p["kind"] for p in doc["panels"]] == ["plan"]
    assert not doc.get("layers") and not doc["panels"][0].get("layers")
    assert doc["panels"][0]["time_s"] == float(ed.run.times[shell_viewer.t])


def test_the_new_dialog_starts_at_no_fill(shell_viewer):
    ed = _editor(shell_viewer)
    ed.open_quick()
    ed.quick.hide()
    assert ed.qs_field.value == "" and NO_FILL in ed.qs_field.options
    assert ed.qs_vary.value == "none" and (ed.qs_rows.value, ed.qs_cols.value) == (1, 1)
    assert FigureQuick._quick_spec(ed)["layers"] == []
    f = ed.F.role("refl") or next(iter(ed.F.defs))
    ed.qs_field.value = f
    lays = FigureQuick._quick_spec(ed)["layers"]
    assert [(x["type"], x["field"]) for x in lays] == [("fill", f)]


def test_a_first_plan_view_added_draws_nothing(shell_viewer):
    ed = _editor(shell_viewer)
    sh = ed.shell
    sh.open()
    sh.edit(lambda d: de.remove_panel(d, d["panels"][0]["id"]) if len(d["panels"]) > 1 else None)
    sh.grid.add_panel("plan", "new column")
    assert not sh.doc.get("layers")
    assert all(not p.get("layers") for p in sh.doc["panels"])
