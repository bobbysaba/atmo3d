"""What each tool of the figure's rail shows in its drawer (docs-dev/figures-ui-plan.md, 3.1,
3.3), at the place the level switch picks (levels.py): the settings as schema rows in the
generic drawer (drawer.py), and the actions that are not settings (add, move, copy, remove).

  Layout   the figure's size, title, grid and spacing, adding and filling panels; a panel's
           title, place and type; an inset's place and area
  Layers   the layers every panel of a kind shares, a panel's (shared ones as it draws them,
           its own), an inset's; the sections cross-sections show and section lines draw
  Look     everything else of the look, at the figure, a kind, a panel or an inset
  Marks    annotations, the contour key, the maximum and minimum marks
  Times    the panels' runs and times, animation
  Runs     the figure's runs

Which tool a schema row is in goes by its section (tool_of).  What is not a setting is in
actions.py (layers, sections, insets, annotations), fill.py (Fill panels), grid.py (adding,
copying and changing panels: the shell's `grid`), entries.py and scene.py (the other kinds'
lists), runs.py (the Runs tool)."""

import html

import panel as pn

from .. import draw as figdraw
from ..choices import ANN_KINDS, SIZE_PRESETS, TYPE_LABEL
from ..draw.base import ann_on
from ..schema.where import Where
from ..shell import docedit as de, nodes
from ..style import STYLE_LABELS
from . import actions as A, drawer as D, entries as E, runs as R, scene as SC
from .grid import grid_map, kind_options
from .fill import fill_card
from .levels import where_of
from .parts import button, head, note  # noqa: F401  (tools.note: the frame's)

TOOLS = (
    ("layout", "Layout", "layout-grid", "The figure's size and grid, the panels' places, titles "
                                        "and types; adding and filling panels"),
    ("layers", "Layers", "stack-2", "What the panels draw: the layers all panels of a kind "
                                    "share, and a panel's own"),
    ("look", "Look", "palette", "Fonts, axes, colorbars, legends, panel labels: the look, for "
                                "the figure, a kind of panel or one panel"),
    ("marks", "Marks", "pencil", "Annotations, section lines, the contour key and the maximum "
                                 "and minimum marks"),
    ("times", "Times", "clock", "Each panel's run and time; animation"),
    ("runs", "Runs", "database", "The runs the figure shows: their labels, colours, time zeros "
                                 "and storm tracks"))
TITLES = {key: label for key, label, _, _ in TOOLS}

LAYOUT = {"Figure", "Grid", "Spacing", "Panel", "Where it sits", "Area", "Region and resolution"}
MARKS = {"Annotations", "Contour key", "Maximum and minimum"}
SECTIONS = {"Section line", "Floor", "Streamlines"}  # (what cross-sections, scenes show: Layers)
TIMES = {"Animation"}
TIMES_KEYS = {"panels[].run", "panels[].time_s"}
ELSEWHERE = {"Export"}  # (the Export dialog's)


def tool_of(row):
    """The rail tool a schema row is shown in (None: the Export dialog's)."""
    part = D.part_of(row)
    if row.types or part == "scene item" or row.section in SECTIONS:
        return "layers"
    if row.key in TIMES_KEYS or row.section in TIMES:
        return "times"
    if part == "run":
        return "runs"
    if row.section in ELSEWHERE:
        return None
    if row.section in LAYOUT:
        return "layout"
    if row.section in MARKS:
        return "marks"
    return "look"


def rows_for(doc, where, tool, part=None):
    """The rows of a tool at a place."""
    return [r for r in D.rows_at(doc, where, part) if tool_of(r) == tool]


ACTIONS = {"up": ("↑", "Earlier: drawn under the next"), "down": ("↓", "Later: drawn over"),
           "copy": ("⧉", "A copy, after it"), "remove": ("✕", "Remove (Undo brings it back)")}


