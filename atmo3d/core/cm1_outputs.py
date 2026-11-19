"""Every field CM1 can write to its output files, and how each one shows.

What a run's files hold depends on its namelist (output_* switches, the microphysics,
PBL and surface schemes...), so this lists all of them; a run lists only the ones its
files have.  Taken from CM1 r19.5 and r21.1 (src/writeout.F for the fields, src/param.F
for the microphysics variables, qname): the switch that writes each is noted.

OUTPUTS = {name: (label, units, scale, cmap, range, diverging, group)}: units are the
display units (the file's times scale).  group is the field-list group of a 3D field
(a 2D one is always "Swaths & 2D").

Fields a namelist names by number (out2d1.., out3d1.., the passive tracers pt1..) are
described by describe() below."""

import re

DIV = "RdBu_r"
TH, KIN, MP, MPN, RAD = "Thermodynamics", "Kinematics", "Microphysics", \
    "Microphysics (number & moments)", "Radiation"
TURB, PBL, BUD, BASE = "Turbulence", "Boundary layer", "Budgets", "Base state"
PDEC, TAVG, HGT, CU = "Pressure decomposition", "Time averages", "Heights", "Cumulus"
SFC = "Swaths & 2D"


def _f(label, units="", scale=1, cmap="viridis", vr=None, div=False, group=SFC):
    return (label, units, scale, cmap, vr, div, group)


def _signed(label, units="", scale=1, vr=None, group=SFC, cmap=DIV):
    return _f(label, units, scale, cmap, vr, True, group)


