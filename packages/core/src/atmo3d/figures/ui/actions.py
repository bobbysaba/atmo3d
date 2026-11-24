"""What the figure's tools do that is not a setting, for plan views, cross-sections, their
sections and zoom insets (docs-dev/figures-ui-plan.md, 3.3; the old plan, cross-section and
inset panes had them): a new layer, copying a layer's look, a zoom inset, a panel's section
(another, its own, the map's A–B), a panel per run, titles from what each shows.  Each is one
edit of the shell (one undo step)."""

import html

import panel as pn

from .. import spec as fg
from ..choices import TYPE_LABEL
from ..schema.where import Where
from ..shell import docedit as de, nodes
from ..times import _nearest_t
from .parts import SECTION, _grid, button, head, note

NO_SETS = "No parcel sets: make one in the viewer's Parcels tab."


# ------------------------------------------------------------ layers
def new_layer(shell, kind):
    """A new layer of a type (a parcels one: the viewer's set not drawn yet; None if there is
    none)."""
    F = shell.fields
    field = None
    if kind in ("fill", "contour", "shade"):
        field = F.role({"fill": "refl", "contour": "w", "shade": "w"}[kind])
        if field is None:
            field = next(iter(F.defs))
    lay = fg.layer_defaults(kind, F, field, 1.0)
    if kind == "parcels":
        have = {x.get("name") for x in (shell.doc.get("layers") or {}).values()}
        sets = shell.ed._parcel_layers()
        if not sets:
            return None
        lay = next((x for x in sets if x["name"] not in have), sets[0])
    return lay


def copy_look(shell, src, to):
    """Shared layer src's look on shared layers `to`, those of its type (one undo step)."""
    doc = shell.doc
    kept = [lid for lid in to if lid != src
            and doc["layers"][lid]["type"] == doc["layers"][src]["type"]]
    if not kept:
        shell.say("Choose layers of the same type to copy to.", True)
        return

    def apply(d):
        for lid in kept:
            d["layers"][lid] = fg.copy_look(d["layers"][src], d["layers"][lid])
    shell.edit(apply, node=shell.node)


def copy_look_card(shell, doc, ids):
    """Copying one shared layer's look onto others, in a fold."""
    fields = shell.fields

    def name(n, lid):
        lay = doc["layers"][lid]
        field = lay.get("field")
        word = f": {fields[field].label}" if field and field in fields else ""
        return f"{n + 1}. {TYPE_LABEL.get(lay['type'], lay['type'])}{word}"

    opts = {name(n, lid): lid for n, lid in enumerate(ids)}
    src = pn.widgets.Select(name="Copy the look of", options=opts)
    to = pn.widgets.MultiChoice(name="To layers", options=opts)
    go = button("Copy", lambda: copy_look(shell, src.value, to.value))
    return pn.Card(note("Colours, lines, style and colorbar of one layer onto others of its "
                        "type; the colour range, levels and labels too when they show the same "
                        "field."), _grid(src, (to, 2)), go, title="Copy a layer's look",
                   collapsed=True, **SECTION)


# ------------------------------------------------------------ zoom insets
def add_inset(shell, pid):
    """A new inset of the middle third of what panel pid shows in the preview, picked.  None
    until the preview has drawn the panel."""
    pl = shell.placing
    p = de.panel_by_id(shell.doc, pid)
    entry = pl.place.get(pid)
    if entry is None or pid in pl.fractions:
        shell.say("Wait for the preview: the inset starts from what the panel shows.", True)
        return None
    box, _ = pl._inset_box(pid, entry, (1 / 3, 1 / 3), (2 / 3, 2 / 3))
    made, centre = [], pl._storm_centre(p)
    shell.edit(lambda d: made.append(de.add_inset(d, pid, box, None, centre)))
    shell._show(f"inset:{pid}:{made[0]['id']}")
    return made[0]


# ------------------------------------------------------------ sections
def section_kind(doc):
    """The kind a section's drawer speaks for (its rows are cross-sections' and plan views')."""
    kinds = {p["kind"] for p in doc.get("panels") or []}
    return "xsec" if "xsec" in kinds else "plan"


