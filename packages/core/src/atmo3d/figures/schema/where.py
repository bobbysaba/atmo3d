"""Reading and writing a look row of the schema at a level, without widgets: what the drawer
shows, and where an edit goes.

A look setting is read style, then kinds[kind], then the panel's opts, then an inset's opts; last
wins (spec/doc.py).  So:

  figure   writes style; a kind's block (KIND_KEYS: axes, skewt, ...) to every kind in the figure
  kind     writes kinds[kind]
  panel    writes the panel's opts, and shows what it inherits otherwise
  inset    writes the inset's opts, over its panel's

value() gives what a row's control shows (its as_.show), write() takes what the control holds.

A layer row (layer.<key>) is read from the layer as drawn at its place (Where.layer: a shared
layer's id at kind level, a place in the panel's, or the inset's, layers below) and written
through docedit: write_shared (every panel drawing it, but what one changes), write_panel (into
the panel's "over", or its own layer); a nested key (recipe.z0) writes its block whole.  A fill (schema/fills.py) adds what else the change sets.

At the level "viewer" (schema/viewer.py) the document is one of the viewer's layers: a layer
row reads and writes it, and nothing is inherited."""

import copy
from dataclasses import dataclass

from .. import draw as figdraw
from ..spec.doc import FIGURE_KEYS, KIND_KEYS
from . import KEEP, RAW, Row


@dataclass(frozen=True)
class Where:
    """A place in the figure: a level, and the kind, panel (id) and inset (id) it is of; item:
    which one of a list a row of its items is of (a scene's isosurfaces: isos[]); layer: the
    layer a layer row is of (kind level: a shared layer's id; panel, inset: its place)."""
    level: str = "figure"
    kind: str = None
    pid: int = None
    iid: int = None
    item: int = None
    layer: object = None


FIGURE = Where()


def kind_block(block):
    """Whether a block of settings is saved under kinds (spec/doc.py's KIND_KEYS)."""
    top = block.partition(".")[0]
    return any(top in keys for keys in KIND_KEYS.values())


def _panel(doc, pid):
    return next((p for p in doc.get("panels") or [] if p["id"] == pid), None)


def _inset(doc, pid, iid):
    return next((i for i in (_panel(doc, pid) or {}).get("insets") or [] if i["id"] == iid), None)


def _holder(doc, where):
    """What has this place's own "opts": its inset or its panel (None above a panel)."""
    if where.iid is not None:
        return _inset(doc, where.pid, where.iid)
    return _panel(doc, where.pid) if where.pid is not None else None


def chain(doc, where, block):
    """The dictionaries a setting of `block` is read through, last wins."""
    kinds = doc.get("kinds") or {}
    out = [doc.get("style") or {}]
    if where.kind is not None:
        out.append(kinds.get(where.kind) or {})
    elif kind_block(block):  # (the figure: as its first kind has it)
        out.append(next(iter(kinds.values()), {}))
    if where.pid is not None:
        out.append((_panel(doc, where.pid) or {}).get("opts") or {})
    if where.iid is not None:
        out.append((_inset(doc, where.pid, where.iid) or {}).get("opts") or {})
    return out


# ------------------------------------------------------------ blocks saved otherwise than shown
def prepared(block, held):
    """A block whose saved form differs from its controls', in its controls' form: a sounding's
    layout and hodograph marks, a distribution's statistics."""
    if block == "skewt":
        return dict(held, layout=figdraw.sounding_layout(held),
                    **{f"hodo_{k}": k in figdraw.hodo_marks(held) for k in figdraw.HODO_MARKS})
    if block == "dist":
        return dict(held, stats=figdraw.dist_stat_keys(held),
                    bar_labels=held.get("bar_labels") or "")
    return held


def _dig(d, path):
    for k in path:
        if not isinstance(d, dict) or k not in d:
            return KEEP
        d = d[k]
    return d


def dig(d, path):
    """d's value at path (a list of keys), None if it has none."""
    v = _dig(d, path)
    return None if v is KEEP else v


def _held(doc, where, block):
    """Block `block` ("" for the top) as resolved at `where` (nested blocks: merged level by
    level)."""
    if not block:
        out = {k: doc[k] for k in FIGURE_KEYS if k in doc}
        for d in chain(doc, where, ""):
            out.update(d)
        return out
    path = block.split(".")
    out = dict(doc[path[0]]) if len(path) == 1 and path[0] in FIGURE_KEYS and \
        isinstance(doc.get(path[0]), dict) else {}
    for d in chain(doc, where, block):
        sub = _dig(d, path)
        if isinstance(sub, dict):
            out.update(sub)
    return prepared(block, out)


