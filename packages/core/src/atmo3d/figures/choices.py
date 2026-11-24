"""The figure editor's choices: each list's options as {what the user reads: what is saved}
(or a list, where they are the same), with no widgets, for the settings schema and the drawers;
and a few helpers of colours and times they share."""

import math

from matplotlib import font_manager
from matplotlib.colors import to_hex

from . import draw as figdraw
from ..core.fields import CMAPS


# ------------------------------------------------------------ shared
PYART_CMAPS = ["HomeyerRainbow", "ChaseSpectral", "NWSRef", "NWSVel", "LangRainbow12",
               "SpectralExtended", "Carbone42", "Theodore16", "BuDRd18"]
FIG_CMAPS = list(dict.fromkeys(PYART_CMAPS + CMAPS + [
    "Greys", "gray_r", "Blues", "Reds", "Purples", "PuOr", "RdBu", "bwr", "jet"]))


def known_cmap(name):
    """name if the Colormap lists offer it, else viridis."""
    return name if name in FIG_CMAPS else "viridis"


def _nice(a):
    """a rounded to 1, 2 or 5 times a power of ten (at least that large)."""
    a = abs(float(a)) or 1.0
    p = 10.0 ** math.floor(math.log10(a))
    return float(next(m * p for m in (1, 2, 5, 10) if m * p >= a - 1e-9))


LOCS = ["upper left", "upper right", "lower left", "lower right", "upper center",
        "lower center", "center left", "center right"]
FIG_LOCS = ["outside right center", "outside right upper", "outside left center",
            "outside lower center", "outside upper center"]  # (a figure legend's, beside the panels)
LABEL_LOCS = LOCS + ["above left", "above right"]  # panel letters, times, run names
MARK_EXTREMES = {"None": "", "Maximum": "max", "Minimum": "min", "Both": "both"}
LEVEL_MODES = {"Height (km AGL)": "height", "Model level (k)": "level",
               "Column max": "colmax", "Column min": "colmin"}
# figures with a run whose levels follow the terrain: heights above sea level too
TERRAIN_LEVEL_MODES = {"Height (km AGL)": "height", "Height (km MSL)": "msl",
                       "Model level (k)": "level", "Column max": "colmax",
                       "Column min": "colmin"}
FONT_CHOICES = ["sans-serif", "serif", "DejaVu Sans", "Arial", "Helvetica", "Liberation Sans",
                "Nimbus Sans", "Source Sans Pro", "Roboto", "Open Sans", "Noto Sans",
                "DejaVu Serif", "Times New Roman", "Liberation Serif", "Nimbus Roman",
                "STIXGeneral", "Noto Serif"]


def _installed_fonts():
    """FONT_CHOICES matplotlib finds on this machine (the generic families always)."""
    try:
        have = {f.name for f in font_manager.fontManager.ttflist}
    except Exception:  # noqa: BLE001
        have = set()
    return [f for f in FONT_CHOICES if f in ("sans-serif", "serif") or f in have]


FONTS = _installed_fonts()
MATH_FONTS = {"DejaVu Sans": "dejavusans", "Like the text font": "custom",
              "STIX Sans": "stixsans", "STIX (Times-like)": "stix",
              "Computer Modern (LaTeX)": "cm"}
FRAMES = {"Ground-relative": "ground", "Grid-relative": "grid", "Storm-relative": "storm"}
HATCHES = {"Solid": "", "Hatching /": "///", "Hatching \\": "\\\\\\", "Cross-hatching": "xxx",
           "Stippling": "..", "Dense stippling": "...", "Circles": "oo"}  # (shade layers)
GRID_DIMS = {"— (fill row by row)": "none", "Runs": "runs", "Sections": "sections",
             "Times": "times", "Fields": "fields", "Heights": "heights"}  # (rows / columns)
QUICK_VARY = {"Time": "times", "Field (one time)": "fields", "Height (one time)": "heights",
              "Run (one time)": "runs",
              "Nothing (alike panels)": "none"}  # (the New dialog: panels fill the grid)
LETTERS = {"a": "{a}", "(a)": "({a})", "a)": "{a})", "A": "{A}", "(A)": "({A})"}
INSET_LOCS = {"Upper right": "upper right", "Upper left": "upper left",
              "Lower right": "lower right", "Lower left": "lower left",
              "At x, y (left, bottom)": "custom"}
TYPE_LABEL = {"fill": "Fill", "contour": "Contours", "shade": "Shading", "vectors": "Vectors",
              "track": "Storm track", "line": "Section line", "sector": "Sector",
              "parcels": "Parcels", "boundaries": "Map boundaries"}
PAR_TAILS = {"Up to the panel time": "until", "All parcel times": "all",
             "Last minutes": "last", "None (heads only)": "none"}
PAR_MOVING = {"The grid": "grid", "Moving with the tracked storm": "track",
              "Moving at a motion": "motion"}
