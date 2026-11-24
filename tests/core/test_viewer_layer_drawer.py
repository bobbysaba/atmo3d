"""One layer component (figures/ui/layer.py, docs-dev/figures-ui-plan.md Phase 5.2): the generic
drawer on one viewer layer dict.  Every row of every viewer layer gets a control; a change is
written to the layer itself and said with the keys it changed; the level slider follows the
level mode (heights, model levels, a radar's sweeps); the figure's drawer is unchanged.  No
viewer: a made-up run and the fields of test_viewer_layers."""

from types import SimpleNamespace

import numpy as np
import param
import pytest

from atmo3d.figures.schema import viewer as V
from atmo3d.figures.ui import drawer as D, layer as L, samples

from test_viewer_layers import FakeFields


class Fields(FakeFields):
    """The fields, with the groups the field menu lists."""

    def groups(self, ndim=None):
        return {"": {n: n for n, d in self.defs.items() if ndim is None or d.ndim == ndim}}


def _run(grid=True, terrain=False):
    z = np.array([0.1, 0.5, 1.0, 2.0, 4.0, 8.0, 12.0])
    return SimpleNamespace(
        grid=grid, terrain=terrain, z=z, nk=len(z), ztop=15.0, nsweeps=9, storm_relative=True,
        level_weights=lambda zkm: (int(np.searchsorted(z, zkm, side="right")) - 1, 0, 0.0),
        terrain_height=lambda: np.full((2, 2), 0.5))


def _drawer(role, kind="plan", lay=None, run=None, **kw):
    said = []
    lay = V.new(role, kind, field="dbz") if lay is None and role != "vectors" else \
        (lay if lay is not None else V.new(role, kind))
    d = L.LayerDrawer(lay, role, kind, run=run or _run(), fields=Fields(),
                      on_change=lambda keys: said.append(set(keys)),
                      runs=lambda: {"other": "/runs/other"},
                      times=lambda rid: {"10 min": 600.0, "20 min": 1200.0}, **kw)
    return d, said


def _slide(ctl, v):
    w = ctl.widget
    w.value = v
    with param.edit_constant(w):
        w.value_throttled = v


@pytest.mark.parametrize("role,kind", sorted(V.LAYOUT))
def test_every_row_has_a_control(role, kind):
    d, said = _drawer(role, kind)
    made = sum(len(s.ctls) for s in d.drawer.sections)
    assert made == len(V.rows(role, kind)), (role, kind)
    assert not said  # (showing it is no change)
    assert all(not hasattr(s.card, "collapsed") for s in d.drawer.sections)  # (flat: no folds)


def test_a_change_is_written_to_the_layer_itself():
    lay = V.new("fill", field="dbz")
    d, said = _drawer("fill", lay=lay)
    d.ctl("alpha").widget.value = 0.5
    assert lay["alpha"] == 0.5 and said == [{"alpha"}]
    d.ctl("field").parts[0].value = "w"  # (a fill: its colours and range beside it)
    assert lay["field"] == "w" and lay["cmap"] == "RdBu_r"
    assert said[-1] >= {"field", "cmap", "vmin", "vmax"}
    assert d.ctl("cmap").get() == "RdBu_r"  # (the controls show it)


def test_what_is_offered_follows_the_layer():
    lay = V.new("fill", field="dbz")
    d, _ = _drawer("fill", lay=lay)
    assert not d.ctl("vmin").widget.visible
    d.ctl("auto").widget.value = False
    assert d.ctl("vmin").widget.visible and lay["auto"] is False
    d.ctl("mode").widget.value = "colmax"
    assert not d.ctl("z").widget.visible


def test_the_level_slider_follows_the_mode():
    lay = V.new("fill", field="dbz", mode="height", z=2.0)
    d, said = _drawer("fill", lay=lay)
    z = d.ctl("z")
    assert z.widget.end == 15.0 and z.widget.name == "km AGL"
    d.ctl("mode").widget.value = "level"
    assert lay["z"] == 3.0 and (z.widget.start, z.widget.end, z.widget.step) == (0, 6, 1)
    assert z.widget.value == 3.0 and z.widget.name == "Model level k"
    d.ctl("mode").widget.value = "height"
    assert lay["z"] == 2.0  # (the level's height)
    z.widget.value = 5.0  # (dragging: nothing yet)
    assert lay["z"] == 2.0
    _slide(z, 5.0)
    assert lay["z"] == 5.0 and said[-1] == {"z"}


def test_terrain_and_radar_levels():
    run = _run(terrain=True)
    assert L.relevel(run, "height", "msl", 1.0) == 1.5
    assert L.relevel(run, "msl", "height", 1.5) == 1.0
    assert L.relevel(run, "colmax", "height", None) == 1.0
    radar = _run(grid=False)
    d, _ = _drawer("fill", lay=V.new("fill", field="dbz", mode="sweep", z=2.0), run=radar)
    assert set(d.host.options("levelmodes", None).values()) == \
        {"sweep", "height", "colmax", "colmin"}
    z = d.ctl("z")
    assert (z.widget.end, z.widget.step, z.widget.value) == (8, 1, 2.0)
    d.ctl("mode").widget.value = "height"
    assert d.lay["z"] == 1.0 and z.widget.name == "km above the radar"


def test_a_difference():
    lay = V.new("fill", field="dbz")
    d, _ = _drawer("fill", lay=lay)
    assert not d.ctl("minus.run").widget.visible
    d.ctl("minus").widget.value = True
    assert lay["minus"] == dict(run=None, time_s=None) and lay["cmap"] == V.DIFF_CMAP
    t = d.ctl("minus.time_s")
    assert t.widget.visible and set(t.widget.options.values()) == {"", "prev", 600.0, 1200.0}
    t.widget.value = "prev"
    assert lay["minus"]["time_s"] == "prev"
    d.ctl("minus.run").widget.value = "/runs/other"
    assert lay["minus"] == dict(run="/runs/other", time_s="prev")


def test_vectors():
    lay = V.new("vectors")
    d, said = _drawer("vectors", lay=lay)
    h = d.ctl("z")
    assert h.widget.end == 15.0 and h.widget.value == 0.5
    _slide(h, 3.0)
    assert lay["z"] == 3.0
    d.ctl("style").widget.value = "streamlines"
    assert not d.ctl("across").widget.visible and d.ctl("stream_n").widget.visible
    assert not d.ctl("ref").widget.visible


def test_the_viewer_changing_the_layer_shows():
    lay = V.new("fill", field="dbz")
    d, said = _drawer("fill", lay=lay)
    lay["alpha"] = 0.3
    d.refresh()
    assert d.ctl("alpha").get() == 0.3 and not said


def test_the_figures_drawer_still_folds():
    host = samples.Host()
    from atmo3d.figures.schema.where import Where
    dr = D.Drawer(host, Where("panel", "plan", 1, layer=0))
    assert not dr.flat and all(hasattr(s.card, "collapsed") for s in dr.sections)