class Item:
    """One thing of a list (a layer, an annotation, a section): a fold whose drawer is made when
    it is opened; its moves (up, down, copy, remove: f()) a row of buttons in it, extras(): what
    is shown above the settings."""

    def __init__(self, frame, key, title, where, rows, moves=None, extras=None, opened=False):
        self.frame, self.key, self.where, self.rows = frame, key, where, rows
        self.moves, self.extras = moves or {}, extras
        self.drawer = None
        self.body = pn.Column(margin=0, sizing_mode="stretch_width")
        opened = frame.folds.get(key, opened)
        self.card = pn.Card(self.body, title=title, collapsed=not opened, margin=(2, 0),
                            sizing_mode="stretch_width")
        self.card.param.watch(self._fold, "collapsed")
        if opened:
            self._build()

    def _fold(self, ev):
        self.frame.folds[self.key] = not ev.new
        if not ev.new and self.drawer is None:
            self._build()

    def _build(self):
        bar = []
        for k in ("up", "down", "copy", "remove"):
            if k in self.moves:
                label, tip = ACTIONS[k]
                b = pn.widgets.Button(name=label, width=36, height=28, margin=(2, 2),
                                      button_type="light", button_style="outline",
                                      description=tip)
                b.on_click(lambda e, f=self.moves[k]: f())
                bar.append(b)
        objs = [pn.Row(*bar, margin=0)] if bar else []
        objs += list(self.extras()) if self.extras else []
        sections = list(dict.fromkeys(r.section for r in self.rows))
        self.drawer = self.frame.drawer(self.where, self.rows,
                                        opened=sections[:1] if len(sections) <= 3 else ())
        self.body.objects = objs + [self.drawer.panel]


# ------------------------------------------------------------ the tools
def build(frame, tool, doc, node):
    """The drawer's contents for a tool at node (a row or column: gridfirst's)."""
    if nodes.is_line(node):
        from . import gridfirst
        return gridfirst.build(frame, tool, doc, node)
    return {"layout": layout, "layers": layers, "look": look, "marks": marks, "times": times,
            "runs": runs}[tool](frame, doc, node)


# ---- Layout
def layout(frame, doc, node):
    grid, where = frame.shell.grid, where_of(doc, node)
    if where.level == "figure":
        objs = [frame.drawer(where, rows_for(doc, where, "layout"), opened=("Figure",)).panel,
                _size_tools(frame, doc)]
        objs += [head("Panels"), grid.type_widget(doc), note("Where the panels sit:"),
                 grid_map(doc), *grid.aside_objs(doc), *grid.add_objs(doc)]
        from . import gridfirst
        objs.append(gridfirst.varies_card(frame, doc))
        if any(p["kind"] == "plan" for p in doc.get("panels") or []):
            objs.append(fill_card(frame))
        for text in doc.get("notes") or []:
            objs.append(note(html.escape(str(text))))
        return objs
    if where.level == "kind":
        objs = [frame.drawer(where, rows_for(doc, where, "layout")).panel,
                note("A panel's place, title and type: pick the panel (click it in the "
                     "preview).")]
        if where.kind == "scene":
            objs += SC.region_tools(frame.shell, where)
            objs.append(button("+ 3D scene panel", lambda: grid.add_panel("scene"),
                               "In the first free cell, or a new row or column", primary=True))
        elif where.kind in E.ENTRY_KINDS:
            objs.append(button(f"+ {E.panel_word(where.kind)} panel",
                               lambda: grid.add_panel(where.kind),
                               "In the first free cell, or a new row or column", primary=True))
            if where.kind in E.SERIES:
                objs += A.titles_objs(frame.shell, where.kind)
        if where.kind == "xsec":
            objs += [button("+ Cross-section panel", lambda: grid.add_panel("xsec"),
                            "Like the last, showing a new section: an x–z one's y–z twin. In "
                            "the first free cell, or a new row or column", primary=True),
                     *A.titles_objs(frame.shell, "xsec")]
        return objs
    pid = where.pid
    if where.level == "inset":
        iid = where.iid
        return [frame.drawer(where, rows_for(doc, where, "layout"),
                             opened=("Where it sits", "Area")).panel,
                note("Dragging in the preview sets what it shows and where it sits (Click, "
                     "above it)."),
                button("Remove this inset", lambda: frame.shell.edit(
                    lambda d: de.remove_inset(d, pid, iid), node=f"panel:{pid}"))]
    pw = Where("panel", where.kind, pid)
    objs = [frame.drawer(pw, rows_for(doc, pw, "layout"), opened=("Panel",)).panel]
    if where.kind == "scene":
        objs += SC.region_tools(frame.shell, pw)
    if where.kind == "plan" and _shares_range(doc, pw):
        objs.append(note("Axes and ticks has panels share a range: this panel's axes stretch to "
                         "it, so they can show more than its own area."))
    objs += _panel_tools(frame, doc, pid)
    p = de.panel_by_id(doc, pid)
    if p["kind"] == "xsec":
        objs.append(button("One per run", lambda: A.one_per_run(frame.shell, pid),
                           "A copy of this panel for each other run, down its column, at the "
                           "same time since time zero"))
    if p["kind"] in de.INSET_KINDS:
        n = len(p.get("insets") or [])
        objs += [head("Zoom insets" + (f" ({n})" if n else "")),
                 note("A box in the panel showing part of it larger. Or pick <b>Drag: new zoom "
                      "inset</b> (Click, above the preview) and drag over what to zoom in on."),
                 pn.Row(button("+ Zoom inset", lambda: A.add_inset(frame.shell, pid),
                               "Of the middle of what the panel shows; then change it"),
                        *[button(f"Inset {k + 1}", lambda i=i: frame.pick(
                            f"inset:{pid}:{i['id']}")) for k, i in
                          enumerate(p.get("insets") or [])], margin=0)]
    return objs


