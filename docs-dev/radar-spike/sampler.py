"""Phase 4 spike: a radar volume in native polar geometry and the sampler primitive.

Throwaway prototype for docs-dev/radar-spike.md (not app code).

Geometry (one explicit, shared choice):
  * Beam propagation: the 4/3 effective-earth-radius model (standard refraction;
    Doviak and Zrnic 1993, eq. 2.28).  In that model beams are straight lines over a
    sphere of radius R = KE * A, so the forward map (range, elevation) -> (ground
    distance, height) and its inverse are both closed-form.
  * Horizontal coordinates: x east, y north (km) on an azimuthal-equidistant plane
    centred on the radar, i.e. hypot(x, y) is the great-circle ground distance on the
    effective sphere and atan2(x, y) the azimuth.  Lat/lon go through pyproj "aeqd"
    centred on the site (not done here).
  * Heights z (km) are above the radar's level (the antenna altitude); MSL is
    z + altitude.
"""
import math

import numpy as np
import netCDF4
import numba

A_EARTH = 6371.0  # km
KE = 4.0 / 3.0
R_EFF = KE * A_EARTH
BEAMWIDTH = 0.95  # deg, WSR-88D half-power beamwidth


# --------------------------------------------------------------- beam model
def beam_height(r, elev_deg):
    """Height (km above the radar) and ground distance (km) of a gate at slant range
    r (km) and elevation elev_deg."""
    th = np.radians(elev_deg)
    h = np.sqrt(r * r + R_EFF * R_EFF + 2.0 * r * R_EFF * np.sin(th)) - R_EFF
    s = R_EFF * np.arcsin(r * np.cos(th) / (R_EFF + h))
    return h, s


def polar_of(x, y, z):
    """(azimuth deg, elevation deg, slant range km) of points x, y, z (km), the exact
    inverse of beam_height on the effective sphere."""
    s = np.hypot(x, y)
    phi = s / R_EFF
    rz = R_EFF + z
    px, pz = rz * np.sin(phi), rz * np.cos(phi) - R_EFF
    r = np.hypot(px, pz)
    el = np.degrees(np.arctan2(pz, px))
    az = np.degrees(np.arctan2(x, y)) % 360.0
    return az, el, r


# --------------------------------------------------------------- the volume
class Volume:
    """One radar volume of one field, natively: sweeps x rays x gates.

    elev   (ns,) each sweep's elevation (deg): the median of its rays' measured
           elevations (closer to the beams than fixed_angle; e.g. 0.92 vs 0.88)
    az     (ns, nr) ray azimuths, sorted ascending within each sweep (NaN padding
           when sweeps have fewer rays than nr)
    data   (ns, nr, ng) float32, NaN where missing, rays in az order
    r0, dr first gate centre and gate spacing (km)
    Sweeps are sorted by elevation (a repeated elevation, e.g. SAILS, keeps the
    last one: the newest)."""

    def __init__(self, elev, az, data, r0, dr, alt_km=0.0):
        self.elev, self.az, self.data = elev, az, data
        self.r0, self.dr, self.alt = float(r0), float(dr), float(alt_km)
        self.ng = data.shape[2]

    @property
    def nbytes(self):
        return self.data.nbytes + self.az.nbytes

    @classmethod
    def from_cfradial(cls, path, field, sweeps=None):
        with netCDF4.Dataset(path) as nc:
            nc.set_auto_mask(True)
            s0 = nc["sweep_start_ray_index"][:].astype(int)
            s1 = nc["sweep_end_ray_index"][:].astype(int)
            el_all = nc["elevation"][:].filled(np.nan)
            az_all = nc["azimuth"][:].filled(np.nan)
            rng = nc["range"][:]
            idx = range(len(s0)) if sweeps is None else sweeps
            nr = max(s1[k] - s0[k] + 1 for k in idx)
            v = nc[field]
            elev, azs, datas = [], [], []
            for k in idx:
                a, b = s0[k], s1[k] + 1
                raw = v[a:b, :]
                d = np.ma.filled(raw.astype(np.float32), np.nan)
                az = az_all[a:b]
                o = np.argsort(az)
                pad = nr - (b - a)
                elev.append(float(np.nanmedian(el_all[a:b])))
                azs.append(np.concatenate([az[o], np.full(pad, np.nan)]))
                datas.append(np.concatenate([d[o], np.full((pad, d.shape[1]), np.nan, np.float32)]))
            alt = float(nc["altitude"][...]) / 1000.0
        elev = np.array(elev)
        order = np.argsort(elev, kind="stable")
        return cls(elev[order], np.array(azs)[order], np.stack(datas)[order],
                   rng[0] / 1000.0, (rng[1] - rng[0]) / 1000.0, alt)


