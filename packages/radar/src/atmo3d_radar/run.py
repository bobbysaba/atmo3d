"""The radar reader: a folder of CfRadial volumes as a PolarRun (core.run.Source).

Native polar is the source of truth (atmo3d-plan.md section 2): a field at one time is
(sweeps, rays, gates) float32 (atmo3d_radar.cfradial), cached whole like a grid run's
3D fields.  The radar site is the origin: x east, y north (km) on the radar-centred
azimuthal-equidistant plane, z (km) above the radar's level (atmo3d_radar.beam).  Views
that are not a sweep go through a sampler (Phase 6 step 4); a sweep alone is read
cheaply with read_sweep (the PPI panel, step 3).
"""
import os

import netCDF4
import numpy as np

from atmo3d.core.run import IO_LOCK, MissingAtTime, Source, VarInfo

from . import beam, cfradial, ppi

# fields computed from the sweep table and the beam model, not read from the files
# (hidden: for checking the geometry)
GEOMETRY = {
    "beam_height": ("Beam height above the radar", "km"),
    "ground_range": ("Ground distance from the radar", "km"),
    "ray_azimuth": ("Ray azimuth", "degrees"),
}

ZTOP_MAX = 20.0  # km: the top of height-based views (sections, 3D) at most


def _site(d):
    def num(name):
        v = d.variables.get(name)
        return float(np.asarray(v[...]).ravel()[0]) if v is not None else float("nan")
    return num("latitude"), num("longitude"), num("altitude")


def _gate_vars(d):
    """{name: VarInfo} of the (time, range) fields of an open file."""
    out = {}
    for n, v in d.variables.items():
        if v.dimensions != ("time", "range"):
            continue
        long = (getattr(v, "long_name", "") or getattr(v, "standard_name", "") or n)
        out[n] = VarInfo(n, str(long), str(getattr(v, "units", "")), 3, None, 1,
                         dict(v.__dict__))
    return out


