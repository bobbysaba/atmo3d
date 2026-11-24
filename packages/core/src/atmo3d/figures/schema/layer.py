"""The layer rows of the schema: each setting of a layer, by layer type
(docs-dev/figures-ui-plan.md, Phase 2.1b).  A row's key is layer.<key> (layer.recipe.z0: the key
z0 of its recipe); its types, the layer types it is a setting of.  An entry of its own
source is a type of its own: "series:parcels" (a parcel series), "series:table" and
"profile:table" (your own data), as where.layer_type names them.

Levels: a map layer (plan views, cross-sections) is a shared layer (kind: layers[id], every panel
drawing it), as one panel draws it (panel: what it changes of the shared layer, or a layer of
its own), or an inset's; an entry (a series, a sounding, ...) is a panel's own.

What a setting shows under is a condition (Row.when) on the layer's other settings; what it sets beside itself (a fill's field: its colours) is a fill
(Row.fills, schema/fills.py)."""

from ...core import geo
from ...core import vectors
from .. import choices as C
from ..draw import base as drawbase
from ..spec import panels as specpanels, tables as spectables
from . import (
    BLANKABLE, CMAP, COLOUR, COLOUR_AUTO, COLOUR_NONE, CONTOUR_LEVELS, FIELD, FIELD_D, KEEP,
    PSET, PVAR, RUN, RUNS, TEXT, TIME, TIMES, TOGGLE, WHEN, XY, As, Control, Row, _xy, _xy_text,
    auto, choice, integer, multi, number, real_or, run_or, text, time_or,
)

MAP = ("fill", "contour", "shade", "vectors", "track", "line", "sector", "parcels", "boundaries")
FIELDED = ("fill", "contour", "shade")
MAP_KINDS = ("plan", "xsec")
MAP_LEVELS = ("kind", "panel", "inset")
OWN = ("panel",)  # (an entry: a panel's own)
TIMED = ("sounding", "dist", "profile", "joint", "azim")  # (one run, at a time)


def _gone():
    """docedit.MISSING: what a blank leaves the layer without (its key goes)."""
    from ..shell.docedit import MISSING
    return MISSING


GONE_BLANK = As(lambda v: v, lambda v: _gone() if v in (None, "") else v)  # (blank: no key)
GONE_OFF = As(bool, lambda v: True if v else _gone())  # (a box only saved when ticked)
PAIR = As(_xy_text, lambda v: _xy(v) or [0.0, 0.0])  # (x, y, saved as a list)
ABOVE = {"Above": True, "Below": False}


def block(fresh):
    """A toggle that makes a block of the layer (a difference, an ensemble): ticked, `fresh`;
    unticked, none."""
    import copy
    return As(bool, lambda v: copy.deepcopy(fresh) if v else _gone())


def L(types, section, *specs, kinds=MAP_KINDS, levels=MAP_LEVELS, **common):
    """Layer rows of `types` in `section`: each spec (key, label, control[, default][, {more}])."""
    out = []
    for spec in specs:
        key, label, control, *more = spec
        over = more.pop() if more and isinstance(more[-1], dict) else {}
        kw = dict(dict(section=section, kinds=kinds, levels=levels, types=tuple(types)), **common)
        if more:
            kw["default"] = more[0]
        kw.update(over)
        out.append(Row(f"layer.{key}", label, control, **kw))
    return out


# ------------------------------------------------------------ conditions about the layer
def _kind_here(doc, where):
    from . import where as W
    return W.kind_at(doc, where)


def _xsec(doc, where, ctx=None):
    return _kind_here(doc, where) == "xsec"


def _th(doc, where, ctx=None):
    return _kind_here(doc, where) == "th"


def _by_height(doc, where, ctx=None):
    """Panels at heights of their own (a panel's: this one; a shared layer's: any of its kind)."""
    from . import where as W
    if where.level in ("panel", "inset"):
        return W.panel_of(doc, where.pid).get("z") is not None
    return any(p.get("z") is not None for p in doc.get("panels") or []
               if p["kind"] == _kind_here(doc, where))


def _framed(doc, where, ctx=None):
    from . import where as W
    q = (W.layer_at(doc, where) or {}).get("vector", "wind")
    return vectors.VECTORS[q].framed if q in vectors.VECTORS else True


def _three_d(doc, where, ctx=None):
    """The layer's fields have heights (a joint distribution: both); unknown without the
    runs' fields: yes."""
    from . import where as W
    F = getattr(ctx, "fields", None)
    lay = W.layer_at(doc, where) or {}
    r = lay.get("recipe") or {}
    names = [n for n in (r.get("field"), r.get("yfield")) if n] or [lay.get("field")]
    if F is None:
        return True
    from ...core.fields import split_deriv
    return all(F[split_deriv(n)[1]].ndim != 2 for n in names if n and split_deriv(n)[1] in F)


def _several_runs(doc, where, ctx=None):
    """Its runs are more than one (every run: None)."""
    from . import where as W
    runs = (W.layer_at(doc, where) or {}).get("runs")
    return runs is None or len(runs) > 1


