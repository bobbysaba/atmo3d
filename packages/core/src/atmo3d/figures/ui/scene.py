"""3D scenes in the figure's tools (docs-dev/figures-ui-plan.md, 3.3; the old sceneview pane had
these): a scene's settings are the schema's scene rows, a key of its block written whole
(schema/where.py, docedit.write_scene: the only scene's go to the kind unless it holds them
itself).  What is not a setting is here:

  Layers   the lists (isosurfaces, vector planes, parcel sets), each item a fold with its
           drawer, adding and removing; the floor and streamlines (seeding them in the map's
           seed box); Copy the 3D view
  Layout   the region (the map's 3D box)
  Look     the camera (Camera of the 3D view)

At All 3D scenes an edit reaches every scene but what one holds itself; at a scene's panel it
is that scene's own, each such key with ↺ to take it back."""

import panel as pn

from ...core import vectors
from .. import schema as S
from ..scene import ISO_MAX, PAR_MAX, VEC_MAX, next_iso, next_vec
from ..schema import KEEP
from ..schema.where import Where
from ..shell import docedit as de, nodes
from .parts import button, head, note

LISTS = (("isos", "Isosurfaces", "+ Isosurface", ISO_MAX),
         ("vecs", "Vectors", "+ Vectors", VEC_MAX),
         ("parcels", "Parcels", "+ Parcels", PAR_MAX))
LIST_NOTES = dict(
    isos="Untick Drawn to leave a surface out (it is kept). Storm-relative fields use the run's "
         "track.",
    vecs="Arrows in a plane at a height; Arrows across: across the region's width.",
    parcels="Parcel sets as the viewer's Parcels tab chose them: tails as lines, heads at the "
            "scene's time as balls, inside the region. Coloured by a variable, the first such "
            "set gets the parcel colorbar (Look).")
KEY_NAMES = dict(isos="Isosurfaces", ground="Floor", vecs="Vectors", stream="Streamlines",
                 parcels="Parcels", box="Region", ztop="Top", exag="Exaggeration",
                 smooth="Smoothing", res="Resolution", camera="Camera", look="Look",
                 follow="Box in animations", orbit="Camera orbit")
HINT = ("One 3D picture, rendered off-screen at the preview's resolution here and at the "
        "export's DPI when saved.")


def _pid(where):
    return where.pid if where.level == "panel" else None


def block(doc, where):
    return de.scene_block(doc, _pid(where))


def write(shell, where, key, value):
    """A key of the scene block at where, whole (one undo step); the drawer shown anew."""
    value = de.plain(value)
    shell.edit(lambda d: de.write_scene(d, _pid(where), key, value), node=shell.node)


def complete(name, item, run=None):
    """A new item of list `name` with every setting its rows have (what a row of the old editor
    collected: a vector's reference length its vector's)."""
    out = dict(item)
    for r in S.ROWS:
        if r.writer == "scene" and r.key.startswith(f"look.scene3d.{name}[]."):
            k = r.key.rsplit(".", 1)[1]
            if k not in out and r.default is not KEEP:
                out[k] = r.default
    out.setdefault("on", True)
    if name == "vecs":
        q = out.get("q") or "wind"
        if q not in vectors.VECTORS:
            q = next(iter(vectors.VECTORS))
        out["q"] = q
        out["ref"] = float(out.get("ref") or vectors.VECTORS[q].ref)
    return out


def new_item(shell, where, name):
    """A new item of a list (None, said: there is none to add, a parcel set)."""
    sc = block(shell.doc, where)
    if name == "isos":
        return complete(name, next_iso(shell.fields, sc["isos"]))
    if name == "vecs":
        return complete(name, next_vec(shell.ed.run, sc["vecs"]))
    e = shell.ed.next_parcels({x.get("name") for x in sc["parcels"]}, shell.say)
    return None if e is None else complete(name, e)


def add_item(frame, where, name):
    shell = frame.shell
    new = new_item(shell, where, name)
    if new is None:
        return
    items = [*block(shell.doc, where)[name], new]
    frame.folds[_fold(where, name, len(items) - 1)] = True
    write(shell, where, name, items)


def remove_item(shell, where, name, n):
    items = [x for k, x in enumerate(block(shell.doc, where)[name]) if k != n]
    write(shell, where, name, items)


def move_item(shell, where, name, n, by):
    items = list(block(shell.doc, where)[name])
    items[n], items[n + by] = items[n + by], items[n]
    write(shell, where, name, items)


def _fold(where, name, n):
    return f"scene:{where.pid}:{name}:{n}"


def copy_view(shell, pid):
    """Everything the 3D workspace shows now, on scene pid (None: all scenes); the animation
    stays."""
    sc = de.plain(shell.ed.viewer_scene())
    now = de.scene_block(shell.doc, pid)
    sc.update(follow=now["follow"], orbit=now["orbit"])

    def apply(d):
        for key, value in sc.items():
            de.write_scene(d, pid, key, value)
    shell.edit(apply, node=shell.node)


