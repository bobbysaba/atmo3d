"""The document's own rows of the schema (docs-dev/figures-ui-plan.md, Phase 2.1c): what is not a
look or a layer setting.  A row's key is its place in the document:

  suptitle, size, background, export.dpi, code.on, grid.rows   the figure's (level figure)
  runs[].label            a run's (Where.item: the run's id)
  annotations[].x         an annotation's (Where.item: its place in the list)
  panels[].title          a panel's (Where.pid)
  insets[].loc            a zoom inset's (Where.pid, Where.iid)
  sections[].half         a cross-section's line (Where.item: the section's id; a panel's own
                          section at panel level when it has none)

Most are written where they are; what has a docedit change of its own goes through it
(Row.writer: the grid's shape, a run's time zero, a panel's height, its place, its colorbar, a
section).  What a row shows under is a condition on its neighbours (an annotation's kind, a
section's orientation)."""

from dataclasses import replace

from .. import choices as C
from ..spec.sections import MOTION, ORIENTS, POSITIONS, SEC_DEFAULTS
from . import (
    BOX, CODE, COLOUR, KEEP, PANELS, TEXT, TOGGLE, WHEN, XY, As, Control, Row, _xy, _xy_text,
    auto, choice, integer, number, panels_text, parse_panels, text,
)

FIG = ("figure",)


def _gone():
    from ..shell.docedit import MISSING
    return MISSING


GONE_BLANK = As(lambda v: v or "", lambda v: (v or "").strip() or _gone())  # (blank: no key)
PAIR = As(_xy_text, lambda v: _xy(v) or [0.0, 0.0])
NUMS = As(lambda v: ", ".join(f"{float(x):g}" for x in v or []),
          lambda v: [float(x) for x in str(v or "").replace(",", " ").split()])


def D(prefix, section, *specs, kinds=None, levels=FIG, **common):
    """Rows of the document's `prefix` ("" for the top): each spec (name, label, control[,
    default][, {more}])."""
    from . import ALL
    out = []
    for spec in specs:
        name, label, control, *more = spec
        over = more.pop() if more and isinstance(more[-1], dict) else {}
        kw = dict(dict(section=section, kinds=kinds or ALL, levels=levels), **common)
        if more:
            kw["default"] = more[0]
        kw.update(over)
        out.append(Row(f"{prefix}.{name}" if prefix else name, label, control, **kw))
    return out


# ------------------------------------------------------------ the figure
def _fit_show(e):
    e = e or {}
    return "full" if not e.get("tight", True) else "width" if e.get("exact_width") else "trim"


FIT = As(_fit_show, lambda v: dict(tight=v != "full", exact_width=v == "width"))

FIGURE_ROWS = [
    *D("", "Figure",
       ("size", "Size (in)", Control("size"), [8.0, 6.0],
        {"also": (("figure", "size_auto", False),), "as_": As(list, lambda v: [float(x)
                                                                             for x in v][:2]),
         "help": "Width and height; a preset width (a journal column) or Fit height"}),
       ("suptitle", "Figure title", text(), "", {"as_": TEXT})),
    *D("export", "Export",
       ("format", "Format", choice({"PNG": "png", "PDF": "pdf", "SVG": "svg", "EPS": "eps",
                                    "TIFF": "tiff"}), "png",
        {"help": "PDF, SVG and EPS keep text and lines as vectors (fields are embedded as "
                 "images at the DPI)"}),
       ("dpi", "DPI", integer(50, 1200, 50), 250, {"as_": As(int, lambda v: int(v or 250))}),
       ("fit", "Image size", choice({"Trim white space": "trim",
                                     "Exact width, trim the height": "width",
                                     "Exact width and height": "full"}), KEEP,
        {"packed": True, "names": ("tight", "exact_width"), "as_": FIT,
         "help": "Trimming adds the margin around what is drawn, so the image can be a little "
                 "wider than the figure's width. Exact width is for a journal column; exact "
                 "width and height keeps all the white space."}),
       ("pad", "Margin when trimmed (in)", number(0.0, step=0.01), 0.05,
        {"when": "fit!=full", "as_": As(float, lambda v: float(v or 0.0))})),
    *D("", "Export",
       ("background", "Background", choice({"White": "white", "Black": "black",
                                            "Transparent": "none"}), "white")),
    *D("code", "Your own code",
       ("on", "Run the code", TOGGLE, False, {"as_": As(bool, bool)}),
       ("text", "Python, run after the figure is drawn", CODE, "",
        {"as_": As(lambda v: v or "", lambda v: v or "")})),
    *D("grid", "Grid",
       ("rows", "Rows", integer(1, 12), 1, {"writer": "grid"}),
       ("cols", "Columns", integer(1, 12), 1, {"writer": "grid"}),
       ("heights", "Row heights", text("equal, or 2, 1"), [],
        {"writer": "shares", "as_": NUMS, "help": "Each row's share of the height"}),
       ("widths", "Column widths", text("equal, or 2, 1"), [],
        {"writer": "shares", "as_": NUMS, "help": "Each column's share of the width"})),
]