# --------------------------------------------------------------- the sampler
@numba.njit(cache=True)
def _sweep_value(data, az, k, a, g, ng, nearest):
    """Value of sweep k at azimuth a (deg) and fractional gate g: bilinear (or
    nearest) in azimuth and range; NaN-aware: valid neighbours must carry at least
    half the weight.  Returns (value, valid weight)."""
    row = az[k]
    nr = 0
    for i in range(row.size):
        if row[i] == row[i]:
            nr += 1
    if nr < 2 or g < -0.5 or g > ng - 0.5:
        return np.nan, 0.0
    # azimuth bracket with wrap
    j1 = np.searchsorted(row[:nr], a)
    j0 = j1 - 1
    if j1 == 0 or j1 == nr:
        j0, j1 = nr - 1, 0
        a0 = row[j0]
        a1 = row[j1] + 360.0
        aa = a if a >= a0 else a + 360.0
    else:
        a0, a1, aa = row[j0], row[j1], a
    span = a1 - a0
    if span > 2.0:  # a hole in the sweep (sector, missing rays)
        return np.nan, 0.0
    wa = (aa - a0) / span if span > 0 else 0.0
    gc = min(max(g, 0.0), ng - 1.0)
    i0 = int(math.floor(gc))
    i1 = min(i0 + 1, ng - 1)
    wg = gc - i0
    if nearest:
        jj = j1 if wa >= 0.5 else j0
        ii = i1 if wg >= 0.5 else i0
        v = data[k, jj, ii]
        return (v, 1.0) if v == v else (np.nan, 0.0)
    tot = 0.0
    wsum = 0.0
    for jj, wj in ((j0, 1.0 - wa), (j1, wa)):
        for ii, wi in ((i0, 1.0 - wg), (i1, wg)):
            w = wj * wi
            v = data[k, jj, ii]
            if v == v and w > 0:
                tot += w * v
                wsum += w
    if wsum < 0.5:
        return np.nan, wsum
    return tot / wsum, wsum


@numba.njit(parallel=True, cache=True)
def _sample(data, az, elev, r0, dr, paz, pel, pr, half_bw, max_gap_km, nearest, out):
    ns, _, ng = data.shape
    for p in numba.prange(paz.size):
        e = pel[p]
        g = (pr[p] - r0) / dr
        k1 = np.searchsorted(elev, e)
        if k1 == 0:
            if e >= elev[0] - half_bw:
                out[p] = _sweep_value(data, az, 0, paz[p], g, ng, nearest)[0]
            else:
                out[p] = np.nan
            continue
        if k1 == ns:
            if e <= elev[ns - 1] + half_bw:
                out[p] = _sweep_value(data, az, ns - 1, paz[p], g, ng, nearest)[0]
            else:
                out[p] = np.nan
            continue
        k0 = k1 - 1
        de = elev[k1] - elev[k0]
        if max_gap_km > 0 and pr[p] * math.radians(de) > max_gap_km:
            out[p] = np.nan
            continue
        we = (e - elev[k0]) / de
        v0, _ = _sweep_value(data, az, k0, paz[p], g, ng, nearest)
        v1, _ = _sweep_value(data, az, k1, paz[p], g, ng, nearest)
        ok0, ok1 = v0 == v0, v1 == v1
        if ok0 and ok1:
            out[p] = (1.0 - we) * v0 + we * v1
        elif ok0 and we <= 0.5:
            out[p] = v0
        elif ok1 and we >= 0.5:
            out[p] = v1
        else:
            out[p] = np.nan


