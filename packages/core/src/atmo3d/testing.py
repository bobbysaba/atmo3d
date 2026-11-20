"""Checks for data-type packages (part of the extension API, docs/datatypes.md).

    from atmo3d.testing import check_datatype
    check_datatype("mytype", folder)      # a test of a new data type: one line

check_datatype opens `folder` the way the viewer does (through the registry, by the
data type's key) and goes through what the core needs from a data type: that it is
registered and declares its API version, that its Model finds the folder, that the run
has times, fields and the neutral facts, a grid's coordinates (when it has a grid), a
field catalog whose roles name the run's fields, capabilities the core knows, one field
read, a derived field computed, one map and one cross-section built.  It collects every
problem before failing, so one run of it lists them all.

It reads one or two fields at one time: on a real run of a large grid, run it on a
compute node.  It writes nothing (no settings, no recent-runs list)."""

import os
import pickle

import numpy as np

__all__ = ["check_datatype", "CheckFailed", "Report"]


class CheckFailed(AssertionError):
    """check_datatype found problems; the message lists them (and its Report is .report)."""

    def __init__(self, report):
        super().__init__(str(report))
        self.report = report


class Report:
    """What check_datatype found: `problems` fail the check, `warnings` do not (things
    the data type may mean, but should know), `notes` say what was checked."""

    def __init__(self, key, folder):
        self.key, self.folder = key, folder
        self.problems, self.warnings, self.notes = [], [], []

    @property
    def ok(self):
        return not self.problems

    def __str__(self):
        head = (f"check_datatype({self.key!r}, {self.folder!r}): "
                + ("passed" if self.ok else f"{len(self.problems)} problem(s)"))
        out = [head]
        for title, items in (("problems", self.problems), ("warnings", self.warnings),
                             ("checked", self.notes)):
            if items:
                out.append(f"  {title}:")
                out += [f"    - {s}" for s in items]
        return "\n".join(out)


class _Stop(Exception):
    """A problem later steps cannot go on from."""


# roles the core reads as 3D fields when a data type maps them
_ROLES_3D = ("u", "v", "w", "theta", "pres", "qv", "refl")


def check_datatype(model, folder, t=0, cache_gb=1.0):
    """Check data type `model` (its key, or its registered Model) on the run in `folder`,
    at time index t.  Returns a Report; raises CheckFailed listing every problem."""
    from .core import models
    key = model if isinstance(model, str) else getattr(model, "key", None)
    rep = Report(key, folder)
    try:
        m = _registered(rep, models, key, model)
        _found(rep, models, m, folder)
        run, F = _open(rep, models, key, folder, cache_gb)
        _times(rep, run, t)
        _fields(rep, run)
        _facts(rep, run)
        if run.grid:
            _grid(rep, run)
        _catalog(rep, run, F)
        _capabilities(rep, run)
        name = _read(rep, run, t)
        _derived(rep, F, t)
        if name is not None:
            _map(rep, run, F, name, t)
            _section(rep, run, F, name, t)
        _sources(rep, run, t)
    except _Stop as e:
        rep.problems.append(str(e))
    if not rep.ok:
        raise CheckFailed(rep)
    return rep


# ------------------------------------------------------------------ steps
def _registered(rep, models, key, model):
    from . import API_VERSION
    if not key:
        raise _Stop("no data-type key given (a Model's key, e.g. \"cm1\")")
    m = models.MODELS.get(key)
    if m is None:
        raise _Stop(f"{key!r} is not registered: installed data types are "
                    f"{sorted(models.MODELS)}; is the package installed (pip install -e) "
                    f"and its entry point in the \"{models.GROUP}\" group?"
                    + (f" (left out: {models.SKIPPED[key]})" if key in models.SKIPPED
                       else ""))
    if not isinstance(model, str) and model is not m:
        rep.warnings.append(f"the Model given is not the one registered as {key!r}; "
                            f"checked the registered one")
    if not isinstance(m, models.Model):
        rep.problems.append(f"{type(m).__name__} is not a core.models.Model subclass")
    if not m.label:
        rep.problems.append("Model.label is empty (the name the run picker shows)")
    if m.api is None:
        rep.problems.append(f"Model.api is not set: say which extension API the data type "
                            f"is written for (api = \"{API_VERSION}\")")
    else:
        rep.notes.append(f"registered, written for API {m.api} (this core: {API_VERSION})")
    return m


