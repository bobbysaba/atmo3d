"""Field catalog (native + derived), display defaults and colormaps."""

import threading
from collections import OrderedDict

import numpy as np
import matplotlib
import matplotlib.colors as mcolors

try:  # registers cmo.* colormaps with matplotlib
    import cmocean  # noqa: F401
except ImportError:  # pragma: no cover
    pass

from .catalog import CLOUD, HYDRO, PRECIP

G = 9.81
RD, RV = 287.04, 461.5
EPS = RD / RV
KAPPA = 287.04 / 1005.7

# --------------------------------------------------------------- colormaps
_NWS_REF = [
    "#04e9e7", "#019ff4", "#0300f4", "#02fd02", "#01c501", "#008e00", "#fdf802",
    "#e5bc00", "#fd9500", "#fd0000", "#d40000", "#bc0000", "#f800fd", "#9854c6",
    "#fdfdfd",
]

CMAPS = [
    "reflectivity", "turbo", "viridis", "magma", "inferno", "plasma", "cividis",
    "RdBu_r", "PuOr_r", "BrBG", "coolwarm", "seismic", "cmo.balance", "cmo.curl",
    "cmo.thermal", "cmo.haline", "cmo.deep", "cmo.rain", "cmo.ice", "cmo.amp",
    "YlGnBu", "YlOrRd", "Spectral_r", "Greys_r", "cubehelix",
]


