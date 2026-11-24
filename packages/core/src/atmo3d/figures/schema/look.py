"""The look settings: style, then a kind's, then a panel's, then an inset's (schema/__init__.py).

A row's default is what a figure that lacks the setting shows (as the old settings table had
it); KEEP: the blocks every figure has whole (a new figure's, spec.fresh_look), which the drawer
falls back to."""

from dataclasses import replace

from .. import draw as figdraw
from ..choices import (CB_LOCS, CB_MODES, DIST_BAR_LABELS, DIST_CUM, DIST_HSTYLES, DIST_NORMS,
                       DIST_PLOTS, DIST_STATS_AT, DIST_WHIS, FIG_CMAPS, FONTS, JOINT_PLOTS,
                       LABEL_LOCS, LETTERS, LOCS, MARK_EXTREMES, MATH_FONTS, SCENE_ARROWS,
                       SCENE_BARS, SCENE_BG, SCENE_FLOOR_CMAPS, SCENE_FLOOR_RANGE,
                       SCENE_LIGHTS, SCENE_PROJ, SCENE_RES, SCENE_STREAM_BY, SCENE_STREAM_DIR,
                       SCENE_VIEWS, SND_LAYOUTS, STORM_MOTIONS, TBL_COMPARE, TBL_DECIMALS,
                       TBL_LAYOUTS, TICKDIR, PAR_MOVING, SCENE_PAR_TAILS)
from ..kinds import KINDS
from . import (ALL, BLANKABLE, WHEN, BOX, CMAP, COLOUR, FIELD, FLAG, KEEP, PANEL, PANELS, PSET,
               PVAR, RAW, SIZE,
               STRIPPED, TEXT, TOGGLE, XY, As, _panels_loose, _panels_text, _same, _xy,
               _xy_text, auto, choice, integer, layer_of,
               look_rows, minutes, multi, number, one_of, opt_or, real, real_or, text)


def _reach(what):
    """The kinds whose picture a look setting reaches (kinds.py)."""
    return tuple(k for k, v in KINDS.items() if what in v.style)


AXES, Y_STEP, CBAR = _reach("axes"), _reach("y_step"), _reach("colorbar")
TIME_LABEL, RUN_LABEL, KEY = _reach("time_label"), _reach("run_label"), _reach("contour_key")
HEIGHTS = ("plan", "xsec")  # (panels at a height)
FIG, KP, FP, KPI = ("figure",), ("kind", "panel"), ("figure", "panel"), ("kind", "panel", "inset")
PANEL_LEGEND_LOCS = ["best"] + LOCS


# ------------------------------------------------------------ conversions of a few
def _cb_place(c):
    """A colorbar's place; older figures only have its orientation."""
    c = c or {}
    return c.get("location") or (
        "bottom" if c.get("orientation", "horizontal" if c.get("mode", "shared") == "shared"
                          else "vertical") == "horizontal" else "right")


def _cb_store(loc):
    return dict(location=loc, orientation="horizontal" if loc in ("bottom", "top") else "vertical")


CB_PLACE = As(_cb_place, _cb_store)
LEGEND_PANEL = As(lambda v: int(v or 0) + 1, lambda v: max(0, int(v or 1) - 1))
OWN = As(lambda v: v is not False, _same)


# ------------------------------------------------------------ figure-wide
TEXT_ROWS = look_rows(
    "font", "Text", ALL, FIG,
    ("family", "Font", choice(FONTS), "sans-serif", dict(as_=one_of(FONTS, "sans-serif"))),
    ("math", "Math & units font", choice(MATH_FONTS), "dejavusans",
     dict(as_=one_of(MATH_FONTS.values(), "dejavusans"),
          help="Font of $...$ text, e.g. m s$^{-1}$")),
    ("size", "Base size (pt)", number(start=4, step=0.5), 10.0, dict(as_=real(10.0))),
    ("tick", "Tick labels (pt)", auto(), None, dict(as_=SIZE)),
    ("label", "Axis labels (pt)", auto(), None, dict(as_=SIZE)),
    ("title", "Panel titles (pt)", auto(), None, dict(as_=SIZE)),
    ("suptitle", "Figure title (pt)", auto(), None, dict(as_=SIZE)),
    ("legend", "Legends (pt)", auto(), None, dict(as_=SIZE)))


def _label_rows(prefix, word, kinds, with_text="", text_help="", default_loc="upper left",
                on_default=True, on_as=RAW):
    """A panel label's rows (letters, time, run name, height): on, its text, where, size, bold,
    box."""
    rows = [("on", word, TOGGLE, on_default, dict(as_=on_as))]
    if with_text:
        rows.append(("fmt", with_text, text(), "", dict(help=text_help)))
    rows += [("loc", "Where", choice(LABEL_LOCS), default_loc),
             ("size", "Size (pt)", auto(step=1), None, dict(as_=BLANKABLE)),
             ("bold", "Bold", TOGGLE, True),
             ("box", "White box", TOGGLE, False, dict(as_=FLAG))]
    return look_rows(prefix, "Panel labels", kinds, FP, *rows)