OUTPUTS = {
    # ---- 2D: swaths (output_rain, output_sws, ..., output_shs; "2": translated with
    # the domain, when the run moves it)
    "rain": _f("Accumulated rain", "cm", 1, "cmo.rain", (0, 5)),
    "rain2": _f("Accumulated rain (translated)", "cm", 1, "cmo.rain", (0, 5)),
    "raincv": _f("Accumulated rain (convective scheme)", "cm", 1, "cmo.rain", (0, 5)),
    "prate": _f("Surface precipitation rate", "mm/h", 3600, "cmo.rain", (0, 100)),
    "sws": _f("Max sfc wind speed", "m/s", 1, "turbo", (0, 40)),
    "sws2": _f("Max sfc wind speed (translated)", "m/s", 1, "turbo", (0, 40)),
    "svs": _f("Max sfc vertical vorticity", "1/s", 1, "magma", (0, 0.1)),
    "svs2": _f("Max sfc vert. vorticity (translated)", "1/s", 1, "magma", (0, 0.1)),
    "sps": _f("Min sfc pressure", "hPa", 0.01),
    "sps2": _f("Min sfc pressure (translated)", "hPa", 0.01),
    "srs": _f("Max sfc rain mixing ratio", "g/kg", 1000, "cmo.rain", (0, 5)),
    "srs2": _f("Max sfc qr (translated)", "g/kg", 1000, "cmo.rain", (0, 5)),
    "sgs": _f("Max sfc graupel mixing ratio", "g/kg", 1000, "cmo.amp", (0, 5)),
    "sgs2": _f("Max sfc qg (translated)", "g/kg", 1000, "cmo.amp", (0, 5)),
    "sus": _f("Max w at 5 km", "m/s", 1, "turbo", (0, 60)),
    "sus2": _f("Max w at 5 km (translated)", "m/s", 1, "turbo", (0, 60)),
    "shs": _f("Max updraft helicity", "m²/s²", 1, "magma", (0, 500)),
    "shs2": _f("Max updraft helicity (translated)", "m²/s²", 1, "magma", (0, 500)),
    "uh": _f("Updraft helicity 2–5 km (CM1's)", "m²/s²", 1, "magma", (0, 300)),
    # output_coldpool
    "cpc": _f("Cold pool intensity C", "m/s", 1, "viridis", (0, 30)),
    "cph": _f("Cold pool depth", "m AGL", 1, "cividis", (0, 3000)),
    # output_sfcflx, output_sfcparams, output_psfc, output_zs, output_dbz
    "thflux": _signed("Surface θ flux", "K m/s"),
    "qvflux": _signed("Surface qv flux", "g/kg m/s", 1000),
    "tsk": _f("Skin (soil/ocean) temperature", "K", 1, "cmo.thermal"),
    "cd": _f("Surface exchange coefficient, momentum"),
    "ch": _f("Surface exchange coefficient, heat"),
    "cq": _f("Surface exchange coefficient, moisture"),
    "tlh": _f("Horizontal length scale (ipbl=2)", "m"),
    "f2d": _f("Coriolis parameter", "1/s"),
    "psfc": _f("Surface pressure", "hPa", 0.01),
    "psmth": _f("Smoothed surface pressure (vortex centre)", "hPa", 0.01),
    "zs": _f("Terrain height", "m", 1, "cividis"),
    "cref": _f("Composite reflectivity", "dBZ", 1, "reflectivity", (0, 75)),
    "cm0": _f("Smagorinsky coefficient C_m0 (LES)"),
    "xland": _f("Land/water flag (1 land, 2 water)"),
    "lu": _f("Land use category"),
    "mavail": _f("Surface moisture availability", "", 1, "YlGnBu", (0, 1)),
    "tmn": _f("Deep soil temperature", "K", 1, "cmo.thermal"),
    "hfx": _signed("Surface sensible heat flux", "W/m²"),
    "qfx": _signed("Surface moisture flux", "kg/m²/s"),
    "gsw": _f("Downward shortwave flux at surface", "W/m²", 1, "magma"),
    "glw": _f("Downward longwave flux at surface", "W/m²", 1, "magma"),
    **{f"tslb{i}": _f(f"Soil temperature, layer {i}", "K", 1, "cmo.thermal")
       for i in range(1, 6)},
    "tml": _f("Ocean mixed-layer temperature", "K", 1, "cmo.thermal"),
    "hml": _f("Ocean mixed-layer depth", "m", 1, "cmo.deep"),
    "huml": _signed("Ocean mixed-layer u", "m/s"),
    "hvml": _signed("Ocean mixed-layer v", "m/s"),
    "coszen": _f("Cosine of solar zenith angle", "", 1, "magma", (0, 1)),
    # radiation (output_sfcparams with radopt >= 1)
    "radsw": _f("Solar radiation at surface", "W/m²", 1, "magma"),
    "rnflx": _f("Net radiation absorbed by surface", "W/m²", 1, "magma"),
    "radswnet": _f("Net solar radiation", "W/m²", 1, "magma"),
    "radlwin": _f("Incoming longwave radiation", "W/m²", 1, "magma"),
    "olr": _f("Outgoing longwave radiation (TOA, net)", "W/m²", 1, "Greys_r"),
    "dsr": _f("Incoming solar radiation (TOA, net)", "W/m²", 1, "magma"),
    "lwupt": _f("LW flux up, top of atmosphere", "W/m²", 1, "magma"),
    "lwdnt": _f("LW flux down, top of atmosphere", "W/m²", 1, "magma"),
    "lwupb": _f("LW flux up, surface", "W/m²", 1, "magma"),
    "lwdnb": _f("LW flux down, surface", "W/m²", 1, "magma"),
    "swupt": _f("SW flux up, top of atmosphere", "W/m²", 1, "magma"),
    "swdnt": _f("SW flux down, top of atmosphere", "W/m²", 1, "magma"),
    "swupb": _f("SW flux up, surface", "W/m²", 1, "magma"),
    "swdnb": _f("SW flux down, surface", "W/m²", 1, "magma"),
    "lwcf": _signed("Longwave cloud forcing (TOA)", "W/m²"),
    "swcf": _signed("Shortwave cloud forcing (TOA)", "W/m²"),
    # output_sfcdiags
    "u10": _signed("10 m u (grid-relative)", "m/s", 1, (-30, 30)),
    "v10": _signed("10 m v (grid-relative)", "m/s", 1, (-30, 30)),
    "s10": _f("10 m wind speed", "m/s", 1, "turbo", (0, 40)),
    "u10e": _signed("10 m u (ensemble/LES)", "m/s", 1, (-30, 30)),
    "v10e": _signed("10 m v (ensemble/LES)", "m/s", 1, (-30, 30)),
    "t2": _f("2 m temperature", "K", 1, "cmo.thermal"),
    "q2": _f("2 m water vapor mixing ratio", "g/kg", 1000, "YlGnBu", (0, 20)),
    "znt": _f("Roughness length", "m"),
    "mznt": _f("Momentum roughness length", "m"),
    "znttavg": _f("Time-average roughness length", "m"),
    "z0t": _f("Roughness length, temperature", "m"),
    "z0q": _f("Roughness length, moisture", "m"),
    "z0base": _f("Background roughness length", "m"),
    "ust": _f("Friction velocity u*", "m/s", 1, "magma"),
    "usttavg": _f("Time-average friction velocity", "m/s", 1, "magma"),
    "ustt": _f("Friction velocity at model top", "m/s", 1, "magma"),
    "stau": _f("Surface stress", "m²/s²", 1, "magma"),
    "taux": _signed("Surface stress, x", "kg/m/s²"),
    "tauy": _signed("Surface stress, y", "kg/m/s²"),
    "tst": _signed("θ* (similarity theory)", "K"),
    "qst": _signed("q* (similarity theory)", "g/kg", 1000),
    "hpbl": _f("PBL height (bulk Richardson)", "m", 1, "cividis"),
    "zi": _f("Boundary-layer depth (max gradient)", "m", 1, "cividis"),
    "zol": _signed("z/L (stability)"),
    "mol": _signed("Monin–Obukhov length L", "m"),
    "moltavg": _signed("Time-average Monin–Obukhov length", "m"),
    "br": _signed("Bulk Richardson number (surface layer)"),
    "brcr": _f("Critical bulk Richardson number (PBL)"),
    "psim": _f("Stability function ψm (lowest level)"),
    "psih": _f("Stability function ψh (lowest level)"),
    "psiq": _f("Stability function ψq (lowest level)"),
    "fm": _f("ln(z/z0) − ψm"),
    "fh": _f("ln(z/z0t) − ψh"),
    "qsfc": _f("Surface water vapor mixing ratio", "g/kg", 1000, "YlGnBu", (0, 20)),
    "wspd": _f("Surface-layer wind speed (with gust)", "m/s", 1, "turbo", (0, 40)),
    "wstar": _f("Convective velocity w*", "m/s", 1, "magma"),
    "delta": _f("Entrainment-zone thickness (PBL)", "m"),
    "prkpp": _f("Prandtl number (KPP PBL)"),
    "wscale": _f("w scale (GFS-EDMF)", "m/s"),
    "wscaleu": _f("u scale (GFS-EDMF)", "m/s"),
    "thz0": _f("θ at roughness height", "K", 1, "cmo.thermal"),
    "qz0": _f("qv at roughness height", "g/kg", 1000, "YlGnBu"),
    "uz0": _signed("u at roughness height", "m/s"),
    "vz0": _signed("v at roughness height", "m/s"),
    "kbdy": _f("Boundary index (recycling)"),
    "recy_cap": _f("Recycling: cap"),
    "recy_inj": _f("Recycling: injection"),
    "zinfl": _f("Inflow-layer depth (u < −2 m/s)", "m", 1, "cividis"),
    # output_lwp, output_pwat, output_cape/cin/lcl/lfc
    "cwp": _f("Cloud water path", "g/m²", 1000, "cmo.ice"),
    "lwp": _f("Liquid water path", "g/m²", 1000, "cmo.ice"),
    "pwat": _f("Precipitable water", "mm", 1000, "YlGnBu", (0, 60)),
    # (CM1 lifts a 500 m mixed-layer parcel, pseudoadiabatic, liquid only: getcape
    # source 3, ml_depth 500 m, adiabat 1, in r19.5 and r21.1)
    "cape": _f("MLCAPE (CM1's, 500 m mixed layer)", "J/kg", 1, "magma", (0, 4000)),
    "cin": _f("MLCIN (CM1's, 500 m mixed layer)", "J/kg", 1, "cmo.ice", (-300, 0)),
    "lcl": _f("MLLCL height (CM1's, 500 m mixed layer)", "m", 1, "cividis", (0, 3000)),
    "lfc": _f("MLLFC height (CM1's, 500 m mixed layer)", "m", 1, "cividis", (0, 4000)),
    "wa500": _signed("w at 500 hPa", "m/s", 1, (-20, 20)),

    # ---- 3D: thermodynamics (output_th, output_thpert, output_prs, ...)
    "zh": _f("Height of model levels", "km", 0.001, "cividis", group=HGT),
    "zhval": _f("Height of model levels", "km", 0.001, "cividis", group=HGT),
    "th": _f("Potential temperature", "K", 1, "cmo.thermal", group=TH),
    "thpert": _signed("θ′", "K", 1, (-6, 6), TH),
    "prs": _f("Pressure", "hPa", 0.01, group=TH),
    "prspert": _signed("p′", "hPa", 0.01, (-4, 4), TH, "PuOr_r"),
    "pi": _f("Exner function", group=TH),
    "pipert": _signed("Exner function perturbation", "", 1, None, TH, "PuOr_r"),
    "phi": _signed("Pressure variable (anelastic)", "m²/s²", 1, None, TH, "PuOr_r"),
    "rho": _f("Dry-air density", "kg/m³", group=TH),
    "rhopert": _signed("Dry-air density perturbation", "kg/m³", group=TH),
    "qv": _f("Water vapor mixing ratio", "g/kg", 1000, "YlGnBu", (0, 20), group=TH),
    "qvpert": _signed("qv′", "g/kg", 1000, (-5, 5), TH, "BrBG"),
    "buoyancy": _signed("Buoyancy (CM1's)", "m/s²", 1, (-0.3, 0.3), TH),
    "nm": _signed("Brunt–Väisälä frequency squared", "1/s²", group=TH),
    "dbz": _f("Reflectivity", "dBZ", 1, "reflectivity", (0, 75), group="Radar"),
    # kinematics (output_u/v/w, output_uinterp..., output_vort, output_pv)
    "uinterp": _signed("u (grid-relative)", "m/s", 1, (-30, 30), KIN),
    "vinterp": _signed("v (grid-relative)", "m/s", 1, (-30, 30), KIN),
    "winterp": _signed("Vertical velocity", "m/s", 1, (-20, 20), KIN),
    "u": _signed("u (grid-relative, staggered)", "m/s", 1, (-30, 30), KIN),
    "v": _signed("v (grid-relative, staggered)", "m/s", 1, (-30, 30), KIN),
    "w": _signed("w (staggered)", "m/s", 1, (-20, 20), KIN),
    "upert": _signed("u′ (staggered)", "m/s", 1, (-20, 20), KIN),
    "vpert": _signed("v′ (staggered)", "m/s", 1, (-20, 20), KIN),
    "xvort": _signed("x vorticity", "1/s", 1, (-0.05, 0.05), KIN),
    "yvort": _signed("y vorticity", "1/s", 1, (-0.05, 0.05), KIN),
    "zvort": _signed("Vertical vorticity", "1/s", 1, (-0.05, 0.05), KIN),
    "pv": _signed("Potential vorticity", "PVU", 1.0e6, (-10, 10), KIN),
    "vgrad": _f("Gradient wind speed", "m/s", 1, "turbo", group=KIN),
    "urad": _signed("Radial velocity (ground-relative)", "m/s", 1, (-30, 30), KIN),
    "vtan": _signed("Tangential velocity (ground-relative)", "m/s", 1, (-60, 60), KIN),
    "wspa": _f("Analytic wind speed", "m/s", 1, "turbo", group=KIN),
    # base state (output_basestate); the catalog gives each the look of its full field
    "pi0": _f("Base-state Exner function", group=BASE),
    "th0": _f("Base-state potential temperature", "K", 1, "cmo.thermal", group=BASE),
    "prs0": _f("Base-state pressure", "hPa", 0.01, group=BASE),
    "qv0": _f("Base-state water vapor mixing ratio", "g/kg", 1000, "YlGnBu", (0, 20),
              group=BASE),
    "u0": _signed("Base-state u (grid-relative)", "m/s", 1, (-30, 30), BASE),
    "v0": _signed("Base-state v (grid-relative)", "m/s", 1, (-30, 30), BASE),
    # (not written by r19.5 or r21.1: kept from the earlier catalog)
    "rho0": _f("Base-state dry-air density", "kg/m³", group=BASE),
    # turbulence (output_tke, output_km, output_kh, output_dissten, output_def)
    "tke": _f("Subgrid TKE", "m²/s²", 1, "magma", (0, 20), group=TURB),
    "kmh": _f("Eddy viscosity, horizontal", "m²/s", 1, "magma", group=TURB),
    "kmv": _f("Eddy viscosity, vertical", "m²/s", 1, "magma", group=TURB),
    "khh": _f("Eddy diffusivity, horizontal", "m²/s", 1, "magma", group=TURB),
    "khv": _f("Eddy diffusivity, vertical", "m²/s", 1, "magma", group=TURB),
    "kmw": _f("Eddy viscosity (w)", "m²/s", 1, "magma", group=TURB),
    "dissten": _f("Dissipation rate", "m²/s³", 1, "magma", group=TURB),
    "epst": _f("Dissipation (epst)", "1/s²", 1, "magma", group=TURB),
    "lenscl": _f("Turbulence length scale", "m", 1, "magma", group=TURB),
    "cme": _f("C_m (subgrid TKE scheme)", "", 1, "magma", group=TURB),
    "defv": _f("Vertical deformation", "1/s²", 1, "magma", group=TURB),
    "defh": _f("Horizontal deformation", "1/s²", 1, "magma", group=TURB),
    # boundary-layer schemes (ipbl): YSU, GFS-EDMF, MYNN, MYJ
    "xkzh": _f("Eddy diffusivity, heat (YSU)", "m²/s", 1, "magma", group=PBL),
    "xkzm": _f("Eddy viscosity (YSU)", "m²/s", 1, "magma", group=PBL),
    "dkt3d": _f("Thermal diffusivity (GFS-EDMF)", "m²/s", 1, "magma", group=PBL),
    "dku3d": _f("Momentum diffusivity (GFS-EDMF)", "m²/s", 1, "magma", group=PBL),
    "exch_h": _f("Thermal diffusivity (PBL)", "m²/s", 1, "magma", group=PBL),
    "exch_m": _f("Momentum diffusivity (PBL)", "m²/s", 1, "magma", group=PBL),
    "el_pbl": _f("PBL length scale", "m", 1, "magma", group=PBL),
    "tke_myj": _f("Subgrid TKE (MYJ)", "m²/s²", 1, "magma", group=PBL),
    "el_myj": _f("Length scale (MYJ)", "m", 1, "magma", group=PBL),
    "qke": _f("Twice TKE (MYNN)", "m²/s²", 1, "magma", group=PBL),
    "qwt": _signed("TKE vertical transport (MYNN)", "m²/s³", group=PBL),
    "qshear": _signed("TKE shear production (MYNN)", "m²/s³", group=PBL),
    "qbuoy": _signed("TKE buoyancy production (MYNN)", "m²/s³", group=PBL),
    "qdiss": _signed("TKE dissipation (MYNN)", "m²/s³", group=PBL),
    "dqke": _signed("TKE change (MYNN)", "m²/s³", group=PBL),
    "qke_adv": _signed("Advection of twice TKE (MYNN)", "m²/s³", group=PBL),
    "sh3d": _f("Stability function, heat (MYNN)", group=PBL),
    "sm3d": _f("Stability function, momentum (MYNN)", group=PBL),
    "tsq": _f("θl variance (MYNN)", "K²", 1, "magma", group=PBL),
    "qsq": _f("Liquid water variance (MYNN)", "(kg/kg)²", 1, "magma", group=PBL),
    "cov": _signed("θl–qw covariance (MYNN)", "K kg/kg", group=PBL),
    "qc_bl": _f("Subgrid cloud water (MYNN)", "g/kg", 1000, "cmo.ice", group=PBL),
    "qi_bl": _f("Subgrid cloud ice (MYNN)", "g/kg", 1000, "cmo.ice", group=PBL),
    "cldfra_bl": _f("Subgrid cloud fraction (MYNN)", "", 1, "Greys_r", (0, 1), group=PBL),
    "edmf_a": _f("Mass-flux updraft area (MYNN EDMF)", "", 1, "magma", group=PBL),
    "brz": _signed("Surface-layer bulk Richardson number", group=PBL),
    "qcpten": _signed("PBL tendency: qc", "g/kg/h", 3.6e6, group=PBL),
    "qipten": _signed("PBL tendency: qi", "g/kg/h", 3.6e6, group=PBL),
    "qncpten": _signed("PBL tendency: cloud droplet number", "#/kg/s", group=PBL),
    "qnipten": _signed("PBL tendency: ice number", "#/kg/s", group=PBL),
    "bndy": _f("Boundary flag", group=PBL),
    # radiation (output_radten)
    "swten": _signed("θ tendency: shortwave radiation", "K/h", 3600, group=RAD),
    "lwten": _signed("θ tendency: longwave radiation", "K/h", 3600, group=RAD),
    "cldfra": _f("Cloud fraction (radiation)", "", 1, "Greys_r", (0, 1), group=RAD),
    **{f"eff{k}": _f(f"Effective radius, {v}", "µm", 1, "magma", group=RAD)
       for k, v in (("c", "cloud water"), ("i", "cloud ice"), ("s", "snow"),
                    ("r", "rain"), ("g", "graupel"), ("is", "ice + snow"))},
    # cumulus scheme tendencies
    "thcuten": _signed("θ tendency: cumulus", "K/h", 3600, group=CU),
    "qvcuten": _signed("qv tendency: cumulus", "g/kg/h", 3.6e6, group=CU),
    "qccuten": _signed("qc tendency: cumulus", "g/kg/h", 3.6e6, group=CU),
    "qicuten": _signed("qi tendency: cumulus", "g/kg/h", 3.6e6, group=CU),
    "ucuten": _signed("u tendency: cumulus", "m/s²", group=CU),
    "vcuten": _signed("v tendency: cumulus", "m/s²", group=CU),
    # CM1's own diagnosed pressure (output_pdcomp)
    "pipb": _signed("π′ buoyant (CM1's)", "", 1, None, PDEC, "PuOr_r"),
    "pipdl": _signed("π′ linear dynamic (CM1's)", "", 1, None, PDEC, "PuOr_r"),
    "pipdn": _signed("π′ nonlinear dynamic (CM1's)", "", 1, None, PDEC, "PuOr_r"),
    "pipc": _signed("π′ Coriolis (CM1's)", "", 1, None, PDEC, "PuOr_r"),
    "pgradb": _signed("Vertical PGF: buoyant part (CM1's)", "m/s²", group=PDEC),
    "pgraddl": _signed("Vertical PGF: linear dynamic part (CM1's)", "m/s²", group=PDEC),
    "pgraddn": _signed("Vertical PGF: nonlinear dynamic part (CM1's)", "m/s²", group=PDEC),
    "pgradc": _signed("Vertical PGF: Coriolis part (CM1's)", "m/s²", group=PDEC),
    # fall speeds (output_fallvel)
    **{f"vt{k}": _f(f"Fall speed, {v}", "m/s", 1, "magma", group=MP)
       for k, v in (("c", "cloud water"), ("r", "rain"), ("s", "snow"),
                    ("g", "graupel"), ("i", "cloud ice"))},
    # time averages (dotimeavg)
    "thtavg": _f("Time-average θ", "K", 1, "cmo.thermal", group=TAVG),
    "qvtavg": _f("Time-average qv", "g/kg", 1000, "YlGnBu", (0, 20), group=TAVG),
    "utavg": _signed("Time-average u (staggered)", "m/s", 1, (-30, 30), TAVG),
    "vtavg": _signed("Time-average v (staggered)", "m/s", 1, (-30, 30), TAVG),
    "wtavg": _signed("Time-average w (staggered)", "m/s", 1, (-20, 20), TAVG),
    "tketavg": _f("Time-average subgrid TKE", "m²/s²", 1, "magma", (0, 20), group=TAVG),
    "wsptavg": _f("Time-average horizontal wind speed", "m/s", 1, "turbo", (0, 40),
                  group=TAVG),
}

