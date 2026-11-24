"""Figure editor: the runs a figure could add (found in the background), what a run's storm track
gives, and the fields of all a figure's runs (AllFields).

A mixin of the FigureEditor (figures/editor.py)."""

import os
import threading
from collections import OrderedDict

from .. import config, registry
from ..core import models
from ..core.fields import deriv_def, group_options, split_deriv


TYPE_PATH = "type a path"  # (the track list's "Type a path…": never a full path)


def _track_path(value):
    """A track box's text as a full path ("" when blank)."""
    value = (value or "").strip()
    return os.path.abspath(os.path.expanduser(os.path.expandvars(value))) if value else ""


def _track_options(found):
    """The track list's choices {label: value}: files by name, with their folder when
    two folders have the same name."""
    names = [os.path.basename(p) for p in found]
    labels = {(n if names.count(n) == 1 else
               os.path.join(os.path.basename(os.path.dirname(p)), n)
               + f" ({os.path.dirname(os.path.dirname(p))})"): p
              for n, p in zip(names, found)}
    return {"None": ""} | labels | {"Type a path…": TYPE_PATH}


class AllFields:
    """The fields of every run of a figure (the viewer's run's first), for the field
    lists: a field only some runs have is listed too, marked as such (its panels in the
    other runs say they have no such field)."""

    def __init__(self, fields):
        self.defs, self._some = OrderedDict(), set()
        self._fields = list(fields)
        from ..core.catalog import Union
        self.cat = Union(F.cat for F in self._fields)
        for F in fields:
            if hasattr(F, "sync_user"):  # (user fields a figure brought: core.userfields)
                F.sync_user()
            for name, d in F.defs.items():
                self.defs.setdefault(name, d)
        for name in self.defs:
            if any(name not in F for F in fields):
                self._some.add(name)

    def __getitem__(self, name):
        d = self.defs.get(name) if isinstance(name, str) else None
        if d is None:
            op, base = split_deriv(name)
            d = deriv_def(op, self.defs[base]) if op and base in self.defs else None
            if d is None:
                raise KeyError(name)
        return d

    def __contains__(self, name):
        try:
            self[name]
        except KeyError:
            return False
        return True

    def role(self, r):
        """The field playing role r in the first run that has one, else None."""
        return next((n for n in (F.role(r) for F in self._fields) if n), None)

    def groups(self, ndim=None):
        def label(d):
            some = " · not in every run" if d.name in self._some else ""
            return f"{d.label} [{d.name}]{some}"
        # (user fields no run can compute: greyed out, with the first run's reason)
        off, seen = [], set(self.defs)
        for F in self._fields:
            for u, why in getattr(F, "user_off", ()):
                if u["name"] not in seen:
                    seen.add(u["name"])
                    off.append((u, why))
        return group_options(self.defs.values(), ndim, label, off=off)


class FigureRuns:
    """The runs a figure could add, and storm tracks."""

    _scanned, _scan_complete, _scan_new, _cands, _cand_labels = [], True, False, [], {}

    def _scan_roots(self):
        """Look for the runs under the runs_root setting in the background (as the Open
        dialog does); the run lists offer them when it is done."""
        roots = list(config.get("runs_root") or [])
        if not roots:
            self._scanned = []
            self._find_runs()
            return
        self._find_runs()  # (next to this run, and recent, meanwhile)

        def job():
            runs, complete = config.scan_runs(roots)

            def done():
                self._scanned, self._scan_complete = runs, complete
                self._find_runs()

            if self.v.doc is not None:
                self.v._schedule(done)
            else:  # (picked up the next time the list is asked for)
                self._scanned, self._scan_complete, self._scan_new = runs, complete, True

        threading.Thread(target=job, daemon=True, name="atmo3d-runscan").start()

    def _find_runs(self):
        """Runs the figure could add: under runs_root, next to this run, and recent."""
        out = []
        own = models.root_of(self.run.path)  # (a WoFS member's experiment: its members
        sibs = registry.sibling_runs(self.run.path)  # are listed one by one instead)
        for p in list(self._scanned) + sibs + registry.recent_runs():
            p = os.path.abspath(p)
            if p not in out and (p != own or own == self.run.path):
                out.append(p)
        self._cands = out
        # (members by name: "<experiment> · Member 5")
        m = models.MODELS.get(self.run.model)
        self._cand_labels = {} if own == self.run.path or m is None else {
            p: f"{os.path.basename(own)} · {m.part_label(p)}" for p in sibs}

    def _other_runs(self, have):
        """{label: path} of the runs not in the figure (have: the paths of the runs in it)."""
        if self._scan_new:
            self._scan_new = False
            self._find_runs()
        roots = [config.expand(r).rstrip("/" + os.sep) + os.sep
                 for r in config.get("runs_root") or []]
        out = {}
        for p in self._cands:
            if p in have:
                continue
            lab = self._cand_labels.get(p) or \
                next((p[len(r):].replace(os.sep, "/") for r in roots if p.startswith(r)),
                     None) or "/".join(p.replace(os.sep, "/").rstrip("/").split("/")[-2:])
            out[lab if lab not in out else p] = p
        return out

    def _track_words(self, e, run=None):
        """What a run entry's storm track gives (HTML): its fixes and times, or why none."""
        if run is None:
            try:
                run, _ = self.open_run(e["path"])
            except Exception as ex:  # noqa: BLE001
                return f'<span style="color:#f87171">{ex}</span>'
        fx = self.run_fixes(e, run)
        tr = e.get("track") or ""
        path = _track_path(tr) if tr != "viewer" else ""
        if path in self.data.track_err:
            return f'<span style="color:#f87171">track: {self.data.track_err[path]}</span>'
        if not tr:
            return "no track (storm-centred panels stay empty)"
        what = f"storm {e['storm']}, " if e.get("storm") and tr != "viewer" else ""
        note = f"track: {what}{len(fx)} fix{'es' if len(fx) != 1 else ''}"
        if fx:
            ts = sorted(fx)
            note += f" ({run.times[ts[0]] / 60:g}–{run.times[ts[-1]] / 60:g} min)"
        return note
