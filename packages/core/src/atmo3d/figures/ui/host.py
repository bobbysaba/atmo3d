"""The drawer's host on the figure shell (figures/shell/frame.py): the document and its undo,
and what the controls offer of the figure's runs (figures/ui/drawer.py says what a host
gives).  The test page's host with no viewer is samples.Host."""

from ...core import vectors
from ...core.services import parcels as P
from .. import choices as C
from ..schema import fills
from ..shell import docedit as de, nodes


class ShellHost:
    def __init__(self, shell):
        self.shell = shell

    # ---- the document
    @property
    def doc(self):
        return self.shell.doc

    @property
    def fields(self):
        return self.shell.fields

    def edit(self, fn):
        self.shell.edit(fn)

    def say(self, text, err=False):
        self.shell.say(text, err)

    @property
    def ctx(self):
        """What fills need of the runs: the fields, the map's view, the parcel sets."""
        v, ed = self.shell.v, self.shell.ed
        pf = getattr(v, "pf", None)
        times = {}
        for r in self.doc.get("runs") or []:
            try:
                times[r["id"]] = [float(t) for t in ed.open_run(r["path"])[0].times]
            except Exception:  # noqa: BLE001  (a run that can't be opened: its panels say)
                continue
        return fills.Context(
            fields=self.fields, view=_map_view(v), pick=lambda c: _pick(ed, c),
            shown=lambda pid: self.shell.placing.shown_area(pid),
            parcel_units=(lambda n: pf.units(n) if pf.has(n) else "") if pf is not None
            else None, times=times)

    # ---- what controls offer
    def options(self, name, where):
        doc, F = self.doc, self.fields
        if name == "levelmodes":
            return C.TERRAIN_LEVEL_MODES if F is not None and "zmsl" in F else C.LEVEL_MODES
        if name == "vectors":
            return vectors.options(F) if F is not None else {}
        if name == "frames":
            return vectors.frames(self._run(self.run_of(where)))
        if name == "sections":
            from .. import spec as fg
            return {f"{k + 1}: {s.get('label') or fg.describe(s)}": sid
                    for k, (sid, s) in enumerate((doc.get("sections") or {}).items())}
        if name.startswith("layers:"):
            types = name[7:].split(",")
            out = {"the first that is on": ""}
            for n, (lid, lay) in enumerate((doc.get("layers") or {}).items()):
                if lay.get("type") in types:
                    out[f"{n + 1}. {nodes.layer_name(lay, F)}"] = lid
            return out
        return {}

    def runs(self):
        names = nodes.run_names(self.doc)
        return {f"{k + 1}. {names[r['id']]}": r["id"]
                for k, r in enumerate(self.doc.get("runs") or [])}

    def run_of(self, where, key=None):
        """The run id a place's times are of: a layer's own (key: a key of it naming one, as
        minus.run), else its panel's, else the figure's first."""
        from ..schema import where as W
        doc = self.doc
        if where is not None and where.layer is not None and key:
            lay = W.layer_at(doc, where) or {}
            got = W.dig(lay, key.split("."))
            if got is not None:
                return got
        p = W.panel_of(doc, where.pid) if where is not None and where.pid is not None else None
        if p is not None and p.get("run") is not None:
            return p["run"]
        runs = doc.get("runs") or []
        return runs[0]["id"] if runs else None

    def times(self, run_id):
        doc = self.doc
        rid = run_id if run_id is not None else (doc.get("runs") or [{}])[0].get("id")
        try:
            k = de.run_index(doc, rid)
        except (StopIteration, ValueError, KeyError):
            k = 0
        return self.shell.time_opts(k)

    def _run(self, rid):
        try:
            r = self.doc["runs"][de.run_index(self.doc, rid)]
            return self.shell.ed.open_run(r["path"])[0]
        except Exception:  # noqa: BLE001
            return None

    def track_files(self, where):
        """A run's (where.item) track files found beside it, and whether it is the viewer's
        run (which can follow the viewer's track)."""
        import os
        from ... import config
        r = next((x for x in self.doc.get("runs") or [] if x["id"] == where.item), None)
        if r is None:
            return [], False
        return config.track_files(r["path"]), \
            os.path.abspath(r["path"]) == self.shell.ed.run.path

    def viewer_storm(self):
        return self.shell.ed._viewer_storm()

    def psets(self, where):
        from ..sources import parcel_sets
        from ..schema import where as W
        lay = W.layer_at(self.doc, where) if where is not None and where.layer is not None \
            else {}
        return parcel_sets(self.shell.v, lay or {})

    def values(self, row, where):
        """The Values table of a series or profile (ui/values.py)."""
        from . import values
        return values.control(self.shell, row, where)

    def pvars(self, where):
        out = {}
        for group in P.var_choices(getattr(self.shell.v, "pf", None)).values():
            out.update(group)
        return out


def _pick(ed, choice):
    from ..sources import parcel_pick
    return parcel_pick(ed, choice) if choice else None


def _map_view(v):
    """The viewer's map view (x0, x1, y0, y1), or None."""
    fig = getattr(v, "fig", None)
    try:
        xr, yr = fig.x_range, fig.y_range
        return float(xr.start), float(xr.end), float(yr.start), float(yr.end)
    except (AttributeError, TypeError, ValueError):
        return None