def _bar_keys_here(doc, where, ctx=None):
    """A colorbar's label, ticks and arrows are set here: a panel's are in its Colorbar section
    (plan views, cross-sections, time-height); a shared layer's while a bar speaks for it."""
    from . import where as W
    from .. import draw as figdraw
    from ..shell import bars
    lay = W.layer_at(doc, where) or {}
    if where.level == "kind":
        return not figdraw.bar_fill(lay) or bars.layer_has_bar(doc, where.layer)
    if where.level == "inset":
        return False
    return _kind_here(doc, where) not in ("plan", "xsec", "th")


def _colours_here(doc, where, ctx=None):
    """A panel's colours are its own, unless they follow the panel whose bar it shares."""
    from ..shell import bars, docedit as de
    if where.level != "panel" or _kind_here(doc, where) not in ("plan", "xsec", "th"):
        return True
    p = de.panel_by_id(doc, where.pid)
    bar = bars.bar_of(doc, where.pid) if bars.place(doc, p) == where.layer else None
    return not (bar and bar["follows"] and bar["members"][0] != where.pid)


def _framed_item(doc, where, ctx=None):
    """A scene's vectors (where.item) of a vector that has a frame."""
    from . import BY_KEY, where as W
    item = W.scene_item(doc, BY_KEY["look.scene3d.vecs[].q"], where) or {}
    q = item.get("q", "wind")
    return vectors.VECTORS[q].framed if q in vectors.VECTORS else True


WHEN.update({"framed item": _framed_item, "xsec": _xsec, "th": _th, "by height": _by_height, "framed": _framed,
             "3d": _three_d, "several runs": _several_runs, "bar keys here": _bar_keys_here,
             "colours here": _colours_here})


# ------------------------------------------------------------ map layers (plan, cross-section)
LAYER_ROWS = [
    *L(MAP, "Layer",
       ("on", "Drawn", TOGGLE, True),
       ("run", "Run", run_or("the panel's"), KEEP, {"as_": GONE_BLANK, "when": "!ens"})),
    *L(MAP, "Layer",
       ("time_s", "Time", time_or("the panel's"), KEEP, {"as_": GONE_BLANK}),
       ("time_lock", "Keep this time in animations", TOGGLE, False,
        {"as_": GONE_OFF, "when": "time_s"}), levels=("panel", "inset")),
]

FIELD_ROWS = [
    *L(FIELDED, "Field",
       ("field", "Field", FIELD_D, KEEP, {"fills": "map field"})),
    *L(FIELDED, "Field",
       ("mode", "Level", choice("levelmodes"), "height"),
       ("z", "Height (km)", number(step=0.25), 1.0,
        {"when": "mode=level|msl or mode=height and !@by height or mode=height and z_fixed"}),
       ("z_fixed", "Own height (not the panel's)", TOGGLE, False,
        {"when": "@by height and mode=height"}), kinds=("plan",)),
    *L(FIELDED, "Time window",
       ("reduce.op", "Over a time window", choice(C.REDUCE), "", {"fills": "reduce"}),
       ("reduce.t0", "From", time_or("the run's first output"), None, {"when": "reduce.op"}),
       ("reduce.t1", "To", time_or("the panel's time"), None, {"when": "reduce.op"}),
       ("reduce.every", "Every nth output", integer(start=1), 1,
        {"when": "reduce.op", "as_": As(int, lambda v: max(1, int(v or 1)))}),
       kinds=("plan",)),
]

FILL_ROWS = [
    *L(("fill",), "Field",
       ("style", "Draw as", choice({"Grid cells": "mesh", "Filled contours": "contourf"}), "mesh"),
       ("mask_below", "Blank where ≤", auto(), None,
        {"as_": BLANKABLE, "help": "Values at or below this are not drawn (blank: off)"})),
    *L(("fill",), "Colours",
       ("cmap", "Colormap", CMAP, "viridis"),
       ("reverse", "Reverse", TOGGLE, False),
       ("white_first", "Start from white", TOGGLE, False),
       ("vmin", "Min", number(), 0.0),
       ("vmax", "Max", number(), 1.0),
       ("nlevels", "Colour steps (0: smooth)", integer(0, 60), 0),
       ("scale", "Scale", choice({"Linear": "linear", "Logarithmic": "log"}), "linear"),
       when="@colours here", tag="fill"),
    *L(("fill",), "Colours",
       ("alpha", "Opacity (0–1)", number(0.0, 1.0, 0.1), 1.0, {"as_": real_or(1.0)}),
       tag="fill"),
    *L(("fill",), "Colorbar",
       ("extend", "Colorbar arrows", choice(C.EXTEND), "auto"),
       ("cbar_label", "Colorbar label (blank: Style's, else units)", text(), "",
        {"as_": TEXT, "help": "Sets the colorbar of this panel. Panels sharing a colorbar: the "
                              "first label among them"}),
       ("cbar_ticks", "Colorbar ticks (blank: Style's, else auto)", text("0:60:10"), "",
        {"as_": TEXT}), when="@bar keys here", tag="fill"),
    *L(("fill",), "Difference",
       ("minus", "Difference: minus another run or time", TOGGLE, KEEP,
        {"as_": block(dict(run=None, time_s=None, grid="ask")), "when": "!ens",
         "fills": "minus"}),
       ("minus.run", "Minus run", run_or("the layer's"), None, {"when": "minus and !ens"}),
       ("minus.time_s", "Minus time", Control("time", "of:minus.run", blank=True,
                                              placeholder="the layer's"), None,
        {"when": "minus and !ens"}),
       ("minus.grid", "If the grids differ", choice(C.GRIDS), "ask",
        {"when": "minus and !ens"})),
    *L(("fill",), "Ensemble",
       ("ens", "Ensemble: a statistic over several runs", TOGGLE, KEEP,
        {"as_": block(dict(runs=None, stat="mean", threshold=0.0, above=True, grid="ask")),
         "fills": "ens", "tag": "fill",
         "help": "The field of each of the runs at the layer's time (the layer's Run is not "
                 "used), combined cell by cell; runs without output at that time are left "
                 "out."}),
       ("ens.runs", "Runs (blank: all)", Control("runs", "some"), None, {"when": "ens"}),
       ("ens.stat", "Statistic", choice(C.ENS_STATS), "mean", {"when": "ens", "fills": "ens"}),
       ("ens.threshold", "Threshold", number(), 0.0, {"when": "ens and ens.stat=prob"}),
       ("ens.above", "Where the value is", choice(ABOVE), True,
        {"when": "ens and ens.stat=prob"}),
       ("ens.grid", "If the grids differ", choice(C.GRIDS), "ask", {"when": "ens"})),
]

