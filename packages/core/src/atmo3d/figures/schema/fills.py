"""What a row sets beside itself when it changes (Row.fills): a fill layer's new field brings its
colours, a vector its arrows' scale, a difference a diverging colormap, an ensemble statistic its
colours, a recipe its normal form, a parcel set its rule.

Each fill takes the changes a row makes to its layer ({top key: value}, where.layer_changes) and
adds to them.  What a fill needs of the runs (their fields, times, parcel sets) is in a Context;
without it (none given, or it lacks that), the fill does what it can without: the row's own
change is always made."""

import copy
from dataclasses import dataclass

from . import where as W


@dataclass
class Context:
    """What fills (and conditions) need of the runs the figure is of.  fields: the viewer's
    fields (core.fields.Fields); view: the map's view (x0, x1, y0, y1), a fixed box's start;
    pick: choice -> a parcel set's keys (sources.parcel_pick's), or None; parcel_units:
    variable -> its units; times: a run's id -> its output times (s); shown: panel id -> the
    area it shows in the preview (x0, x1, y0, y1), or None."""
    fields: object = None
    view: object = None
    pick: object = None
    parcel_units: object = None
    times: object = None
    shown: object = None
    drawn: object = None  # (the viewer: (lo, hi) of the range a layer was last drawn with)
    relevel: object = None  # (the viewer: (old mode, new mode, z) -> z in the new mode)


def _gone():
    from ..shell.docedit import MISSING
    return MISSING


def _nice(a):
    from ..choices import _nice as nice
    return nice(a)


def _after(doc, where, changes):
    """The layer as it would be with the changes."""
    lay = dict(W.layer_at(doc, where) or {})
    for k, v in changes.items():
        if v is _gone():
            lay.pop(k, None)
        else:
            lay[k] = v
    return lay


# ------------------------------------------------------------ a fill layer's colours
def _field_colours(F, field):
    """A fill field's own colours (spec.layer_defaults), as the card set them."""
    from .. import spec as fg
    from ..choices import known_cmap
    d = fg.layer_defaults("fill", F, field)
    return dict(cmap=known_cmap(d["cmap"]), vmin=d["vmin"], vmax=d["vmax"], extend=d["extend"],
                mask_below=d["mask_below"], units=d["units"])


def _ens_colours(F, lay):
    """An ensemble's colours: a probability 0-100 %, a spread or range from 0, else the
    field's own."""
    st = (lay.get("ens") or {}).get("stat", "mean")
    if st == "prob":
        return dict(cmap="Blues", reverse=False, white_first=True, vmin=0.0, vmax=100.0,
                    scale="linear", mask_below=0.0, nlevels=10, extend="neither")
    own = _field_colours(F, lay["field"]) if F is not None and lay.get("field") in F else {}
    if st in ("sd", "range") and own:
        a = _nice((0.25 if st == "sd" else 0.5) * (float(own["vmax"]) - float(own["vmin"])))
        return dict(cmap="viridis", reverse=False, white_first=False, vmin=0.0, vmax=a,
                    scale="linear", mask_below=None)
    return dict(own, reverse=False) if own else {}


def _minus_colours(lay):
    """A difference: a diverging colormap centred on 0, nothing blanked."""
    a = _nice(0.25 * (float(lay.get("vmax", 1.0)) - float(lay.get("vmin", 0.0))))
    return dict(cmap="RdBu", reverse=True, white_first=False, vmin=-a, vmax=a, scale="linear",
                mask_below=None)


def map_field(row, doc, where, changes, ctx):
    """A layer's new field: a fill's colours, range and units follow it (an ensemble's or a
    difference's colours, theirs)."""
    lay = _after(doc, where, changes)
    F = getattr(ctx, "fields", None)
    if lay.get("type") != "fill" or F is None or lay.get("field") not in F:
        return
    changes.update(_field_colours(F, lay["field"]))
    lay = _after(doc, where, changes)
    if lay.get("ens"):
        changes.update(_ens_colours(F, lay))
    elif lay.get("minus"):
        changes.update(_minus_colours(lay))


def minus(row, doc, where, changes, ctx):
    """A difference on: a diverging colormap; off: the field's own colours."""
    lay = _after(doc, where, changes)
    F = getattr(ctx, "fields", None)
    if lay.get("minus"):
        changes.update(_minus_colours(lay))
    elif F is not None and lay.get("field") in F:
        own = _field_colours(F, lay["field"])
        own.pop("extend")
        changes.update(own, reverse=False)


