"""Field catalogs: what one data type's fields are called and how they show.

The core (derived fields, vectors, soundings, the viewer and figure defaults) never
names a data type's fields.  It names **roles** ("w": vertical velocity, "theta":
potential temperature, ...) and asks the run's catalog which field plays each:

    cat = run.catalog            # (or Fields.cat)
    cat.name("w")                # "winterp" for CM1, "W" for WoFS, None if none

A data type supplies one Catalog:

  key       its key in core.models.MODELS (Run.model)
  natives   {field name: (label, units, scale, cmap, vrange, diverging)}: display
            defaults of fields in its files (others: their long name and units)
  roles     {role: field name}; a role a data type lacks is left out
  turbulence  names grouped as "Turbulence" (optional)

The roles (ROLES below) are the inputs of the core's derived fields and defaults; a
new data type maps the ones it has.  Display defaults per role (isosurface values,
contour levels) are the core's, in DEFAULTS, so every data type gets the same ones."""

ROLES = {
    # kinematics, on scalar points, grid-relative (m/s)
    "u": "x wind", "v": "y wind", "w": "vertical velocity",
    "xvort": "x vorticity", "yvort": "y vorticity", "zvort": "vertical vorticity",
    # thermodynamics: potential temperature (K), pressure (Pa), vapour (kg/kg)
    "theta": "potential temperature", "pres": "pressure", "qv": "water vapor mixing ratio",
    # base state (perturbations are relative to it)
    "theta0": "base-state potential temperature", "pres0": "base-state pressure",
    "qv0": "base-state vapor", "u0": "base-state x wind", "v0": "base-state y wind",
    # hydrometeor mixing ratios (kg/kg): cloud (qc, qi) and precipitation (the rest)
    "qc": "cloud water", "qi": "cloud ice", "qr": "rain", "qs": "snow", "qg": "graupel",
    "qhl": "hail",
    # radar: 3D reflectivity, and the composite (2D) when the files have one (dBZ)
    "refl": "reflectivity", "cref": "composite reflectivity",
}

HYDRO = ("qc", "qr", "qi", "qs", "qg", "qhl")
CLOUD = ("qc", "qi")
PRECIP = ("qr", "qs", "qg", "qhl")
KINEMATIC = ("u", "v", "w", "xvort", "yvort", "zvort")
THERMO = ("theta", "pres", "qv")
BASE = ("theta0", "pres0", "qv0", "u0", "v0")

# the core's defaults, by role
DEFAULTS = dict(
    isos=(("refl", 30.0), ("w", 10.0), ("w", -5.0), ("zvort", 0.05)),  # 3D isosurfaces
    main="w",              # the field a new map / section / series / track starts on
    contour=("w", 3.0, (5.0, 15.0, 25.0)),  # (role, height km, levels): a map's contours
)


class Catalog:
    def __init__(self, key, natives, roles, turbulence=(), extra_groups=None):
        unknown = set(roles) - set(ROLES)
        if unknown:
            raise ValueError(f"unknown roles {sorted(unknown)} (see core.catalog.ROLES)")
        self.key, self.natives, self.roles = key, dict(natives), dict(roles)
        self.turbulence = frozenset(turbulence)
        self.extra_groups = dict(extra_groups or {})  # {field name: group}
        self._by_name = {}
        for r, n in self.roles.items():
            self._by_name.setdefault(n, r)

    def name(self, role):
        """The field playing `role`, or None."""
        return self.roles.get(role)

    def names(self, roles):
        """The fields playing `roles` (None for each one missing)."""
        return tuple(self.roles.get(r) for r in roles)

    def role_of(self, name):
        """The role field `name` plays, or None."""
        return self._by_name.get(name)

    def is_role(self, name, *roles):
        """Whether field `name` plays one of `roles`."""
        return name is not None and any(self.roles.get(r) == name for r in roles)

    def group(self, name, ndim):
        """The field-list group of a field in the files."""
        from .fields import PDECOMP
        if ndim == 2:
            return "Swaths & 2D"
        if name in self.extra_groups:
            return self.extra_groups[name]
        role = self.role_of(name)
        if role in ("refl", "cref"):
            return "Radar"
        if name in PDECOMP:
            return "Pressure decomposition"
        if "b_" in name:
            return "Budgets"
        if role in BASE:
            return "Base state"
        if role in KINEMATIC:
            return "Kinematics"
        if role in THERMO:
            return "Thermodynamics"
        if role in HYDRO:
            return "Microphysics"
        if name in self.turbulence:
            return "Turbulence"
        if name.isupper():  # (another model's own names, e.g. WRF's PH)
            return "Other model fields"
        return "Microphysics"

    # ---- the core's defaults, as this data type's names
    def main(self):
        return self.name(DEFAULTS["main"])

    def isos(self):
        """[(field, value)] default isosurfaces (fields this data type has a role for)."""
        return [(self.name(r), v) for r, v in DEFAULTS["isos"] if self.name(r)]

    def contour(self):
        """(field or None, height km, levels) of a map's default contours."""
        r, h, lv = DEFAULTS["contour"]
        return self.name(r), h, lv

    def reflectivity(self, name):
        """Whether `name` is a reflectivity field (its colours and limits)."""
        return self.is_role(name, "refl", "cref")

    def sounding_names(self):
        """The fields a sounding reads, in order (theta, pres, qv, u, v), or None if
        any is missing."""
        got = self.names(("theta", "pres", "qv", "u", "v"))
        return None if None in got else got


CATALOGS = {}


def register(cat):
    CATALOGS[cat.key] = cat
    return cat


def of_model(key):
    """The catalog of data type `key` (a run of no known type: CM1's)."""
    _load()
    return CATALOGS.get(key) or CATALOGS["cm1"]


def _load():
    if "cm1" not in CATALOGS:
        from . import cm1_catalog, wofs_catalog  # noqa: F401  (they register)
