"""CM1's field catalog (core.catalog): its output's names and how they show."""

from atmo3d.core.catalog import Catalog, register

from .outputs import OUTPUTS, describe

# display defaults (label, units, scale, cmap, range, diverging, group): every field
# CM1 can write (atmo3d_cm1.outputs), and the pressure decomposition atmo3d computes
NATIVES = {
    **OUTPUTS,
    # pressure decomposition, CM1's method (from the files, or computed: atmo3d.pdecomp)
    "p_b": ("p′ buoyancy (p_b)", "Pa", 1, "PuOr_r", None, True),
    "p_l": ("p′ linear dynamic (p_l)", "Pa", 1, "PuOr_r", None, True),
    "p_nl": ("p′ nonlinear dynamic (p_nl)", "Pa", 1, "PuOr_r", None, True),
    "p_c": ("p′ Coriolis (p_c)", "Pa", 1, "PuOr_r", None, True),
    "acc_b": ("Buoyancy acceleration (B − cp θv0 ∂π_b/∂z)", "m/s²", 1, "RdBu_r", None, True),
    "acc_l": ("Linear dynamic VPPGA (−cp θv0 ∂π_l/∂z)", "m/s²", 1, "RdBu_r", None, True),
    "acc_nl": ("Nonlinear dynamic VPPGA (−cp θv0 ∂π_nl/∂z)", "m/s²", 1, "RdBu_r", None,
               True),
    "acc_c": ("Coriolis VPPGA (−cp θv0 ∂π_c/∂z)", "m/s²", 1, "RdBu_r", None, True),
}

ROLES = {
    "u": "uinterp", "v": "vinterp", "w": "winterp",
    "xvort": "xvort", "yvort": "yvort", "zvort": "zvort",
    "theta": "th", "pres": "prs", "qv": "qv",
    "theta0": "th0", "pres0": "prs0", "qv0": "qv0", "u0": "u0", "v0": "v0",
    "qc": "qc", "qi": "qi", "qr": "qr", "qs": "qs", "qg": "qg", "qhl": "qhl",
    "refl": "dbz", "cref": "cref",
    "u10": "u10", "v10": "v10", "uh25": "uh",
}

_SWATHS = ("sws", "svs", "sps", "srs", "sgs", "sus", "shs")

# under "Other" (Phase 2b field audit, 2026-11-18): rarely wanted fields
OTHER = ("pi", "cref", "rain", "rain2", *_SWATHS, *(s + "2" for s in _SWATHS))
OTHER_GROUPS = ("Turbulence", "Budgets")  # (tke, kmh, kmv, khh, khv...; ub_hadv, ...)

CATALOG = register(Catalog(
    "cm1", NATIVES, ROLES, also={"u": ("u",), "v": ("v",), "w": ("w",)},
    turbulence=("tke", "kmh", "kmv", "khh", "khv"), describe=describe,
    # CM1 writes these (output_thpert, output_prspert) as atmo3d derives them
    file_first=("thpert", "prspert"),
    other=OTHER, other_groups=OTHER_GROUPS,
    # the staggered winds go under Other when the run has the interpolated ones
    other_if={"u": "uinterp", "v": "vinterp", "w": "winterp"},
    # the rest of what CM1's own buoyancy loads (pdcomp.F, solve2.F: every liquid and
    # ice species), beyond the hydrometeor roles
    condensate=("qh", "qi1", "qi2", "qi3")))