def ens(row, doc, where, changes, ctx):
    """An ensemble on, or another statistic: its colours (no difference beside it); off: the
    field's own."""
    lay = _after(doc, where, changes)
    F = getattr(ctx, "fields", None)
    if lay.get("ens"):
        if lay.get("minus"):
            changes["minus"] = _gone()
        changes.update(_ens_colours(F, lay))
    elif F is not None and lay.get("field") in F:
        own = _field_colours(F, lay["field"])
        own.pop("extend")
        changes.update(own, reverse=False)


def reduce(row, doc, where, changes, ctx):
    """A time window turned off: none (its times go with it)."""
    r = changes.get("reduce")
    if isinstance(r, dict):
        if not r.get("op"):
            changes["reduce"] = _gone()
        else:
            changes["reduce"] = dict(dict(op="", t0=None, t1=None, every=1), **r)


def vector(row, doc, where, changes, ctx):
    """Another vector: arrows scaled for its magnitudes (a key arrow of its typical one, when
    there is a key)."""
    from ...core import vectors
    d = vectors.VECTORS.get(changes.get("vector"))
    if d is None:
        return
    changes["scale"] = vectors.FIG_SCALE * d.ref
    if (W.layer_at(doc, where) or {}).get("key"):
        changes["key"] = d.ref


# ------------------------------------------------------------ the viewer's layers (schema/viewer.py)
def _viewer_field_of(F, lay):
    try:
        return F[lay.get("field")]
    except (KeyError, TypeError):
        return None


def viewer_field(row, doc, where, changes, ctx):
    """A viewer fill's new field: its own colormap (a difference's: diverging) and range; the
    tool's first fill back on an automatic range."""
    from .viewer import DIFF_CMAP
    lay = _after(doc, where, changes)
    d = _viewer_field_of(getattr(ctx, "fields", None), lay)
    if lay.get("type") != "fill" or d is None:
        return
    changes.update(cmap=DIFF_CMAP if lay.get("minus") else d.cmap, reverse=False)
    if d.vrange:
        changes["vmin"], changes["vmax"] = d.vrange
    if lay.get("role") == "fill":
        changes["auto"] = True


def viewer_minus(row, doc, where, changes, ctx):
    """A viewer difference on: a diverging colormap; off: the field's own; either way on an
    automatic range."""
    from .viewer import DIFF_CMAP
    lay = _after(doc, where, changes)
    d = _viewer_field_of(getattr(ctx, "fields", None), lay)
    if lay.get("minus"):
        changes["cmap"] = DIFF_CMAP
    elif d is not None:
        changes["cmap"] = d.cmap
    changes.update(reverse=False, auto=True)


def viewer_vector(row, doc, where, changes, ctx):
    """A viewer layer's new vector: its typical magnitude as the reference arrow."""
    from ...core import vectors
    d = vectors.VECTORS.get(changes.get("vector"))
    if d is not None:
        changes["ref"] = d.ref


def viewer_mode(row, doc, where, changes, ctx):
    """A viewer layer's level mode changed: its level as the same place in the new mode (a
    model level's height, a height's nearest level: ctx.relevel, ui/layer.py)."""
    conv = getattr(ctx, "relevel", None)
    old, new = doc.get("mode"), changes.get("mode")
    if conv is None or new is None or old == new or new in ("colmax", "colmin"):
        return
    changes["z"] = conv(old, new, doc.get("z"))


def viewer_auto(row, doc, where, changes, ctx):
    """Auto range off: Min and Max start from the range last drawn (ctx.drawn)."""
    last = getattr(ctx, "drawn", None)
    if changes.get("auto") is False and last is not None:
        changes["vmin"], changes["vmax"] = [round(float(v), 4) for v in last]


# ------------------------------------------------------------ an entry's recipe
def _recipe_defaults(lay):
    """A recipe's keys as its rows have them by default (what a normal form left out: a
    radius when the region was not the storm's)."""
    from . import ROWS, KEEP
    t = W.layer_type(lay)
    out = {}
    for r in ROWS:
        if t in r.types and r.key.startswith("layer.recipe.") and r.default is not KEEP:
            out.setdefault(r.key.split(".", 2)[2], copy.deepcopy(r.default))
    return out