def draws_sections(doc):
    """Whether anything shows a section: a cross-section, or a plan view's Section line layer."""
    from .. import draw as figdraw
    return any(p["kind"] == "xsec" or any(lay.get("type") == "line" for _, lay in
                                          figdraw.panel_layers(doc, p))
               for p in doc.get("panels") or [])


def add_section(shell, frame=None):
    """A new section after the last (an x–z one's y–z twin, along the motion's across one),
    open."""
    def apply(d):
        last = list((d.get("sections") or {}).values())
        sid = de.add_section(d, de.twin_section(last[-1]) if last else {})
        if frame is not None:
            frame.folds[f"sec:{sid}"] = True
    shell.edit(apply, node=shell.node)


def copy_section(shell, sid, frame=None):
    def apply(d):
        new = de.add_section(d, d["sections"][sid])
        if frame is not None:
            frame.folds[f"sec:{new}"] = True
    shell.edit(apply, node=shell.node)


def new_section(shell, pid):
    """Panel pid shows a new section: its section's twin (or a first one)."""
    def apply(d):
        p = de.panel_by_id(d, pid)
        now = (d.get("sections") or {}).get(p.get("section"))
        p["section"] = de.add_section(d, de.twin_section(now) if now else fg.section_defaults())
    shell.edit(apply, node=shell.node)


def keep_apart(shell, pid):
    """Panel pid gets a copy of its section of its own."""
    shell.edit(lambda d: de.split_section(d, pid), node=shell.node)


def use_ab(shell, sid):
    """Section sid runs between the map's A and B points."""
    pts = shell.v.xs_pts
    if len(pts) != 2:
        shell.say("Draw a cross-section on the map first (Cross-section click mode, points A "
                  "and B).", True)
        return
    shell.edit(lambda d: de.write_section(d, sid, dict(orient="ab", a=list(pts[0]),
                                                       b=list(pts[1]))), node=shell.node)


def ab_button(shell, sid):
    return button("Use the map's A–B", lambda: use_ab(shell, sid),
                  "The section the viewer's map has, from its A to its B point")


def panel_section(frame, doc, pid):
    """A cross-section's section: which, another, one of its own; its settings (which reach
    what else shows it, it says)."""
    from . import drawer as D
    shell = frame.shell
    secs = doc.get("sections") or {}
    if not secs:
        return [head("Its section"), note("No section yet."),
                button("+ Section", lambda: new_section(shell, pid), primary=True)]
    p = de.panel_by_id(doc, pid)
    sid = p.get("section") if p.get("section") in secs else next(iter(secs))
    opts = {f"{k + 1}: {s.get('label') or fg.describe(s)}": k_id
            for k, (k_id, s) in enumerate(secs.items())}
    pick = pn.widgets.Select(name="Section", options=opts, value=sid,
                             sizing_mode="stretch_width")
    pick.param.watch(lambda ev: shell.edit(
        lambda d: de.panel_by_id(d, pid).update(section=ev.new), node=shell.node), "value")
    objs = [head("Its section"),
            pn.Row(pick, button("+ Section", lambda: new_section(shell, pid),
                                "A new section for this panel: an x–z one's y–z twin, along "
                                "the motion's across one"), margin=0,
                   sizing_mode="stretch_width")]
    names = nodes.letters(doc)
    others = [q for q in de.section_panels(doc, sid) if q["id"] != pid]
    if others:
        n = len(others)
        objs += [note(f"<b>Panel{'s' if n > 1 else ''} "
                      + html.escape(", ".join(names[q["id"]] for q in others))
                      + f" show{'' if n > 1 else 's'} this section too:</b> changes here reach "
                        "them."),
                 button("Keep apart", lambda: keep_apart(shell, pid),
                        "This panel gets a copy of the section of its own; the others keep "
                        "this one")]
    where = Where("panel", "xsec", pid)
    rows = D.rows_at(doc, where, "section")
    objs += [frame.drawer(where, rows, opened=("Section line",)).panel, ab_button(shell, sid)]
    return objs