def _shares_range(doc, pw):
    from .. import schema as S
    from ..schema import KEEP, where as W
    v = W.value(doc, S.BY_KEY["look.axes.share"], pw)
    return v not in (None, KEEP, "none")


def _size_tools(frame, doc):
    """A size preset, and Fit height (the old figure node's, beside the Size row)."""
    shell = frame.shell
    preset = pn.widgets.Select(name="Size preset", options=SIZE_PRESETS, value="", width=200)
    fit = pn.widgets.Button(name="Fit height", height=32, align="end", button_type="light",
                            button_style="outline", margin=(4, 4),
                            disabled=not shell.can_follow(doc),
                            description="The height for the width and the panels; it then "
                                        "follows them, until a size is typed" if
                            shell.can_follow(doc) else "Only a figure of one kind of panel, in "
                            "equal cells, has an automatic size (a 3D scene's is typed)")

    def on_preset(ev):
        if not ev.new:
            return
        h = float(shell.doc["size"][1])
        if "x" in ev.new:
            size, auto = [float(v) for v in ev.new.split("x")], False
        else:
            size = [float(ev.new), h]
            auto = shell.can_follow() and shell.doc["panels"][0]["kind"] in ("plan", "xsec",
                                                                             "table")
        shell.edit(lambda d: d.update(size=size, size_auto=auto), node=shell.node)

    def on_fit(ev):
        def apply(d):
            d["size_auto"] = True
            now = de.kind_size(d)
            if now is not None:
                d["size"] = list(now)
        shell.edit(apply, node=shell.node)

    preset.param.watch(on_preset, "value")
    fit.on_click(on_fit)
    return pn.Row(preset, fit, margin=0)


def _panel_tools(frame, doc, pid):
    """A panel's type, a copy of it, removing it."""
    shell, grid = frame.shell, frame.shell.grid
    kind = de.panel_by_id(doc, pid)["kind"]
    type_w = pn.widgets.Select(name="Panel type", options=kind_options(kind), value=kind,
                               description="Change this panel to another type, in the same "
                                           "cell. What it showed is replaced; Undo takes it "
                                           "back.")
    type_w.param.watch(lambda ev: grid.set_kind([pid], ev.new), "value")
    rm = button("Remove this panel", lambda: shell.edit(
        lambda d: de.remove_panel(d, pid), node=nodes.KIND_PREFIX + kind), "Its cell stays empty")
    rm.disabled = len(doc["panels"]) < 2
    return [type_w, pn.Row(button("Copy this panel", lambda: grid.copy_panel(pid),
                                  "Into the first free cell, or a new row or column"), rm,
                           margin=0)]


