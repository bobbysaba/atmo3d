"""Field catalogs: what one data type's fields are called and how they show.

The core (derived fields, vectors, soundings, the viewer and figure defaults) never
names a data type's fields.  It names **roles** ("w": vertical velocity, "theta":
potential temperature, ...) and asks the run's catalog which field plays each:

    cat = run.catalog            # (or Fields.cat)
    cat.name("w")                # "winterp" for CM1, "W" for WoFS, None if none

A data type supplies one Catalog:

  key       its key in core.models.MODELS (Run.model)
  natives   {field name: (label, units, scale, cmap, vrange, diverging[, group])}:
            display defaults of every field its files can hold (a field it misses:
            tidy(), from the file's long name and units)
  describe  name -> such an entry for fields named by a pattern (optional)
  file_first  derived fields' names its files may hold too (the same quantity): the
            file's is listed when a run has it (optional)
  roles     {role: field name}; a role a data type lacks is left out
  also      {role: more field names} that are the same quantity on another grid
            (CM1's staggered w is vertical velocity too): they count for is_role and
            role_of, never for name (optional)
  turbulence  names grouped as "Turbulence" (optional)
  extra_groups  {field name: field-list group} for fields no role places (optional)
  renamed   {old name: name} of fields this data type's saved files (sessions,
            figures) called otherwise before; rename_fields maps them on load
  other     names of fields listed under "Other" (still offered, out of the main
            lists): rarely wanted ones (optional)
  other_groups  groups whose fields all go under "Other" (optional)
  other_if  {name: another name}: the field goes under "Other" when the run has the
            other one too (CM1's staggered u when uinterp is there) (optional)
  hidden    names of fields not listed at all unless the show_hidden_fields setting is
            on (static, grid and scheme internals) (optional)
  unknown_hidden  file fields this catalog does not name are hidden too (WoFS: a new
            WRF version's extra output never floods the lists) (optional)

Each field has a tier (Catalog.tier): "main", "other" or "hidden".  Derived fields
are "main".  A hidden field still draws in a saved figure that uses it.

The roles (ROLES below) are the inputs of the core's derived fields and defaults; a
new data type maps the ones it has.  Display defaults per role (isosurface values,
contour levels, which role a new map starts on) stay with the code that uses them,
written by role, so every data type gets the same ones."""

import re

ROLES = {
    # kinematics, on scalar points, grid-relative (m/s)
    "u": "x wind", "v": "y wind", "w": "vertical velocity",
    "xvort": "x vorticity", "yvort": "y vorticity", "zvort": "vertical vorticity",
    # thermodynamics: potential temperature (K), pressure (Pa), vapour (kg/kg)
    "theta": "potential temperature", "pres": "pressure", "qv": "water vapor mixing ratio",
    # base state (perturbations are relative to it)
    "theta0": "base-state potential temperature", "pres0": "base-state pressure",
    "qv0": "base-state vapor", "u0": "base-state x wind", "v0": "base-state y wind",
    # base-state condensate, where the files have it (kg/kg; subtracted from the loading)
    "qc0": "base-state cloud water", "qi0": "base-state cloud ice",
    # hydrometeor mixing ratios (kg/kg): cloud (qc, qi) and precipitation (the rest)
    "qc": "cloud water", "qi": "cloud ice", "qr": "rain", "qs": "snow", "qg": "graupel",
    "qhl": "hail",
    # radar: 3D reflectivity, and the composite (2D) when the files have one (dBZ)
    "refl": "reflectivity", "cref": "composite reflectivity",
    # 2D: the Coriolis parameter where it varies (1/s; a run with one f: Run.fcor),
    # winds at 10 m (grid-relative, as u, v), the model's own 2–5 km updraft helicity
    "fcor": "Coriolis parameter", "u10": "10 m x wind", "v10": "10 m y wind",
    "uh25": "updraft helicity 2-5 km",
}

