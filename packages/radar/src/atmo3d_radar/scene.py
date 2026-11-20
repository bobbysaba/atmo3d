"""A radar volume in the 3D workspace: isosurfaces found natively, in (sweep, ray, gate)
index space, their vertices placed by the beam model (docs-dev/radar-spike.md section 4,
Bobby's Phase 4 decision: no regrid, no PyVista).

  * Each sweep's rays are first put on one azimuth grid shared by all sweeps (the
    nearest ray, up to GAP_RAYS ray spacings away, as on the PPI): sweeps can have
    different ray counts, so ray j of one is not ray j of another.
  * Marching cubes (skimage) runs on that (sweep, azimuth, gate) array; a vertex's
    fractional sweep index gives its elevation (linear between the sweeps' measured
    elevations), its azimuth and gate index give the rest, and atmo3d_radar.beam its
    x, y, z.  The surface is linear between two sweeps however far apart they are (the
    gaps are bridged, as the sampler bridges them: the scene's note says so).
  * Missing gates count as outside the surface (below the value when it is above the
    field's median, else above), so surfaces close at the edge of the data.
  * Only the gates and azimuths that can reach the region are used; faces outside the
    region or above its top are dropped.

build_scene(run, F, scene, ...) returns what core.volume3d.build_scene returns on a grid
(meshes, floor; no vectors or streamlines on radar yet).
"""
import math

import numpy as np
from scipy.ndimage import gaussian_filter
from skimage.measure import marching_cubes

from atmo3d.core import volume3d

from . import beam
from .ppi import GAP_RAYS, _nearest_ray

MAX_VOXELS = 12e6  # the automatic stride keeps a surface's array to about this many


def _sector(box):
    """(full, a0, width) of the azimuths (deg) a region box (x0, x1, y0, y1 km) spans:
    full when it holds the radar."""
    x0, x1, y0, y1 = box
    if x0 <= 0 <= x1 and y0 <= 0 <= y1:
        return True, 0.0, 360.0
    az = np.degrees(np.arctan2([x0, x0, x1, x1], [y0, y1, y0, y1])) % 360.0
    # (the smallest arc holding the four corners: the widest gap between them is outside)
    a = np.sort(az)
    gaps = np.diff(np.r_[a, a[0] + 360.0])
    i = int(np.argmax(gaps))
    a0 = a[(i + 1) % 4]
    return False, float(a0), float(360.0 - gaps[i])


def _distances(box):
    """(nearest, farthest) ground distance (km) of a region box from the radar."""
    x0, x1, y0, y1 = box
    nx = 0.0 if x0 <= 0 <= x1 else min(abs(x0), abs(x1))
    ny = 0.0 if y0 <= 0 <= y1 else min(abs(y0), abs(y1))
    fx, fy = max(abs(x0), abs(x1)), max(abs(y0), abs(y1))
    return math.hypot(nx, ny), math.hypot(fx, fy)


def azimuth_grid(run, t, box):
    """The shared azimuth grid of the region: (az (na,) deg, closed) at the finest
    sweep's ray spacing, over the region's sector (closed: all the way round, the first
    azimuth repeated at the end)."""
    sw = run.sweeps(t)
    steps = [float(np.median(np.diff(sw.az[k][np.isfinite(sw.az[k])])))
             for k in range(len(sw)) if np.isfinite(sw.az[k]).sum() > 2]
    daz = max(min(steps), 0.05) if steps else 1.0
    full, a0, width = _sector(box)
    if full:
        n = int(round(360.0 / daz))
        return np.arange(n + 1) * (360.0 / n), True
    pad = 2 * daz
    n = max(2, int(math.ceil((width + 2 * pad) / daz)) + 1)
    return (a0 - pad + np.arange(n) * daz) % 360.0, False


