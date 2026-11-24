"""The Figure workspace's layout, as the viewer's (docs-dev/figures-ui-plan.md, 3.1; mockup A):
a top bar (the runs, Find, New, undo and redo, Auto-redraw, Redraw, Export), a tool rail (Layout,
Layers, Look, Marks, Times, Runs: tools.py), one drawer at a time beside it with the level switch
on top (levels.py), and the preview with its toolbar (Size, Colours, Click), the time slider and
the status line.  Find (find.py) lists the settings with the words typed, over the drawer; a hit
opens its tool at its place, with its section open and the setting marked.

The shell (figures/shell/frame.py) keeps the document, undo, the preview's drawing, the time
slider and what is picked (its node); it calls show(node) when the picked thing or the
document's shape changed, and refresh() after an edit made from what is shown."""

import html

import panel as pn

from ...theme import GRID, PANEL
from ...viewer.ui import RAIL_BTN, out_of_flow
from .. import spec as fg
from ..shell import nodes
from . import drawer as D, tools
from .find import Find
from .host import ShellHost
from .levels import LevelSwitch, kind_of

FOUND = "0 0 0 2px #22d3ee"  # (the setting Find went to)

DRAWER_W = 450


class Frame:
    def __init__(self, shell):
        self.shell = shell
        self.host = ShellHost(shell)
        self.tool = "layers"  # (the drawer open: a tool's key, or None)
        self.folds = {}  # (what is open in the lists, by key: it outlasts a rebuild and undo)
        self.drawers = []  # (the drawers shown: refreshed after an edit)
        self.live = []  # (f() of other parts shown, to follow an edit: refreshed too)
        self._fresh = {}
        self.pin = None  # (the row Find went to, while its drawer is being made)
        self.pin_said = "Found"  # (how the note under the level switch says it: Find's, a click's)
        self.levels = LevelSwitch(self.pick)
        from .gridfirst import Chips
        self.chips = Chips(self)  # (the layers every panel draws, above the preview)
        self.find = Find(self.host, self.go_to, prefer=self._prefer, most=12,
                         box=pn.widgets.TextInput(placeholder="Find a setting…", width=230,
                                                  margin=(4, 8), align="center"))
        self.find.box.param.watch(self._finding, "value_input")
        self._build()

    # ------------------------------------------------------------ the layout
    def _build(self):
        sh = self.shell
        self.runs_btn = pn.widgets.Button(name="Runs", icon="database", height=32, margin=(4, 4),
                                          button_type="light", button_style="outline",
                                          description="The figure's runs: open the Runs tool")
        self.runs_btn.on_click(lambda e: self.open_tool("runs"))
        actions = pn.Row(sh.new_btn, sh.undo_btn, sh.redo_btn, sh.auto, sh.update, sh.exp_btn,
                         margin=0, align="center")
        self.top = pn.FlexBox(pn.Row(self.runs_btn, self.find.box, margin=0), actions,
                              flex_wrap="wrap", align_items="center",
                              justify_content="space-between", sizing_mode="stretch_width",
                              styles={"flex": "0 0 auto", "border-bottom": f"1px solid {GRID}"})
        self.rail_btns = {}
        for key, label, icon, tip in tools.TOOLS:
            b = pn.widgets.Button(name=label, icon=icon, description=tip, width=64, height=58,
                                  margin=(2, 4), stylesheets=[RAIL_BTN])
            b.on_click(lambda e, k=key: self.open_tool(k))
            self.rail_btns[key] = b
        self.rail = pn.Column(*self.rail_btns.values(), pn.Spacer(), margin=0, width=72,
                              sizing_mode="stretch_height",
                              styles={"flex": "0 0 72px", "padding": "6px 0",
                                      "align-items": "center", "background": PANEL,
                                      "border-right": f"1px solid {GRID}"})
        self.title = pn.pane.HTML(margin=(6, 6, 0, 6), sizing_mode="stretch_width")
        # (taller than the pane: it scrolls; its height is what it holds, as the old
        # inspector's: Bokeh's max-height 100% would cap each card in it at the pane's)
        self.body = pn.Column(margin=0, sizing_mode="stretch_width",
                              styles={"flex": "0 0 auto", "height": "max-content",
                                      "max-height": "none"})
        self.found = pn.pane.HTML(margin=(0, 6), sizing_mode="stretch_width")
        self.links = pn.Column(margin=(0, 6), sizing_mode="stretch_width")  # (go_part's)
        self.side = pn.Column(self.find.list, self.title, self.levels.panel, self.found,
                              self.links, self.body, width=DRAWER_W,
                              scroll="y-auto", sizing_mode="stretch_height",
                              styles={"border-right": f"1px solid {GRID}", "padding": "0 8px",
                                      "overflow-x": "hidden", "flex": "0 0 auto"})

        def label(text):
            return pn.pane.HTML(f'<span class="cv-hint">{text}</span>', margin=(4, 2, 4, 10),
                                align="center")

        view_bar = pn.FlexBox(label("Size"), sh.zoom, label("Colours"), sh.vision,
                              label("Click"), sh.placing.mode, flex_wrap="wrap",
                              align_items="center", sizing_mode="stretch_width",
                              styles={"flex": "0 0 auto"})
        preview = pn.Column(view_bar, sh.placing.hint, self.chips.row, sh.picture, sh.scrubber,
                            sh.status,
                            margin=0, sizing_mode="stretch_both",
                            styles={"flex": "1 1 0", "min-width": "0", "min-height": "0"})
        self.main = pn.Row(self.rail, self.side, preview, margin=0, sizing_mode="stretch_both",
                           styles={"flex": "1 1 0", "min-height": "0"})
        self.panel = pn.Column(self.top, self.main, out_of_flow(sh.export.dlg), margin=0,
                               sizing_mode="stretch_both", styles={"min-height": "0"})
        self._lit()

    def _lit(self):
        for k, b in self.rail_btns.items():
            b.css_classes = ["cv-on"] if k == self.tool else []
        self.side.visible = self.tool is not None or bool(self.find.box.value_input)

    # ------------------------------------------------------------ Find
    def _finding(self, ev):
        self._lit()  # (the hits show over the drawer: open while there are words)

    def _prefer(self, places):
        """Of a setting's places, the one of what is picked, else of its panel, else the
        first."""
        from .levels import where_of
        now = where_of(self.shell.doc, self.shell.node)
        same = [w for w in places if w == now]
        near = [w for w in places if now.pid is not None and w.pid == now.pid]
        kind = [w for w in places if w.level == "kind" and w.kind == now.kind]
        return (same or near or kind or places)[0]

    def go_to(self, row, where, node=None, said="Found"):
        """A Find hit: its tool, at its place, its section open and the setting marked (the
        Export dialog's: the dialog).  node: what to pick there (a row or column), else the
        place's own; said: what the note says it is (a click's: what was clicked)."""
        sh = self.shell
        self.find.box.param.update(value="", value_input="")
        tool = tools.tool_of(row)
        if tool is None:
            self._lit()
            sh.export.open()
            return
        at, fold = node_of(sh.doc, where, D.part_of(row))
        node = node or at
        if fold:
            self.folds[fold] = True
        self.pin, self.pin_said = row.id, said
        self.tool = tool
        self._lit()
        if node == sh.node:
            self.show(node)
        else:
            sh.select(node)
        if self.pin is not None:  # (not shown there now: what the figure is set to leaves it)
            self.found.object = (f'<div class="cv-hint"><b>{html.escape(row.label)}</b> isn\'t '
                                 "shown here now: what the figure is set to leaves it out.</div>")
            self.pin = None

    def go_part(self, part):
        """A part of the preview clicked (click.Part: a title, a label, a legend, a colorbar):
        its setting's tool at its place, as a Find hit, with the note and links of a part
        panels share (clicked.py).  A part with nothing to open picks its panel."""
        from . import clicked
        sh = self.shell
        t = clicked.target(sh.doc, part)
        if t is None:
            sh.select(nodes.FIGURE if part.panel is None else f"panel:{part.panel}")
            return
        self.go_to(t.row, t.where, t.node, said=f"Clicked {t.words}")
        objs = []
        if t.note:
            objs.append(pn.pane.HTML(f'<div class="cv-hint">{t.note}</div>', margin=0,
                                     sizing_mode="stretch_width"))
        if t.links:
            row = pn.FlexBox(flex_wrap="wrap", sizing_mode="stretch_width")
            for words, to in t.links:
                b = pn.widgets.Button(name=f"Jump to: {words}", button_type="light", height=28,
                                      margin=(2, 4, 2, 0),
                                      description=f"{to.row.label} ({to.row.section})")
                b.on_click(lambda e, to=to: self.go_to(to.row, to.where, to.node,
                                                       said="Jumped to"))
                row.append(b)
            objs.append(row)
        self.links.objects = objs

    def _pinned(self):
        """After a drawer is made: the section Find went to open, the setting marked."""
        rid, self.pin = self.pin, None
        for d in self.drawers:
            for sec in d.sections:
                if rid in {r.id for r in sec.rows} and sec.card.visible:
                    sec.card.collapsed = False
                    ctl = sec.ctls.get(rid)
                    if ctl is not None and sec.lines[rid][0].visible:
                        ctl.widget.styles = dict(ctl.widget.styles or {}, outline="2px solid "
                                                 "#22d3ee")
                        row = next(r for r in sec.rows if r.id == rid)
                        self.found.object = (f'<div class="cv-hint">'
                                             f'{html.escape(self.pin_said)}: <b>'
                                             f'{html.escape(row.label)}</b>, in '
                                             f'{html.escape(sec.title)}.</div>')
                        return
        self.pin = rid

    # ------------------------------------------------------------ what is shown
    def open_tool(self, key):
        """A tool's drawer; the open one's button again closes it."""
        self.tool = None if key == self.tool else key
        self._lit()
        if self.tool is not None and self.shell.doc is not None:
            self.show(self.shell.node)

    def pick(self, node):
        """The level switch, or a button in the drawer, picked node."""
        self.shell.select(node)

    def show(self, node):
        """The drawer anew for node (picked, or the document's shape changed)."""
        doc = self.shell.doc
        if doc is None:
            return
        self._runs_label(doc)
        self.levels.show(doc, node)
        self.chips.show(doc, node)
        if self.tool is None:
            return
        self.drawers, self.live = [], []
        self._shape = shape(doc)
        self.found.object = ""
        self.links.objects = []
        self.title.object = f'<div class="cv-h" style="margin:0">{tools.TITLES[self.tool]}</div>'
        try:
            objs = tools.build(self, self.tool, doc, node)
        except Exception as e:  # noqa: BLE001  (said, and the rest of the page goes on)
            import traceback
            traceback.print_exc()
            objs = [tools.note(f'<span style="color:#f87171">Could not show this: '
                               f'{html.escape(str(e))}</span>')]
        self.body.objects = objs
        if self.pin is not None:
            self._pinned()

    def refresh(self):
        """After an edit made from what is shown: the controls as the document has it now; the
        drawer anew if the edit changed the figure's shape (the grid, its panels and lists: what
        the drawer's maps, notes and lists show)."""
        doc = self.shell.doc
        if self.tool is not None and shape(doc) != getattr(self, "_shape", None):
            sh = self.shell
            sh._show(sh.node if nodes.still_there(doc, sh.node) else nodes.FIGURE)
            return
        self._runs_label(doc)
        self.levels.show(doc, self.shell.node)
        self.chips.show(doc, self.shell.node)
        for d in self.drawers:
            d.refresh()
        for f in self.live:
            f()

    def _runs_label(self, doc):
        names = list(nodes.run_names(doc).values())
        text = ", ".join(names[:3]) + (f" +{len(names) - 3}" if len(names) > 3 else "")
        self.runs_btn.name = f"Runs: {text}" if text else "Runs"

    # ------------------------------------------------------------ drawers
    def drawer(self, where, rows, opened=(), spread=None):
        """A drawer of rows at where, refreshed after each edit while it is shown (spread: the
        places an edit is written to, a row or column's panels)."""
        d = D.Drawer(self.host, where, rows, fallback=self.fresh(where.kind), opened=opened,
                     folds=self.folds, spread=spread)
        self.drawers.append(d)
        return d

    def fresh(self, kind=None):
        """A new figure's look with panels of `kind` (the figure's first kind: None), what a
        figure lacks is shown from."""
        sh = self.shell
        if kind is None:
            kind = next((p["kind"] for p in nodes.in_order(sh.doc)), "plan")
        key = (kind, bool(sh.v.fixes))
        if key not in self._fresh:
            try:
                self._fresh[key] = fg.fresh_look(sh.ed.run, sh.ed.fields, sh.v.t, kind,
                                                 tracked=key[1])
            except Exception:  # noqa: BLE001  (a kind it can't start: no fallback)
                self._fresh[key] = None
        return self._fresh[key]

    def kind(self):
        """The kind of what is picked (None: the figure)."""
        return kind_of(self.shell.doc, self.shell.node)


