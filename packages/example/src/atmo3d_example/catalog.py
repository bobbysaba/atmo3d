"""The field catalog: what the files' fields are called, how they show, and which field
plays each role.

The core never names a data type's fields.  It names roles ("w", "theta", "refl" ...:
core.catalog.ROLES lists them, with the units each must be in) and asks this catalog
which field plays each.  Derived fields, soundings, vectors and the viewer's defaults are
written by role, so mapping a role is what makes everything built on it work: here
theta, pres, qv, u and v give soundings, CAPE and the rest; w gives tracking; u, v, w
give vorticity."""

from atmo3d.core.catalog import Catalog, register

# optional but worth it: display defaults of the fields the files hold,
#   name: (label, units, scale, colormap, (lo, hi) or None, diverging[, group])
# scale multiplies the values for display (1000: kg/kg shown as g/kg, with units to
# match); the group places a 3D field in the field menus.  A field left out still
# shows, labelled from the file's long_name and units.
KIN, TH, RADAR, SFC = "Kinematics", "Thermodynamics", "Radar", "Swaths & 2D"
NATIVES = {
    "u": ("x wind (u)", "m/s", 1, "RdBu_r", (-30, 30), True, KIN),
    "v": ("y wind (v)", "m/s", 1, "RdBu_r", (-30, 30), True, KIN),
    "w": ("Vertical velocity (w)", "m/s", 1, "RdBu_r", (-20, 20), True, KIN),
    "theta": ("Potential temperature (θ)", "K", 1, "cmo.thermal", None, False, TH),
    "pres": ("Pressure", "hPa", 0.01, "viridis", None, False, TH),
    "qv": ("Water vapor mixing ratio (qv)", "g/kg", 1000, "YlGnBu", (0, 20), False, TH),
    "dbz": ("Reflectivity", "dBZ", 1, "reflectivity", (0, 75), False, RADAR),
    "rain": ("Accumulated rain", "mm", 1, "cmo.rain", (0, 50), False, SFC),
    "tke": ("Subgrid TKE", "m²/s²", 1, "magma", (0, 20), False),
}

# REQUIRED (at least one): {role: the field's name in the files}.  Map every role the
# files have; leave out the rest.
ROLES = {
    "u": "u", "v": "v", "w": "w",
    "theta": "theta", "pres": "pres", "qv": "qv",
    "refl": "dbz",
}

# REQUIRED: register it under the Model's key.  Optional arguments (core/catalog.py's
# docstring lists them all): other= (fields listed under "Other"), hidden= (not listed),
# renamed= (old names in saved sessions and figures), turbulence=, kappa= ...
CATALOG = register(Catalog("example", NATIVES, ROLES, turbulence=("tke",)))
