"""CfRadial volumes: finding the files, the sweep table, reading a field natively.

One file is one volume (one time).  What the reader relies on, from the Phase 4 survey
of the KTLX files (docs-dev/radar-spike.md section 1):

  * Rays come from the sweep table (sweep_start_ray_index .. sweep_end_ray_index), never
    from the length of `time`: files pad it with rays whose angles and data are masked.
  * The number of sweeps can change from one time to the next (a volume cut short).
  * A sweep's elevation is the median of its rays' measured elevations, which differ
    from fixed_angle by up to 0.2 degrees.
  * A volume's time is the one in its file name (Bobby, 2026-11-19), e.g.
    combined_radar_object_advcor_9_20260404_020040.nc or
    cfrad.20260404_020040.000_to_....nc (the first stamp); files without one fall back
    to time_coverage_start.

Native storage is (sweeps, rays, gates) float32, NaN where missing: sweeps sorted by
elevation (stable, so repeated elevations keep the file's order), rays sorted by
azimuth within each sweep, padded with NaN rays when sweeps have fewer rays than the
longest one.
"""
import datetime as dt
import functools
import os
import re

import numpy as np

STAMP = re.compile(r"(?<!\d)(\d{8})[_T-]?(\d{6})(?!\d)")
SUFFIXES = (".nc", ".nc4", ".cdf")


def name_time(fname):
    """The UTC time stamped in a file name (the first YYYYMMDD_HHMMSS), or None."""
    m = STAMP.search(os.path.basename(fname))
    if not m:
        return None
    try:
        return dt.datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S")
    except ValueError:
        return None


def candidate(fname):
    """From the name alone: could this file be a CfRadial volume?"""
    b = os.path.basename(fname)
    return b.lower().endswith(SUFFIXES) and (b.startswith("cfrad.")
                                            or name_time(b) is not None)


@functools.lru_cache(maxsize=256)
def _is_cfradial(path, _key):
    import netCDF4
    try:
        with netCDF4.Dataset(path) as d:
            return ("sweep_start_ray_index" in d.variables and "range" in d.dimensions
                    and "time" in d.dimensions)
    except (OSError, RuntimeError):
        return False


def is_cfradial(path):
    """Whether `path` is a CfRadial file (its header has a sweep table)."""
    try:
        st = os.stat(path)
    except OSError:
        return False
    return _is_cfradial(os.fspath(path), (st.st_mtime_ns, st.st_size))


def coverage_start(d):
    """time_coverage_start of an open file as a datetime, or None."""
    name, s = "time_coverage_start", None
    v = d.variables.get(name)
    if v is not None:
        a = v[...]
        s = a.tobytes().decode(errors="ignore") if hasattr(a, "tobytes") else str(a)
    elif name in d.ncattrs():
        s = str(d.getncattr(name))
    s = (s or "").strip("\x00 ").rstrip("Z")
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return dt.datetime.strptime(s[:19], fmt)
        except ValueError:
            pass
    return None


def files_in(path, names=None):
    """[(UTC time, file path)] of the CfRadial volumes in folder `path`, by time.  Only
    the first candidate's header is read (the rest are taken on their names), and files
    without a time in their name are opened for time_coverage_start."""
    if names is None:
        try:
            names = os.listdir(path)
        except OSError:
            return []
    cands = sorted(n for n in names if candidate(n))
    if not cands or not is_cfradial(os.path.join(path, cands[0])):
        return []
    out = []
    for n in cands:
        f = os.path.join(path, n)
        w = name_time(n)
        if w is None:
            import netCDF4
            try:
                with netCDF4.Dataset(f) as d:
                    w = coverage_start(d)
            except OSError:
                w = None
        if w is not None:
            out.append((w, f))
    out.sort()
    return out


def _filled(v, key):
    """v[key] of netCDF variable v as float32, NaN where netCDF4's masking says the
    value is missing (_FillValue, or the type's default fill when the variable has none,
    missing_value, valid_min/valid_max), with scale_factor/add_offset applied.  (The
    run's files are opened unmasked, core.run.open_source: masking is turned on here,
    per variable.)"""
    v.set_auto_maskandscale(True)
    a = v[key]
    return np.ma.filled(np.ma.asarray(a).astype(np.float32), np.nan)


