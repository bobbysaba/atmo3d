"""The reader: a folder of gridded netCDF files as a core.run.Run.

The layout it reads (synthetic.py writes a small run of it):

  files   <folder>/gridded_*.nc (model.PATTERN); each holds one or more times, and
          together they are in time order once sorted by their times
  dims    time (unlimited), z, y, x; z_stag (the w levels: one more than z)
  coords  time(time) in "seconds since <date and time>" (CF); x(x), y(y) in m;
          z(z), z_stag(z_stag) in m above ground, the same in every column
  fields  (time, z, y, x) 3D on the scalar points, (time, z_stag, y, x) 3D on the w
          levels, (time, y, x) 2D; a field may be in some files only

What the core needs from a Run is in docs/datatypes.md ("The reader").  In short: set
files, times, xh, yh, z, zf, vars (and var_times, attrs), call _grid_done(), and make
every field readable as d[name][0, ...] from what source(t) opens.  The core then reads
in its reader processes, caches, destaggers, and computes the derived fields.

A copy for files of another layout changes the constants below and, if need be,
_info() and TimeView; the rest stays."""
import glob
import os

import netCDF4
import numpy as np

from atmo3d.core.run import IO_LOCK, Run, VarInfo, file_key

from .model import PATTERN, TIME

# REQUIRED to match your files (as model.PATTERN and model.TIME do): each dimension
# name, and the axis it runs along.  A staggered dimension (one more point than the
# scalar one: cell faces) says so with True; the core averages such fields onto the
# scalar points.  (x and y staggers work the same: "x_stag": ("x", True).)
AXES = {"z": ("z", False), "z_stag": ("z", True), "y": ("y", False), "x": ("x", False)}
# REQUIRED: the coordinate variables, and the factor that makes each km
X, Y, Z, ZSTAG = "x", "y", "z", "z_stag"
TO_KM = 1e-3  # (the files' coordinates are in m)

# optional: unit changes on read, {field: (factor, units after)}.  A field playing a role
# must be in the role's units (core.catalog.ROLES: winds m/s, theta K, pressure Pa,
# mixing ratios kg/kg); these files write vapour in g/kg.
CONVERT = {"qv": (1e-3, "kg/kg")}


class ExampleRun(Run):
    """A folder of gridded netCDF files (the layout above)."""

    # REQUIRED: the Model's key, and the type's name in run details
    model = "example"
    model_label = "Example gridded netCDF"
    # optional: capabilities (core.capabilities.CAPS) this data type offers.  Each is
    # usable on a run that has its inputs: soundings need the roles theta, pres, qv, u
    # and v; tracking needs w.  ("parcels" with traced_parcels = True traces trajectories
    # through the winds, as WoFS does.)
    OFFERS = frozenset({"soundings", "tracking"})
    # optional, with their defaults (core.run.Source): terrain = False (levels at one
    # height everywhere), geo = None (no map projection: x, y in km), storm_relative =
    # True, note = "", height_units = "km AGL"

    def __init__(self, path, cache_gb=12.0, workers=None, cache=None):
        # REQUIRED first: the core's set-up (cache, reader processes, empty vars ...)
        super().__init__(path, cache_gb, workers, cache)
        paths = sorted(glob.glob(os.path.join(self.path, PATTERN)))
        if not paths:
            raise FileNotFoundError(f"no {PATTERN} files in {self.path}")

        # every time of every file: (valid time, file, index in the file), and the
        # fields each file has (one metadata pass; read no data here)
        slots, names, infos = [], {}, {}
        with IO_LOCK:  # (netCDF / HDF5 is not thread safe: every open in the core's lock)
            for f in paths:
                with netCDF4.Dataset(f) as d:
                    tv = d[TIME]
                    when = netCDF4.num2date(tv[:], tv.units, only_use_cftime_datetimes=False,
                                            only_use_python_datetimes=True)
                    slots += [(w, f, i) for i, w in enumerate(np.atleast_1d(when))]
                    names[f] = set()
                    for n, v in d.variables.items():
                        info = _info(n, v)
                        if info is not None:
                            names[f].add(n)
                            infos.setdefault(n, info)
            with netCDF4.Dataset(paths[0]) as d:
                # REQUIRED: the grid, in km (x, y increasing; z, zf heights above ground)
                self.xh = np.asarray(d[X][:], dtype=np.float64) * TO_KM
                self.yh = np.asarray(d[Y][:], dtype=np.float64) * TO_KM
                self.z = np.asarray(d[Z][:], dtype=np.float64) * TO_KM
                self.zf = np.asarray(d[ZSTAG][:], dtype=np.float64) * TO_KM
                # optional: global attributes (shown with the run's details)
                self.attrs = {k: d.getncattr(k) for k in d.ncattrs()}
        slots.sort(key=lambda s: s[0])

        # REQUIRED: one entry per time.  files[t] is also what says a time changed (its
        # stat), so a file holding several times appears once for each.
        self.files = [f for _, f, _ in slots]
        self._index = [i for _, _, i in slots]  # (the time's index in its file)
        self.valid = [w for w, _, _ in slots]  # (for time_label)
        # REQUIRED: seconds since the first time, strictly increasing
        self.times = np.array([(w - self.valid[0]).total_seconds() for w in self.valid])
        # REQUIRED: {name: VarInfo} of every field
        self.vars = infos
        # REQUIRED when some times lack a field: {name: frozenset of time indices}
        for n in infos:
            ts = frozenset(t for t, f in enumerate(self.files) if n in names[f])
            if len(ts) < len(self.files):
                self.var_times[n] = ts
        # REQUIRED last: the grid's sizes and spacing from xh, yh, z
        self._grid_done()
        # optional: self.nml (a namelist, {} by default), self.fcor (one Coriolis
        # parameter, 1/s; or map the fcor role to a 2D field), self.umove, self.vmove
        # (grid motion, m/s)

    def source(self, t):
        """What a reader process opens for time t: by default the path files[t], whose
        fields the core reads as d[name][0] (one time per file).  These files hold
        several times, so the source says which; it must pickle (it goes to the reader
        processes), so it holds names, not open files."""
        return TimeSource(self.files[t], self._index[t])

    def time_label(self, t):
        """optional: how a time reads in the viewer (default: H:MM:SS since the first)."""
        w = self.valid[t]
        return f"{w:%Y-%m-%d %H:%M} UTC"


