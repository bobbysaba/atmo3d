"""The viewer's layers on the schema (docs-dev/figures-ui-plan.md, Phase 5): the map's and the
cross-section tool's fill, more fills, contours and vectors, as rows at the level "viewer".

A viewer layer is a dict in a figure layer's form (type, field, mode, z, cmap, reverse, vmin,
...) and a role: "fill" (the tool's first fill), "more" (a fill over it), "contour", "vectors".
Its rows are the figure's rows (schema/layer.py) where the two mean the same, as copies with what
the viewer offers in place of the figure's (its labels, choices, conditions, fills), and rows of
the viewer's own (VIEWER_ONLY) where they do not.  The figure's table (schema.ROWS) has none of
them: the figure never offers the level "viewer".

  rows(role, kind)   a viewer layer's rows, in its drawer's order
  at(kind)           the Where a viewer layer's rows are read and written at (where.py: the
                     document is the layer itself)
  new(role, kind)    a viewer layer with every row's value (its defaults)
  saved(lay)         a viewer layer as a session (FORMAT 3: viewer/session.py) keeps it
  from_session(role, d, kind)
                     a FORMAT 2 session's layer (its widgets' keys) as a viewer layer
  upgraded(role, d, kind)
                     a FORMAT 2 session's layer as FORMAT 3 keeps one: what d has, nothing
                     more (a layer put back keeps the rest as it is; a difference off is
                     "minus": None)"""

import dataclasses

from ...core import vectors
from ...core.fields import CMAPS, deriv_name
from . import (
    COLOUR, CONTOUR_LEVELS, FIELD, KEEP, TOGGLE, Control, Row, choice, integer, number,
    row_for,
)
from .layer import block
from .where import Where

VIEWER = "viewer"
KINDS = ("plan", "xsec")
ROLES = ("fill", "more", "contour", "vectors")
TYPE = {"fill": "fill", "more": "fill", "contour": "contour", "vectors": "vectors"}
DIFF_CMAP = "RdBu_r"  # (a difference's colours: viewer/diff.py)


def at(kind="plan"):
    return Where(VIEWER, kind)


# ------------------------------------------------------------ controls the viewer's host makes
LEVEL = Control("vlevel")  # (a level of the layer's mode: a height, a model level, a sweep)
HEIGHT = Control("vheight")  # (a height in km AGL, up to the run's top)
MINUS_RUN = Control("run", options="viewer", blank=True, placeholder="this run")
MINUS_TIME = Control("time", options="minus", blank=True, placeholder="the shown time")
REF = Control("vref")  # (a number, its label in the layer's vector's units)


def _own(key, label, control, default, types, when="", **kw):
    return Row(f"layer.{key}", label, control, "", kinds=KINDS, levels=(VIEWER,),
               default=default, types=types, when=when, **kw)


VIEWER_ONLY = {
    "auto": _own("auto", "Auto range", TOGGLE, True, ("fill",), fills="viewer auto"),
    "clip": _own("clip", "Clear outside range", TOGGLE, True, ("fill",),
                 help="Values below Min or above Max left uncoloured: the fill below shows"),
    "across": _own("across", "Arrows across", integer(8, 50), 24, ("vectors",),
                   when="style!=streamlines"),
    "stream_n": _own("stream_n", "Streamline density", integer(8, 50), 24, ("vectors",),
                     when="style=streamlines"),
    "ref": _own("ref", "Ref. arrow (the vector's units)", REF, 10.0, ("vectors",),
                when="style!=streamlines",
                help="The length of the reference arrow, in the vector's units"),
}

_LEVELLED = "mode!=colmax|colmin and @3d"


def _copy(key, type_, **over):
    """The figure's row of layer key for type_, as the viewer offers it."""
    r = row_for(f"layer.{key}", type_)
    assert r is not None and type_ in r.types, (key, type_)
    over.setdefault("when", "")
    return dataclasses.replace(r, kinds=KINDS, levels=(VIEWER,), section="", **over)


def _row(key, type_, **over):
    if key in VIEWER_ONLY:
        r = VIEWER_ONLY[key]
        return dataclasses.replace(r, **over) if over else r
    return _copy(key, type_, **over)


# (role, kind) -> [(key, overrides)], in the drawer's order
_ON = ("on", {"label": "Drawn"})
_FIELD_MAIN = ("field", {"fills": "viewer field"})  # (FIELD_D: with its derivative)
_FIELD = ("field", {"control": FIELD, "fills": "viewer field"})
_MODE = ("mode", {"when": "@3d", "fills": "viewer mode"})
_Z = ("z", {"label": "Level", "control": LEVEL, "when": _LEVELLED})
_STYLE = ("style", {"control": choice({"Pixels": "mesh", "Filled contours": "contourf"})})
_COLOURS = [("cmap", {"control": choice(CMAPS)}), ("reverse", {}),  # (the ones Bokeh draws)
            ("auto", {}),
            ("vmin", {"when": "!auto"}), ("vmax", {"when": "!auto"})]
_NLEV = ("nlevels", {"label": "Contour intervals", "control": integer(4, 30), "default": 15,
                     "when": "style=contourf"})
_ALPHA = ("alpha", {"label": "Opacity", "control": number(0.1, 1.0, 0.05)})
_MINUS = [("minus", {"label": "Difference: minus another time or run", "fills": "viewer minus",
                     "as_": block(dict(run=None, time_s=None))}),  # (no "grid": it interpolates)
          ("minus.run", {"control": MINUS_RUN, "when": "minus"}),
          ("minus.time_s", {"control": MINUS_TIME, "when": "minus"})]
