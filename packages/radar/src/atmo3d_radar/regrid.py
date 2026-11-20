"""Regrid (optional, off by default): a radar folder's volumes on a regular grid, as a grid
Run every grid feature works on (derivatives of the retrieved winds, series, figures).

Native polar stays the source of truth (atmo3d-plan.md section 2): a regridded run is
another run of the same folder, opened only when asked for (the Native / Regridded
switch, after a dialog that confirms the settings), never behind the user's back.

  * Its path names its settings: <folder>/regrid_<method>_dx<km>_dz<km>_r<km>_gap<km>,
    e.g. .../regrid_linear_dx0.5_dz0.5_r150_gap0.  So the settings travel with anything
    that records the run (sessions, figure bundles, exports, the address), and the
    regridded arrays' cache key holds them.
  * The grid: x, y from -range to +range around the radar every dx (km), heights z at
    the middle of layers dz deep from the radar's level up to the radar run's top
    (atmo3d_radar.run.ZTOP_MAX at most); points beyond the maximum range are empty.
  * Each value is the sampler's (atmo3d_radar.sampler: the method within a sweep,
    linear in elevation between sweeps, gaps wider than the gap setting left empty;
    gap 0: every gap bridged).
  * A field at a time is regridded when first read (about 1-2 s on a 150 km, 0.5 km
    grid) and kept in the 3D cache like any volume, and as a .npy file under the cache
    folder (cache_dir/regrid/<folder key>/<settings>/, at most DISK_GB of them): its
    name holds the source file's time of change and size, so a rewritten volume is
    regridded again.

Settings (core.config): radar_regrid_method, radar_regrid_dx, radar_regrid_dz,
radar_regrid_range, radar_regrid_max_gap.
"""
import os
import re
import tempfile
from dataclasses import dataclass

import numpy as np

from atmo3d.core.run import Run, VarInfo, file_key

from . import sampler

PREFIX = "regrid_"
DISK_GB = 4.0  # the cache files of one regridded run at most (cache_dir may be in home)
_NAME = re.compile(r"^regrid_(linear|nearest)_dx([0-9.]+)_dz([0-9.]+)_r([0-9.]+)_gap([0-9.]+)$")
LIMITS = dict(dx=(0.1, 10.0), dz=(0.05, 5.0), range=(5.0, 1000.0), gap=(0.0, 100.0))
DEFAULTS = dict(method="linear", dx=0.5, dz=0.5, range=150.0, gap=0.0)


def _num(v):
    return f"{float(v):g}"


@dataclass(frozen=True)
class Settings:
    """How a radar folder is regridded (method within a sweep, dx and dz km, maximum
    range km, max_gap km: 0 bridges every gap between sweeps)."""
    method: str = "linear"
    dx: float = 0.5
    dz: float = 0.5
    range: float = 150.0
    gap: float = 0.0

    def __post_init__(self):
        if self.method not in sampler.METHODS:
            raise ValueError(f"regrid method {self.method!r}: one of {sampler.METHODS}")
        for k in ("dx", "dz", "range", "gap"):
            lo, hi = LIMITS[k]
            v = float(getattr(self, k))
            if not lo <= v <= hi:
                raise ValueError(f"regrid {k} {v:g} km: from {lo:g} to {hi:g}")

    @property
    def name(self):
        """The regridded run's folder name: what its path and cache key hold."""
        return (f"{PREFIX}{self.method}_dx{_num(self.dx)}_dz{_num(self.dz)}"
                f"_r{_num(self.range)}_gap{_num(self.gap)}")

    @property
    def label(self):
        """'linear, 0.5 km × 0.5 km' (the views' "regridded: ..." label)."""
        return f"{self.method}, {_num(self.dx)} km × {_num(self.dz)} km"

    @property
    def long_label(self):
        gap = f"gaps over {_num(self.gap)} km empty" if self.gap else "every gap bridged"
        return (f"{self.method}; {_num(self.dx)} km across, {_num(self.dz)} km deep; "
                f"out to {_num(self.range)} km; {gap}")

    def sizes(self, ztop):
        """(ni, nk, MB of one field at one time) on a top at ztop km."""
        ni = len(axis(self.range, self.dx))
        nk = max(1, int(round(ztop / self.dz)))
        return ni, nk, 4.0 * ni * ni * nk / 1e6


