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
  also      {role: more field names} that are the same quantity on another grid
            (CM1's staggered w is vertical velocity too): they count for is_role and
            role_of, never for name (optional)
  turbulence  names grouped as "Turbulence" (optional)
  extra_groups  {field name: field-list group} for fields no role places (optional)

The roles (ROLES below) are the inputs of the core's derived fields and defaults; a
new data type maps the ones it has.  Display defaults per role (isosurface values,
contour levels, which role a new map starts on) stay with the code that uses them,
written by role, so every data type gets the same ones."""

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

class Catalog:
    def __init__(self, key, natives, roles, also=None, turbulence=(), extra_groups=None):
        unknown = (set(roles) | set(also or {})) - set(ROLES)
        if unknown:
            raise ValueError(f"unknown roles {sorted(unknown)} (see core.catalog.ROLES)")
        self.key, self.natives, self.roles = key, dict(natives), dict(roles)
        self.also = {r: tuple(ns) for r, ns in (also or {}).items()}
        self.turbulence = frozenset(turbulence)
        self.extra_groups = dict(extra_groups or {})  # {field name: group}
        self._by_name = {}
        for r, n in self.roles.items():
            self._by_name.setdefault(n, r)
        for r, ns in self.also.items():
            for n in ns:
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
        """Whether field `name` (or a derivative's base field: no) plays one of `roles`."""
        return name is not None and self._by_name.get(name) in roles

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

    def reflectivity(self, name):
        """Whether `name` is a reflectivity field (its colours and limits)."""
        return self.is_role(name, "refl", "cref")

    def sounding_names(self):
        """The fields a sounding reads, in order (theta, pres, qv, u, v), or None if
        any is missing."""
        got = self.names(("theta", "pres", "qv", "u", "v"))
        return None if None in got else got


class Union:
    """The catalogs of several runs seen as one (a figure's runs): a field plays a role
    if it does in any of them; names come from the first that has the role."""

    def __init__(self, cats):
        self.cats = list(dict.fromkeys(cats))
        self.key = self.cats[0].key if self.cats else None

    def name(self, role):
        return next((n for n in (c.name(role) for c in self.cats) if n), None)

    def role_of(self, name):
        return next((r for r in (c.role_of(name) for c in self.cats) if r), None)

    def is_role(self, name, *roles):
        return any(c.is_role(name, *roles) for c in self.cats)

    def reflectivity(self, name):
        return self.is_role(name, "refl", "cref")


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