def saved(doc, row, where):
    """Row's value as saved, resolved at `where` (KEEP: none, and no default)."""
    if row.types:
        return _layer_saved(doc, row, where)
    if is_doc(row):
        return _doc_saved(doc, row, where)
    if row.writer == "scene":
        return _scene_saved(doc, row, where)
    block, name = row.block
    held = _held(doc, where, block)
    if row.packed:
        return held
    return held[name] if name in held else row.default


def value(doc, row, where, fallback=None):
    """What row's control shows at `where`; KEEP: the figure has none and the row no default
    (fallback: a document to read it from then, a new figure's look, spec.fresh_look)."""
    v = saved(doc, row, where)
    if v is KEEP and fallback is not None:
        v = saved(fallback, row, Where(where.level, where.kind))
    return KEEP if v is KEEP else row.as_.show(v)


def targets(doc, row, where):
    """The dictionaries a look row is written to at `where` (their block, made if missing)."""
    block, _ = row.block
    holder = _holder(doc, where)
    if where.level in ("panel", "inset") and holder is not None:
        out = [holder.setdefault("opts", {})]
    elif where.level == "kind" and where.kind is not None:
        out = [doc.setdefault("kinds", {}).setdefault(where.kind, {})]
    elif kind_block(block):
        kinds = doc.setdefault("kinds", {})
        out = [kinds.setdefault(k, {}) for k in (list(kinds) or ["plan"])]
    else:
        out = [doc.setdefault("style", {})]
    path = [k for k in block.split(".") if k]
    return [_make(d, path) for d in out]


def _make(d, path):
    for k in path:
        if not isinstance(d.get(k), dict):
            d[k] = dict(d.get(k) or {})
        d = d[k]
    return d


def _put(doc, row, where, v):
    _, name = row.block
    for d in targets(doc, row, where):
        if row.packed:
            d.update(v)
        else:
            d[name] = v


def write(doc, row, where, shown, ctx=None):
    """Row takes its control's value `shown` at `where`, in place (ctx: what a fill needs of
    the runs, fills.Context)."""
    v = row.as_.read(shown)
    if row.types:
        _layer_write(doc, row, where, v, ctx)
        return
    if is_doc(row):
        _doc_write(doc, row, where, v, ctx)
        return
    if row.writer == "scene":
        _scene_write(doc, row, where, v, ctx)
        return
    _put(doc, row, where, v)
    for level, key, val in row.also:
        if level == where.level:
            _put(doc, Row(key, "", None, "", as_=RAW), where, copy.deepcopy(val))
    if row.fills:  # (what else it sets: a fixed box's start)
        from . import fills
        fills.fill_look(row, doc, where, v, ctx)


def put(doc, row, where, v):
    """Look row's saved value v at `where` (no fill, no also)."""
    _put(doc, row, where, v)


def _names(row):
    return row.names if row.packed else (row.block[1],)


def own(doc, row, where):
    """Whether row has a value of its own at `where` over what it inherits (a panel's, an
    inset's, a kind's own colorbar); the figure's never does: it is the top."""
    if row.types:
        over = _over(doc, where)
        return any(k in over for k in _names_of(row))
    if is_doc(row):  # (the document's own: nothing it inherits, but what a new inset has)
        name = _inset_key(row, where)
        if name is None:
            return False
        inset = _inset(doc, where.pid, where.iid) or {}
        return name in inset and inset[name] != _INSET_NEW()[name]
    if row.writer == "scene":
        return where.pid is not None and \
            _scene_unit(row)[0].removesuffix("[]") in _scene_own(doc, where.pid)
    if where.level == "figure":
        return False
    if where.level == "kind" and kind_block(row.block[0]):
        return False  # (the kind's is the top of a kind's block)
    held = (_holder(doc, where) or {}).get("opts") or {} if where.level in ("panel", "inset") \
        else (doc.get("kinds") or {}).get(where.kind) or {}
    sub = _dig(held, [k for k in row.block[0].split(".") if k])
    return isinstance(sub, dict) and any(k in sub for k in _names(row))


def _INSET_NEW():
    from ..shell import docedit as de
    return {**de.INSET_PLACE, **de.INSET_LOOK}


