"""A figure document with a panel of every kind and a layer of every type, and no data: for the
drawer's test page (tools/schema_drawers.py) and its tests.  Its runs are names only."""

import copy

from ..spec.sections import section_defaults

FILL = dict(type="fill", on=True, field="dbz", mode="height", z=1.0, units="dBZ",
            cmap="viridis", reverse=False, white_first=False, vmin=0.0, vmax=60.0, nlevels=0,
            style="mesh", mask_below=None, extend="auto")
CONTOUR = dict(type="contour", on=True, field="w", mode="height", z=3.0, levels="5, 10",
               color="k", lw=0.75, neg_dashed=True, clabel=False, legend="")
SHADE = dict(type="shade", on=True, field="w", mode="height", z=1.0, threshold=10.0,
             above=True, color="magenta", alpha=0.6, outline="", lw=1.0, legend="", hatch="",
             hatch_lw=0.6)
VECTORS = dict(type="vectors", on=True, vector="wind", z=0.0, spacing=2.0, zspacing=0.5,
               frame="ground", scale=250.0, width=0.002, color="k", key=0.0, style="arrows",
               density=1.5, slw=0.8, arrowsize=1.0, barb_len=5.5, barb_units="kt")
TRACK = dict(type="track", on=True, color="k", run_color=True, lw=1.0, ls="-", marker=True,
             legend="")
LINE = dict(type="line", on=True, color="k", lw=2.0, labels="A, A′", which="all", legend="")
SECTOR = dict(type="sector", on=True, color="k", lw=1.5, ls="-", az0=0.0, az1=360.0,
              rmax=20.0, ref="motion", center="track", offx=0.0, offy=0.0, cx=0.0, cy=0.0,
              legend="")
BOUNDARIES = dict(type="boundaries", on=True, kinds=["coastlines", "states"], color="#555555",
                  lw=0.6, grid=False, step=0.0, grid_labels=True, legend="")
PARCELS = dict(type="parcels", on=True, name="up", rule=None, ids=[1, 2], color="#d62728",
               cvar="", units="", cmap="viridis", reverse=False, vmin=None, vmax=None,
               tails="until", minutes=10.0, heads=True, interp=True, lw=0.8, alpha=0.8, ms=3.0,
               within=1.0, xs_tails="near", moving="grid", move_u=0.0, move_v=0.0,
               cbar_label="", legend="")
SERIES = dict(type="series", recipe=dict(field="w", vmode="layer", region="domain",
                                         reduce="max", z0=0.0, z1=10.0),
              label="max w", op="", units="m/s", base_units="m/s", cmap="viridis",
              reverse=False, white_first=False, vmin=0.0, vmax=40.0, nlevels=0, extend="auto",
              color="#1f77b4", lw=1.5, ls="-", marker="", axis="auto", ylabel="", runs=None,
              ens="", ens_mid="mean", ens_members="faint", ens_alpha=0.25)
PARCEL_SERIES = dict(type="series", source="parcels", recipe={}, runs=["r0"], name="up",
                     var="w", op="", ens="", ens_mid="mean", ens_members="faint", each=0,
                     ens_alpha=0.25, label="up: w", color="#d62728", lw=1.5, ls="-")
MY_SERIES = dict(type="series", source="table", recipe={}, runs=[],
                 table=dict(t=[0.0, 5.0], v=[1.0, 2.0]), label="My data", units="mm",
                 base_units="mm", t0_min=0.0, color="k", lw=1.5, ls="-")
SOUNDING = dict(type="sounding", run="r0", time_s=3600.0, where=dict(kind="trk", x=0.0, y=0.0,
                                                                     avg=0.0),
                label="", color="")
DIST = dict(type="dist", run="r0", time_s=3600.0, label="", color="",
            recipe=dict(field="w", vmode="height", region="domain", z=1.0, lo=None, hi=None))
PROFILE = dict(type="profile", run="r0", runs=["r0"], time_s=3600.0, time_s1=None, label="",
               color="", ls="", lw=1.5, op="", ens="",
               recipe=dict(field="w", vmode="layer", region="track", radius=5.0,
                           offset=[0.0, 0.0], reduce="max", z0=0.0, z1=10.0))
