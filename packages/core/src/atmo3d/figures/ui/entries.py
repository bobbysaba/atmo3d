"""The Layers tool of the kinds whose panels draw entries of their own rather than shared map
layers (docs-dev/figures-ui-plan.md, 3.3): soundings, time–height panels and time series,
distributions, profiles, joint distributions, azimuthal means and tables.  An entry is a panel's
own layer, with its own run and time (its settings: the schema's entry rows, in the drawer).

  All <kind>   a panel of the kind, a panel for each of the viewer's tool's entries
  a panel      its entries, each a fold (↑ ↓ ⧉ ✕, In panel, One per run), adding one
  an entry     itself

What a new entry is (the old entryview, seriesview and statsview panes had it): it starts at the
viewer's shown time in the viewer's run; a distribution's at w at 1 km, a joint distribution's
vorticity against w, an azimuthal mean's and a table's like the kind's last."""

from types import SimpleNamespace

import panel as pn

from ...core import series as ser
from .. import draw as figdraw, spec as fg
from ..kinds import KINDS
from ..schema.where import Where
from ..shell import docedit as de, nodes
from .grid import own_run, shown_time
from .parts import button, head, note

ENTRY_KINDS = ("sounding", "th", "line", "dist", "profile", "joint", "azim", "table")
SERIES = ("th", "line")
NO_RUNS = "The figure has one run: add others first (Runs)."


# ------------------------------------------------------------ what a new entry is
def has_track(shell):
    return bool(shell.v.fixes) or any(r.get("track") for r in shell.doc["runs"])


def new_recipe(shell):
    """A new series' recipe: max w in 0–10 km near the storm (the whole domain without a
    track), as for updraft time-height plots."""
    F = shell.fields
    field = F.role("w") or next(iter(F.defs))
    return ser.normalize(dict(field=field, vmode="layer", z0=0.0, z1=10.0,
                              region="track" if has_track(shell) else "domain", radius=5.0,
                              offset=(0.0, 0.0), reduce="max"))


def new_dist_recipe(shell):
    """w over the whole domain at 1 km."""
    F = shell.fields
    field = F.role("w") or next(iter(F.defs))
    return dict(field=field, vmode="height", z=1.0, region="domain")


def new_joint_recipe(shell):
    """Vertical vorticity against w (the Distribution tool's last field and place, if it has
    any) over the whole domain at 1 km."""
    tool = list((getattr(shell.v, "dists", {}) or {}).values())
    r = dict(tool[-1]["recipe"]) if tool else new_dist_recipe(shell)
    zv = shell.fields.role("zvort")
    r["yfield"] = zv if zv and r["field"] != zv else r["field"]
    return r


def new_azim_recipe(shell):
    """w around the tracked storm, else around the middle of the map's view; the whole ring out
    to 20 km, 0-15 km."""
    F = shell.fields
    field = F.role("w") or next(
        (k for k, d in F.defs.items() if d.ndim == 3), next(iter(F.defs)))
    x0, x1, y0, y1 = (float(v) for v in shell.v.view)
    return dict(field=field, center="track" if has_track(shell) else "point",
                point=(0.5 * (x0 + x1), 0.5 * (y0 + y1)))


def new_sounding(shell, where=None):
    """A sounding at the shown time in the viewer's run: at the storm, or `where`."""
    rid = own_run(shell)
    e = fg.sounding_defaults(0, shown_time(shell, rid), where)
    e.pop("panel", None)
    return dict(e, type="sounding", run=rid)


def _count(shell, kind):
    """How many entries the figure's panels of a kind have (a new one's colour goes by it)."""
    return sum(len(p.get("layers") or []) for p in de.panels_of(shell.doc, kind))


def _last(shell, kind):
    """The kind's last entry in reading order (None: it has none)."""
    for p in reversed(de.panels_of(shell.doc, kind)):
        if p.get("layers"):
            return de.plain(p["layers"][-1])
    return None


def _start(shell):
    """(place of the run a new entry is of, its id, the shown time in that run)."""
    rid = own_run(shell)
    return de.run_index(shell.doc, rid), rid, shown_time(shell, rid)