PAR_XS_TAILS = {"Their parts near it": "near", "Whole, of parcels near it now": "whole"}
REDUCE = {"One time (off)": "", "Maximum (swath)": "max", "Minimum": "min", "Mean": "mean",
          "Sum": "sum", "Storm-following mean (composite)": "composite"}
GRIDS = {"Say so (ask)": "ask", "Interpolate onto this layer's grid": "interp",
         "Refuse": "refuse"}
EXTEND = {"Auto (where the data pass the range)": "auto", "None": "neither",
          "Max end": "max", "Min end": "min", "Both ends": "both"}
TICKDIR = {"Out": "out", "In": "in", "Across": "inout"}
CB_MODES = {"One for the figure": "shared", "One per row": "row", "One per column": "col",
            "One per panel": "each", "None": "none"}
CB_LOCS = {"Below": "bottom", "Right": "right", "Above": "top", "Left": "left"}
SIZE_PRESETS = {"Custom": "", "3.25 in wide (one journal column)": "3.25",
                "5 in wide": "5", "6.5 in wide (full page width)": "6.5", "7.5 in wide": "7.5",
                "Slide, 13.3 × 7.5 in": "13.333x7.5"}
SER_REGIONS = {"Around tracked storm": "track", "Whole domain": "domain",
               "Fixed box (map view)": "box"}
SER_REDUCE = {"Maximum": "max", "Minimum": "min", "Mean": "mean", "Percentile": "pct"}
AZ_REFS = {"Storm motion (0: ahead, 90: right)": "motion", "Grid north (0: north, 90: east)":
           "north"}
AZ_CENTERS = {"Tracked storm (offset, km)": "track", "Point (model x, y km)": "point"}
SER_OPS = {"None": "", "d/dz (per m)": "ddz", "d/dt (per s)": "ddt"}
MARKERS = {"none": "", "dots": "o", "squares": "s", "triangles": "^"}
LINE_STYLES = {"Solid": "-", "Dashed": "--", "Dotted": ":", "Dash-dot": "-."}
SND_LAYOUTS = {"Skew-T with a hodograph inset": "inset",
               "Skew-T and hodograph side by side": "side", "Skew-T only": "skewt",
               "Hodograph only": "hodo"}
SND_WHERE = {"Storm (offset, km)": "trk", "Point (model x, y km)": "pt",
             "Domain mean": "mean"}
STORM_MOTIONS = {"Bunkers right mover": "rm", "Bunkers left mover": "lm",
                 "0–6 km mean wind": "mean", "Custom (u, v)": "custom"}
ANN_KINDS = {"Text": "text", "Marker": "marker", "Arrow": "arrow", "Line": "line",
             "Vertical line": "vline", "Horizontal line": "hline", "Box": "box",
             "Circle": "circle", "Legend entry": "legend"}
ANN_FIELDS = {  # widgets each kind uses (besides kind, panel, colour, remove)
    "text": ("coords", "x", "y", "text", "size", "bold"),
    "marker": ("coords", "x", "y", "marker", "size", "lw", "text", "bold"),
    "arrow": ("coords", "x", "y", "x2", "y2", "text", "size", "lw", "bold"),
    "line": ("coords", "x", "y", "x2", "y2", "lw", "ls"),
    "vline": ("x", "lw", "ls", "text", "bold"),
    "hline": ("y", "lw", "ls", "text", "bold"),
    "box": ("coords", "x", "y", "x2", "y2", "lw", "ls"),
    "circle": ("coords", "x", "y", "r", "lw", "ls"),
    "legend": ("text", "look", "lw", "ls", "marker", "alpha"),  # (no place: in the legend)
}
ENS_BANDS = {"Off": "", "Min to max": "minmax", "10–90th percentile": "p10p90",
             "25–75th percentile": "p25p75", "Mean ± 1 sd": "sd"}
ENS_MIDS = {"Mean": "mean", "Median": "median", "None": ""}
ENS_MEMBERS = {"Faint": "faint", "Hidden": "hidden", "As other lines": "full"}
PANEL_CHOICES = {  # (a grid has at most 8 × 8 cells; letters repeat past z, as drawn)
    figdraw.panel_letter(i, "{a}") if i < 26 else f'{figdraw.panel_letter(i, "{a}")} ({i + 1})':
    i + 1 for i in range(64)}


# ------------------------------------------------------------ series
SER_VMODES = {"Layer (every level)": "layer", "At a height": "height"}
SND_LINES = (("T", "Temperature", "#d62728", "-"), ("Td", "Dewpoint", "#2ca02c", "-"),
             ("Tp", "Parcel", "#000000", "--"))  # (what Own line looks starts from)


# ------------------------------------------------------------ layers
ENS_STATS = {"Mean": "mean", "Median": "median", "Spread (sd)": "sd", "Min": "min",
             "Max": "max", "Range (max − min)": "range",
             "Probability of exceeding (%)": "prob"}


