"""The viewer's layers on the schema (figures/schema/viewer.py, docs-dev/figures-ui-plan.md Phase
5.1): every setting a session saves of a layer is a row at the level "viewer"; a session's layer
comes back as it was; the rows read and write the layer itself; what a change fills in beside
it is what the viewer's widgets did; the figure never offers the level.  No viewer needed."""

from types import SimpleNamespace

import pytest

from atmo3d.figures import schema as S
from atmo3d.figures.schema import KEEP, fills, viewer as V, where as W

# what a session of FORMAT 2 (1.1.0: viewer/session.py then) saved of a layer, its widgets' keys
FILL_KEYS = ("on", "var", "mode", "level", "style", "cmap", "rev", "auto", "vmin", "vmax",
             "alpha", "clip")
OV_KEYS = ("on", "var", "mode", "level", "levels", "color", "width", "negdash")
VEC_KEYS = ("on", "q", "level", "frame", "style", "density", "ref", "color")
MAIN_KEYS = ("var", "op", "mode", "level", "style", "cmap", "rev", "auto", "vmin", "vmax",
             "nlev", "alpha")
# (role, kind) -> the keys a session (FORMAT 2) saves of such a layer
SESSION_KEYS = {
    ("fill", "plan"): list(MAIN_KEYS) + ["diff"],
    ("more", "plan"): list(FILL_KEYS),
    ("contour", "plan"): list(OV_KEYS),
    ("vectors", "plan"): list(VEC_KEYS),
    ("fill", "xsec"): ["var", "style", "cmap", "rev", "auto", "vmin", "vmax", "nlev", "diff"],
    ("more", "xsec"): [k for k in FILL_KEYS if k not in ("mode", "level")],
    ("contour", "xsec"): [k for k in OV_KEYS if k not in ("mode", "level")],
    ("vectors", "xsec"): [k for k in VEC_KEYS if k not in ("level", "style")],
}

SAMPLE = dict(on=False, var="w", op="ddx", mode="level", level=12.0, style="contourf",
              cmap="magma", rev=True, auto=False, vmin=-5.0, vmax=25.0, nlev=20, alpha=0.55,
              clip=False, levels="5, 15", color="#60a5fa", width=2.25, negdash=False, q="hvort",
              frame="storm", density=31, ref=0.02,
              diff=dict(on=True, run="/runs/other", time="prev"))
_PER_ROLE = {("vectors", "plan"): dict(level=3.5, style="streamlines"),
             ("vectors", "xsec"): dict(style="arrows")}


def _session(role, kind):
    keys = SESSION_KEYS[(role, kind)]
    vals = dict(SAMPLE, **_PER_ROLE.get((role, kind), {}))
    d = {k: vals[k] for k in keys}
    if role == "fill" and kind == "xsec":
        d.pop("op", None)
    return d


class FakeFields:
    """What the viewer fills read of the runs' fields: a cmap, a range, dimensions."""
    defs = {"dbz": SimpleNamespace(cmap="pyart_NWSRef", vrange=(0.0, 70.0), ndim=3),
            "w": SimpleNamespace(cmap="RdBu_r", vrange=(-20.0, 20.0), ndim=3),
            "cref": SimpleNamespace(cmap="pyart_NWSRef", vrange=(0.0, 70.0), ndim=2)}

    def __contains__(self, name):
        return name in self.defs

    def __getitem__(self, name):
        return self.defs[name]


CTX = fills.Context(fields=FakeFields(), drawn=(1.23456, 47.0))
CASES = sorted(V.LAYOUT)


@pytest.mark.parametrize("role,kind", CASES)
def test_every_session_key_is_a_viewer_row(role, kind):
    keys = {r.key.split(".")[1] for r in V.rows(role, kind)}
    lay = V.from_session(role, _session(role, kind), kind)
    for k in SESSION_KEYS[(role, kind)]:
        name = {"var": "field", "op": "field", "level": "z", "rev": "reverse",
                "nlev": "nlevels", "width": "lw", "negdash": "neg_dashed", "q": "vector",
                "diff": "minus",
                "density": "stream_n" if lay.get("style") == "streamlines" else "across"
                }.get(k, k)
        assert name in keys, (role, kind, k)


@pytest.mark.parametrize("role,kind", CASES)
def test_a_format_2_layer_upgraded(role, kind):
    """A FORMAT 2 layer as FORMAT 3 keeps it (session.upgrade): what it had, in the layer's
    keys, nothing more; put over a new layer, the layer read from it."""
    d = _session(role, kind)
    lay = V.from_session(role, d, kind)
    assert lay["type"] == V.TYPE[role] and lay["role"] == role
    up = V.upgraded(role, d, kind)
    keys = {r.key.split(".")[1] for r in V.rows(role, kind)}
    assert set(up) <= keys and len(up) <= len(d)
    assert dict(V.new(role, kind), **up) == lay
    assert V.saved(lay) == {k: v for k, v in lay.items() if k not in ("type", "role")}
    off = V.upgraded(role, dict(d, diff=dict(on=False)), kind)
    assert ("minus" in off and off["minus"] is None) == (role == "fill")