LOOK_ROWS = [
    *L(("contour", "vectors", "line", "sector", "boundaries"), "Look",
       ("color", "Colour", COLOUR, "k")),
    *L(("contour", "line", "sector", "boundaries"), "Look",
       ("lw", "Line width", number(step=0.25), 1.0)),
    *L(("contour", "shade", "track", "line", "sector", "parcels", "boundaries"), "Look",
       ("legend", "Legend entry (blank: none)", text("e.g. w = 10, 20 m s⁻¹"), "",
        {"as_": TEXT})),
]

CONTOUR_ROWS = L(
    ("contour",), "Lines",
    ("levels", "Levels (e.g. 10, 20 or -6:6:2)", CONTOUR_LEVELS, "10, 20",
     {"as_": As(str, lambda v: str(v).strip())}),
    ("neg_dashed", "Dash negative", TOGGLE, True),
    ("clabel", "Label the lines", TOGGLE, False),
    ("clabel_size", "Label size (pt)", number(4, step=1), 8.0,
     {"when": "clabel", "as_": real_or(8.0)}),
    ("clabel_fmt", "Label format", text("%g"), "%g", {"when": "clabel"}))

SHADE_ROWS = [
    *L(("shade",), "Shading",
       ("threshold", "Threshold", number(), 10.0),
       ("above", "Shade", choice(ABOVE), True),
       ("color", "Colour", COLOUR, "magenta", {"tag": "shade"}),
       ("alpha", "Opacity (0–1)", number(0.0, 1.0, 0.1), 0.6, {"tag": "shade"}),
       ("hatch", "Pattern", choice(C.HATCHES), ""),
       ("hatch_lw", "Pattern line width", number(0.1, step=0.1), 0.6, {"when": "hatch"}),
       ("outline", "Outline", COLOUR_NONE, "", {"as_": TEXT}),
       ("lw", "Outline width", number(step=0.25), 1.0, {"when": "outline", "tag": "shade"})),
]

_ARROWS = "style=arrows or style=barbs and @xsec"  # (barbs in a section: arrows)
_BARBS = "style=barbs and !@xsec"
VECTOR_ROWS = [
    *L(("vectors",), "Vectors",
       ("vector", "Vector", choice("vectors"), "wind", {"fills": "vector"}),
       ("style", "Draw as", choice({"Arrows": "arrows", "Barbs (plan views)": "barbs",
                                    "Streamlines": "streamlines"}), "arrows", {"tag": "vectors"}),
       ("frame", "Frame", choice("frames"), "ground", {"when": "@framed"})),
    *L(("vectors",), "Vectors",
       ("z", "Height (km)", number(step=0.25), 0.0,
        {"when": "!@by height or z_fixed", "tag": "vectors"}),
       ("z_fixed", "Own height (not the panel's)", TOGGLE, False,
        {"when": "@by height", "tag": "vectors"}), kinds=("plan",)),
    *L(("vectors",), "Vectors",
       ("spacing", "Spacing (km)", number(step=0.25), 2.0, {"when": "style!=streamlines"})),
    *L(("vectors",), "Vectors",
       ("zspacing", "Vertical spacing (km)", number(step=0.1), 0.5,
        {"when": "style!=streamlines"}), kinds=("xsec",)),
    *L(("vectors",), "Arrows",
       ("scale", "Scale (larger: shorter)", number(step=25), 250.0,
        {"when": _ARROWS, "tag": "vectors"}),
       ("width", "Arrow width", number(step=0.0005), 0.002, {"when": _ARROWS}),
       ("key", "Key arrow (0: none)", number(step=5), 0.0, {"when": _ARROWS}),
       ("density", "Density", number(0.25, step=0.25), 1.5, {"when": "style=streamlines"}),
       ("slw", "Line width", number(step=0.1), 0.8, {"when": "style=streamlines or " + _BARBS}),
       ("arrowsize", "Arrow size", number(step=0.25), 1.0, {"when": "style=streamlines"}),
       ("barb_len", "Barb length", number(2, step=0.5), 5.5, {"when": _BARBS}),
       ("barb_units", "Barbs in", choice({"knots": "kt", "m/s": "ms"}), "kt",
        {"when": _BARBS + " and vector=wind"})),
]

