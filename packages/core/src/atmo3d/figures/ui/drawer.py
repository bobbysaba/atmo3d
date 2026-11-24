"""One generic drawer of figure settings (docs-dev/figures-ui-plan.md, Phase 2.2): the sections
of the schema's rows at a place in the figure (a where.Where), each a fold whose controls are made
only when it is opened.  A control shows the row's value as the document resolves it there, and a
change is written through the schema (schema/where.py: docedit underneath) by the host, who keeps
undo.  A row set here over what it inherits is marked, with ↺ to take it back; a section says
how many are, with "Reset section".  Where a row has nothing to inherit from (the figure's look,
a kind's own blocks at the kind), what is marked is what differs from a new figure (the
fallback), and taking it back gives it a new figure's value.

A flat drawer (the viewer's layers: one layer dict, schema/viewer.py, through ui/layer.py) has no
folds: its rows' controls side by side, wrapping, made at once, with no marks, ↺ or reset (a viewer
layer inherits nothing).

A drawer of a row or column of the grid (spread: the place of each of its panels) shows its
first panel's values, writes an edit to every panel of it, and marks with a dashed outline a
setting its panels do not all have the same of.

The host (the shell, or a test page) gives:

  host.doc                the document now
  host.edit(fn)           fn(doc) changes it (with undo); then the host calls drawer.refresh()
  host.ctx                schema.fills.Context: what fills need of the runs
  host.say(text, err)     a message
  and what controls offer of the figure (figures/ui/controls.py)."""

import html

import panel as pn

from .. import schema as S
from ..schema import KEEP, where as W
from ...theme import ACCENT  # (the viewer's cyan: a set setting's mark)
from . import controls

MARK = f"-3px 0 0 {ACCENT}"
MIXED = "1px dashed #a78bfa"  # (a row or column's panels have it otherwise)
ITEMS = {"runs[]": "run", "annotations[]": "annotation", "insets[]": "inset",
         "sections[]": "section", "panels[]": "panel"}


# ------------------------------------------------------------ which rows a place has
def part_of(row):
    """What part of the figure a row is a setting of: look, layer, scene item, or the
    document's own (figure, run, annotation, panel, inset, section)."""
    if row.types:
        return "layer"
    if row.key.startswith("look."):
        return "scene item" if "[]" in row.key else "look"
    head = row.key.partition(".")[0]
    return ITEMS.get(head, "figure")


def rows_at(doc, where, part=None):
    """The rows a drawer shows at `where`: a layer's (where.layer), a list item's (where.item;
    part: "run", "annotation", "section", or a scene's list, "scene:isos"), or (part None) the
    look and the document's own of its level."""
    kind = W.kind_at(doc, where)
    if where.layer is not None:
        t = W.layer_type(W.layer_at(doc, where))
        return [r for r in S.ROWS if r.types and t in r.types and r.at(where.level)
                and (kind is None or kind in r.kinds)]
    if part is None:
        part = {"inset": "inset"}.get(where.level, "look")
    want = {"look": ("look", "panel" if where.level == "panel" else "figure"),
            "inset": ("look", "inset")}.get(part, ("scene item",) if str(part).startswith(
                "scene:") else (part,))
    out = []
    for r in S.ROWS:
        p = part_of(r)
        if p not in want or not r.at(where.level):
            continue
        if p == "figure" and where.level != "figure":
            continue
        if kind is not None and where.level != "figure" and kind not in r.kinds:
            continue
        if p == "scene item" and f".{str(part)[6:]}[]." not in r.key:
            continue
        out.append(r)
    return out


def same(a, b):
    """Whether two control values read the same: every blank is one, a number whatever its
    type."""
    blank = (None, "", [], ())
    if a in blank or b in blank:
        return a in blank and b in blank
    try:
        return abs(float(a) - float(b)) < 1e-9
    except (TypeError, ValueError):
        pass
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return list(a) == list(b)
    return a == b


def is_top(row, where):
    """Row has nothing to inherit from at `where`: the figure's look, or a kind's own block at
    the kind."""
    if row.key.startswith("code.") and where.level == "figure":
        return True  # (your own code: the figure's look too)
    if not row.key.startswith("look.") or row.writer == "scene" or "[]" in row.key:
        return False
    if where.level == "figure":
        return True
    return where.level == "kind" and where.layer is None and W.kind_block(row.block[0])


def _raw(key):
    """A row of a look key no row has (what another row writes beside its own)."""
    return S.Row(key, "", None, "", as_=S.RAW)