# ---- Layers
def _add_menu(frame, add, name):
    """A menu of the types of layer; add(type) (Map boundaries: a run on a map projection;
    Parcels: with parcels)."""
    ed = frame.shell.ed
    on_map = getattr(ed.run, "geo", None) is not None
    items = [(label, t) for t, label in TYPE_LABEL.items()
             if (t != "parcels" or frame.shell.v.pf is not None)
             and (t != "boundaries" or on_map)]
    menu = pn.widgets.MenuButton(name=name, items=items, button_type="primary",
                                 button_style="outline", height=32, margin=(4, 4))
    menu.on_click(lambda ev: add(ev.new))
    return menu


def _new_layer(frame, t):
    lay = A.new_layer(frame.shell, t)
    if lay is None:
        frame.shell.say(A.NO_SETS, True)
    return lay


def layers(frame, doc, node):
    where = where_of(doc, node)
    if where.kind == "scene" and where.level in ("kind", "panel"):
        return SC.layers(frame, doc, Where(where.level, "scene", where.pid))
    if where.kind in E.ENTRY_KINDS and where.level == "kind":
        return E.kind_layers(frame, doc, where.kind)
    if where.kind in E.ENTRY_KINDS and where.level == "panel":
        return E.panel_layers(frame, doc, where, node)
    if where.level == "figure":
        kinds = list(dict.fromkeys(p["kind"] for p in nodes.in_order(doc)))
        return [note("Each kind of panel has its layers: pick one."),
                *[button(f"All {nodes.kind_name(k, len(de.panels_of(doc, k)))}",
                         lambda k=k: frame.pick(nodes.KIND_PREFIX + k)) for k in kinds]]
    if where.level == "kind":
        objs = _shared_layers(frame, doc, where.kind)
        if where.kind == "xsec" or where.kind == "plan" and A.draws_sections(doc) and \
                doc.get("sections"):
            secs = A.sections_list(frame, doc)
            objs = secs + objs if where.kind == "xsec" else objs + secs
        return objs
    if where.level == "inset":
        return _inset_layers(frame, doc, where)
    objs = _panel_layers(frame, doc, where, node)
    if where.kind == "xsec" and where.layer is None:
        objs = A.panel_section(frame, doc, where.pid) + [head("Layers")] + objs
    if where.layer is None:  # (what it changes of what it shares: Phase 4.3)
        from . import gridfirst
        objs = objs + gridfirst.own_list(frame, doc, [where.pid], always=False)
    return objs


def _layer_title(doc, lay, fields, n, shared=None, over=False):
    name = nodes.layer_name(lay, fields)
    off = "" if lay.get("on", True) else " (off)"
    tail = " · shared" + (", changed here" if over else "") if shared else ""
    return f"{n + 1}. {name}{off}{tail}"


