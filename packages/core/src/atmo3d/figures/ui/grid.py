"""The grid's actions (Layout tool): the figure's type, the panels set aside, adding a panel of
any kind and filling empty cells, a panel's type, a copy of it.  Kinds mix freely: a panel is
only a kind at a place.  The grid's rows, columns and shares, and a panel's place, are schema rows
(Layout, Grid and Panel); this is what is not a setting.  The shell holds one (`shell.grid`)."""

import html

import panel as pn

from .. import spec as fg
from ...theme import GRID
from ..draw.base import _cell
from ..kinds import KINDS
from ..spec.doc import KIND_KEYS
from ..times import _nearest_t
from ..shell import docedit as de, nodes
from .parts import note

# (the kinds a panel can be)
ADDABLE = ("plan", "sounding", "xsec", "th", "line", "dist", "profile", "joint", "azim", "table",
           "scene")
NEW_ROW, NEW_COL = "new row", "new column"


def grid_map(doc):
    """The grid with each panel's letter where it sits (a table: spans shown as spans)."""
    grid, names = doc.get("grid") or {}, nodes.letters(doc)
    rows, cols = int(grid.get("rows", 1)), int(grid.get("cols", 1))
    at = {tuple(_cell(p)[:2]): p for p in doc.get("panels") or []}
    covered, trs = set(), []
    for r in range(rows):
        tds = []
        for c in range(cols):
            if (r, c) in covered:
                continue
            p = at.get((r, c))
            rs, cs = _cell(p)[2:] if p else (1, 1)
            covered.update((r + a, c + b) for a in range(rs) for b in range(cs))
            tds.append(f'<td rowspan="{rs}" colspan="{cs}" style="border:1px solid {GRID};'
                       f'text-align:center;min-width:28px;height:24px;padding:2px">'
                       f'{names[p["id"]] if p else "·"}</td>')
        trs.append(f'<tr>{"".join(tds)}</tr>')
    return pn.pane.HTML(f'<table style="border-collapse:collapse;font-size:12px">{"".join(trs)}'
                        '</table>', margin=(4, 4))


def main_kind(doc):
    """The kind most of the figure's panels are (the first such: tied)."""
    kinds = [p["kind"] for p in doc.get("panels") or []]
    return max(kinds, key=kinds.count) if kinds else "plan"


def kind_options(also=None):
    """The kinds to choose from, by name (also: a kind not otherwise listed)."""
    extra = (also,) if also and also not in ADDABLE else ()
    return {KINDS[k].label: k for k in (*ADDABLE, *extra)}


def moment_of(p):
    """The run and time panel p shows: its own, else its first entry's that has them."""
    items = [p, *(p.get("layers") or [])]
    return (next((x["run"] for x in items if x.get("run") is not None), None),
            next((x["time_s"] for x in items if x.get("time_s") is not None), None))


def to_moment(p, run, time_s):
    """New panel p, and its entries, show that run and time, where they have one."""
    for x in (p, *(p.get("layers") or [])):
        if run is not None and x.get("run") is not None:
            x["run"] = run
        if time_s is not None and x.get("time_s") is not None:
            x["time_s"] = time_s


def own_run(shell):
    """The run new panels start with: the viewer's, if in the figure, else the first."""
    runs = shell.doc["runs"]
    here = shell.ed.run.path
    return next((r["id"] for r in runs if r["path"] == here), runs[0]["id"])


def shown_time(shell, rid):
    """The viewer's shown time, as the nearest output of run rid."""
    times = list(shell.time_opts(de.run_index(shell.doc, rid)).values())
    now = float(shell.ed.run.times[shell.v.t])
    return _nearest_t(times, now) if times else now


def _btn(name, fn, tip="", primary=False):
    b = pn.widgets.Button(name=name, height=32, margin=(6, 4), description=tip or None,
                          button_type="primary" if primary else "light", button_style="outline")
    b.on_click(lambda e: fn())
    return b