def _reflectivity(n):
    """NWS-style stepped reflectivity over 0-75 dBZ; < 5 dBZ transparent."""
    out = []
    for v in np.linspace(0, 75, n, endpoint=False):
        idx = int(v // 5) - 1
        out.append("#00000000" if idx < 0 else _NWS_REF[min(idx, len(_NWS_REF) - 1)])
    return out


# colormaps with a neutral (white) middle: kept on 0 when the range has both signs
DIVERGING = {"BrBG", "PiYG", "PRGn", "PuOr", "RdBu", "RdGy", "RdYlBu", "RdYlGn", "bwr",
             "coolwarm", "seismic", "cmo.balance", "cmo.curl", "cmo.delta", "cmo.diff",
             "cmo.tarn"}


def zero_window(name, lo=None, hi=None):
    """(start, stop) of the part of colormap `name` that keeps its middle on 0 over
    lo..hi: -2..6 on RdBu uses 0.33..1 (the colours of -6..6, cut at -2).  (0, 1) when
    the map is not diverging or lo..hi does not cross 0."""
    base = name[:-2] if name.endswith("_r") else name
    if base not in DIVERGING or lo is None or hi is None or not lo < 0 < hi:
        return 0.0, 1.0
    m = 2.0 * max(-lo, hi)
    return 0.5 + lo / m, 0.5 + hi / m


def palette(name, n=256, reverse=False, lo=None, hi=None):
    """n colours of colormap `name`; given lo / hi, a diverging map stays white at 0."""
    if name == "reflectivity":
        pal = _reflectivity(n)
        return pal[::-1] if reverse else pal
    a, b = zero_window(name, lo, hi)
    p = np.linspace(a, b, n)
    cmap = matplotlib.colormaps[name]
    return [mcolors.to_hex(c) for c in cmap(1.0 - p if reverse else p)]


def mpl_cmap(name, reverse=False):
    if name == "reflectivity":
        cm = mcolors.ListedColormap(_reflectivity(256))
    else:
        cm = matplotlib.colormaps[name]
    return cm.reversed() if reverse else cm


# --------------------------------------------------------------- catalog
class FieldDef:
    def __init__(self, name, label, units, group, ndim=3, scale=1.0, cmap="viridis",
                 vrange=None, diverging=False, deps=(), func=None, pointwise=True,
                 storm=False, layer=None, edges=False, costly=False, tier="main",
                 note="", confirmed=True):
        self.name, self.label, self.units, self.group = name, label, units, group
        # confirmed: a derived field whose equation passed the audit (_make_fields sets
        # it from CONFIRMED; an unconfirmed one is hidden, labelled "unverified")
        self.confirmed = confirmed
        # note: what the field leaves out or assumes, in a sentence or two (the
        # derived-field docs page, a tooltip)
        self.note = note
        # tier: where the field lists put it: "main", "other" (under Other) or
        # "hidden" (only with the show_hidden_fields setting): core.catalog.Catalog.tier
        self.tier = tier
        # layer: a column field (2D from 3D natives) over (z0, z1) km AGL, z1 None: the
        # model top.  func(f, c) gets f(n) -> (levels, ny, nx) of native n on the model
        # levels whose cells reach into the layer, c["dz"] (m, each one's thickness in
        # it), c["zk"] (km) and c["top"] (the layer top, km); see column_levels.
        # edges: also the level just below and above the layer (thickness 0), so func
        # can interpolate to its bounds
        self.layer = None if layer is None else tuple(layer)
        self.edges = edges
        # costly: a column field slow per column (parcels): computed on every
        # column_stride(run)-th column, and func gets c["memo"] (a dict shared by the
        # fields of one time, to keep results such as a parcel's) and c["threads"]
        self.costly = costly
        if self.layer is not None:
            ndim, pointwise = 2, False
        self.ndim, self.scale, self.cmap, self.vrange = ndim, scale, cmap, vrange
        self.diverging, self.deps, self.func = diverging, tuple(deps), func
        # deps may name derivatives of native fields ("ddz.winterp": per m, in the
        # field's display units), which Fields and the series worker compute for func
        # pointwise: func works on any samples of its inputs (no spatial derivatives)
        self.pointwise = pointwise and not any(split_deriv(n)[0] for n in self.deps)
        # storm: depends on the storm motion, c["storm"] = ground-relative (u, v) m/s
        self.storm = storm

    @property
    def derived(self):
        return self.func is not None

    @property
    def column(self):
        return self.layer is not None

    def levels(self, z, zf):
        """(ks, dz) of a column field's layer on model levels z, cell faces zf (km)."""
        return column_levels(z, zf, *self.layer, edges=self.edges)

    @property
    def natives(self):
        """The native fields read: deps, with a derivative's base field in its place."""
        return tuple(dict.fromkeys(split_deriv(n)[1] for n in self.deps))

    @property
    def title(self):
        return f"{self.label} ({self.units})" if self.units else self.label


PDECOMP = ("p_b", "p_l", "p_nl", "p_c", "acc_b", "acc_l", "acc_nl", "acc_c")


# ---- derived fields: f(name) fetches a native field (raw units) on the same
# plane/volume, c is a context dict (dx, dy in m; umove, vmove in m/s)
# (temperature, dewpoint, θe and es: thermo's, the copies the soundings use)
def _tempk(f, c):
    """T (K) from θ with the data type's κ (Catalog.kappa: the model's own θ)."""
    return f("theta") * (f("pres") / 1.0e5) ** c.get("kappa", KAPPA)


def _qv(f):
    return np.maximum(f("qv"), 1e-10)


def _vap(f):
    q = _qv(f)
    return f("pres") * q / (EPS + q)


def _dewc(f, c):
    from . import thermo
    return thermo.dewpoint(f("pres"), _qv(f)) - 273.15


def _thetae(f, c):
    """Bolton (1980) eq. 43 equivalent potential temperature (thermo.theta_e)."""
    from . import thermo
    return thermo.theta_e(f("pres"), _tempk(f, c), _qv(f))


def _rh(f, c):
    from . import thermo
    return 100.0 * _vap(f) / thermo.esat(_tempk(f, c))


def _bind(d, cat):
    """FieldDef d, written with role names (core.catalog.ROLES), as the catalog's own
    field names; None if the catalog lacks a role it needs."""
    from .catalog import ROLES

    def name(x):
        op, base = split_deriv(x)
        if base not in ROLES:
            return x
        got = cat.name(base)
        return None if got is None else deriv_name(op, got)

    deps = tuple(name(x) for x in d.deps)
    if None in deps:
        return None
    func = d.func

    def bound(f, c):
        return func(lambda x: f(name(x)), c)

    d.deps, d.func = deps, bound
    return d


# derived fields whose equation Bobby reviewed and confirmed (Phase 2b, 2026-11-19:
# docs-dev/derived-fields.md), each with a test in tests/test_derived_analytic.py or
# beside it.  A derived field not named here is listed only under the hidden fields
# (show_hidden_fields), its label marked "(unverified)": add it after its review.
CONFIRMED = frozenset([
    "thpert", "prspert", "buoy", "bgen_x", "bgen_y", "thrho", "thrhopert", "thetae",
    "tempc", "dewc", "rh", "wspd3d", "hdiv", "xvort", "yvort", "hvort", "wstream",
    "wcross", "p_dyn", "acc_dyn", "acc_tot", "qcloud", "qprecip",
    "zstretch", "ztilt", "ztend", "okubo", "uh25", "uh01",
    "shear0250", "shear0500", "shear01", "shear03", "shear06",
    "srh0250", "srh0500", "srh01", "srh03",
    "sbcape", "sbcin", "sblcl", "mlcape", "mlcin", "mllcl", "mucape", "mucin", "mulcl",
    "stp", "scp",
])
UNVERIFIED = " (unverified)"


def _confirm(d):
    """Derived FieldDef d with its confirmed flag set from CONFIRMED; an unconfirmed one
    moved to the hidden tier and its label marked."""
    d.confirmed = d.name in CONFIRMED
    if not d.confirmed:
        d.tier = "hidden"
        if not d.label.endswith(UNVERIFIED):
            d.label += UNVERIFIED
    return d


# notes shared by several fields (FieldDef.note)
WOFS_PERT = "For WoFS the base state is the member's first time, so this is the change since then."
PARCEL = ("Pseudoadiabatic, liquid only (no ice), with the virtual-temperature correction "
          "and no condensate loading.")
SFC_WIND = "From the 10 m winds when the output has them, else from the lowest model level."
STORM = "Relative to the storm motion used, which the title shows."


def _make_fields(avail, cat):
    """The derived fields computable from fields `avail` of a data type with catalog
    `cat`.  They are written with role names (f("theta"), "ddz.w"), bound to the
    catalog's names on the way out."""
    D = []
    hyd = [r for r in HYDRO if cat.name(r) in avail]
    D.append(FieldDef("thpert", "θ′", "K", "Thermodynamics", cmap="RdBu_r",
                      vrange=(-6, 6), diverging=True, deps=("theta", "theta0"),
                      func=lambda f, c: f("theta") - f("theta0"), note=WOFS_PERT))
    D.append(FieldDef("prspert", "p′", "hPa", "Thermodynamics", cmap="PuOr_r",
                      vrange=(-4, 4), diverging=True, deps=("pres", "pres0"),
                      func=lambda f, c: 0.01 * (f("pres") - f("pres0")),
                      note=WOFS_PERT + " It includes any domain-wide pressure trend."))

    # every condensate the model's buoyancy loads: the hydrometeor roles, and the data
    # type's other liquid and ice species present (Catalog.condensate)
    cond = hyd + [n for n in getattr(cat, "condensate", ()) if n in avail]
    rvrd = RV / RD - 1.0

    def buoy(f, c):  # CM1's (pdcomp.F, solve2.F): g [θ′/θ0 + (Rv/Rd − 1) qv′ − Σ q_cond]
        load = sum(f(n) for n in cond) if cond else 0.0
        return G * ((f("theta") - f("theta0")) / f("theta0")
                    + rvrd * (f("qv") - f("qv0")) - load)

    bdeps = ("theta", "qv", "theta0", "qv0", *cond)
    D.append(FieldDef("buoy", "Buoyancy", "m/s²", "Thermodynamics",
                      cmap="RdBu_r", vrange=(-0.3, 0.3), diverging=True,
                      deps=bdeps, func=buoy,
                      note="No pressure term; no condensate in the base state (qc0, qi0 "
                      "not subtracted). " + WOFS_PERT))

    # baroclinic generation of horizontal vorticity, ∇ × (B k) = (∂B/∂y, −∂B/∂x): the
    # components of the "Baroclinic generation" vector (core/vectors.py).  ∂B/∂x from
    # the inputs' derivatives (B is linear in them), so it is the derivative every
    # other field gets (hgrad: the real grid spacing; terrain: at constant height).
    # Those come in the inputs' display units (qv: g/kg), hence the scales.
    def dbuoy(op):
        def func(f, c):
            th0 = f("theta0")
            out = f(op + ".theta") / th0 - f("theta") * f(op + ".theta0") / th0 ** 2
            out = out + rvrd * (f(op + ".qv") - f(op + ".qv0")) / qs
            for n in cond:
                out = out - f(op + "." + n) / sc[n]
            return G * out
        return func

    def scale(r):  # (a role's or native's display scale: its derivative comes so)
        return float(cat.look(cat.name(r) or r)[2] or 1.0)

    qs, sc = scale("qv"), {n: scale(n) for n in cond}

    def ddeps(op):
        return ("theta", "theta0", op + ".theta", op + ".theta0", op + ".qv", op + ".qv0",
                *(op + "." + n for n in cond))

    BGEN = "B as in buoy; the buoyancy torque only (no term from p′)."
    D.append(FieldDef("bgen_x", "Baroclinic x-vorticity generation (∂B/∂y)", "10⁻⁴ s⁻²",
                      "Kinematics", cmap="RdBu_r", vrange=(-2, 2), diverging=True,
                      deps=ddeps("ddy"), note=BGEN,
                      func=lambda f, c, g=dbuoy("ddy"): 1.0e4 * g(f, c)))
    D.append(FieldDef("bgen_y", "Baroclinic y-vorticity generation (−∂B/∂x)", "10⁻⁴ s⁻²",
                      "Kinematics", cmap="RdBu_r", vrange=(-2, 2), diverging=True,
                      deps=ddeps("ddx"), note=BGEN,
                      func=lambda f, c, g=dbuoy("ddx"): -1.0e4 * g(f, c)))
    # density potential temperature (θ including the vapour and condensate loading)
    def thrho(f, c):
        load = sum(f(n) for n in cond) if cond else 0.0
        return f("theta") * (1.0 + f("qv") / EPS) / (1.0 + f("qv") + load)

    D.append(FieldDef("thrho", "θρ", "K", "Thermodynamics", cmap="cmo.thermal",
                      deps=("theta", "qv", *cond), func=thrho,
                      note="Loads every liquid and ice species in the output."))
    D.append(FieldDef("thrhopert", "θρ′", "K", "Thermodynamics", cmap="RdBu_r",
                      vrange=(-6, 6), diverging=True, deps=("theta", "qv", "theta0", "qv0", *cond),
                      func=lambda f, c: thrho(f, c) - f("theta0") * (1.0 + f("qv0") / EPS)
                      / (1.0 + f("qv0")),
                      note="The base state has no condensate. " + WOFS_PERT))
    D.append(FieldDef("thetae", "θe", "K", "Thermodynamics", cmap="Spectral_r",
                      deps=("theta", "pres", "qv"), func=_thetae,
                      note="Pseudo-equivalent; the dewpoint is over liquid and held at or "
                      "below T."))
    D.append(FieldDef("tempc", "Temperature", "°C", "Thermodynamics", cmap="cmo.thermal",
                      deps=("theta", "pres"), func=lambda f, c: _tempk(f, c) - 273.15,
                      note="κ is the model's own: CM1's Rd/cp, or WRF's 2/7 for WoFS."))
    D.append(FieldDef("dewc", "Dewpoint", "°C", "Thermodynamics", cmap="YlGnBu",
                      deps=("pres", "qv"), func=_dewc,
                      note="Over liquid water at every temperature (no frost point)."))
    D.append(FieldDef("rh", "Relative humidity (liquid)", "%", "Thermodynamics",
                      cmap="YlGnBu", vrange=(0, 100), deps=("theta", "pres", "qv"), func=_rh,
                      note="Over liquid water at every temperature, so below 0 °C it reads "
                      "lower than RH over ice. Not capped at 100 %."))
    D.append(FieldDef("wspd3d", "Wind speed (ground-relative)", "m/s", "Kinematics",
                      cmap="turbo", vrange=(0, 40), deps=("u", "v"),
                      func=lambda f, c: np.hypot(f("u") + c["umove"],
                                                 f("v") + c["vmove"]),
                      note="The horizontal wind only (no w)."))

    NO_MAPFAC = "No map factor (WoFS's map projection is left out)."
    D.append(FieldDef("hdiv", "Horizontal divergence", "10⁻³ s⁻¹", "Kinematics",
                      cmap="PuOr_r", vrange=(-10, 10), diverging=True,
                      deps=("ddx.u", "ddy.v"),
                      func=lambda f, c: 1.0e3 * (f("ddx.u") + f("ddy.v")),
                      note=NO_MAPFAC))
    # ζ: the files' (CM1, WoFS), or from the winds where a data type writes none (a
    # regridded radar run): ζ = ∂v/∂x − ∂u/∂y
    if cat.name("zvort") not in avail and cat.name("u") in avail and cat.name("v") in avail:
        D.append(FieldDef("zvort", "Vertical vorticity (∂v/∂x − ∂u/∂y)", "1/s", "Kinematics",
                          cmap="RdBu_r", vrange=(-0.05, 0.05), diverging=True,
                          deps=("ddx.v", "ddy.u"),
                          func=lambda f, c: f("ddx.v") - f("ddy.u"), note=NO_MAPFAC))
    # ξ, η: the files' (CM1), or from the winds where a data type writes none (WoFS):
    # ξ = ∂w/∂y − ∂v/∂z, η = ∂u/∂z − ∂w/∂x, listed as xvort / yvort
    xi, eta, xdeps, ydeps = horizontal_vorticity(cat, avail)
    if cat.name("xvort") not in avail and set(xdeps) - {"xvort"}:
        D.append(FieldDef("xvort", "x vorticity (∂w/∂y − ∂v/∂z)", "1/s", "Kinematics",
                          cmap="RdBu_r", vrange=(-0.05, 0.05), diverging=True,
                          deps=xdeps, func=lambda f, c: xi(f), note=NO_MAPFAC))
        D.append(FieldDef("yvort", "y vorticity (∂u/∂z − ∂w/∂x)", "1/s", "Kinematics",
                          cmap="RdBu_r", vrange=(-0.05, 0.05), diverging=True,
                          deps=ydeps, func=lambda f, c: eta(f), note=NO_MAPFAC))
    D.append(FieldDef("hvort", "Horizontal vorticity magnitude", "1/s", "Kinematics",
                      cmap="magma", vrange=(0, 0.1), deps=xdeps + ydeps,
                      func=lambda f, c: np.hypot(xi(f), eta(f))))

    # horizontal vorticity along / across the storm-relative horizontal wind; c["storm"]
    # is the storm motion (ground-relative), the grid winds are relative to (umove, vmove)
    def sr_unit(f, c):
        us = f("u") + (c["umove"] - c["storm"][0])
        vs = f("v") + (c["vmove"] - c["storm"][1])
        sp = np.maximum(np.hypot(us, vs), 1e-6)
        return us / sp, vs / sp

    def wstream(f, c):
        sx, sy = sr_unit(f, c)
        return xi(f) * sx + eta(f) * sy

    def wcross(f, c):  # positive: vorticity to the left of the storm-relative wind
        sx, sy = sr_unit(f, c)
        return -xi(f) * sy + eta(f) * sx

    SR_DIR = STORM + " The direction is arbitrary where the storm-relative wind is near 0."
    vdeps = tuple(dict.fromkeys(xdeps + ydeps + ("u", "v")))
    D.append(FieldDef("wstream", "Streamwise vorticity", "1/s", "Kinematics", cmap="RdBu_r",
                      vrange=(-0.05, 0.05), diverging=True, deps=vdeps, func=wstream,
                      storm=True, note=SR_DIR))
    D.append(FieldDef("wcross", "Crosswise vorticity", "1/s", "Kinematics", cmap="RdBu_r",
                      vrange=(-0.05, 0.05), diverging=True, deps=vdeps, func=wcross,
                      storm=True, note=SR_DIR))
    D.append(FieldDef("p_dyn", "p′ dynamic (p_l + p_nl + p_c)", "Pa", "Pressure decomposition",
                      cmap="PuOr_r", diverging=True, deps=("p_l", "p_nl", "p_c"),
                      func=lambda f, c: f("p_l") + f("p_nl") + f("p_c")))
    D.append(FieldDef("acc_dyn", "Dynamic VPPGA (linear + nonlinear + Coriolis)", "m/s²",
                      "Pressure decomposition", cmap="RdBu_r", diverging=True,
                      deps=("acc_l", "acc_nl", "acc_c"),
                      func=lambda f, c: f("acc_l") + f("acc_nl") + f("acc_c")))
    D.append(FieldDef("acc_tot", "Total acceleration (b + l + nl + c)", "m/s²",
                      "Pressure decomposition", cmap="RdBu_r", diverging=True,
                      deps=("acc_b", "acc_l", "acc_nl", "acc_c"),
                      func=lambda f, c: f("acc_b") + f("acc_l") + f("acc_nl") + f("acc_c"),
                      note="Leaves out the rest of w's equation: turbulence, damping and "
                      "the compressible part."))
    if hyd:
        cl = [n for n in CLOUD if n in hyd]
        pr = [n for n in PRECIP if n in hyd]
        if cl:
            D.append(FieldDef("qcloud", "Cloud condensate (qc+qi)", "g/kg", "Microphysics",
                              cmap="cmo.ice", vrange=(0, 3), deps=cl,
                              func=lambda f, c: 1000.0 * sum(f(n) for n in cl)))
        if pr:
            D.append(FieldDef("qprecip", "Precipitation (qr+qs+qg+qhl)", "g/kg",
                              "Microphysics", cmap="cmo.rain", vrange=(0, 8), deps=pr,
                              func=lambda f, c: 1000.0 * sum(f(n) for n in pr),
                              note="Snow counts as precipitation."))
    D += _vort_tendencies(cat, avail, xi, eta, xdeps, ydeps)
    D += _columns(cat, avail)
    D += _sounding_kinematics(cat, avail)
    D += _sounding_thermo(cat, avail)
    D = [_bind(_confirm(d), cat) for d in D]
    return [d for d in D if d is not None and all(x in avail for x in d.natives)]


def horizontal_vorticity(cat, avail):
    """(xi(f), eta(f), xi's deps, eta's deps): ξ and η as the files have them, or from
    the winds' derivatives (per m: 1/s) for a data type without them."""
    if cat.name("xvort") in avail and cat.name("yvort") in avail:
        return (lambda f: f("xvort")), (lambda f: f("yvort")), ("xvort",), ("yvort",)
    return ((lambda f: f("ddy.w") - f("ddz.v")), (lambda f: f("ddz.u") - f("ddx.w")),
            ("ddy.w", "ddz.v"), ("ddz.u", "ddx.w"))


def _vort_tendencies(cat, avail, xi, eta, xdeps, ydeps):
    """Vertical-vorticity tendencies and the Okubo–Weiss parameter, in 10⁻⁴ s⁻².  Their
    deps' derivatives are per m (m/s per m = 1/s).  Stretching acts on the absolute
    vorticity ζ + f, with f the fcor role where the data type has it (WoFS's F), else
    the run's one f (c["f"]: Run.fcor; 0 for none)."""
    has_f = cat.name("fcor") in avail

    def fcor(f, c):
        return f("fcor") if has_f else c.get("f", 0.0)

    def stretch(f, c):  # −(ζ + f) ∇h·V (anelastic)
        return -1.0e4 * (f("zvort") + fcor(f, c)) * (f("ddx.u") + f("ddy.v"))

    def tilt(f, c):  # ξ ∂w/∂x + η ∂w/∂y
        return 1.0e4 * (xi(f) * f("ddx.w") + eta(f) * f("ddy.w"))

    def okubo(f, c):  # W = s_n² + s_s² − ω² (strain dominates > 0, rotation < 0)
        ux, uy, vx, vy = (f("ddx.u"), f("ddy.u"), f("ddx.v"),
                          f("ddy.v"))
        return 1.0e4 * ((ux - vy) ** 2 + (vx + uy) ** 2 - (vx - uy) ** 2)

    g, kw = "Vorticity tendencies", dict(cmap="RdBu_r", vrange=(-5, 5), diverging=True)
    sdeps = ("zvort", "ddx.u", "ddy.v") + (("fcor",) if has_f else ())
    tdeps = tuple(dict.fromkeys(xdeps + ydeps + ("ddx.w", "ddy.w")))
    left_out = "advection, mixing and the baroclinic and solenoidal terms are left out."
    return [
        FieldDef("zstretch", "ζ stretching (−(ζ + f) ∇h·V)", "10⁻⁴ s⁻²", g, deps=sdeps,
                 func=stretch, note="Anelastic form; f is the run's Coriolis parameter.",
                 **kw),
        FieldDef("ztilt", "ζ tilting (ξ ∂w/∂x + η ∂w/∂y)", "10⁻⁴ s⁻²", g, deps=tdeps,
                 func=tilt, **kw),
        FieldDef("ztend", "ζ stretching + tilting", "10⁻⁴ s⁻²", g,
                 deps=tuple(dict.fromkeys(sdeps + tdeps)),
                 func=lambda f, c: stretch(f, c) + tilt(f, c),
                 note="Not the full ζ tendency: " + left_out, **kw),
        FieldDef("okubo", "Okubo–Weiss (s_n² + s_s² − ω²)", "10⁻⁴ s⁻²", g,
                 deps=("ddx.u", "ddy.u", "ddx.v", "ddy.v"),
                 func=okubo, note="ω is from the winds, not the files' ζ.", **kw),
    ]


def _columns(cat, avail):
    """Column fields (2D from 3D): updraft helicity, summed where w > 0 and ζ > 0 (as
    CM1's own uh).  2–5 km only for a data type whose files have none (the uh25 role:
    CM1's uh, WoFS's UH)."""
    def uh(f, c):  # ∫ w ζ dz over the updraft's cyclonic part
        w, z = f("w"), f("zvort")
        return layer_sum(c["dz"], np.where((w > 0) & (z > 0), w * z, 0.0))

    g = "Column fields"
    out = [FieldDef("uh01", "Updraft helicity 0–1 km", "m²/s²", g, cmap="magma",
                    vrange=(0, 50), deps=("w", "zvort"), func=uh, layer=(0.0, 1.0),
                    note="∫ w ζ dz where w > 0 and ζ > 0.")]
    if cat.name("uh25") not in avail:
        out.insert(0, FieldDef("uh25", "Updraft helicity 2–5 km", "m²/s²", g, cmap="magma",
                               vrange=(0, 300), deps=("w", "zvort"), func=uh,
                               layer=(2.0, 5.0), note="∫ w ζ dz where w > 0 and ζ > 0."))
    return out


def _wind(f, c):  # ground-relative
    return f("u") + c["umove"], f("v") + c["vmove"]


def bulk_shear(u, v, zk, top):
    """|V(top) − V(lowest level)| of (L, ...) winds on levels zk (km)."""
    return np.hypot(at_height(u, zk, top) - u[0], at_height(v, zk, top) - v[0])


def helicity(u, v, zk, top, storm):
    """Storm-relative helicity from the lowest level to top km:
    Σ (u_k+1 − cx)(v_k − cy) − (u_k − cx)(v_k+1 − cy).  zk: (L,) or each column's
    (L, ...) heights."""
    if np.ndim(zk) > 1:
        return _helicity_columns(u - storm[0], v - storm[1], np.asarray(zk, np.float64),
                                 top)
    u = layer_points(u - storm[0], zk, top)
    v = layer_points(v - storm[1], zk, top)
    return (u[1:] * v[:-1] - u[:-1] * v[1:]).sum(axis=0)


def _helicity_columns(u, v, zk, top):
    """helicity of (L, ...) storm-relative winds on each column's own heights zk:
    the pairs of levels below top, then the highest of those with the wind at top."""
    pair = u[1:] * v[:-1] - u[:-1] * v[1:]
    out = np.where(zk[1:] < top, pair, 0.0).sum(axis=0)
    nb = (zk < top).sum(axis=0)
    kl = np.maximum(nb - 1, 0)[None]
    ul, vl = np.take_along_axis(u, kl, 0)[0], np.take_along_axis(v, kl, 0)[0]
    ut, vt = at_height(u, zk, top), at_height(v, zk, top)
    return out + np.where(nb > 0, ut * vl - ul * vt, 0.0)


def wind_profile(f, c, sfc):
    """(u, v, zk) ground-relative winds of a column field's levels, starting with the
    10 m winds (u10, v10 roles) when sfc and the lowest level is above 10 m."""
    u, v = _wind(f, c)
    zk = c["zk"]
    if not sfc or np.min(zk[0]) <= 0.01:
        return u, v, zk
    u10 = f("u10")[0] + c["umove"]  # (2D: a column field gets it as one level)
    v10 = f("v10")[0] + c["vmove"]
    z10 = np.full_like(np.asarray(zk[:1], np.float64), 0.01)
    return (np.concatenate([np.broadcast_to(u10, u.shape[1:])[None], u]),
            np.concatenate([np.broadcast_to(v10, v.shape[1:])[None], v]),
            np.concatenate([z10, np.asarray(zk, np.float64)]))


def _sounding_kinematics(cat=None, avail=()):
    """Bulk shear and storm-relative helicity of every column, as the soundings give
    them (thermo.analyze): from the 10 m winds where the data type has them (u10,
    v10), else the lowest model level, up to the layer top, the winds linearly
    interpolated between the levels."""
    sfc = cat is not None and cat.name("u10") in avail and cat.name("v10") in avail

    def shear(f, c):
        u, v, zk = wind_profile(f, c, sfc)
        return bulk_shear(u, v, zk, c["top"])

    def srh(f, c):
        u, v, zk = wind_profile(f, c, sfc)
        return helicity(u, v, zk, c["top"], c["storm"])

    g, deps = "Sounding parameters", ("u", "v") + (("u10", "v10") if sfc else ())
    kw = dict(deps=deps, edges=True)
    srh_note = SFC_WIND + " " + STORM
    # (name, label of the layer, top km, starting range top): shear, then SRH
    shears = (("shear0250", "0–250 m", 0.25, 15), ("shear0500", "0–500 m", 0.5, 20),
              ("shear01", "0–1 km", 1.0, 25), ("shear03", "0–3 km", 3.0, 35),
              ("shear06", "0–6 km", 6.0, 40))
    srhs = (("srh0250", "0–250 m", 0.25, 200), ("srh0500", "0–500 m", 0.5, 250),
            ("srh01", "0–1 km", 1.0, 300), ("srh03", "0–3 km", 3.0, 500))
    return [
        *(FieldDef(n, f"Bulk shear {lab}", "m/s", g, cmap="viridis", vrange=(0, top),
                   func=shear, layer=(0.0, z), note=SFC_WIND, **kw)
          for n, lab, z, top in shears),
        *(FieldDef(n, f"Storm-relative helicity {lab}", "m²/s²", g, cmap="RdBu_r",
                   vrange=(-top, top), diverging=True, func=srh, layer=(0.0, z),
                   storm=True, note=srh_note, **kw) for n, lab, z, top in srhs),
    ]


def _parcel(f, c, kind):
    """(CAPE, CIN, LCL m) of parcel kind ('sb', 'ml', 'mu') in the columns, kept in
    c["memo"] for the other fields of this time."""
    memo = c.get("memo")
    if memo is not None and kind in memo:
        return memo[kind]
    from . import thermo
    out = thermo.parcel_columns(1000.0 * np.asarray(c["zk"], np.float64), f("pres"),
                                f("theta"), f("qv"), kind, c.get("threads", 1),
                                c.get("kappa", KAPPA))
    if memo is not None:
        memo[kind] = out
    return out


def _sounding_thermo(cat=None, avail=()):
    """CAPE, CIN and LCL of surface-based, 100 hPa mixed-layer and most-unstable
    parcels in every column, and fixed-layer STP and SCP: as the soundings compute
    them (thermo.analyze), on every column_stride-th column."""
    g, deps = "Sounding parameters", ("pres", "theta", "qv")
    kw = dict(layer=(0.0, None), costly=True)
    names = dict(sb="Surface-based", ml="Mixed-layer (100 hPa)", mu="Most-unstable")
    D = []
    for kind, lab in names.items():
        def pick(i, kind=kind):
            return lambda f, c: _parcel(f, c, kind)[i]
        D += [
            FieldDef(f"{kind}cape", f"{lab} CAPE", "J/kg", g, cmap="magma",
                     vrange=(0, 4000), deps=deps, func=pick(0), note=PARCEL, **kw),
            FieldDef(f"{kind}cin", f"{lab} CIN", "J/kg", g, cmap="cmo.ice",
                     vrange=(-300, 0), deps=deps, func=pick(1), note=PARCEL, **kw),
            FieldDef(f"{kind}lcl", f"{lab} LCL height", "m AGL", g, cmap="cividis",
                     vrange=(0, 3000), deps=deps, func=pick(2), **kw),
        ]

    sfc = cat is not None and cat.name("u10") in avail and cat.name("v10") in avail

    def stp(f, c):  # (SBCAPE/1500)(SBLCL term)(0–1 km SRH/150)(0–6 km shear term)
        cape, _, lcl = _parcel(f, c, "sb")
        u, v, zk = wind_profile(f, c, sfc)
        bwd = bulk_shear(u, v, zk, 6.0)
        return ((cape / 1500.0) * np.clip((2000.0 - lcl) / 1000.0, 0.0, 1.0)
                * (helicity(u, v, zk, 1.0, c["storm"]) / 150.0)
                * np.where(bwd < 12.5, 0.0, np.minimum(bwd, 30.0) / 20.0))

    def scp(f, c):  # (MUCAPE/1000)(0–3 km SRH/50)(0–6 km shear term)(MUCIN term)
        cape, cin, _ = _parcel(f, c, "mu")
        u, v, zk = wind_profile(f, c, sfc)
        bwd = bulk_shear(u, v, zk, 6.0)
        return ((cape / 1000.0) * (helicity(u, v, zk, 3.0, c["storm"]) / 50.0)
                * np.where(bwd < 10.0, 0.0, np.minimum(bwd, 20.0) / 20.0)
                * np.where(cin > -40.0, 1.0, -40.0 / np.minimum(cin, -40.0)))

    wdeps = deps + ("u", "v") + (("u10", "v10") if sfc else ())
    ckw = dict(cmap="RdBu_r", diverging=True, deps=wdeps, storm=True, **kw)
    D += [
        FieldDef("stp", "Significant tornado parameter (fixed layer)", "", g,
                 vrange=(-6, 6), func=stp,
                 note="Fixed layers (not the effective layer); no CIN term. " + SFC_WIND,
                 **ckw),
        FieldDef("scp", "Supercell composite parameter (fixed layer)", "", g,
                 vrange=(-20, 20), func=scp,
                 note="0–3 km SRH and 0–6 km shear stand in for the effective-layer "
                 "ones. " + SFC_WIND, **ckw),
    ]
    return D


COSTLY = frozenset(d.name for d in _sounding_thermo())  # (names of the costly fields)


def finite_sample(a, n=200000):
    """About n of a's finite values, evenly spaced (for percentiles of a large array:
    the stride is taken before the finite test, so no full-size copy is made)."""
    a = np.asarray(a).ravel()
    sub = a[:: max(1, a.size // n)]
    return sub[np.isfinite(sub)]


def column_stride(run):
    """Columns apart of the costly column fields' computed columns: the column_stride
    setting; auto: the smallest that keeps them to about 250 000 (1 up to 500 x 500)."""
    from .. import config
    s = config.get("column_stride")
    if s == "auto":
        s = int(np.ceil(np.sqrt(run.ni * run.nj / 250000.0)))
    return max(1, int(s))


def stride_cols(lo, hi, n, s):
    """Points lo..hi-1 (of n along an axis) on a stride s: each s-wide block (from 0)
    takes the value at its middle point.  Returns (r0, r1, take, back): read r0..r1,
    keep `take` of those (relative to r0); back[i - lo] is point i's among the kept."""
    idx = np.minimum((np.arange(lo, hi) // s) * s + s // 2, n - 1)
    u, back = np.unique(idx, return_inverse=True)
    return int(u[0]), int(u[-1]) + 1, u - u[0], back


def at_height(a, zk, h):
    """(L, ...) values a on levels zk (km; (L,), or (L, ...): each column's own)
    linearly interpolated to height h km, held at the end levels beyond them."""
    zk = np.asarray(zk, dtype=np.float64)
    if zk.ndim > 1:
        L = zk.shape[0]
        if L == 1:
            return a[0]
        k1 = np.clip((zk < h).sum(axis=0), 1, L - 1)[None]
        z0, z1 = np.take_along_axis(zk, k1 - 1, 0)[0], np.take_along_axis(zk, k1, 0)[0]
        with np.errstate(divide="ignore", invalid="ignore"):
            w = np.clip((h - z0) / (z1 - z0), 0.0, 1.0)
        w = np.where(np.isfinite(w), w, 0.0)
        return (1.0 - w) * np.take_along_axis(a, k1 - 1, 0)[0] + \
            w * np.take_along_axis(a, k1, 0)[0]
    if zk.size == 1 or h <= zk[0]:
        return a[0]
    if h >= zk[-1]:
        return a[-1]
    k = int(np.searchsorted(zk, h)) - 1
    w = (h - zk[k]) / (zk[k + 1] - zk[k])
    return (1.0 - w) * a[k] + w * a[k + 1]


def layer_points(a, zk, top):
    """(P, ...) a from the lowest level up to height top km: the levels below it, then
    its value at top (interpolated)."""
    zk = np.asarray(zk, dtype=np.float64)
    below = np.flatnonzero(zk < top)
    if below.size == 0:
        return a[:1]
    return np.concatenate([a[below], at_height(a, zk, top)[None]])


def layer_top(d, run):
    """Top (km) of column field d's layer (None: the model top)."""
    return float(run.zf[-1]) if d.layer[1] is None else float(d.layer[1])


def column_levels(z, zf, z0, z1, edges=False):
    """(ks, dz) of a column layer z0..z1 km AGL (z1 None: the model top): the model
    levels (heights z, km) whose cells (between the zf levels) reach into it, and each
    one's thickness inside it (m), so sum(dz * f[ks]) integrates f over the layer.
    edges: also the level below and above those (where there is one), thickness 0."""
    zf = np.asarray(zf, dtype=np.float64)
    top = zf[-1] if z1 is None else float(z1)
    lo, hi = np.clip(zf[:-1], z0, top), np.clip(zf[1:], z0, top)
    ks = np.flatnonzero(hi > lo)
    if ks.size == 0:  # (a layer thinner than nothing: the nearest level)
        ks = np.array([int(np.argmin(np.abs(np.asarray(z) - z0)))])
        return [int(ks[0])], np.zeros(1)
    dz = 1000.0 * (hi - lo)[ks]
    if edges:
        lo_k, hi_k = int(ks[0]) - 1, int(ks[-1]) + 1
        if lo_k >= 0:
            ks, dz = np.concatenate([[lo_k], ks]), np.concatenate([[0.0], dz])
        if hi_k < len(zf) - 1:
            ks, dz = np.concatenate([ks, [hi_k]]), np.concatenate([dz, [0.0]])
    return [int(k) for k in ks], dz


def column_levels_3d(Z, Zw, z0, z1, edges=False):
    """column_levels on a terrain run's own heights: Z (nk, ...) of the levels and Zw
    (nk + 1, ...) of the cell faces (km above ground).  Returns (ks, dz, zk): the
    levels whose cells reach into the layer in any column (with edges also the one
    below and above those), each one's thickness in it in every column ((L, ...) m, 0
    where outside it) and their heights ((L, ...) km)."""
    Zw = np.asarray(Zw, dtype=np.float64)
    top = Zw[-1] if z1 is None else float(z1)
    lo, hi = np.clip(Zw[:-1], z0, top), np.clip(Zw[1:], z0, top)
    th = hi - lo
    ks = np.flatnonzero((th > 0).reshape(th.shape[0], -1).any(axis=1))
    if ks.size == 0:  # (a layer thinner than nothing: the nearest level)
        k = int(np.argmin(np.abs(np.asarray(Z).reshape(len(Z), -1).mean(axis=1) - z0)))
        return [k], np.zeros((1,) + th.shape[1:]), np.asarray(Z[k:k + 1], np.float64)
    ks = list(range(int(ks[0]), int(ks[-1]) + 1))
    if edges:
        ks = ([ks[0] - 1] if ks[0] > 0 else []) + ks + \
            ([ks[-1] + 1] if ks[-1] + 1 < th.shape[0] else [])
    return ks, 1000.0 * th[ks], np.asarray(Z, np.float64)[ks]


def layer_sum(dz, a):
    """Σ dz a over a column field's levels: dz (L,) or each column's (L, ...)."""
    dz = np.asarray(dz)
    return np.tensordot(dz, a, axes=1) if dz.ndim == 1 else (dz * a).sum(axis=0)


def in_layer(a, dz, fill):
    """(L, ...) a, with `fill` where a column's level is outside the layer (dz 0 there,
    on a terrain run's own heights; with one profile dz, a as it is)."""
    dz = np.asarray(dz)
    return a if dz.ndim == 1 else np.where(dz > 0, a, fill)


def ddz_volume(b, z):
    """∂/∂z (per m) of a volume (nk, ...) on heights z (km): (nk,) as np.gradient, or
    each column's own (nk, ...) with the same centred / one-sided differences."""
    z = np.asarray(z)
    if z.ndim == 1:
        return np.gradient(b, 1000.0 * z, axis=0)
    out = np.empty(b.shape, dtype=np.float32)
    for k in range(b.shape[0]):
        out[k] = ddz_level(lambda kk: b[kk], z, k)
    return out


GROUP_ORDER = ["Radar", "Kinematics", "Vorticity tendencies", "Column fields",
               "Sounding parameters", "Thermodynamics",
               "Pressure decomposition", "Microphysics", "Microphysics (number & moments)",
               "Swaths & 2D", "Turbulence", "Boundary layer", "Radiation", "Cumulus",
               "Electrification", "Budgets", "Time averages", "Heights",
               "Other model fields", "Base state"]


# group-name prefixes of the field lists: derived fields, Other, hidden (group_options;
# viewer.fieldmenu nests them under entries of their own)
DERIVED_PREFIX, OTHER_PREFIX, HIDDEN_PREFIX = "Derived · ", "Other · ", "Hidden · "


def show_hidden():
    """Whether the field lists show hidden fields (the show_hidden_fields setting)."""
    from .. import config
    return bool(config.get("show_hidden_fields"))


def listed(d):
    """Whether FieldDef d is offered in field lists (not hidden, or the
    show_hidden_fields setting on)."""
    return d.tier != "hidden" or show_hidden()


class Groups(OrderedDict):
    """group_options' {group: {label: name}}, with .tips: {name: the field's note} for
    the pickers' tooltips (a copy made of it by hand just goes without tips)."""
    tips = {}


def group_options(defs, ndim=None, label=None):
    """{group: {label: name}} of FieldDefs `defs` for the field pickers
    (viewer.fieldmenu; grouped Selects too): the fields in the files by group
    (GROUP_ORDER), then the derived ones ("Derived · <group>"), then those under Other
    ("Other · <group>"), then the hidden ones ("Hidden · <group>") only with the
    show_hidden_fields setting.  label(d): an option's text (default
    "<label> [<name>]")."""
    shown = show_hidden()
    kinds = ("main", "derived", "other", "hidden")
    tiers = {t: OrderedDict((g, OrderedDict()) for g in GROUP_ORDER) for t in kinds}
    for d in defs:
        if (ndim is not None and d.ndim != ndim) or (d.tier == "hidden" and not shown):
            continue
        kind = "derived" if d.tier == "main" and d.derived else d.tier
        text = label(d) if label else f"{d.label} [{d.name}]"
        tiers[kind].setdefault(d.group, OrderedDict())[text] = d.name
    out = Groups()
    for kind, prefix in zip(kinds, ("", DERIVED_PREFIX, OTHER_PREFIX, HIDDEN_PREFIX)):
        out.update((prefix + g, v) for g, v in tiers[kind].items() if v)
    out.tips = {d.name: d.note for d in defs if d.note}
    return out


# ---- derivatives of any field, per m: "ddz.winterp" (∂w/∂z), "ddx.", "ddy.", "gradh."
# (|∇h|).  Built on demand by Fields / AllFields, not listed in the field lists: a
# Derivative select beside a Field select names them (deriv_name).
DERIVS = OrderedDict([("ddz", "∂/∂z"), ("ddx", "∂/∂x"), ("ddy", "∂/∂y"), ("gradh", "|∇h|")])


def deriv_name(op, base):
    """The field name of derivative op ('' : none) of field `base`."""
    return f"{op}.{base}" if op else base


def split_deriv(name):
    """(op, base field) of a derivative's name; ('', name) for any other field."""
    if not isinstance(name, str):
        return "", name
    op, dot, base = name.partition(".")
    return (op, base) if dot and op in DERIVS else ("", name)


def deriv_options(d):
    """{label: op} for a Derivative select of field d (∂/∂z: 3D fields only)."""
    return {"None": ""} | {v: k for k, v in DERIVS.items() if k != "ddz" or d.ndim == 3}


def _per_m(units):
    """A field's units per metre (a derivative's)."""
    return {"m/s": "1/s", "m": "", "1/s": "1/(m s)", "": "1/m"}.get(
        units, f"({units})/m" if " " in units or "/" in units else f"{units}/m")


def _no_func(f, c):
    raise ValueError("a derivative is computed from whole levels (Fields.plane / volume)")


def deriv_def(op, base):
    """FieldDef of derivative op of field `base` (a FieldDef), in its units per m
    (m/s: 1/s); None when there is none (∂/∂z of a 2D field)."""
    if op not in DERIVS or (op == "ddz" and base.ndim != 3):
        return None
    vr = None
    if base.vrange is not None:  # (a starting range: half the field's per km, in /m)
        m = 0.5e-3 * max(abs(float(base.vrange[0])), abs(float(base.vrange[1])))
        vr = (0.0, m) if op == "gradh" else (-m, m)
    deps = base.deps if base.derived else (base.name,)
    return FieldDef(deriv_name(op, base.name), f"{base.label} · {DERIVS[op]}",
                    _per_m(base.units), "Derivatives", ndim=base.ndim,
                    cmap="magma" if op == "gradh" else "RdBu_r", vrange=vr,
                    diverging=op != "gradh", deps=deps, func=_no_func, pointwise=False,
                    storm=base.storm, confirmed=base.confirmed)


def ddz_level(f, z, k):
    """∂/∂z (per m) on model level k of f(level) -> plane, on levels z (km): centred
    on the stretched levels inside, one-sided at the bottom and top (as np.gradient of
    the volume, so maps, sections and series agree)."""
    nk = len(z)
    k = min(max(int(k), 0), nk - 1)
    lo, hi = max(k - 1, 0), min(k + 1, nk - 1)
    if lo == hi:
        return np.zeros_like(f(k))
    if lo == k or hi == k:
        return (f(hi) - f(lo)) / (1000.0 * (z[hi] - z[lo]))
    hl, hr = z[k] - z[lo], z[hi] - z[k]  # (km)
    return (hl * hl * f(hi) - hr * hr * f(lo) + (hr * hr - hl * hl) * f(k)) / \
        (1000.0 * hl * hr * (hl + hr))


def hgrad(op, a, xkm, ykm):
    """Horizontal derivative op ('ddx', 'ddy', 'gradh') of a (..., ny, nx) array on
    the grid's x / y (km; stretched grids too), per m."""
    def d(axis, c):
        return np.gradient(a, 1000.0 * np.asarray(c, dtype=np.float64), axis=axis) \
            if a.shape[axis] > 1 else np.zeros_like(a)
    if op == "ddx":
        return d(-1, xkm)
    if op == "ddy":
        return d(-2, ykm)
    return np.hypot(d(-1, xkm), d(-2, ykm))


def hgrad_level(op, a, zmsl, xkm, ykm, dadz):
    """Horizontal derivative op ('ddx', 'ddy', 'gradh') at constant height of a
    (..., ny, nx) on terrain-following levels whose heights are zmsl (km above sea
    level, same shape): along the levels, less the levels' slope times ∂a/∂z (dadz,
    per m):  ∂a/∂x|z = ∂a/∂x|level − (∂z/∂x|level) ∂a/∂z.  Per m."""
    def one(o):
        return hgrad(o, a, xkm, ykm) - 1000.0 * hgrad(o, zmsl, xkm, ykm) * dadz
    if op == "gradh":
        return np.hypot(one("ddx"), one("ddy"))
    return one(op)


def once(fetch):
    """fetch(name), each name fetched once: a derived field asks for its inputs several
    times (θe: prs three times), and each ask of a plane not cached is a read."""
    got = {}

    def f(n):
        if n not in got:
            got[n] = fetch(n)
        return got[n]
    return f


SLAB_CELLS = 2_000_000  # values a slab of levels holds (by_slabs): 8 MB a temporary
SLAB_THREADS = 8  # most threads computing slabs at once
PLANE_COUNT = 40  # most planes a Fields keeps
PLANE_SHARE = 16  # ... within this share (1 / PLANE_SHARE) of the 3D cache's bytes
PLANE_BYTES = 64 * 1024**2  # ... and never under this many
TILE = 8  # columns a side of the boxes Fields.along computes a field with gradients in
PART_BYTES = 1024**3  # most a slab of levels reads at once (a column max of a field
#                       too large for the 3D cache), or an eighth of the cache if less


def slabs(shape):
    """[(k0, k1)] slabs of whole levels of a (nk, ...) volume, about SLAB_CELLS values
    each (at least one level)."""
    per = max(1, SLAB_CELLS // max(1, int(np.prod(shape[1:]))))
    return [(k, min(k + per, shape[0])) for k in range(0, shape[0], per)]


def by_slabs(shape, part, threads=1):
    """float32 (nk, ...) array of `shape`, part(k0, k1) -> its levels k0:k1 written
    slab after slab into the one array: the temporaries of the computation are a
    slab's size, not the volume's (θe: about ten of them), and the slabs are computed
    on up to `threads` threads (numpy releases the GIL on arrays this size)."""
    out = np.empty(shape, dtype=np.float32)
    todo = slabs(shape)
    err = np.geterr()  # (numpy's error state is each thread's own: the caller's here)

    def one(b):
        with np.errstate(**err):
            out[b[0]:b[1]] = part(*b)

    n = min(int(threads), SLAB_THREADS, len(todo))
    if n <= 1:
        for b in todo:
            one(b)
    else:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(n) as ex:
            list(ex.map(one, todo))
    return out


def _batch(d, n, got):
    """The native inputs of field d to read together when its function asks for n: n
    and the inputs listed after it in d.deps not read yet (those before it were not
    asked for: the parcel fields' thermodynamic inputs once the parcel is in the memo)."""
    deps = [m for m in d.deps if not split_deriv(m)[0]]
    if n not in deps:
        return [n]
    return [m for m in deps[deps.index(n):] if m not in got]


class Fields:
    def __init__(self, run):
        from .services import pdecomp
        pdecomp.register(run)  # decomposition fields, computable where no file has them
        self.run = run
        self.cat = cat = run.catalog  # (the data type's names: core.catalog)
        # (a run with no grid, a radar's: no dx, dy, and only the pointwise derived
        # fields, whose inputs may be any samples, e.g. a sweep's gates)
        grid = getattr(run, "grid", True)
        self.ctx = dict(dx=getattr(run, "dx", None), dy=getattr(run, "dy", None),
                        umove=run.umove, vmove=run.vmove,
                        kappa=getattr(cat, "kappa", KAPPA), f=getattr(run, "fcor", 0.0))
        self.defs = OrderedDict()
        for name, info in run.vars.items():
            label, units, scale, cmap, vr, div = cat.look(name, info.long_name, info.units)
            group = cat.group(name, info.ndim)
            if name in PDECOMP and getattr(run, "var_times", {}).get(name) == frozenset():
                label += " (computed on request)"  # (no file holds it: pdecomp.register)
            self.defs[name] = FieldDef(name, label, units, group, ndim=info.ndim,
                                       scale=scale, cmap=cmap, vrange=vr, diverging=div,
                                       tier=cat.tier(name, group, run.vars))
        for d in _make_fields(run.vars, cat):
            if d.storm and not getattr(run, "storm_relative", True):
                continue  # (no storm motion for this run: see Run.storm_relative)
            if not grid and (not d.pointwise or d.column):
                continue  # (needs a grid: derivatives, columns)
            if d.name in self.defs and d.name in cat.file_first:
                continue  # (the files hold it: theirs is listed)
            self.defs[d.name] = d
        # main fields first, then Other, then hidden: a "first field" fallback
        # (next(iter(F.defs))) is never one the lists leave out
        order = {"main": 0, "other": 1, "hidden": 2}
        self.defs = OrderedDict(sorted(self.defs.items(), key=lambda kv: order[kv[1].tier]))
        self._planes = OrderedDict()
        self._plane_bytes = 0
        self._lock = threading.Lock()
        self._derivs = {}  # (derivative name -> its FieldDef, built when first asked)
        self._memo = OrderedDict()  # (t, stride) -> costly column fields' shared results

    # ---- catalog helpers
    def __getitem__(self, name):
        d = self.defs.get(name) if isinstance(name, str) else None
        if d is None:
            d = self._deriv(name)
            if d is None:
                raise KeyError(name)
        return d

    def __contains__(self, name):
        return (isinstance(name, str) and name in self.defs) or self._deriv(name) is not None

    def _deriv(self, name):
        """FieldDef of a derivative's name (split_deriv), or None."""
        op, base = split_deriv(name)
        if not op or base not in self.defs:
            return None
        d = self._derivs.get(name)
        if d is None:
            d = deriv_def(op, self.defs[base])
            if d is not None:
                self._derivs[name] = d
        return d

    def groups(self, ndim=None):
        """{group: {label: name}} for grouped Select widgets (group_options)."""
        return group_options(self.defs.values(), ndim)

    def role(self, r):
        """The field playing role r (core.catalog.ROLES) if this run has it, else None."""
        n = self.cat.name(r)
        return n if n is not None and n in self else None

    def native_deps(self, name):
        d = self[name]
        return list(d.natives) if d.derived else [name]

    # ---- data access
    def _ctx(self, d, storm):
        """Context for a derived field; storm defaults to the domain motion."""
        if not d.storm:
            return self.ctx
        return dict(self.ctx, storm=tuple(storm) if storm is not None
                    else (self.ctx["umove"], self.ctx["vmove"]))

    def plane(self, name, t, mode="height", value=1.0, storm=None):
        """2D (nj, ni) array of a field.
        mode: 'height' (km AGL), 'msl' (km above sea level: a terrain run's; the same
        as 'height' on a flat run), 'level' (model level index), 'colmax', 'colmin';
        on a radar run 'sweep' (value: the sweep's index): (rays, gates), not (nj, ni).
        storm: ground-relative storm motion (m/s) for storm-relative fields."""
        d = self[name]
        if d.ndim == 2:
            mode, value = "2d", 0
        ctx = self._ctx(d, storm)
        key = (name, t, mode, round(float(value), 4),
               tuple(round(float(x), 3) for x in ctx["storm"]) if d.storm else None,
               column_stride(self.run) if d.costly else None)
        with self._lock:
            a = self._planes.get(key)
            if a is not None:
                self._planes.move_to_end(key)
                return a
        op, base = split_deriv(name)
        if mode in ("colmax", "colmin"):
            a = self._extreme(name, t, mode[3:], storm)
        elif op:
            a = self._deriv_plane(op, base, t, mode, value, storm)
        elif d.column:
            a = self._column(d, t, ctx)
        else:
            got = {}  # (a derived field's native inputs, read together when first asked)

            def fetch(n):
                if split_deriv(n)[0]:  # (a derivative input, e.g. ∂w/∂z)
                    return self.plane(n, t, mode, value, storm)
                if n not in got:
                    got.update(self._native_planes(_batch(d, n, got), t, mode, value))
                return got[n]

            a = d.func(once(fetch), ctx) if d.derived else fetch(name) * d.scale
        # a copy: a slice of a cached volume would keep the whole volume alive
        a = np.array(a, dtype=np.float32)
        with self._lock:
            old = self._planes.pop(key, None)  # (another thread made it meanwhile)
            self._planes[key] = a
            self._plane_bytes += a.nbytes - (old.nbytes if old is not None else 0)
            limit = max(PLANE_BYTES, getattr(self.run, "cache_bytes", 0) // PLANE_SHARE)
            while len(self._planes) > 1 and (len(self._planes) > PLANE_COUNT
                                             or self._plane_bytes > limit):
                self._plane_bytes -= self._planes.popitem(last=False)[1].nbytes
        return a

    def read_bytes(self, name, mode=None):
        """About the bytes read for a plane of the field (plane's `mode`), or with mode
        None for its volume: what a loop over times sizes its read-ahead by
        (run.ahead_width)."""
        d, run = self[name], self.run
        per = 4 * run.nj * run.ni
        n3 = sum(run.vars[n].ndim == 3 for n in self.native_deps(name) if n in run.vars)
        if d.column:
            levels = len(d.levels(run.z, run.zf)[0])
            if d.costly:
                per //= column_stride(run) ** 2
        elif mode is None or mode in ("colmax", "colmin"):
            levels = run.nk
        else:
            levels = (2 if mode in ("height", "msl") else 1) \
                * (3 if split_deriv(name)[0] == "ddz" else 1)
        return max(per, per * n3 * levels)

    def clear_planes(self):
        """Drop every plane kept."""
        with self._lock:
            self._planes.clear()
            self._plane_bytes = 0

    def _native_planes(self, names, t, mode, value):
        """{name: (nj, ni)} of native fields on one surface (plane's mode, value; mode
        "2d": 2D fields, a 3D one's lowest level), their levels read together."""
        run = self.run
        if mode == "sweep":  # (a radar's: sweep `value` as it is, rays by gates)
            return {n: run.read_sweep(n, t, int(value)) for n in names}
        if mode in ("height", "msl"):
            return run.read_heights(names, t, float(value), "msl" if mode == "msl" else "agl")
        out = {n: run.read_level(n, t) for n in names if run.vars[n].ndim == 2}
        n3 = [n for n in names if n not in out]
        if n3:
            lv = run.read_levels(n3, t, [int(value) if mode == "level" else 0])
            out.update((n, lv[n][0]) for n in n3)
        return out

    def _column(self, d, t, ctx):
        """A column field: its inputs on the levels of its layer only (a costly one on
        every column_stride-th column, each block of columns showing its middle one)."""
        run = self.run
        if run.terrain:  # (each column's own levels: per-column thickness, heights)
            ks, dz, zk = column_levels_3d(run.heights(t), run.heights(t, w=True),
                                          *d.layer, edges=d.edges)
        else:
            ks, dz = d.levels(run.z, run.zf)
            zk = run.z[ks]
        c = dict(ctx, dz=dz, zk=zk, top=layer_top(d, run))
        got = {}  # (the inputs' levels, read together when the first is asked for)

        def layers(n, rows=None, cols=None):
            if run.vars[n].ndim == 2:  # (a 2D input, u10: as one level)
                a = run.read_level(n, t)
                return (a if rows is None else a[np.ix_(rows, cols)])[None]
            if n not in got:
                got.update(run.read_levels([m for m in _batch(d, n, got)
                                            if run.vars[m].ndim == 3], t, ks, rows, cols))
            return got[n]

        if not d.costly:
            return d.func(layers, c)
        s = column_stride(run)
        with self._lock:
            memo = self._memo.setdefault((t, s), {})
            self._memo.move_to_end((t, s))
            while len(self._memo) > 4:
                self._memo.popitem(last=False)
        c.update(memo=memo, threads=run.workers)
        if s == 1:
            return d.func(layers, c)
        r0, r1, tj, bj = stride_cols(0, run.nj, run.nj, s)
        c0, c1, ti, bi = stride_cols(0, run.ni, run.ni, s)
        if run.terrain:  # (the heights of the columns computed)
            c.update(dz=dz[:, r0:r1, c0:c1][:, tj][:, :, ti],
                     zk=zk[:, r0:r1, c0:c1][:, tj][:, :, ti])
        a = d.func(lambda n: layers(n, r0 + tj, c0 + ti), c)  # (only those columns)
        return np.asarray(a)[np.ix_(bj, bi)]

    def _deriv_plane(self, op, base, t, mode, value, storm):
        """2D derivative op of field base: horizontal ones of its plane; ∂/∂z on a
        model level from the levels next to it (as np.gradient does on the volume, so
        maps and cross-sections agree), at a height between the two levels' values."""
        if op != "ddz":
            if self.defs[base].ndim == 2:
                mode, value = "2d", 0
            elif self.run.terrain:  # (at constant height: hgrad_level, then to the plane)
                def level(k):
                    return self._hgrad_level(op, base, t, k, storm)
                if mode == "level":
                    return level(int(value))
                return self.run.interp_height(level, t, float(value),
                                              "msl" if mode == "msl" else "agl")
            return hgrad(op, self.plane(base, t, mode, value, storm), self.run.xh,
                         self.run.yh)
        if mode == "level":
            return self._ddz_level(base, t, int(value), storm)
        return self.run.interp_height(lambda k: self._ddz_level(base, t, k, storm), t,
                                      float(value), "msl" if mode == "msl" else "agl")

    def _hgrad_level(self, op, base, t, k, storm):
        """Horizontal derivative op (per m) of field base at constant height, on model
        level k of a terrain run (hgrad_level)."""
        run = self.run
        return hgrad_level(op, self.plane(base, t, "level", k, storm),
                           run.heights(t, "msl")[k], run.xh, run.yh,
                           self._ddz_level(base, t, k, storm))

    def _ddz_level(self, base, t, k, storm):
        """∂/∂z (per m) of field base on model level k (ddz_level)."""
        z = self.run.heights(t) if self.run.terrain else self.run.z  # (each column's)
        return ddz_level(lambda kk: self.plane(base, t, "level", kk, storm), z, k)

    def forget(self, t, names):
        """Drop cached planes at time t of `names` and the fields derived from them
        (after those were recomputed)."""
        names = set(names)
        dep = {n for n, d in self.defs.items() if n in names or names & set(d.natives)}
        dep |= {n for n in list(self._derivs) if split_deriv(n)[1] in dep}
        with self._lock:
            for k in [k for k in self._planes if k[1] == t and k[0] in dep]:
                self._plane_bytes -= self._planes.pop(k).nbytes
            if any(self.defs[n].costly for n in dep if n in self.defs):
                for k in [k for k in self._memo if k[0] == t]:
                    del self._memo[k]
        self.run.forget(dep, t)

    def volume(self, name, t, storm=None):
        """(nk, nj, ni) of a field in its display units (a column field: its plane).
        A derived one or a derivative is computed once and kept in the 3D cache; a
        native with a scale (qv: g/kg) is a scaled copy each call, not kept: where
        only part of it is wanted, use take() or raw()."""
        d = self[name]
        if d.column:  # (2D: its plane)
            return self.plane(name, t, storm=storm)
        if not d.derived:
            vol = self.run.volume(name, t)
            return vol if d.scale == 1.0 else vol * np.float32(d.scale)
        # derived volumes are cached ('~name', '~ddz.w'; '~name@u,v' if storm-relative)
        ctx = self._ctx(d, storm)
        key = f"~{name}" + ("@{:.3f},{:.3f}".format(*ctx["storm"]) if d.storm else "")
        vol = self.run.cached(key, t)
        if vol is None:
            op, base = split_deriv(name)
            vol = (self._deriv_volume(op, base, t, storm) if op
                   else self._derived_volume(d, t, storm, ctx))
            self.run._insert(key, t, vol)
        return vol

    def _threads(self):
        return max(1, int(getattr(self.run, "workers", 1) or 1))

    def _derived_volume(self, d, t, storm, ctx):
        """A derived field's volume, computed in slabs of levels (by_slabs): its
        function works on whole levels (plane() gives it single ones)."""
        self.run.load_volumes(d.natives, t)
        ins = {n: self._input(n, t, storm) for n in d.deps}  # (held: not evicted)
        shape = np.broadcast_shapes(*(v.shape for v in ins.values()))
        if len(shape) != 3:
            return np.asarray(d.func(ins.__getitem__, ctx), dtype=np.float32)
        def levels(n, k0, k1):  # (an input with no levels: as it is)
            v = ins[n]
            return v[k0:k1] if np.ndim(v) == 3 and v.shape[0] == shape[0] else v

        return by_slabs(shape, lambda k0, k1: d.func(
            once(lambda n: levels(n, k0, k1)), ctx), self._threads())

    def _deriv_volume(self, op, base, t, storm):
        """Derivative op of field base as a volume, in slabs of levels: ∂/∂z of a slab
        from the slab and the level below and above it (np.gradient's own values)."""
        b, scale = self.raw(base, t, storm)
        run = self.run
        z = np.asarray(run.heights(t) if run.terrain else run.z)
        nk = b.shape[0]

        def levels(k0, k1):  # (in display units: a slab's copy, not the volume's)
            return b[k0:k1] if scale == 1.0 else b[k0:k1] * scale

        zmsl = np.asarray(run.heights(t, "msl")) if run.terrain and op != "ddz" else None

        def dz(k0, k1):  # (∂/∂z of levels k0:k1, from them and the level beyond each end)
            lo, hi = max(k0 - 1, 0), min(k1 + 1, nk)
            if hi - lo < 2:  # (a single level: no ∂/∂z)
                return np.zeros((k1 - k0,) + b.shape[1:], np.float32)
            return ddz_volume(levels(lo, hi), z[lo:hi])[k0 - lo:k1 - lo]

        def part(k0, k1):
            if op == "ddz":
                return dz(k0, k1)
            if zmsl is not None:  # (terrain: at constant height)
                return hgrad_level(op, levels(k0, k1), zmsl[k0:k1], run.xh, run.yh,
                                   dz(k0, k1))
            return hgrad(op, levels(k0, k1), run.xh, run.yh)

        return by_slabs(b.shape, part, self._threads())

    def raw(self, name, t, storm=None):
        """(volume, scale) of a field: volume * scale is the field in its display
        units.  A native with a scale comes as it was read with its factor (no scaled
        copy of the whole volume); any other field as volume() gives it, scale 1."""
        d = self[name]
        if d.derived or d.column or d.scale == 1.0:
            return self.volume(name, t, storm), np.float32(1.0)
        return self.run.volume(name, t), np.float32(d.scale)

    def take(self, name, t, fn, storm=None):
        """fn(volume) of a field in its display units, for an fn that takes part of
        the volume as it is (a slice, samples, an interpolation, a max or min): the
        part is taken first and then scaled (raw())."""
        vol, scale = self.raw(name, t, storm)
        a = fn(vol)
        return a if scale == 1.0 else a * scale

    def _input(self, n, t, storm):
        """Volume of a derived field's input n: raw native, or a derivative."""
        return self.volume(n, t, storm) if split_deriv(n)[0] else self.run.volume(n, t)

    # ---- parts of a field without its volume: a request too large for the 3D cache
    def fits(self, names, t=None):
        """Whether the volumes behind 3D fields `names` together belong in the 3D
        cache (Run.fits): their native inputs, and each derived field's or
        derivative's own volume.  If not, read parts: crop() / box(), along(),
        at_levels(), and plane()'s column max and min do."""
        run = self.run
        if not hasattr(run, "fits"):
            return True
        natives, more = set(), 0
        for name in dict.fromkeys(names):
            op, base = split_deriv(name)
            d = self[base]
            if d.ndim != 3:
                continue
            natives.update(n for n in (d.natives if d.derived else (base,))
                           if n in run.vars and run.vars[n].ndim == 3)
            more += bool(op) + bool(d.derived)
        if not natives and not more:  # (2D fields only: no volume to fit)
            return True
        return run.fits(run.field_bytes * (len(natives) + more))

    def _halo(self, name):
        """Grid points beyond a part of the grid that 3D field `name` there depends
        on: one for a derivative, one more for a field with gradients of its own."""
        op, base = split_deriv(name)
        d = self[base]
        if d.ndim != 3:
            raise ValueError(f"{name} is not a 3D field")
        return bool(op) + bool(d.derived and not d.pointwise)

    def _region(self, name, t, reg, storm, got):
        """Field `name` in its display units on a part of the grid, from its native
        inputs there: got = {native: raw values}.  reg = (k0, k1, j0, j1, i0, i1), the
        box the values cover ((levels, ny, nx)); None: loose columns ((levels, n)), a
        field without gradients only.  Gradients are one-sided at the box's edges as at
        the grid's: box() and along() read a halo (_halo) and cut it off."""
        run = self.run
        op, base = split_deriv(name)
        if op:
            b = self._region(base, t, reg, storm, got)
            k0, k1, j0, j1, i0, i1 = reg
            if op != "ddz" and run.terrain and b.ndim == 3 and k1 - k0 >= 2:
                a = hgrad_level(op, b, run.heights(t, "msl")[k0:k1, j0:j1, i0:i1],
                                run.xh[i0:i1], run.yh[j0:j1],
                                ddz_volume(b, run.heights(t)[k0:k1, j0:j1, i0:i1]))
            elif op != "ddz":
                a = hgrad(op, b, run.xh[i0:i1], run.yh[j0:j1])
            elif k1 - k0 < 2:  # (a single level: no ∂/∂z)
                a = np.zeros_like(b)
            else:
                a = ddz_volume(b, run.heights(t)[k0:k1, j0:j1, i0:i1] if run.terrain
                               else np.asarray(run.z)[k0:k1])
            return np.asarray(a, dtype=np.float32)
        d = self.defs[name]
        if not d.derived:
            return got[name] if d.scale == 1.0 else got[name] * np.float32(d.scale)
        return np.asarray(d.func(once(
            lambda n: self._region(n, t, reg, storm, got) if split_deriv(n)[0] else got[n]),
            self._ctx(d, storm)), dtype=np.float32)

    def _read_part(self, name, t, ks, rows, cols, points=False):
        """{native: raw values} of field `name`'s native inputs on levels ks at rows
        and columns (Run.read_levels; a 2D input: its plane's part)."""
        run = self.run
        got = {}
        for n in self.native_deps(name):
            if run.vars[n].ndim == 2:
                a = run.read_level(n, t)
                got[n] = a[rows, cols] if points else a[np.ix_(rows, cols)]
                continue
            vol = run.cached(n, t)
            shape = vol.shape if vol is not None else run._vol_shape(n, t)
            if tuple(shape) != (run.nk, run.nj, run.ni):
                raise ValueError(f"{n} is not on the scalar grid")
        n3 = [n for n in self.native_deps(name) if n not in got]
        got.update(run.read_levels(n3, t, ks, rows, cols, points=points))
        return got

    def box(self, name, t, k0, k1, j0, j1, i0, i1, storm=None):
        """float32 (k1 - k0, j1 - j0, i1 - i0): 3D field `name` in its display units on
        levels k0:k1, rows j0:j1, columns i0:i1, the values its volume has there,
        computed from that box of its native inputs (and a halo for gradients): no
        whole volume is read and nothing enters the 3D cache."""
        run = self.run
        h = self._halo(name)
        K0, K1 = max(k0 - h, 0), min(k1 + h, run.nk)
        J0, J1 = max(j0 - h, 0), min(j1 + h, run.nj)
        I0, I1 = max(i0 - h, 0), min(i1 + h, run.ni)
        got = self._read_part(name, t, range(K0, K1), np.arange(J0, J1), np.arange(I0, I1))
        a = np.broadcast_to(self._region(name, t, (K0, K1, J0, J1, I0, I1), storm, got),
                            (K1 - K0, J1 - J0, I1 - I0))
        return np.ascontiguousarray(a[k0 - K0:k1 - K0, j0 - J0:j1 - J0, i0 - I0:i1 - I0],
                                    dtype=np.float32)

    def strided(self, name, t, k0, k1, j0, j1, i0, i1, step=1, storm=None):
        """float32: 3D field `name` in its display units on levels k0:k1, every step-th
        row of j0:j1 and column of i0:i1: its volume's [k0:k1, j0:j1:step, i0:i1:step]
        without the volume (a 3D scene thinned to its stride).  A field without
        gradients reads only those rows and columns; one with gradients is computed
        at full resolution in bands of rows (box()), each thinned as it comes."""
        if step <= 1:
            return self.box(name, t, k0, k1, j0, j1, i0, i1, storm)
        run = self.run
        rows, cols = np.arange(j0, j1, step), np.arange(i0, i1, step)
        shape = (k1 - k0, rows.size, cols.size)
        if not rows.size or not cols.size or k1 <= k0:
            return np.zeros(shape, dtype=np.float32)
        if self._halo(name) == 0:
            got = self._read_part(name, t, range(k0, k1), rows, cols)
            return np.ascontiguousarray(
                np.broadcast_to(self._region(name, t, None, storm, got), shape),
                dtype=np.float32)
        n3 = sum(run.vars[n].ndim == 3 for n in self.native_deps(name))
        per = min(PART_BYTES, run.cache_bytes // 8) \
            // (4 * (k1 - k0 + 2) * (i1 - i0 + 2) * max(1, n3))
        per = max(1, per // step) * step  # (rows a band; whole steps, so they line up)
        out = np.empty(shape, dtype=np.float32)
        for b0 in range(j0, j1, per):
            a = self.box(name, t, k0, k1, b0, min(b0 + per, j1), i0, i1, storm)
            r0 = (b0 - j0) // step
            out[:, r0:r0 + -(-a.shape[1] // step)] = a[:, ::step, ::step]
        return out

    def crop(self, name, t, k0, k1, j0, j1, i0, i1, storm=None):
        """3D field `name` in its display units on levels k0:k1, rows j0:j1, columns
        i0:i1: of its volume where that fits the 3D cache (fits), else box()."""
        if self.fits([name], t):
            return self.take(name, t, lambda v: v[k0:k1, j0:j1, i0:i1], storm)
        return self.box(name, t, k0, k1, j0, j1, i0, i1, storm)

    def along(self, name, t, fi, fj, storm=None, k0=0, k1=None):
        """float32 (k1 - k0, n): the columns of 3D field `name` (display units, levels
        k0:k1) at the n points with fractional grid indices (fj, fi), bilinear between
        the four columns around each (a point off the grid: the edge's), as sampling
        its volume gives, reading only the columns needed: a section or parcels of a
        field too large for the 3D cache (fits).  A field with gradients is computed
        in boxes of TILE columns a side around the points, their halo read too."""
        run = self.run
        ni, nj = run.ni, run.nj
        k1 = run.nk if k1 is None else k1
        fi = np.clip(np.asarray(fi, np.float64).ravel(), 0, ni - 1)
        fj = np.clip(np.asarray(fj, np.float64).ravel(), 0, nj - 1)
        out = np.empty((k1 - k0, fi.size), dtype=np.float32)
        if not out.size:
            return out
        ia = np.minimum(np.floor(fi).astype(np.intp), max(ni - 2, 0))
        ja = np.minimum(np.floor(fj).astype(np.intp), max(nj - 2, 0))
        ib, jb = np.minimum(ia + 1, ni - 1), np.minimum(ja + 1, nj - 1)
        wi, wj = fi - ia, fj - ja

        def mix(c, g=slice(None)):  # (c(j, i) -> the columns of the points g there)
            return (1 - wj[g]) * ((1 - wi[g]) * c(ja[g], ia[g]) + wi[g] * c(ja[g], ib[g])) \
                + wj[g] * ((1 - wi[g]) * c(jb[g], ia[g]) + wi[g] * c(jb[g], ib[g]))

        h = self._halo(name)
        K0, K1 = max(k0 - h, 0), min(k1 + h, run.nk)
        if h == 0:  # (no gradients: the field at the columns around the points)
            flat = np.unique(np.concatenate([ja * ni + ia, ja * ni + ib,
                                             jb * ni + ia, jb * ni + ib]))
            got = self._read_part(name, t, range(K0, K1), flat // ni, flat % ni, True)
            a = np.broadcast_to(self._region(name, t, None, storm, got),
                                (K1 - K0, flat.size))
            out[:] = mix(lambda j, i: a[:, np.searchsorted(flat, j * ni + i)])
            return out
        # the points by tile: each tile's box (and halo) is computed as a small volume
        tile = (ja // TILE) * (ni // TILE + 1) + ia // TILE
        order = np.argsort(tile, kind="stable")
        cuts = np.flatnonzero(np.diff(tile[order])) + 1
        groups = np.split(order, cuts)
        boxes = []
        for g in groups:
            tj, ti = (ja[g[0]] // TILE) * TILE, (ia[g[0]] // TILE) * TILE
            boxes.append((max(tj - h, 0), min(tj + TILE + 1 + h, nj),
                          max(ti - h, 0), min(ti + TILE + 1 + h, ni)))
        cells = [(np.arange(J0, J1)[:, None] * ni + np.arange(I0, I1)).ravel()
                 for J0, J1, I0, I1 in boxes]
        flat = np.unique(np.concatenate(cells))
        got = self._read_part(name, t, range(K0, K1), flat // ni, flat % ni, True)
        for g, (J0, J1, I0, I1), cell in zip(groups, boxes, cells):
            at = np.searchsorted(flat, cell)
            shape = (J1 - J0, I1 - I0)
            part = {n: a[..., at].reshape(a.shape[:-1] + shape) for n, a in got.items()}
            a = np.broadcast_to(self._region(name, t, (K0, K1, J0, J1, I0, I1), storm, part),
                                (K1 - K0,) + shape)[k0 - K0:k1 - K0]
            out[:, g] = mix(lambda j, i: a[:, j - J0, i - I0], g)
        return out

    def at_levels(self, name, t, fi, fj, fk, storm=None):
        """float32 (n,): 3D field `name` at n points with fractional grid indices (fk,
        fj, fi), trilinear as sampling its volume gives, reading only the columns
        around them on the levels they span (along)."""
        run = self.run
        fk = np.clip(np.asarray(fk, np.float64).ravel(), 0, run.nk - 1)
        if not fk.size:
            return np.zeros(0, dtype=np.float32)
        ka = min(int(np.floor(fk.min())), max(run.nk - 2, 0))
        kb = min(int(np.floor(fk.max())) + 2, run.nk)
        cols = self.along(name, t, fi, fj, storm, ka, kb)
        k = np.clip(np.floor(fk).astype(np.intp), ka, max(kb - 2, ka))
        w, n = fk - k, np.arange(fk.size)
        return ((1 - w) * cols[k - ka, n]
                + w * cols[np.minimum(k + 1, kb - 1) - ka, n]).astype(np.float32)

    def _extreme(self, name, t, op, storm):
        """(nj, ni): the max or min (op) over the levels of a 3D field: of its volume
        where that fits the 3D cache; else a native field's is reduced in the reader
        processes (Run.reduce_levels) and any other's slab of levels by slab (box)."""
        f = np.maximum if op == "max" else np.minimum
        if self[name].ndim != 3 or self.fits([name], t):
            return self.take(name, t, lambda v: f.reduce(v, axis=0), storm)
        run, d = self.run, self[name]
        if not d.derived:
            a = run.reduce_levels(name, t, op)
            return a if d.scale == 1.0 else a * np.float32(d.scale)
        n3 = sum(run.vars[n].ndim == 3 for n in self.native_deps(name))
        per = max(1, min(PART_BYTES, run.cache_bytes // 8)
                  // (4 * run.nj * run.ni * max(1, n3)))
        out = None
        for k in range(0, run.nk, per):
            a = f.reduce(self.box(name, t, k, min(k + per, run.nk), 0, run.nj, 0, run.ni,
                                  storm), axis=0)
            out = a if out is None else f(out, a)
        return out

    def at_points(self, name, t, sample, storm=None):
        """Field values at arbitrary points: sample(vol) -> values.  Pointwise derived
        fields are computed from sampled inputs, so no derived volume is built."""
        d = self[name]
        if d.derived and d.pointwise:
            self.run.load_volumes(d.natives, t)
            return np.asarray(d.func(once(lambda n: sample(self.run.volume(n, t))),
                                     self._ctx(d, storm)))
        if d.derived:
            return np.asarray(sample(self.volume(name, t, storm)))
        return np.asarray(sample(self.run.volume(name, t))) * d.scale

    def auto_range(self, name, a):
        d = self[name]
        if d.vrange is not None:
            return d.vrange
        sub = finite_sample(a)
        if sub.size == 0:
            return (0.0, 1.0)
        if d.diverging:
            m = float(np.percentile(np.abs(sub), 99.5)) or 1.0
            return (-m, m)
        lo, hi = np.percentile(sub, [0.5, 99.5])
        if hi <= lo:
            hi = lo + 1.0
        return (float(lo), float(hi))