# ---- budgets (output_thbudget, output_qvbudget, output_u/v/wbudget)
_TERMS = {
    "hadv": "horizontal advection", "vadv": "vertical advection",
    "hidiff": "horizontal implicit diffusion", "vidiff": "vertical implicit diffusion",
    "hediff": "horizontal explicit diffusion", "vediff": "vertical explicit diffusion",
    "hturb": "horizontal subgrid turbulence", "vturb": "vertical subgrid turbulence",
    "mp": "microphysics", "rdamp": "Rayleigh damping", "rad": "radiation",
    "div": "moist divergence", "diss": "dissipative heating", "pbl": "PBL scheme",
    "subs": "large-scale subsidence", "nudge": "nudging", "lsw": "large-scale w",
    "pgrad": "pressure gradient", "cor": "Coriolis", "cent": "centrifugal",
    "buoy": "buoyancy",
}
_ADV = "hadv vadv hidiff vidiff hediff vediff hturb vturb"
_BUDGETS = {  # prefix: (quantity, units, scale, its terms)
    "ptb": ("θ", "K/h", 3600, f"{_ADV} mp rdamp rad div diss pbl subs nudge lsw"),
    "qvb": ("qv", "g/kg/h", 3.6e6, f"{_ADV} mp pbl subs nudge lsw"),
    "ub": ("u", "m/s²", 1, f"{_ADV} pgrad rdamp cor cent pbl subs lsw"),
    "vb": ("v", "m/s²", 1, f"{_ADV} pgrad rdamp cor cent pbl subs lsw"),
    "wb": ("w", "m/s²", 1, f"{_ADV} pgrad rdamp buoy"),
}
for _p, (_q, _u, _s, _ts) in _BUDGETS.items():
    for _t in _ts.split():
        OUTPUTS[f"{_p}_{_t}"] = _signed(f"{_q} budget: {_TERMS[_t]}", _u, _s, None, BUD)
