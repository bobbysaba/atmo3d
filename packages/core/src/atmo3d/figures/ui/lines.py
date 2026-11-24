"""The grid's rows and columns, without widgets (docs-dev/figures-ui-plan.md, Phase 4, mockup B):
which panels a row or a column holds, what its panels have in common that the next row or column
has otherwise (what the grid varies: a run, a time, a height, a field), the headers drawn above
and beside the preview from it, a panel's own changes (what it sets over the shared layers and
the look of its kind), and the copy a panel added to a row or a column starts as.

A row or a column is picked like a panel: its node is row:<r> or col:<c> (0-based), and an edit
made there is written to each panel of it of its kind (decision 2: the document's format does
not change).  A panel spanning several rows or columns is in each."""

import copy

from .. import draw as figdraw
from ..draw.base import _cell
from ..shell import docedit as de, nodes

AXES = {"row": "Row", "col": "Column"}
DIMS = ("run", "time", "height", "field")
DIM_WORDS = {"run": "Run", "time": "Time", "height": "Height", "field": "Field"}
COPIED = ("plan", "xsec")  # (the kinds a panel added beside others copies: copy_from)
# (the schema row a dimension is set by, at a panel: the field is its first fill layer's)
DIM_ROWS = {"run": "panels[].run", "time": "panels[].time_s", "height": "panels[].z"}


# ------------------------------------------------------------ the nodes
def is_line(node):
    return node.split(":", 1)[0] in AXES


def line_of(node):
    """("row" or "col", its index) of a line node."""
    axis, _, k = node.partition(":")
    return axis, int(k)


def node_of(axis, k):
    return f"{axis}:{int(k)}"


def count(doc, axis):
    grid = doc.get("grid") or {}
    return int(grid.get("rows" if axis == "row" else "cols", 1))


def _covers(p, axis, k):
    r, c, rs, cs = _cell(p)
    start, n = (r, rs) if axis == "row" else (c, cs)
    return start <= k < start + n


def panels_in(doc, axis, k):
    """The panels of a row or column, in reading order."""
    return [p for p in nodes.in_order(doc) if _covers(p, axis, k)]


def kind_of(doc, node):
    """The kind a row or column's edits are of: the one most of its panels are (the first
    such: tied); None: it has none."""
    kinds = [p["kind"] for p in panels_in(doc, *line_of(node))]
    return max(kinds, key=kinds.count) if kinds else None


def members(doc, node):
    """The ids of the panels a row or column's edits reach: those of its kind."""
    kind = kind_of(doc, node)
    return [p["id"] for p in panels_in(doc, *line_of(node)) if p["kind"] == kind]


def still_there(doc, node):
    axis, k = line_of(node)
    return k < count(doc, axis) and bool(panels_in(doc, axis, k))


def name(node):
    axis, k = line_of(node)
    return f"{AXES[axis]} {k + 1}"


def scope(doc, node):
    """What an edit made at a row or column reaches, in words."""
    names = nodes.letters(doc)
    ids = members(doc, node)
    said = ", ".join(names[i] for i in ids)
    word = "panel" if len(ids) == 1 else "panels"
    out = f"Applies to {name(node).lower()}: {word} {said}"
    skipped = [names[p["id"]] for p in panels_in(doc, *line_of(node)) if p["id"] not in ids]
    if skipped:
        out += f" (not {', '.join(skipped)}: another kind)"
    return out


# ------------------------------------------------------------ what a panel varies in
def value(doc, p, dim):
    """What panel p shows of a dimension (None: it has none of its own)."""
    if dim == "run":
        return p.get("run")
    if dim == "time":
        t = p.get("time_s")
        return None if t is None else round(float(t), 3)
    if dim == "height":
        if p.get("z") is not None:
            return (round(float(p["z"]), 4), p.get("zmode", "height"))
        j = de._first_fill(doc, p)
        if j is None:
            return None
        lay = figdraw.panel_layers(doc, p)[j][1]
        return None if lay.get("z") is None else (round(float(lay["z"]), 4),
                                                   lay.get("mode", "height"))
    j = de._first_fill(doc, p)
    return None if j is None else figdraw.panel_layers(doc, p)[j][1].get("field")