LABEL_ROWS = (
    look_rows("axes", "Panel labels", ALL, FP,
              ("title_loc", "Where", choice({"Center": "center", "Left": "left", "Right": "right"}),
               "center", dict(help="The panel titles'")),
              ("title_bold", "Bold", TOGGLE, True, dict(help="The panel titles'")))
    + look_rows("", "Panel labels", ALL, FIG,
                ("label_fit", "Shrink these labels to fit narrow panels", TOGGLE, False,
                 dict(as_=FLAG)))
    # (letters set by hand at the figure: no longer the count's, letters.auto)
    + [replace(r, also=(("figure", "look.letters.auto", False),)) if r.key == "look.letters.on"
       else r for r in _label_rows("letters", "Panel letters", ALL)]
    + look_rows("letters", "Panel labels", ALL, FIG,
                ("fmt", "Style", choice(LETTERS), "{a}",
                 dict(as_=one_of(LETTERS.values(), "{a}"))))
    + _label_rows("time_label", "Time label", TIME_LABEL, "Text",
                  "{min}: minutes (from time zero), {model}: model minutes, {s}: seconds, "
                  "{hms}: h:mm:ss; e.g. t = {min:g} min", "lower right")
    + look_rows("time_label", "Panel labels", ALL, FIG,
                ("t0_min", "Minutes counted from", number(step=10), 0.0,
                 dict(as_=real(), when="older t0",
                      help="From an older figure: adds to each run's time zero (on the Runs "
                           "node), which is the place to set it. At 0 this box goes away")))
    + look_rows("run_label", "Panel labels", RUN_LABEL, FP,
                ("on", "Run name", TOGGLE, True),
                ("run_color", "In the run's colour", TOGGLE, False, dict(as_=FLAG)),
                ("loc", "Where", choice(LABEL_LOCS), "upper left"),
                ("size", "Size (pt)", auto(step=1), None, dict(as_=BLANKABLE)),
                ("bold", "Bold", TOGGLE, True),
                ("box", "White box", TOGGLE, False, dict(as_=FLAG)))
    + _label_rows("z_label", "Height label", HEIGHTS, "Text (blank: z = … km / k = …)",
                  "{z}: the height (km), {k}: the model level; e.g. {z:g} km AGL",
                  "upper right", on_default=False, on_as=FLAG))
# (the text of time and height labels: blank is "t = {min:g} min" / automatic)
FMT_AS = {"look.time_label.fmt": As(_same, lambda v: v or "t = {min:g} min"),
          "look.z_label.fmt": STRIPPED}
LABEL_ROWS = [replace(r, as_=FMT_AS.get(r.key, r.as_)) for r in LABEL_ROWS]

COLORBAR_ROWS = look_rows(
    "colorbar", "Colorbar", CBAR, FIG,
    ("mode", "Colorbars", choice(CB_MODES), "shared"),
    ("location", "Where", choice(CB_LOCS), KEEP,
     dict(as_=CB_PLACE, packed=True, names=("location", "orientation"))),
    ("label", "Label of bars with none of their own (blank: units)", text("e.g. w (m s$^{-1}$)"),
     "", dict(help="A panel's own Colorbar label comes first, so clear it for this one to show; "
                   "$…$ is math, e.g. m s$^{-1}$")),
    ("ticks", "Ticks of bars with none of their own (blank: auto)", text("0:60:10"), "",
     dict(help="A panel's own Colorbar ticks come first")),
    ("tick_fmt", "Tick format (blank: auto)", text("%g"), "",
     dict(as_=STRIPPED, help="e.g. %.1f, %d, %.0e")),
    ("shrink", "Length (0–1)", number(0.1, 1.0, 0.05), 0.7, dict(as_=real(0.7))),
    ("fraction", "Thickness (0–1)", number(0.01, 0.5, 0.01), 0.05, dict(as_=real(0.05))),
    ("pad", "Gap (0–1)", number(0.0, 0.5, 0.01), 0.02, dict(as_=real())),
    ("label_size", "Label size (pt)", auto(), None, dict(as_=SIZE)),
    ("tick_size", "Tick size (pt)", auto(), None, dict(as_=SIZE)),
    ("label_bold", "Bold label", TOGGLE, False, dict(as_=FLAG)),
    ("label_side", "Label side",
     choice({"Auto": "", "Above / left": "first", "Below / right": "second"}), ""))
# (a kind's own bars, in a figure of several kinds: all but how many there are)
COLORBAR_ROWS = [r if r.key == "look.colorbar.mode" else replace(r, levels=("figure", "kind"))
                 for r in COLORBAR_ROWS]

def _legend_reaches(doc, where, ctx=None):
    """Whether a figure's legend has anything to list: not with only box plots, nor only
    time-height panels without legend annotations."""
    kinds = {p["kind"] for p in doc.get("panels") or []}
    if kinds == {"th"}:
        return any(a.get("kind") == "legend" for a in doc.get("annotations") or [])
    if kinds == {"dist"}:
        plot = (((doc.get("kinds") or {}).get("dist") or {}).get("dist") or {}).get("plot")
        return plot not in ("box", "violin")
    return True