TRACK_ROWS = [
    *L(("track",), "Look",
       ("run_color", "Run's colour", TOGGLE, False),
       ("color", "Colour", COLOUR, "k", {"when": "!run_color", "tag": "track"}),
       ("lw", "Line width", number(step=0.25), 1.0, {"tag": "track"}),
       ("marker", "Dot at the panel time", TOGGLE, True, {"tag": "track"})),
    *L(("track", "sector"), "Look",
       ("ls", "Line style", choice(C.LINE_STYLES), "-")),
]

SECTION_LINE_ROWS = L(
    ("line",), "Section line",
    ("which", "Sections", choice({"All, labelled in turn": "all", "The panel's own": "panel"}),
     "all"),
    ("labels", "End labels", text(), "",
     {"help": "The first section's ends; the others step on (A, A′ → B, B′)"}))

SECTOR_ROWS = L(
    ("sector",), "Sector",
    ("center", "Centre", choice(C.AZ_CENTERS), "track"),
    ("offx", "Offset x (km)", number(step=1.0), 0.0, {"when": "center!=point"}),
    ("offy", "Offset y (km)", number(step=1.0), 0.0, {"when": "center!=point"}),
    ("cx", "x (km)", number(step=1.0), 0.0, {"when": "center=point"}),
    ("cy", "y (km)", number(step=1.0), 0.0, {"when": "center=point"}),
    ("ref", "Azimuth 0", choice(C.AZ_REFS), "motion"),
    ("az0", "Azimuth from (°)", number(step=15.0), 0.0),
    ("az1", "to (°)", number(step=15.0), 360.0),
    ("rmax", "Radius (km)", number(step=1.0), 20.0),
    help="The sector of an azimuthal mean panel, at each panel's time: azimuths clockwise from "
         "the storm's motion (its track's) or from north, from the first to the second (0 to "
         "360: a circle).")


def _step_shown(step):
    s = float(step or 0.0)
    return min(geo.STEPS, key=lambda v: abs(v - s)) if s > 0 else 0.0


BOUNDARY_ROWS = L(
    ("boundaries",), "Boundaries",
    ("kinds", "Lines", multi({geo.KIND_LABELS[k]: k for k in geo.KINDS}), list(geo.SHOWN),
     {"as_": As(lambda v: [k for k in v or [] if k in geo.KINDS], list)}),
    ("grid", "Lat/lon lines", TOGGLE, False),
    ("step", "Every", choice({"Auto": 0.0, **{f"{s:g}°": s for s in geo.STEPS}}), 0.0,
     {"when": "grid", "as_": As(_step_shown, float)}),
    ("grid_labels", "Label them at the edges", TOGGLE, True, {"when": "grid"}),
    help="Coastlines, borders, states, lakes and US counties where the run's grid sits on the "
         "Earth (its map projection).")

PARCEL_ROWS = [
    *L(("parcels",), "Parcels",
       ("name", "Parcels", PSET, "parcels",
        {"fills": "pset", "help": "The parcel set drawn: pick another set of the viewer, or a "
                                  "saved one"}),
       ("cvar", "Colour by", PVAR, "", {"fills": "pvar", "tag": "parcels"}),
       ("color", "Colour", COLOUR, "k", {"when": "!cvar", "tag": "parcels"})),
    *L(("parcels",), "Parcels",
       ("cmap", "Colormap", CMAP, "viridis"),
       ("reverse", "Reverse", TOGGLE, False),
       ("vmin", "Min", auto(), None, {"as_": BLANKABLE}),
       ("vmax", "Max", auto(), None, {"as_": BLANKABLE}),
       ("cbar_label", "Colorbar label (blank: variable)", text(), "", {"as_": TEXT}),
       when="cvar", tag="parcels"),
    *L(("parcels",), "Parcels",
       ("tails", "Tails", choice(C.PAR_TAILS), "until"),
       ("minutes", "Minutes", number(0.0, step=5.0), 10.0, {"when": "tails=last"}),
       ("moving", "Tails seen from", choice(C.PAR_MOVING), "grid",
        {"help": "Relative to the storm: each point moved back by how far the storm went "
                 "between its time and the panel time (the heads stay put)"}),
       ("move_u", "u (m/s)", number(step=1.0), 0.0, {"when": "moving=motion"}),
       ("move_v", "v (m/s)", number(step=1.0), 0.0, {"when": "moving=motion"}),
       ("lw", "Line width", number(0.0, step=0.2), 0.8, {"tag": "parcels"}),
       ("alpha", "Opacity (0–1)", number(0.0, 1.0, 0.1), 0.8, {"tag": "parcels"}),
       ("ms", "Head size", number(0.0, step=0.5), 3.0),
       ("heads", "Heads at the panel time", TOGGLE, True),
       ("interp", "Between parcel times: interpolate", TOGGLE, True)),
    *L(("parcels",), "Parcels",
       ("within", "Section ± (km)", number(0.0, step=0.5), 1.0,
        {"help": "The parcels at most this far from the section's line, drawn where they "
                 "project onto it"}),
       ("xs_tails", "Tails on the section", choice(C.PAR_XS_TAILS), "near"), kinds=("xsec",)),
]