def _as_doc(shell, kind, e):
    """An entry as the defaults give it (runs by place) as the document holds it."""
    e = de.from_card(shell.doc, de.plain(e))
    e.pop("panel", None)
    e["type"] = kind
    return e


def series_entry(shell, kind, recipe):
    """A new series of a recipe: of every run; time-height: of the viewer's run."""
    e = fg.series_defaults(shell.fields, recipe, _count(shell, "line"))
    e.pop("panel", None)
    e["type"] = "series"
    if kind == "th":
        e.update(on=True, runs=[own_run(shell)])
    return e


def new_entry(shell, kind):
    """A new entry of a kind."""
    if kind == "sounding":
        return new_sounding(shell)
    if kind in SERIES:
        return series_entry(shell, kind, new_recipe(shell))
    if kind == "table":  # (the kind's last, else sounding values at the storm, or the domain's)
        last = _last(shell, kind)
        if last:
            return last
        k, _, ts = _start(shell)
        where = dict(kind="trk" if has_track(shell) else "mean", x=0.0, y=0.0, avg=0.0)
        return _as_doc(shell, kind, fg.tbl_defaults(new_dist_recipe(shell), k, ts, where))
    k, _, ts = _start(shell)
    n = _count(shell, kind)
    if kind == "dist":
        return _as_doc(shell, kind, fg.dist_defaults(new_dist_recipe(shell), k, ts, n))
    if kind == "profile":
        return _as_doc(shell, kind, fg.profile_defaults(new_recipe(shell), k, ts, n))
    if kind == "joint":
        return _as_doc(shell, kind, fg.joint_defaults(new_joint_recipe(shell), k, ts, n))
    last = _last(shell, kind)  # (azim: the last one's recipe)
    recipe = last["recipe"] if last else new_azim_recipe(shell)
    return _as_doc(shell, kind, fg.azim_defaults(recipe, k, ts, n))


def first_entries(shell, kind):
    """A new panel's entries (series: none; nothing is computed until one is added)."""
    return [] if kind in SERIES else [new_entry(shell, kind)]


def _of_viewer_run(shell, kind, entries):
    """The lists of the viewer's tool, in the viewer's run."""
    rid = own_run(shell)
    out = []
    for e in entries:
        e = de.plain(e)
        e.pop("panel", None)
        e.update(type=kind, run=rid)
        if "runs" in e:
            e["runs"] = [rid]
        out.append(e)
    return out


def map_soundings(shell):
    """The soundings marked in the viewer's Sounding tool, as entries: in the viewer's run."""
    rid = own_run(shell)
    return [dict({k: v for k, v in e.items() if k != "panel"}, type="sounding", run=rid,
                 time_s=float(e["time_s"])) for e in shell.ed.tab_soundings()]


# (a kind's: what its entries are called, a word on its panels, the viewer's tool's entries)
SPEC = dict(
    sounding=SimpleNamespace(
        head="Soundings", one="Sounding",
        note="Soundings of one panel share its skew-T (colour = sounding).",
        tool="+ The map's soundings", tool_tip="A panel for each sounding marked in the viewer's "
                                               "Sounding tool",
        none="No soundings yet: click the map with the Sounding tool first.",
        entries=map_soundings),
    th=SimpleNamespace(head="Series", one="Series", note="", tool="", entries=None),
    line=SimpleNamespace(
        head="Series", one="Series",
        note="Series of one panel share its axes; other units get their own axis.", tool="",
        entries=None),
    dist=SimpleNamespace(
        head="Distributions", one="Distribution",
        note="Distributions of one panel share its axes (colour = distribution).",
        tool="+ The Distribution tool's", tool_tip="A panel for each distribution computed with "
                                                   "the viewer's Distribution tool",
        none="No distributions yet: compute one with the Distribution tool on the map first.",
        entries=lambda sh: _of_viewer_run(sh, "dist", sh.ed.tab_dists())),
    profile=SimpleNamespace(
        head="Profiles", one="Profile",
        note="Profiles of one panel share its axes (colour = profile).",
        tool="+ The Series tool's", tool_tip="A panel for each layer series of the viewer's "
                                             "Series tool, at the shown time",
        none="No layer series yet: make one with the Series tool (Vertical: Layer) first.",
        entries=lambda sh: _of_viewer_run(sh, "profile", sh.ed.tab_profiles())),
    joint=SimpleNamespace(
        head="Joint distributions", one="Joint distribution",
        note="The first of a panel's joint distributions is shaded; the others draw over it.",
        tool="", entries=None),
    azim=SimpleNamespace(
        head="Azimuthal means", one="Azimuthal mean",
        note="The first of a panel's azimuthal means is shaded; the others are contour lines.",
        tool="", entries=None),
    table=SimpleNamespace(
        head="Values", one="Values",
        note="The values of one panel make one table: add more for more columns.", tool="",
        entries=None))


