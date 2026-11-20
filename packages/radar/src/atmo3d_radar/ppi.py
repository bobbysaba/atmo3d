"""A sweep on the map (PPI): native (rays, gates) values drawn on the map's x, y pixels.

No sampler and no regrid: each pixel of the map view takes the value of the gate it falls
in, the nearest ray (by azimuth) and the nearest gate (by ground distance along that
sweep's beam, atmo3d_radar.beam, 4/3 earth).  A pixel farther from every ray than
GAP_RAYS ray spacings (a sector the sweep lacks) or outside the gates is empty.

  window(run, view, maxpix)   the map pixels of a view: (x0, x1, y0, y1, stride, n)
  raster(run, a, t, k, win)   x (nx,), y (ny,), (ny, nx) of sweep k's values a at time t
  reduce_sweeps(run, vol, t, win, op)  the most / least of the sweeps over each pixel

The window takes the place of the grid's index window (core.render.view_window): its
stride (win[4]) says how much coarser than the gates the pixels are (1: full res).
"""
import math
from collections import OrderedDict
import threading

import numpy as np

from . import beam

GAP_RAYS = 1.5  # a pixel farther than this many ray spacings from any ray: no value
_INDEX = OrderedDict()  # (sweep geometry, window) -> (ray, gate) of each pixel
_INDEX_MAX = 16
_LOCK = threading.Lock()


def window(run, view, maxpix):
    """The map pixels of a view (km), at most maxpix across its longer side and no finer
    than half a gate: (x0, x1, y0, y1, stride, n), n pixels across the longer side."""
    e0, e1, f0, f1 = run.extent
    x0, x1, y0, y1 = view
    x0, x1 = max(min(x0, x1), e0), min(max(x0, x1), e1)
    y0, y1 = max(min(y0, y1), f0), min(max(y0, y1), f1)
    if x1 - x0 <= 0 or y1 - y0 <= 0:
        x0, x1, y0, y1 = e0, e1, f0, f1
    dr = float(np.median(np.diff(run.ranges))) if len(run.ranges) > 1 else 1.0
    span = max(x1 - x0, y1 - y0)
    n = int(max(2, min(maxpix, math.ceil(span / (dr / 2)))))
    stride = max(1, int(math.ceil((span / n) / dr - 1e-9)))
    return (float(x0), float(x1), float(y0), float(y1), stride, n)


def pixels(win):
    """x (nx,), y (ny,) pixel centres (km) of a window."""
    x0, x1, y0, y1, _, n = win
    px = max(x1 - x0, y1 - y0) / n
    nx, ny = max(2, int(round((x1 - x0) / px))), max(2, int(round((y1 - y0) / px)))
    return (x0 + (np.arange(nx) + 0.5) * (x1 - x0) / nx,
            y0 + (np.arange(ny) + 0.5) * (y1 - y0) / ny)


def _nearest_ray(az_sorted, az):
    """Index into az_sorted (ascending, finite) of the ray nearest each azimuth az (deg,
    wrapping at 360), and the angular distance to it."""
    n = len(az_sorted)
    i = np.searchsorted(az_sorted, az) % n
    j = (i - 1) % n
    di = np.abs((az_sorted[i] - az + 180.0) % 360.0 - 180.0)
    dj = np.abs((az_sorted[j] - az + 180.0) % 360.0 - 180.0)
    near = np.where(dj < di, j, i)
    return near, np.minimum(di, dj)


def _polar(win):
    """Ground distance and azimuth (deg) of window win's pixels, (ny, nx) each."""
    x, y = pixels(win)
    X, Y = np.meshgrid(x, y)
    return np.hypot(X, Y), np.degrees(np.arctan2(X, Y)) % 360.0


