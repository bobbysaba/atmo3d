"""Figure editor: placing things by clicking the preview.  A click in a panel of the
preview is turned into that panel's axis units (km, minutes, values; temperature and
pressure in a skew-T) and starts or finishes what the "Click to" list says: text, a
marker, an arrow, a line, a box, a circle, or the A–B of the cross-section (on a plan
view).  Dragging does the two clicks of those in one go, moves an annotation (its
text, marker or centre moves it all; an end moves that end), or sets the plan-view
area to the box dragged.

A mixin of the FigureEditor (figures/editor.py), and the clickable image."""

import math
from dataclasses import dataclass

import param
from panel.reactive import ReactiveHTML

from .choices import ANN_FIELDS
from .draw.base import ann_on
from .kinds import LINEAR
from .spec.doc import is_doc

PLACE = {"Click: nothing": "", "Click to add text": "text",
         "Click to add a marker": "marker", "Click twice: arrow (text, then tip)": "arrow",
         "Click twice: line": "line", "Click twice: box (corners)": "box",
         "Click twice: circle (centre, edge)": "circle",
         "Click twice: section A–B (plan views)": "section",
         "Drag: move an annotation": "move",
         "Drag a box: plan-view area": "area"}
TWO = ("arrow", "line", "box", "circle", "section")
DRAG = ("move", "area")  # (modes that need a drag, not a click)
GRAB = 0.06  # how near (a fraction of the panel) a drag must start to grab a point