def sections_list(frame, doc):
    """All the figure's sections: adding one, each with what shows it, removing one no panel
    shows."""
    from .tools import Item
    from . import drawer as D
    shell = frame.shell
    secs = doc.get("sections") or {}
    names = nodes.letters(doc)
    kind = section_kind(doc)
    objs = [head("Sections"),
            note("Where the cross-sections and section lines run. A change reaches everything "
                 "showing the section."),
            button("+ Section", lambda: add_section(shell, frame),
                   "A new section after the last: an x–z one's y–z twin, along the motion's "
                   "across one")]
    for k, (sid, s) in enumerate(secs.items()):
        using = de.section_panels(doc, sid)
        words = ("Cross-section panels " + ", ".join(names[p["id"]] for p in using) + "."
                 if using else "No cross-section shows it: a plan view's Section line layer "
                               "draws it.")
        moves = dict(copy=lambda i=sid: copy_section(shell, i, frame))
        if de.remove_section(de.plain(doc), sid) is None:
            moves["remove"] = lambda i=sid: shell.edit(lambda d: de.remove_section(d, i),
                                                       node=shell.node)
        where = Where("kind", kind, item=sid)
        objs.append(Item(frame, f"sec:{sid}", f"{k + 1}. {s.get('label') or fg.describe(s)}",
                         where, D.rows_at(doc, where, "section"), moves,
                         extras=lambda w=words, i=sid: [note(w), ab_button(shell, i)],
                         opened=len(secs) == 1).card)
    return objs


# ------------------------------------------------------------ panels
def one_per_run(shell, pid):
    """A copy of cross-section pid for each other run, down its column, at the same time since
    time zero."""
    doc = shell.doc
    if len(doc["runs"]) < 2:
        shell.say("The figure has one run: add others first (Runs).", True)
        return
    p = de.panel_by_id(doc, pid)
    times = {}
    for r in doc["runs"]:
        if p.get("time_s") is not None:
            ts = de._moved(doc, p["time_s"], p["run"], r["id"])
            tl = list(shell.time_opts(de.run_index(doc, r["id"])).values())
            times[r["id"]] = _nearest_t(tl, ts) if tl else ts
    if not de.panel_per_run(de.plain(doc), pid, times):
        shell.say("Every run has this section already.", True)
        return
    shell.edit(lambda d: de.panel_per_run(d, pid, times), node=shell.node)


def titles_objs(shell, kind):
    """Titles of a kind's panels from what each shows, and clearing them."""
    def clear():
        def apply(d):
            for p in de.panels_of(d, kind):
                p["title"] = ""
        shell.edit(apply, node=shell.node)

    return [pn.Row(button("Titles from what each shows", lambda: shell.edit(
        lambda d: de.entry_titles(d, kind), node=shell.node)),
        button("Clear the titles", clear), margin=0)]


# ------------------------------------------------------------ annotations
def _ann_lims(shell, pid):
    """The axis ranges a new annotation of panel pid (None: of every panel) goes by; None: as
    fractions of the panel, as a skew-T, a 3D scene or several kinds together have it."""
    doc, place = shell.doc, shell.placing
    if pid is None:
        kinds = {p["kind"] for p in doc["panels"]}
        drawn = [p["id"] for p in nodes.in_order(doc) if p["id"] in place.place]
        if len(kinds) != 1 or not drawn:
            return None
        pid = drawn[0]
    b = place.place.get(pid)
    return None if b is None or b[6] is not None or pid in place.fractions else (b[4], b[5])


def add_annotation(shell, kind, pid=None):
    """A new annotation of a kind, on panel pid (None: every panel), open in Marks."""
    append_annotation(shell, de.new_annotation(kind, -1 if pid is None else pid,
                                               _ann_lims(shell, pid)))


def append_annotation(shell, new, node=None):
    """Annotation `new` into the document, its fold in Marks open (node: what is picked
    after)."""
    frame = shell.frame

    def apply(d):
        d.setdefault("annotations", []).append(new)
        frame.folds[f"ann:{len(d['annotations']) - 1}"] = True
    shell.edit(apply, node=node or shell.node)


def own_area(doc, keys=("domain.mode", "domain.box")):
    """The letters of the plan views with an area of their own (which the kind's skips)."""
    names, out = nodes.letters(doc), []
    for p in de.panels_of(doc, "plan"):
        opts = p.get("opts") or {}
        if any(isinstance(opts.get(b), dict) and k in opts[b]
               for b, _, k in (x.rpartition(".") for x in keys)):
            out.append(names[p["id"]])
    return out