# ------------------------------------------------------------ Layers
def layers(frame, doc, where):
    """A scene's lists, its floor and streamlines; Copy the 3D view."""
    from .tools import Item, rows_for
    from . import drawer as D
    shell = frame.shell
    pid = _pid(where)
    objs = [note(HINT), *_reach(frame, doc, where),
            button("Copy the 3D view", lambda: copy_view(shell, pid),
                   "Everything the 3D workspace shows now (its box, surfaces, floor, vectors, "
                   "streamlines and camera)")]
    sc = block(doc, where)
    for name, title, add, most in LISTS:
        if name == "parcels" and shell.v.pf is None and not sc["parcels"]:
            continue
        items = sc[name]
        objs += [head(title + (f" ({len(items)})" if items else "")), note(LIST_NOTES[name])]
        for n, item in enumerate(items):
            w = Where(where.level, "scene", where.pid, item=n)
            moves = dict(remove=lambda n=n, name=name: remove_item(shell, where, name, n))
            if n > 0:
                moves["up"] = lambda n=n, name=name: move_item(shell, where, name, n, -1)
            if n < len(items) - 1:
                moves["down"] = lambda n=n, name=name: move_item(shell, where, name, n, 1)
            objs.append(Item(frame, _fold(where, name, n), f"{n + 1}. {_item_name(shell, name, item)}",
                             w, D.rows_at(doc, w, f"scene:{name}"), moves,
                             opened=len(items) == 1 and name == "isos").card)
        b = button(add, lambda name=name: add_item(frame, where, name), primary=not items)
        b.disabled = len(items) >= most
        objs.append(b)
    rows = rows_for(doc, where, "layers")
    if rows:
        objs += [head("Floor and streamlines"), frame.drawer(where, rows).panel,
                 *_seeding(shell, where, sc)]
    return objs


def _item_name(shell, name, item):
    off = "" if item.get("on", True) else " (off)"
    F = shell.fields
    if name == "isos":
        var = item.get("var")
        label = F[var].label if F is not None and var in F else str(var or "")
        return f"{label} = {float(item.get('val') or 0):g}{off}"
    if name == "vecs":
        return f"{item.get('q') or 'wind'} at {float(item.get('level') or 0):g} km{off}"
    return f"{item.get('name') or 'parcels'}{off}"


def _seeding(shell, where, sc):
    """Where the streamlines are seeded: the map's seed box, or the whole region."""
    sb = sc["stream"].get("seed_box")
    said = "Streamlines seeded over the whole region." if not sb else (
        f"Streamlines seeded in x {sb[0]:.1f} to {sb[1]:.1f}, y {sb[2]:.1f} to {sb[3]:.1f} km.")

    def seed(box):
        write(shell, where, "stream", dict(block(shell.doc, where)["stream"], seed_box=box))

    def from_map():
        box = getattr(shell.v, "seed_box", None)
        if box is None:
            shell.say("Pick a seed box on the map first (3D tool → Seed box on map).", True)
            return
        seed([float(v) for v in box])

    tools = [button("The map's seed box", from_map,
                    "Seed inside the box picked on the map (3D tool → Seed box on map)")]
    if sb:
        tools.append(button("Whole region", lambda: seed(None)))
    return [note(said), pn.Row(*tools, margin=0)]


def _reach(frame, doc, where):
    """At a scene: what it holds of its own, each to take back (↺); at All 3D scenes: which
    scenes keep their own."""
    shell = frame.shell
    names = nodes.letters(doc)
    if where.level == "kind":
        differ = [names[p["id"]] for p in de.panels_of(doc, "scene") if de.scene_own(doc, p["id"])]
        if not differ:
            return []
        return [note("Set in a scene alone, so changes here skip it: panel"
                     + ("s " if len(differ) > 1 else " ") + ", ".join(differ) + ".")]
    pid = where.pid
    own = de.scene_own(doc, pid)
    if not own:
        return []

    def back(key):
        shell.edit(lambda d: de.scene_take_back(d, pid, key), node=shell.node)

    chips = []
    for key in own:
        b = pn.widgets.Button(name=f"↺ {KEY_NAMES.get(key, key)}", height=26, margin=(2, 2),
                              button_type="light", button_style="outline",
                              description="Back to what all 3D scenes have")
        b.on_click(lambda e, k=key: back(k))
        chips.append(b)
    return [note("Set for this scene alone:"), pn.FlexBox(*chips, sizing_mode="stretch_width")]


# ------------------------------------------------------------ Layout, Look
def region_tools(shell, where):
    """Below the region's settings: the box drawn on the map."""
    def from_map():
        b = getattr(shell.v, "box", None)
        if b is None:
            shell.say("Draw a 3D box on the map first (3D tool), or type one.", True)
            return
        write(shell, where, "box", [round(float(v), 2) for v in b])

    return [button("The map's 3D box", from_map, "The box drawn on the map (3D tool)"),
            note("The exaggeration only stretches the picture (nothing is read again); the "
                 "region, top, smoothing and resolution compute the surfaces again.")]


def camera_tools(shell, where):
    """Below the camera's settings: the camera the 3D workspace was left with."""
    def tidy(c):  # (an explicit position, as a saved figure has, no longer holds)
        return dict(c, zoom=c.get("zoom") or 1.0, view_angle=c.get("view_angle") or 30.0,
                    position=None, focal=None, up=None)

    def from_3d():
        write(shell, where, "camera", tidy(shell.ed._view_camera()))

    return [button("Camera of the 3D view", from_3d,
                   "The direction and distance the 3D workspace is seen from now"),
            note("A view, turned by the azimuth and elevation typed (blank: the view's own), at "
                 "the distance where the region fits, divided by the zoom. Camera of the 3D "
                 "view: as you left the 3D workspace (rotate it there, then click).")]