def varies(doc):
    """{"row": [dims], "col": [dims]}: what each row (column) has one of for all its panels,
    and the rows (columns) do not all have the same of (a panel spanning lines: not counted)."""
    out = {}
    for axis in AXES:
        n = count(doc, axis)
        out[axis] = []
        if n < 2:
            continue
        for dim in DIMS:
            per = []
            for k in range(n):
                vals = {value(doc, p, dim) for p in panels_in(doc, axis, k)
                        if _spans(p, axis) == 1}
                vals.discard(None)
                if len(vals) > 1:
                    break
                per.append(next(iter(vals), None))
            else:
                got = [v for v in per if v is not None]
                if len(set(got)) > 1:
                    out[axis].append(dim)
    return out


def _spans(p, axis):
    return _cell(p)[2] if axis == "row" else _cell(p)[3]


def words(doc, dim, v, fields=None):
    """A dimension's value in words, as a header says it."""
    if v is None:
        return ""
    if dim == "run":
        return nodes.run_names(doc).get(v, str(v))
    if dim == "time":
        return f"{float(v) / 60:g} min"
    if dim == "height":
        z, mode = v
        return f"k = {int(round(z))}" if mode == "level" else f"{z:g} km"
    return fields[v].label if fields is not None and v in fields else str(v)


def label(doc, node, dims, fields=None):
    """A row or column's header: what it varies in, else its name."""
    axis, k = line_of(node)
    ps = [p for p in panels_in(doc, axis, k) if _spans(p, axis) == 1]
    said = []
    for dim in dims:
        v = next((value(doc, p, dim) for p in ps if value(doc, p, dim) is not None), None)
        if v is not None:
            said.append(words(doc, dim, v, fields))
    return " · ".join(said) or name(node)


def heads(doc, boxes, picked=None, fields=None):
    """The headers over the preview: [[node, label, a, b, axis, lit]] with a, b the fractions of
    the image the row (top, bottom) or column (left, right) takes, of its panels' boxes; none
    for an axis of one line, or with no panel drawn."""
    out = []
    if not boxes or not doc.get("panels"):
        return out
    vary = varies(doc)
    for axis in AXES:
        n = count(doc, axis)
        if n < 2:
            continue
        for k in range(n):
            ps = [p for p in panels_in(doc, axis, k) if _spans(p, axis) == 1
                  and p["id"] in boxes] or [p for p in panels_in(doc, axis, k) if p["id"] in boxes]
            if not ps:
                continue
            bs = [boxes[p["id"]] for p in ps]
            a, b = (min(x[0] for x in bs), max(x[1] for x in bs)) if axis == "col" else \
                (min(x[2] for x in bs), max(x[3] for x in bs))
            node = node_of(axis, k)
            out.append([node, label(doc, node, vary[axis], fields), float(a), float(b), axis,
                        node == picked])
    return out


# ------------------------------------------------------------ a panel's own changes
def own_changes(doc, pid, fields=None, look_rows=None):
    """What panel pid sets for itself: [(what, kind of change, place or None)], kind "over" (a
    shared layer it changes: place is its place in the panel's layers), "own" (a layer of its
    own) or "look" (look settings over its kind's: place None).  look_rows(where): the look
    rows to count at a panel (tools.rows_for's), None: the look is not counted."""
    p = de.panel_by_id(doc, pid)
    if p is None:
        return []
    out = []
    shared = doc.get("layers") or {}
    own_z = p.get("z") is not None
    for j, item in enumerate(de.places(doc, p)):
        if "ref" in item:
            keys = [k for k in de.overrides(item) if k not in de.BAR_KEYS
                    and not (own_z and k in de.HEIGHT_KEYS)]
            if keys:
                lay = dict(shared[item["ref"]], **de.overrides(item))
                what = "doesn't draw" if keys == ["on"] and not lay.get("on", True) else \
                    "its own " + ", ".join(keys)
                out.append((f"{nodes.layer_name(lay, fields)}: {what}", "over", j))
        else:
            out.append((f"its own layer: {nodes.layer_name(item, fields)}", "own", j))
    if look_rows is not None:
        from ..schema import where as W
        from ..schema.where import Where
        pw = Where("panel", p["kind"], pid)
        mine = [r for r in look_rows(pw) if W.own(doc, r, pw)]
        if mine:
            secs = list(dict.fromkeys(r.section for r in mine))
            n = len(mine)
            out.append((f"its own look: {', '.join(secs)} ({n} setting{'s' * (n > 1)})",
                        "look", None))
    return out