WHEN["legend reaches"] = _legend_reaches
LEGEND_ROWS = look_rows(
    "legend", "Legend", ALL, FIG,
    ("where", "Legends on", choice({"Each panel": "panel", "The figure": "figure"}), "panel"),
    ("panel", "In panel", PANEL, 0, dict(as_=LEGEND_PANEL)),
    ("panels", "From panels (blank: all)", PANELS, None,
     dict(as_=As(_panels_text, _panels_loose),
          help="The panels whose entries it lists (letters or numbers)")),
    ("loc", "At", choice(LOCS), "upper right"),
    ("anchor", "Anchor x, y (blank: none)", XY, None,
     dict(as_=As(_xy_text, _xy),
          help="Puts the legend's 'At' corner at this point: fractions of the panel (on the "
               "figure: of the figure); below 0 or above 1 is outside it")),
    ("title", "Title", text(), "", dict(as_=TEXT)),
    ("ncol", "Columns", integer(1, 8), 1,
     dict(as_=As(lambda v: int(v or 1), lambda v: int(v or 1)))),
    ("frame", "Frame", TOGGLE, True),
    ("own", "Panels' own legends", TOGGLE, True, dict(as_=OWN)), when="legend reaches")

CONTOUR_KEY_ROWS = look_rows(
    "contour_key", "Contour key", KEY, FIG,
    ("on", "Contour key (nested circles)", TOGGLE, False),
    ("layer", "Of the layer", layer_of(("contour",)), -1),
    ("label", "Name in the middle", text(), "w"),
    ("x", "x (figure 0–1)", number(step=0.01), 0.01, dict(as_=real())),
    ("y", "y (figure 0–1)", number(step=0.01), 0.01, dict(as_=real())),
    ("size", "Size (0–1)", number(step=0.01), 0.1, dict(as_=real(0.1))),
    ("fs", "Font (pt)", number(step=1), 10.0, dict(as_=real(10.0))),
    ("frame", "Frame", TOGGLE, True))

EXTREMES_ROWS = look_rows(
    "extremes", "Maximum and minimum", ("plan", "xsec", "th"), FIG,
    ("on", "Maximum / minimum", TOGGLE, False, dict(as_=FLAG)),
    ("layer", "Of the layer", layer_of(("fill", "contour", "shade")), -1),
    ("what", "Show", choice({k: v for k, v in MARK_EXTREMES.items() if v}), "both"),
    ("loc", "Text at", choice(LOCS), "upper center"),
    ("marker", "Mark where (+ max, × min)", TOGGLE, True),
    ("box", "White box", TOGGLE, True))

SPACING_ROWS = look_rows(
    "spacing", "Spacing", ALL, FIG,
    ("wspace", "Between columns", number(start=0.0, step=0.01), 0.02,
     dict(as_=real(), help="Extra space between panels, as a fraction of a panel")),
    ("hspace", "Between rows", number(start=0.0, step=0.01), 0.02, dict(as_=real())),
    ("w_pad", "Around panels, x (in)", number(start=0.0, step=0.01), 0.04,
     dict(as_=real(), help="Padding around each panel and its labels (inches)")),
    ("h_pad", "Around panels, y (in)", number(start=0.0, step=0.01), 0.04, dict(as_=real()))
) + look_rows(
    "", "matplotlib style", ALL, FIG,
    ("mplstyle", "matplotlib style (blank: none)", text("e.g. dark_background"), "",
     dict(as_=TEXT, help="A matplotlib style name or a .mplstyle file on the server: its "
                         "colours and lines (fonts and sizes stay those above)")))


# ------------------------------------------------------------ a kind's, and a panel's
AREA_ROWS = look_rows(
    "domain", "Area", ("plan",), KPI,
    ("mode", "Plan-view area",
     choice({"Follow the tracked storm": "storm", "Fixed box": "box", "Whole domain": "full"}),
     "storm", dict(help="Follow the tracked storm: the panel stays centred on the storm track "
                        "loaded for the run, moving with it from time to time. Fixed box: "
                        "the same x and y at every time (starting as what the panel shows).",
                   fills="area box")),
    ("half", "Half-width (km)", number(start=0.5, step=0.5), 12.5, dict(as_=real_or(12.5))),
    ("box", "Fixed box", BOX, None)
) + look_rows(
    "domain", "Area", ("plan",), ("inset",),
    ("off", "Centre east, north of the storm (km)", XY, [0.0, 0.0],
     dict(when="mode=storm", as_=As(_xy_text, lambda v: _xy(v) or [0.0, 0.0]),
          help="While the inset follows the storm: how far its centre is east and north of "
               "it"))
) + look_rows(
    "", "Area", ("plan",), KPI,
    ("coords", "Axis coordinates",
     choice({"Model grid x, y": "grid", "Relative to the storm": "storm"}), "grid")
) + look_rows(
    "xsec", "Height and x axis", ("xsec",), KP,
    ("ztop", "Top (km)", number(start=0.5, step=0.5), 6.0, dict(as_=real_or(6.0))),
    ("coords", "x–z, y–z x axis",
     choice({"From the storm": "storm", "Model grid x, y": "grid"}), "storm",
     dict(help="The x axis of x–z and y–z sections through the storm: x (or y) from the "
               "storm's, or the model's. Fixed ones: the model's; angled and A–B ones: the "
               "distance along them")))