def gate_span(run, t, box):
    """(g0, g1): the gates (slice) whose beams can reach the region's distances."""
    sw = run.sweeps(t)
    near, far = _distances(box)
    r = np.asarray(run.ranges)
    emax = float(np.nanmax(sw.elev)) if len(sw) else 0.0
    # (the ground distance of a gate is at most its range, and at least range x cos(elev))
    g0 = int(np.searchsorted(r, near)) - 1
    g1 = int(np.searchsorted(r, far / max(math.cos(math.radians(min(emax, 89.0))), 1e-3))) + 2
    return max(g0, 0), min(max(g1, g0 + 2), len(r))


def on_azimuths(run, t, vol, az, g0, g1, stride):
    """vol's sweeps (sweeps, rays, gates) on the shared azimuths az: (sweeps, na, n
    gates g0:g1:stride), each the nearest ray up to GAP_RAYS spacings away (NaN past)."""
    sw = run.sweeps(t)
    ns = min(len(sw), vol.shape[0])
    out = np.full((ns, len(az), len(range(g0, g1, stride))), np.nan, np.float32)
    for k in range(ns):
        a = sw.az[k]
        n = int(np.isfinite(a).sum())
        if n < 2:
            continue
        near, dist = _nearest_ray(a[:n], az)
        spacing = float(np.median(np.diff(a[:n]))) if n > 2 else 360.0 / n
        ok = dist <= GAP_RAYS * spacing
        out[k, ok] = vol[k][near[ok], g0:g1:stride]
    return out


def auto_stride(run, t, box, max_voxels=MAX_VOXELS):
    """The gate and azimuth stride that keeps the region's array to about max_voxels."""
    az, _ = azimuth_grid(run, t, box)
    g0, g1 = gate_span(run, t, box)
    n = len(run.sweeps(t)) * len(az) * (g1 - g0)
    return max(1, int(math.ceil(math.sqrt(n / max_voxels))))


def isosurface(run, t, vol, box, value, stride, smooth, ztop):
    """Vertices (km) and faces of the `value` surface of time t's volume vol (sweeps,
    rays, gates) inside the region box (x0, x1, y0, y1 km) up to ztop (km above the
    radar), as core.volume3d.isosurface gives them on a grid; None when there is none."""
    az, closed = azimuth_grid(run, t, box)
    az = az[::stride] if not closed else np.r_[az[:-1][::stride], az[-1]]
    g0, g1 = gate_span(run, t, box)
    sub = on_azimuths(run, t, np.asarray(vol), az, g0, g1, stride)
    if sub.size == 0 or min(sub.shape) < 2:
        return None
    ok = np.isfinite(sub)
    if not ok.any():
        return None
    lo, hi = float(np.min(sub[ok])), float(np.max(sub[ok]))
    if not lo < value < hi:
        return None
    # (missing gates: outside the surface, so it closes at the data's edge)
    outside = lo - 1.0 if value >= float(np.median(sub[ok])) else hi + 1.0
    sub = np.where(ok, sub, np.float32(outside)).astype(np.float32)
    if smooth > 0:
        sub = gaussian_filter(sub, smooth)
    step = 1
    while True:
        try:
            verts, faces, _, _ = marching_cubes(sub, level=value, step_size=step,
                                                allow_degenerate=False)
        except (ValueError, RuntimeError):  # (no crossing after smoothing)
            return None
        if len(faces) <= volume3d.MAX_FACES or step >= 4:
            break
        step += 1
    kk, jj, ii = verts.T
    sw = run.sweeps(t)
    ns = sub.shape[0]
    e = np.interp(kk, np.arange(ns), sw.elev[:ns])
    # (azimuths of fractional indices: unwrapped, then back to 0-360)
    au = np.unwrap(np.radians(az))
    a = np.interp(jj, np.arange(len(az)), au)
    r = np.asarray(run.ranges)
    rr = np.interp(g0 + ii * stride, np.arange(len(r)), r)
    h, s = beam.gate_position(rr, e)
    x, y = s * np.sin(a), s * np.cos(a)
    x0, x1, y0, y1 = box
    inside = (x >= x0) & (x <= x1) & (y >= y0) & (y <= y1) & (h <= ztop)
    faces = faces[inside[faces].all(axis=1)]
    if not len(faces):
        return None
    used = np.unique(faces)
    remap = np.full(len(x), -1, np.int64)
    remap[used] = np.arange(len(used))
    return dict(x=x[used].astype(np.float32), y=y[used].astype(np.float32),
                z=h[used].astype(np.float32), faces=remap[faces].astype(np.int32),
                step=step)


