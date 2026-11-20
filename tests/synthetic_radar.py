"""Small synthetic CfRadial volumes with analytic fields, for the radar reader's tests.

write(folder) makes two volumes shaped like the KTLX files (docs-dev/radar-spike.md
section 1), with every quirk the reader must handle, at a tiny size:

  * names combined_radar_object_advcor_<n>_<YYYYMMDD_HHMMSS>.nc, with n = 9 and 10 so
    the names sort in the wrong order (10 before 9) while the times do not;
  * `time` padded past the sweep table with masked rays;
  * sweeps written out of elevation order, rays out of azimuth order;
  * measured elevations off fixed_angle (the median differs from it);
  * the second volume one sweep short;
  * a field with _FillValue (reflectivity) and one without (u: netCDF's default
    fill marks its missing gates);
  * a field only in the first file (w).

Fields, at gate g (range R0 + g * DR km), ray azimuth a (deg), sweep elevation e:
  reflectivity = refl(a, g, e)   NaN where g is a multiple of 7
  velocity     = vel(a, g, e)    (no missing gates)
  u            = 10, NaN for g < 5 (default fill)
  v            = -5 (with _FillValue; no missing gates)
  w            = 1 (the first volume only)
"""
import os

import netCDF4
import numpy as np

SITE = (35.0, -97.0, 400.0)  # lat, lon, altitude m
R0, DR, NG = 2.0, 0.5, 40     # km, km, gates
NRAY = 36                     # 10 degrees apart
FIXED = [2.4, 0.5, 1.3]       # written in this order (not sorted)
OFFSET = [0.05, -0.02, 0.03]  # measured minus fixed (deg)
PAD = 7                       # padding rays after the sweep table
NAMES = {9: "20260404_020040", 10: "20260404_020733"}


def refl(a, g, e):
    return 10.0 + 0.5 * g + 0.01 * a + e


def vel(a, g, e):
    return 20.0 * np.sin(np.radians(a)) + 0.1 * g - e


def write(folder):
    os.makedirs(folder, exist_ok=True)
    out = []
    for n, stamp in NAMES.items():
        nsweep = 3 if n == 9 else 2  # (the second volume lacks the last sweep written)
        path = os.path.join(folder, f"combined_radar_object_advcor_{n}_{stamp}.nc")
        _volume(path, nsweep, with_w=(n == 9), seed=n)
        out.append(path)
    return out


def _volume(path, nsweep, with_w, seed):
    rng = np.random.default_rng(seed)
    nrays = nsweep * NRAY + PAD
    g = np.arange(NG)
    with netCDF4.Dataset(path, "w") as d:
        d.Conventions = "CF/Radial instrument_parameters"
        d.instrument_name = "TEST"
        d.createDimension("time", None)
        d.createDimension("range", NG)
        d.createDimension("sweep", nsweep)
        r = d.createVariable("range", "f4", ("range",))
        r[:] = (R0 + DR * g) * 1000.0
        r.units = "meters"
        for name in ("latitude", "longitude", "altitude"):
            d.createVariable(name, "f8", ())
        d["latitude"][...], d["longitude"][...], d["altitude"][...] = SITE
        az_v = d.createVariable("azimuth", "f8", ("time",), fill_value=-9999.0)
        el_v = d.createVariable("elevation", "f8", ("time",), fill_value=-9999.0)
        ny_v = d.createVariable("nyquist_velocity", "f4", ("time",), fill_value=-9999.0)
        z_v = d.createVariable("reflectivity", "f8", ("time", "range"), fill_value=-9999.0)
        z_v.units, z_v.long_name = "dBZ", "Reflectivity"
        v_v = d.createVariable("velocity", "f8", ("time", "range"), fill_value=-9999.0)
        v_v.units = "meters_per_second"
        u_v = d.createVariable("u", "f8", ("time", "range"))  # (no _FillValue)
        u_v.units = "m/s"
        vv_v = d.createVariable("v", "f8", ("time", "range"), fill_value=-9999.0)
        vv_v.units = "m/s"
        w_v = d.createVariable("w", "f8", ("time", "range")) if with_w else None
        s0 = d.createVariable("sweep_start_ray_index", "i4", ("sweep",))
        s1 = d.createVariable("sweep_end_ray_index", "i4", ("sweep",))
        fa = d.createVariable("fixed_angle", "f4", ("sweep",))
        az = np.zeros(nrays)
        el = np.zeros(nrays)
        Z = np.full((nrays, NG), -9999.0)
        V = np.full((nrays, NG), -9999.0)
        for k in range(nsweep):
            a0 = k * NRAY
            ray_az = rng.permutation(np.arange(NRAY) * 10.0 + 0.5)
            # measured elevations scatter evenly about fixed + OFFSET: their median
            e_meas = FIXED[k] + OFFSET[k] + np.where(np.arange(NRAY) % 2, 0.01, -0.01)
            az[a0:a0 + NRAY], el[a0:a0 + NRAY] = ray_az, e_meas
            e = FIXED[k] + OFFSET[k]
            for i in range(NRAY):
                zz = refl(ray_az[i], g, e)
                zz[g % 7 == 0] = -9999.0
                Z[a0 + i] = zz
                V[a0 + i] = vel(ray_az[i], g, e)
            s0[k], s1[k], fa[k] = a0, a0 + NRAY - 1, FIXED[k]
        n_in = nsweep * NRAY
        az_v[:n_in], el_v[:n_in] = az[:n_in], el[:n_in]
        ny_v[:n_in] = 25.0
        z_v[:nrays] = Z
        v_v[:nrays] = V
        U = np.full((n_in, NG), 10.0)
        u_v[:n_in, 5:] = U[:, 5:]  # (gates < 5 never written: the default fill)
        vv_v[:n_in] = np.full((n_in, NG), -5.0)
        if w_v is not None:
            w_v[:n_in] = np.ones((n_in, NG))
        # the padding rays: angles left as fill, data written as fill
        z_v[n_in:nrays] = np.full((PAD, NG), -9999.0)