AXES_ROWS = look_rows(
    "axes", "Axes and ticks", AXES, KP,
    ("xlabel", "x label", text(), ""),
    ("ylabel", "y label", text(), ""),
    ("ticks", "Tick marks", TOGGLE, True),
    ("minor", "Minor ticks", TOGGLE, False),
    ("tickdir", "Ticks point", choice(TICKDIR), "out",
     dict(as_=one_of(TICKDIR.values(), "out"))),
    ("xstep", "x tick every", auto(start=0), None, dict(as_=BLANKABLE)),
    ("ystep", "y tick every", auto(start=0), None, dict(as_=BLANKABLE, kinds=Y_STEP)),
    ("frame_lw", "Frame width (pt)", number(start=0.1, step=0.1), 0.8, dict(as_=real_or(0.8))),
    ("grid", "Grid lines", TOGGLE, False, dict(as_=FLAG)),
    ("grid_ls", "Grid style", choice({"dotted": ":", "dashed": "--", "solid": "-"}), ":")
) + look_rows(
    "axes", "Axes and ticks", AXES, ("kind",),
    ("ticklabels", "Tick labels on",
     choice({"All panels": "all", "Outer panels": "outer", "No panels": "none"}), "all"),
    ("share", "Share limits (panels of a kind)",
     choice({"No": "none", "x": "x", "y": "y", "x and y": "both"}), "none"),
    ("equal", "Equal x/y scale", TOGGLE, True, dict(kinds=("plan",))))


def _panel_legend(block, kind, on=True, loc="best", frame=False, word="Legend", when=""):
    """A kind's own legend in each panel."""
    return look_rows(
        block, "Legend in the panel", (kind,), KP,
        ("legend", word, TOGGLE, on),
        ("legend_loc", "At", choice(PANEL_LEGEND_LOCS), loc),
        ("legend_ncol", "Columns", integer(1, 8), 1),
        ("legend_frame", "Frame", TOGGLE, frame), when=when)


TS_ROWS = look_rows(
    "ts", "Plot", ("th", "line"), ("kind",),
    ("tmin", "From (min)", text("data"), None, dict(as_=minutes())),
    ("tmax", "To (min)", text("data"), None, dict(as_=minutes()))
) + look_rows(
    "ts", "Plot", ("th",), KP,
    ("zmin", "Axis from (km)", number(step=0.5), 0.0, dict(as_=real_or(0.0))),
    ("zmax", "Axis to (km)", number(step=0.5), 10.0, dict(as_=real_or(10.0)))
) + look_rows(
    "ts", "Plot", ("line",), KP,
    ("ymin", "y from (left axis)", auto(), None, dict(as_=BLANKABLE)),
    ("ymax", "y to (left axis)", auto(), None, dict(as_=BLANKABLE)),
    ("zero_line", "Zero line", TOGGLE, False),
    ("mark", "Mark each line's", choice(MARK_EXTREMES), "",
     dict(as_=As(lambda v: v or "", _same))),
    ("mark_legend", "Extremes in the legend", TOGGLE, False, dict(as_=FLAG)),
    ("mark_edited", "Mark edited lines", TOGGLE, False, dict(as_=FLAG))
) + _panel_legend("ts", "line")


def _snd_table_options():
    order = ("sbcape", "sbcin", "sblcl", "mlcape", "mlcin", "mllcl", "mllfc", "mucape", "mucin",
             "shear250", "shear500", "shear01", "shear03", "shear06", "srh250", "srh500", "srh1",
             "srh3", "esrh", "stp_fixed", "stp_eff", "scp")  # (as the Sounding tab lists them)
    return {f"{h} ({u})" if u else h: k
            for k, h, u in sorted(figdraw.SND_PARAMS, key=lambda p: order.index(p[0]))}


# ------------------------------------------------------------ what a kind's plot shows
def _snd_layout(doc, where):
    """The sounding layout at where (a kind: as its block has it)."""
    from . import BY_KEY, where as W
    try:
        v = W.value(doc, BY_KEY["look.skewt.layout"], where)
    except Exception:  # noqa: BLE001  (a figure with no sounding yet)
        v = None
    if v in ("inset", "side", "skewt", "hodo"):
        return v
    return figdraw.sounding_layout(((doc.get("kinds") or {}).get("sounding") or {}).get(
        "skewt") or {})


WHEN.update({
    "skew-T drawn": lambda doc, where, ctx=None: _snd_layout(doc, where) != "hodo",
    "hodograph drawn": lambda doc, where, ctx=None: _snd_layout(doc, where) != "skewt",
    "hodograph whole": lambda doc, where, ctx=None: _snd_layout(doc, where) in ("side", "hodo"),
    "hodograph inset": lambda doc, where, ctx=None: _snd_layout(doc, where) == "inset"})
HODO = "@hodograph drawn"


def _when(rows, cond):
    """Rows with a condition joined to theirs (each alternative of theirs)."""
    out = []
    for r in rows:
        when = cond if not r.when else " or ".join(f"{a} and {cond}"
                                                   for a in r.when.split(" or "))
        out.append(replace(r, when=when))
    return out