def _shared_layers(frame, doc, kind):
    shell = frame.shell
    names = nodes.letters(doc)
    mine = de.panels_of(doc, kind)
    ids = de.shared_ids(doc, kind)

    def step(fn, lid, *args):
        shell.edit(lambda d: fn(d, kind, lid, *args), node=shell.node)

    def add(t):
        lay = _new_layer(frame, t)
        if lay is None:
            return

        def apply(d):
            frame.folds[f"s:{de.add_shared(d, kind, lay)}"] = True
        shell.edit(apply, node=shell.node)

    def copied(lid):
        def apply(d):
            frame.folds[f"s:{de.copy_shared(d, kind, lid)}"] = True
        shell.edit(apply, node=shell.node)

    objs = [note("Drawn in this order, the last on top. A change reaches every panel, but what a "
                 "panel has set for itself (marked there)."),
            _add_menu(frame, add, "+ Add a layer")]
    for n, lid in enumerate(ids):
        lay = doc["layers"][lid]
        where = Where("kind", kind, layer=lid)
        moves = dict(copy=lambda i=lid: copied(i), remove=lambda i=lid: step(de.remove_shared, i))
        if n > 0:
            moves["up"] = lambda i=lid: step(de.move_shared, i, -1)
        if n < len(ids) - 1:
            moves["down"] = lambda i=lid: step(de.move_shared, i, 1)
        objs.append(Item(frame, f"s:{lid}", _layer_title(doc, lay, shell.fields, n),
                         where, D.rows_at(doc, where), moves,
                         extras=lambda i=lid: _shared_extras(frame, kind, i),
                         opened=n == 0).card)
    if not ids:
        objs.append(note("No shared layers: add one above."))
    own = [names[p["id"]] for p in mine if any("ref" not in x for x in p.get("layers") or [])]
    if own:
        objs.append(note("Panel" + ("s " if len(own) > 1 else " ") + ", ".join(own)
                         + " also draw" + ("" if len(own) > 1 else "s")
                         + " layers of their own: pick the panel."))
    if len(ids) > 1:
        objs.append(A.copy_look_card(frame.shell, doc, ids))
    return objs


def _shared_extras(frame, kind, lid):
    """Which panels draw a shared layer, and which of them have it otherwise."""
    shell = frame.shell
    doc = shell.doc
    names = nodes.letters(doc)
    mine = de.panels_of(doc, kind)
    pick = pn.widgets.CheckButtonGroup(
        name="In panels", options={names[p["id"]]: p["id"] for p in mine},
        value=[p["id"] for p in mine if de.draws(doc, p, lid)], button_type="light",
        button_style="outline", margin=(2, 4), height=28)

    def on_pick(ev):
        def apply(d):
            for p in de.panels_of(d, kind):
                now = p["id"] in ev.new
                if now != de.draws(d, p, lid):
                    de.in_panel(d, p, lid, now)
        shell.edit(apply)

    pick.param.watch(on_pick, "value")
    objs = [note("Drawn in panels:"), pick]
    others = de.other_kinds_with(doc, kind, lid)
    if others:
        n = len(others)
        objs += [note(f"<b>Panel{'s' if n > 1 else ''} "
                      + ", ".join(names[p["id"]] for p in others)
                      + f" of another kind draw{'' if n > 1 else 's'} this layer too:</b> "
                      "changes here reach them."),
                 button("Keep apart", lambda: shell.edit(
                     lambda d: de.split_shared(d, kind, lid), node=shell.node),
                     "These panels get a copy of this layer of their own; the others keep this "
                     "one")]
    differ = de.differing(doc, lid, kind)
    if differ:
        n = len(differ)
        objs += [note(f"{n} panel{'s differ' if n > 1 else ' differs'} ("
                      + ", ".join(names[i] for i in differ)
                      + "): what they set stays as it is when this changes."),
                 button("↺ All as shared", lambda: shell.edit(
                     lambda d: de.clear_shared_over(d, lid, kind), node=shell.node),
                     "No panel has this layer otherwise any more")]
    return objs


