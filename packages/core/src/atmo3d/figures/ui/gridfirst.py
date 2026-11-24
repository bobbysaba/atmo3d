"""The grid as the editor (docs-dev/figures-ui-plan.md, Phase 4; mockup B): what the drawer shows
at a row or column of the grid (its edits written to each of its panels: lines.py), a panel's own
changes with "Use the shared ones", the layer chips above the preview, and "What the grid varies"
in the Layout tool at the figure."""

import dataclasses
import html

import panel as pn

from .. import schema as S
from ..schema import KEEP, where as W
from ..schema.where import Where
from ..shell import docedit as de, nodes
from . import controls, lines
from .levels import spread
from .parts import SECTION, button, head, note

CHIP = """
.bk-btn { font-size: 12px !important; padding: 2px 10px !important; border-radius: 14px !important; }
"""


def look_rows(doc):
    """look_rows(where) for lines.own_changes: the Look tool's rows at a panel."""
    from .tools import rows_for
    return lambda pw: rows_for(doc, pw, "look")


# ------------------------------------------------------------ a row or a column picked
def build(frame, tool, doc, node):
    """A tool's drawer at a row or column."""
    from . import tools
    spots = spread(doc, node)
    if not spots:
        return [note("No panels in it.")]
    first = spots[0]
    if tool == "runs":
        return tools.runs(frame, doc, node)
    if tool == "marks":
        return [note("Annotations are the figure's, or a panel's: pick a panel for its own."),
                *tools.marks(frame, doc, nodes.FIGURE)]
    if tool == "layers":
        return layers(frame, doc, node)
    rows = [r for r in tools.rows_for(doc, first, tool) if r.key != "panels[].cell"]
    objs = []
    if tool == "layout":
        objs += varies_here(frame, doc, node)
        objs.append(share(frame, doc, node))
    if rows:
        opened = ("Panel",) if tool in ("layout", "times") else ()
        objs.append(frame.drawer(first, rows, opened=opened, spread=spots).panel)
    if tool == "layout":
        objs += add_here(frame, doc, node)
    return objs


def varies_here(frame, doc, node):
    """What its row (column) has that the others have otherwise, one control each."""
    axis, _ = lines.line_of(node)
    dims = lines.varies(doc)[axis]
    if not dims:
        return [note(f"Its panels have nothing in common the other {lines.AXES[axis].lower()}s "
                     "have otherwise (run, time, height or field).")]
    word = lines.AXES[axis]
    objs = [head(f"This {word.lower()}: what the {word.lower()}s differ in")]
    for dim in dims:
        objs += dim_control(frame, doc, node, dim)
    return objs


def dim_control(frame, doc, node, dim, label=None):
    """The control of what a row or column has of a dimension, written to each of its panels
    (the field: its first fill layer's, in each panel's Layers)."""
    key = lines.DIM_ROWS.get(dim)
    spots = spread(doc, node)
    if key is None or not spots:
        names = nodes.letters(doc)
        ps = [names[w.pid] for w in spots]
        v = next((lines.value(doc, de.panel_by_id(doc, w.pid), dim) for w in spots), None)
        return [note(f"{html.escape(label or lines.DIM_WORDS[dim])}: "
                     f"<b>{html.escape(lines.words(doc, dim, v, frame.shell.fields))}</b> (each "
                     f"panel's first fill: panels {', '.join(ps)}, Layers)")]
    row = S.BY_KEY[key]
    if label:
        row = dataclasses.replace(row, label=label)
    return [spread_control(frame, row, spots)]


def spread_control(frame, row, spots):
    """A schema row's control at the first of spots, an edit written to each: refreshed after
    every edit while shown."""
    host = frame.host
    ctl = controls.make(row, spots[0], host)
    held = []

    def show():
        if not nodes.still_there(host.doc, f"panel:{spots[0].pid}"):
            return
        held.append(1)
        try:
            v = W.value(host.doc, row, spots[0])
            if v is not KEEP:
                ctl.set(v)
        except Exception:  # noqa: BLE001  (a value the control can't show: as it is)
            pass
        finally:
            held.pop()

    def changed():
        if held:
            return
        try:
            shown = ctl.get()
        except Exception as e:  # noqa: BLE001
            host.say(f"{row.label}: {e}", True)
            return
        ctx = host.ctx

        def apply(d):
            for w in spots:
                W.write(d, row, w, shown, ctx)
        try:
            host.edit(apply)
        except (ValueError, IndexError, KeyError, TypeError) as e:
            host.say(f"{row.label}: {e}", True)
    show()
    ctl.watch(changed)
    frame.live.append(show)
    return ctl.widget


