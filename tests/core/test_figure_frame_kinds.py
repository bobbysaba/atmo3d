"""The frame's tools for the kinds after plan views and cross-sections (docs-dev/figures-ui-plan.md
3.3): soundings, time–height panels and time series, distributions, profiles, joint
distributions, azimuthal means, tables and 3D scenes.  On the demo run: every tool at every level
of each shows, and the drawers the tools make there hold every setting of the place (its
entries', a scene's lists'), so nothing the old screens offered is out of reach; the Layers
tool's actions of each kind.  (The kinds' own edits: test_figure_shell_{stats,series,scene,
mixed}.py.)"""

import pytest

from conftest import at_tool, drawer_text, fresh_shell, press

from atmo3d.figures import draw as figdraw
from atmo3d.figures.schema.where import Where
from atmo3d.figures.shell import docedit as de
from atmo3d.figures.ui import drawer as D, entries, tools

KINDS = ("sounding", "th", "line", "dist", "profile", "joint", "azim", "table", "scene")
TOOLS = [k for k, *_ in tools.TOOLS]


@pytest.fixture
def shell(shell_viewer):
    return fresh_shell(shell_viewer, min(4, len(shell_viewer.run.times) - 1))


def _panel_of(shell, kind):
    """A new panel of the kind (time series: with a series), picked."""
    if kind == "scene":
        pytest.importorskip("pyvista")
        shell.doc["export"] = dict(shell.doc.get("export") or {}, dpi=60)
    p = shell.grid.add_panel(kind, "new column")
    if kind in entries.SERIES:
        at_tool(shell, "layers", f"panel:{p['id']}")
        press(shell, "+ Series")
    return de.panel_by_id(shell.doc, p["id"])


def _places(doc, kind, pid):
    """(node, place, part) of every place of the kind's settings."""
    out = [(f"kind:{kind}", Where("kind", kind), None),
           (f"panel:{pid}", Where("panel", kind, pid), None)]
    p = de.panel_by_id(doc, pid)
    for j, _ in enumerate(figdraw.panel_layers(doc, p)):
        out.append((f"layer:{pid}:{j}", Where("panel", kind, pid, layer=j), None))
    if kind == "scene":
        for level, node, at in (("kind", f"kind:{kind}", None), ("panel", f"panel:{pid}", pid)):
            sc = de.scene_block(doc, at)
            for name in ("isos", "vecs", "parcels"):
                for n, _ in enumerate(sc[name]):
                    out.append((node, Where(level, kind, at, item=n), f"scene:{name}"))
    return out


@pytest.mark.parametrize("kind", KINDS)
def test_every_tool_shows_at_every_level_and_holds_every_setting(shell, kind):
    p = _panel_of(shell, kind)
    doc = shell.doc
    for node, where, part in _places(doc, kind, p["id"]):
        made = set()
        for tool in TOOLS:
            at_tool(shell, tool, node)
            said = drawer_text(shell)
            assert "Could not show" not in said, (kind, tool, node, said)
            assert shell.frame.body.objects, (kind, tool, node)
            made |= {(d.where, r.id) for d in shell.frame.drawers for s in d.sections
                     for r in s.rows}
        want = {(where, r.id) for r in D.rows_at(shell.doc, where, part)
                if tools.tool_of(r) is not None}
        # (a layer node's Look is its panel's: its own rows are in Layers there)
        assert want <= made, (kind, node, sorted(r for _, r in want - made)[:10])


@pytest.mark.parametrize("kind", [k for k in entries.ENTRY_KINDS if k not in entries.SERIES])
def test_a_panel_of_entries_adds_one_open_and_a_copy(shell, kind):
    p = _panel_of(shell, kind)
    pid, n = p["id"], len(p["layers"])
    at_tool(shell, "layers", f"panel:{pid}")
    press(shell, f"+ {entries.SPEC[kind].one}")
    assert len(de.panel_by_id(shell.doc, pid)["layers"]) == n + 1
    assert shell.frame.folds.get(f"p:{pid}:{n}")
    at_tool(shell, "layers")
    press(shell, "⧉")
    assert len(de.panel_by_id(shell.doc, pid)["layers"]) == n + 2
    shell.undo()
    shell.undo()
    assert len(de.panel_by_id(shell.doc, pid)["layers"]) == n


def test_all_soundings_add_a_panel_and_say_when_the_map_has_none(shell):
    _panel_of(shell, "sounding")
    at_tool(shell, "layers", "kind:sounding")
    n = len(de.panels_of(shell.doc, "sounding"))
    press(shell, "+ Sounding panel")
    assert len(de.panels_of(shell.doc, "sounding")) == n + 1
    at_tool(shell, "layers", "kind:sounding")
    shell.ed.tab_soundings = lambda: []
    press(shell, "+ The map's soundings")
    assert "Sounding tool" in shell.status.object
    assert len(de.panels_of(shell.doc, "sounding")) == n + 1


def test_an_entry_kinds_times_say_where_they_are(shell):
    p = _panel_of(shell, "dist")
    at_tool(shell, "times", f"panel:{p['id']}")
    assert "own run and time" in drawer_text(shell)


def test_a_scenes_layers_list_its_items_and_the_kinds_say_who_differs(shell):
    p = _panel_of(shell, "scene")
    pid = p["id"]
    copy = shell.grid.copy_panel(pid)
    at_tool(shell, "layers", f"panel:{copy['id']}")
    press(shell, "+ Isosurface")
    assert "isos" in de.scene_own(shell.doc, copy["id"])
    at_tool(shell, "layers", "kind:scene")
    assert "Set in a scene alone" in drawer_text(shell)
    at_tool(shell, "layers", f"panel:{copy['id']}")
    press(shell, "↺ Isosurfaces")
    assert not de.scene_own(shell.doc, copy["id"])