def _inset_key(row, where):
    """An inset's place or box-and-lines key a doc row is (None: another row)."""
    if where.level != "inset" or not row.key.startswith("insets[]."):
        return None
    name = row.key[len("insets[]."):]
    return name if name in _INSET_NEW() else None


def take_back(doc, row, where):
    """Row's own value at `where` gone: it inherits again (empty blocks and opts go too); an
    inset's place or box: back to a new inset's."""
    if is_doc(row):
        name = _inset_key(row, where)
        if name is not None:
            (_inset(doc, where.pid, where.iid) or {}).pop(name, None)
        return
    if row.types:
        from ..shell import docedit as de
        if where.level in ("panel", "inset") and _over(doc, where):
            names = _names_of(row)
            for k in names:
                de.clear_over(doc, _layer_holder(doc, where), where.layer, k)
        return
    if row.writer == "scene":
        from ..shell import docedit as de
        if where.pid is not None:
            de.scene_take_back(doc, where.pid, _scene_unit(row)[0].removesuffix("[]"))
        return
    holder = _holder(doc, where) if where.level in ("panel", "inset") else \
        (doc.get("kinds") or {}).get(where.kind) if where.level == "kind" else None
    if holder is None:
        return
    top = holder.get("opts") or {} if where.level in ("panel", "inset") else holder
    path = [k for k in row.block[0].split(".") if k]
    trail, d = [], top
    for k in path:
        if not isinstance(d.get(k), dict):
            return
        trail.append((d, k))
        d = d[k]
    for k in _names(row):
        d.pop(k, None)
    for parent, k in reversed(trail):  # (blocks left empty go)
        if not parent[k]:
            parent.pop(k)
    if where.level in ("panel", "inset") and not top:
        holder.pop("opts", None)


# ------------------------------------------------------------ 3D scenes (Row.writer "scene")
def _scene_unit(row):
    """(the key of the scene block written whole, the path below it) of a scene row."""
    block, name = row.block
    path = block.split(".")[1:] + [name]  # (below "scene3d")
    return path[0], path[1:]


def _scene_own(doc, pid):
    from ..shell import docedit as de
    return de.scene_own(doc, pid)


def _scene_saved(doc, row, where):
    from ..shell import docedit as de
    unit, rest = _scene_unit(row)
    block = de.scene_block(doc, where.pid if where.level == "panel" else None)
    if unit.endswith("[]"):  # (an item of a list: where.item's)
        items = block.get(unit[:-2]) or []
        block = items[where.item] if where.item is not None and 0 <= where.item < len(items) \
            else {}
        v = _dig(block, rest)
    else:
        v = _dig(block, [unit, *rest])
    return row.default if v is KEEP or (v is None and rest) else v


def _scene_write(doc, row, where, v, ctx=None):
    from ..shell import docedit as de
    unit, rest = _scene_unit(row)
    pid = where.pid if where.level == "panel" else None
    if unit.endswith("[]"):
        items = copy.deepcopy(de.scene_block(doc, pid).get(unit[:-2]) or [])
        if where.item is None or not 0 <= where.item < len(items):
            raise IndexError(f"{row.key}: no item {where.item}")
        _make(items[where.item], rest[:-1])[rest[-1]] = v
        if row.fills:  # (what else it sets in its item)
            from . import fills
            fills.fill_item(row, items[where.item], ctx)
        de.write_scene(doc, pid, unit[:-2], items)
        return
    if not rest:
        de.write_scene(doc, pid, unit, v)
        return
    whole = copy.deepcopy(de.scene_block(doc, pid).get(unit) or {})
    _make(whole, rest[:-1])[rest[-1]] = v
    de.write_scene(doc, pid, unit, whole)


# ------------------------------------------------------------ layers (Row.types)
def panel_of(doc, pid):
    return _panel(doc, pid) or {}


def kind_at(doc, where):
    """The kind of panel a place is in."""
    if where.pid is not None:
        return panel_of(doc, where.pid).get("kind", where.kind)
    return where.kind


def _layer_holder(doc, where):
    """What holds the layer's place: the inset (its own layers) or the panel."""
    if where.level == "inset":
        return _inset(doc, where.pid, where.iid)
    return _panel(doc, where.pid)


def layer_at(doc, where):
    """The layer a layer row is read from at `where`, as drawn there (None: no such layer); at
    the level "viewer" (schema/viewer.py), the document is the layer."""
    if where.level == "viewer":
        return doc
    if where.layer is None:
        return None
    if where.level == "kind":
        return (doc.get("layers") or {}).get(where.layer)
    holder = _layer_holder(doc, where)
    if holder is None:
        return None
    lays = figdraw.panel_layers(doc, holder)
    return lays[where.layer][1] if 0 <= where.layer < len(lays) else None