# ------------------------------------------------------------ entries (a panel's own)
def E(types, kinds, section, *specs, **common):
    return L(types, section, *specs, kinds=kinds, levels=OWN, **common)


def _region(types, kinds, tag="", when=""):
    """The region a recipe reads (Region; around the storm: its radius and offset)."""
    pre = f"{when} and " if when else ""
    return E(types, kinds, "Where",
             ("recipe.region", "Region", choice(C.SER_REGIONS), "domain",
              {"fills": "recipe", "when": when}),
             ("recipe.radius", "Radius (km)", number(step=0.5), 5.0,
              {"fills": "recipe", "when": pre + "recipe.region=track"}),
             ("recipe.offset", "Offset x, y (km)", XY, [0.0, 0.0],
              {"fills": "recipe", "when": pre + "recipe.region=track", "as_": PAIR}),
             tag=tag)


ENTRY_LABEL = E(("series", "sounding", "dist", "profile", "joint", "azim"),
                ("line", "th", "sounding", "dist", "profile", "joint", "azim"), "Look",
                ("label", "Legend text (blank: automatic)", text(), "", {"as_": TEXT}))

ONE_RUN = [  # (a sounding, distribution, joint distribution, azimuthal mean)
    *E(("sounding", "dist", "joint", "azim"), ("sounding", "dist", "joint", "azim"),
       "Run and time", ("run", "Run", RUN, KEEP, {"tag": "entry", "fills": "run"})),
    *E(TIMED, ("sounding", "dist", "profile", "joint", "azim"), "Run and time",
       ("time_s", "Time", TIME, 0.0, {"tag": "entry"}),
       ("time_lock", "Keep this time in animations", TOGGLE, False,
        {"as_": GONE_OFF, "tag": "entry",
         "help": "Holds it still under the ones that step in an animation"})),
    *E(("joint",), ("joint",), "Run and time",
       ("time_s1", "To (a time window)", time_or("— (this time only)"), None,
        {"tag": "joint", "help": "Take the pairs of every output from Time to this one"})),
    *E(("azim",), ("azim",), "Run and time",
       ("time_s1", "Composite to (a time window)", time_or("— (this time only)"), None,
        {"tag": "azim", "help": "Every output from Time to this one, each around its own "
                                "centre"})),
    *E(("profile",), ("profile",), "Run and time",
       ("time_s1", "Mean to (a time window)", time_or("— (this time only)"), None,
        {"tag": "profile", "help": "Average the profiles of every output from Time to this "
                                   "one"})),
]

AUTO_COLOUR = E(("sounding", "dist", "profile", "joint", "azim"),
                ("sounding", "dist", "profile", "joint", "azim"), "Look",
                ("color", "Colour", COLOUR_AUTO, "",
                 {"tag": "entry", "as_": TEXT,
                  "help": "Automatic: the run's colour when each of the panel's is from "
                          "another run, else the next colour"}))

ENS_BAND = E(("series", "profile"), ("line", "profile"), "Ensemble band",
             ("ens", "Ensemble of its runs", choice(C.ENS_BANDS), "", {"when": "@several runs"}),
             ("ens_mid", "Centre line", choice(C.ENS_MIDS), "mean",
              {"when": "@several runs and ens"}),
             ("ens_members", "Runs' own lines", choice(C.ENS_MEMBERS), "faint",
              {"when": "@several runs and ens"}),
             ("ens_alpha", "Band opacity", number(0.0, 1.0, 0.05), 0.25,
              {"when": "@several runs and ens",
               "as_": As(float, lambda v: 0.25 if v in (None, "") else float(v))}))

VALUES = E(("series", "profile"), ("line", "profile"), "Values",
           ("edits", "Values (your edits of them)", Control("values"), KEEP,
            {"help": "Its values, and your edits of them"}))

SERIES_LINE_LOOK = E(  # (a time series' line: computed, a parcel series or your own data)
    ("series", "series:parcels", "series:table"), ("line",), "Look",
    ("color", "Colour", COLOUR, "k", {"tag": "line"}),
    ("ls", "Line style", choice(C.LINE_STYLES), "-", {"tag": "line"}),
    ("lw", "Line width", number(step=0.25), 1.5, {"tag": "line", "as_": real_or(1.5)}),
    ("marker", "Markers", choice(C.MARKERS), "", {"tag": "line"}),
    ("axis", "y axis", choice({"By units": "auto", "Own axis (right)": "right"}), "auto"),
    ("ylabel", "Axis label (blank: units)", text(), ""))

