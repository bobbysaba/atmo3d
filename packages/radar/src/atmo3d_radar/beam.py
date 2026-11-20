"""Radar beam geometry: one explicit, shared choice (docs-dev/radar-spike.md section 2).

  * Beam propagation: the 4/3 effective-earth-radius model (standard refraction;
    Doviak and Zrnic 1993, eq. 2.28).  Beams are straight lines over a sphere of radius
    R_EFF = 4/3 x 6371 km, so (slant range, elevation) -> (ground distance, height) and
    its inverse are both closed-form.
  * Horizontal coordinates: x east, y north (km) on an azimuthal-equidistant plane
    centred on the radar: hypot(x, y) is the ground distance and atan2(x, y) the
    azimuth.  Lat/lon go through pyproj "aeqd" centred on the site (geo()).
  * Heights z (km) are above the radar's level (the antenna altitude); MSL is z plus
    the altitude.  No terrain.
"""
import numpy as np

A_EARTH = 6371.0  # km
KE = 4.0 / 3.0
R_EFF = KE * A_EARTH
BEAMWIDTH = 0.95  # deg, the WSR-88D half-power beamwidth


def gate_position(r, elev_deg):
    """(height km above the radar, ground distance km) of gates at slant range r (km)
    and elevation elev_deg (broadcast)."""
    r = np.asarray(r, dtype=np.float64)
    th = np.radians(elev_deg)
    h = np.sqrt(r * r + R_EFF * R_EFF + 2.0 * r * R_EFF * np.sin(th)) - R_EFF
    s = R_EFF * np.arcsin(r * np.cos(th) / (R_EFF + h))
    return h, s


def polar_of(x, y, z):
    """(azimuth deg, elevation deg, slant range km) of points x, y, z (km): the exact
    inverse of gate_position on the effective sphere."""
    x, y, z = (np.asarray(a, dtype=np.float64) for a in (x, y, z))
    phi = np.hypot(x, y) / R_EFF
    rz = R_EFF + z
    px, pz = rz * np.sin(phi), rz * np.cos(phi) - R_EFF
    r = np.hypot(px, pz)
    el = np.degrees(np.arctan2(pz, px))
    az = np.degrees(np.arctan2(x, y)) % 360.0
    return az, el, r


def geo(lat, lon):
    """core.geo.Geo of the radar-centred azimuthal-equidistant plane (x, y km)."""
    from pyproj import CRS
    from atmo3d.core.geo import Geo
    crs = CRS.from_proj4(f"+proj=aeqd +lat_0={lat:.6f} +lon_0={lon:.6f} +x_0=0 +y_0=0 "
                         f"+datum=WGS84 +units=m +no_defs")
    return Geo(crs)