def use_shared(doc, pid, look_rows=None):
    """Panel pid back at what it shares: its changes to shared layers gone, and (look_rows: as
    own_changes) its own look; its own layers stay."""
    p = de.panel_by_id(doc, pid)
    if p is None:
        return
    for j, item in enumerate(de.places(doc, p)):
        if "ref" in item and de.overrides(item):
            de.clear_over(doc, p, j)
    if look_rows is not None:
        from ..schema import where as W
        from ..schema.where import Where
        pw = Where("panel", p["kind"], pid)
        for r in look_rows(pw):
            if W.own(doc, r, pw):
                W.take_back(doc, r, pw)


# ------------------------------------------------------------ a panel added to a row or column
def neighbour(doc, kind, cell):
    """The panel a new panel of `kind` at cell (r, c) starts as a copy of (decision 2): the
    nearest of that kind in its row, else in its column; and the panel of its column (row) it
    takes what the columns (rows) vary in from.  (None, None): no such panel."""
    r, c = int(cell[0]), int(cell[1])

    def near(axis, k, at):
        ps = [p for p in panels_in(doc, axis, k) if p["kind"] == kind]
        pos = (lambda p: _cell(p)[1]) if axis == "row" else (lambda p: _cell(p)[0])
        return min(ps, key=lambda p: abs(pos(p) - at), default=None)

    in_row, in_col = near("row", r, c), near("col", c, r)
    if in_row is not None:
        return in_row, in_col
    return in_col, None


def copy_from(doc, kind, cell):
    """A new panel at cell copied from its neighbour (neighbour()), with what the columns
    (rows) vary in from its column's (row's) panel: added, and returned; None: no neighbour.
    Its title and row label are not copied; annotations stay with the panel copied."""
    src, other = neighbour(doc, kind, cell)
    if src is None:
        return None
    vary = varies(doc)
    new = copy.deepcopy(src)
    for k in ("rowlabel", "letter", "title"):  # (its own: a title says what it shows)
        new.pop(k, None)
    new.update(id=de.next_panel_id(doc), cell=[int(cell[0]), int(cell[1]), 1, 1])
    de._new_inset_ids(doc, new)
    took_row = _cell(src)[0] == int(cell[0])
    if other is not None:  # (the other axis's dimensions from its own line)
        for dim in vary["col" if took_row else "row"]:
            _take(doc, new, other, dim)
    doc["panels"].append(new)
    de.letters_in_order(doc)
    return new


def _take(doc, new, src, dim):
    """New panel takes what src has of a dimension."""
    if dim in ("run", "time"):
        key = {"run": "run", "time": "time_s"}[dim]
        if src.get(key) is not None:
            new[key] = src[key]
        return
    if dim == "height":
        if src.get("z") is not None:
            de.set_height(doc, new, float(src["z"]), src.get("zmode", "height"))
        return
    j, i = de._first_fill(doc, src), de._first_fill(doc, new)
    if j is None or i is None:
        return
    # (its first fill as the other's is: field, colours and range go together)
    items = new.get("layers") or []
    at = items.index(de.places(doc, new)[i])
    items[at] = copy.deepcopy(de.places(doc, src)[j])