# microphysics process tendencies (with the θ / qv budgets)
for _t, _d in {"cond": "condensation", "evac": "cloud water evaporation",
               "evar": "rain evaporation", "dep": "deposition", "subl": "sublimation",
               "melt": "melting", "frz": "freezing"}.items():
    OUTPUTS[f"tt_{_t}"] = _signed(f"θ tendency: {_d}", "K/h", 3600, None, BUD)
    if _t not in ("melt", "frz"):
        OUTPUTS[f"qt_{_t}"] = _signed(f"qv tendency: {_d}", "g/kg/h", 3.6e6, None, BUD)
OUTPUTS["td_efall"] = _signed("T tendency: energy fallout", "K/h", 3600, None, BUD)

# ---- microphysics variables (output_q), by scheme (param.F's qname).  Mass mixing
# ratios in g/kg; numbers per kg; NSSL volumes and 6th moments as in the files.
_MASS = {
    "qc": ("Cloud water", "cmo.ice", (0, 3)), "ql": ("Liquid water", "cmo.ice", (0, 3)),
    "qr": ("Rain", "cmo.rain", (0, 5)), "qi": ("Cloud ice", "cmo.ice", (0, 2)),
    "qs": ("Snow", "cmo.ice", (0, 3)), "qg": ("Graupel", "cmo.amp", (0, 5)),
    "qhl": ("Hail", "cmo.amp", (0, 5)),
    "qi1": ("Ice, category 1 (planar)", "cmo.ice", (0, 2)),
    "qi2": ("Ice, category 2 (columnar)", "cmo.ice", (0, 2)),
    "qi3": ("Ice, category 3 (aggregates)", "cmo.ice", (0, 2)),
    "qir": ("Rime ice mass (P3)", "cmo.amp", (0, 5)),
    "ri": ("Rime ice mass (P3)", "cmo.amp", (0, 5)),
    "ri2": ("Rime ice mass, 2nd category (P3)", "cmo.amp", (0, 5)),
}
for _n, (_l, _c, _r) in _MASS.items():
    OUTPUTS[_n] = _f(_l, "g/kg", 1000, _c, _r, group=MP)