SERIES_ROWS = [
    *E(("series",), ("line", "th"), "Run",
       ("runs", "Run", RUNS, None, {"tag": "series"})),
    *E(("series",), ("line", "th"), "Field",
       ("recipe.field", "Field", FIELD_D, KEEP, {"fills": "recipe", "tag": "series"})),
    *E(("series",), ("line",), "Field",
       ("recipe.vmode", "Vertical", choice(C.SER_VMODES), "layer",
        {"fills": "recipe", "when": "@3d"}),
       ("recipe.z", "Height (km)", number(step=0.25), 1.0,
        {"fills": "recipe", "when": "@3d and recipe.vmode=height"}), tag="series"),
    *E(("series",), ("line", "th"), "Field",
       ("recipe.z0", "Read from (km)", number(step=0.5), 0.0,
        {"fills": "recipe", "when": "@3d and recipe.vmode=layer or @3d and @th"}),
       ("recipe.z1", "Read to (km)", number(step=0.5), 10.0,
        {"fills": "recipe", "when": "@3d and recipe.vmode=layer or @3d and @th"}),
       tag="series"),
    *_region(("series", "profile", "dist", "joint"), ("line", "th", "profile", "dist", "joint")),
    *E(("series", "profile"), ("line", "th", "profile"), "Field",
       ("recipe.reduce", "Reduce", choice(C.SER_REDUCE), "max", {"fills": "recipe"}),
       ("recipe.pct", "Percentile", number(step=0.5), 99.0,
        {"fills": "recipe", "when": "recipe.reduce=pct"})),
    *E(("series",), ("line", "th"), "Field",
       ("op", "Then apply", choice(C.SER_OPS), "",
        {"fills": "op units", "tag": "series",
         "help": "Applied to this series once computed (a Derivative is taken of the field "
                 "before the reduction)"}),
       ("t0_min", "Time zero (min)", number(step=1.0), 0.0,
        {"when": "t0_min", "tag": "series",
         "help": "From an older figure: adds to its run's time zero (on the Runs node), which "
                 "is the place to set it. At 0 this box goes away"})),
    *E(("series",), ("th",), "Colours",
       ("cmap", "Colormap", CMAP, "viridis"),
       ("reverse", "Reverse", TOGGLE, False),
       ("white_first", "Start from white", TOGGLE, False),
       ("vmin", "Min", number(), 0.0, {"as_": As(float, lambda v: float(v or 0))}),
       ("vmax", "Max", number(), 1.0, {"as_": As(float, lambda v: float(v or 0))}),
       ("nlevels", "Colour steps (0: smooth)", integer(0, 60), 0),
       when="@colours here", tag="series"),
    *E(("series",), ("th",), "Colorbar",
       ("extend", "Colorbar arrows", choice(C.EXTEND), "auto"),
       ("cbar_label", "Colorbar label (blank: Style's, else units)", text(), "", {"as_": TEXT}),
       ("cbar_ticks", "Colorbar ticks (blank: Style's, else auto)", text("0:60:10"), "",
        {"as_": TEXT}), when="@bar keys here", tag="series"),
]

PARCEL_SERIES_ROWS = E(
    ("series:parcels",), ("line",), "Parcels",
    ("runs", "Run", RUN, KEEP, {"tag": "parcels", "as_": As(lambda v: (v or [None])[0],
                                                           lambda v: [v])}),
    ("name", "Parcels", PSET, "parcels", {"fills": "pset", "tag": "series"}),
    ("var", "Variable", PVAR, "", {"fills": "pvar"}),
    ("op", "Plot", choice(C.PAR_OPS), "", {"fills": "op units", "tag": "parcels"}),
    ("ens_mid", "Centre line", choice(C.ENS_MIDS), "mean", {"tag": "parcels"}),
    ("ens", "Band over the parcels", choice(C.ENS_BANDS), "", {"tag": "parcels"}),
    ("ens_alpha", "Band opacity", number(0.0, 1.0, 0.05), 0.25, {"when": "ens", "tag": "parcels"}),
    ("each", "Parcels' own lines", integer(0, specpanels.PARCEL_EACH_MAX), 0,
     {"help": f"Draw this many parcels' own lines too, spread through the set (0: none; at "
              f"most {specpanels.PARCEL_EACH_MAX})"}),
    ("ens_members", "Their look", choice(C.PAR_EACH_LOOK), "faint",
     {"when": "each and ens or each and ens_mid", "tag": "parcels"}),
    ("label", "Legend text", text(), "", {"as_": TEXT, "tag": "parcels"}),
    ("t0_min", "Time zero (min)", number(step=1.0), 0.0, {"when": "t0_min", "tag": "parcels"}))

TABLE_DATA = "Your data"
OWN_DATA_ROWS = [
    *E(("series:table",), ("line",), TABLE_DATA,
       ("table", "Your data: time (min), value", Control("table", "time"), KEEP,
        {"tag": "time", "fills": "table header"}),
       ("label", "Legend text", text(), "My data", {"as_": TEXT, "tag": "data"}),
       ("units", "Units (axis sharing)", text("e.g. m/s"), "",
        {"as_": TEXT, "fills": "table units", "tag": "data"}),
       ("t0_min", "Time zero (min)", number(step=1.0), 0.0,
        {"tag": "data", "help": "Your times are counted from here, as a run's are from its "
                                "time zero (your data has no run)"})),
    *E(("profile:table",), ("profile",), TABLE_DATA,
       ("table", "Your data: height (km), value", Control("table", "height"), KEEP,
        {"tag": "height", "fills": "table header"}),
       ("label", "Legend text", text(), "My data", {"as_": TEXT, "tag": "profile data"}),
       ("units", "Units", text("e.g. m/s"), "", {"as_": TEXT, "tag": "profile data"}),
       ("color", "Colour", COLOUR, "k", {"tag": "profile data"}),
       ("ls", "Line style", choice(C.LINE_STYLES), "-", {"tag": "profile data"}),
       ("lw", "Line width", number(step=0.25), 1.5, {"tag": "profile data"}),
       ("marker", "Markers", choice(C.MARKERS), "", {"tag": "profile data"}),
       ("xlabel", "Value axis label (blank: the computed profiles')", text(), "")),
]