MY_PROFILE = dict(type="profile", source="table", table=dict(t=[0.5, 1.0], v=[3.0, 4.0]),
                  recipe={}, run=0, runs=[], units="m/s", label="My data", xlabel="",
                  color="k", ls="-", lw=1.5, marker="")
JOINT = dict(type="joint", run="r0", time_s=3600.0, time_s1=None, label="", color="",
             recipe=dict(field="w", yfield="zvort", vmode="height", region="domain", z=1.0,
                         lo=None, hi=None, ylo=None, yhi=None))
AZIM = dict(type="azim", run="r0", time_s=3600.0, time_s1=None, label="", color="", levels="",
            lw=1.0, recipe=dict(field="w", op="mean", center="track", offset=[0.0, 0.0],
                                ref="motion", az0=0.0, az1=360.0, rmax=20.0, dr=None, z0=0.0,
                                z1=15.0))
TABLE = dict(type="table", what="sounding", run="r0", runs=None, times_s=[3600.0], label="",
             params=["sbcape"], stats=[], where=dict(kind="trk", x=0.0, y=0.0, avg=0.0),
             recipe=dict(field="w", vmode="height", region="domain", z=1.0, lo=None, hi=None))


def _panel(pid, kind, r, c, layers, **keys):
    return dict(id=pid, kind=kind, cell=[r, c, 1, 1], layers=copy.deepcopy(layers), **keys)


def every_kind():
    """A document with a panel of each kind (plan views sharing layers, an inset, a section,
    entries of every type, a 3D scene with its lists), two runs and an annotation."""
    at = dict(run="r0", time_s=3600.0)
    return dict(
        version=3, size=[13.0, 9.0], size_auto=False, suptitle="",
        grid=dict(rows=3, cols=4),
        runs=[dict(id="r0", path="/demo/run_a", label="A"),
              dict(id="r1", path="/demo/run_b", label="B")],
        style={}, kinds=dict(scene=dict(scene3d=dict(
            isos=[dict(on=True, var="dbz", val=40.0, color="#7dd3fc", op=0.5)],
            vecs=[dict(on=True, q="wind", level=1.0, frame="ground", density=16, ref=20.0,
                       color="#000000")],
            parcels=[dict(on=True, name="up", cvar="", color="#d62728", tails="until",
                          minutes=10.0, lw=1.5, ms=3.0, alpha=0.8, heads=True, moving="grid",
                          move_u=0.0, move_v=0.0)]))),
        layers=dict(l0=copy.deepcopy(FILL), l1=copy.deepcopy(CONTOUR)),
        sections=dict(s0=section_defaults(orient="x", pos="storm")),
        panels=[
            _panel(0, "plan", 0, 0, [dict(ref="l0", over={}), dict(ref="l1", over={}), SHADE,
                                     VECTORS, TRACK, LINE, SECTOR, BOUNDARIES, PARCELS], **at,
                   insets=[dict(id=7, loc="upper right", size=0.4)]),
            _panel(1, "plan", 0, 1, [dict(ref="l0", over=dict(cmap="Reds")),
                                     dict(ref="l1", over={})], **at),
            _panel(2, "xsec", 0, 2, [VECTORS, PARCELS], section="s0", **at),
            _panel(3, "th", 0, 3, [dict(SERIES, runs=["r0"])], run="r0"),
            _panel(4, "line", 1, 0, [SERIES, PARCEL_SERIES, MY_SERIES]),
            _panel(5, "sounding", 1, 1, [SOUNDING]),
            _panel(6, "dist", 1, 2, [DIST]),
            _panel(8, "profile", 1, 3, [PROFILE, MY_PROFILE]),
            _panel(9, "joint", 2, 0, [JOINT]),
            _panel(10, "azim", 2, 1, [AZIM]),
            _panel(11, "table", 2, 2, [TABLE]),
            _panel(12, "scene", 2, 3, [], **at)],
        annotations=[dict(kind="text", panel=-1, coords="axes", x=0.5, y=0.5, text="A",
                          color="#000000", size=10.0, bold=False)])


