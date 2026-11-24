"""Phase 6 (docs-dev/figures-ui-plan.md; mockup C): a click on a part of the preview (a title,
an axis label, a panel label, a legend, a colorbar) opens its setting.  The parts map
(click.part_boxes, from where the drawing put each), what each part opens (ui/clicked.py), the
shell's click (Click to first, then a part, then the panel) and the hover outlines' zones."""
import html
import io
import struct

import matplotlib
import panel as pn
import pytest

from conftest import fresh_shell

from atmo3d.figures import schema as S
from atmo3d.figures.click import Part, part_at, part_boxes, watch_parts, watch_tight
from atmo3d.figures.schema import where as W
from atmo3d.figures.schema.where import Where
from atmo3d.figures.ui import clicked

matplotlib.use("Agg")


# ------------------------------------------------------------------ the parts map
def _drawn(watch=True):
    """A plain figure of two panels as the drawing marks them (draw/: _cv_axes, _cv_tags, a block
    legend, a shared colorbar), saved trimmed at another dpi than its own, as the preview is."""
    import matplotlib.pyplot as plt
    import numpy as np
    from atmo3d.figures.draw.base import _anchored
    from atmo3d.figures.draw.layers import note_bar
    fig, axs = plt.subplots(1, 2, figsize=(6, 3))
    for i, ax in enumerate(axs):
        m = ax.pcolormesh(np.arange(25.0).reshape(5, 5))
        ax.plot([0, 4], [0, 4], label="a")
        ax.set_title(f"T{i}")
        ax.set_xlabel("x (km)")
        ax.set_ylabel("y (km)")
        ax.__dict__.setdefault("_cv_tags", []).append(("letters", _anchored(ax, "(a)", {}, 10)))
    axs[0].legend()._cv_block = True
    c = fig.colorbar(m, ax=list(axs), location="bottom", shrink=0.8)
    note_bar(fig, c.ax, [0, 1], "shared")
    fig.suptitle("A figure")
    fig._cv_axes = {0: axs[0], 1: axs[1]}
    watch_tight(fig)
    if watch:
        watch_parts(fig)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=80, bbox_inches="tight", pad_inches=0.05)
    wh = struct.unpack(">II", buf.getvalue()[16:24])
    return fig, axs, wh


def _centre(fig, art, wh):
    """Where artist art's middle is in the image saved (fractions from the upper left)."""
    e = art.get_window_extent()  # (at the figure's own dpi, after the save: so its share)
    f, tb = fig.dpi, fig._cv_tight
    x0, y1 = tb.x0 - 0.05, tb.y1 + 0.05
    return (((e.x0 + e.x1) / 2 / f - x0) / (wh[0] / 80),
            (y1 - (e.y0 + e.y1) / 2 / f) / (wh[1] / 80))


def test_the_parts_map_holds_each_drawn_part():
    fig, axs, wh = _drawn()
    parts = part_boxes(fig, {}, wh, 80)
    got = {(q.part, q.panel) for q in parts}
    assert {("title", 0), ("title", 1), ("xlabel", 0), ("ylabel", 1), ("letters", 0),
            ("legend", 0), ("suptitle", None), ("colorbar", 0)} <= got
    bar = next(q for q in parts if q.part == "colorbar")
    assert bar.panels == (0, 1) and bar.mode == "shared"
    areas = [(q.box[1] - q.box[0]) * (q.box[3] - q.box[2]) for q in parts]
    assert areas == sorted(areas)  # (small first: they win over what holds them)
    for ax, k in zip(axs, (0, 1)):  # (a click on a title's middle is on it)
        hit = part_at(parts, *_centre(fig, ax.title, wh))
        assert (hit.part, hit.panel) == ("title", k)
    assert part_at(parts, 0.5, 0.55) is None  # (inside a panel: no part, the panel is picked)


def test_no_parts_unless_watched():
    fig, _, wh = _drawn(watch=False)
    assert part_boxes(fig, {}, wh, 80) == []


# ------------------------------------------------------------------ what a part opens
def _box():
    return (0.0, 1.0, 0.0, 1.0)