HYDRO = ("qc", "qr", "qi", "qs", "qg", "qhl")
CLOUD = ("qc", "qi")
PRECIP = ("qr", "qs", "qg", "qhl")
KINEMATIC = ("u", "v", "w", "xvort", "yvort", "zvort")
THERMO = ("theta", "pres", "qv")
BASE = ("theta0", "pres0", "qv0", "u0", "v0")
BASE_COND = ("qc0", "qi0")  # (optional: not a base sounding's inputs)
SOUNDING = ("theta", "pres", "qv", "u", "v")  # a sounding's inputs (thermo.analyze)
SOUNDING_BASE = BASE

KAPPA_CM1 = 287.04 / 1005.7


class Catalog:
    def __init__(self, key, natives, roles, also=None, turbulence=(), extra_groups=None,
                 renamed=None, describe=None, file_first=(), other=(), other_groups=(),
                 other_if=None, hidden=(), unknown_hidden=False, kappa=None,
                 condensate=(), other_match=None):
        unknown = (set(roles) | set(also or {})) - set(ROLES)
        if unknown:
            raise ValueError(f"unknown roles {sorted(unknown)} (see core.catalog.ROLES)")
        self.key, self.roles = key, dict(roles)
        # natives' entries may carry a 7th item: the group of the field (when 3D)
        self.natives, groups = {}, {}
        for n, e in natives.items():
            self.natives[n] = tuple(e[:6])
            if len(e) > 6 and e[6]:
                groups[n] = e[6]
        self.also = {r: tuple(ns) for r, ns in (also or {}).items()}
        self.turbulence = frozenset(turbulence)
        self.extra_groups = groups | dict(extra_groups or {})  # {field name: group}
        self.renamed = dict(renamed or {})
        # describe(name): a natives entry (7 items) for fields named by a pattern
        # (CM1's pt1, out2d3, out12), or None
        self._describe = describe
        # file_first: names of derived fields (core.fields) this data type's files may
        # hold as the same quantity under the same name: a run whose files have one
        # lists the file's, not the derived one
        self.file_first = frozenset(file_first)
        self.other, self.other_groups = frozenset(other), frozenset(other_groups)
        # other_match(name): whether a field named by a pattern goes under Other (as
        # `other` does the fields named one by one)
        self.other_match = other_match
        self.other_if = dict(other_if or {})
        self.hidden, self.unknown_hidden = frozenset(hidden), bool(unknown_hidden)
        # kappa: Rd/cp of the model's own θ definition, to get T back from θ exactly
        # (CM1: 287.04/1005.7; WRF: 2/7, as MetPy)
        self.kappa = float(kappa) if kappa is not None else KAPPA_CM1
        # condensate: native names of liquid or ice mass mixing ratios (kg/kg) besides
        # the hydrometeor roles, that buoyancy and θρ load too (CM1's qh, P3's qi1...)
        self.condensate = tuple(condensate)
        self._resolved = {}
        self._index()

    def _index(self):
        self._by_name = {}
        for r, n in self.roles.items():
            self._by_name.setdefault(n, r)
        for r, ns in self.also.items():
            for n in ns:
                self._by_name.setdefault(n, r)

    def resolved(self, names):
        """This catalog for a run whose files hold `names`: a role whose field the run
        lacks is played by an `also` field it has (CM1 with only staggered u, v, w:
        those play u, v, w).  The catalog itself when nothing changes."""
        names = frozenset(names)
        swap = {}
        for r, n in self.roles.items():
            if n not in names:
                alt = next((a for a in self.also.get(r, ()) if a in names), None)
                if alt is not None:
                    swap[r] = alt
        if not swap:
            return self
        key = tuple(sorted(swap.items()))
        got = self._resolved.get(key)
        if got is None:
            import copy
            got = copy.copy(self)
            got.roles = dict(self.roles) | swap
            got._resolved = {}
            got._index()
            self._resolved[key] = got
        return got

    def tier(self, name, group, names=()):
        """'main', 'other' or 'hidden': where field `name` (of field-list group
        `group`) of a run whose files hold `names` is listed."""
        if name in self.hidden:
            return "hidden"
        if self.unknown_hidden and name not in self.natives and \
                (self._describe is None or self._describe(name) is None):
            return "hidden"
        if name in self.other or group in self.other_groups or \
                self.other_if.get(name, "\0") in names or \
                (self.other_match is not None and self.other_match(name)):
            return "other"
        return "main"

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

    def look(self, name, long_name="", units=""):
        """(label, units, scale, cmap, range, diverging) of a field in the files: its
        natives entry, a described one, or else made from the file's long name and
        units (tidy)."""
        if name in self.natives:
            return self.natives[name]
        e = self._describe(name) if self._describe else None
        if e is not None:
            return tuple(e[:6])
        return tidy(name, long_name, units, self)

    def group(self, name, ndim):
        """The field-list group of a field in the files."""
        from .fields import PDECOMP
        if ndim == 2:
            return "Swaths & 2D"
        if name in self.extra_groups:
            return self.extra_groups[name]
        e = self._describe(name) if self._describe else None
        if e is not None and len(e) > 6 and e[6]:
            return e[6]
        role = self.role_of(name)
        if role in ("refl", "cref"):
            return "Radar"
        if name in PDECOMP:
            return "Pressure decomposition"
        if "b_" in name:
            return "Budgets"
        if role in BASE or role in BASE_COND:
            return "Base state"
        if role in KINEMATIC:
            return "Kinematics"
        if role in THERMO:
            return "Thermodynamics"
        if role in HYDRO:
            return "Microphysics"
        if name in self.turbulence:
            return "Turbulence"
        # (a field no table names: never Microphysics by default, as zagl once was)
        return "Other model fields"

    def reflectivity(self, name):
        """Whether `name` is a reflectivity field (its colours and limits)."""
        return self.is_role(name, "refl", "cref")

    def sounding_names(self, base=False):
        """The fields a sounding reads, in order (theta, pres, qv, u, v; base: the base
        state's), or None if any is missing."""
        got = self.names(SOUNDING_BASE if base else SOUNDING)
        return None if None in got else got