RUN_ROWS = D(
    "runs[]", "Runs",
    ("label", "Label", text(), ""),
    ("color", "Colour", COLOUR, KEEP, {"help": "The run's colour: its lines, its track"}),
    ("t0_min", "Time zero (min)", number(step=1.0), 0.0,
     {"writer": "t0", "help": "The model time this run counts from: its time labels count "
                              "from it, and panels of the other runs move to stay at the same "
                              "time since their time zeros"}),
    ("track", "Track", Control("track"), KEEP,
     {"packed": True, "names": ("track", "storm"), "as_": As(lambda r: dict(
         track=r.get("track"), storm=r.get("storm")), dict),
      "help": "The storm's track: the viewer's, a track file and the storm in it, or none"}))


# ------------------------------------------------------------ a panel
MAPS = ("plan", "xsec")
PANEL = ("panel",)
WHEN["several sections"] = lambda doc, where, ctx=None: len(doc.get("sections") or {}) > 1


def _controls_bar(doc, where, ctx=None):
    """The panel has a colorbar, which it controls (the first of the panels sharing it)."""
    from ..shell import bars
    try:
        bar = bars.bar_of(doc, where.pid)
    except Exception:  # noqa: BLE001  (a figure that can't be drawn yet: no bar)
        return False
    return bar is not None and bar["members"][0] == where.pid


def _could_have_bar(doc, where, ctx=None):
    """The panel would have a colorbar were its own on (it has a fill, the figure colorbars)."""
    from ..shell import bars
    try:
        return bars.bar_of(doc, where.pid, as_if_shown=True) is not None
    except Exception:  # noqa: BLE001
        return False


def _has_bar(doc, where, ctx=None):
    from ..shell import bars
    try:
        return bars.bar_of(doc, where.pid) is not None
    except Exception:  # noqa: BLE001
        return False


WHEN.update({"controls its bar": _controls_bar, "could have a bar": _could_have_bar,
             "has a bar": _has_bar})
