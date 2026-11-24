"""The figure editor's settings, each described once (docs-dev/figures-ui-plan.md, Phase 2): where
it is saved, its control, its section, the kinds of panel it applies to and the levels it can be
set at.  One generic drawer (figures/ui/drawer.py) shows any section of them at any level, and
Find searches them.  No widgets here: a row says what control it needs, the drawer makes it.

A row's key names a setting whatever level it is written at (as the inventory does,
tests/core/figure_inventory.setting_of):

  look.<block>.<name>  a look setting: in style, kinds[kind], a panel's opts or an inset's opts
  look.<name>          one with no block (coords, label_fit, mplstyle)
  layer.<name>         a layer's: the shared layer (layers[id]), or a panel's (what it changes of
                       the shared layer, its "over", or a layer of its own)
  anything else        the document's own (schema/doc.py): suptitle, size, code.on, grid.rows,
                       runs[].label, annotations[].x, sections[].<name>, panels[].<name>,
                       insets[].<name>

Levels (where.py reads and writes them):

  figure   the whole figure: the document itself, or its style
  kind     every panel of a kind (kinds[kind]); a layer row: the shared layer (Where.layer: its
           id)
  panel    one panel (its opts); a layer row: the layer as that panel draws it (Where.layer:
           its place, as figdraw.panel_layers counts them)
  inset    one zoom inset (its opts, over its panel's); a layer row: one of its own layers

A layer row is of the layer types in its types (an entry of another source is a type of its own:
"series:parcels"); one key can have a row per type it means another thing to (layer.cmap~fill,
layer.cmap~parcels): Row.id names it, row_for(key, type) finds it.  What a layer row shows under
is a condition on the layer's other settings (when_ok); what it sets beside itself, a fill
(schema/fills.py).

A look setting is read style, then kinds[kind], then the panel's opts, then an inset's
(spec/doc.py), last wins; writing at a level writes there and nowhere else."""

import re
from collections import namedtuple
from dataclasses import dataclass

from .. import draw as figdraw
from ..kinds import KINDS

KEEP = object()  # (a row with no default: a figure that lacks it shows the control as it is)
LEVELS = ("figure", "kind", "panel", "inset")
ALL = tuple(KINDS)


# ------------------------------------------------------------ between saved and shown
As = namedtuple("As", "show read")  # saved value -> control value, and back


def _same(v):
    return v


def _num(v):
    """A blank-able number for the spec (None when blank)."""
    return None if v in (None, "") else float(v)