# ------------------------------------------------------------ adding
def add(frame, pid, new):
    """Entries into panel pid, the last open (one undo step)."""
    shell = frame.shell

    def apply(d):
        p = de.panel_by_id(d, pid)
        for e in new:
            if e.get("type") == "series":
                de.add_series(p, de.plain(e))
            else:
                de.add_own(p, de.plain(e))
        frame.folds[f"p:{pid}:{len(de.places(d, p)) - 1}"] = True
    shell.edit(apply, node=shell.node)


def add_panel(frame, kind):
    return frame.shell.grid.add_panel(kind)


def add_tool_panels(frame, kind):
    """Each of the viewer's tool's entries in a panel of its own."""
    shell = frame.shell
    new = SPEC[kind].entries(shell)
    if not new:
        shell.say(SPEC[kind].none, True)
        return

    def apply(d):
        for e in new:
            p = de.add_panel(d, kind, de.next_cell(d), [de.plain(e)])
            frame.folds.setdefault(f"p:{p['id']}:0", True)
    shell.edit(apply, node=shell.node)


def add_tool_entries(frame, kind, pid):
    """The viewer's tool's entries into panel pid."""
    new = SPEC[kind].entries(frame.shell)
    if not new:
        frame.shell.say(SPEC[kind].none, True)
        return
    add(frame, pid, new)


def _parcel_source(shell):
    have = {x.get("name") for p in de.panels_of(shell.doc, "line")
            for x in p.get("layers") or [] if fg.is_parcels(x)}
    src = shell.ed._parcel_series_source(have)
    if src is None:
        shell.say("No parcel set yet: choose some in the viewer's <b>Parcels</b> tab first.",
                  True)
    return src


def add_data(frame, kind, pid):
    """A series or profile of your own (observations, another model) in panel pid, open."""
    shell = frame.shell
    if kind == "profile":
        e = _as_doc(shell, "profile", fg.profile_table_defaults(_count(shell, "profile")))
    else:
        e = fg.table_defaults(_count(shell, "line"))
        e.pop("panel", None)
        e = dict(e, type="series")
    add(frame, pid, [e])


def add_parcels(frame, pid):
    shell = frame.shell
    v = shell.v
    src = _parcel_source(shell)
    if src is None:
        return
    var = "w" if "w" in v.pf.vars else next(n for n in v.pf.vars if n != "mtime")
    e = fg.parcel_series_defaults(src, var, v.pf.units(var), 0, _count(shell, "line"))
    e.pop("panel", None)
    add(frame, pid, [dict(e, type="series", runs=[own_run(shell)])])


def add_budget(frame, pid, how):
    """The w budget of the next parcel set, a series per term, in panel pid."""
    shell = frame.shell
    src = _parcel_source(shell)
    if src is None:
        return
    out = []
    for e in fg.w_budget_entries(shell.v.pf, src, how, 0, 0):
        e.pop("panel", None)
        out.append(dict(e, type="series", runs=[own_run(shell)]))
    add(frame, pid, out)


def add_from_series_tool(frame, kind, pid, key):
    shell = frame.shell
    add(frame, pid, [series_entry(shell, kind, dict(shell.v.series[key]["recipe"]))])


