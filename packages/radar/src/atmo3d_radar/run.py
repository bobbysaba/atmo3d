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

from . import beam, cfradial, ppi, sampler, scene

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
    sampled = True  # (atmo3d_radar.sampler: sections, constant-height maps, 3D)
    storm_relative = False  # (no storm motion for radar yet)
    height_units = "km above the radar"

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

    def load_volumes(self, names, t, progress=None, cancelled=None):
        """Read the volumes of `names` at time t into the cache (core.run.Run's, one at
        a time here).  False once cancelled."""
        names = [n for n in dict.fromkeys(names) if n in self.vars]
        todo = [n for n in names if self.cached(n, t) is None]
        for i, n in enumerate(todo):
            if cancelled is not None and cancelled():
                return False
            if progress is not None:
                progress(i, len(todo), n)
            self.volume(n, t)
        if progress is not None and todo:
            progress(len(todo), len(todo), "")
        return not (cancelled is not None and cancelled())

    # ------------------------------------------------------------------ the sampler
    def sampling(self):
        """(method, max_gap_km) of the sampler, from the settings (radar_sampling,
        radar_max_gap_km; 0: every gap between sweeps bridged)."""
        from atmo3d import config
        m = str(config.get("radar_sampling") or "linear").strip().lower()
        g = config.get("radar_max_gap_km")
        try:
            g = 0.0 if g in (None, "", "auto") else max(0.0, float(g))
        except (TypeError, ValueError):
            g = 0.0
        return (m if m in sampler.METHODS else "linear"), g

    def sample(self, vol, t, x, y, z):
        """Values of time t's volume vol (sweeps, rays, gates) at x, y, z (km; z above
        the radar), broadcast: atmo3d_radar.sampler with the settings' method and gap."""
        m, g = self.sampling()
        return sampler.sample(self, vol, t, x, y, z, m, g)

    def view_note(self):
        """How the views off the sweeps come about, for their titles."""
        m, g = self.sampling()
        return (f"native, {m} between sweeps" if not g else
                f"native, {m}; gaps over {g:g} km left empty")

    # ------------------------------------------------------------------ the map
    def map_window(self, view, maxpix):
        """The map's pixels for a view (core.render.view_window on a grid)."""
        return ppi.window(self, view, maxpix)

    def map_plane(self, F, name, t, mode, level, win, storm=None):
        """x, y, (ny, nx) of field `name` (display units) on the map's pixels win:
          "sweep"   sweep `level` (its index), each pixel the gate it falls in;
          "height"  `level` km above the radar, through the sampler (a CAPPI);
          "colmax", "colmin"  the most / least of the sweeps over each pixel (the
                    column max of reflectivity: composite reflectivity)."""
        if mode == "sweep":
            a = F.plane(name, t, "sweep", level, storm=storm)
            return ppi.raster(self, a, t, int(level), win)
        x, y = ppi.pixels(win)
        if mode == "height":
            X, Y = np.meshgrid(x, y)
            return x, y, F.take(name, t, lambda v: self.sample(v, t, X, Y, float(level)),
                                storm)
        if mode in ("colmax", "colmin"):
            return x, y, F.take(name, t, lambda v: ppi.reduce_sweeps(
                self, v, t, win, mode[3:]), storm)
        raise ValueError(f"a radar map shows sweeps, heights or column extremes, not "
                         f"{mode!r}")

    def level_text(self, t, mode, level):
        """A map title's level: " @ 0.5° sweep", " @ 3 km", " column max"."""
        if mode == "height":
            return f" @ {level:g} km"
        if mode in ("colmax", "colmin"):
            return f" column {mode[3:]} (of the sweeps)"
        sw = self.sweeps(t)
        k = int(level)
        return f" @ {sw.label(k)} sweep" if 0 <= k < len(sw) else f" @ sweep {k}"

    # ------------------------------------------------------------------ sections
    def section_points(self, A, B, max_pts=1200):
        """(s, x, y, (ex, ey)) of a section from A to B (km): points about half a gate
        apart (core.render.section_coords: fi, fj on a grid; x, y km here)."""
        (xa, ya), (xb, yb) = A, B
        L = float(np.hypot(xb - xa, yb - ya))
        dr = float(np.median(np.diff(self.ranges))) if len(self.ranges) > 1 else 1.0
        n = int(min(max_pts, max(2, np.ceil(L / (dr / 2)) + 1)))
        s = np.linspace(0.0, L, n)
        e = ((xb - xa) / max(L, 1e-9), (yb - ya) / max(L, 1e-9))
        return s, xa + e[0] * s, ya + e[1] * s, e

    def sample_section(self, vol, t, x, y, zq):
        """(nz, n) of time t's volume at the section's points x, y (km) and heights zq."""
        zq = np.asarray(zq, np.float64)
        return self.sample(vol, t, np.asarray(x)[None, :], np.asarray(y)[None, :],
                           zq[:, None])

    # ------------------------------------------------------------------ 3D
    def build_scene(self, F, spec, progress=None, cancelled=None, cache=None):
        """A 3D scene (core.volume3d.build_scene): atmo3d_radar.scene."""
        return scene.build_scene(self, F, spec, progress, cancelled, cache)

    def scene_stride(self, box, t=0):
        """The stride a 3D scene of region box takes on its own (its "Auto")."""
        return scene.auto_stride(self, t, tuple(box))

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