_SND_LOOKS = [(f"{k}_{x}", k, x, name, col, ls) for k, name, col, ls in C.SND_LINES
              for x in ("color", "ls", "lw")]


def _own_looks():
    names = tuple(n for n, *_ in _SND_LOOKS)
    fresh = {f"{k}_color": col for k, _, col, _ in C.SND_LINES} | \
        {f"{k}_ls": ls for k, _, _, ls in C.SND_LINES}
    return As(lambda lay: any((lay or {}).get(n) for n in names),
              lambda v: dict(fresh) if v else {n: _gone() for n in names}), names


_OWN_AS, _OWN_NAMES = _own_looks()
SOUNDING_ROWS = [
    *E(("sounding", "table"), ("sounding", "table"), "Where",
       ("where.kind", "Where", choice(C.SND_WHERE), "trk", {"when": "!what or what=sounding"}),
       ("where.x", "x (km)", number(step=1.0), 0.0,
        {"when": "where.kind!=mean and !what or where.kind!=mean and what=sounding"}),
       ("where.y", "y (km)", number(step=1.0), 0.0,
        {"when": "where.kind!=mean and !what or where.kind!=mean and what=sounding"}),
       ("where.avg", "Box width (km, 0: column)", number(0.0, step=0.5), 0.0,
        {"when": "where.kind!=mean and !what or where.kind!=mean and what=sounding"})),
    *E(("sounding",), ("sounding",), "Lines",
       ("own_looks", "Own line looks", TOGGLE, KEEP,
        {"packed": True, "names": _OWN_NAMES, "as_": _OWN_AS,
         "help": "The temperature, dewpoint and parcel lines' own colour, style and width (a "
                 "blank width: automatic); the colour above stays on the barbs and hodograph "
                 "marks"}),
       *[(key, f"{name} {'colour' if x == 'color' else 'line style' if x == 'ls' else 'width'}",
          COLOUR if x == "color" else choice(C.LINE_STYLES) if x == "ls" else auto(step=0.25),
          col if x == "color" else ls if x == "ls" else None,
          {"when": "own_looks", **({"as_": BLANKABLE} if x == "lw" else {})})
         for key, _, x, name, col, ls in _SND_LOOKS]),
]

DIST_RECIPE = [
    *E(("dist", "table"), ("dist", "table"), "Field",
       ("recipe.field", "Field", FIELD, KEEP, {"fills": "recipe", "tag": "dist",
                                                "when": "!what or what=field"})),
    *E(("joint",), ("joint",), "Field",
       ("recipe.field", "x field", FIELD, KEEP, {"fills": "recipe", "tag": "joint"}),
       ("recipe.yfield", "y field", FIELD, KEEP, {"fills": "recipe"})),
    *E(("dist", "joint", "table"), ("dist", "joint", "table"), "Field",
       ("recipe.vmode", "Vertical", choice(C.DIST_VMODES), "height",
        {"fills": "recipe", "when": "@3d and !what or @3d and what=field", "tag": "dist"}),
       ("recipe.z0", "Read from (km)", number(step=0.5), 0.0,
        {"fills": "recipe", "tag": "dist",
         "when": "@3d and recipe.vmode=layer and !what or @3d and recipe.vmode=layer and "
                 "what=field"}),
       ("recipe.z1", "Read to (km)", number(step=0.5), 10.0,
        {"fills": "recipe", "tag": "dist",
         "when": "@3d and recipe.vmode=layer and !what or @3d and recipe.vmode=layer and "
                 "what=field"})),
    *E(("dist", "table"), ("dist", "table"), "Field",
       ("recipe.z", "Height (km)", number(step=0.25), 1.0,
        {"fills": "recipe", "tag": "dist",
         "when": "@3d and recipe.vmode=height and !what or @3d and recipe.vmode=height and "
                 "what=field"})),
    *E(("joint",), ("joint",), "Field",
       ("recipe.z", "Height (km)", number(step=0.25), 1.0,
        {"fills": "recipe", "tag": "joint", "when": "!@3d or recipe.vmode=height"})),
    *_region(("table",), ("table",), tag="table", when="what=field"),
    *E(("dist", "table"), ("dist", "table"), "Field",
       ("recipe.lo", "Only values from", auto(), None,
        {"fills": "recipe", "as_": BLANKABLE, "tag": "dist", "when": "!what or what=field",
         "help": "Keep values at or above this (blank: no limit), e.g. 1 m/s for updrafts"}),
       ("recipe.hi", "to", auto(), None,
        {"fills": "recipe", "as_": BLANKABLE, "tag": "dist", "when": "!what or what=field"})),
    *E(("joint",), ("joint",), "Field",
       ("recipe.lo", "Only x from", auto(), None,
        {"fills": "recipe", "as_": BLANKABLE, "tag": "joint",
         "help": "Keep pairs whose x is at or above this (blank: no limit)"}),
       ("recipe.hi", "to", auto(), None, {"fills": "recipe", "as_": BLANKABLE, "tag": "joint"}),
       ("recipe.ylo", "Only y from", auto(), None,
        {"fills": "recipe", "as_": BLANKABLE,
         "help": "Keep pairs whose y is at or above this (blank: no limit)"}),
       ("recipe.yhi", "to", auto(), None, {"fills": "recipe", "as_": BLANKABLE})),
]