def _xy(text):
    """An "x, y" text as [x, y] for the spec (None unless two numbers)."""
    v = re.findall(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?", str(text or ""))
    return [float(v[0]), float(v[1])] if len(v) == 2 else None


def _xy_text(v):
    """[x, y] as the text of an "x, y" box (blank: none)."""
    return f"{v[0]:g}, {v[1]:g}" if v else ""


def _panels_parse(text):
    """'a, c' / '1, 3' / 'b-d' / '2-4' -> sorted 0-based panel indices ([]: every
    panel).  Raises ValueError on anything else."""
    out = set()
    for part in str(text or "").replace(";", ",").split(","):
        part = part.strip().lower()
        if not part:
            continue
        a, _, b = part.partition("-")
        ends = []
        for v in (a.strip(), (b or a).strip()):
            if v.isdigit() and int(v) > 0:
                ends.append(int(v) - 1)
            elif len(v) == 1 and v.isalpha():
                ends.append(ord(v) - ord("a"))
            else:
                raise ValueError(f"panels: {part!r} is not a panel letter or number")
        out.update(range(min(ends), max(ends) + 1))
    return sorted(out)


def _panel_tok(i):
    """Panel i (from 0) as typed: its letter (past z, where letters repeat: its number)."""
    return figdraw.panel_letter(int(i), "{a}") if int(i) < 26 else str(int(i) + 1)


def _panels_text(panels):
    return ", ".join(_panel_tok(i) for i in panels or [])


def _panels_loose(text):
    """Like _panels_parse, also split by spaces, leaving out what is not a panel."""
    out = set()
    for tok in str(text or "").replace(",", " ").split():
        try:
            out.update(_panels_parse(tok))
        except ValueError:
            continue
    return sorted(out)


def parse_panels(text):
    """An annotation's "panel" from the Panels box (letters or numbers from 1): -1 (blank,
    "all" or 0: every panel), one panel index, or a sorted list of them ("a, c-d" and
    "1, 3-4" -> [0, 2, 3]); what is not a panel or a range of them is left out."""
    toks = str(text or "").replace(",", " ").split()
    if any(int(n) <= 0 for t in toks for n in t.split("-") if n.isdigit()):
        return -1
    ps = _panels_loose(text)
    return -1 if not ps else ps[0] if len(ps) == 1 else ps


def panels_text(p):
    """The Panels box's text of an annotation's "panel" (the inverse of parse_panels)."""
    ps = sorted(int(q) for q in p) if isinstance(p, (list, tuple)) else [int(p)]
    if not ps or -1 in ps:
        return ""
    out, i = [], 0
    while i < len(ps):  # runs of consecutive panels as ranges
        j = i
        while j + 1 < len(ps) and ps[j + 1] == ps[j] + 1:
            j += 1
        out.append(_panel_tok(ps[i]) if j == i else f"{_panel_tok(ps[i])}-{_panel_tok(ps[j])}")
        i = j + 1
    return ", ".join(out)


RAW = As(_same, _same)
FLAG = As(bool, _same)  # (a saved value of any truth, a box's True or False)
STRIPPED = As(_same, lambda v: v.strip())
TEXT = As(lambda v: v or "", lambda v: (v or "").strip())  # (may be saved as None)
BLANKABLE = As(_num, _num)
SIZE = As(lambda v: _num(v) or None, _num)  # (0: blank)


def real(blank=0.0):
    """A number that can't be blank: emptied, it is `blank`."""
    return As(float, lambda v: float(v or blank))


def real_or(blank):
    """... and a saved 0 or None is `blank` too."""
    return As(lambda v: float(v or blank), lambda v: float(v or blank))


def int_or(blank):
    return As(int, lambda v: int(v or blank))


def opt_or(blank):
    """A blank-able number in the control, but never blank as saved."""
    return As(_num, lambda v: blank if v in (None, "") else float(v))


def one_of(values, other):
    """A choice's value; one it doesn't have (an older figure's, a font not here) is `other`."""
    values = tuple(values)
    return As(lambda v: v if v in values else other, _same)


def minutes():
    """A time in minutes typed as text ("" for none)."""
    def read(v):
        try:
            return float(v) if str(v).strip() else None
        except ValueError:
            return None
    return As(lambda v: "" if v in (None, "") else f"{float(v):g}", read)


# ------------------------------------------------------------ controls
@dataclass(frozen=True)
class Control:
    """What a row is set with.  kind: number, int, choice, multi, text, longtext, toggle, colour,
    code, or a named one with a component of its own (panel: one panel by letter; panels: some
    panels, as letters; xy: a pair of numbers; box: x0, x1, y0, y1; layer: one of the figure's
    layers; field: a field of the runs, with options "deriv" also its derivative; cmap: a colour
    ramp; levels: contour levels as typed; run: one of the figure's runs; runs: every run, one,
    or some; time: an output time of the layer's run; times: some of them, as typed; pset: a
    parcel set to take; pvar: a variable of the parcels).  options: a choice's {shown: saved} (a
    list: the same), or the name of a list made from the figure (OPTIONS_OF in the drawer:
    "layers:contour", "frames", "vectors", ...).  blank: a number, colour, run or time that can
    be left blank (placeholder: what blank means)."""
    kind: str
    options: object = ()
    start: float = None
    end: float = None
    step: float = None
    blank: bool = False  # (a number left blank: automatic, saved as None)
    placeholder: str = ""
    unit: str = ""


def number(start=None, end=None, step=None, blank=False, placeholder=""):
    return Control("number", start=start, end=end, step=step, blank=blank,
                   placeholder=placeholder or ("auto" if blank else ""))


def auto(start=None, end=None, step=None):
    """A number left blank for automatic."""
    return number(start, end, step, blank=True)


def integer(start=None, end=None, step=None):
    return Control("int", start=start, end=end, step=step)


def choice(options):
    return Control("choice", options=options)


def multi(options):
    return Control("multi", options=options)


def text(placeholder=""):
    return Control("text", placeholder=placeholder)


def longtext(placeholder=""):
    return Control("longtext", placeholder=placeholder)


TOGGLE = Control("toggle")
COLOUR = Control("colour")
CODE = Control("code")
FIELD = Control("field")  # (a field of the figure's runs: the viewer's field menu)
PANEL = Control("panel")
PANELS = Control("panels", placeholder="a, c")
XY = Control("xy", placeholder="1.02, 1")
BOX = Control("box")


COLOUR_AUTO = Control("colour", blank=True, placeholder="automatic")  # (saved "": automatic)
COLOUR_NONE = Control("colour", blank=True, placeholder="none")
CMAP = Control("cmap")
CONTOUR_LEVELS = Control("levels", placeholder="e.g. 10, 20 or -6:6:2")
FIELD_D = Control("field", options="deriv")  # (with its derivative: fields.deriv_name)
RUN = Control("run")
RUNS = Control("runs")
TIME = Control("time")
TIMES = Control("times", placeholder="30, 60, 90 or 30-120/15")
PSET = Control("pset")
PVAR = Control("pvar")


def run_or(placeholder):
    """One of the figure's runs, or blank (saved: none)."""
    return Control("run", blank=True, placeholder=placeholder)


def time_or(placeholder):
    """An output time, or blank (saved: none)."""
    return Control("time", blank=True, placeholder=placeholder)


def layer_of(types):
    """One of the figure's layers of these types (blank: the first that is on)."""
    return Control("layer", options="layers:" + ",".join(types))


# ------------------------------------------------------------ rows
@dataclass(frozen=True)
class Row:
    key: str
    label: str
    control: Control
    section: str
    kinds: tuple = ALL
    levels: tuple = ("figure",)
    default: object = KEEP  # (as saved; shown when a figure has none)
    as_: As = RAW
    help: str = ""
    when: str = ""  # (a condition it is offered under: WHEN)
    packed: bool = False  # (as_.read gives several keys of its block: {name: value})
    also: tuple = ()  # ((level, key, value), ...) written beside it at that level
    names: tuple = ()  # (the keys of its block a packed row holds)
    writer: str = ""  # (its block's own way of being written: "scene", where.WRITERS)
    types: tuple = ()  # (a layer row: the layer types it is a setting of)
    tag: str = ""  # (one of several rows of a key, for other layer types: its id's tail)
    fills: str = ""  # (what else it sets when it changes: FILLS in schema/fills.py)

    @property
    def id(self):
        """What names the row in the table: its key, or with several rows of a key (a layer
        setting that means another thing to another layer type), key~tag."""
        return f"{self.key}~{self.tag}" if self.tag else self.key

    @property
    def block(self):
        """(block, name) of a look or layer row: ("axes", "xstep"); ("", "coords");
        ("recipe", "z0")."""
        rest = self.key.partition(".")[2] if self.key.startswith(("look.", "layer.")) \
            else self.key
        block, _, name = rest.rpartition(".")
        return block, name

    def at(self, level):
        return level in self.levels


def look_rows(prefix, section, kinds, levels, *specs, **common):
    """Rows of look block `prefix` ("" for none): each spec (name, label, control[, default],
    {overrides})."""
    out = []
    for spec in specs:
        name, label, control, *more = spec
        over = more.pop() if more and isinstance(more[-1], dict) else {}
        kw = dict(dict(section=section, kinds=kinds, levels=levels), **common)
        if more:
            kw["default"] = more[0]
        kw.update(over)
        key = f"look.{prefix}.{name}" if prefix else f"look.{name}"
        out.append(Row(key, label, control, **kw))
    return out


# ------------------------------------------------------------ conditions (Row.when)
def _several_kinds(doc, where, ctx=None):
    return len({p["kind"] for p in doc.get("panels") or []}) > 1


def _t0_left(doc, where, ctx=None):  # (an older figure's minutes counted from: shown until 0)
    return float(((doc.get("style") or {}).get("time_label") or {}).get("t0_min") or 0.0) != 0.0


WHEN = {"several kinds": _several_kinds, "older t0": _t0_left}  # (and schema/layer.py's)


def when_ok(row, doc, where, ctx=None):
    """Whether row's condition holds at `where`.  A condition is a name in WHEN, or (a layer
    row's) clauses about the layer's other settings, as their rows show them: "clabel" (set),
    "!clabel", "style=streamlines|barbs", "style!=streamlines", "@xsec" (a WHEN name), joined
    by " and ", alternatives by " or "."""
    if not row.when:
        return True
    if row.when in WHEN:
        return WHEN[row.when](doc, where, ctx)
    return any(all(_clause(c, row, doc, where, ctx) for c in alt.split(" and "))
               for alt in row.when.split(" or "))


def _clause(c, row, doc, where, ctx):
    from . import where as W
    c = c.strip()
    if c.startswith("@"):
        return WHEN[c[1:]](doc, where, ctx)
    if c.startswith("!@"):
        return not WHEN[c[2:]](doc, where, ctx)
    neg = c.startswith("!")
    key, op, want = re.match(r"^!?([\w.]+)\s*(!?=)?\s*(.*)$", c).groups()
    if row.types:  # (a layer row: the layer's other setting, as its row shows it)
        other = row_for(f"layer.{key}", W.layer_type(W.layer_at(doc, where)))
        v = W.value(doc, other, where) if other is not None else \
            W.dig(W.layer_at(doc, where) or {}, key.split("."))
    else:  # (a look row's other look setting; the document's: its neighbour)
        near = f"{row.key.rpartition('.')[0]}.{key}".lstrip(".")
        other = BY_KEY.get(near) or (BY_KEY.get(f"look.{key}") if row.key.startswith("look.")
                                     else None)
        v = W.value(doc, other, where) if other is not None else None
    v = None if v is KEEP else v
    if op is None:
        return bool(v) != neg
    hit = str(v) in want.split("|") or (isinstance(v, bool) and str(v).lower() in want.split("|"))
    return hit == (op == "=")


RAW_KEYS = ("what", "t0_min")  # (a layer key a condition reads where some types have no row)


def when_problems(row):
    """What is wrong with row's condition: a name not in WHEN, a key with no row (for a test)."""
    if not row.when or row.when in WHEN:
        return []
    out = []
    for alt in row.when.split(" or "):
        for c in alt.split(" and "):
            name = c.strip().lstrip("!")
            if name.startswith("@"):
                out += [] if name[1:] in WHEN else [f"{c}: no such condition"]
                continue
            m = re.match(r"^[\w.]+", name)
            key = m.group(0) if m else ""
            if row.types:
                ok = key in RAW_KEYS or any(row_for(f"layer.{key}", t) for t in row.types)
            else:
                near = f"{row.key.rpartition('.')[0]}.{key}".lstrip(".")
                ok = near in BY_KEY or (row.key.startswith("look.") and f"look.{key}" in BY_KEY)
            out += [] if ok else [f"{c}: no row of {key!r}"]
    return out


def offered(row, doc, where, ctx=None):
    """Whether row is offered at `where` (a where.Where) in figure doc (ctx: what a condition
    about the runs needs: shell.Context)."""
    if not row.at(where.level):
        return False
    if where.kind is not None and where.level != "figure" and where.kind not in row.kinds:
        return False
    if row.types and where.layer is not None:
        from . import where as W
        if W.layer_type(W.layer_at(doc, where)) not in row.types:
            return False
    return when_ok(row, doc, where, ctx)


# ------------------------------------------------------------ the table
def _all_rows():
    from . import doc, layer, look
    return tuple(look.ROWS) + tuple(layer.ROWS) + tuple(doc.ROWS)


ROWS = _all_rows()
BY_KEY = {r.id: r for r in ROWS}
assert len(BY_KEY) == len(ROWS), "a key described twice"
_OF_TYPE = {(r.key, t): r for r in ROWS for t in r.types}
assert len(_OF_TYPE) == sum(len(r.types) for r in ROWS), "a layer type's key described twice"


def row(key):
    """The row of id `key` (a key, or key~tag)."""
    return BY_KEY[key]


def row_for(key, layer_type=None):
    """The row of `key` for a layer of type `layer_type` (None: of any, or a look row)."""
    if layer_type is not None and (key, layer_type) in _OF_TYPE:
        return _OF_TYPE[(key, layer_type)]
    return BY_KEY.get(key)


# What a new figure is not filled with (filled): a kind's own legend (it follows the figure's
# until set), the 3D scene's blocks (spec.scene3d_of makes them whole), the layer the contour key
# and the maximum / minimum name (the first that has one), a fixed box and an inset's offset.
_NOT_FILLED = ("look.contour_key.layer", "look.extremes.layer", "look.domain.box",
               "look.domain.off")
_FILLED_DOC = ("suptitle", "export.format", "export.dpi", "export.pad", "background",
               "code.on", "code.text")


def _filled_rows():
    out = {}
    for r in ROWS:
        look = r.key.startswith("look.")
        if r.default is KEEP or r.packed or r.key in _NOT_FILLED or not (
                look or r.key in _FILLED_DOC) or (look and (
                r.section == "Legend in the panel" or r.block[0].startswith("scene3d"))):
            continue
        out.setdefault(r.block, r)
    return tuple(out.values())


def filled(spec):
    """A new figure's spec (spec/base.py's form) with the settings it doesn't name at their
    defaults, in place, so a new figure says what it was made with."""
    for r in _filled_rows():
        block, key = r.block
        held = spec.setdefault(block, {}) if block else spec
        if key not in held:
            held[key] = r.as_.read(r.as_.show(r.default))
    return spec


def _fits(r, kinds, level, types):
    return set(r.kinds) & set(kinds) and (level is None or r.at(level)) and \
        (types is None or bool(set(r.types) & set(types)) == bool(types))


def sections(kinds=ALL, level=None, types=None):
    """The sections with a row for any of `kinds` (at `level`; of a layer of one of `types`;
    types (): no layer's), in table order."""
    out = []
    for r in ROWS:
        if r.section not in out and _fits(r, kinds, level, types):
            out.append(r.section)
    return out


def rows_of(section, kinds=ALL, level=None, types=None):
    """The rows of a section for any of `kinds`, at `level` (None: any), of `types` (sections)."""
    return [r for r in ROWS if r.section == section and _fits(r, kinds, level, types)]


def layer_rows(layer_type, kind=None, level=None):
    """The rows of a layer of `layer_type` (in `kind` panels, at `level`), in table order."""
    return [r for r in ROWS if layer_type in r.types and (kind is None or kind in r.kinds)
            and (level is None or r.at(level))]


def plain(text):
    """Words as searched: British spellings and a split "color bar" are the same."""
    text = str(text).lower().replace("colour", "color").replace("centre", "center")
    return text.replace("color bar", "colorbar")


def _rank(row, words):
    """How well a row answers the words (lower: better), or None when it hasn't them all: a
    label starting with each first, then a word of the label, then anywhere in it, then a word
    of the rest (section, help, key, layer types), then anywhere."""
    label = plain(row.label)
    rest = plain(" ".join((row.section, row.help, row.key, *row.types)))
    score = 0
    for w in words:
        if label.startswith(w):
            continue
        if any(part.startswith(w) for part in label.replace("(", " ").split()):
            score = max(score, 1)
        elif w in label:
            score = max(score, 2)
        elif any(part.startswith(w) for part in rest.replace(".", " ").split()):
            score = max(score, 3)
        elif w in rest:
            score = max(score, 4)
        else:
            return None
    return score


def search(words, kinds=ALL):
    """The rows with every one of `words` in their label, section, help or key (Find), best
    first (a tie: in table order)."""
    want = plain(words).split()
    if not want:
        return []
    ranked = []
    for n, r in enumerate(ROWS):
        if not set(r.kinds) & set(kinds):
            continue
        k = _rank(r, want)
        if k is not None:
            ranked.append((k, n, r))
    return [r for _, _, r in sorted(ranked, key=lambda x: x[:2])]