class ClickImage(ReactiveHTML):
    """An image that reports where it is clicked or dragged, as fractions of its width
    and height from the upper left: click = [x, y, n], drag = [x0, y0, x1, y1, n] (n: a
    count, so the same spot twice is a new event).  band: show the box being dragged.
    marks: outlines drawn over it in the browser, {name: [left, right, top, bottom]
    fractions}, so showing what is selected redraws nothing (a dict: Panel 1.7.5 can't
    empty a list parameter that holds lists).  fit: the image's own box takes the height it
    is given, so a css of max-height:100% keeps the whole image in view.
    heads: the grid's row and column headers (ui/lines.heads: [node, label, a, b, axis, lit]),
    drawn in a margin above (columns: a, b their left and right) and to the left (rows: their
    top and bottom) of the image; clicking one sets head = [node, n].  dots: {name: [x, y]}
    fractions where a dot marks a panel with changes of its own.  zones: the parts a click opens
    (part_boxes: [left, right, top, bottom, words]); the one under the mouse is outlined, dashed,
    with its words as the tooltip (none while a drag or Click to is on: the shell sends none).
    src and css are set on the image by scripts, not in the template: a template that
    changes is rendered again, which could leave a second image (a stale preview)."""

    src = param.String(default="")
    css = param.String(default="")
    band = param.Boolean(default=False)
    click = param.List(default=[])
    drag = param.List(default=[])
    marks = param.Dict(default={})
    fit = param.Boolean(default=False)
    heads = param.List(default=[])
    head = param.List(default=[])
    dots = param.Dict(default={})
    zones = param.List(default=[])

    _template = (
        '<div id="wrap" style="position:relative;line-height:0">'
        '<img id="img" draggable="false" '
        'onmousedown="${script(\'down\')}" onmousemove="${script(\'move\')}" '
        'onmouseup="${script(\'up\')}" onmouseleave="${script(\'leave\')}"/>'
        '<div id="box" style="position:absolute;display:none;pointer-events:none;'
        'border:1px solid #22d3ee;background:rgba(34,211,238,0.12)"></div>'
        '<div id="over" style="position:absolute;left:0;top:0;pointer-events:none"></div>'
        '<div id="hov" style="position:absolute;display:none;pointer-events:none;'
        'box-sizing:border-box;border:1px dashed #22d3ee;border-radius:3px"></div>'
        '<div id="tabs" style="position:absolute;left:0;top:0"></div></div>')
    _scripts = {
        "render": """
            if (data.src) img.src = data.src;
            img.style.cssText = data.css;
            wrap.style.height = data.fit ? '100%' : '';
            self.heads();
            new ResizeObserver(() => { self.marks(); self.heads(); }).observe(img);
        """,
        "heads": """
            const cols = data.heads.some(h => h[4] === 'col');
            const rows = data.heads.some(h => h[4] === 'row');
            wrap.style.boxSizing = 'border-box';
            wrap.style.paddingTop = cols ? '26px' : '0';
            wrap.style.paddingLeft = rows ? '84px' : '0';
            tabs.replaceChildren(...data.heads.map(([node, label, a, b, axis, lit]) => {
                const d = document.createElement('div');
                const W = img.offsetWidth, H = img.offsetHeight;
                const L = img.offsetLeft, T = img.offsetTop;
                let css = 'position:absolute;box-sizing:border-box;cursor:pointer;'
                    + 'font:12px/20px sans-serif;text-align:center;overflow:hidden;'
                    + 'white-space:nowrap;text-overflow:ellipsis;border-radius:6px;'
                    + 'padding:0 6px;user-select:none;'
                    + (lit ? 'background:rgba(34,211,238,.25);color:#a5f3fc;'
                              + 'border:1px solid #22d3ee;'
                           : 'background:rgba(148,163,184,.12);color:#cbd5e1;'
                              + 'border:1px solid rgba(148,163,184,.35);');
                if (axis === 'col')
                    css += 'left:' + (L + a * W + 2) + 'px;top:' + (T - 24) + 'px;width:'
                        + Math.max(20, (b - a) * W - 4) + 'px;height:22px;';
                else
                    css += 'left:' + Math.max(0, L - 82) + 'px;width:78px;top:'
                        + (T + ((a + b) / 2) * H - 11) + 'px;height:22px;';
                d.style.cssText = css;
                d.textContent = label;
                d.title = (axis === 'col' ? 'This column' : 'This row') + ': ' + label
                    + ' (click: its settings, written to each of its panels)';
                d.onclick = () => {
                    state.h = (state.h || 0) + 1;
                    data.head = [node, state.h];
                };
                return d;
            }));
            self.marks();
        """,
        "dots": "self.marks();",
        "fit": "wrap.style.height = data.fit ? '100%' : '';",
        "src": "if (data.src) img.src = data.src;",
        "css": "img.style.cssText = data.css;",
        "marks": """
            const dots = Object.values(data.dots).map(([x, y]) => {
                const d = document.createElement('div');
                d.style.cssText = 'position:absolute;width:9px;height:9px;border-radius:50%;'
                    + 'background:#22d3ee;box-shadow:0 0 0 2px rgba(0,0,0,.55);'
                    + 'left:' + (img.offsetLeft + x * img.offsetWidth - 12) + 'px;'
                    + 'top:' + (img.offsetTop + y * img.offsetHeight + 3) + 'px';
                return d;
            });
            over.replaceChildren(...dots, ...Object.values(data.marks).map(([l, r, t, b]) => {
                const d = document.createElement('div');
                d.style.cssText = 'position:absolute;box-sizing:border-box;'
                    + 'border:2px solid #22d3ee;box-shadow:0 0 0 1px rgba(0,0,0,.45);'
                    + 'left:' + (img.offsetLeft + l * img.offsetWidth) + 'px;'
                    + 'top:' + (img.offsetTop + t * img.offsetHeight) + 'px;'
                    + 'width:' + ((r - l) * img.offsetWidth) + 'px;'
                    + 'height:' + ((b - t) * img.offsetHeight) + 'px';
                return d;
            }));
        """,
        "down": """
            const e = state.event;
            if (e.button !== 0) return;
            e.preventDefault();
            state.d = [e.clientX, e.clientY];
        """,
        "zones": "hov.style.display = 'none'; img.title = '';",
        "move": """
            const e = state.event;
            if (!state.d) {
                const r = img.getBoundingClientRect();
                if (!r.width || !r.height) return;
                const fx = (e.clientX - r.left) / r.width, fy = (e.clientY - r.top) / r.height;
                const z = data.zones.find(q => q[0] <= fx && fx <= q[1] && q[2] <= fy
                                          && fy <= q[3]);
                if (!z) {
                    hov.style.display = 'none';
                    img.title = '';
                    return;
                }
                hov.style.left = (img.offsetLeft + z[0] * img.offsetWidth) + 'px';
                hov.style.top = (img.offsetTop + z[2] * img.offsetHeight) + 'px';
                hov.style.width = ((z[1] - z[0]) * img.offsetWidth) + 'px';
                hov.style.height = ((z[3] - z[2]) * img.offsetHeight) + 'px';
                hov.style.display = 'block';
                img.title = z[4];
                return;
            }
            hov.style.display = 'none';
            if (!data.band) return;
            const w = wrap.getBoundingClientRect();
            const x0 = Math.min(state.d[0], e.clientX), y0 = Math.min(state.d[1], e.clientY);
            box.style.left = (x0 - w.left) + 'px';
            box.style.top = (y0 - w.top) + 'px';
            box.style.width = Math.abs(e.clientX - state.d[0]) + 'px';
            box.style.height = Math.abs(e.clientY - state.d[1]) + 'px';
            box.style.display = 'block';
        """,
        "up": """
            const e = state.event, r = img.getBoundingClientRect();
            const d = state.d;
            state.d = null;
            box.style.display = 'none';
            if (!d || !r.width || !r.height) return;
            state.n = (state.n || 0) + 1;
            const fx = (x) => (x - r.left) / r.width, fy = (y) => (y - r.top) / r.height;
            if (Math.hypot(e.clientX - d[0], e.clientY - d[1]) < 4)
                data.click = [fx(e.clientX), fy(e.clientY), state.n];
            else
                data.drag = [fx(d[0]), fy(d[1]), fx(e.clientX), fy(e.clientY), state.n];
        """,
        "leave": """
            state.d = null;
            box.style.display = 'none';
            hov.style.display = 'none';
        """}