# ------------------------------------------------------------ a run each
def one_per_run(shell, kind, pid, j):
    """A series or profile of several runs split into one per run; of one, a copy for each
    other.  A time-height panel: a copy of the panel for each other run."""
    doc = shell.doc
    if len(doc["runs"]) < 2:
        shell.say(NO_RUNS, True)
        return
    trial = de.plain(doc)
    if kind == "th":
        if not de.panel_per_run(trial, pid):
            shell.say("Every run has this series already.", True)
            return
        shell.edit(lambda d: de.panel_per_run(d, pid), node=shell.node)
        return
    fn = de.profile_per_run if kind == "profile" else de.series_per_run
    if not fn(trial, de.panel_by_id(trial, pid), j):
        shell.say("Each run has this profile in this panel already." if kind == "profile"
                  else "Every run has this series already.", True)
        return
    shell.edit(lambda d: fn(d, de.panel_by_id(d, pid), j), node=shell.node)


def _per_run_button(shell, kind, pid, j, lay):
    if kind not in ("th", "line", "profile") or fg.is_table(lay) or fg.is_parcels(lay):
        return []
    tip = ("A copy of this panel for each other run, down its column" if kind == "th" else
           "Of several runs: one for each run, in the runs' colours; of one run: a copy for "
           "each other run, at the same time since time zero")
    return [button("One per run", lambda: one_per_run(shell, kind, pid, j), tip)]


# ------------------------------------------------------------ the tool
def panel_word(kind):
    """What a new panel of the kind is called on its button."""
    return (KINDS[kind].head or "Time–height") if kind in SERIES else SPEC[kind].one


def kind_layers(frame, doc, kind):
    """All <kind>: its panels, adding one, a panel for each of the viewer's tool's entries."""
    spec = SPEC[kind]
    mine = de.panels_of(doc, kind)
    names = nodes.letters(doc)
    tools = [button(f"+ {panel_word(kind)} panel",
                    lambda: add_panel(frame, kind),
                    "In the first free cell, or a new row or column" + (
                        ": nothing is computed until it has a series" if kind in SERIES
                        else ""), primary=True)]
    if spec.tool:
        tools.append(button(spec.tool, lambda: add_tool_panels(frame, kind), spec.tool_tip))
    objs = [note(f"Each panel has {spec.head.lower()} of its own: pick a panel (click it in the "
                 "preview) to add, change or remove them."),
            pn.FlexBox(*tools, sizing_mode="stretch_width")]
    for p in mine:
        lays = figdraw.panel_layers(doc, p)
        words = ", ".join(nodes.layer_name(lay, frame.shell.fields) for _, lay in lays) or \
            f"no {spec.head.lower()} yet"
        objs.append(button(f"Panel {names[p['id']]}: {words}"[:80],
                           lambda i=p["id"]: frame.pick(f"panel:{i}")))
    return objs


def _panel_tools(frame, doc, kind, pid):
    """What a panel has above its entries."""
    shell = frame.shell
    spec = SPEC[kind]
    lays = de.places(doc, de.panel_by_id(doc, pid))
    if kind == "th":
        if lays:
            more = " Only the first is drawn." if len(lays) > 1 else ""
            return [note("A time-height panel shows one series: <b>Copy this panel</b> (Layout) "
                         f"for another.{more}")]
        return [note("One series, of one run. Nothing is computed until there is one."),
                pn.FlexBox(button("+ Series", lambda: add(frame, pid, [new_entry(shell, kind)]),
                                  primary=True), *_from_series_tool(frame, kind, pid),
                           sizing_mode="stretch_width")]
    tools = [button(f"+ {spec.one}", lambda: add(frame, pid, [new_entry(shell, kind)]),
                    primary=True)]
    if spec.tool:
        tools.append(button(spec.tool, lambda: add_tool_entries(frame, kind, pid)))
    if kind in ("line", "profile"):
        tools.append(button("+ Your data", lambda: add_data(frame, kind, pid),
                            f"A {'series' if kind == 'line' else 'profile'} of your own "
                            "(observations, another model): paste "
                            f"{'time' if kind == 'line' else 'height'} and value columns or "
                            "load a CSV file"))
    if kind == "line":
        v = shell.v
        if v.pf is not None:
            tools.append(button("+ Parcels", lambda: add_parcels(frame, pid),
                                "A variable of a parcel set over the parcel times: its mean or "
                                "median, a band, and parcels' own lines"))
            if v.pf.has_budget():
                budget = pn.widgets.MenuButton(
                    name="+ w budget", button_type="light", button_style="outline", height=30,
                    margin=(4, 4), items=[("Rates: Dw/Dt, b, vpg, the rest", "rates"), (
                        "Integrated since the set's time: Δw, ∫b, ∫vpg, ∫rest", "int")])
                budget.on_click(lambda ev: add_budget(frame, pid, ev.new))
                tools.append(budget)
        tools += _from_series_tool(frame, kind, pid)
    objs = [note(spec.note), pn.FlexBox(*tools, sizing_mode="stretch_width")]
    if not lays:
        objs.append(note(f"No {spec.head.lower()} here: add one above."
                         + (" Nothing is computed until then." if kind in SERIES else "")))
    return objs


