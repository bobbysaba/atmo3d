"""Differences: the map fill or the cross-section fill minus the same field at another
time and/or in another run: the runs it can be taken from, and finding what it subtracts (its
controls: the layer's, figures/schema/viewer.py; what it subtracts: layers.minus_spec).

A mixin of the Viewer (atmo3d/viewer/app.py): its methods use the Viewer's widgets and state."""

import os

from .. import registry
from ..core import models
from ..figures.spec import tindex


class Differences:
    def _minus_runs(self):
        """{label: path} of this run, then the runs next to it and the recent ones."""
        out, here = {"this run": ""}, os.path.abspath(self.run.path)
        own = models.root_of(here)  # (a WoFS member: the others by name, not the folder)
        for p in registry.sibling_runs(self.run.path) + registry.recent_runs():
            p = os.path.abspath(p)
            if p != here and p not in out.values() and (p != own or own == here):
                lab = "/".join(p.rstrip("/").split("/")[-2:])
                if own != here and models.root_of(p) == own:
                    lab = f"{os.path.basename(own)} · {models.part_label(p)}"
                out[lab if lab not in out else p] = p
        return out

    def _minus_ref(self, m, t):
        """{F, t, label} of a minus_spec m (layers.py) at the shown time index t: the other run's
        Fields and output index (an error when it has no output then).  Opens the other
        run (off the page thread)."""
        if m["path"]:
            run, F = self.figed.open_run(m["path"])
        else:
            run, F = self.run, self.F
        ts = float(self.run.times[t])
        where = "" if run is self.run else f" of {run.name}"
        if m["time"] == "prev":
            k = tindex(run, ts)
            if k is None or k == 0:
                raise ValueError(f"difference: {run.name} has no output before "
                                 f"{self.run.time_label(t)}")
            k -= 1
        else:
            want = ts if m["time"] == "" else float(m["time"])
            k = tindex(run, want)
            if k is None:
                s = int(round(want))
                raise ValueError(f"difference: {run.name} has no output at "
                                 f"{s // 3600:d}:{(s % 3600) // 60:02d}:{s % 60:02d}")
        return dict(F=F, t=k, label=f"{run.time_label(k)}{where}")

    @staticmethod
    def _minus_note(m):
        """The title's note on a difference ('' without one)."""
        return f' <span>minus {m["label"]}</span>' if m else ""
