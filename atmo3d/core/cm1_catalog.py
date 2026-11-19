"""CM1's field catalog (core.catalog): its output's names and how they show."""

from .catalog import Catalog, register

# display defaults: label, units, scale, cmap, range, diverging
NATIVES = {
    "cref": ("Composite reflectivity", "dBZ", 1, "reflectivity", (0, 75), False),
    "dbz": ("Reflectivity", "dBZ", 1, "reflectivity", (0, 75), False),
    "uinterp": ("u (grid-relative)", "m/s", 1, "RdBu_r", (-30, 30), True),
    "vinterp": ("v (grid-relative)", "m/s", 1, "RdBu_r", (-30, 30), True),
    "winterp": ("Vertical velocity", "m/s", 1, "RdBu_r", (-20, 20), True),
    "u": ("u (grid-relative, staggered)", "m/s", 1, "RdBu_r", (-30, 30), True),
    "v": ("v (grid-relative, staggered)", "m/s", 1, "RdBu_r", (-30, 30), True),
    "w": ("w (staggered)", "m/s", 1, "RdBu_r", (-20, 20), True),
    "zvort": ("Vertical vorticity", "1/s", 1, "RdBu_r", (-0.05, 0.05), True),
    "xvort": ("x vorticity", "1/s", 1, "RdBu_r", (-0.05, 0.05), True),
    "yvort": ("y vorticity", "1/s", 1, "RdBu_r", (-0.05, 0.05), True),
    "th": ("Potential temperature", "K", 1, "cmo.thermal", None, False),
    "prs": ("Pressure", "hPa", 0.01, "viridis", None, False),
    "pi": ("Exner function", "", 1, "viridis", None, False),
    "rho": ("Density", "kg/m³", 1, "viridis", None, False),
    "qv": ("Water vapor mixing ratio", "g/kg", 1000, "YlGnBu", (0, 20), False),
    "qc": ("Cloud water", "g/kg", 1000, "cmo.ice", (0, 3), False),
    "qr": ("Rain", "g/kg", 1000, "cmo.rain", (0, 5), False),
    "qi": ("Cloud ice", "g/kg", 1000, "cmo.ice", (0, 2), False),
    "qs": ("Snow", "g/kg", 1000, "cmo.ice", (0, 3), False),
    "qg": ("Graupel", "g/kg", 1000, "cmo.amp", (0, 5), False),
    "qhl": ("Hail", "g/kg", 1000, "cmo.amp", (0, 5), False),
    "tke": ("Subgrid TKE", "m²/s²", 1, "magma", (0, 20), False),
    "rain": ("Accumulated rain", "cm", 1, "cmo.rain", (0, 5), False),
    "rain2": ("Accumulated rain (translated)", "cm", 1, "cmo.rain", (0, 5), False),
    "sws": ("Max sfc wind speed", "m/s", 1, "turbo", (0, 40), False),
    "sws2": ("Max sfc wind speed (translated)", "m/s", 1, "turbo", (0, 40), False),
    "svs": ("Max sfc vertical vorticity", "1/s", 1, "magma", (0, 0.1), False),
    "svs2": ("Max sfc vert. vorticity (translated)", "1/s", 1, "magma", (0, 0.1), False),
    "sps": ("Min sfc pressure", "hPa", 0.01, "viridis", None, False),
    "sps2": ("Min sfc pressure (translated)", "hPa", 0.01, "viridis", None, False),
    "srs": ("Max sfc rain mixing ratio", "g/kg", 1000, "cmo.rain", (0, 5), False),
    "srs2": ("Max sfc qr (translated)", "g/kg", 1000, "cmo.rain", (0, 5), False),
    "sgs": ("Max sfc graupel mixing ratio", "g/kg", 1000, "cmo.amp", (0, 5), False),
    "sgs2": ("Max sfc qg (translated)", "g/kg", 1000, "cmo.amp", (0, 5), False),
    "sus": ("Max w at 5 km", "m/s", 1, "turbo", (0, 60), False),
    "sus2": ("Max w at 5 km (translated)", "m/s", 1, "turbo", (0, 60), False),
    "shs": ("Max updraft helicity", "m²/s²", 1, "magma", (0, 500), False),
    "shs2": ("Max updraft helicity (translated)", "m²/s²", 1, "magma", (0, 500), False),
    # pressure decomposition (from the files, or computed with the pdecomp_script)
    "p_b": ("p′ buoyant (p_b)", "Pa", 1, "PuOr_r", None, True),
    "p_l": ("p′ linear dynamic (p_l)", "Pa", 1, "PuOr_r", None, True),
    "p_nl": ("p′ nonlinear dynamic (p_nl, residual)", "Pa", 1, "PuOr_r", None, True),
    "acc_b": ("Buoyant acceleration (B − ∂p_b/∂z / ρ)", "m/s²", 1, "RdBu_r", None, True),
    "acc_l": ("Linear dynamic VPPGA (−∂p_l/∂z / ρ)", "m/s²", 1, "RdBu_r", None, True),
    "acc_nl": ("Nonlinear dynamic VPPGA (−∂p_nl/∂z / ρ)", "m/s²", 1, "RdBu_r", None,
               True),
}

ROLES = {
    "u": "uinterp", "v": "vinterp", "w": "winterp",
    "xvort": "xvort", "yvort": "yvort", "zvort": "zvort",
    "theta": "th", "pres": "prs", "qv": "qv",
    "theta0": "th0", "pres0": "prs0", "qv0": "qv0", "u0": "u0", "v0": "v0",
    "qc": "qc", "qi": "qi", "qr": "qr", "qs": "qs", "qg": "qg", "qhl": "qhl",
    "refl": "dbz", "cref": "cref",
}

CATALOG = register(Catalog(
    "cm1", NATIVES, ROLES, also={"u": ("u",), "v": ("v",), "w": ("w",)},
    turbulence=("tke", "kmh", "kmv", "khh", "khv"),
    extra_groups={"pi0": "Base state", "rho0": "Base state", "pi": "Thermodynamics",
                  "rho": "Thermodynamics"}))