_CONTOUR = [("levels", {"label": "Levels", "control": CONTOUR_LEVELS, "default": "auto"}),
            ("color", {"label": "Color", "control": COLOUR, "default": "#ffffff"}),
            ("lw", {"label": "Line width", "control": number(0.5, 4.0, 0.25), "default": 1.4}),
            ("neg_dashed", {})]
_VEC = [("vector", {"fills": "viewer vector"}), ("frame", {"when": "@framed"})]
_VEC_LOOK = [("across", {}), ("ref", {}), ("color", {"label": "Color", "default": "#e5e7eb"})]

LAYOUT = {
    ("fill", "plan"): [_ON, _FIELD_MAIN, _MODE, _Z, _STYLE, *_COLOURS, _NLEV,
                       (_ALPHA[0], dict(_ALPHA[1], default=1.0)), *_MINUS],
    ("more", "plan"): [_ON, _FIELD, _MODE, _Z, _STYLE, *_COLOURS,
                       (_ALPHA[0], dict(_ALPHA[1], default=0.7)), ("clip", {})],
    ("contour", "plan"): [_ON, (_FIELD[0], {"control": FIELD, "fills": ""}), _MODE, _Z,
                          *_CONTOUR],
    ("vectors", "plan"): [_ON, _VEC[0],
                          ("z", {"label": "Height (km AGL)", "control": HEIGHT, "default": 0.5}),
                          _VEC[1],
                          ("style", {"control": choice({"Arrows": "arrows",
                                                        "Streamlines": "streamlines"})}),
                          _VEC_LOOK[0], ("stream_n", {}), *_VEC_LOOK[1:]],
    ("fill", "xsec"): [_FIELD, _STYLE, *_COLOURS, _NLEV, *_MINUS],
    ("more", "xsec"): [_ON, _FIELD, _STYLE, *_COLOURS,
                       (_ALPHA[0], dict(_ALPHA[1], default=0.7)), ("clip", {})],
    ("contour", "xsec"): [_ON, (_FIELD[0], {"control": FIELD, "fills": ""}), *_CONTOUR],
    ("vectors", "xsec"): [_ON, _VEC[0], _VEC[1],
                          ("across", {"control": integer(8, 60), "default": 28}),
                          *_VEC_LOOK[1:]],
}
# (the cross-section's own fields: no field without heights, LayerHost.field_groups; its first
# fill has no on box)

_ROWS = {k: [_row(key, TYPE[k[0]], **over) for key, over in spec] for k, spec in LAYOUT.items()}


def rows(role, kind="plan"):
    """A viewer layer's rows, in its drawer's order."""
    return list(_ROWS[(role, kind)])


def _top(r):
    return r.key.split(".")[1]


def new(role, kind="plan", **values):
    """A viewer layer: its type and role, each row's default (its field: none; a block's rows:
    none until it is turned on; a vector's reference arrow: its typical magnitude), then
    values."""
    lay = dict(type=TYPE[role], role=role)
    for r in rows(role, kind):
        if "." in r.key[len("layer."):] or r.key == "layer.minus":
            continue
        lay[_top(r)] = None if r.default is KEEP else r.default
    lay.update(values)
    if role == "vectors" and "ref" not in values and lay.get("vector") in vectors.VECTORS:
        lay["ref"] = vectors.VECTORS[lay["vector"]].ref
    return lay


# ------------------------------------------------------------ sessions
def saved(lay):
    """A viewer layer as a session keeps it (FORMAT 3): its keys but its type and role (the
    session's place says them)."""
    import copy
    return {k: copy.deepcopy(v) for k, v in lay.items() if k not in ("type", "role")}


def upgraded(role, d, kind="plan"):
    """A FORMAT 2 session's layer d as FORMAT 3 keeps one (session.upgrade): what d has, in
    the layer's keys."""
    lay = from_session(role, d, kind, base={})
    diff = d.get("diff")
    if role == "fill" and diff and not diff.get("on"):
        lay["minus"] = None
    return lay


# ------------------------------------------------------------ FORMAT 2
# session key -> layer key, where only the name differs
_NAMES = {"var": "field", "level": "z", "rev": "reverse", "nlev": "nlevels", "width": "lw",
          "negdash": "neg_dashed", "q": "vector"}
_STYLES = {"image": "mesh", "contourf": "contourf", "arrows": "arrows",
           "streamlines": "streamlines"}


def from_session(role, d, kind="plan", base=None):
    """A session's layer (its widgets' values: FILL_KEYS, OV_KEYS, VEC_KEYS; a tool's first
    fill: its keys and "diff") as a viewer layer: over `base` (a layer; None: a new one),
    what d has."""
    import copy
    lay = new(role, kind) if base is None else copy.deepcopy(base)
    keys = {_top(r) for r in rows(role, kind)}
    for k, v in d.items():
        if k in ("op", "diff", "density"):
            continue
        name = _NAMES.get(k, k)
        if name == "style":
            v = _STYLES.get(v, v)
        if name in keys:
            lay[name] = v
    if "var" in d:
        lay["field"] = deriv_name(d.get("op") or "", d["var"])
    if "density" in d:
        streams = lay.get("style") == "streamlines"
        lay["stream_n" if streams else "across"] = d["density"]
    diff = d.get("diff")
    if diff and not diff.get("on"):
        lay.pop("minus", None)
    if diff and diff.get("on"):
        t = diff.get("time", "")
        lay["minus"] = dict(run=diff.get("run") or None,
                            time_s=None if t in ("", None) else t)
    return lay


ALL_ROWS = tuple(r for rs in _ROWS.values() for r in rs)  # (a row of several layers: each time)