def floor(run, F, fs, box, t, fstorm):
    """The 3D floor (core.volume3d.floor_surface's dict; None when off): the floor field
    at its height over the region, through the sampler, about 300 points across."""
    name = fs["var"]
    if not fs["on"] or name not in F:
        return None
    d = F[name]
    x0, x1, y0, y1 = box
    n = 300
    px = max(x1 - x0, y1 - y0) / n
    x = np.linspace(x0, x1, max(2, int(round((x1 - x0) / px))))
    y = np.linspace(y0, y1, max(2, int(round((y1 - y0) / px))))
    X, Y = np.meshgrid(x, y)
    z = max(float(fs["z"]), 0.0)
    a = np.asarray(F.take(name, t, lambda v: run.sample(v, t, X, Y, z), fstorm[0]),
                   np.float64)
    cmap = d.cmap if fs["cmap"] == "Field default" else fs["cmap"]
    title = f"{d.title} @ {z * 1000:.0f} m above the radar"
    if fs["range"] == "custom" and fs["hi"] > fs["lo"]:
        lo, hi = fs["lo"], fs["hi"]
    elif cmap == "reflectivity" and not fs["rev"]:
        lo, hi = 0.0, 75.0  # (the stepped NWS scale is laid out for 0-75 dBZ)
    else:
        lo, hi = volume3d.floor_range(a, d.vrange, d.diverging, fs["range"])
    return dict(x=x, y=y, a=a, lo=lo, hi=hi, title=title, cmap=cmap, rev=fs["rev"],
                colorscale=volume3d.floor_colorscale(cmap, fs["rev"]))


def build_scene(run, F, scene, progress=None, cancelled=None, cache=None):
    """core.volume3d.build_scene on a radar run: its isosurfaces and floor (no vectors
    or streamlines yet: the 3D workspace hides them on a run with no grid)."""
    t, box, ztop = scene["t"], tuple(scene["box"]), scene["ztop"]
    stride = scene["res"] or auto_stride(run, t, box)
    names = [n for iso in scene["isos"] for n in F.native_deps(iso["var"])]
    if scene["ground"]["on"] and scene["ground"]["var"] in F:
        names += F.native_deps(scene["ground"]["var"])
    if not run.load_volumes(names, t, progress=progress, cancelled=cancelled):
        return None
    meshes, notes = [], []
    for iso in scene["isos"]:
        d = F[iso["var"]]
        vol, sc = F.raw(iso["var"], t, scene["fstorm"][0])
        m = isosurface(run, t, vol, box, iso["val"] / float(sc), stride, scene["smooth"],
                       ztop)
        name = f'{d.label} = {iso["val"]:g} {d.units}'
        if m is None:
            notes.append(f"{name}: no surface in region")
            continue
        if m["step"] > 1:
            notes.append(f"{name}: coarsened ×{m['step']} (mesh too large)")
        m.update(color=iso["color"], opacity=iso["op"], name=name)
        meshes.append(m)
    if cancelled is not None and cancelled():
        return None
    ground = floor(run, F, scene["ground"], box, t, scene["fstorm"])
    notes.append(f"{run.view_note()}; heights above the radar")
    return dict(meshes=meshes, ground=ground, vecs=[], stream=None, notes=notes,
                stride=stride, off=(0.0, 0.0), terrain=None)