def _found(rep, models, m, folder):
    if not os.path.isdir(folder) and not m.virtual(folder):
        raise _Stop(f"{folder} is not a folder (nor a run {m.key!r} names inside one)")
    if os.path.isdir(folder):
        entries = list(os.scandir(folder))
        if not m.looks(entries):
            rep.problems.append("Model.looks(entries) is False for this folder's listing: "
                                "the run picker will not offer it")
    n = m.count(folder)
    if not n:
        raise _Stop("Model.count(folder) is 0: no output times found")
    got = models.detect(folder)
    if got is not m:
        rep.warnings.append(f"auto-detect opens this folder as {got.key if got else None!r}"
                            f", not {m.key!r} (models try in entry-point name order; it "
                            f"opens as {m.key!r} only when chosen)")
    if not isinstance(m.summary(folder), str):
        rep.problems.append("Model.summary(folder) is not a str")
    parts = m.parts(folder)
    if parts:
        bad = [p for p in parts if not models.exists(p)]
        if bad:
            rep.problems.append(f"Model.parts lists runs that models.exists() does not "
                                f"accept (virtual() should say they are): {bad[:3]}")
        rep.notes.append(f"{len(parts)} runs named inside the folder (parts)")
    rep.notes.append(f"found: {n} output time(s)")


def _open(rep, models, key, folder, cache_gb):
    from .core.fields import Fields
    from .core.run import Source
    try:  # (as the Registry opens it, without its recent-runs list)
        run = models.open_run(folder, key, cache_gb=cache_gb, workers=1)
    except Exception as e:
        raise _Stop(f"opening the run failed: {type(e).__name__}: {e}") from e
    if not isinstance(run, Source):
        raise _Stop(f"Model.open gave a {type(run).__name__}, not a core.run.Source "
                    f"(Run for a grid) subclass")
    if run.model != key:
        rep.problems.append(f"run.model is {run.model!r}, not {key!r} (the run class's "
                            f"`model` must be its Model's key)")
    try:
        F = Fields(run)
    except Exception as e:
        raise _Stop(f"the field list (core.fields.Fields) could not be built for the run: "
                    f"{type(e).__name__}: {e}") from e
    rep.notes.append(f"opened as {type(run).__name__} ({'grid' if run.grid else 'no grid'})")
    return run, F


def _times(rep, run, t):
    times = np.asarray(getattr(run, "times", []), dtype=float)
    files = getattr(run, "files", None)
    if times.ndim != 1 or times.size == 0:
        raise _Stop("run.times is empty (seconds of each time index)")
    if not np.all(np.isfinite(times)) or np.any(np.diff(times) <= 0):
        rep.problems.append("run.times must be finite and strictly increasing")
    if files is not None and len(files) != times.size:
        rep.problems.append(f"run.files has {len(files)} entries for {times.size} times "
                            f"(one per time)")
    if not 0 <= t < times.size:
        raise _Stop(f"time index {t} is not in the run (0 to {times.size - 1})")
    if not isinstance(run.time_label(t), str):
        rep.problems.append("run.time_label(t) is not a str")
    rep.notes.append(f"{times.size} times, {run.time_label(0)} to {run.time_label(times.size - 1)}")


def _fields(rep, run):
    from .core.run import VarInfo
    if not run.vars:
        raise _Stop("run.vars is empty: no fields")
    bad = [n for n, v in run.vars.items() if not isinstance(v, VarInfo)]
    if bad:
        raise _Stop(f"run.vars values must be core.run.VarInfo: {bad[:5]}")
    for n, ts in getattr(run, "var_times", {}).items():
        if n not in run.vars:
            rep.problems.append(f"var_times names {n!r}, which run.vars does not")
        elif not all(0 <= i < len(run.times) for i in ts):
            rep.problems.append(f"var_times[{n!r}] has time indices outside the run")
    n3 = sum(v.ndim == 3 for v in run.vars.values())
    rep.notes.append(f"{len(run.vars)} fields ({n3} 3D)")