_NUMBER = {
    "nci": "Ice number", "ncs": "Snow number", "ncr": "Rain number",
    "ncg": "Graupel number", "ncc": "Cloud droplet number",
    "nc": "Cloud droplet number", "nr": "Rain number", "ni": "Ice number",
    "ni1": "Ice number, category 1", "ni2": "Ice number, category 2",
    "ni3": "Ice number, category 3", "qni": "Ice number", "qnr": "Rain number",
    "qnc": "Cloud droplet number",
    "ccn": "CCN number", "cna": "Activated CCN number", "cia": "Activated IN number",
    "ccw": "Cloud droplet number", "crw": "Rain number", "cci": "Ice crystal number",
    "csw": "Snow number", "chw": "Graupel number", "chl": "Hail number",
}
for _n, _l in _NUMBER.items():
    OUTPUTS[_n] = _f(_l, "#/kg", 1, "magma", group=MPN)
for _n, _l in {"vhw": "Graupel particle volume", "vhl": "Hail particle volume",
               "qib": "Rime volume (P3)", "bi": "Rime volume (P3)",
               "bi2": "Rime volume, 2nd category (P3)"}.items():
    OUTPUTS[_n] = _f(_l, "m³/kg", 1, "magma", group=MPN)
for _n, _l in {"zrw": "Rain reflectivity moment", "zhw": "Graupel reflectivity moment",
               "zhl": "Hail reflectivity moment",
               "qzi": "Ice 6th moment (P3)"}.items():
    OUTPUTS[_n] = _f(_l, "m⁶/kg", 1, "magma", group=MPN)
