"""WoFS's field catalog (core.catalog): WRF's own names.

Two fields are sums the reader makes (core.wofs.SUMS), since WRF splits them:
THETA = T + 300 (potential temperature) and PRES = P + PB (pressure).  The base state
is each field at the member's first time: THETA0, PRES0, QVAPOR0, U0, V0 (core.wofs.BASE).
U, V, W are averaged onto the mass points on read."""

from .catalog import Catalog, register

# display defaults: label, units, scale, cmap, range, diverging (as CM1's)
NATIVES = {
    "REFL_10CM": ("Reflectivity", "dBZ", 1, "reflectivity", (0, 75), False),
    "U": ("u (grid-relative)", "m/s", 1, "RdBu_r", (-30, 30), True),
    "V": ("v (grid-relative)", "m/s", 1, "RdBu_r", (-30, 30), True),
    "W": ("Vertical velocity", "m/s", 1, "RdBu_r", (-20, 20), True),
    "THETA": ("Potential temperature", "K", 1, "cmo.thermal", None, False),
    "PRES": ("Pressure", "hPa", 0.01, "viridis", None, False),
    "QVAPOR": ("Water vapor mixing ratio", "g/kg", 1000, "YlGnBu", (0, 20), False),
    "QCLOUD": ("Cloud water", "g/kg", 1000, "cmo.ice", (0, 3), False),
    "QRAIN": ("Rain", "g/kg", 1000, "cmo.rain", (0, 5), False),
    "QICE": ("Cloud ice", "g/kg", 1000, "cmo.ice", (0, 2), False),
    "QSNOW": ("Snow", "g/kg", 1000, "cmo.ice", (0, 3), False),
    "QGRAUP": ("Graupel", "g/kg", 1000, "cmo.amp", (0, 5), False),
    "QHAIL": ("Hail", "g/kg", 1000, "cmo.amp", (0, 5), False),
}

ROLES = {
    "u": "U", "v": "V", "w": "W",
    "theta": "THETA", "pres": "PRES", "qv": "QVAPOR",
    "theta0": "THETA0", "pres0": "PRES0", "qv0": "QVAPOR0", "u0": "U0", "v0": "V0",
    "qc": "QCLOUD", "qi": "QICE", "qr": "QRAIN", "qs": "QSNOW", "qg": "QGRAUP",
    "qhl": "QHAIL",
    "refl": "REFL_10CM",
}

CATALOG = register(Catalog("wofs", NATIVES, ROLES))