SOUNDING = ("sounding",)
SKEWT_ROWS = look_rows(
    "skewt", "Sounding panels", SOUNDING, KP,
    ("layout", "Sounding layout", choice(SND_LAYOUTS), KEEP),
    ("storm", "Storm motion (SRH, ring)", choice(STORM_MOTIONS), KEEP),
    ("storm_u", "Storm u (m/s)", number(step=1.0), KEEP, dict(as_=real(), when="storm=custom")),
    ("storm_v", "Storm v (m/s)", number(step=1.0), KEEP, dict(as_=real(), when="storm=custom")),
    ("table", "Parameter table under each panel (blank: none)", multi(_snd_table_options()),
     KEEP)
) + _when(look_rows(
    "skewt", "Skew-T", SOUNDING, KP,
    ("pmax", "Bottom (hPa)", number(step=25), KEEP, dict(as_=real())),
    ("pmin", "Top (hPa)", number(step=25), KEEP, dict(as_=real())),
    ("skew", "Skew", number(step=5), KEEP, dict(as_=real())),
    ("tmin", "T left (°C)", number(step=5), KEEP, dict(as_=real())),
    ("tmax", "T right (°C)", number(step=5), KEEP, dict(as_=real())),
    ("lw", "Line width", number(step=0.2), KEEP, dict(as_=real())),
    ("parcel", "Parcel",
     choice({"Mixed layer": "ml", "Surface": "sb", "Most unstable": "mu", "None": "none"}), KEEP),
    ("params", "CAPE / CIN in legend", TOGGLE, KEEP),
    ("guides", "Adiabats", TOGGLE, KEEP),
    ("barbs", "Wind barbs", TOGGLE, KEEP)), "@skew-T drawn") + _when(look_rows(
    "skewt", "Hodograph", SOUNDING, KP,
    ("hodo_center", "Hodograph centred on",
     choice({"The origin (0, 0)": "origin", "What is drawn (fit)": "fit",
             "Custom (u, v below)": "custom"}), KEEP),
    ("hodo_max", "Hodograph ± (m/s)", number(step=5), KEEP,
     dict(as_=real(), help="Half the width of the (square) view", when="hodo_center!=fit")),
    ("hodo_cu", "Centre u (m/s)", number(step=5), KEEP,
     dict(as_=real(), when="hodo_center=custom")),
    ("hodo_cv", "Centre v (m/s)", number(step=5), KEEP,
     dict(as_=real(), when="hodo_center=custom")),
    ("hodo_top", "Hodograph top (km)", number(step=1), KEEP, dict(as_=real())),
    ("hodo_rm", "Bunkers right mover (RM)", TOGGLE, KEEP),
    ("hodo_lm", "Bunkers left mover (LM)", TOGGLE, KEEP),
    ("hodo_mean", "0–6 km mean wind", TOGGLE, KEEP),
    ("hodo_labels", "Heights along the trace", TOGGLE, KEEP),
    ("hodo_heights", "Heights marked (km)", text(), KEEP,
     dict(help="Along the trace, e.g. 0.5, 1, 3, 6 or 0:3:0.5 (start:stop:step)",
          when="hodo_labels!=false")),
    ("hodo_key", "Key of the height colours", TOGGLE, KEEP, dict(when="@hodograph whole")),
    ("hodo_key_loc", "Key at", choice(LOCS), KEEP,
     dict(when="@hodograph whole and hodo_key!=false")),
    ("hodo_key_ncol", "Key columns", integer(1, 8), KEEP,
     dict(when="@hodograph whole and hodo_key!=false")),
    ("hodo_key_frame", "Key frame", TOGGLE, KEEP,
     dict(when="@hodograph whole and hodo_key!=false")),
    ("srh", "SRH shading", choice({"None": "", "0–1 km": "1", "0–3 km": "3"}), KEEP,
     dict(when="@hodograph whole")),
    ("hodo_storm", "Ring at the storm motion", TOGGLE, KEEP),
    ("inset_loc", "Inset at",
     choice({"Auto (clear of the traces)": "clear",
             "Auto, top corners only (older figures)": "auto", "Upper right": "upper right",
             "Upper left": "upper left", "Lower right": "lower right",
             "Lower left": "lower left", "Custom (x, y below)": "custom"}), KEEP,
     dict(when="@hodograph inset")),
    ("inset_size", "Inset size", number(step=0.01), KEEP,
     dict(as_=real(), help="Width as a fraction of the skew-T's (0.37: the default)",
          when="@hodograph inset")),
    ("inset_x", "Inset x (left edge)", number(step=0.01), KEEP,
     dict(as_=real(), help="Fraction of the skew-T's width: 0 left, 1 right",
          when="@hodograph inset and inset_loc=custom")),
    ("inset_y", "Inset y (bottom edge)", number(step=0.01), KEEP,
     dict(as_=real(), help="Fraction of the skew-T's height: 0 bottom, 1 top",
          when="@hodograph inset and inset_loc=custom"))), HODO) + _panel_legend("skewt", "sounding", on=False, loc="upper left", frame=True,
                  word="Legend (one sounding)")

