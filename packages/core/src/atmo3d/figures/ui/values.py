"""The Values control of a time series or profile in the drawer: its computed values, a run at a
time, with your edits of them (a value of your own, a point blanked, rows of your own).  The
table is seriesvals.py's; here it works on the document's entry, and each change is one edit of
the shell (entry["edits"], entry["added"])."""

from types import SimpleNamespace

from ..schema import where as W
from ..shell import docedit as de, nodes
from .controls import Ctl
from .seriesvals import ProfileValues, SeriesValues


class _Entry:
    """What the values table asks of its card and editor (it is both), on an entry of the
    document: the entry (runs by place, as the table counts them), the figure's runs and data,
    and a change of its edits."""

    def __init__(self, shell, where):
        self.shell, self.where = shell, where
        self.ed, self._hold = self, False
        self.ent = self.read()

    # (what the table reads of the figure)
    @property
    def data(self):
        return self.shell.ed.data

    @property
    def spec(self):
        return self.shell.doc.get("style") or {}

    def _runs_collect(self):
        return [dict(r) for r in self.shell.doc["runs"]]

    def _run_names(self):
        names = nodes.run_names(self.shell.doc)
        return {f"{k + 1}. {names[r['id']]}": k for k, r in enumerate(self.shell.doc["runs"])}

    def request(self):
        """(The edit, edits_changed, redraws the preview.)"""

    def read(self):
        lay = W.layer_at(self.shell.doc, self.where) or {}
        return de.to_card(self.shell.doc, de.plain(lay))

    def run_list(self):
        """The entry's runs: None for every run, else their places."""
        runs = self.ent.get("runs", de.MISSING)
        if runs is de.MISSING:
            run = self.ent.get("run")
            return None if run is None else [int(run)]
        return None if runs is None else [int(k) for k in runs]

    def collect(self):
        return self.ent

    def edits_changed(self):
        changes = {k: de.plain(self.ent[k]) if self.ent.get(k) else de.MISSING
                   for k in ("edits", "added")}
        where = self.where

        def apply(d):
            p = W.panel_of(d, where.pid)
            de.write_panel(d, p, where.layer, changes)
        self.shell.edit(apply)


def control(shell, row, where):
    """The Values table of the entry at where, open (it reads the values the preview has: nothing
    is computed here)."""
    host = _Entry(shell, where)
    kind = W.kind_at(shell.doc, where)
    vals = (ProfileValues if kind == "profile" else SeriesValues)(host)
    vals.section.param.update(hide_header=True, margin=0)
    vals.section.collapsed = False  # (its widgets made, its values read)

    def put(v):
        now = host.read()
        if all(de.plain(now.get(k)) == de.plain(host.ent.get(k)) for k in ("edits", "added")):
            return
        host.ent = now
        vals.refresh()

    return Ctl(vals.section, get=lambda: SimpleNamespace(), set=put, parts=[])