def _saved_box(fig, spec, size_px, dpi):
    """(left, top, width, height), inches in fig, of the image just saved from it."""
    tb = getattr(fig, "_cv_tight", None)
    W, H = size_px[0] / dpi, size_px[1] / dpi
    if tb is None:
        return 0.0, float(fig.get_size_inches()[1]), W, H
    pad = float(spec.get("export", {}).get("pad", 0.05))
    # (exact width: only the height is trimmed)
    return 0.0 if spec.get("export", {}).get("exact_width") else tb.x0 - pad, tb.y1 + pad, W, H


def panel_boxes(fig, spec, size_px, dpi):
    """{panel: [left, right, top, bottom]}, fractions of the image just saved from fig, of
    every panel drawn, whatever its axes, and of its zoom insets (by their keys, negative), ahead
    of the panels: they are what a click there is on."""
    x0, y1, W, H = _saved_box(fig, spec, size_px, dpi)
    out = {}
    drawn = (getattr(fig, "_cv_axes", None) or {}).items()
    inside = [(k, cax) for _, ax in drawn for k, cax in getattr(ax, "_cv_insets", {}).items()]
    for i, ax in [*inside, *drawn]:
        boxes = [a.get_window_extent() for a in (ax, *getattr(ax, "_cv_parts", ()))]
        f = fig.dpi
        out[i] = [(min(e.x0 for e in boxes) / f - x0) / W, (max(e.x1 for e in boxes) / f - x0) / W,
                  (y1 - max(e.y1 for e in boxes) / f) / H, (y1 - min(e.y0 for e in boxes) / f) / H]
    return out


@dataclass(frozen=True)
class Part:
    """A part of the preview a click opens the settings of: its box ([left, right, top, bottom]
    fractions of the image, as panel_boxes'), the panel it is of (None: the figure's), what it is
    (PART_WORDS), and of a colorbar the panels it serves (the first: whose colours it shows) and
    the colorbar mode it was drawn by (shared, row, col, each, figure)."""
    box: tuple
    panel: object
    part: str
    panels: tuple = ()
    mode: str = ""


PART_WORDS = {"title": "the panel's title", "xlabel": "the x label", "ylabel": "the y label",
              "rowlabel": "the row label", "letters": "the panel letter",
              "time_label": "the time label", "run_label": "the run name",
              "z_label": "the height label", "legend": "the legend",
              "own legend": "the panel's legend", "figure legend": "the figure's legend",
              "suptitle": "the figure title", "colorbar": "the colorbar",
              "own colorbar": "the panel's colorbar"}