def share(frame, doc, node):
    """Its share of the figure's height (a row) or width (a column)."""
    axis, k = lines.line_of(node)
    n = lines.count(doc, axis)
    key = "heights" if axis == "row" else "widths"
    word = "height" if axis == "row" else "width"
    w = pn.widgets.FloatInput(name=f"Its share of the {word}", start=0.05, step=0.1, width=150,
                              description=f"Against the other {lines.AXES[axis].lower()}s' "
                                          "(1 each, unless set)")
    held = []

    def show():
        have = list((frame.shell.doc.get("grid") or {}).get(key) or [])
        held.append(1)
        try:
            w.value = float(have[k]) if k < len(have) else 1.0
        finally:
            held.pop()

    def on(ev):
        if held or ev.new is None:
            return

        def apply(d):
            grid = d.setdefault("grid", {})
            have = [float(x) for x in grid.get(key) or []]
            have += [1.0] * (n - len(have))
            have[k] = float(ev.new)
            grid[key] = [] if all(abs(x - 1.0) < 1e-9 for x in have) else have[:n]
        frame.host.edit(apply)
    show()
    w.param.watch(on, "value")
    frame.live.append(show)
    return w


def add_here(frame, doc, node):
    """A panel in its first free cell: a copy of its neighbour (lines.copy_from)."""
    axis, k = lines.line_of(node)
    free = [c for c in de.free_cells(doc) if c[0 if axis == "row" else 1] == k]
    if not free:
        return []
    kind = lines.kind_of(doc, node)
    return [button(f"+ Panel in this {lines.AXES[axis].lower()}",
                   lambda: frame.shell.grid.add_panel(kind, tuple(free[0])),
                   f"In its first free cell (row {free[0][0] + 1}, column {free[0][1] + 1}), as "
                   "the panel beside it is", primary=True)]


def layers(frame, doc, node):
    """At a row or column: the layers its panels share (the chips above the preview: their
    kind's) and its panels' own changes."""
    kind = lines.kind_of(doc, node)
    ids = lines.members(doc, node)
    objs = [note("The layers every panel draws are the shared ones: the chips above the "
                 "preview, or "),
            button(f"All {nodes.kind_name(kind, len(de.panels_of(doc, kind)))}: shared layers",
                   lambda: frame.pick(nodes.KIND_PREFIX + kind)),
            *own_list(frame, doc, ids)]
    return objs


# ------------------------------------------------------------ a panel's own changes
def own_list(frame, doc, ids, always=True):
    """The own changes of panels ids, each panel's with "Use the shared ones" (always: say
    there are none, too)."""
    names = nodes.letters(doc)
    rows = look_rows(doc)
    found = [(pid, lines.own_changes(doc, pid, frame.shell.fields, rows)) for pid in ids]
    found = [(pid, ch) for pid, ch in found if ch]
    if not found:
        return [head("Panels' own changes"), note("None: they draw the shared layers as they "
                                                  "are, with their kind's look.")] \
            if always else []
    objs = [head("Panels' own changes" if len(ids) > 1 else "Its own changes"),
            note("Marked with a dot in the preview. <b>Use the shared ones</b> takes back what "
                 "a panel changes of the shared layers and of its kind's look; layers of its "
                 "own stay.")]
    for pid, changes in found:
        said = "<br>".join(f"{names[pid]} · {html.escape(what)}" for what, _, _ in changes)
        objs.append(note(said))
        btns = []
        if any(how in ("over", "look") for _, how, _ in changes):
            btns.append(button("Use the shared ones", lambda pid=pid: use_shared(frame, pid),
                               f"Panel {names[pid]} back at the shared layers and its kind's "
                               "look. Undo takes it back"))
        if len(ids) > 1 or frame.shell.node != f"panel:{pid}":
            btns.append(button(f"Panel {names[pid]}", lambda pid=pid: frame.pick(
                f"panel:{pid}")))
        if btns:
            objs.append(pn.Row(*btns, margin=0))
    return objs


def use_shared(frame, pid):
    sh = frame.shell
    sh.edit(lambda d: lines.use_shared(d, pid, look_rows(d)), node=sh.node)