DIST = ("dist",)
_HIST = "plot=hist|None"  # (a histogram's, the plot a figure without one draws)
_BOXY = "plot=box|violin"
_LINEY = "plot!=box and plot!=violin"  # (a box plot has no count axis, no legend)
DIST_ROWS = look_rows(
    "dist", "Plot", DIST, KP,
    ("plot", "Draw as", choice(DIST_PLOTS), KEEP),
    ("norm", "Histogram of", choice(DIST_NORMS), KEEP,
     dict(help="PDF: the whole sample integrates to 1 (values outside the range count too); "
               "fraction: of the whole sample per bin", when=_HIST)),
    ("bins", "Bins", integer(1, 2000), KEEP, dict(when=_HIST)),
    ("width", "Bin width", auto(), KEEP,
     dict(as_=BLANKABLE, help="Blank: the number of bins", when=_HIST)),
    ("hstyle", "Bars as", choice(DIST_HSTYLES), KEEP, dict(when=_HIST)),
    ("bar_labels", "Bar labels", choice(DIST_BAR_LABELS), KEEP, dict(when=_HIST)),
    ("cum", "Fraction", choice(DIST_CUM), KEEP, dict(when="plot=ecdf")),
    ("whis", "Whiskers", choice(DIST_WHIS), KEEP, dict(when=_BOXY)),
    ("xmin", "Values from", auto(), KEEP, dict(as_=BLANKABLE)),
    ("xmax", "Values to", auto(), KEEP, dict(as_=BLANKABLE)),
    ("ymin", "Count axis from", auto(), KEEP,
     dict(as_=BLANKABLE, when="plot!=ecdf and " + _LINEY)),
    ("ymax", "Count axis to", auto(), KEEP,
     dict(as_=BLANKABLE, when="plot!=ecdf and " + _LINEY)),
    ("ymin", "Fraction axis from", auto(), KEEP,  # (the same axis, an ECDF's: a fraction)
     dict(as_=BLANKABLE, when="plot=ecdf", tag="ecdf")),
    ("ymax", "Fraction axis to", auto(), KEEP,
     dict(as_=BLANKABLE, when="plot=ecdf", tag="ecdf")),
    ("logy", "Log scale", TOGGLE, KEEP),
    ("means", "Mean (diamond)", TOGGLE, KEEP, dict(when=_BOXY)),
    ("horizontal", "Horizontal", TOGGLE, KEEP, dict(when=_BOXY)),
    ("zero_line", "Zero line", TOGGLE, KEEP),
    ("alpha", "Fill opacity", number(0.0, 1.0, 0.05), KEEP, dict(as_=opt_or(0.35))),
    ("lw", "Line width", number(start=0.0, step=0.25), KEEP, dict(as_=opt_or(1.5)))
) + look_rows(
    "dist", "Statistics", DIST, KP,
    ("stats", "Statistics of each distribution (blank: none)",
     multi({v: k for k, v in figdraw.DIST_STATS.items()}), KEEP),
    ("stats_at", "Statistics shown", choice(DIST_STATS_AT), KEEP),
    ("stats_loc", "Box at", choice(LOCS), KEEP, dict(when="stats_at=box"))
) + _panel_legend("dist", "dist", when=_LINEY)

PROFILE_ROWS = look_rows(
    "prof", "Plot", ("profile",), KP,
    ("xmin", "Values from", auto(), KEEP, dict(as_=BLANKABLE)),
    ("xmax", "Values to", auto(), KEEP, dict(as_=BLANKABLE)),
    ("zmin", "Axis from (km)", auto(), KEEP,
     dict(as_=BLANKABLE, help="Blank: the profiles' layer")),
    ("zmax", "Axis to (km)", auto(), KEEP,
     dict(as_=BLANKABLE, help="Blank: the profiles' layer")),
    ("zero_line", "Zero line", TOGGLE, KEEP),
    ("mark_edited", "Mark edited lines", TOGGLE, KEEP)
) + _panel_legend("prof", "profile")

JOINT = ("joint",)
JOINT_ROWS = look_rows(
    "joint", "Plot", JOINT, KP,
    ("plot", "Draw as", choice(JOINT_PLOTS), KEEP),
    ("norm", "Histogram of", choice(DIST_NORMS), KEEP,
     dict(help="PDF: the whole sample integrates to 1; fraction: of the whole sample per bin",
          when=_HIST)),
    ("bins", "Bins (each axis)", integer(2, 200), KEEP),
    ("cmap", "Colormap", choice(FIG_CMAPS), KEEP, dict(when=_HIST)),
    ("cbar_label", "Colorbar label", text("what it counts"), KEEP,
     dict(help="Blank: what it counts", when=_HIST)),
    ("pcts", "Contours enclosing (%)", text(), KEEP,
     dict(help="Each contour encloses this percentage of the pairs, densest first")),
    ("ms", "Dot size", number(start=0.5, step=0.5), KEEP,
     dict(as_=opt_or(2.0), when="plot=scatter")),
    ("alpha", "Dot opacity", number(0.05, 1.0, 0.05), KEEP,
     dict(as_=opt_or(0.5), when="plot=scatter")),
    ("lw", "Line width", number(start=0.25, step=0.25), KEEP, dict(as_=opt_or(1.2))),
    ("xmin", "x from", auto(), KEEP, dict(as_=BLANKABLE)),
    ("xmax", "x to", auto(), KEEP, dict(as_=BLANKABLE)),
    ("ymin", "y from", auto(), KEEP, dict(as_=BLANKABLE)),
    ("ymax", "y to", auto(), KEEP, dict(as_=BLANKABLE)),
    ("log", "Log colours", TOGGLE, KEEP, dict(when=_HIST)),
    ("reverse", "Reverse", TOGGLE, KEEP, dict(when=_HIST)),
    ("colorbar", "Colorbar", TOGGLE, KEEP, dict(when=_HIST)),
    ("contours", "Contours over", TOGGLE, KEEP, dict(when="plot!=contour")),
    ("contour_labels", "Contour labels", TOGGLE, KEEP),
    ("fit", "Fit line", TOGGLE, KEEP),
    ("one_one", "1:1 line", TOGGLE, KEEP),
    ("zero_line", "Zero lines", TOGGLE, KEEP)
) + look_rows(
    "joint", "Statistics", JOINT, KP,
    ("stats", "Statistics of each (blank: none)",
     multi({v: k for k, v in figdraw.JOINT_STATS.items()}), KEEP),
    ("stats_loc", "Box at", choice(LOCS), KEEP)
) + _panel_legend("joint", "joint")