class PolarRun(Source):
    """A folder of radar volumes, one CfRadial file per time.

      valid      UTC time of each volume (from its file name)
      site       (lat, lon, altitude m) of the radar
      ranges     (ng,) slant range of each gate centre (km)
      sweeps(t)  the sweep table at time t (cfradial.Sweeps; 13 or 14 sweeps here)
      volume(name, t)       (sweeps, rays, gates) float32
      read_sweep(name, t, k) (rays, gates) float32 of one sweep"""

    model = "radar"
    model_label = "Radar"
    OFFERS = frozenset({"native_polar"})
    storm_relative = False  # (no storm motion for radar yet)

    def __init__(self, path, cache_gb=12.0, workers=None, cache=None):
        super().__init__(path, cache_gb, workers, cache)
        found = cfradial.files_in(self.path)
        if not found:
            raise FileNotFoundError(f"no CfRadial volumes in {self.path}")
        self.valid = [w for w, _ in found]
        self.files = [f for _, f in found]
        self.times = np.array([(w - self.valid[0]).total_seconds() for w in self.valid],
                              dtype=np.float64)
        # (only the first file's header is read here: the others are taken to hold the
        # same fields until a time is read, in_file, sweeps)
        with IO_LOCK, netCDF4.Dataset(self.files[0]) as d:
            d.set_auto_mask(False)
            self.attrs = {k: d.getncattr(k) for k in d.ncattrs()}
            self.site = _site(d)
            self.ranges = np.asarray(d["range"][:], np.float64) / 1000.0
            self._sweeps = {0: cfradial.Sweeps(d)}
            self.vars = _gate_vars(d)
        self._names = {0: frozenset(self.vars)}  # time -> its file's (time, range) fields
        for n, (long, units) in GEOMETRY.items():
            self.vars[n] = VarInfo(n, long, units, 3, None, 1, {"computed": "beam model"})
        lat, lon, alt = self.site
        self.geo = beam.geo(lat, lon) if np.isfinite(lat) and np.isfinite(lon) else None
        if self.geo is not None:
            self.geo.limits = self.extent
            self.geo.spacing = float(np.median(np.diff(self.ranges))) if len(self.ranges) > 1 else None
        name = self.attrs.get("instrument_name", "")
        name = name.decode() if isinstance(name, bytes) else str(name)
        self.instrument = name.strip() or "radar"
        self.note = (f"Native {self.instrument} volumes, one file per time, shown on their "
                     f"sweeps. Heights are above the radar ({alt:.0f} m above sea level); "
                     f"each volume's time is the one in its file name.")

    # ------------------------------------------------------------------ meta
    def time_label(self, t):
        w = self.valid[t]
        return f"{w:%H:%M:%S} UTC" if w.second else f"{w:%H:%M} UTC"

    def sweeps(self, t):
        """The sweep table of time t (read once per time)."""
        sw = self._sweeps.get(t)
        if sw is None:
            with IO_LOCK:
                d = self._ds(t)
                sw = cfradial.Sweeps(d)
                self._names.setdefault(t, frozenset(_gate_vars(d)))
            self._sweeps[t] = sw
        return sw

    def in_file(self, name, t):
        """Whether time t's file has field `name` (a time not read yet: as the first
        file).  The GEOMETRY fields are at every time."""
        if name in GEOMETRY:
            return True
        names = self._names.get(t)
        return name in (names if names is not None else self.vars)

    def _file_check(self, name, t):
        """_check after time t's file was opened (sweeps), so its own fields are known."""
        self.sweeps(t)
        self._check(name, t)

    # ------------------------------------------------------------------ io
    def _geometry(self, name, sw, ks):
        """A GEOMETRY field on sweeps ks: (len(ks), nr, ng)."""
        ng = len(self.ranges)
        out = np.empty((len(ks), sw.nr, ng), np.float32)
        for i, k in enumerate(ks):
            if name == "ray_azimuth":
                out[i] = sw.az[k][:, None]
                continue
            h, s = beam.gate_position(self.ranges, sw.elev[k])
            out[i] = (h if name == "beam_height" else s)[None, :]
            out[i][~np.isfinite(sw.az[k])] = np.nan  # (padding rays)
        return out

    def _read_volume_local(self, name, t):
        self._file_check(name, t)
        sw = self.sweeps(t)
        if name in GEOMETRY:
            return self._geometry(name, sw, range(len(sw)))
        with IO_LOCK:
            return cfradial.read_volume(self._ds(t)[name], sw)

    def read_sweep(self, name, t, k):
        """Sweep k (native order: by elevation) of a field at time t: (nr, ng) float32.
        Reads only that sweep unless the whole volume is cached."""
        vol = self.cached(name, t)
        if vol is not None:
            return vol[k]
        self._not_writing(t)
        self._file_check(name, t)
        sw = self.sweeps(t)
        if not 0 <= k < len(sw):
            raise MissingAtTime(name, t, f"the volume at {self.time_label(t)} has "
                                         f"{len(sw)} sweeps (no sweep {k})")
        if name in GEOMETRY:
            return self._geometry(name, sw, [k])[0]
        with IO_LOCK:
            return cfradial.read_sweep(self._ds(t)[name], sw, k)

    # ------------------------------------------------------------------ the map
    def map_window(self, view, maxpix):
        """The map's pixels for a view (core.render.view_window on a grid)."""
        return ppi.window(self, view, maxpix)

    def map_crop(self, a, win, t, mode, level):
        """x, y, (ny, nx) of a plane `a` (Fields.plane) on the map's pixels win
        (core.render._crop on a grid): a sweep (mode "sweep", level: its index)."""
        if mode != "sweep":
            raise ValueError(f"a radar map shows sweeps, not {mode!r}")
        return ppi.raster(self, a, t, int(level), win)

    def level_text(self, t, mode, level):
        """A map title's level: " @ 0.5° sweep" ."""
        sw = self.sweeps(t)
        k = int(level)
        return f" @ {sw.label(k)} sweep" if 0 <= k < len(sw) else f" @ sweep {k}"

    # ------------------------------------------------------------------ neutral facts
    @property
    def extent(self):
        r = float(beam.gate_position(self.ranges[-1], 0.0)[1]) if len(self.ranges) else 0.0
        return -r, r, -r, r

    @property
    def ztop(self):
        sw = self._sweeps[0]
        top = float(np.nanmax(beam.gate_position(self.ranges[-1], sw.elev)[0]))
        return min(top, ZTOP_MAX)

    @property
    def nsweeps(self):
        """Sweeps of a volume, as the first one has them (the sweep choices; a volume
        cut short lacks its top ones, read_sweep)."""
        return len(self._sweeps[0])

    @property
    def size_label(self):
        sw = self._sweeps[0]
        return f"{len(sw)} sweeps × {sw.nr} rays × {len(self.ranges)} gates"

    @property
    def field_bytes(self):
        sw = self._sweeps[0]
        return 4 * len(sw) * sw.nr * len(self.ranges)


def count(path):
    return len(cfradial.files_in(path)) if os.path.isdir(path) else 0
