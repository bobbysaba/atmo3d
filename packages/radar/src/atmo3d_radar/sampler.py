"""The radar sampler: a volume's values at any points x, y, z (km), natively.

The views that are not one sweep (constant-height maps, cross-sections, columns) ask it
for values at their own points; nothing is regridded (docs-dev/radar-spike.md section 2,
the Phase 4 decisions in section 8):

  * Geometry: atmo3d_radar.beam (4/3 earth; x, y on the radar-centred azimuthal-
    equidistant plane; z above the radar).  A point's (azimuth, elevation, slant range)
    is the exact inverse of the beam model.
  * Within a sweep: bilinear in azimuth and range across the two nearest rays and gates
    ("linear"), or the nearest gate ("nearest").
  * Between sweeps: linear in elevation across the two sweeps around the point
    (gaps bridged, however wide, unless max_gap_km > 0 leaves NaN where the two sweeps
    are further apart vertically than that at the point's range).
  * Up to half a beamwidth below the lowest sweep or above the highest a point takes
    that sweep's value; beyond, NaN.
  * Missing data: a value needs valid neighbours carrying at least half the weight, so
    echo edges fall halfway between gates or sweeps.
  * A gap between two rays wider than GAP_RAYS ray spacings (a sector the sweep lacks)
    gives NaN, as on the PPI (atmo3d_radar.ppi).

  sample(run, vol, t, x, y, z)   values (float32, the shape of x, y, z broadcast)
"""
import math
import threading

import numba
import numpy as np

from . import beam
from .ppi import GAP_RAYS

METHODS = ("linear", "nearest")
_GEOM = {}  # (run path, t, sweeps) -> geometry() of that volume
_LOCK = threading.Lock()


def geometry(run, t):
    """(az (ns, nr) float64, rays (ns,) int64, elev (ns,), r0, dr, span (ns,)) of time t's
    volume: az sorted within each sweep (NaN padding after its rays), the largest
    azimuth step that is not a hole (GAP_RAYS ray spacings), kept per time."""
    sw = run.sweeps(t)
    key = (run.path, t, len(sw), sw.nr)
    with _LOCK:
        got = _GEOM.get(key)
    if got is not None:
        return got
    az = np.ascontiguousarray(sw.az, np.float64)
    rays = np.isfinite(az).sum(axis=1).astype(np.int64)
    span = np.empty(len(sw))
    for k in range(len(sw)):
        a = az[k, :rays[k]]
        span[k] = GAP_RAYS * (float(np.median(np.diff(a))) if rays[k] > 2 else
                              360.0 / max(rays[k], 1))
    r = np.asarray(run.ranges, np.float64)
    dr = float(np.median(np.diff(r))) if len(r) > 1 else 1.0
    got = (az, rays, np.ascontiguousarray(sw.elev, np.float64), float(r[0]), dr, span)
    with _LOCK:
        _GEOM[key] = got
        while len(_GEOM) > 64:
            _GEOM.pop(next(iter(_GEOM)))
    return got


@numba.njit(cache=True)
def _sweep_value(data, az, nr, span, k, a, g, ng, nearest):
    """Sweep k's value at azimuth a (deg) and fractional gate g (NaN-aware: valid
    neighbours must carry at least half the weight)."""
    n = nr[k]
    if n < 2 or g < -0.5 or g > ng - 0.5:
        return np.nan
    row = az[k]
    j1 = np.searchsorted(row[:n], a)
    if j1 == 0 or j1 == n:  # (across north: the last ray and the first)
        j0, j1 = n - 1, 0
        a0, a1 = row[j0], row[j1] + 360.0
        aa = a if a >= a0 else a + 360.0
    else:
        j0 = j1 - 1
        a0, a1, aa = row[j0], row[j1], a
    gap = a1 - a0
    wa = (aa - a0) / gap if gap > 0 else 0.0
    wa = min(max(wa, 0.0), 1.0)
    if gap > 2.0 * span[k]:  # (the edge of a sector the sweep lacks: the nearer ray,
        if min(aa - a0, a1 - aa) > span[k]:  # up to GAP_RAYS spacings from it, as on
            return np.nan  # the PPI)
        wa = 0.0 if aa - a0 <= a1 - aa else 1.0
    gc = min(max(g, 0.0), ng - 1.0)
    i0 = int(math.floor(gc))
    i1 = min(i0 + 1, ng - 1)
    wg = gc - i0
    if nearest:
        jj = j1 if wa >= 0.5 else j0
        ii = i1 if wg >= 0.5 else i0
        return data[k, jj, ii]
    tot = 0.0
    wsum = 0.0
    for c in range(4):
        jj = j0 if c < 2 else j1
        ii = i0 if c % 2 == 0 else i1
        w = (1.0 - wa if c < 2 else wa) * (1.0 - wg if c % 2 == 0 else wg)
        v = data[k, jj, ii]
        if v == v and w > 0:
            tot += w * v
            wsum += w
    if wsum < 0.5:
        return np.nan
    return tot / wsum


