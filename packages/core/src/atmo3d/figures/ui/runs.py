"""The Runs tool: the figure's runs, each its path, its settings (the schema's run rows: label,
colour, time zero, track) and what it holds; how several runs line up; adding and removing
one."""

import html
import os

import panel as pn

from ...theme import GRID
from ..schema.where import Where
from ..shell import docedit as de, nodes
from . import drawer as D
from .parts import note

LINE_UP = {"Time since each run's time zero": "time", "Output number": "output"}


def runs(frame, doc):
    """The Runs tool's contents."""
    shell = frame.shell
    used, names = nodes.runs_used(doc), nodes.letters(doc)
    rs = doc.get("runs") or []
    objs = [_line_up(shell, doc)] if len(rs) > 1 else []
    objs += [_run(frame, doc, r, k, used.get(r["id"], []), names) for k, r in enumerate(rs)]
    have = {os.path.abspath(r["path"]) for r in rs}
    others = shell.ed._other_runs(have)
    if others:
        pick = pn.widgets.Select(name="Add a run", options=others, sizing_mode="stretch_width")
        add = pn.widgets.Button(name="Add", width=70, align="end", button_type="primary",
                                button_style="outline")
        add.on_click(lambda ev: shell.add_run(pick.value, node=nodes.RUNS))
        objs.append(pn.Row(pick, add, margin=0, sizing_mode="stretch_width"))
    return objs


def _line_up(shell, doc):
    """How the runs line up: by time zero, or output number (each run lists its outputs)."""
    w = pn.widgets.Select(
        name="Line runs up by", width=240, options=LINE_UP,
        value="output" if any(r.get("outputs_s") for r in doc["runs"]) else "time",
        description="Time since time zero: a run's output at the same time since its time "
                    "zero. Output number: the nth output of each run, whatever its model "
                    "time; times are labelled with the first run's, and past a shorter "
                    "run's end its panels are blank")

    def on_pick(ev):
        def apply(d):
            style = d.setdefault("style", {})
            style.pop("time_match", None)
            for r in d["runs"]:
                r.pop("outputs_s", None)
            if ev.new == "output":
                style["time_match"] = "output"
                for r in d["runs"]:
                    run = shell.ed.open_run(r["path"])[0]
                    r["outputs_s"] = [float(t) for t in run.times]
        shell.edit(apply, node=nodes.RUNS)

    w.param.watch(on_pick, "value")
    return w


def _run(frame, doc, r, k, used, names):
    shell, rid = frame.shell, r["id"]
    path = os.path.abspath(r["path"])
    own = path == shell.ed.run.path
    where = Where("figure", item=rid)
    rows = D.rows_at(doc, where, "run")
    lined = bool(r.get("outputs_s")) and k > 0  # (by output number: the first run's time zero)
    drawer = frame.drawer(where, rows, opened=("Runs",))  # (its few settings: open)
    if lined:
        _t0_greyed(drawer)
    head = pn.pane.HTML(f'<div style="overflow-wrap:anywhere"><b>{k + 1}.</b> '
                        f'<code>{html.escape(path)}</code>'
                        + ('<span class="cv-hint"> (this viewer\'s run)</span>' if own else "")
                        + "</div>", margin=(6, 4, 0, 4), sizing_mode="stretch_width",
                        min_width=0)
    objs = [pn.Row(head, _remove(shell, doc, r, names), margin=0, sizing_mode="stretch_width"),
            drawer.panel]
    if lined:
        objs.append(note("Its time zero is the first run's: the runs line up by output "
                         "number."))
    objs.append(note(_about(shell, r, used, names)))
    return pn.Column(*objs, margin=(2, 0), sizing_mode="stretch_width",
                     styles={"border-bottom": f"1px solid {GRID}"})


def _t0_greyed(drawer):
    """A run's time zero shown but not to be changed (once its section's controls exist)."""
    def grey(*_):
        for sec in drawer.sections:
            for rid, ctl in sec.ctls.items():
                if rid.endswith("t0_min"):
                    for w in ctl.parts:
                        w.disabled = True
    grey()
    for sec in drawer.sections:
        sec.card.param.watch(grey, "collapsed")


def _remove(shell, doc, r, names):
    """A run's ✕.  Panels of that run alone go with it (Undo brings them back); it stays
    when it is the figure's last run, or every panel is of it."""
    rid = r["id"]
    gone = de.panels_of_run(doc, rid)
    words = ", ".join(names.get(i, str(i)) for i in gone)
    every = bool(gone) and len(gone) == len(doc.get("panels") or [])
    rm = pn.widgets.Button(name="✕", width=32, height=28, margin=(2, 1), button_type="default",
                           button_style="outline", disabled=len(doc["runs"]) < 2 or every,
                           description="Every panel is of this run: add others first" if every
                           else f"Remove the run and panel {words}" if gone
                           else "Remove the run")

    def remove(ev):
        shell.edit(lambda d: de.remove_run(d, rid), node=nodes.RUNS)
        shell._sync_fields()
        what = html.escape(nodes.run_names(dict(runs=[r]))[rid])
        shell.say(f"Removed {what} and panel {html.escape(words)} (Undo brings them back)."
                  if gone else f"Removed {what}.")

    rm.on_click(remove)
    return rm


def _about(shell, r, used, names):
    """What a run holds, and the panels showing it."""
    where = "not used yet" if not used else "panel " + ", ".join(names[i] for i in used)
    try:
        run, _ = shell.ed.open_run(r["path"])
    except Exception as e:  # noqa: BLE001
        return f'<span style="color:#f87171">{html.escape(str(e))}</span>'
    return (f"{len(run.times)} outputs, {run.times[0] / 60:g}–{run.times[-1] / 60:g} min · "
            f"{run.ni}×{run.nj}×{run.nk}, dx {run.dx:g} m · {where}")