_SUPER = {"2": "²", "3": "³", "4": "⁴", "6": "⁶"}
_UNIT_WORDS = {"degree_north": "°N", "degrees_north": "°N", "degree_east": "°E",
               "degrees_east": "°E", "dimensionless": "", "nondimensional": "",
               "unitless": "", "-": "", "none": "", "unknown": "", "dbz": "dBZ"}
_UNIT_TOKEN = re.compile(r"^([A-Za-z#%°]+)\^?\(?(-?\d)?\)?$")


def tidy_units(units):
    """WRF / CF style units written plainly: "m s-1" -> "m/s", "kg m-2 s-1" ->
    "kg/m²/s", "m2 s-2" -> "m²/s²", "degree_north" -> "°N".  Units already plain (or
    not understood) come back as they are, stripped."""
    u = (units or "").strip()
    if u.lower() in _UNIT_WORDS:
        return _UNIT_WORDS[u.lower()]
    if "/" in u or " " not in u and not re.search(r"\d", u):
        return u.replace("^2", "²").replace("^3", "³")
    num, den = [], []
    for tok in u.split():
        m = _UNIT_TOKEN.match(tok)
        if not m:
            return u
        base, exp = m.group(1), int(m.group(2) or 1)
        p = _SUPER.get(str(abs(exp)), "") if abs(exp) != 1 else ""
        (den if exp < 0 else num).append(base + p)
    return (" ".join(num) or ("#" if den == ["kg"] else "1")) + "".join("/" + d for d in den)


