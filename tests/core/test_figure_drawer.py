"""The generic drawer (figures/ui/drawer.py, docs-dev/figures-ui-plan.md Phase 2.2) and Find over
the schema (figures/ui/find.py, 2.3), on a document with a panel of every kind (ui/samples.py): a
drawer is made for every place of it with every section open; a change made in a control is the
schema's write; what a panel sets for itself is marked and taken back; Reset section; Find opens
the right place.  No viewer: the host is the samples' (no fields: a field is typed)."""

import pytest

from atmo3d.figures import schema as S
from atmo3d.figures.schema import where as W
from atmo3d.figures.schema.where import Where
from atmo3d.figures.ui import drawer as D, find, samples


def _places(doc):
    return [(w, part) for _, w, part in samples.places(doc)]


def _open(d):
    for s in d.sections:
        s.card.collapsed = False
    return d


@pytest.mark.parametrize("n", range(len(_places(samples.every_kind()))))
def test_every_place_of_every_kind_has_a_drawer(n):
    host = samples.Host()
    where, part = _places(host.doc)[n]
    rows = D.rows_at(host.doc, where, part)
    assert rows, where
    d = _open(D.Drawer(host, where, rows))
    host.drawers.append(d)
    made = sum(len(s.ctls) for s in d.sections)
    assert made == len(rows) - sum(r.control.kind == "values" for r in rows) or \
        made == len(rows), (where, made, len(rows))
    assert not host.said
    assert any(s.card.visible for s in d.sections)


def _ctl(d, key):
    for s in d.sections:
        for r in s.rows:
            if r.id == key:
                return s, s.ctls[r.id]
    raise KeyError(key)


def test_a_change_in_a_control_is_the_schemas_write():
    host = samples.Host()
    at = Where("panel", "plan", 1, layer=0)
    d = _open(D.Drawer(host, at))
    host.drawers.append(d)
    _, ctl = _ctl(d, "layer.vmax~fill")
    ctl.widget.value = 50.0
    assert W.layer_at(host.doc, at)["vmax"] == 50.0
    assert host.doc["layers"]["l0"]["vmax"] == 60.0  # (this panel's: the shared one stays)
    assert len(host.undo) == 1
    sec, ctl = _ctl(d, "layer.cmap~fill")
    assert ctl.get() == "Reds" and sec.lines["layer.cmap~fill"][1].visible  # (marked, ↺)
    assert "set here" in sec.card.title
    sec.lines["layer.cmap~fill"][1].clicks += 1  # (↺: back to the shared layer's)
    assert W.layer_at(host.doc, at)["cmap"] == "viridis"
    assert not sec.lines["layer.cmap~fill"][1].visible


def test_your_own_code_has_a_plain_box_too():
    """The highlighted editor comes from a CDN: the plain box beside it (for a browser without
    internet) holds the same text, and typing in either is one edit."""
    host = samples.Host()
    d = _open(D.Drawer(host, Where()))
    host.drawers.append(d)
    _, ctl = _ctl(d, "code.text")
    editor, plain = ctl.parts
    plain.value = "fig.suptitle('x')"
    assert editor.value == "fig.suptitle('x')" and len(host.undo) == 1
    assert host.doc["code"]["text"] == "fig.suptitle('x')"
    editor.value = "pass"
    assert plain.value == "pass" and len(host.undo) == 2


def test_a_control_shows_and_hides_with_its_condition():
    host = samples.Host()
    at = Where("kind", "plan", layer="l1")
    d = _open(D.Drawer(host, at))
    host.drawers.append(d)
    sec, size = _ctl(d, "layer.clabel_size")
    assert not sec.lines["layer.clabel_size"][0].visible
    _, clabel = _ctl(d, "layer.clabel")
    clabel.widget.value = True
    assert host.doc["layers"]["l1"]["clabel"] is True
    assert sec.lines["layer.clabel_size"][0].visible


def test_reset_section_takes_a_panels_own_settings_back():
    host = samples.Host()
    host.doc["panels"][4]["opts"] = dict(axes=dict(xlabel="own", ylabel="mine"))
    at = Where("panel", "line", 4)
    d = _open(D.Drawer(host, at))
    host.drawers.append(d)
    sec = next(s for s in d.sections if any(r.key == "look.axes.xlabel" for r in s.rows))
    assert "2 set here" in sec.card.title or "set here" in sec.card.title
    sec.reset.clicks += 1
    assert not (host.doc["panels"][4].get("opts") or {}).get("axes")


def test_a_bad_value_is_said_not_written():
    host = samples.Host()
    d = _open(D.Drawer(host, W.FIGURE, D.rows_at(host.doc, W.FIGURE)))
    host.drawers.append(d)
    _, ctl = _ctl(d, "grid.widths")
    ctl.widget.value = "1, 2, 3, 4, 5, 6"
    assert host.said and host.said[-1][1] and not host.undo


def test_find_opens_the_place_a_setting_is_set_at():
    doc = samples.every_kind()
    hits = find.hits(doc, "colormap")
    keys = {r.id for r, _ in hits}
    assert "layer.cmap~fill" in keys and "layer.cmap~series" in keys
    row, at = next((r, a) for r, a in hits if r.id == "layer.cmap~fill")
    assert {w.level for w in at} == {"kind", "panel"}
    assert all(W.layer_type(W.layer_at(doc, w)) == "fill" for w in at)
    assert find.place_words(doc, at[0]).startswith("all ")
    picked = []
    f = find.Find(samples.Host(doc), lambda r, w: picked.append((r.id, w)))
    f.show("tick every")
    assert len(f.list.objects) >= 2
    f.list.objects[0].clicks += 1
    assert picked and picked[0][0] in S.BY_KEY
    f.show("no such setting at all")
    assert "No setting" in f.list.objects[0].object