def recipe(row, doc, where, changes, ctx):
    """A recipe changed: in its normal form (core's normalize: only the keys that matter), a
    field with no heights read in 2D, a fixed box starting as the map's view; a series' new
    field brings its colours and units, and an automatic label follows."""
    from ...core import azim as caz, dist as cdist, joint as cjoint, series as cser
    from ...core.fields import split_deriv
    old = W.layer_at(doc, where) or {}
    lay = _after(doc, where, changes)
    t, F = lay.get("type"), getattr(ctx, "fields", None)
    r = dict(_recipe_defaults(lay), **(lay.get("recipe") or {}))
    if r.get("region") == "box" and not r.get("box"):
        view = getattr(ctx, "view", None)
        r["box"] = [float(v) for v in view] if view is not None else [0.0, 1.0, 0.0, 1.0]

    def flat(name):
        base = split_deriv(name or "")[1]
        return F is not None and base in F and F[base].ndim == 2

    if t == "series":
        if W.kind_at(doc, where) == "th":
            r["vmode"] = "layer"
        elif flat(r["field"]):
            r["vmode"] = "2d"
        elif r.get("vmode") == "2d":
            r["vmode"] = "layer"
        r = cser.normalize(r)
    elif t == "profile":
        r = cser.normalize(dict(r, vmode="layer"))
    elif t in ("dist", "table"):
        r = cdist.normalize(dict(r, vmode="2d" if flat(r["field"]) else
                                 r.get("vmode") if r.get("vmode") != "2d" else "height"))
    elif t == "joint":
        two = [flat(r.get(k)) for k in ("field", "yfield")]
        vm = r.get("vmode") if r.get("vmode") != "2d" else "height"
        r = cjoint.normalize(dict(r, vmode="2d" if all(two) else "height" if any(two) else vm))
    elif t == "azim":
        r = caz.normalize(r)
    changes["recipe"] = r
    if t == "series":
        _series_follows(old, lay, r, changes, F)


def _series_follows(old, lay, r, changes, F):
    """A series' new field: its colours and range (spec.series_defaults), units; an automatic
    label follows the recipe (one typed stays)."""
    from ...core import series as cser
    from .. import spec as fg
    from ..choices import known_cmap
    if F is None or r["field"] not in F:
        return
    o = old.get("recipe") or {}
    if o.get("field") != r["field"]:
        e = fg.series_defaults(F, r)
        changes.update({k: e[k] for k in ("vmin", "vmax", "extend", "white_first")},
                       cmap=known_cmap(e["cmap"]))
    changes["base_units"] = F[r["field"]].units
    changes["units"] = fg.op_units(changes["base_units"], lay.get("op", ""))
    label = lay.get("label", "")
    if o.get("field") in F:
        was = cser.describe(o, F[o["field"]].label) if "vmode" in o else ""
        if label in ("", was):
            changes["label"] = cser.describe(r, F[r["field"]].label)


def op_units(row, doc, where, changes, ctx):
    """Then apply: its units (d/dz: per m)."""
    from .. import spec as fg
    lay = _after(doc, where, changes)
    changes["units"] = fg.op_units(lay.get("base_units", ""), lay.get("op", ""))


def runs(row, doc, where, changes, ctx):
    """An entry's runs: its run, the first of them (every run: the figure's first)."""
    ks = changes.get("runs")
    first = (doc.get("runs") or [{}])[0].get("id")
    changes["run"] = ks[0] if ks else first


def run(row, doc, where, changes, ctx):
    """An entry's other run: its time, the same time since that run's time zero."""
    from .. import draw as figdraw
    old = W.layer_at(doc, where) or {}
    ts, ids = old.get("time_s"), [r["id"] for r in doc.get("runs") or []]
    if ts is None or old.get("run") not in ids or changes.get("run") not in ids:
        return
    changes["time_s"] = figdraw.moved_time(dict(runs=doc["runs"]), float(ts),
                                           ids.index(old["run"]), ids.index(changes["run"]))


def pset(row, doc, where, changes, ctx):
    """Another parcel set picked (the viewer's, or a saved one): its rule or parcels, name and
    colour."""
    pick = getattr(ctx, "pick", None)
    choice = changes.pop("name", None)
    if pick is None or not choice:
        return
    src = pick(choice)
    if src is None:
        return
    changes.update({k: v for k, v in src.items() if k != "color" or v})