# ------------------------------------------------------------ tables
TBL_WHAT = {"Sounding parameters": "sounding", "Field statistics": "field"}
TBL_LAYOUTS = {"A row per run and time, a column per value": "rows",
               "A row per value, a column per run and time": "values",
               "A row per value and run, a column per time": "values_run",
               "A row per value and time, a column per run": "values_time"}
TBL_COMPARE = {"The values": "", "Differences from the first run": "run",
               "Differences from the first time": "time"}
TBL_DECIMALS = {"Automatic": -1, "0": 0, "1": 1, "2": 2, "3": 3, "4": 4}


# ------------------------------------------------------------ profiles
PROF_STYLES = dict(LINE_STYLES, Solid="")  # (saved so: solid is the blank value)
PROF_OPS = {"None": "", "d/dz (per m)": "ddz"}


# ------------------------------------------------------------ 3D scenes
SCENE_VIEWS = {"From the southwest": "oblique", "From above": "top", "From the south": "south",
               "From the north": "north", "From the west": "west", "From the east": "east"}
SCENE_PROJ = {"Perspective": "perspective", "Orthographic (no foreshortening)": "orthographic"}
SCENE_RES = {"Auto": 0, "Full": 1, "1/2": 2, "1/3": 3, "1/4": 4}
SCENE_LIGHTS = {"Light kit (soft, from several sides)": "kit", "Three lights": "three",
                "Headlight (from the camera)": "head"}
SCENE_BG = {"The figure's (Export)": "", "White": "white", "Black": "black",
            "Transparent": "transparent"}
SCENE_ARROWS = {"3D arrows (scaled by length)": "glyph", "Lines (as the 3D view)": "lines"}
SCENE_BARS = {"Below": "bottom", "Right": "right", "Left": "left", "Above": "top",
              "None": "none"}
SCENE_STREAM_DIR = {"Forward": "forward", "Backward": "backward", "Both": "both"}
SCENE_STREAM_BY = {"Height": "z", "Vertical velocity": "w"}
SCENE_FLOOR_RANGE = {"From the data": "data", "Field default": "field", "Custom": "custom"}
SCENE_FLOOR_CMAPS = ["Field default"] + list(CMAPS)  # (the 3D view's: also plotly's)
SCENE_PAR_TAILS = {k.replace("panel", "scene"): v for k, v in PAR_TAILS.items()}


# ------------------------------------------------------------ joint distributions
JOINT_PLOTS = {"2D histogram": "hist", "Scatter": "scatter", "Density contours": "contour"}


# ------------------------------------------------------------ parcel series
PAR_OPS = {"Value": "", "d/dt along the parcel": "ddt",
           "Change since the set's time": "delta", "∫ dt since the set's time": "int"}
OP_TAGS = {"ddt": " d/dt", "delta": " change", "int": " ∫ dt"}
PAR_EACH_LOOK = {"Faint": "faint", "As other lines": "full"}


# ------------------------------------------------------------ distributions
DIST_VMODES = {"At a height": "height", "Layer (every level)": "layer",
               "Every level (whole depth)": "all"}
DIST_PLOTS = {"Histogram": "hist", "Box plot": "box", "Violin": "violin",
              "Cumulative (ECDF)": "ecdf"}
DIST_NORMS = {"Count": "count", "PDF (density)": "pdf", "Fraction": "frac"}
DIST_HSTYLES = {"Filled outline": "stepfilled", "Outline": "step", "Bars": "bar"}
DIST_CUM = {"At or below x": "below", "Above x (exceedance)": "above"}
DIST_BAR_LABELS = {"None": "", "Count": "count", "Percent of the sample": "percent",
                   "Value (as the count axis)": "axis"}
DIST_STATS_AT = {"In the legend (box plots: under the boxes)": "legend",
                 "In a box in the panel": "box"}
DIST_WHIS = {"1.5 × IQR (Tukey)": "tukey", "Min – max": "range", "5th – 95th percentile": "p5",
             "1st – 99th percentile": "p1"}


# ------------------------------------------------------------ azimuthal means
AZ_OPS = {"Mean": "mean", "Maximum": "max", "Minimum": "min"}


# ------------------------------------------------------------ helpers
def _hex(c, default="#000000"):
    try:
        return to_hex(c)
    except (ValueError, TypeError):
        return default


def _near(opts, ts):
    """The value of opts nearest model time ts ("": None, or no times)."""
    vals = [v for v in opts.values() if v != ""]
    return "" if ts is None or not vals else min(vals, key=lambda v: abs(v - float(ts)))


def _dark(color):
    """Light colours chosen for the dark map turn black on a white figure."""
    try:
        r, g, b = (int(color.lstrip("#")[k:k + 2], 16) for k in (0, 2, 4))
    except (ValueError, AttributeError):
        return "#000000"
    return "#000000" if 0.299 * r + 0.587 * g + 0.114 * b > 180 else color