# ------------------------------------------------------------ the drawer
class Section:
    """One fold of the drawer: its rows' controls made when it is first opened."""

    def __init__(self, drawer, title, rows, opened=False):
        self.d, self.title, self.rows = drawer, title, rows
        self.ctls = {}
        self.lines = {}
        self.reset = pn.widgets.Button(name="↺ Reset section", height=26, margin=(2, 2),
                                       button_type="light", button_style="outline",
                                       description="Every setting of this section back to what "
                                                   "it inherits. Undo takes it back")
        self.reset.on_click(lambda e: self.d.reset(self))
        if drawer.flat:
            self.body = self.card = pn.FlexBox(flex_wrap="wrap", align_items="flex-end",
                                               gap="2px 14px", sizing_mode="stretch_width")
            self._build()
            return
        self.body = pn.Column(margin=0, sizing_mode="stretch_width")
        self.card = pn.Card(self.body, title=title, collapsed=not opened,
                            sizing_mode="stretch_width", margin=(2, 0))
        self.card.param.watch(self._opened, "collapsed")
        if opened:
            self._build()

    def _opened(self, ev):
        if self.d.folds is not None:
            self.d.folds[(self.d.where, self.title)] = not ev.new
        if not ev.new and not self.ctls:
            self._build()
            self.refresh()

    def _build(self):
        flat = self.d.flat
        objs = [] if flat else [self.reset]
        for r in self.rows:
            try:
                ctl = controls.make(r, self.d.where, self.d.host)
            except Exception as e:  # noqa: BLE001  (a control the host can't offer: said)
                objs.append(pn.pane.HTML(f'<div class="cv-hint">{html.escape(r.label)}: '
                                         f'{html.escape(str(e))}</div>'))
                continue
            ctl.watch(lambda row=r, c=ctl: self.d.changed(row, c))
            if r.help:
                for w in ctl.parts:
                    if hasattr(w, "description") and not getattr(w, "description", None):
                        w.description = r.help
            if flat:
                self.ctls[r.id], self.lines[r.id] = ctl, (ctl.widget, None)
                objs.append(ctl.widget)
                continue
            back = pn.widgets.Button(name="↺", width=30, height=28, margin=(20, 2, 0, 2),
                                     button_type="light", visible=False,
                                     description=f"Back to what it inherits: {r.label}")
            back.on_click(lambda e, row=r: self.d.take_back(row))
            line = pn.Row(ctl.widget, back, margin=0)
            self.ctls[r.id], self.lines[r.id] = ctl, (line, back)
            objs.append(line)
        self.body.objects = objs

    def refresh(self):
        """The controls as the document has it now; what is offered shown; what is set here
        marked; the count on the fold."""
        doc, where, host = self.d.host.doc, self.d.where, self.d.host
        own = new = mixed = 0
        for r in self.rows:
            mine = any(W.own(doc, r, w) for w in self.d.spread)
            changed = not mine and self.d.differs_from_new(r)
            own += mine
            new += changed
            mine = mine or changed
            if r.id not in self.ctls:
                continue
            ctl, (line, back) = self.ctls[r.id], self.lines[r.id]
            line.visible = S.offered(r, doc, where, host.ctx)
            try:
                v = W.value(doc, r, where, fallback=self.d.fallback)
            except Exception:  # noqa: BLE001  (an odd value saved: the control as it is)
                v = KEEP
            if v is not KEEP:
                with self.d.quiet():
                    try:
                        ctl.set(v)
                    except Exception:  # noqa: BLE001  (a value the control can't show: as is)
                        pass
            if back is None:  # (flat: nothing marked)
                continue
            back.visible = mine and r.control.kind != "code"
            styles = dict(ctl.widget.styles or {})
            if mine:
                styles["box-shadow"] = MARK
            else:
                styles.pop("box-shadow", None)
            odd = len(self.d.spread) > 1 and v is not KEEP and self.d.mixed(r, v)
            mixed += odd
            if odd:
                styles["outline"] = MIXED
            elif styles.get("outline") == MIXED:
                styles.pop("outline")
            ctl.widget.styles = styles
        if self.d.flat:
            self.card.visible = any(line.visible for line, _ in self.lines.values())
            return
        said = [f"{own} set here"] * bool(own) + [f"{new} changed"] * bool(new) + \
            [f"{mixed} differ between its panels"] * bool(mixed)
        self.card.title = self.title + (" · " + ", ".join(said) if said else "")
        # (your own code has no reset: a click would lose what was typed)
        self.reset.visible = bool(own or new) and not any(r.control.kind == "code"
                                                           for r in self.rows)
        self.card.visible = any(S.offered(r, doc, where, host.ctx) for r in self.rows)


