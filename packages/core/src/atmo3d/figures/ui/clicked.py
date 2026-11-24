"""A click on a part of the preview (docs-dev/figures-ui-plan.md, Phase 6; mockup C): which
setting a title, an axis label, a panel label, a legend or a colorbar opens, at which place, and
what the drawer says of a part several panels share (a colorbar), with links to the settings
behind it.  Without widgets: the Frame (frame.go_part) opens what this says.

The parts come from click.part_boxes (where the drawing put each); a part names a schema row
(PARTS, or for a panel's own legend or colorbar its kind's) and its place is the row's place
nearest the panel clicked: the panel, else its kind, else the figure (find.places)."""

import html
from dataclasses import dataclass

from .. import draw as figdraw, schema as S
from ..draw.base import _cell
from ..draw.layers import bar_fill
from ..draw.v2 import LEGEND_OPTS
from ..schema import where as W
from ..schema.where import Where
from ..shell import docedit as de, nodes
from . import lines
from .find import places

PARTS = {"title": "panels[].title", "rowlabel": "panels[].rowlabel",
         "xlabel": "look.axes.xlabel", "ylabel": "look.axes.ylabel",
         "letters": "look.letters.on", "time_label": "look.time_label.on",
         "run_label": "look.run_label.on", "z_label": "look.z_label.on",
         "legend": "look.legend.where", "figure legend": "look.legend.where",
         "suptitle": "suptitle"}
OWN_BAR = {"joint": "look.joint.cbar_label", "azim": "look.azim.cbar_label"}
PANEL_BAR = "panels[].colorbar.cbar_label"
ALL_BARS = "look.colorbar.mode"


@dataclass(frozen=True)
class Target:
    """What a click on a part opens: a row at a place (go_to's), the node to pick there (None:
    the place's own; a row or column for its colorbar), what was clicked in words, and a note
    with links [(words, Target)] (a shared part's)."""
    row: object
    where: Where
    node: str = None
    words: str = ""
    note: str = ""
    links: tuple = ()


def nearest(doc, row, pid):
    """Of the places row is offered at in doc, the one nearest panel pid: the panel's own (not a
    layer's or an inset's), else its kind's, else the figure's, else the first (None: none)."""
    at = places(doc, row)
    if not at:
        return None
    p = de.panel_by_id(doc, pid) if pid is not None else None
    kind = p["kind"] if p is not None else None
    for ok in (lambda w: w.level == "panel" and w.pid == pid and w.layer is None,
               lambda w: w.level == "kind" and w.kind == kind and w.layer is None,
               lambda w: w.level == "figure"):
        hit = next((w for w in at if ok(w)), None)
        if hit is not None:
            return hit
    return at[0]


def _at(doc, key, pid, words, **kw):
    row = S.BY_KEY.get(key)
    where = nearest(doc, row, pid) if row is not None else None
    return None if where is None else Target(row, where, words=words, **kw)


def target(doc, part):
    """The Target of a click.Part of figure doc (None: nothing of it to open)."""
    from ..click import PART_WORDS
    words = PART_WORDS.get(part.part, part.part)
    p = de.panel_by_id(doc, part.panel) if part.panel is not None else None
    if part.panel is not None and p is None:
        return None
    if part.part == "colorbar":
        return bar_target(doc, part, words)
    if part.part == "own legend":
        prefix = LEGEND_OPTS.get(p["kind"], ("",))[0]
        return _at(doc, f"look.{prefix}.legend", p["id"], words) if prefix else None
    if part.part == "own colorbar":
        key = OWN_BAR.get(p["kind"])
        return _at(doc, key, p["id"], words) if key else None
    key = PARTS.get(part.part)
    if key is None:
        return None
    return _at(doc, key, None if p is None else p["id"], words)


def first_fill(doc, pid):
    """(place in panel pid's layers, its layer) of the first fill a colorbar shows, or None."""
    p = de.panel_by_id(doc, pid)
    for j, (_, lay) in enumerate(figdraw.panel_layers(doc, p) if p else ()):
        if bar_fill(lay):
            return j, lay
    return None


def _fill_link(doc, pid, letter):
    hit = first_fill(doc, pid)
    if hit is None:
        return None
    j, lay = hit
    p = de.panel_by_id(doc, pid)
    row = S.row_for("layer.cmap", W.layer_type(lay))
    if row is None:
        return None
    return (f"Panel {letter}'s fill", Target(row, Where("panel", p["kind"], pid, layer=j),
                                             words=f"panel {letter}'s fill"))


def _names(letters):
    return letters[0] if len(letters) == 1 else ", ".join(letters[:-1]) + " and " + letters[-1]


def bar_target(doc, part, words):
    """A colorbar's Target: a bar of one panel (one per panel) at the panel; a bar panels name
    (their bar group) at its first panel; one per row or column at that row or column; one for
    the figure at the figure.  Its note says which panels it serves and whose colours it shows;
    its links go to that panel's fill, to all colorbars and to the first panel's own colorbar
    settings."""
    from ..shell import bars
    names = nodes.letters(doc)
    ids = [i for i in part.panels if de.panel_by_id(doc, i) is not None]
    if not ids:
        return None
    try:
        bar = bars.bar_of(doc, ids[0])
    except Exception:  # noqa: BLE001  (a figure that can't be drawn now: as it was drawn)
        bar = None
    if bar is not None:  # (its controlling panel first: its settings are set there)
        ids = list(bar["members"])
    follows = bar["follows"] if bar is not None else len(ids) > 1
    first = de.panel_by_id(doc, ids[0])
    a = names.get(ids[0], "?")  # (after bar_of: the controlling panel)
    group = (first.get("colorbar") or {}).get("group")
    node, key, pid = None, ALL_BARS, None
    if group:
        key, pid = "panels[].colorbar.group", ids[0]
    elif part.mode in ("row", "col"):
        r, c = _cell(first)[:2]
        line = lines.node_of(part.mode, r if part.mode == "row" else c)
        if ids[0] in lines.members(doc, line):
            node, key, pid = line, PANEL_BAR, ids[0]
    elif len(ids) == 1 and part.mode not in ("shared", "figure"):
        key, pid = PANEL_BAR, ids[0]
    row = S.BY_KEY[key]
    where = nearest(doc, row, pid)
    if where is None:
        return None
    if len(ids) > 1:
        note = (f"Shared by panels {html.escape(_names([names.get(i, '?') for i in ids]))}. "
                f"Its colours {'follow' if follows else 'are'} panel {html.escape(a)}'s fill.")
    else:
        note = f"Panel {html.escape(a)}'s colorbar: its colours are its fill's."
    links = []
    fill = _fill_link(doc, ids[0], a)
    if fill is not None:
        links.append(fill)
    if key != ALL_BARS:
        links.append(("All colorbars", Target(S.BY_KEY[ALL_BARS], Where(), words="all colorbars")))
    if key != PANEL_BAR:
        own = nearest(doc, S.BY_KEY[PANEL_BAR], ids[0])
        if own is not None:
            links.append((f"Panel {a}'s colorbar", Target(S.BY_KEY[PANEL_BAR], own,
                                                          words=f"panel {a}'s colorbar")))
    return Target(row, where, node, words, note, tuple(links))