def sample(vol, x, y, z, method="linear", max_gap_km=0.0, beam_extend=True):
    """Field values of vol at points x, y, z (km, radar-relative; z above the radar).

    method: "linear" (bilinear in azimuth and range within a sweep, then linear in
    elevation between the two sweeps around the point) or "nearest" (nearest gate
    within a sweep, still linear in elevation).
    max_gap_km: > 0 leaves NaN where the two sweeps around a point are further apart
    (vertically, at the point's range) than this.
    beam_extend: points up to half a beamwidth below the lowest sweep or above the
    highest take that sweep's value (else NaN outside the sweeps)."""
    x, y, z = (np.asarray(a, np.float64) for a in np.broadcast_arrays(x, y, z))
    shape = x.shape
    paz, pel, pr = polar_of(x.ravel(), y.ravel(), z.ravel())
    out = np.empty(paz.size, np.float32)
    _sample(vol.data, vol.az, vol.elev, vol.r0, vol.dr, paz, pel, pr,
            BEAMWIDTH / 2.0 if beam_extend else 0.0, float(max_gap_km),
            method == "nearest", out)
    return out.reshape(shape)


# --------------------------------------------------------------- views built on it
def cross_section(vol, A, B, ztop=18.0, dz=0.1, ds=0.25, **kw):
    (xa, ya), (xb, yb) = A, B
    L = math.hypot(xb - xa, yb - ya)
    s = np.linspace(0.0, L, int(round(L / ds)) + 1)
    zq = np.arange(0.0, ztop + dz / 2, dz)
    xp = xa + (xb - xa) * s / L
    yp = ya + (yb - ya) * s / L
    X = np.broadcast_to(xp, (zq.size, s.size))
    Y = np.broadcast_to(yp, (zq.size, s.size))
    Z = np.broadcast_to(zq[:, None], (zq.size, s.size))
    return s, zq, sample(vol, X, Y, Z, **kw)


def column(vol, x, y, ztop=18.0, dz=0.05, **kw):
    zq = np.arange(0.0, ztop + dz / 2, dz)
    return zq, sample(vol, np.full_like(zq, x), np.full_like(zq, y), zq, **kw)


def cappi(vol, z, half=150.0, d=0.5, center=(0.0, 0.0), **kw):
    xs = center[0] + np.arange(-half, half + d / 2, d)
    ys = center[1] + np.arange(-half, half + d / 2, d)
    X, Y = np.meshgrid(xs, ys)
    return xs, ys, sample(vol, X, Y, np.full_like(X, z), **kw)


def regrid(vol, half=460.0, d=1.0, dz=None, ztop=20.0, center=(0.0, 0.0), **kw):
    """(nk, nj, ni) float32 on a regular grid: the sampler at every grid point, one
    level at a time (so temporaries stay one level big)."""
    dz = d if dz is None else dz
    xs = center[0] + np.arange(-half, half + d / 2, d)
    ys = center[1] + np.arange(-half, half + d / 2, d)
    zs = np.arange(0.0, ztop + dz / 2, dz)
    X, Y = np.meshgrid(xs, ys)
    out = np.empty((zs.size, ys.size, xs.size), np.float32)
    for k, z in enumerate(zs):
        out[k] = sample(vol, X, Y, np.full_like(X, z), **kw)
    return xs, ys, zs, out


# --------------------------------------------------------------- native 3D grid
def sweep_grid(vol, stride_gate=1, max_range=None):
    """PyVista StructuredGrid with points at gate centres: dimensions
    (gates, rays + 1 (closing the circle), sweeps).  Cells join neighbouring gates,
    rays and sweeps, so an isosurface is interpolated linearly across the gap between
    two sweeps, however wide."""
    import pyvista as pv
    ng = vol.ng if max_range is None else int((max_range - vol.r0) / vol.dr) + 1
    gi = np.arange(0, ng, stride_gate)
    r = vol.r0 + gi * vol.dr
    az = np.concatenate([vol.az, vol.az[:, :1] + 360.0], axis=1)  # (ns, nr+1)
    data = np.concatenate([vol.data[:, :, gi], vol.data[:, :1, gi]], axis=1)
    E = vol.elev[:, None, None]
    R = r[None, None, :]
    h, s = beam_height(R, E)
    h = np.broadcast_to(h, data.shape)
    s = np.broadcast_to(s, data.shape)
    A = np.radians(az)[:, :, None]
    X, Y = s * np.sin(A), s * np.cos(A)
    # StructuredGrid wants (ni, nj, nk) arrays in Fortran order: gates fastest
    g = pv.StructuredGrid(np.ascontiguousarray(X.transpose(2, 1, 0)),
                          np.ascontiguousarray(Y.transpose(2, 1, 0)),
                          np.ascontiguousarray(h.transpose(2, 1, 0)))
    g.point_data["f"] = data.transpose(2, 1, 0).ravel(order="F")
    return g
