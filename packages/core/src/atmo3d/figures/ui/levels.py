"""The level switch at the top of the figure's drawer (docs-dev/figures-ui-plan.md, 3.2): where
an edit made in the drawer goes, "Figure · All plan views · Panel b · Layer", following what
is picked in the preview.  It replaces the old tree.

What is picked is a node of figures/shell/nodes.py (figure, kind:<kind>, panel:<id>,
inset:<panel id>:<inset id>, layer:<panel id>:<place>, row:<r>, col:<c>); the switch offers the
figure, every kind of the figure, and the last row or column, or panel picked with its inset or
layer, so going up to All plan views and back down to the panel is one click each.  where_of()
gives the schema's place (schema/where.py) of a node; a row or column's is its first panel's,
and spread() the places of each of its panels, which its edits are written to (lines.py)."""

import panel as pn

from ..schema.where import Where
from ..shell import nodes

SWITCH = """
.bk-btn { font-size: 12px !important; padding: 3px 9px !important; }
.bk-btn-group .bk-btn.bk-active { background-color: rgba(34,211,238,.20) !important;
                                  color: #a5f3fc !important; }
"""


def kind_of(doc, node):
    """The kind of panel a node speaks for (None: the figure)."""
    if node.startswith(nodes.KIND_PREFIX):
        return node.partition(":")[2]
    if nodes.is_line(node):
        from . import lines
        return lines.kind_of(doc, node)
    p = nodes.panel_of(doc, node)
    return None if p is None else p["kind"]


def where_of(doc, node):
    """The schema's place of a node: the figure (and the runs), a kind, a panel, an inset, or
    a layer of a panel (by its place in the panel's layers)."""
    kind = kind_of(doc, node)
    if node.startswith(nodes.KIND_PREFIX):
        return Where("kind", kind)
    if nodes.is_line(node):
        ids = spread(doc, node)
        return ids[0] if ids else Where()
    p = nodes.panel_of(doc, node)
    if p is None:
        return Where()
    if node.startswith("inset:"):
        return Where("inset", kind, p["id"], int(node.rsplit(":", 1)[1]))
    if node.startswith("layer:"):
        return Where("panel", kind, p["id"], layer=int(node.rsplit(":", 1)[1]))
    return Where("panel", kind, p["id"])


def spread(doc, node):
    """The places an edit at node is written to: a row or column's, one for each of its panels
    of its kind (lines.members); any other node's, its own."""
    if not nodes.is_line(node):
        return [where_of(doc, node)]
    from . import lines
    kind = lines.kind_of(doc, node)
    return [Where("panel", kind, pid) for pid in lines.members(doc, node)]


def deeper(node):
    """Whether a node is below a kind: a row or column, a panel, its inset or one of its
    layers."""
    return node.split(":", 1)[0] in ("panel", "inset", "layer", "row", "col")


def ladder(doc, node, last=None):
    """[(label, node)] the switch offers: the figure, All <kind> for each kind, then the panel
    of `node` (or of `last`, the last panel, inset or layer picked, while it is there) with its
    inset or layer."""
    panels = nodes.in_order(doc)
    out = [("Figure", nodes.FIGURE)]
    for kind in dict.fromkeys(p["kind"] for p in panels):
        n = sum(p["kind"] == kind for p in panels)
        out.append((f"All {nodes.kind_name(kind, n)}", f"{nodes.KIND_PREFIX}{kind}"))
    low = node if deeper(node) else last
    if low is None or not deeper(low) or not nodes.still_there(doc, low):
        return out
    if nodes.is_line(low):
        from . import lines
        names = nodes.letters(doc)
        ids = lines.members(doc, low)
        return out + [(f"{lines.name(low)} · {', '.join(names[i] for i in ids)}", low)]
    p = nodes.panel_of(doc, low)
    out.append((f"Panel {nodes.letters(doc)[p['id']]}", f"panel:{p['id']}"))
    if low.startswith("inset:"):
        at = [int(i["id"]) for i in p.get("insets") or []].index(int(low.rsplit(":", 1)[1]))
        out.append((f"Inset {at + 1}", low))
    elif low.startswith("layer:"):
        from .. import draw as figdraw
        j = int(low.rsplit(":", 1)[1])
        lay = figdraw.panel_layers(doc, p)[j][1]
        out.append((f"Layer: {nodes.layer_name(lay)}", low))
    return out


def reach(doc, node):
    """What an edit made at node reaches, in words (the old inspector's line)."""
    return nodes.scope(doc, node)


class LevelSwitch:
    """The switch: a row of buttons, the one of the node picked lit; pick(node) is called when
    another is clicked."""

    def __init__(self, pick):
        self._pick, self._held = pick, False
        self.last = None  # (the last panel, inset or layer picked)
        self.buttons = pn.widgets.RadioButtonGroup(
            options={}, button_type="light", button_style="outline", height=30,
            margin=(4, 4, 0, 4), stylesheets=[SWITCH], orientation="horizontal",
            sizing_mode="stretch_width")
        self.said = pn.pane.HTML(margin=(0, 6), sizing_mode="stretch_width")
        self.panel = pn.Column(self.buttons, self.said, margin=0, sizing_mode="stretch_width")
        self.buttons.param.watch(self._on, "value")

    def show(self, doc, node):
        if deeper(node):
            self.last = node
        opts = {label: n for label, n in ladder(doc, node, self.last)}
        self._held = True
        try:
            self.buttons.param.update(options=opts, value=node if node in opts.values()
                                      else nodes.FIGURE)
        finally:
            self._held = False
        self.said.object = f'<div class="cv-hint">{reach(doc, node)}</div>'

    def _on(self, ev):
        if not self._held and ev.new is not None:
            self._pick(ev.new)