def shape(doc):
    """What the drawer's maps, notes and lists are made from: the grid, each panel's kind, cell
    and lists, those set aside, the figure's lists."""
    from ..draw.base import _cell
    grid = doc.get("grid") or {}
    return (grid.get("rows"), grid.get("cols"),
            tuple((p["id"], p["kind"], tuple(_cell(p)), len(p.get("layers") or []),
                   len(p.get("insets") or [])) for p in doc.get("panels") or []),
            len(doc.get("off_grid") or []), len(doc.get("annotations") or []),
            tuple(doc.get("layers") or {}), tuple(doc.get("sections") or {}),
            tuple(r["id"] for r in doc.get("runs") or []))


def node_of(doc, where, part):
    """The node a place is picked at, and the fold of a list to open there (or None)."""
    if where.level == "kind":
        if where.layer is not None:
            return nodes.KIND_PREFIX + where.kind, f"s:{where.layer}"
        if part == "section":
            from .actions import section_kind
            return nodes.KIND_PREFIX + section_kind(doc), f"sec:{where.item}"
        return nodes.KIND_PREFIX + where.kind, None
    if where.level == "panel":
        if where.layer is not None:
            return f"layer:{where.pid}:{where.layer}", None
        return f"panel:{where.pid}", None
    if where.level == "inset":
        return f"inset:{where.pid}:{where.iid}", None
    if part == "run":
        return nodes.RUNS, None
    if part == "annotation":
        return nodes.FIGURE, f"ann:{where.item}"
    return nodes.FIGURE, None