def _from_series_tool(frame, kind, pid):
    """A menu of the viewer's Series tool's series, when it has any."""
    have = getattr(frame.shell.v, "series", {}) or {}
    if not have:
        return []
    menu = pn.widgets.MenuButton(name="+ From the Series tool", button_type="light",
                                 button_style="outline", height=30, margin=(4, 4),
                                 items=[(s["label"], key) for key, s in have.items()])
    menu.on_click(lambda ev: add_from_series_tool(frame, kind, pid, ev.new))
    return [menu]


def _moves(shell, kind, pid, j, n):
    def step(fn, *args):
        shell.edit(lambda d: fn(d, de.panel_by_id(d, pid), j, *args), node=shell.node)

    moves = dict(remove=lambda: step(de.remove_in_panel))
    if kind != "th":  # (a second series there isn't drawn)
        moves["copy"] = lambda: step(de.copy_in_panel)
    if j > 0:
        moves["up"] = lambda: step(de.move_in_panel, -1)
    if j < n - 1:
        moves["down"] = lambda: step(de.move_in_panel, 1)
    return moves


def _entry_extras(frame, kind, pid, j):
    """Above an entry's settings: which of the kind's panels it is in (it moves there), One per
    run."""
    shell = frame.shell
    doc = shell.doc
    p = de.panel_by_id(doc, pid)
    lays = figdraw.panel_layers(doc, p)
    if j >= len(lays):
        return []
    objs = []
    mine = de.panels_of(doc, kind)
    if kind != "th" and len(mine) > 1:
        names = nodes.letters(doc)
        pick = pn.widgets.Select(name="In panel", value=pid, width=140,
                                 options={names[q["id"]]: q["id"] for q in mine},
                                 description="Move it to another panel of this kind")
        pick.param.watch(lambda ev: shell.edit(
            lambda d: de.move_entry(d, pid, j, ev.new), node=f"panel:{ev.new}"), "value")
        objs.append(pick)
    objs += _per_run_button(shell, kind, pid, j, lays[j][1])
    return [pn.Row(*objs, margin=0)] if objs else []


def panel_layers(frame, doc, where, node):
    """A panel's entries (a layer node: that entry alone)."""
    from .tools import Item
    from . import drawer as D
    shell, pid, kind = frame.shell, where.pid, where.kind
    p = de.panel_by_id(doc, pid)
    lays = figdraw.panel_layers(doc, p)
    if node.startswith("layer:"):
        j = where.layer
        return [*_entry_extras(frame, kind, pid, j),
                frame.drawer(where, D.rows_at(doc, where), opened=_first_sections(doc, where))
                .panel]
    objs = [head(SPEC[kind].head), *_panel_tools(frame, doc, kind, pid)]
    for j, (_, lay) in enumerate(lays):
        w = Where("panel", kind, pid, layer=j)
        objs.append(Item(frame, f"p:{pid}:{j}",
                         f"{j + 1}. {nodes.layer_name(lay, shell.fields)}", w,
                         D.rows_at(doc, w), _moves(shell, kind, pid, j, len(lays)),
                         extras=lambda j=j: _entry_extras(frame, kind, pid, j),
                         opened=len(lays) == 1).card)
    return objs


def _first_sections(doc, where):
    from . import drawer as D
    secs = list(dict.fromkeys(r.section for r in D.rows_at(doc, where)))
    return secs[:2]