def _gates(run, sw, k, s, paz):
    """(ray, gate) indices of sweep k of sweep table sw at ground distance s and
    azimuth paz (arrays): the nearest ray and gate, -1 where there is none."""
    az = sw.az[k]
    nray = int(np.isfinite(az).sum())
    ray = np.full(s.shape, -1, np.int32)
    gate = np.full(s.shape, -1, np.int32)
    if nray >= 2 and len(run.ranges):
        a = az[:nray]
        near, dist = _nearest_ray(a, paz)
        spacing = float(np.median(np.diff(a))) if nray > 2 else 360.0 / nray
        _, sg = beam.gate_position(run.ranges, float(sw.elev[k]))
        half = 0.5 * (np.diff(sg).mean() if len(sg) > 1 else 1.0)
        g = np.clip(np.searchsorted(0.5 * (sg[1:] + sg[:-1]), s), 0, len(sg) - 1)
        ok = (dist <= GAP_RAYS * spacing) & (s >= sg[0] - half) & (s <= sg[-1] + half)
        ray[ok], gate[ok] = near[ok], g[ok]
    return ray, gate


def index(run, t, k, win):
    """(ray, gate) index arrays (ny, nx) of sweep k at time t on window win's pixels; -1
    where a pixel has no gate.  Kept for the last few windows."""
    sw = run.sweeps(t)
    nray = int(np.isfinite(sw.az[k]).sum())
    key = (run.path, t, k, float(sw.elev[k]), nray, win)
    with _LOCK:
        got = _INDEX.get(key)
        if got is not None:
            _INDEX.move_to_end(key)
            return got
    out = _gates(run, sw, k, *_polar(win))
    with _LOCK:
        _INDEX[key] = out
        while len(_INDEX) > _INDEX_MAX:
            _INDEX.popitem(last=False)
    return out


def raster(run, a, t, k, win):
    """Sweep k's values a (rays, gates) at time t on window win: x, y, (ny, nx)."""
    x, y = pixels(win)
    ray, gate = index(run, t, k, win)
    a = np.asarray(a)
    out = np.full(ray.shape, np.nan, np.float32)
    ok = ray >= 0
    out[ok] = a[ray[ok], gate[ok]]
    return x, y, out


def reduce_sweeps(run, vol, t, win, op="max"):
    """The most ("max") or least ("min") of every sweep of vol (sweeps, rays, gates) at
    time t over each pixel of window win, each sweep's value the gate the pixel falls
    in (as raster): (ny, nx), NaN where no sweep has a value."""
    s, paz = _polar(win)
    sw = run.sweeps(t)
    out = np.full(s.shape, np.nan, np.float32)
    pick = np.fmax if op == "max" else np.fmin
    vol = np.asarray(vol)
    for k in range(min(len(sw), vol.shape[0])):
        ray, gate = _gates(run, sw, k, s, paz)
        ok = ray >= 0
        v = np.full(s.shape, np.nan, np.float32)
        v[ok] = vol[k][ray[ok], gate[ok]]
        pick(out, v, out=out)
    return out


def gate_at(run, t, k, x, y):
    """The gate of sweep k at time t under map point x, y (km): dict(ray, gate, az,
    range, ground, height) (ray, gate: indices into read_sweep's array), or None where
    the sweep has no gate (beyond the last, or in a sector it lacks)."""
    sw = run.sweeps(t)
    if not 0 <= k < len(sw):
        return None
    az = sw.az[k]
    nray = int(np.isfinite(az).sum())
    if nray < 2 or not len(run.ranges):
        return None
    a = az[:nray]
    paz = float(np.degrees(np.arctan2(x, y)) % 360.0)
    near, dist = _nearest_ray(a, np.array([paz]))
    spacing = float(np.median(np.diff(a))) if nray > 2 else 360.0 / nray
    h, sg = beam.gate_position(run.ranges, float(sw.elev[k]))
    s = float(np.hypot(x, y))
    half = 0.5 * (np.diff(sg).mean() if len(sg) > 1 else 1.0)
    if dist[0] > GAP_RAYS * spacing or not sg[0] - half <= s <= sg[-1] + half:
        return None
    g = int(np.clip(np.searchsorted(0.5 * (sg[1:] + sg[:-1]), s), 0, len(sg) - 1))
    return dict(ray=int(near[0]), gate=g, az=float(a[near[0]]), range=float(run.ranges[g]),
                ground=float(sg[g]), height=float(h[g]))