for _i, _k in ((1, "planar"), (2, "columnar"), (3, "aggregate")):
    OUTPUTS[f"ai{_i}"] = _f(f"Ice a-axis moment, {_k}", "", 1, "magma", group=MPN)
    OUTPUTS[f"ci{_i}"] = _f(f"Ice c-axis moment, {_k}", "", 1, "magma", group=MPN)
    OUTPUTS[f"vmi3d_{_i}"] = _f(f"Ice fall speed, {_k} (ISHMAEL)", "m/s", 1, "magma",
                                group=MP)
    OUTPUTS[f"di3d_{_i}"] = _f(f"Ice max diameter, {_k} (ISHMAEL)", "mm", 1000, "magma",
                               group=MP)
    OUTPUTS[f"rhopo3d_{_i}"] = _f(f"Ice effective density, {_k} (ISHMAEL)", "kg/m³", 1,
                                  "magma", group=MP)
    OUTPUTS[f"phii3d_{_i}"] = _f(f"Ice aspect ratio, {_k} (ISHMAEL)", "", 1, "magma",
                                 group=MP)
for _s, _k in (("", ""), ("2", ", 2nd category")):
    OUTPUTS[f"p3_vmi{_s}"] = _f(f"Ice fall speed{_k} (P3)", "m/s", 1, "magma", group=MP)
    OUTPUTS[f"p3_di{_s}"] = _f(f"Ice mean size{_k} (P3)", "mm", 1000, "magma", group=MP)
    OUTPUTS[f"p3_rhopo{_s}"] = _f(f"Ice density{_k} (P3)", "kg/m³", 1, "magma", group=MP)


# ---- fields a namelist names by number
_NUMBERED = (
    (re.compile(r"^pt(\d+)$"), lambda i: _f(f"Passive tracer {i}", "g/kg", 1000,
                                            "magma", group=MP)),
    (re.compile(r"^out2d(\d+)$"), lambda i: _f(f"User 2D output {i}")),
    # (3D ones, on scalar, u, v or w points alike: out1, out2, ...)
    (re.compile(r"^out(\d+)$"), lambda i: _f(f"User 3D output {i}",
                                             group="Other model fields")),
)


def describe(name):
    """OUTPUTS' entry for a numbered field (pt3, out2d1, out12), or None."""
    for pat, make in _NUMBERED:
        m = pat.match(name)
        if m:
            return make(int(m.group(1)))
    return None