def dots(doc, boxes, fields=None):
    """{panel id: [x, y]} where the preview marks a panel with its own changes: its box's upper
    right corner."""
    rows = look_rows(doc)
    out = {}
    for p in doc.get("panels") or []:
        b = boxes.get(p["id"])
        if b is not None and lines.own_changes(doc, p["id"], fields, rows):
            out[str(p["id"])] = [float(b[1]), float(b[2])]
    return out


# ------------------------------------------------------------ the layer chips
def chips_kind(doc, node):
    """The kind whose shared layers the chips show: of what is picked, else the figure's main
    one (None: it has no shared layers)."""
    from .levels import kind_of
    kind = kind_of(doc, node) if node not in (nodes.FIGURE, nodes.RUNS) else None
    if kind is None:
        kinds = [p["kind"] for p in nodes.in_order(doc)]
        kind = max(kinds, key=kinds.count) if kinds else None
    return kind


class Chips:
    """The row above the preview: "In every plan view:" and a chip for each shared layer (it
    opens that layer in the Layers tool, at the kind), and "+ Layer"."""

    def __init__(self, frame):
        self.frame = frame
        self.said = pn.pane.HTML(margin=(6, 2, 0, 10), align="center")
        self.row = pn.FlexBox(flex_wrap="wrap", align_items="center",
                              sizing_mode="stretch_width", styles={"flex": "0 0 auto"})
        self._key = None

    def show(self, doc, node):
        kind = chips_kind(doc, node)
        ids = de.shared_ids(doc, kind) if kind in ("plan", "xsec") else []
        F = self.frame.shell.fields
        layers = doc.get("layers") or {}
        key = (kind, tuple((lid, nodes.layer_name(layers[lid], F),
                            layers[lid].get("on", True)) for lid in ids))
        if key == self._key:
            return
        self._key = key
        if kind is None or kind not in ("plan", "xsec"):
            self.row.objects = []
            self.row.visible = False
            return
        self.row.visible = True
        word = nodes.kind_name(kind, 0).rsplit(" (", 1)[0]
        self.said.object = f'<span class="cv-hint">In all {html.escape(word)}:</span>'
        objs = [self.said]
        for n_, (lid, name, on) in enumerate(key[1]):
            b = pn.widgets.Button(name=f"{n_ + 1}. {name}" + ("" if on else " (off)"),
                                  button_type="light", button_style="outline", height=28,
                                  margin=(2, 3), stylesheets=[CHIP],
                                  description="Open this shared layer (Layers, at all "
                                              f"{word})")
            b.on_click(lambda e, lid=lid, k=kind: self.open(k, lid))
            objs.append(b)
        add = pn.widgets.Button(name="+ Layer", button_type="primary", button_style="outline",
                                height=28, margin=(2, 3), stylesheets=[CHIP],
                                description=f"A layer all {word} draw: Layers, at the "
                                            "kind")
        add.on_click(lambda e, k=kind: self.open(k, None))
        objs.append(add)
        self.row.objects = objs

    def open(self, kind, lid):
        fr = self.frame
        if lid is not None:
            fr.folds[f"s:{lid}"] = True
        fr.tool = "layers"
        fr._lit()
        node = nodes.KIND_PREFIX + kind
        if fr.shell.node == node:
            fr.show(node)
        else:
            fr.pick(node)


# ------------------------------------------------------------ the figure's Layout
def varies_card(frame, doc):
    """What the grid varies: what the rows and the columns differ in, and each one's, editable
    in place (a row's or column's time, run or height written to each of its panels)."""
    vary = lines.varies(doc)
    card = pn.Card(title="What the grid varies", collapsed=not frame.folds.get("varies", True),
                   **SECTION)
    card.param.watch(lambda ev: frame.folds.__setitem__("varies", not ev.new), "collapsed")
    objs = []
    for axis, word in lines.AXES.items():
        n = lines.count(doc, axis)
        dims = vary[axis]
        if n < 2:
            continue
        said = ", ".join(lines.DIM_WORDS[d] for d in dims) if dims else "nothing in common"
        objs.append(note(f"<b>{word}s differ in</b>: {html.escape(said)}"))
        for dim in dims:
            for k in range(n):
                node = lines.node_of(axis, k)
                if not lines.still_there(doc, node):
                    continue
                objs += dim_control(frame, doc, node, dim,
                                    label=f"{word} {k + 1}: {lines.DIM_WORDS[dim].lower()}")
    if not objs:
        objs.append(note("One row and one column: nothing to vary."))
    else:
        objs.append(note("Click a header above or beside the preview for a row or column's "
                         "settings; <b>Fill panels</b> (below) steps them all through a list."))
    card.objects = objs
    return card