PAD_PX = 3  # (how near a part's drawn box, in pixels of the image, a click still hits it)


def _shown(t):
    """Whether artist t is drawn and, a text, says something."""
    if t is None or not t.get_visible():
        return False
    get = getattr(t, "get_text", None)
    return not callable(get) or bool(str(get()).strip())


def _figures(fig):
    """fig and its subfigures, all the way down."""
    out = [fig]
    for sf in getattr(fig, "subfigs", ()):
        out += _figures(sf)
    return out


def _parts_of(fig):
    """[(artist, tight, panel, part, panels, mode)] of figure fig that a click opens (tight: its
    box with its ticks and labels, a colorbar's)."""
    found = []
    for pid, ax in (getattr(fig, "_cv_axes", None) or {}).items():
        tags = list(getattr(ax, "_cv_tags", ()))
        taken = {id(t) for _, t in tags}
        found += [(t, False, pid, name, (), "") for name, t in tags]
        for t in (ax.title, getattr(ax, "_left_title", None), getattr(ax, "_right_title", None)):
            if t is not None and id(t) not in taken:
                found.append((t, False, pid, "title", (), ""))
        if not getattr(ax, "_cv_hodo", False) and ax.name != "3d":
            found += [(ax.xaxis.label, False, pid, "xlabel", (), ""),
                      (ax.yaxis.label, False, pid, "ylabel", (), "")]
        found.append((getattr(ax, "_cv_rowlabel", None), False, pid, "rowlabel", (), ""))
        for a in (ax, *getattr(ax, "_cv_more", ())):
            leg = a.get_legend()
            if leg is not None:
                part = "legend" if getattr(leg, "_cv_block", False) else "own legend"
                found.append((leg, False, pid, part, (), ""))
        own = getattr(ax, "_cv_own_bar", None)
        if own is not None:
            found.append((own, True, pid, "own colorbar", (pid,), "own"))
    for sf in _figures(fig):
        found.append((getattr(sf, "_suptitle", None), False, None, "suptitle", (), ""))
        found += [(leg, False, None, "figure legend", (), "") for leg in sf.legends]
    for cax, ids, mode in getattr(fig, "_cv_bars", ()):
        found.append((cax, True, ids[0] if ids else None, "colorbar", tuple(ids), mode))
    return found


def watch_parts(fig):
    """Record, each time fig is drawn, where its parts (_parts_of) are in the picture drawn
    (fig._cv_parts_px: [(x0, x1, y0, y1 pixels from the lower left, panel, part, panels, mode)]):
    a text's place is laid out at the dpi it is drawn at, so it is read in the draw itself, and in
    savefig's last draw (of a trimmed box: bbox_inches "tight") the pixels are the image's."""
    def seen(event):
        out = []
        r = event.renderer
        for art, tight, pid, part, ids, mode in _parts_of(fig):
            if not _shown(art):
                continue
            try:
                e = art.get_tightbbox(r) if tight else art.get_window_extent(r)
            except Exception:  # noqa: BLE001  (an artist not laid out: not clickable)
                continue
            if e is not None and e.width > 0 and e.height > 0:
                out.append((e.x0, e.x1, e.y0, e.y1, pid, part, ids, mode))
        fig._cv_parts_px = out

    fig.canvas.mpl_connect("draw_event", seen)


def part_boxes(fig, spec, size_px, dpi):
    """[Part] of the preview just saved from fig (watch_parts must watch it first): each panel's
    title, axis labels, row label, panel labels (letter, time, run, height), legend and own
    colorbar, the figure's title and legend, and the colorbars (fig._cv_bars:
    draw/layers.note_bar), smallest first so a click on one inside another (a legend in a
    colorbar's box) is on the small one.  spec and dpi: as panel_boxes' (not needed: the pixels
    are the image's)."""
    W, H = max(size_px[0], 1), max(size_px[1], 1)
    px, py = PAD_PX / W, PAD_PX / H
    out = [Part((x0 / W - px, x1 / W + px, 1 - y1 / H - py, 1 - y0 / H + py), pid, part, ids,
                mode)
           for x0, x1, y0, y1, pid, part, ids, mode in getattr(fig, "_cv_parts_px", ())]
    out.sort(key=lambda q: (q.box[1] - q.box[0]) * (q.box[3] - q.box[2]))
    return out