class Sweeps:
    """One volume's sweep table, in native order (sorted by elevation).

    index    (ns,) the file's sweep number of each
    start, stop  (ns,) its rays: start .. stop - 1 in the file
    elev     (ns,) median measured elevation (deg)
    fixed    (ns,) the file's fixed_angle (deg; NaN if none)
    nyquist  (ns,) median Nyquist velocity (m/s; NaN if none)
    az       (ns, nr) ray azimuths (deg), ascending; NaN padding
    order    [ns] each sweep's rays in azimuth order (indices from start)
    nr       rays of the longest sweep"""

    def __init__(self, d):
        s0 = np.asarray(d["sweep_start_ray_index"][:], dtype=np.int64)
        s1 = np.asarray(d["sweep_end_ray_index"][:], dtype=np.int64) + 1
        ev, av = d["elevation"], d["azimuth"]
        lo, hi = int(s0.min()), int(s1.max())
        el_all = _filled(ev, slice(lo, hi)).astype(np.float64)
        az_all = _filled(av, slice(lo, hi)).astype(np.float64)
        fixed = (_filled(d["fixed_angle"], slice(None)).astype(np.float64)
                 if "fixed_angle" in d.variables else np.full(len(s0), np.nan))
        nyq = None
        if "nyquist_velocity" in d.variables:
            nv = d["nyquist_velocity"]
            nyq = _filled(nv, slice(lo, hi)).astype(np.float64)
        elev, nyquist, azs, orders = [], [], [], []
        for a, b in zip(s0, s1):
            e = el_all[a - lo:b - lo]
            elev.append(float(np.nanmedian(e)) if np.isfinite(e).any() else np.nan)
            nyquist.append(float(np.nanmedian(nyq[a - lo:b - lo]))
                           if nyq is not None and np.isfinite(nyq[a - lo:b - lo]).any()
                           else np.nan)
            az = az_all[a - lo:b - lo]
            o = np.argsort(az, kind="stable")  # (NaN azimuths last)
            orders.append(o)
            azs.append(az[o])
        elev = np.array(elev)
        keep = np.argsort(np.where(np.isfinite(elev), elev, np.inf), kind="stable")
        self.index = keep
        self.start, self.stop = s0[keep], s1[keep]
        self.elev, self.fixed = elev[keep], fixed[keep]
        self.nyquist = np.array(nyquist)[keep]
        self.order = [orders[k] for k in keep]
        self.nr = max((len(o) for o in self.order), default=0)
        self.az = np.full((len(keep), self.nr), np.nan)
        for i, k in enumerate(keep):
            self.az[i, :len(azs[k])] = azs[k]
        self.lo, self.hi = lo, hi

    def __len__(self):
        return len(self.index)

    def label(self, k):
        """A sweep's name in a list: its measured elevation, e.g. "0.5°" ."""
        return f"{self.elev[k]:.1f}°"


def read_sweep(v, sw, k):
    """Sweep k (native order) of netCDF variable v: (nr, ng) float32, rays by azimuth,
    padded with NaN rays to sw.nr."""
    a, b = int(sw.start[k]), int(sw.stop[k])
    raw = _filled(v, (slice(a, b), slice(None)))
    out = np.full((sw.nr, raw.shape[1]), np.nan, np.float32)
    out[:b - a] = raw[sw.order[k]]
    return out


def read_volume(v, sw):
    """Every sweep of netCDF variable v: (ns, nr, ng) float32 (one read of the rays the
    sweep table covers)."""
    raw = _filled(v, (slice(sw.lo, sw.hi), slice(None)))
    out = np.full((len(sw), sw.nr, raw.shape[1]), np.nan, np.float32)
    for i in range(len(sw)):
        a, b = int(sw.start[i]) - sw.lo, int(sw.stop[i]) - sw.lo
        out[i, :b - a] = raw[a:b][sw.order[i]]
    return out
