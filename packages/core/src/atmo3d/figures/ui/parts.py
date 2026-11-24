"""Small pieces the figure's drawers and dialogs are made of: a hint, a heading, a button, a
folding section, number boxes and a checkbox, widgets in a grid of columns."""

import html
import re

import panel as pn

from ...theme import GRID, PANEL, RAISED, TEXT
from ...viewer.numinput import FloatInput

SECTION = dict(sizing_mode="stretch_width", header_background=RAISED,
               active_header_background=RAISED, header_color=TEXT, margin=(4, 0),
               styles={"background": PANEL, "border": f"1px solid {GRID}",
                       "border-radius": "8px"})


def note(text):
    return pn.pane.HTML(f'<div class="cv-hint">{text}</div>', margin=(2, 4),
                        sizing_mode="stretch_width")


def head(text):
    return pn.pane.HTML(f"<b>{html.escape(text)}</b>", margin=(10, 4, 0, 4))


def button(name, on_click, tip="", primary=False):
    b = pn.widgets.Button(name=name, height=30, margin=(4, 4), description=tip or None,
                          button_type="primary" if primary else "light",
                          button_style="outline")
    b.on_click(lambda e: on_click())
    return b


def _f(name, value, width=90, **kw):
    return FloatInput(name=name, value=value, width=width, **kw)


def _auto(name, value=None, **kw):
    """A number that may be left blank (automatic)."""
    v = None if value in (None, "", 0) else float(value)
    return FloatInput(name=name, value=v, placeholder="auto", width=90, **kw)


def _chk(name, value):
    return pn.widgets.Checkbox(name=name, value=bool(value), margin=(5, 6, 12, 6))


def _grid(*objs, n=None):
    """Widgets in n equal columns (3 unless it says) (a CSS grid), each filling its cell; (widget, k)
    spans k columns.  Everything sits on the cell's bottom line, so checkboxes and
    buttons line up with the input boxes beside them; hidden widgets leave no gap."""
    n = 3 if n is None else n
    items = []
    for o in objs:
        o, span = o if isinstance(o, tuple) else (o, 1)
        span = min(span, n)
        o.width = None
        o.sizing_mode = "stretch_width"
        st = {"align-self": "end"}
        if span > 1:
            st["grid-column"] = f"span {span}"
        o.styles = dict(o.styles or {}, **st)
        if isinstance(o, pn.widgets.Checkbox):
            o.margin = (5, 6, 12, 6)
        items.append(o)
    # (inside a plain column: bokeh hides with a ":host {display: none}" stylesheet,
    # which the grid's inline display would override, so .visible = False did nothing)
    return pn.Column(_cells(items, n), sizing_mode="stretch_width", margin=0)


def _cells(objs, n):
    """A column laid out as n equal grid columns, holding those of objs that are shown (a
    hidden one is not sent to the browser).  Panel puts an invisible scroll button among a
    Column's children, and a widget shown later lands after it: in a grid the button takes
    a cell, which left a hole in the options, so it is taken out of the layout."""
    grid = pn.Column(*objs, sizing_mode="stretch_width", margin=0,
                     stylesheets=[".scroll-button { display: none !important; }"], styles={
                         "display": "grid", "column-gap": "2px",
                         "grid-template-columns": f"repeat({n}, minmax(0, 1fr))"})
    _follow_shown(grid, objs)
    return grid


def _keep_shown(col, objs):
    """col holds those of objs that are visible: a hidden one is left out (its widgets
    are not sent to the browser) until it is shown again."""
    keep = [o for o in objs if o.visible]
    if [id(o) for o in keep] != [id(o) for o in col.objects]:
        col.objects = keep


def _follow_shown(col, objs):
    """_keep_shown(col, objs) now and whenever one of objs is shown or hidden."""
    objs = list(objs)
    for o in objs:
        o.param.watch(lambda e: _keep_shown(col, objs), "visible")
    _keep_shown(col, objs)


HINT_SHORT = 120  # (characters of a hint shown whole; a longer one folds after its first sentence)


def _hint_html(text):
    """A hint's HTML: a long one is its first sentence, which opens to show the rest (in
    the browser alone: no widgets, no round trip)."""
    if len(re.sub(r"<[^>]+>", "", text)) > HINT_SHORT:
        depth = 0  # (not inside a tag such as <code>a. b</code>)
        for m in re.finditer(r"<(/?)[a-zA-Z][^>]*>|(?<!e\.g)(?<!i\.e)\.\s+(?=\S)", text):
            if m.group(0).startswith("<"):
                depth += -1 if m.group(1) else 1
            elif depth == 0:
                return (f'<details class="cv-hint"><summary>{text[:m.start() + 1]}</summary>'
                        f'{text[m.end():]}</details>')
    return f'<div class="cv-hint">{text}</div>'


def _hint(text, margin=(4, 4, 2, 4)):
    return pn.pane.HTML(_hint_html(text), margin=margin, sizing_mode="stretch_width")