def axis(rng, dx):
    """x (or y) of a grid out to rng km every dx km, centred on the radar."""
    n = int(np.floor(rng / dx + 1e-9))
    return np.arange(-n, n + 1) * float(dx)


def parse(path):
    """(radar folder, Settings) of a regridded run's path, or None."""
    p = os.path.abspath(path).rstrip("/")
    m = _NAME.match(os.path.basename(p))
    if not m:
        return None
    try:
        s = Settings(m.group(1), float(m.group(2)), float(m.group(3)), float(m.group(4)),
                     float(m.group(5)))
    except ValueError:
        return None
    return os.path.dirname(p), s


def path_of(folder, settings):
    return os.path.join(os.path.abspath(folder), settings.name)


def from_config():
    """The settings in core.config (their defaults where unset or out of range)."""
    from atmo3d import config

    def get(k, key, kind=float):
        v = config.get(key)
        if v in (None, "", "auto"):
            return DEFAULTS[k]
        try:
            return kind(v)
        except (TypeError, ValueError):
            return DEFAULTS[k]

    vals = dict(method=str(get("method", "radar_regrid_method", str)).strip().lower(),
                dx=get("dx", "radar_regrid_dx"), dz=get("dz", "radar_regrid_dz"),
                range=get("range", "radar_regrid_range"),
                gap=get("gap", "radar_regrid_max_gap"))
    try:
        return Settings(**vals)
    except ValueError:
        return Settings()


def to_config(s):
    """The values of core.config's settings file for Settings s (config.save takes)."""
    return dict(radar_regrid_method=s.method, radar_regrid_dx=s.dx, radar_regrid_dz=s.dz,
                radar_regrid_range=s.range, radar_regrid_max_gap=s.gap)


_NATIVE = {}  # (in a reader process) folder -> its PolarRun, for a regrid there


def _native(folder):
    run = _NATIVE.get(folder)
    if run is None:
        from .run import PolarRun
        run = _NATIVE[folder] = PolarRun(folder, 2.0, 1)
    return run


def regrid_volume(native, name, t, settings, xh, yh, z):
    """Field `name` at time t of native run `native` on the grid xh, yh (km), z (km
    above the radar): (nk, nj, ni) float32, empty beyond the maximum range."""
    vol = native.volume(name, t)
    X, Y = np.meshgrid(xh, yh)
    far = np.hypot(X, Y) > settings.range
    out = np.empty((len(z), len(yh), len(xh)), np.float32)
    for k, zk in enumerate(z):
        out[k] = sampler.sample(native, vol, t, X, Y, float(zk), settings.method,
                                settings.gap)
        out[k][far] = np.nan
    return out


def load_or_regrid(native, name, t, settings, xh, yh, z, fn):
    """regrid_volume, through the cache file fn (written when there is room: DISK_GB
    for the folder fn is in)."""
    shape = (len(z), len(yh), len(xh))
    try:
        a = np.load(fn)
        if a.shape == shape:
            return a
    except (OSError, ValueError):
        pass
    a = regrid_volume(native, name, t, settings, xh, yh, z)
    try:
        d = os.path.dirname(fn)
        os.makedirs(d, mode=0o755, exist_ok=True)
        with os.scandir(d) as it:  # (one folder: this run's settings)
            used = sum(e.stat().st_size for e in it if e.name.endswith(".npy"))
        if used + a.nbytes > DISK_GB * 1024**3:
            return a  # (the cache is full: in memory only)
        fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
        with os.fdopen(fd, "wb") as f:
            np.save(f, a)
        os.replace(tmp, fn)
    except OSError:  # (no room or no folder: kept in memory only)
        pass
    return a


class _Var:
    """One field of a regridded time, as a dataset variable: [0, ...] regrids it."""

    def __init__(self, src, name):
        self.src, self.name = src, name
        self.shape = (1, len(src.z), len(src.yh), len(src.xh))
        self.dimensions = ("time", "z", "y", "x")
        self._a = None

    def __getitem__(self, key):
        if self._a is None:
            self._a = self.src.field(self.name)
        return self._a[None][key]


class _Dataset:
    """One regridded time, dataset-like (core.run.open_source: d.variables, d[name])."""

    def __init__(self, src):
        self.variables = {n: _Var(src, n) for n in src.names}

    def __getitem__(self, name):
        return self.variables[name]

    def close(self):
        self.variables = {}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