def part_at(parts, fx, fy):
    """The first of parts (part_boxes) holding a point of the preview, or None."""
    return next((q for q in parts or () if q.box[0] <= fx <= q.box[1]
                 and q.box[2] <= fy <= q.box[3]), None)


def place_map(fig, spec, size_px, dpi):
    """{data key: (left, right, top, bottom) as fractions of the saved image, xlim,
    ylim, skew} of the panels whose axes clicks map onto (plain linear axes, and
    skew-T panels: skew = (skew, bottom pressure), else None), for the preview just
    saved from fig (its trimmed box, if any, recorded by watch_tight).  Of a document: by
    panel id."""
    if is_doc(spec):
        kinds = {p["id"]: p["kind"] for p in spec.get("panels") or []}
        kind_of = kinds.get
    else:
        kinds = {k: part["kind"] for k, part in enumerate(spec.get("parts") or [spec])}
        kind_of = lambda i: kinds.get(int(i) // 1000 if spec.get("kind") == "combo" else 0)  # noqa: E731
    x0, y1, W, H = _saved_box(fig, spec, size_px, dpi)
    out = {}
    for i, ax in (getattr(fig, "_cv_axes", None) or {}).items():
        if kind_of(i) not in LINEAR:
            continue
        skew = getattr(ax, "_cv_skew", None)
        if getattr(ax, "_cv_hodo", False) or ax.get_xscale() != "linear" or (
                ax.get_yscale() != "linear" and skew is None):
            continue
        e = ax.get_window_extent()
        f = fig.dpi
        out[i] = ((e.x0 / f - x0) / W, (e.x1 / f - x0) / W, (y1 - e.y1 / f) / H,
                  (y1 - e.y0 / f) / H, tuple(ax.get_xlim()), tuple(ax.get_ylim()),
                  None if skew is None else tuple(float(v) for v in skew))
    return out


def to_data(b, u, w):
    """Axis units of the point at fractions (u from the left, w from the bottom) of
    panel box b (a place_map entry): x, y, or in a skew-T temperature and pressure."""
    xl, yl, skew = b[4], b[5], b[6]
    x = xl[0] + u * (xl[1] - xl[0])
    if skew is None:
        return x, yl[0] + w * (yl[1] - yl[0])
    p = math.exp(math.log(yl[0]) + w * (math.log(yl[1]) - math.log(yl[0])))
    return x - skew[0] * math.log(skew[1] / p), p


def to_frac(b, x, y):
    """The inverse of to_data: fractions (u, w) of the panel at axis units x, y."""
    xl, yl, skew = b[4], b[5], b[6]
    if skew is not None:
        y = max(float(y), 1e-6)
        x = x + skew[0] * math.log(skew[1] / y)
        w = (math.log(yl[0]) - math.log(y)) / (math.log(yl[0]) - math.log(yl[1]))
    else:
        w = (y - yl[0]) / ((yl[1] - yl[0]) or 1e-9)
    return (x - xl[0]) / ((xl[1] - xl[0]) or 1e-9), w


def locate(place, fx, fy):
    """(key, its place_map entry, u, w) of the panel of `place` holding a point of the preview
    (u, w: fractions of the panel from the left and bottom), or None."""
    hit = next(((i, b) for i, b in place.items()
                if b[0] <= fx <= b[1] and b[2] <= fy <= b[3]), None)
    if hit is None:
        return None
    i, b = hit
    return i, b, (fx - b[0]) / max(b[1] - b[0], 1e-9), (b[3] - fy) / max(b[3] - b[2], 1e-9)


def dragged_to(b, u0, w0, f0, f1):
    """The panel fractions (u, w) a drag from (u0, w0) in panel box b ends at, from its two
    points in the preview, f0 and f1 (fractions of the image, x then y)."""
    return (u0 + (f1[0] - f0[0]) / max(b[1] - b[0], 1e-9),
            w0 - (f1[1] - f0[1]) / max(b[3] - b[2], 1e-9))


def placed_item(mode, panel, first, x, y):
    """The annotation of a click-placing mode finishing at (x, y); first: the (x, y) of the first
    click of a two-point one."""
    a = dict(kind=mode, panel=panel, coords="data", x=x, y=y, x2=x, y2=y,
             text="A" if mode == "text" else "", color="#000000",
             size=10.0 if mode != "marker" else 8.0, lw=1.5, ls="-", r=1.0)
    if first is not None:
        x1, y1 = first
        a.update(x=x1, y=y1, x2=x, y2=y)
        if mode == "circle":
            a.update(x2=x1, y2=y1, r=round(((x - x1) ** 2 + (y - y1) ** 2) ** 0.5, 2))
    return a


def grab_annotation(anns, panel, b, start):
    """What a drag starting at `start` (fractions of panel b) takes of annotations `anns`: (its
    place in anns, its grip), or None (nothing of panel `panel` near enough)."""
    best = None
    for n, a in enumerate(anns):
        if not ann_on(a, panel):
            continue
        for grip, (u, w) in _grips(a, b, start).items():
            dist = math.hypot(u - start[0], w - start[1])
            if dist < GRAB and (best is None or dist < best[0]):
                best = (dist, n, grip)
    return None if best is None else best[1:]


def axis_digits(lim):
    """Decimals that place a point on axis range lim to about a thousandth of it (2 at least)."""
    span = abs(float(lim[1]) - float(lim[0]))
    return max(2, 3 - math.floor(math.log10(span))) if span > 0 else 2


def moved_annotation(a, b, start, end, grip, digits=(2, 2)):
    """The new values of annotation a's keys when grabbed at grip and dragged from `start` to
    `end` (fractions of panel b).  digits: the decimals of its x and y in axis units."""
    du, dw = end[0] - start[0], end[1] - start[1]
    axes = a.get("coords") == "axes"
    new = {}
    pts = {"all": [("x", "y"), ("x2", "y2")], "1": [("x", "y")], "2": [("x2", "y2")]}
    for kx, ky in pts[grip if grip in pts else "all"]:
        if kx not in a and ky not in a:
            continue
        x, y = float(a.get(kx, a.get("x", 0.0))), float(a.get(ky, a.get("y", 0.0)))
        if a["kind"] == "vline":  # (moves sideways only; hline: up and down)
            y = to_data(b, *start)[1]
        u, w = (x, y) if axes else to_frac(b, x, y)
        x, y = (u + du, w + dw) if axes else to_data(b, u + du, w + dw)
        if kx in a:
            new[kx] = round(x, 4 if axes else digits[0])
        if ky in a and a["kind"] != "vline":
            new[ky] = round(y, 4 if axes else digits[1])
    return new


def watch_tight(fig):
    """Record the trimmed box (inches) savefig computes for fig (fig._cv_tight)."""
    orig = fig.get_tightbbox

    def spy(*a, **kw):
        b = orig(*a, **kw)
        fig._cv_tight = b
        return b

    fig.get_tightbbox = spy


def _grips(a, b, start):
    """{grip: (u, w) panel fractions} of annotation a: "all" (its text, marker, centre
    or middle: moves it all), "1" and "2" (the ends of an arrow, line or box)."""
    use = ANN_FIELDS.get(a.get("kind", "text"), ())
    axes = a.get("coords") == "axes"

    def frac(x, y):
        return (float(x), float(y)) if axes else to_frac(b, float(x), float(y))

    kind = a.get("kind")
    if kind == "legend":  # (in the legend, not on the panel)
        return {}
    if kind == "vline":  # (grabbed anywhere along it)
        return {"all": (to_frac(b, float(a["x"]), to_data(b, *start)[1])[0], start[1])}
    if kind == "hline":
        return {"all": (start[0], to_frac(b, to_data(b, *start)[0], float(a["y"]))[1])}
    p1 = frac(a.get("x", 0.0), a.get("y", 0.0))
    if "x2" not in use:
        return {"all": p1}
    p2 = frac(a.get("x2", 0.0), a.get("y2", 0.0))
    return {"1": p1, "2": p2, "all": (0.5 * (p1[0] + p2[0]), 0.5 * (p1[1] + p2[1]))}