def _panel_layers(frame, doc, where, node):
    shell, pid = frame.shell, where.pid
    p = de.panel_by_id(doc, pid)
    lays = figdraw.panel_layers(doc, p)

    def step(fn, j, *args):
        shell.edit(lambda d: fn(d, de.panel_by_id(d, pid), j, *args), node=shell.node)

    def add(t):
        lay = _new_layer(frame, t)
        if lay is None:
            return

        def apply(d):
            q = de.panel_by_id(d, pid)
            de.add_own(q, lay)
            frame.folds[f"p:{pid}:{len(de.places(d, q)) - 1}"] = True
            de.apply_heights(d, [q])
        shell.edit(apply, node=shell.node)

    if node.startswith("layer:"):  # (one layer, picked: itself)
        j = where.layer
        ref, lay = lays[j]
        return [*_layer_head(frame, doc, p, j, ref),
                frame.drawer(where, D.rows_at(doc, where), opened=("Field", "Layer")).panel]
    objs = [note("For this panel alone: a shared layer's other settings follow "
                 f"<b>All {nodes.kind_name(p['kind'], len(de.panels_of(doc, p['kind'])))}</b>."),
            _add_menu(frame, add, "+ Add a layer to this panel")]
    for j, (ref, lay) in enumerate(lays):
        w = Where("panel", where.kind, pid, layer=j)
        moves = dict(copy=lambda j=j: step(de.copy_in_panel, j),
                     remove=lambda j=j: step(de.remove_in_panel, j))
        if j > 0:
            moves["up"] = lambda j=j: step(de.move_in_panel, j, -1)
        if j < len(lays) - 1:
            moves["down"] = lambda j=j: step(de.move_in_panel, j, 1)
        over = bool(ref) and bool(_over(p, j))
        objs.append(Item(frame, f"p:{pid}:{j}",
                         _layer_title(doc, lay, shell.fields, j, ref, over), w,
                         D.rows_at(doc, w), moves,
                         extras=lambda j=j, ref=ref: _layer_head(frame, shell.doc, p, j, ref),
                         opened=len(lays) == 1).card)
    if not lays:
        objs.append(note("No layers here: add one above."))
    return objs


def _over(p, j):
    items = p.get("layers") or []
    return (items[j].get("over") or {}) if j < len(items) else {}


def _layer_head(frame, doc, p, j, ref):
    """What a layer of a panel says above its settings: shared or its own, and taking back
    what the panel changed of a shared one."""
    shell, pid = frame.shell, p["id"]
    if not ref:
        return [note("A layer of this panel alone."), *_bar_notes(frame, doc, p, j)]
    back = button("↺ Use the shared settings", lambda: shell.edit(
        lambda d: de.clear_over(d, de.panel_by_id(d, pid), j), node=shell.node),
        "Everything this panel changed of the layer back to the shared one")

    def follow():
        p = de.panel_by_id(shell.doc, pid)
        back.visible = p is not None and bool(_over(p, j))
    follow()
    frame.live.append(follow)
    return [note("A shared layer, as this panel draws it: what is set here stays here (marked); "
                 "↺ takes a setting back."), back, *_bar_notes(frame, doc, p, j)]


def _bar_of(doc, pid):
    from ..shell import bars
    try:
        return bars.bar_of(doc, pid)
    except Exception:  # noqa: BLE001  (a figure that can't be drawn yet)
        return None


def _bar_notes(frame, doc, p, j):
    """Layer j of panel p speaks for its colorbar: where the bar's settings are, and whether its
    colours follow another panel's (with Match the bar when they differ)."""
    from ..shell import bars
    pid, shell = p["id"], frame.shell
    if bars.place(doc, p) != j:
        return []
    bar = _bar_of(doc, pid)
    if bar is None:
        return []
    first = bar["members"][0]
    if first == pid or not bar["follows"]:
        return [note("Its colorbar's label, ticks and arrows: the panel's Look, Colorbar.")]
    letter = nodes.letters(doc)[first]
    if not bars.colours_differ(doc, bar, pid):
        return [note(f"Its colours follow panel {letter}, whose colorbar it shares.")]

    def match():
        def apply(d):
            now = bars.bar_of(d, pid)
            if now is not None:
                bars.match_colours(d, now, pid)
        shell.edit(apply, node=shell.node)
    return [note(f'<span style="color:#fcd34d">⚠ Its colours differ from panel {letter}\'s, so '
                 "the colorbar is wrong for this panel.</span>"),
            button("Match the bar", match, "Its colours as panel " + letter + "'s")]