class _Source:
    """What core.run opens for one regridded time: in this process through the run (its
    3D cache), in a reader process (pickled, e.g. a time series) on its own, through
    the cache files."""

    def __init__(self, run, t):
        self.run, self.t = run, t
        self.folder, self.settings = run.folder, run.settings
        self.xh, self.yh, self.z = run.xh, run.yh, run.z
        self.names = list(run.vars)
        self.files = {n: run.cache_path(n, t) for n in self.names}

    def __getstate__(self):
        d = dict(self.__dict__)
        d["run"] = None  # (a reader process regrids on its own)
        return d

    def field(self, name):
        if self.run is not None:
            return self.run.volume(name, self.t)
        return load_or_regrid(_native(self.folder), name, self.t, self.settings,
                              self.xh, self.yh, self.z, self.files[name])

    def key(self):
        return None  # (not kept open by a reader: a field read is a whole regrid)

    def open(self):
        return _Dataset(self)


class RegriddedRun(Run):
    """A radar folder regridded with the Settings its path names (module notes).  Its
    native run (PolarRun, sharing the 3D cache) supplies times, fields and volumes."""

    model = "radar"
    OFFERS = frozenset()
    storm_relative = False
    open_max = 2
    height_units = "km above the radar"

    def __init__(self, path, cache_gb=12.0, workers=None, cache=None):
        from .run import GEOMETRY, PolarRun
        got = parse(path)
        if got is None:
            raise FileNotFoundError(f"{path} is not a regridded radar run "
                                    f"(<folder>/{PREFIX}...)")
        folder, self.settings = got
        # (regridding runs here, numba-threaded: no reader processes)
        super().__init__(path, cache_gb, 1, cache)
        self.native = nat = PolarRun(folder, cache_gb, 1, self._vc)
        self.folder = nat.path
        self.files, self.valid, self.times = nat.files, nat.valid, nat.times
        self.attrs, self.site, self.instrument = nat.attrs, nat.site, nat.instrument
        self.busy = []
        s = self.settings
        rng = min(s.range, nat.extent[1])
        self.xh = axis(rng, s.dx)
        self.yh = self.xh.copy()
        nk = max(2, int(round(nat.ztop / s.dz)))
        self.zf = np.arange(nk + 1) * s.dz
        self.z = 0.5 * (self.zf[1:] + self.zf[:-1])
        self._grid_done()
        # every gate field but the beam-model ones (meaningless off their gates); a
        # level comes from the whole regridded volume (one regrid per field and time)
        self.vars = {n: VarInfo(n, v.long_name, v.units, 3, None, 1 << 20, dict(v.attrs))
                     for n, v in nat.vars.items() if n not in GEOMETRY}
        self.geo = None
        if nat.geo is not None:
            from .beam import geo
            self.geo = geo(*nat.site[:2])
            self.geo.limits = self.extent
            self.geo.spacing = s.dx
        self.model_label = f"Radar, regridded ({s.label})"
        lat, lon, alt = nat.site
        self.note = (f"{nat.instrument} volumes regridded ({s.long_label}) from their "
                     f"native sweeps; heights above the radar ({alt:.0f} m above sea "
                     f"level). Native polar is the source: switch back with "
                     f"Native in the toolbar.")

    # ------------------------------------------------------------------ meta
    def time_label(self, t):
        return self.native.time_label(t)

    def in_file(self, name, t):
        return self.native.in_file(name, t)

    def view_note(self):
        return f"regridded: {self.settings.label}"

    def source(self, t):
        return _Source(self, t)

    def terrain_height(self):
        return np.zeros((self.nj, self.ni), np.float32)

    # ------------------------------------------------------------------ io
    def cache_path(self, name, t):
        """The .npy file of field `name` at time t regridded (its name: the source
        file's time of change and size)."""
        from atmo3d import config
        from atmo3d.config import run_key
        _, mtime, size = file_key(self.files[t])
        return config.cache_dir("regrid", run_key(self.folder), self.settings.name,
                                f"{name}.t{t:03d}.{mtime}.{size}.npy")

    def regridded(self, name, t):
        """Field `name` at time t on the grid (nk, nj, ni) float32: from the cache file,
        else regridded from the native volume (and saved there)."""
        self._check(name, t)
        return load_or_regrid(self.native, name, t, self.settings, self.xh, self.yh,
                              self.z, self.cache_path(name, t))

    def _read_volume_local(self, name, t):
        return self.regridded(name, t)