@numba.njit(parallel=True, cache=True)
def _sample(data, az, nr, span, elev, r0, dr, paz, pel, pr, half_bw, max_gap_km, nearest,
            out):
    ns = data.shape[0]
    ng = data.shape[2]
    for p in numba.prange(paz.size):
        e = pel[p]
        g = (pr[p] - r0) / dr
        k1 = np.searchsorted(elev, e)
        if k1 == 0:
            out[p] = (_sweep_value(data, az, nr, span, 0, paz[p], g, ng, nearest)
                      if e >= elev[0] - half_bw else np.nan)
            continue
        if k1 == ns:
            out[p] = (_sweep_value(data, az, nr, span, ns - 1, paz[p], g, ng, nearest)
                      if e <= elev[ns - 1] + half_bw else np.nan)
            continue
        k0 = k1 - 1
        de = elev[k1] - elev[k0]
        if max_gap_km > 0 and pr[p] * math.radians(de) > max_gap_km:
            out[p] = np.nan
            continue
        we = (e - elev[k0]) / de if de > 0 else 0.0
        v0 = _sweep_value(data, az, nr, span, k0, paz[p], g, ng, nearest)
        v1 = _sweep_value(data, az, nr, span, k1, paz[p], g, ng, nearest)
        ok0 = v0 == v0
        ok1 = v1 == v1
        if ok0 and ok1:
            out[p] = (1.0 - we) * v0 + we * v1
        elif ok0 and we <= 0.5:
            out[p] = v0
        elif ok1 and we >= 0.5:
            out[p] = v1
        else:
            out[p] = np.nan


def sample(run, vol, t, x, y, z, method="linear", max_gap_km=0.0, beam_extend=True):
    """Values of vol ((sweeps, rays, gates) of time t, as run.volume gives it) at points
    x, y, z (km; z above the radar), broadcast together: float32 of their shape.

    method: "linear" or "nearest" (within a sweep; always linear between sweeps).
    max_gap_km > 0: NaN where the two sweeps around a point are further apart than that
    (vertically, at its range).  beam_extend: half a beamwidth beyond the lowest and
    highest sweeps takes their values (else NaN outside the sweeps)."""
    if method not in METHODS:
        raise ValueError(f"radar sampling method {method!r}: one of {METHODS}")
    x, y, z = np.broadcast_arrays(*(np.asarray(a, np.float64) for a in (x, y, z)))
    shape = x.shape
    az, nr, elev, r0, dr, span = geometry(run, t)
    data = np.asarray(vol)
    if data.dtype != np.float32:
        data = data.astype(np.float32)
    out = np.empty(x.size, np.float32)
    if x.size == 0:
        return out.reshape(shape)
    if data.shape[0] != len(elev):
        raise ValueError(f"a volume of {data.shape[0]} sweeps for a sweep table of "
                         f"{len(elev)}")
    paz, pel, pr = beam.polar_of(x.ravel(), y.ravel(), z.ravel())
    _sample(data, az, nr, span, elev, r0, dr, paz, pel, pr,
            beam.BEAMWIDTH / 2.0 if beam_extend else 0.0, float(max_gap_km),
            method == "nearest", out)
    return out.reshape(shape)