def layer_type(lay):
    """A layer's type as the layer rows name it: its type, or an entry of another source
    (a parcel series, your own data) type:source."""
    if not lay:
        return None
    t, src = lay.get("type"), lay.get("source")
    return f"{t}:{src}" if src in ("parcels", "table") else t


def _layer_top(row):
    return row.key.split(".")[1]


def _layer_path(row):
    return row.key.split(".")[1:]


def _names_of(row):
    return row.names if row.packed else (_layer_top(row),)


def _over(doc, where):
    """What the panel's layer at `where` changes of its shared layer ({} for a shared one, or a
    layer of the panel's own)."""
    from ..shell import docedit as de
    if where.level not in ("panel", "inset"):
        return {}
    holder = _layer_holder(doc, where)
    items = de.places(doc, holder) if holder is not None else []
    return de.overrides(items[where.layer]) if 0 <= where.layer < len(items) else {}


def _layer_saved(doc, row, where):
    lay = layer_at(doc, where)
    if lay is None:
        return row.default
    if row.packed:
        return lay
    v = _dig(lay, _layer_path(row))
    return row.default if v is KEEP else v


def layer_changes(doc, row, where, v):
    """{top key of the layer: its new value} of row taking v (a nested key: its block whole;
    a packed row: each of its keys)."""
    if row.packed:
        return dict(v)
    path = _layer_path(row)
    if len(path) == 1:
        return {path[0]: v}
    lay = layer_at(doc, where) or {}
    top = copy.deepcopy(lay.get(path[0]) or {})
    _make(top, path[1:-1])[path[-1]] = v
    return {path[0]: top}


def write_layer(doc, where, changes):
    """Changes to the layer at `where`, through docedit (and the colorbar's followers)."""
    from ..shell import bars, docedit as de
    if where.level == "viewer":  # (the layer itself: nothing shares it)
        for k, v in changes.items():
            if v is de.MISSING:
                doc.pop(k, None)
            else:
                doc[k] = v
        return
    if where.level == "kind":
        de.write_shared(doc, where.layer, changes)
        bars.clear_bar_overrides(doc, where.layer, [k for k in changes if k in bars.BAR_KEYS])
        return
    holder = _layer_holder(doc, where)
    de.write_panel(doc, holder, where.layer, changes)
    if where.level == "panel":
        bars.follow_colours(doc, where.pid, where.layer, changes)


def _layer_write(doc, row, where, v, ctx):
    if layer_at(doc, where) is None:
        raise IndexError(f"{row.key}: no layer {where.layer!r} at {where}")
    changes = layer_changes(doc, row, where, v)
    if row.fills:
        from . import fills
        fills.fill(row, doc, where, changes, ctx)
    write_layer(doc, where, changes)


# ------------------------------------------------------------ the document's own (schema/doc.py)
ITEMS = ("runs[]", "annotations[]", "panels[]", "insets[]", "sections[]")


def is_doc(row):
    return not row.key.startswith(("look.", "layer."))


def _doc_place(row):
    """(the list a row's item is in, or "", the path below it) of a document row."""
    head, _, rest = row.key.partition(".")
    if head in ITEMS:
        return head, rest.split(".")
    return "", row.key.split(".")


def doc_item(doc, row, where):
    """The dictionary a document row's path starts from: the document, or its item at `where`
    (None: no such item)."""
    items, _ = _doc_place(row)
    if items == "runs[]":
        return next((r for r in doc.get("runs") or [] if r["id"] == where.item), None)
    if items == "annotations[]":
        ann = doc.get("annotations") or []
        return ann[where.item] if where.item is not None and 0 <= where.item < len(ann) \
            else None
    if items == "panels[]":
        return _panel(doc, where.pid)
    if items == "insets[]":
        return _inset(doc, where.pid, where.iid)
    if items == "sections[]":
        sid = where.item if where.item is not None else \
            (_panel(doc, where.pid) or {}).get("section")
        return (doc.get("sections") or {}).get(sid)
    return doc


def _section_id(doc, where):
    return where.item if where.item is not None else (_panel(doc, where.pid) or {}).get("section")