def test_a_panels_own_legend_and_colorbar_are_its_kinds():
    doc = {"version": 3, "panels": [{"id": 0, "kind": "line", "cell": [0, 0]},
                                    {"id": 1, "kind": "joint", "cell": [0, 1]}]}
    t = clicked.target(doc, Part(_box(), 0, "own legend"))
    assert t.row.key == "look.ts.legend" and t.where == Where("panel", "line", 0)
    t = clicked.target(doc, Part(_box(), 1, "own colorbar", (1,), "own"))
    assert t.row.key == "look.joint.cbar_label" and t.where == Where("panel", "joint", 1)
    t = clicked.target(doc, Part(_box(), None, "suptitle"))
    assert t.row.key == "suptitle" and t.where.level == "figure"
    assert clicked.target(doc, Part(_box(), 7, "title")) is None  # (a panel gone)


# ------------------------------------------------------------------ in the shell
@pytest.fixture
def shell(shell_viewer):
    return fresh_shell(shell_viewer, min(4, len(shell_viewer.run.times) - 1))


def _part(shell, part, panel=None):
    hit = next((q for q in shell._parts if q.part == part
                and (panel is None or q.panel == panel)), None)
    assert hit is not None, f"no {part} drawn: {[(q.part, q.panel) for q in shell._parts]}"
    return hit


def _click(shell, q, n=1):
    shell.image.click = [0.5 * (q.box[0] + q.box[1]), 0.5 * (q.box[2] + q.box[3]), n]


def test_clicking_a_panel_title_opens_its_title(shell):
    pid = shell.doc["panels"][1]["id"]
    shell.edit(lambda d: d["panels"][1].update(title="Clicked one"))
    shell.request(force=True, delay=False)
    _click(shell, _part(shell, "title", pid))
    assert shell.node == f"panel:{pid}" and shell.frame.tool == "layout"
    assert "Clicked the panel's title" in html.unescape(shell.frame.found.object)
    assert "<b>Title</b>" in shell.frame.found.object


def test_clicking_an_axis_label_opens_it_at_the_panel(shell):
    q = _part(shell, "xlabel")
    t = clicked.target(shell.doc, q)
    assert t.row.key == "look.axes.xlabel" and t.where.level == "panel"
    _click(shell, q)
    assert shell.node == f"panel:{q.panel}" and shell.frame.tool == "look"
    assert "x label" in shell.frame.found.object


def test_clicking_the_shared_colorbar_opens_all_colorbars_with_links(shell):
    q = _part(shell, "colorbar")
    assert len(q.panels) == len(shell.doc["panels"]) and q.mode == "shared"
    _click(shell, q)
    assert shell.node == "figure" and shell.frame.tool == "look"
    assert "<b>Colorbars</b>" in shell.frame.found.object
    said = " ".join(str(o.object) for o in shell.frame.links.select(pn.pane.HTML))
    assert "Shared by panels a, b" in said and "follow panel a's fill" in said
    links = {b.name: b for b in shell.frame.links.select(pn.widgets.Button)}
    assert set(links) == {"Jump to: Panel a's fill", "Jump to: Panel a's colorbar"}
    links["Jump to: Panel a's fill"].clicks += 1
    j, _ = clicked.first_fill(shell.doc, q.panels[0])
    assert shell.node == f"layer:{q.panels[0]}:{j}" and shell.frame.tool == "layers"
    assert "Jumped to: <b>Colormap</b>" in shell.frame.found.object
    assert not shell.frame.links.objects  # (the note was the colorbar's)


def test_a_bar_per_row_opens_its_row(shell):
    ctx = shell.frame.host.ctx
    shell.edit(lambda d: W.write(d, S.BY_KEY["look.colorbar.mode"], Where(), "row", ctx))
    shell.request(force=True, delay=False)
    bars = [q for q in shell._parts if q.part == "colorbar"]
    assert len(bars) == 2 and all(q.mode == "row" for q in bars)  # (the 2 x 3 grid's rows)
    _click(shell, bars[-1])
    assert shell.node.startswith("row:") and shell.frame.tool == "look"
    assert "Colorbar label" in shell.frame.found.object
    links = {b.name for b in shell.frame.links.select(pn.widgets.Button)}
    assert "Jump to: All colorbars" in links


def test_click_to_comes_before_a_part(shell):
    q = _part(shell, "colorbar")
    n = len(shell.doc.get("annotations") or [])
    shell.placing.mode.value = "text"
    assert shell.image.zones == []  # (no outlines while clicks place)
    _click(shell, q)
    assert len(shell.doc.get("annotations") or []) in (n, n + 1)  # (on a panel or not)
    assert "Clicked" not in (shell.frame.found.object or "")
    shell.placing.mode.value = ""
    assert shell.image.zones and all(len(z) == 5 for z in shell.image.zones)
    assert any("click for its settings" in z[4] for z in shell.image.zones)