def _info(name, v):
    """The VarInfo of a netCDF variable that is a field (2D or 3D, time first), else
    None (coordinates, anything else).  core.run.var_info does this for files whose
    dimension names the core knows (core.run.STAG_DIMS); these files' names are their
    own, so the reader says what they mean (AXES)."""
    dims = v.dimensions
    if len(dims) not in (3, 4) or dims[0] != TIME or not all(x in AXES for x in dims[1:]):
        return None
    axes = tuple(AXES[x][0] for x in dims[1:])
    if axes not in (("y", "x"), ("z", "y", "x")):
        return None
    stag = next((AXES[x][0] for x in dims[1:] if AXES[x][1]), None)
    ch = v.chunking()
    # levels per chunk: a field stored many levels to a chunk is read whole
    zchunk = int(ch[1]) if len(dims) == 4 and ch != "contiguous" else 1
    units = CONVERT[name][1] if name in CONVERT else getattr(v, "units", "")
    return VarInfo(name, getattr(v, "long_name", name), units, len(dims) - 1, stag,
                   zchunk, dict(v.__dict__))


class TimeSource:
    """One time of one file: what the reader processes open (core.run.open_source)."""

    def __init__(self, path, index):
        self.path, self.index = path, index

    def open(self):
        return TimeView(self.path, self.index)

    def key(self):
        """What a reader process keeps the open file under between reads (core.run.opened):
        its first item names this time, the rest change when the file does."""
        path, mtime, size = file_key(self.path)
        return (f"{path}#{self.index}", mtime, size)


class TimeView:
    """A file seen at one of its times, as the core reads a file of one time:
    d.variables, d[name][0, ...] (that time), a context manager."""

    def __init__(self, path, index):
        self._d = netCDF4.Dataset(path)
        self._d.set_auto_mask(False)  # (fill values are made NaN in _AtTime instead)
        self.index = index
        self.variables = self._d.variables

    def __getitem__(self, name):
        return _AtTime(self._d[name], self.index, CONVERT.get(name, (1.0,))[0])

    def close(self):
        if self._d.isopen():
            self._d.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


class _AtTime:
    """A (time, ...) variable indexed as if its only time were `index`: v[0, ...] is
    v[index, ...], as float32, fill values NaN, units converted."""

    def __init__(self, v, index, factor=1.0):
        self._v, self._index, self._factor = v, index, factor
        self.shape = (1,) + tuple(v.shape[1:])  # (the core asks a field's shape)
        self._fill = getattr(v, "_FillValue", None)

    def __getitem__(self, key):
        key = key if isinstance(key, tuple) else (key,)
        if key[0] != 0:  # (the core always reads its one time, 0)
            raise IndexError(f"time index {key[0]!r}: this view has one time, 0")
        a = np.asarray(self._v[(self._index,) + key[1:]], dtype=np.float32)
        if self._fill is not None:
            a = np.where(a == np.float32(self._fill), np.float32(np.nan), a)
        return a * np.float32(self._factor) if self._factor != 1.0 else a