AZIM_ROWS = look_rows(
    "azim", "Plot", ("azim",), KP,
    ("plot", "Shade as", choice({"Grid cells": "mesh", "Filled contours": "filled"}), KEEP),
    ("cmap", "Colormap", choice({"The field's": ""} | {c: c for c in FIG_CMAPS}), KEEP),
    ("nlevels", "Colour steps", integer(2, 60), KEEP),
    ("vmin", "Min", auto(), KEEP, dict(as_=BLANKABLE)),
    ("vmax", "Max", auto(), KEEP, dict(as_=BLANKABLE)),
    ("cbar_label", "Colorbar label", text("the field's"), KEEP,
     dict(help="Blank: the field's")),
    ("rmin", "Radius from (km)", auto(), KEEP, dict(as_=BLANKABLE)),
    ("rmax", "Radius to (km)", auto(), KEEP, dict(as_=BLANKABLE)),
    ("zmin", "Axis from (km)", auto(), KEEP, dict(as_=BLANKABLE)),
    ("zmax", "Axis to (km)", auto(), KEEP, dict(as_=BLANKABLE)),
    ("reverse", "Reverse", TOGGLE, KEEP),
    ("colorbar", "Colorbar", TOGGLE, KEEP),
    ("clabels", "Contour labels", TOGGLE, KEEP)
) + _panel_legend("azim", "azim")

TABLE_ROWS = look_rows(
    "table", "Table", ("table",), KP,
    ("layout", "Set out as", choice(TBL_LAYOUTS), KEEP),
    ("compare", "Show", choice(TBL_COMPARE), KEEP),
    ("decimals", "Decimals", choice(TBL_DECIMALS), KEEP))


# ------------------------------------------------------------ 3D scenes
# (a scene's settings are written a key of its block at a time, whole: its camera, its look; the
# only scene's go to the kind, docedit.write_scene)
def _scene(sub, section, *specs):
    rows = look_rows(f"scene3d.{sub}" if sub else "scene3d", section, ("scene",), KP, *specs)
    return [replace(r, writer="scene") for r in rows]


SCENE_ROWS = _scene(
    "", "Region and resolution",
    ("box", "Region", BOX, None,
     dict(help="Blank: the whole domain; else x min, x max, y min, y max (km)")),
    ("ztop", "Top (km)", number(start=0.5, step=0.5), KEEP, dict(as_=real())),
    ("exag", "Vertical exaggeration", number(start=0.25, step=0.5), 2.0, dict(as_=real())),
    ("smooth", "Smoothing σ (grid cells)", number(start=0.0, step=0.25), 0.75,
     dict(as_=real())),
    ("res", "Resolution", choice(SCENE_RES), 0,
     dict(help="Auto: coarser for a large region (about 12 million grid points at most)"))
) + _scene(
    "camera", "Camera",
    ("preset", "View", choice(SCENE_VIEWS), "oblique"),
    ("azimuth", "Azimuth (°)", auto(), None,
     dict(as_=BLANKABLE, help="The compass bearing the camera stands at from the middle (0: "
                              "north, 90: east). Blank: the view's")),
    ("elevation", "Elevation (°)", auto(), None,
     dict(as_=BLANKABLE, help="Above the horizon (90: straight down). Blank: the view's")),
    ("zoom", "Zoom", number(start=0.1, step=0.1), 1.0,
     dict(as_=real(1.0), help="1: the whole region fits; 2: twice as close")),
    ("projection", "Projection", choice(SCENE_PROJ), "perspective"),
    ("view_angle", "View angle (°)", number(5.0, 120.0, 5.0), 30.0,
     dict(as_=real(30.0), help="Perspective only: smaller is flatter (a long lens)"))
) + _scene(
    "ground", "Floor",
    ("on", "Floor", TOGGLE, False),
    ("var", "Field", FIELD, None),
    ("z", "Height (km; 0: lowest level)", number(start=0.0, step=0.25), 0.0, dict(as_=real())),
    ("cmap", "Colormap", choice(SCENE_FLOOR_CMAPS), "Field default"),
    ("rev", "Reverse", TOGGLE, False),
    ("range", "Range", choice(SCENE_FLOOR_RANGE), "data"),
    ("lo", "Min", number(), 0.0, dict(as_=real())),
    ("hi", "Max", number(), 0.0, dict(as_=real()))
) + _scene(
    "stream", "Streamlines",
    ("on", "Streamlines", TOGGLE, False),
    ("z", "Seed height (km)", number(start=0.0, step=0.1), 0.5, dict(as_=real())),
    ("n", "Seeds across (n × n)", integer(2, 40), 12),
    ("length", "Max length (km)", number(start=1.0, step=5.0), 40.0, dict(as_=real())),
    ("dir", "Direction", choice(SCENE_STREAM_DIR), "forward"),
    ("frame", "Frame", choice("frames"), "storm"),
    ("color_by", "Colour by", choice(SCENE_STREAM_BY), "z")
) + _scene(
    "look", "Look",
    ("lighting", "Lighting", choice(SCENE_LIGHTS), "kit"),
    ("background", "Background", choice(SCENE_BG), ""),
    ("outline_color", "Box colour", COLOUR, "#475569"),
    ("tube", "Line thickness", number(start=0.1, step=0.25), 1.0,
     dict(as_=real(1.0), help="Streamline tubes and line arrows (1: the default)")),
    ("arrows", "Vectors as", choice(SCENE_ARROWS), "glyph"),
    ("shine", "Shine", number(0.0, 1.0, 0.1), 0.3,
     dict(as_=real(), help="The surfaces' specular highlight (0: matte)")),
    ("ambient", "Ambient light", number(0.0, 1.0, 0.05), 0.25,
     dict(as_=real(), help="How light the shadowed sides stay")),
    ("floor_bar", "Floor colorbar", choice(SCENE_BARS), "bottom"),
    ("stream_bar", "Streamline colorbar", choice(SCENE_BARS), "right"),
    ("parcel_bar", "Parcel colorbar", choice(SCENE_BARS), "left"),
    ("outline", "Box outline", TOGGLE, True),
    ("ticks", "Axis ticks", TOGGLE, True),
    ("legend", "Legend", TOGGLE, True),
    ("seed_box", "Seed box outline", TOGGLE, True),
    ("labels", "Axis labels (x, y, z)", text("x (km), y (km), z (km)"), None,
     dict(as_=As(lambda v: ", ".join(v or []), lambda t: [s.strip() for s in t.split(",")]
                 if t and t.strip() else None)))
) + _scene(
    "", "Animation",
    ("follow", "Box in animations",
     choice({"Stays where it is": "fixed", "Follows the track": "track"}), "fixed",
     dict(help="A fixed box moved each frame by as far as the run's track has moved since the "
               "first frame")),
    ("orbit", "Camera orbit (°)", number(-3600.0, 3600.0, 15.0), 0.0,
     dict(as_=real(), help="How far the camera turns round the region over the whole "
                           "animation (360: once round; negative: the other way)")))