PANEL_ROWS = [
    *D("panels[]", "Panel",
       ("title", "Title", text(), "", {"as_": TEXT}),
       ("rowlabel", "Row label (left)", text("none"), "", {"as_": GONE_BLANK}),
       ("cell", "Place (row, column)", Control("cell"), KEEP,
        {"writer": "cell", "help": "Where it sits on the grid, and how many cells it spans"}),
       levels=PANEL),
    *D("panels[]", "Panel",
       ("run", "Run", Control("run"), KEEP,
        {"writer": "panel run", "help": "Another run keeps the panel's moment, at that run's "
                                        "nearest output"}),
       ("time_s", "Time", Control("time"), KEEP), kinds=("plan", "xsec", "scene"), levels=PANEL),
    *D("panels[]", "Panel",
       ("z", "Own height (blank: its layers')", auto(), None,
        {"writer": "height", "help": "The layers at a height draw at this one here, and the "
                                     "panel's height label says it"}),
       ("zmode", "Height in", choice({"km": "height", "Model level": "level"}), "height",
        {"writer": "height"}), kinds=("plan",), levels=PANEL),
    *D("panels[]", "Panel",
       ("section", "Its section line", choice("sections"), KEEP, {"when": "@several sections"}),
       kinds=MAPS, levels=PANEL),
    *D("panels[].colorbar", "Colorbar",
       ("show", "Its colours have a bar", TOGGLE, True,
        {"writer": "colorbar", "as_": As(lambda v: v is not False, bool),
         "when": "@could have a bar"}),
       ("group", "The bar it shares (a name)", text("as the figure's mode"), "",
        {"writer": "colorbar", "as_": TEXT, "when": "@has a bar",
         "help": "Panels naming the same bar share it; blank: as the figure's mode says"}),
       # (the bar's own: on the layer of each panel sharing it, written to them all)
       ("cbar_label", "Colorbar label (blank: the figure's, else units)",
        text("e.g. w (m s$^{-1}$)"), "",
        {"writer": "bar", "as_": TEXT, "when": "@controls its bar",
         "help": "$…$ is math, e.g. m s$^{-1}$"}),
       ("cbar_ticks", "Colorbar ticks (blank: the figure's, else auto)", text("0:60:10"), "",
        {"writer": "bar", "as_": TEXT, "when": "@controls its bar"}),
       ("extend", "Colorbar arrows", choice(C.EXTEND), "auto",
        {"writer": "bar", "when": "@controls its bar"}),
       kinds=("plan", "xsec", "th"), levels=PANEL),
]

INSET_ROWS = [
    *D("insets[]", "Where it sits",
       ("loc", "Where", choice(C.INSET_LOCS), "upper right"),
       ("size", "Width (of the panel)", number(0.05, 1.0, 0.05), 0.4),
       ("x", "x (left edge)", number(step=0.01), 0.03, {"when": "loc=custom"}),
       ("y", "y (bottom edge)", number(step=0.01), 0.03, {"when": "loc=custom"}),
       ("h", "Height (blank: as it shows)", auto(step=0.05), None,
        {"as_": As(lambda v: v, lambda v: _gone() if v in (None, "") else float(v))}),
       kinds=MAPS, levels=("inset",)),
    *D("insets[]", "Area",
       ("view", "From, to, height from, height to (km)", BOX, None),
       kinds=("xsec",), levels=("inset",)),
    *D("insets[]", "Box and lines",
       ("mark", "Box in the panel", TOGGLE, True),
       ("connect", "Lines to the inset", TOGGLE, True),
       ("ticks", "Tick labels", TOGGLE, False),
       ("color", "Colour", COLOUR, "#000000"),
       ("lw", "Line width", number(0.25, step=0.25), 1.0),
       ("ls", "Line style", choice(C.LINE_STYLES), "-"),
       kinds=MAPS, levels=("inset",)),
]


# ------------------------------------------------------------ a cross-section's line
def _sec(*specs):
    return D("sections[]", "Section line", *specs, kinds=MAPS, levels=("kind", "panel"),
             writer="section")