class Grid:
    def __init__(self, shell):
        self.shell = shell

    # ------------------------------------------------------------ the Layout tool's
    def type_widget(self, doc):
        """Which kind every panel of the figure is: choosing one changes them all."""
        kinds = {p["kind"] for p in doc.get("panels") or []}  # (those set aside change with them)
        one = next(iter(kinds)) if len(kinds) == 1 else None
        options = kind_options(one)
        if one is None:
            options = {"Mixed": "", **options}
        w = pn.widgets.Select(name="Figure type", options=options, value=one or "",
                              description="Change every panel to this type, in the cell it is in. "
                                          "What the panels showed is replaced; Undo takes it back. "
                                          "To change only one, pick it in the preview.")

        def on_type(ev):
            if ev.new:
                self.set_kind([p["id"] for p in self.shell.doc["panels"]], ev.new, nodes.FIGURE,
                              aside=True)

        w.param.watch(on_type, "value")
        return w

    def aside_objs(self, doc):
        """The panels with no room on the grid, if any: back, or gone."""
        aside = doc.get(de.OFF_GRID) or []
        if not aside:
            return []
        shell = self.shell
        n = len(aside)
        what = ", ".join(dict.fromkeys(html.escape(KINDS[p["kind"]].label) for p in aside))
        back = _btn("Bring back", lambda: shell.edit(de.bring_back, node=nodes.FIGURE),
                    "Into free cells; the grid grows if it has to")
        drop = _btn("Remove", lambda: shell.edit(de.forget_aside, node=nodes.FIGURE),
                    "Out of the figure. Undo takes it back")
        return [note(f"<b>{n} panel{'s' if n > 1 else ''} set aside, not drawn</b> ({what}): no "
                     "room on this grid. They return when the grid has room."),
                pn.Row(back, drop, margin=0)]

    def add_objs(self, doc):
        """Adding a panel of a kind, at a free cell or a new row or column; filling the empty
        cells."""
        kinds = kind_options()
        free = {f"Row {r + 1}, column {c + 1}": (r, c) for r, c in de.free_cells(doc)}
        where = {**free, "A new row": NEW_ROW, "A new column": NEW_COL}
        mine = main_kind(doc)
        kind = pn.widgets.Select(name="Add a panel of", options=kinds,
                                 value=mine if mine in kinds.values() else "plan", width=190)
        place = pn.widgets.Select(name="At", options=where, width=190)
        btns = [_btn("Add the panel", lambda: self.add_panel(kind.value, place.value),
                     primary=True)]
        if free:
            btns.append(_btn(f"Fill {len(free)} empty cell{'s' if len(free) > 1 else ''}",
                             lambda: self.fill_empty(kind.value),
                             "A new panel of the type chosen in each empty cell"))
        objs = [pn.Row(kind, place, margin=0), pn.Row(*btns, margin=0)]
        if len({p["kind"] for p in doc.get("panels") or []}) > 1:
            objs.append(note("Set the figure's size by hand: panels of several kinds have no "
                             "automatic one."))
        return objs

    # ------------------------------------------------------------ doing it
    def add_panel(self, kind, place=None):
        """A new panel of a kind at a cell (r, c), in a new row or column, or the first cell
        free; it is then what's picked.  A plan view or cross-section at a cell given, in a row
        or column with one of its kind, starts as a copy of it (ui/lines.copy_from: decision
        2).  Returns it."""
        shell = self.shell
        make = self._maker(kind)
        made = []

        def apply(d):
            grow = {NEW_ROW: "row", NEW_COL: "col"}.get(place)
            if isinstance(place, tuple):
                made.append(self._beside(d, kind, place, make))
            else:
                made.append(make(d, de.next_cell(d, grow)))

        # (the node goes by id, known only once it is made)
        shell.edit(apply)
        shell._show(f"panel:{made[0]['id']}")
        return made[0]

    def _maker(self, kind):
        """make(doc, cell): a new panel of a kind at a cell, as this moment's viewer starts it."""
        from . import entries
        shell = self.shell
        spec = fg.default_spec(shell.ed.run, shell.ed.fields, shell.v.t)
        rid = own_run(shell)
        ts = shown_time(shell, rid)
        scene3d = shell.ed.viewer_scene() if kind == "scene" else None

        def make(d, at):
            start = {k: spec[k] for k in KIND_KEYS[kind] if k in spec}
            if kind == "scene":  # (the first shows what the 3D workspace does; seed_kind)
                start = dict(axes=dict(start.get("axes") or {}, **de.SCENE_START_AXES),
                             scene3d=scene3d)
            de.seed_kind(d, kind, start, KINDS[kind].labels)
            # (the first plan view or section of a figure with no layers draws nothing yet:
            # what it shows is the user's to add)
            if kind == "plan":
                p = de.plan_panel(d, at, rid, ts, (), fg.card_section(spec["sections"][0]))
            elif kind == "xsec":
                p = de.xsec_panel(d, at, rid, ts, (), fg.card_section(spec["sections"][0]))
            elif kind == "scene":
                p = de.add_panel(d, kind, at, run=rid, time_s=ts)
            else:
                p = de.add_panel(d, kind, at, entries.first_entries(shell, kind))
            present = {KINDS[q["kind"]] for q in d["panels"]} | {KINDS[k] for k in ADDABLE}
            de.label_places(d, p, KINDS[kind], present)
            shell.frame.folds.setdefault(f"p:{p['id']}:0", True)  # (its first entry open)
            return p

        return make

    def _beside(self, d, kind, at, make):
        """A new panel of a kind at cell `at`: a copy of its neighbour in the row or column
        (what the grid varies taken from its own row and column), else as make() starts it.
        Other kinds than plan views and cross-sections (their entries are each panel's own,
        their lists): as make() starts them."""
        from . import lines
        p = lines.copy_from(d, kind, at) if kind in lines.COPIED else None
        if p is None:
            return make(d, at)
        self.shell.frame.folds.setdefault(f"p:{p['id']}:0", True)
        return p

    def fill_empty(self, kind):
        """A new panel of a kind in every empty cell (beside a panel of the kind: a copy of
        it, as add_panel)."""
        make = self._maker(kind)

        def apply(d):
            for at in de.free_cells(d):
                self._beside(d, kind, at, make)
        self.shell.edit(apply, node=nodes.FIGURE)

    def set_kind(self, pids, kind, node=None, aside=False):
        """Panels pids become new panels of a kind, each in the cell it holds (and what it
        spans) and at the run and time it shows; what they showed goes, one undo step.  node:
        what to show, else the last one made.  aside: those set aside change too.  Returns the
        new panels."""
        shell = self.shell
        make = self._maker(kind)
        made = []

        def apply(d):
            for pid in pids:
                old = de.panel_by_id(d, pid)
                if old["kind"] == kind:
                    continue
                cell, moment = list(_cell(old)), moment_of(old)
                de.remove_panel(d, pid)
                p = make(d, cell[:2])
                p["cell"] = cell
                to_moment(p, *moment)
                made.append(p)
            for n, old in enumerate(d.get(de.OFF_GRID) or [] if aside else []):
                if old["kind"] != kind:
                    p = make(d, _cell(old)[:2])
                    p["cell"] = list(_cell(old))
                    to_moment(p, *moment_of(old))
                    d["panels"].remove(p)
                    d[de.OFF_GRID][n] = p
                    de.drop_annotations(d, {old["id"]})
            if aside:
                de.letters_in_order(d)
        shell.edit(apply, node=node)
        if node is None and made:
            shell._show(f"panel:{made[-1]['id']}")
        return made

    def copy_panel(self, pid):
        """A copy of panel pid in the first free cell, or a new row or column; it is picked."""
        made = []

        def apply(d):
            made.append(de.copy_panel(d, pid, de.next_cell(d)))
        self.shell.edit(apply)
        self.shell._show(f"panel:{made[0]['id']}")
        return made[0]