def test_session_values_in_the_figure_form():
    lay = V.from_session("fill", _session("fill", "plan"))
    assert lay["field"] == "ddx.w" and lay["style"] == "contourf" and lay["reverse"] is True
    assert lay["minus"] == dict(run="/runs/other", time_s="prev")
    assert V.from_session("fill", dict(var="dbz", op="", style="image"))["style"] == "mesh"
    assert "minus" not in V.from_session("fill", dict(var="dbz", diff=dict(on=False)))
    vec = V.from_session("vectors", dict(q="wind", style="streamlines", density=12))
    assert vec["stream_n"] == 12 and vec["across"] == 24


@pytest.mark.parametrize("role,kind", CASES)
def test_rows_read_and_write_the_layer_itself(role, kind):
    lay = V.from_session(role, _session(role, kind), kind)
    if role == "fill":
        lay["minus"] = dict(run=None, time_s=None)
    where = V.at(kind)
    before = dict(lay)
    for r in V.rows(role, kind):
        assert r.at("viewer") and not any(r.at(lv) for lv in S.LEVELS), r.id
        assert S.offered(r, lay, where) in (True, False)
        v = W.value(lay, r, where)
        assert v is not KEEP, r.id
        W.write(lay, r, where, v)  # (no ctx: no fill needs the runs)
        assert not W.own(lay, r, where)
    for k in before:
        assert lay[k] == before[k] or k in ("ref", "cmap", "reverse", "auto"), k


def test_conditions():
    where = V.at("plan")
    rows = {r.key: r for r in V.rows("fill")}
    lay = V.new("fill", field="dbz")
    on = lambda key, l=lay: S.offered(rows[key], l, where, CTX)  # noqa: E731
    assert not on("layer.vmin") and not on("layer.nlevels") and not on("layer.minus.run")
    lay.update(auto=False, style="contourf", minus=dict(run=None, time_s=None))
    assert on("layer.vmin") and on("layer.nlevels") and on("layer.minus.run")
    assert on("layer.z")
    assert not on("layer.z", dict(lay, mode="colmax"))
    assert not on("layer.mode", dict(lay, field="cref"))  # (a 2D field: no level)
    vec = {r.key: r for r in V.rows("vectors")}
    v = V.new("vectors")
    assert S.offered(vec["layer.across"], v, where) and \
        not S.offered(vec["layer.stream_n"], v, where)
    v["style"] = "streamlines"
    assert not S.offered(vec["layer.across"], v, where) and \
        not S.offered(vec["layer.ref"], v, where) and S.offered(vec["layer.stream_n"], v, where)
    assert set(S.row_for("layer.style", "vectors").control.options.values()) > \
        set(vec["layer.style"].control.options.values())  # (no barbs in the viewer)


def _write(role, key, v, lay, kind="plan", ctx=CTX):
    r = next(r for r in V.rows(role, kind) if r.key == key)
    W.write(lay, r, V.at(kind), v, ctx)
    return lay


def test_fills_are_the_viewers():
    lay = _write("fill", "layer.field", "w", V.new("fill", field="dbz", auto=False))
    assert (lay["cmap"], lay["reverse"], lay["vmin"], lay["vmax"], lay["auto"]) == \
        ("RdBu_r", False, -20.0, 20.0, True)
    assert set(lay) <= {r.key.split(".")[1] for r in V.rows("fill")} | {"type", "role"}
    more = _write("more", "layer.field", "dbz", V.new("more", field="w", auto=False))
    assert more["cmap"] == "pyart_NWSRef" and more["auto"] is False  # (a more fill keeps it)
    lay = _write("fill", "layer.minus", True, V.new("fill", field="dbz", auto=False))
    assert lay["cmap"] == V.DIFF_CMAP and lay["auto"] is True and lay["minus"]
    lay = _write("fill", "layer.field", "w", lay)
    assert lay["cmap"] == V.DIFF_CMAP  # (a difference keeps its colours)
    lay = _write("fill", "layer.minus", False, lay)
    assert "minus" not in lay and lay["cmap"] == "RdBu_r"
    lay = _write("fill", "layer.auto", False, V.new("fill", field="dbz"))
    assert (lay["vmin"], lay["vmax"]) == (1.2346, 47.0)
    from atmo3d.core import vectors
    vec = _write("vectors", "layer.vector", "hvort", V.new("vectors"))
    assert vec["ref"] == vectors.VECTORS["hvort"].ref
    assert V.new("vectors")["ref"] == vectors.VECTORS["wind"].ref
    cont = _write("contour", "layer.field", "dbz", V.new("contour", field="w"))
    assert cont["color"] == "#ffffff" and "cmap" not in cont


def test_the_figure_never_offers_the_viewer_level():
    assert not any(r.at("viewer") for r in S.ROWS)
    assert not any(r.at(lv) for r in V.ALL_ROWS for lv in S.LEVELS)


def test_viewer_conditions_name_known_keys():
    known = {r.key.split(".", 1)[1] for r in V.ALL_ROWS} | set(V.VIEWER_ONLY) | {"role"}
    for r in V.ALL_ROWS:
        for alt in r.when.split(" or ") if r.when else []:
            for c in alt.split(" and "):
                name = c.strip().lstrip("!")
                if name.startswith("@"):
                    assert name[1:] in S.WHEN, (r.id, c)
                    continue
                key = name.split("=")[0].rstrip("!")
                assert key in known, (r.id, c)