PROFILE_ROWS = [
    *E(("profile",), ("profile",), "Run and time",
       ("runs", "Run", RUNS, None, {"tag": "profile", "fills": "runs"})),
    *E(("profile",), ("profile",), "Field",
       ("recipe.field", "Field", FIELD_D, KEEP, {"fills": "recipe", "tag": "profile"}),
       ("recipe.z0", "Read from (km)", number(step=0.5), 0.0, {"fills": "recipe",
                                                               "tag": "profile"}),
       ("recipe.z1", "Read to (km)", number(step=0.5), 10.0, {"fills": "recipe",
                                                              "tag": "profile"}),
       ("op", "Then apply", choice(C.PROF_OPS), "",
        {"tag": "profile", "help": "d/dz of this profile, e.g. of the maximum w at each level "
                                   "(not the maximum of dw/dz at each level)"})),
    *E(("profile",), ("profile",), "Look",
       ("ls", "Line style", choice(C.PROF_STYLES), "", {"tag": "profile"}),
       ("lw", "Line width", number(step=0.25), 1.5, {"tag": "profile", "as_": real_or(1.5)})),
]

AZIM_ROWS = [
    *E(("azim",), ("azim",), "Field",
       ("recipe.field", "Field", FIELD, KEEP, {"fills": "recipe", "tag": "azim"}),
       ("recipe.op", "Reduce", choice(C.AZ_OPS), "mean", {"fills": "recipe"}),
       ("recipe.center", "Centre", choice(C.AZ_CENTERS), "track", {"fills": "recipe"}),
       ("recipe.offset", "Offset x, y (km)", XY, [0.0, 0.0],
        {"fills": "recipe", "when": "recipe.center!=point", "as_": PAIR, "tag": "azim"}),
       ("recipe.point", "x, y (km)", XY, [0.0, 0.0],
        {"fills": "recipe", "when": "recipe.center=point", "as_": PAIR}),
       ("recipe.ref", "Azimuth 0", choice(C.AZ_REFS), "motion", {"fills": "recipe"}),
       ("recipe.az0", "Azimuth from (°)", number(step=15.0), 0.0, {"fills": "recipe"}),
       ("recipe.az1", "to (°)", number(step=15.0), 360.0, {"fills": "recipe"}),
       ("recipe.rmax", "Radius (km)", number(step=1.0), 20.0, {"fills": "recipe"}),
       ("recipe.dr", "Bin width (km)", Control("number", blank=True, placeholder="grid"), None,
        {"fills": "recipe", "as_": BLANKABLE, "help": "Blank: the grid spacing"}),
       ("recipe.z0", "Read from (km)", number(step=0.5), 0.0, {"fills": "recipe",
                                                               "tag": "azim"}),
       ("recipe.z1", "Read to (km)", number(step=0.5), 15.0, {"fills": "recipe",
                                                              "tag": "azim"})),
    *E(("azim",), ("azim",), "Look",
       ("levels", "Contour levels (blank: auto)", text("e.g. 5, 10 or -6:6:2"), "",
        {"as_": TEXT, "tag": "azim",
         "help": "The panel's first is shaded; the others are contour lines"}),
       ("lw", "Line width", number(step=0.25), 1.0, {"tag": "azim", "as_": real_or(1.0)})),
]

TABLE_ROWS = [
    *E(("table",), ("table",), "Runs and times",
       ("runs", "Run", RUNS, None, {"tag": "table", "fills": "runs"}),
       ("times_s", "Times (min)", TIMES, [],
        {"help": "Minutes of the first run: 30, 60, 90; 30-120/15 (every 15 min); 30-120 "
                 "(every output). Each goes to the nearest output."})),
    *E(("table",), ("table",), "Values",
       ("what", "Values", choice(C.TBL_WHAT), "sounding"),
       ("params", "Parameters", multi({f"{h} ({u})" if u else h: p
                                       for p, h, u in drawbase.SND_PARAMS}), [],
        {"when": "what=sounding", "as_": As(list, list)}),
       ("stats", "Statistics", multi({v: k for k, v in spectables.TBL_STATS.items()}), [],
        {"when": "what=field", "as_": As(list, list)}),
       ("label", "Name in the headings (blank: automatic)", text(), "",
        {"as_": TEXT, "tag": "table"})),
]

ROWS = (LAYER_ROWS + FIELD_ROWS + FILL_ROWS + LOOK_ROWS + CONTOUR_ROWS + SHADE_ROWS
        + VECTOR_ROWS + TRACK_ROWS + SECTION_LINE_ROWS + SECTOR_ROWS + BOUNDARY_ROWS
        + PARCEL_ROWS + SERIES_ROWS + PARCEL_SERIES_ROWS + OWN_DATA_ROWS + SERIES_LINE_LOOK
        + ENS_BAND + VALUES + ONE_RUN + ENTRY_LABEL + AUTO_COLOUR + SOUNDING_ROWS
        + DIST_RECIPE + PROFILE_ROWS + AZIM_ROWS + TABLE_ROWS)