class Drawer:
    """The settings of `rows` (rows_at's) at `where`, by section.  fallback: a document to show
    what a figure lacks from (a new figure's look, spec.fresh_look); folds: {(where, section):
    open} kept by its owner, so what was opened or closed by hand stays so in the drawer made
    next for that place (after undo, say); opened: the sections open otherwise; flat: no folds
    (the viewer's layers)."""

    def __init__(self, host, where, rows=None, fallback=None, opened=(), folds=None,
                 spread=None, flat=False):
        self.host, self.where, self.fallback, self.folds = host, where, fallback, folds
        self.flat = flat
        self.spread = list(spread or [where])
        self._held = 0
        rows = rows_at(host.doc, where) if rows is None else rows
        by = {}
        for r in rows:
            by.setdefault(r.section, []).append(r)
        kept = folds or {}
        self.sections = [Section(self, title, rs,
                                 opened=kept.get((where, title), title in opened))
                         for title, rs in by.items()]
        self.panel = pn.Column(*[s.card for s in self.sections], margin=0,
                               sizing_mode="stretch_width")
        self.refresh()

    # ---- changes
    def quiet(self):
        """While the controls are set from the document: no change of theirs is an edit."""
        from contextlib import contextmanager

        @contextmanager
        def held():
            self._held += 1
            try:
                yield
            finally:
                self._held -= 1
        return held()

    def changed(self, row, ctl):
        if self._held:
            return
        try:
            shown = ctl.get()
        except Exception as e:  # noqa: BLE001  (half typed)
            self.host.say(f"{row.label}: {e}", True)
            return
        spread, ctx = self.spread, self.host.ctx

        def apply(d):
            for w in spread:
                W.write(d, row, w, shown, ctx)
        self._edit(apply, row.label)

    def mixed(self, row, v):
        """Of a row or column: whether its panels do not all show v for row."""
        doc = self.host.doc
        for w in self.spread[1:]:
            try:
                other = W.value(doc, row, w, fallback=self.fallback)
            except Exception:  # noqa: BLE001
                continue
            if other is not KEEP and not same(other, v):
                return True
        return False

    def new_value(self, row):
        """What a new figure shows for row here (KEEP: none)."""
        if self.fallback is None:
            return KEEP
        return W.value(self.fallback, row, W.Where(self.where.level, self.where.kind))

    def differs_from_new(self, row):
        """At the top (is_top): whether row differs from a new figure's."""
        if not is_top(row, self.where) or self.fallback is None:
            return False
        new = self.new_value(row)
        if new is KEEP:
            return False
        doc = self.host.doc
        for level, key, by_hand in row.also:  # (it follows something until set by hand:
            if level == self.where.level and not same(  # letters, the panel count)
                    W.saved(doc, _raw(key), self.where), by_hand):
                return False
        try:
            now = W.value(doc, row, self.where)
        except Exception:  # noqa: BLE001  (an odd value: not counted)
            return False
        return now is not KEEP and not same(now, new)

    def _back(self, d, r, where):
        """Row r at its top: a new figure's value (else its default); below: what it
        inherits."""
        if is_top(r, where):
            new = self.new_value(r)
            if new is KEEP and r.default is not KEEP and not r.packed:
                new = r.as_.show(r.default)
            if new is not KEEP and S.offered(r, d, where):
                W.write(d, r, where, new)
                for level, key, _ in r.also:  # (what it follows, as a new figure has it)
                    if level == where.level and self.fallback is not None:
                        was = W.saved(self.fallback, _raw(key), W.Where(where.level,
                                                                        where.kind))
                        if was is not KEEP:
                            W.put(d, _raw(key), where, was)
            return
        if where.level == "figure" or where.layer is not None and where.level == "kind":
            if r.default is not KEEP and not r.packed and S.offered(r, d, where):
                W.write(d, r, where, r.as_.show(r.default))
            return
        W.take_back(d, r, where)

    def take_back(self, row):
        def apply(d):
            for w in self.spread:
                self._back(d, row, w)
        self._edit(apply, row.label)

    def reset(self, sec):
        """A section's settings back to what they inherit (at the top: a new figure's; your
        own code stays)."""
        where = self.where

        def apply(d):
            for w in self.spread:
                for r in sec.rows:
                    if r.control.kind != "code":
                        self._back(d, r, w)
        self._edit(apply, sec.title)
        if where.level == "kind" and where.layer is None:
            self._kept_by_panels(sec)

    def _kept_by_panels(self, sec):
        """A kind's reset: which of its panels keep what they set alone (it skips them)."""
        from ..shell import docedit as de, nodes
        doc = self.host.doc
        names = nodes.letters(doc) if doc.get("panels") else {}
        keep = []
        for p in de.panels_of(doc, self.where.kind):
            pw = W.Where("panel", self.where.kind, p["id"])
            if any(r.at("panel") and W.own(doc, r, pw) for r in sec.rows):
                keep.append(names.get(p["id"], str(p["id"])))
        if keep:
            many = len(keep) > 1
            self.host.say(f"Panel{'s' if many else ''} {', '.join(keep)} "
                          f"keep{'' if many else 's'} what {'they' if many else 'it'} set alone.")

    def _edit(self, fn, what):
        try:
            self.host.edit(fn)
        except (ValueError, IndexError, KeyError, TypeError) as e:
            self.host.say(f"{what}: {e}", True)
            self.refresh()

    def refresh(self):
        for s in self.sections:
            s.refresh()