class Host:
    """A drawer's host with no viewer: the document, undo, and lists made up from the document
    (fields: none, so a field is typed)."""

    fields = None

    def __init__(self, doc=None):
        from ..schema import fills
        self.doc = doc if doc is not None else every_kind()
        self.undo, self.said, self.drawers = [], [], []
        self.ctx = fills.Context()

    def edit(self, fn):
        before = copy.deepcopy(self.doc)
        new = copy.deepcopy(self.doc)
        fn(new)
        self.undo.append(before)
        self.doc = new
        for d in self.drawers:
            d.refresh()

    def back(self):
        if self.undo:
            self.doc = self.undo.pop()
            for d in self.drawers:
                d.refresh()

    def say(self, text, err=False):
        self.said.append((text, err))

    # ---- what controls offer
    def options(self, name, where):
        from ..choices import LEVEL_MODES
        from ...core import vectors
        if name == "levelmodes":
            return LEVEL_MODES
        if name == "vectors":
            return {d.label if hasattr(d, "label") else k: k for k, d in vectors.VECTORS.items()}
        if name == "frames":
            return {"Ground-relative": "ground", "Grid-relative": "grid",
                    "Storm-relative": "storm"}
        if name == "sections":
            return {f"{n + 1}: {s.get('label') or sid}": sid
                    for n, (sid, s) in enumerate((self.doc.get("sections") or {}).items())}
        if name.startswith("layers:"):
            types = name[7:].split(",")
            return {"the first that is on": ""} | {
                f"{lid}: {lay.get('field', lay['type'])}": lid
                for lid, lay in (self.doc.get("layers") or {}).items() if lay["type"] in types}
        return {}

    def runs(self):
        return {f"{n + 1}. {r.get('label') or r['id']}": r["id"]
                for n, r in enumerate(self.doc.get("runs") or [])}

    def run_of(self, where, key=None):
        return None

    def times(self, run_id):
        return {f"{m} min": m * 60.0 for m in range(0, 121, 5)}

    def psets(self, where):
        return {"this one": "", "down (viewer)": "v:down"}

    def pvars(self, where):
        return {"w": "w", "θ": "theta", "Height": "z"}


def places(doc):
    """[(words, where.Where, part)] of every place of doc a drawer can be opened at (part:
    drawer.rows_at's)."""
    from .. import draw as figdraw
    from ..kinds import KINDS
    from ..schema.where import Where
    kinds = list(dict.fromkeys(p["kind"] for p in doc["panels"]))
    letter = {p["id"]: figdraw.panel_letter(n, "{a}") for n, p in enumerate(doc["panels"])}
    out = [("The figure", Where("figure"), None)]
    out += [(f"All {KINDS[k].name}", Where("kind", k), None) for k in kinds]
    out += [(f"Panel {letter[p['id']]} ({p['kind']})", Where("panel", p["kind"], p["id"]), None)
            for p in doc["panels"]]
    out += [(f"Inset {i['id']} of panel {letter[p['id']]}", Where("inset", p["kind"], p["id"],
                                                                  i["id"]), None)
            for p in doc["panels"] for i in p.get("insets") or []]
    out += [(f"Run {r.get('label') or r['id']}", Where("figure", item=r["id"]), "run")
            for r in doc.get("runs") or []]
    out += [(f"Annotation {n + 1}", Where("figure", item=n), "annotation")
            for n, _ in enumerate(doc.get("annotations") or [])]
    out += [(f"Section {sid}", Where("kind", "xsec", item=sid), "section")
            for sid in doc.get("sections") or {}]
    out += [(f"Shared layer {lid} ({lay['type']})", Where("kind", "plan", layer=lid), None)
            for lid, lay in (doc.get("layers") or {}).items()]
    for p in doc["panels"]:
        for j, (ref, lay) in enumerate(figdraw.panel_layers(doc, p)):
            src = f":{lay['source']}" if lay.get("source") else ""
            out.append((f"Panel {letter[p['id']]}, layer {j + 1} ({lay['type']}{src}"
                        + (f", shared {ref}" if ref else "") + ")",
                        Where("panel", p["kind"], p["id"], layer=j), None))
    sc = ((doc.get("kinds") or {}).get("scene") or {}).get("scene3d") or {}
    for name in ("isos", "vecs", "parcels"):
        out += [(f"3D scene: {name} {n + 1}", Where("kind", "scene", item=n), f"scene:{name}")
                for n, _ in enumerate(sc.get(name) or [])]
    return out