def _facts(rep, run):
    try:
        x0, x1, y0, y1 = (float(v) for v in run.extent)
        if not (np.isfinite([x0, x1, y0, y1]).all() and x0 < x1 and y0 < y1):
            rep.problems.append(f"run.extent {run.extent} is not (x0, x1, y0, y1) km with "
                                f"x0 < x1, y0 < y1")
        if not float(run.ztop) > 0:
            rep.problems.append(f"run.ztop is {run.ztop} (km, > 0)")
        if not isinstance(run.size_label, str):
            rep.problems.append("run.size_label is not a str")
        if not int(run.field_bytes) > 0:
            rep.problems.append("run.field_bytes is not > 0")
    except NotImplementedError:
        raise _Stop("a run with no grid must give extent, ztop, size_label and "
                    "field_bytes (core.run.Source)") from None


def _grid(rep, run):
    from .core.run import Run
    if not isinstance(run, Run):
        raise _Stop("run.grid is True but the run is not a core.run.Run")
    for c in ("xh", "yh", "z"):
        a = np.asarray(getattr(run, c, []), dtype=float)
        if a.ndim != 1 or a.size < 2 or np.any(np.diff(a) <= 0):
            rep.problems.append(f"run.{c} must be 1D, at least 2 long and increasing (km)")
    if not hasattr(run, "ni") or not run.dx > 0:
        rep.problems.append("the grid sizes are not set: call self._grid_done() once xh, "
                            "yh and z are")
    zf = getattr(run, "zf", None)
    if zf is None or len(zf) != len(run.z) + 1:
        rep.warnings.append("run.zf (staggered heights) is not one longer than run.z")
    rep.notes.append(f"grid {run.size_label}, dx {run.dx:g} m")


def _catalog(rep, run, F):
    from .core import catalog as C
    C.of_model(run.model)  # (loads the catalogs; falls back to CM1's for an unknown key)
    if run.model not in C.CATALOGS:
        raise _Stop(f"no field catalog registered for {run.model!r}: the run would use "
                    f"CM1's (core.catalog.register(Catalog({run.model!r}, ...)))")
    cat = run.catalog
    have, absent = [], []
    for r in C.ROLES:
        n = cat.name(r)
        if n is None:
            continue
        (have if run.has(n) else absent).append(r)
    if not have:
        rep.problems.append("no role resolves: the catalog's roles name none of the run's "
                            "fields (core.catalog.ROLES: u, v, w, theta, refl...)")
    if absent:
        rep.warnings.append(f"roles named in the catalog but not in this run: "
                            f"{', '.join(f'{r}={cat.name(r)}' for r in absent)}")
    flat = [r for r in _ROLES_3D if r in have and run.vars[cat.name(r)].ndim != 3]
    if flat:
        rep.problems.append(f"roles the core reads as 3D fields are not 3D here: {flat}")
    listed = [n for n in run.vars if n in F.defs]
    if len(listed) != len(run.vars):
        rep.problems.append("some fields of run.vars are missing from the field list")
    rep.notes.append(f"roles: {', '.join(have) or 'none'}; {len(F.defs)} fields listed "
                     f"({len(F.defs) - len(run.vars)} derived)")


def _capabilities(rep, run):
    from .core import capabilities as K
    bad = sorted(set(getattr(run, "OFFERS", ())) - set(K.CAPS))
    if bad:
        rep.problems.append(f"OFFERS names capabilities the core does not know: {bad} "
                            f"(core.capabilities.CAPS)")
        return
    try:
        can = K.of(run)
    except Exception as e:
        rep.problems.append(f"working out the run's capabilities failed: "
                            f"{type(e).__name__}: {e}")
        return
    lacking = [c for c in K.CAPS if K.offers(run, c) and c not in can]
    if lacking:
        rep.warnings.append(f"offered, but this run lacks their inputs: {lacking}")
    if not run.grid:
        hooks = ("map_window", "map_plane", "level_text")
        if run.sampled:
            hooks += ("section_points", "sample_section", "build_scene")
        missing = [h for h in hooks if not callable(getattr(run, h, None))]
        if missing:
            rep.problems.append(f"a run with no grid must give the views' hooks: {missing}")
    rep.notes.append(f"capabilities: {', '.join(sorted(can)) or 'none'}")


def _pick(run):
    """The 3D field the map and section draw: w, else refl, else the first 3D one."""
    for r in ("w", "refl"):
        n = run.role(r)
        if n is not None and run.vars[n].ndim == 3:
            return n
    return next((n for n, v in run.vars.items() if v.ndim == 3), None)


