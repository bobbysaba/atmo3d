"""Find over the settings schema (docs-dev/figures-ui-plan.md, Phase 2.3): the rows whose words
match, each with the places in this figure it can be set at (where.Where's), for the shell to open
a drawer there.  The old Find (shell/findview.py) walked the inspector's widgets for this; here it
is a search over the table and the document."""

import html

import panel as pn

from .. import draw as figdraw, schema as S
from ..schema.where import Where
from .drawer import part_of


def places(doc, row):
    """Where in figure doc the row can be set: every place it is offered at."""
    kinds = list(dict.fromkeys(p["kind"] for p in doc.get("panels") or []))
    panels = doc.get("panels") or []
    out = []
    if row.types:
        for lid, lay in (doc.get("layers") or {}).items():
            for k in kinds:
                out.append(Where("kind", k, layer=lid))
        for p in panels:
            for j, _ in enumerate(figdraw.panel_layers(doc, p)):
                out.append(Where("panel", p["kind"], p["id"], layer=j))
    else:
        part = part_of(row)
        if part in ("look", "figure"):
            out += [Where("figure")] + [Where("kind", k) for k in kinds]
            out += [Where("panel", p["kind"], p["id"]) for p in panels]
            out += [Where("inset", p["kind"], p["id"], i["id"]) for p in panels
                    for i in p.get("insets") or []]
        elif part == "run":
            out += [Where("figure", item=r["id"]) for r in doc.get("runs") or []]
        elif part == "annotation":
            out += [Where("figure", item=n) for n, _ in enumerate(doc.get("annotations") or [])]
        elif part == "panel":
            out += [Where("panel", p["kind"], p["id"]) for p in panels]
        elif part == "inset":
            out += [Where("inset", p["kind"], p["id"], i["id"]) for p in panels
                    for i in p.get("insets") or []]
        elif part == "section":
            out += [Where("kind", k, item=sid) for sid in doc.get("sections") or {}
                    for k in kinds if k in ("plan", "xsec")]
    keep = []
    for w in out:
        try:
            if S.offered(row, doc, w):
                keep.append(w)
        except (KeyError, IndexError, TypeError):  # (a layer of another kind's panels)
            continue
    return keep


def hits(doc, words):
    """[(row, its places in doc)] of the rows matching `words`, of the figure's kinds, that it
    has a place for."""
    kinds = tuple(dict.fromkeys(p["kind"] for p in doc.get("panels") or [])) or S.ALL
    out = []
    for r in S.search(words, kinds):
        at = places(doc, r)
        if at:
            out.append((r, at))
    return out


def place_words(doc, w):
    """A place in words: the figure, all plan views, panel b, its inset, a layer of panel b."""
    from ..kinds import KINDS
    from ..shell import nodes
    letters = nodes.letters(doc) if doc.get("panels") else {}
    if w.level == "figure":
        return "the figure"
    if w.level == "kind":
        name = KINDS[w.kind].name if w.kind in KINDS else w.kind
        return f"all {name}" + (" (a shared layer)" if w.layer is not None else "")
    at = f"panel {letters.get(w.pid, w.pid)}"
    if w.level == "inset":
        return f"the inset of {at}"
    return f"a layer of {at}" if w.layer is not None else at


class Find:
    """A Find box and its hits: picking one calls on_pick(row, where); prefer(places) says which
    of a row's places a hit goes to (else its first); Enter picks the first hit."""

    def __init__(self, host, on_pick, most=30, prefer=None, box=None):
        self.host, self.on_pick, self.most, self.prefer = host, on_pick, most, prefer
        self.found = []  # ((row, where) of each hit shown)
        self.box = box or pn.widgets.TextInput(name="Find a setting",
                                               placeholder="e.g. tick, colorbar",
                                               sizing_mode="stretch_width")
        self.list = pn.Column(margin=0, sizing_mode="stretch_width")
        self.box.param.watch(lambda ev: self.show(ev.new), "value_input")
        self.box.param.watch(lambda ev: self.show(ev.new), "value")
        self.box.param.watch(lambda ev: self.first(), "enter_pressed")
        self.panel = pn.Column(self.box, self.list, margin=0, sizing_mode="stretch_width")

    def show(self, words):
        doc = self.host.doc
        found = hits(doc, words or "") if doc is not None else []
        objs, self.found = [], []
        for r, at in found[:self.most]:
            first = self.prefer(at) if self.prefer else at[0]
            self.found.append((r, first))
            b = pn.widgets.Button(name=f"{r.label} · {r.section}", button_type="light",
                                  sizing_mode="stretch_width", height=28, margin=(1, 0),
                                  description=f"Set at {place_words(doc, first)}"
                                  + (f" and {len(at) - 1} more places" if len(at) > 1 else ""))
            b.on_click(lambda e, row=r, w=first: self.pick(row, w))
            objs.append(b)
        if words and not found:
            objs.append(pn.pane.HTML(f'<div class="cv-hint">No setting matches '
                                     f'“{html.escape(words)}”.</div>'))
        elif len(found) > self.most:
            objs.append(pn.pane.HTML(f'<div class="cv-hint">And {len(found) - self.most} more: '
                                     "type another word.</div>"))
        self.list.objects = objs

    def first(self):
        if self.found:
            self.pick(*self.found[0])

    def pick(self, row, where):
        self.on_pick(row, where)