def pvar(row, doc, where, changes, ctx):
    """Parcels coloured by another variable: its units (a parcel series': its base units)."""
    from .. import spec as fg
    units_of = getattr(ctx, "parcel_units", None)
    lay = _after(doc, where, changes)
    var = lay.get("cvar") if lay.get("type") == "parcels" else lay.get("var")
    units = units_of(var) if units_of is not None and var else ""
    if lay.get("type") == "parcels":
        changes["units"] = units
    else:
        changes["base_units"] = units
        changes["units"] = fg.op_units(units, lay.get("op", ""))


def table_units(row, doc, where, changes, ctx):
    """Your own data's units: its base units too."""
    changes["base_units"] = changes.get("units", "")


def table_header(row, doc, where, changes, ctx):
    """Your data's header ("rain (mm)" for its values): the label and units, unless you gave
    them already (a series' base units with its units)."""
    import re
    names = (changes.get("table") or {}).get("names")
    if not names or len(names) < 2:
        return
    m = re.match(r"^(.*?)\s*[\(\[](.+)[\)\]]\s*$", str(names[1]))
    lab, units = (m.group(1), m.group(2)) if m else (str(names[1]), "")
    lay = W.layer_at(doc, where) or {}
    if lab and str(lay.get("label") or "").strip() in ("", "My data"):
        changes["label"] = lab
    if units and not str(lay.get("units") or "").strip():
        changes["units"] = units
        if "base_units" in lay:
            changes["base_units"] = units


# ------------------------------------------------------------ an item of a 3D scene's list
def scene_vector(row, item, ctx):
    """Another vector: its typical magnitude as the reference length."""
    from ...core import vectors
    d = vectors.VECTORS.get(item.get("q"))
    if d is not None:
        item["ref"] = d.ref


def scene_pvar(row, item, ctx):
    """Parcels coloured by another variable: its units, and its own range."""
    units_of = getattr(ctx, "parcel_units", None)
    var = item.get("cvar") or ""
    item.update(units=units_of(var) if units_of is not None and var else "", vmin=None,
                vmax=None)


def scene_pset(row, item, ctx):
    """Another parcel set picked: its rule or parcels, name and colour."""
    pick = getattr(ctx, "pick", None)
    choice = item.pop("name", None)
    src = pick(choice) if pick is not None and choice else None
    if src is None:
        item["name"] = choice if choice and ":" not in str(choice) else item.get("name", "parcels")
        return
    item.update({k: v for k, v in src.items() if k != "color" or v})


FILL_ITEMS = {"scene vector": scene_vector, "scene pvar": scene_pvar, "pset": scene_pset}


def fill_item(row, item, ctx=None):
    """What row's change also sets in its item of a scene's list, in place."""
    FILL_ITEMS[row.fills](row, item, ctx)


FILLS = {"map field": map_field, "minus": minus, "ens": ens, "reduce": reduce, "vector": vector,
         "recipe": recipe, "op units": op_units, "runs": runs, "run": run, "pset": pset,
         "pvar": pvar, "table units": table_units, "table header": table_header,
         "viewer field": viewer_field, "viewer minus": viewer_minus,
         "viewer vector": viewer_vector, "viewer auto": viewer_auto,
         "viewer mode": viewer_mode}


def fill(row, doc, where, changes, ctx=None):
    """What row's change also sets, added to `changes`."""
    FILLS[row.fills](row, doc, where, changes, ctx)


# ------------------------------------------------------------ a look row's
def area_box(row, doc, where, v, ctx):
    """A fixed box chosen with none yet: it starts as what the panel shows in the preview, else
    the map's view."""
    from . import BY_KEY, KEEP
    if v != "box":
        return
    box = BY_KEY["look.domain.box"]
    if W.value(doc, box, where) not in (None, "", KEEP):
        return
    start = None
    if where.pid is not None and getattr(ctx, "shown", None) is not None:
        start = ctx.shown(where.pid)
    if start is None:
        start = getattr(ctx, "view", None)
    if start is not None:
        W.write(doc, box, where, box.as_.show([round(float(a), 2) for a in start]))


LOOK_FILLS = {"area box": area_box}


def fill_look(row, doc, where, v, ctx=None):
    """What a look row's change also sets, in place."""
    LOOK_FILLS[row.fills](row, doc, where, v, ctx)