def _read(rep, run, t):
    name = _pick(run)
    if name is None:
        rep.warnings.append("no 3D field: nothing read, no map or section checked")
        return None
    if not run.in_file(name, t):
        rep.warnings.append(f"{name} is not in the files at time index {t}")
        return None
    try:
        vol = run.volume(name, t)
    except Exception as e:
        raise _Stop(f"reading {name} at time {t} failed: {type(e).__name__}: {e}") from e
    if not isinstance(vol, np.ndarray) or vol.dtype != np.float32:
        rep.problems.append(f"run.volume({name!r}, t) must be a float32 numpy array, "
                            f"not {type(vol).__name__} {getattr(vol, 'dtype', '')}")
    elif run.grid and vol.shape != (run.nk, run.nj, run.ni):
        rep.problems.append(f"run.volume({name!r}, t) is {vol.shape}; a grid's fields are "
                            f"(nk, nj, ni) = {(run.nk, run.nj, run.ni)} on the scalar "
                            f"points (destaggered)")
    elif not np.isfinite(vol).any():
        rep.problems.append(f"{name} at time {t} has no finite value")
    else:
        rep.notes.append(f"read {name}: {vol.shape}, {np.nanmin(vol):.4g} to "
                         f"{np.nanmax(vol):.4g}")
    return name


def _derived(rep, F, t):
    d = next((d for d in F.defs.values() if d.derived and d.ndim == 3 and d.pointwise
              and not d.column), None)
    if d is None:
        rep.warnings.append("no derived 3D field is offered (none has its inputs here)")
        return
    try:
        a = F.volume(d.name, t)
    except Exception as e:
        rep.problems.append(f"derived field {d.name} failed: {type(e).__name__}: {e}")
        return
    if not np.isfinite(a).any():
        rep.problems.append(f"derived field {d.name} has no finite value")
    else:
        rep.notes.append(f"derived {d.name} from {', '.join(d.natives)}")


def _map(rep, run, F, name, t):
    from .core import render
    if run.grid:
        mode, level = "height", float(run.z[len(run.z) // 2])
    elif run.offers("native_polar"):
        mode, level = "sweep", 0.0
    elif run.sampled:
        mode, level = "height", float(run.ztop) / 4
    else:
        rep.warnings.append("no grid, sampler or native view: no map to check")
        return
    fill = dict(var=name, mode=mode, level=level, style="image", nlev=12, cmap="viridis",
                rev=False, auto=True, vmin=0, vmax=1, minus=None)
    spec = dict(t=t, view=run.extent, maxpix=120, fill=fill, fills=[], ov=[], vecs=[],
                storm=None, fstorm=None)
    try:
        res = render.compute_map(F, spec)
    except Exception as e:
        rep.problems.append(f"the map of {name} ({mode} {level:g}) failed: "
                            f"{type(e).__name__}: {e}")
        return
    if not res.get("fill"):
        rep.problems.append(f"the map of {name} ({mode} {level:g}) drew nothing")
    else:
        rep.notes.append(f"map of {name}: {mode} {level:g}")


def _section(rep, run, F, name, t):
    from .core import render
    if not run.sampled:
        rep.notes.append("no cross-section (the run is not `sampled`)")
        return
    x0, x1, y0, y1 = run.extent
    ym = (y0 + y1) / 2
    try:
        s, fi, fj, _ = render.section_coords(run, (x0, ym), (x1, ym))
        z0, top, _ = render.section_span(run, fi, fj, float(run.ztop))
        zq = np.linspace(z0, top, 25)
        a = np.asarray(render.section_field(F, name, t, fi, fj, zq))
    except Exception as e:
        rep.problems.append(f"the cross-section of {name} failed: {type(e).__name__}: {e}")
        return
    if a.shape != (zq.size, np.size(s)):
        rep.problems.append(f"the cross-section of {name} is {a.shape}, not "
                            f"(heights, points) = {(zq.size, np.size(s))}")
    elif not np.isfinite(a).any():
        rep.problems.append(f"the cross-section of {name} across the middle has no "
                            f"finite value")
    else:
        rep.notes.append(f"cross-section of {name}: {np.size(s)} points by {zq.size} heights")


def _sources(rep, run, t):
    try:
        pickle.dumps(run.source(t))
    except Exception as e:
        rep.problems.append(f"run.source(t) cannot be pickled, so reader processes cannot "
                            f"open it ({type(e).__name__}: {e})")