# (a scene's lists, a row per setting of an item; adding and removing them: the drawer's)
SCENE_ROWS += _scene(
    "isos[]", "Isosurfaces",
    ("on", "Drawn", TOGGLE, True),
    ("var", "Field", FIELD, None),
    ("val", "Value", number(), 0.0, dict(as_=real())),
    ("color", "Colour", COLOUR, "#7dd3fc"),
    ("op", "Opacity", number(0.05, 1.0, 0.05), 0.5, dict(as_=real(0.5)))
) + _scene(
    "vecs[]", "Vectors",
    ("on", "Drawn", TOGGLE, True),
    ("q", "Vector", choice("vectors"), "wind", dict(fills="scene vector")),
    ("level", "Height (km)", number(start=0.0, step=0.25), 0.0, dict(as_=real())),
    ("frame", "Frame", choice("frames"), "ground", dict(when="@framed item")),
    ("density", "Arrows across", integer(4, 60), 16),
    ("ref", "Ref. length", number(start=0.1), KEEP,  # (a new Vector: its own, schema/fills.py)
     dict(as_=real(20.0), help="The vector length that makes an arrow one spacing long")),
    ("color", "Colour", COLOUR, "#000000")
) + _scene(
    "parcels[]", "Parcels",
    ("on", "Drawn", TOGGLE, True),
    ("name", "Parcels", PSET, "parcels",
     dict(fills="pset", help="The parcel set drawn: pick another set of the viewer, or a saved "
                             "one")),
    ("cvar", "Colour by", PVAR, "", dict(fills="scene pvar")),
    ("color", "Colour", COLOUR, "#d62728", dict(when="!cvar")),
    ("cmap", "Colormap", CMAP, "viridis", dict(when="cvar")),
    ("tails", "Tails", choice(SCENE_PAR_TAILS), "until"),
    ("minutes", "Minutes", number(0.0, step=5.0), 10.0, dict(when="tails=last")),
    ("lw", "Line width", number(0.0, step=0.5), 1.5),
    ("ms", "Head size", number(0.0, step=0.5), 3.0),
    ("alpha", "Opacity", number(0.0, 1.0, 0.1), 0.8,
     dict(as_=As(float, lambda v: 0.8 if v is None else float(v)))),
    ("heads", "Heads", TOGGLE, True),
    ("moving", "Tails seen from", choice(PAR_MOVING), "grid"),
    ("move_u", "u (m/s)", number(step=1.0), 0.0, dict(when="moving=motion", as_=real())),
    ("move_v", "v (m/s)", number(step=1.0), 0.0, dict(when="moving=motion", as_=real())))


ROWS = (TEXT_ROWS + LABEL_ROWS + COLORBAR_ROWS + LEGEND_ROWS + CONTOUR_KEY_ROWS + EXTREMES_ROWS
        + SPACING_ROWS + AREA_ROWS + AXES_ROWS + TS_ROWS + SKEWT_ROWS + DIST_ROWS + PROFILE_ROWS
        + JOINT_ROWS + AZIM_ROWS + TABLE_ROWS + SCENE_ROWS)