def tidy(name, long_name, units, cat=None):
    """(label, units, scale, cmap, range, diverging) of a field no catalog names, from
    its file's long name and units: an ALL-CAPS description in sentence case, units
    written plainly (tidy_units), mixing ratios in g/kg; diverging (RdBu_r) for
    budgets and vorticities."""
    label = " ".join((long_name or name).split())
    if label.isupper():
        label = label.lower()
        label = label[:1].upper() + label[1:]
    elif label[:1].islower():
        label = label[:1].upper() + label[1:]
    units, scale = tidy_units(units), 1.0
    div = "b_" in name or name.lower().endswith("vort")
    if units in ("kg/kg", "g/g") and (name.lower().startswith("q")
                                      or (cat is not None and cat.role_of(name) == "qv0")):
        units, scale = "g/kg", 1000.0
    return label, units, scale, ("RdBu_r" if div else "viridis"), None, div


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


# ------------------------------------------------------------------ saved files
# keys of a saved session or figure whose values (a string or a list of them) name
# fields: a layer's field, an isosurface's var, the 3D floor, a distribution's
# yfield, a parcel colour variable ("@field": a field at the parcels)...  Only these
# are renamed: a figure's panel kind "th" (time-height) or a label is never touched.
FIELD_KEYS = frozenset(("field", "var", "yfield", "xfield", "floor", "fields", "cvar",
                        "color", "plot_x", "plot_y"))


def _renamed(v, table):
    """Field name v with table applied to it, its derivative's base ("ddz.winterp")
    or a field at the parcels ("@winterp")."""
    from .fields import deriv_name, split_deriv
    at = "@" if v.startswith("@") else ""
    op, base = split_deriv(v[len(at):])
    return at + deriv_name(op, table[base]) if base in table else v


def rename_fields(obj, table):
    """Rename, in place, the fields of a saved session or figure (JSON: dicts and
    lists) by table {old: new}, under FIELD_KEYS only.  The number renamed."""
    if not table:
        return 0
    n = 0
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in FIELD_KEYS and isinstance(v, str):
                new = _renamed(v, table)
                if new != v:
                    obj[k], n = new, n + 1
            elif k in FIELD_KEYS and isinstance(v, list) and all(isinstance(x, str) for x in v):
                new = [_renamed(x, table) for x in v]
                n += sum(a != b for a, b in zip(new, v))
                obj[k] = new
            else:
                n += rename_fields(v, table)
    elif isinstance(obj, list):
        for v in obj:
            n += rename_fields(v, table)
    return n


# the field names a saved session or figure uses: its "field_names" (none: 1).  Saving
# writes FIELD_NAMES; on load, derived_renames gives what changed since.  2: the derived
# 3D wind speed wspd became wspd3d (CM1 writes a 2D wspd of its own, the surface layer's)
FIELD_NAMES = 2
RENAMED_DERIVED = {2: {"wspd": "wspd3d"}}  # {field_names: renames that version made}


def derived_renames(doc):
    """{old: new} of the derived fields (every data type's) renamed since saved
    session or figure `doc` was written."""
    v = doc.get("field_names", 1) if isinstance(doc, dict) else FIELD_NAMES
    out = {}
    for ver, table in sorted(RENAMED_DERIVED.items()):
        if not isinstance(v, (int, float)) or v < ver:
            out.update(table)
    return out


def renames_for(paths):
    """(table, note) for a saved file naming runs `paths`: the data type's renamed
    table when every run is of one data type (else {}), and why not when runs of
    several types would each want their own (""; nothing to do)."""
    from . import models
    keys = set()
    for p in paths:
        m = models.detect(p) if p else None
        keys.add(m.key if m is not None else None)
    keys.discard(None)
    tables = {k: of_model(k).renamed for k in keys}
    if len(keys) == 1:
        return tables[keys.pop()], ""
    if any(tables.values()):
        return {}, ("its runs are of several data types and the field names of some "
                    "changed (WoFS: WRF names); fields kept as saved")
    return {}, ""


CATALOGS = {}


def register(cat):
    CATALOGS[cat.key] = cat
    return cat


def of_model(key):
    """The catalog of data type `key` (a run of no known type: CM1's)."""
    _load()
    return CATALOGS.get(key) or CATALOGS["cm1"]


def _load():
    from . import models
    models.load()  # (each data-type package registers its catalog)
