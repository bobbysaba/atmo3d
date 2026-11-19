"""WoFS's field catalog (core.catalog): WRF's own names.

Two fields are sums the reader makes (core.wofs.SUMS), since WRF splits them:
THETA = T + 300 (potential temperature) and PRES = P + PB (pressure).  The base state
is each field at the member's first time: THETA0, PRES0, QVAPOR0, U0, V0 (core.wofs.BASE).
U, V, W are averaged onto the mass points on read."""

from .catalog import Catalog, register
from .wofs_outputs import OUTPUTS

# display defaults: every field of WoFS's files (core.wofs_outputs)
NATIVES = OUTPUTS

ROLES = {
    "u": "U", "v": "V", "w": "W",
    "theta": "THETA", "pres": "PRES", "qv": "QVAPOR",
    "theta0": "THETA0", "pres0": "PRES0", "qv0": "QVAPOR0", "u0": "U0", "v0": "V0",
    "qc": "QCLOUD", "qi": "QICE", "qr": "QRAIN", "qs": "QSNOW", "qg": "QGRAUP",
    "qhl": "QHAIL",
    "refl": "REFL_10CM", "cref": "COMPOSITE_REFL_10CM",
    # ζ: WRF's REL_VORT (the dataset's creator, 2026-11-19); ξ and η are derived from the
    # winds (core.fields)
    "zvort": "REL_VORT",
    "fcor": "F", "u10": "U10", "v10": "V10", "uh25": "UH",
}

# Phase 2b field audit (2026-11-18): under "Other" ...
OTHER = (
    # 3D
    "H_DIABATIC", "QV_DIABATIC", "QC_DIABATIC",
    "QNDROP", "QNRAIN", "QNICE", "QNSNOW", "QNGRAUPEL", "QNHAIL", "QNCCN",
    "QVGRAUPEL", "QVHAIL", "QNWFA", "QNIFA", "CLDFRA",
    "NONINDUC", "NONINDUCN", "NONINDUCP", "P_HYD", "PH", "PHB", "WW",
    # 2D storm diagnostics
    "REFL_10CM_1KM", "REFL_10CM_4KM", "REFD_MAX", "REFDM10C_MAX",
    "UP_HELI_MAX", "UP_HELI_MAX16", "UP_HELI_MAX02", "UP_HELI_MAX03",
    "UP_HELI_MIN", "UP_HELI_MIN16", "UP_HELI_MIN02", "UP_HELI_MIN03",
    "REL_VORT_MAX", "REL_VORT_MAX01", "W_UP_MAX", "W_DN_MAX", "W_MEAN",
    "WSPD10MAX", "WSPD80MAX", "GRPL_MAX",
    "HAIL_MAXK1", "HAIL_MAX2D", "HAILCAST_DIAM_MAX",
    "LTG1_MAX", "LTG2_MAX", "LTG3_MAX", "GLM_FED_AVG", "GLM_FED_MAX",
    # 2D near surface, precipitation, water paths, surface fluxes
    "T2", "TH2", "Q2", "PSFC", "U10", "V10", "WSPD10", "WSPD80",
    "RAINNC", "SNOWNC", "GRAUPELNC",
    "PREC_ACC_NC", "SNOW_ACC_NC", "GRAUP_ACC_NC",
    "PREC_ACC_NC1", "SNOW_ACC_NC1", "GRAUP_ACC_NC1",
    "LWP", "IWP", "MAXCLDFRA",
    "PBLH", "HFX", "LH", "QFX", "UST", "TSK", "SST", "OLR", "SWDOWN", "SR",
    "RSCGHIS_2D", "RSCGHIS_2DN", "RSCGHIS_2DP",
)

# ... and not listed unless the show_hidden_fields setting is on: static, dynamics,
# cumulus, land/snow/lake, radiation/aerosol, time-step and CI counters, the wind
# maxima's components
HIDDEN = (
    "XLAT", "XLONG", "CLAT", "LU_INDEX", "VAR_SSO", "VAR", "TOPOSTDV", "TOPOSLPX",
    "TOPOSLPY", "SHDMAX", "SHDMIN", "SNOALB", "SLOPECAT", "SOILHGT", "SOILCAT", "VEGCAT",
    "IVGTYP", "ISLTYP", "LANDMASK", "LAKEMASK", "XLAND", "LAKE_DEPTH", "LAKEDEPTH2D",
    "MAPFAC_M", "MAPFAC_MX", "MAPFAC_MY", "F", "E", "SINALPHA", "COSALPHA", "ALBBCK",
    "EMISS", "TMN", "NEST_POS",
    "MU", "MUB", "MU0", "PC", "PCB",
    "RAINC", "RAINCV", "PRATEC", "CUTOP", "CUBOT", "CUPPT", "PREC_ACC_C", "PREC_ACC_C1",
    "SEAICE", "SFROFF", "UDROFF", "VEGFRA", "GRDFLX", "ACSNOW", "ACGRAUP", "ACRUNOFF",
    "ACSNOM", "SNOW", "SNOWH", "CANWAT", "RHOSNF", "SNOWFALLAC", "LAI", "SNOWDP2D",
    "H2OSNO2D", "SNL2D", "T_GRND2D", "SAVEDTKE12D", "SOILT1", "SNOWC", "MAVAIL", "QVG",
    "QCG", "FLHC", "ZNT", "BR", "ZOL", "SST_INPUT",
    "COSZEN", "GSW", "GLW", "SWDDNI", "SWDDIF", "SWDDNIC", "SWDDIFC", "AOD5502D",
    "ANGEXP2D", "AERSSA2D", "AERASY2D", "TAOD5502D", "SWRADMEAN", "SWNORMMEAN", "ALBEDO",
    "ALBSOL", "ALBBCKSOL", "QNWFA2D", "QNN2D", "QNN2D_BASE",
    "RAINNCV", "SNOWNCV", "GRAUPELNCV", "NCI_LTG", "NCA_LTG", "NCI_W", "NCA_W", "NCI_WQ",
    "NCA_WQ", "NCI_REFD", "NCA_REFD", "QR_MAX_CI", "QG_MAX_CI",
    "WSPD10UMAX", "WSPD10VMAX", "WSPD80UMAX", "WSPD80VMAX",
)

# what sessions and figures saved before atmo3d's catalogs called WoFS's fields (the
# reader renamed them to CM1's): core.catalog.rename_fields maps them on load
OLD_NAMES = {
    "th": "THETA", "prs": "PRES", "qv": "QVAPOR", "qc": "QCLOUD", "qr": "QRAIN",
    "qi": "QICE", "qs": "QSNOW", "qg": "QGRAUP", "qhl": "QHAIL", "dbz": "REFL_10CM",
    "uinterp": "U", "vinterp": "V", "winterp": "W",
    "th0": "THETA0", "prs0": "PRES0", "qv0": "QVAPOR0", "u0": "U0", "v0": "V0",
}

CATALOG = register(Catalog("wofs", NATIVES, ROLES, renamed=OLD_NAMES, other=OTHER,
                           hidden=HIDDEN, unknown_hidden=True,
                           kappa=2.0 / 7.0))  # (WRF: Rd = 287, cp = 7 Rd / 2)