def _bar_follower(frame, doc, pid):
    """A panel on a bar another panel controls: which, to go there."""
    bar = _bar_of(doc, pid)
    if bar is None or bar["members"][0] == pid:
        return []
    first = bar["members"][0]
    letter = nodes.letters(doc)[first]
    return [note(f"Shares the bar with panel {letter}: its label, ticks and arrows are set "
                 "there."), button(f"Go to panel {letter}", lambda: frame.pick(f"panel:{first}"))]


def _inset_layers(frame, doc, where):
    shell, pid, iid = frame.shell, where.pid, where.iid
    p = de.panel_by_id(doc, pid)
    inset = de.inset_by_id(p, iid)
    own = inset.get("layers") is not None
    node = f"inset:{pid}:{iid}"
    same = pn.widgets.Checkbox(name="The panel's layers", value=not own, margin=(4, 8))
    same.param.watch(lambda ev: shell.edit(
        lambda d: de.own_inset_layers(d, pid, iid, not ev.new), node=node), "value")
    objs = [same]
    if not own:
        return objs + [note("As the panel has them, whatever changes there. Untick for layers "
                            "of its own, starting from these.")]

    def step(fn, j, *args):
        shell.edit(lambda d: fn(d, de.inset_by_id(de.panel_by_id(d, pid), iid), j, *args),
                   node=shell.node)

    def add(t):
        lay = _new_layer(frame, t)
        if lay is None:
            return

        def apply(d):
            q = de.panel_by_id(d, pid)
            i = de.inset_by_id(q, iid)
            de.add_own(i, lay)
            frame.folds[f"i:{iid}:{len(de.places(d, i)) - 1}"] = True
            de.apply_heights(d, [q])
        shell.edit(apply, node=shell.node)

    lays = figdraw.panel_layers(doc, inset)
    objs += [note("Its own list: what is added, removed or changed here stays here."),
             _add_menu(frame, add, "+ Add a layer to this inset")]
    for j, (ref, lay) in enumerate(lays):
        w = Where("inset", where.kind, pid, iid, layer=j)
        moves = dict(copy=lambda j=j: step(de.copy_in_panel, j),
                     remove=lambda j=j: step(de.remove_in_panel, j))
        if j > 0:
            moves["up"] = lambda j=j: step(de.move_in_panel, j, -1)
        if j < len(lays) - 1:
            moves["down"] = lambda j=j: step(de.move_in_panel, j, 1)
        objs.append(Item(frame, f"i:{iid}:{j}", _layer_title(doc, lay, shell.fields, j, ref),
                         w, D.rows_at(doc, w), moves, opened=len(lays) == 1).card)
    return objs


# ---- Look
def look(frame, doc, node):
    where = where_of(doc, node)
    if where.layer is not None:  # (a layer picked: the look of its panel)
        where = Where("panel", where.kind, where.pid)
    rows = rows_for(doc, where, "look")
    objs = []
    if where.level == "figure":
        menu = pn.widgets.MenuButton(name="Apply a style preset", button_type="light",
                                     button_style="outline", height=32, margin=(4, 4),
                                     items=[(label, key) for key, label in STYLE_LABELS.items()])
        menu.on_click(lambda e: frame.shell.apply_style(e.new))
        objs.append(menu)
        if doc.get("groups"):
            objs.append(note("This figure was made of parts: each part's colorbar, legend and "
                             "ticks stay its own, whatever is set here."))
    objs.append(frame.drawer(where, rows).panel)
    if where.kind == "scene" and where.level in ("kind", "panel"):
        objs += SC.camera_tools(frame.shell, where)
    if where.level == "panel":
        objs += _bar_follower(frame, doc, where.pid)
    if where.level == "kind":
        objs.append(note("A panel's own look: pick the panel. What a panel sets for itself is "
                         "marked there, and changes here skip it."))
        own = own_look(doc, where.kind)
        if own:
            objs.append(note("Set in a panel alone, so changes here skip it: panel"
                             + ("s " if len(own) > 1 else " ") + ", ".join(own) + "."))
    return objs