_MOT = "|".join(MOTION)
_FIXED_X, _FIXED_Y = "orient=x and pos=fixed", "orient=y and pos=fixed"
SECTION_ROWS = _sec(
    ("label", "Label (blank: automatic)", text(), "", {"as_": TEXT}),
    ("orient", "Orientation", choice(ORIENTS), SEC_DEFAULTS["orient"]),
    ("pos", "Position", choice(POSITIONS), SEC_DEFAULTS["pos"],
     {"when": f"orient!=ab|{_MOT}"}),
    ("half", "Half-length (km)", number(0.5, step=1), SEC_DEFAULTS["half"],
     {"when": f"orient=angle|{_MOT} or orient=x|y and pos!=fixed"}),
    ("off", "Offset across (km)", number(step=0.5), SEC_DEFAULTS["off"],
     {"when": "orient=x|y and pos!=fixed"}),
    ("y", "At y (km; blank: centre)", auto(step=0.5), None, {"when": _FIXED_X}),
    ("x0", "From x (km; blank: edge)", auto(step=0.5), None, {"when": _FIXED_X}),
    ("x1", "To x (km; blank: edge)", auto(step=0.5), None, {"when": _FIXED_X}),
    ("x", "At x (km; blank: centre)", auto(step=0.5), None, {"when": _FIXED_Y}),
    ("y0", "From y (km; blank: edge)", auto(step=0.5), None, {"when": _FIXED_Y}),
    ("y1", "To y (km; blank: edge)", auto(step=0.5), None, {"when": _FIXED_Y}),
    ("angle", "Direction (° clockwise from north)", number(step=15), SEC_DEFAULTS["angle"],
     {"when": "orient=angle"}),
    ("offset", "Offset x, y (km)", XY, [0.0, 0.0],
     {"when": "orient=angle and pos!=fixed", "as_": PAIR}),
    ("cx", "Centre x (km; blank: centre)", auto(step=0.5), None,
     {"when": "orient=angle and pos=fixed"}),
    ("cy", "Centre y (km; blank: centre)", auto(step=0.5), None,
     {"when": "orient=angle and pos=fixed"}),
    ("ahead", "Centre ahead of the storm (km)", number(step=0.5), 0.0,
     {"when": f"orient={_MOT}"}),
    ("right", "Centre right of the storm (km)", number(step=0.5), 0.0,
     {"when": f"orient={_MOT}"}),
    ("mwin", "Motion averaged over (min; 0: at the time)", number(0.0, step=1), 0.0,
     {"when": f"orient={_MOT}"}),
    ("avg", "Average across (km)", number(0.0, step=0.5), 0.0,
     {"as_": As(lambda v: float(v or 0.0), lambda v: float(v or 0.0))}))


# ------------------------------------------------------------ annotations
def _uses(key):
    """An annotation row's condition: the kinds that use it (a legend entry: by its look)."""
    kinds = [k for k, fs in C.ANN_FIELDS.items() if key in fs and k != "legend"]
    alts = [f"kind={'|'.join(kinds)}"] if kinds else []
    if key in C.ANN_FIELDS["legend"]:
        look = {"marker": "look=marker|both", "ls": "look!=marker",
                "alpha": "look=patch"}.get(key)
        alts.append("kind=legend" + (f" and {look}" if look else ""))
    return " or ".join(alts)


PANELS_AS = As(panels_text, parse_panels)
ANNOTATION_ROWS = D(
    "annotations[]", "Annotations",
    ("kind", "Kind", choice(C.ANN_KINDS), "text"),
    ("panel", "Panels (blank: all)", PANELS, -1, {"as_": PANELS_AS}),
    ("coords", "Position in", choice({"Axis units (km, min)": "data",
                                      "Panel fraction (0–1)": "axes"}), "data"),
    *[(k, lab, number(step=0.5), d, {"as_": As(float, lambda v: float(v or 0.0))})
      for k, lab, d in (("x", "x", 0.0), ("y", "y", 0.0), ("x2", "x to", 0.0),
                        ("y2", "y to", 0.0), ("r", "Radius", 1.0))],
    ("text", "Text", text(), ""),
    ("size", "Size", number(step=1), 10.0, {"as_": As(float, lambda v: float(v or 10.0))}),
    ("lw", "Line width", number(step=0.25), 1.5),
    ("ls", "Line style", choice(C.LINE_STYLES), "-"),
    ("marker", "Marker", choice({"×": "x", "+": "+", "●": ".", "○": "o", "□": "s", "★": "*",
                                 "▲": "^"}), "x"),
    ("look", "Looks like", choice({"Line": "line", "Marker": "marker",
                                   "Line and marker": "both", "Filled box": "patch"}), "line"),
    ("alpha", "Opacity", number(step=0.1), 1.0),
    ("bold", "Bold", TOGGLE, False),
    ("color", "Colour", COLOUR, "#000000"),
    levels=("figure", "panel"))
ANNOTATION_ROWS = [replace(r, when=_uses(r.key.rpartition(".")[2]))
                   if r.key.rpartition(".")[2] not in ("kind", "panel", "color") else r
                   for r in ANNOTATION_ROWS]

ROWS = FIGURE_ROWS + RUN_ROWS + PANEL_ROWS + INSET_ROWS + SECTION_ROWS + ANNOTATION_ROWS