def _doc_saved(doc, row, where):
    if row.writer == "bar":
        return _bar_saved(doc, row, where)
    item = doc_item(doc, row, where)
    _, path = _doc_place(row)
    if item is None:
        return row.default
    if row.packed:
        held = _dig(item, path[:-1]) if path[:-1] else item
        return held if isinstance(held, dict) else {}
    v = _dig(item, path)
    return row.default if v is KEEP else v


def _doc_put(holder, path, v, packed=False):
    from ..shell.docedit import MISSING
    d = _make(holder, path[:-1])
    for k, x in (v.items() if packed else [(path[-1], v)]):
        if x is MISSING:
            d.pop(k, None)
        else:
            d[k] = x


def _doc_write(doc, row, where, v, ctx):
    item = doc_item(doc, row, where)
    if item is None:
        raise IndexError(f"{row.key}: nothing at {where}")
    _, path = _doc_place(row)
    if row.writer:
        WRITERS[row.writer](doc, row, where, item, path, v, ctx)
    else:
        _doc_put(item, path, v, row.packed)
    for level, key, val in row.also:
        if level == where.level:
            _doc_put(doc, key.split("."), copy.deepcopy(val))


def _grid(doc, row, where, item, path, v, ctx):
    from ..shell import docedit as de
    rows, cols = de.grid_shape(doc)
    de.set_grid(doc, int(v) if path[-1] == "rows" else rows, int(v) if path[-1] == "cols" else cols)


def _shares(doc, row, where, item, path, v, ctx):
    from ..shell import docedit as de
    why = de.set_shares(doc, path[-1], v)
    if why:
        raise ValueError(why)


def _t0(doc, row, where, item, path, v, ctx):
    from ..shell import docedit as de
    de.set_t0(doc, where.item, float(v or 0.0))


def _height(doc, row, where, item, path, v, ctx):
    from ..shell import docedit as de
    z = v if path[-1] == "z" else item.get("z")
    mode = v if path[-1] == "zmode" else item.get("zmode", "height")
    if z is None and path[-1] == "zmode":
        item["zmode"] = mode
        return
    de.set_height(doc, item, None if z in (None, "") else float(z), mode)


def _cell(doc, row, where, item, path, v, ctx):
    from ..shell import docedit as de
    why = de.place_panel(doc, where.pid, list(v))
    if why:
        raise ValueError(why)


def _colorbar(doc, row, where, item, path, v, ctx):
    from ..shell import docedit as de
    de.set_panel_colorbar(doc, where.pid, **{path[-1]: v})


def _bar_saved(doc, row, where):
    """A panel's colorbar setting: what the bar it controls shows (bars.values)."""
    from ..shell import bars
    try:
        bar = bars.bar_of(doc, where.pid)
    except Exception:  # noqa: BLE001  (no bar to read)
        bar = None
    return row.default if bar is None else bars.values(doc, bar)[row.key.rpartition(".")[2]]


def _bar(doc, row, where, item, path, v, ctx):
    """... written to every panel sharing the bar."""
    from ..shell import bars
    bar = bars.bar_of(doc, where.pid)
    if bar is None:
        raise ValueError("this panel has no colorbar")
    bars.set_value(doc, bar, path[-1], v)


def _section(doc, row, where, item, path, v, ctx):
    from ..shell import docedit as de
    de.write_section(doc, _section_id(doc, where), {path[-1]: v})


def _panel_run(doc, row, where, item, path, v, ctx):
    """A panel's other run: it keeps its moment, at that run's nearest output (with ctx.times)."""
    from ..shell import docedit as de
    ts = item.get("time_s")
    if ts is not None and item.get("run") is not None:
        ts = de._moved(doc, ts, item["run"], v)
        outs = getattr(ctx, "times", None)
        outs = outs(v) if outs is not None else None
        if outs:
            ts = min(outs, key=lambda t: abs(float(t) - ts))
    item.update(run=v, time_s=ts)


WRITERS = {"grid": _grid, "shares": _shares, "t0": _t0, "height": _height, "cell": _cell,
           "colorbar": _colorbar, "bar": _bar, "section": _section, "panel run": _panel_run}


def scene_item(doc, row, where):
    """The item of a scene list a row of its items is read from at `where` (None: none)."""
    from ..shell import docedit as de
    unit, _ = _scene_unit(row)
    items = de.scene_block(doc, where.pid if where.level == "panel" else None).get(
        unit.removesuffix("[]")) or []
    return items[where.item] if where.item is not None and 0 <= where.item < len(items) else None