def own_look(doc, kind):
    """The letters of a kind's panels that set some of the look for themselves."""
    from ..schema import where as W
    names = nodes.letters(doc)
    out = []
    for p in de.panels_of(doc, kind):
        pw = Where("panel", kind, p["id"])
        if any(W.own(doc, r, pw) for r in rows_for(doc, pw, "look")):
            out.append(names[p["id"]])
    return out


# ---- Marks
def marks(frame, doc, node):
    shell, where = frame.shell, where_of(doc, node)
    pid = where.pid
    objs = []
    if where.level == "figure":
        rows = rows_for(doc, where, "marks")
        if rows:
            objs.append(frame.drawer(where, rows).panel)
    objs.append(head("Annotations"))
    kind = pn.widgets.Select(name="", options=ANN_KINDS, width=140, margin=(4, 4))
    anns = doc.get("annotations") or []

    def on_add():
        frame.folds[f"ann:{len(shell.doc.get('annotations') or [])}"] = True  # (open)
        A.add_annotation(shell, kind.value, pid)
    add = button("+ Add", on_add, primary=True)
    objs += [note("Text, markers, arrows, lines, boxes and circles, or an entry of its own in the "
                  "legends. <b>Click</b> (above the preview) places them by clicking and moves "
                  "them by dragging." + (" These are the ones on this panel." if pid is not None
                                         else "")),
             pn.Row(kind, add, margin=0)]
    for n, a in enumerate(anns):
        if pid is not None and not ann_on(a, pid):
            continue
        w = Where("figure", item=n)
        objs.append(Item(frame, f"ann:{n}", f"{n + 1}. {_ann_name(a)}", w,
                         [r for r in D.rows_at(doc, w, "annotation")],
                         dict(remove=lambda n=n: shell.edit(
                             lambda d: d["annotations"].pop(n), node=shell.node)),
                         extras=lambda a=a: _ann_gone(doc, a),
                         opened=len(anns) == 1).card)
    return objs


def _ann_gone(doc, a):
    """A note on an annotation whose panels are all gone (it stays, drawn nowhere, until its
    panels are set)."""
    ids = de.ann_panels(a)
    have = {p["id"] for p in doc.get("panels") or []}
    if -1 in ids or any(i in have for i in ids):
        return []
    return [note("Drawn in no panel now: no such panel (it was removed). Set its panels.")]


def _ann_name(a):
    kind = next((k for k, v in ANN_KINDS.items() if v == a.get("kind")), a.get("kind", ""))
    text = str(a.get("text") or "").strip()
    return f"{kind}: “{text[:30]}”" if text else kind


# ---- Times
def times(frame, doc, node):
    where = where_of(doc, node)
    if where.level in ("panel", "inset"):
        pw = Where("panel", where.kind, where.pid)
        objs = [frame.drawer(pw, rows_for(doc, pw, "times"), opened=("Panel", "Animation")).panel]
        if where.kind in E.ENTRY_KINDS:
            objs.insert(0, note(f"Each of its {E.SPEC[where.kind].head.lower()} has its own "
                                "run and time: Layers, Run and time."))
        if where.level == "inset":
            objs.insert(0, note("An inset shows its panel's run and time."))
        return objs
    kind = where.kind
    shown = [p for p in nodes.in_order(doc) if kind is None or p["kind"] == kind]
    names = nodes.letters(doc)
    objs = [note("Each panel's run and time. The slider under the preview moves them all "
                 "together; <b>Keep this time</b> keeps where it is.")]
    for p in shown:
        pw = Where("panel", p["kind"], p["id"])
        rows = [r for r in rows_for(doc, pw, "times") if r.key in TIMES_KEYS]
        if rows:
            objs += [head(f"Panel {names[p['id']]}"), frame.drawer(pw, rows, opened=("Panel",)).panel]
    if kind is not None:
        anim = [r for r in rows_for(doc, where, "times") if r.key not in TIMES_KEYS]
        if anim:
            objs.append(frame.drawer(where, anim).panel)
    return objs


# ---- Runs
def runs(frame, doc, node):
    return R.runs(frame, doc)
