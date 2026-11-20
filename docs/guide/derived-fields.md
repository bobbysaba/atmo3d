# Derived fields

Every field atmo3d computes from the output: what it is, the equation as coded, its
units and sign, the inputs it needs, and what it leaves out or assumes. A field is listed
only when the run has every input it needs. [Notes on the fields](fields.md) says how
the derived fields are used (layers, storm motion, derivatives, speed). To add a field of
your own as an expression, without changing the code, see
[Your own derived fields](user-fields.md).

Inputs are given as CM1 / WoFS names. Constants: g = 9.81 m/s², Rd = 287.04, Rv = 461.5
J/(kg K), ε = Rd/Rv, κ = Rd/cp (CM1's 287.04/1005.7 = 0.2854; WRF's 2/7 for WoFS).
q is a mixing ratio in kg/kg in the equations (shown in g/kg). A prime (′) is the
departure from the base state: CM1's `th0`, `prs0`, `qv0`, or for WoFS the member's own
field at its first time (`THETA0`, `PRES0`, `QVAPOR0`).

Each field's "Leaves out / assumes" text is its own description in the code, so the two
always agree.

## Thermodynamics

| Name | Field (units) | Equation as coded | Inputs | Leaves out / assumes |
|---|---|---|---|---|
| `thpert` | θ′ (K) | θ − θ0 | th, th0 / THETA, THETA0 | For WoFS the base state is the member's first time, so this is the change since then. |
| `prspert` | p′ (hPa) | (p − p0) / 100 | prs, prs0 / PRES, PRES0 | For WoFS the base state is the member's first time, so this is the change since then. It includes any domain-wide pressure trend. |
| `buoy` | Buoyancy (m/s²) | B = g [θ′/θ0 + (Rv/Rd − 1)(qv − qv0) − Σ q<sub>cond</sub>], Σ over every liquid and ice species in the output, less the base state's qc0 + qi0 where the files have them. Positive upward. | th, th0, qv, qv0, the hydrometeors (qc0, qi0 if present) | No pressure term. The base state's condensate (qc0, qi0) is subtracted where the files have it, else taken as zero. For WoFS the base state is the member's first time, so this is the change since then. |
| `thrho` | θρ (K) | θ (1 + qv/ε) / (1 + qv + Σ q<sub>cond</sub>) | th, qv, the hydrometeors | Loads every liquid and ice species in the output. |
| `thrhopert` | θρ′ (K) | θρ − θ0 (1 + qv0/ε) / (1 + qv0 + qc0 + qi0) | th, th0, qv, qv0, the hydrometeors (qc0, qi0 if present) | The base state's condensate (qc0, qi0) is loaded where the files have it, else taken as zero. For WoFS the base state is the member's first time, so this is the change since then. |
| `thetae` | θe (K) | T (10⁵/p)<sup>0.2854 (1 − 0.28 r)</sup> exp[(3.376/T<sub>L</sub> − 0.00254) · 1000 r (1 + 0.81 r)], with T<sub>L</sub> = 56 + 1 / [1/(Td − 56) + ln(T/Td)/800], r = qv | th, prs, qv | Pseudo-equivalent; the dewpoint is over liquid and held at or below T. |
| `tempc` | Temperature (°C) | θ (p/10⁵)<sup>κ</sup> − 273.15 | th, prs | κ is the model's own: CM1's Rd/cp, or WRF's 2/7 for WoFS. |
| `dewc` | Dewpoint (°C) | e = p qv / (ε + qv); Td = 243.5 ln(e/611.2) / (17.67 − ln(e/611.2)) | prs, qv | Over liquid water at every temperature (no frost point). |
| `rh` | Relative humidity (liquid) (%) | 100 e / e<sub>s</sub>(T), e<sub>s</sub> = 611.2 exp(17.67 T<sub>c</sub> / (T<sub>c</sub> + 243.5)) Pa | th, prs, qv | Over liquid water at every temperature, so below 0 °C it reads lower than RH over ice. Not capped at 100 %. |

## Kinematics

u, v, w are the winds on the scalar points (CM1's `uinterp`, `vinterp`, `winterp`;
WoFS's U, V, W averaged from the staggered points). Derivatives are per metre, centred
on the grid's real spacing; on WoFS's terrain-following levels ∂/∂x and ∂/∂y are taken at
constant height (along the level, less its slope times ∂/∂z).

| Name | Field (units) | Equation as coded | Inputs | Leaves out / assumes |
|---|---|---|---|---|
| `wspd3d` | Wind speed (ground-relative) (m/s) | √((u + umove)² + (v + vmove)²) | u, v | The horizontal wind only (no w). |
| `hdiv` | Horizontal divergence (10⁻³ s⁻¹) | 10³ (∂u/∂x + ∂v/∂y). Positive: divergence. | u, v | No map factor (WoFS's map projection is left out). |
| `xvort` | x vorticity (1/s), WoFS only | ξ = ∂w/∂y − ∂v/∂z (CM1's files have their own `xvort`) | U, V, W | No map factor (WoFS's map projection is left out). |
| `yvort` | y vorticity (1/s), WoFS only | η = ∂u/∂z − ∂w/∂x (CM1's files have their own `yvort`) | U, V, W | No map factor (WoFS's map projection is left out). |
| `hvort` | Horizontal vorticity magnitude (1/s) | √(ξ² + η²) | xvort, yvort (CM1) or the winds (WoFS) | |
| `wstream` | Streamwise vorticity (1/s) | ξ s<sub>x</sub> + η s<sub>y</sub>, s the unit vector of the storm-relative horizontal wind (u + umove − c<sub>x</sub>, v + vmove − c<sub>y</sub>) | as `hvort`, u, v, the storm motion c | Relative to the storm motion used, which the title shows. The direction is arbitrary where the storm-relative wind is near 0. |
| `wcross` | Crosswise vorticity (1/s) | −ξ s<sub>y</sub> + η s<sub>x</sub>. Positive: the vorticity points to the left of the storm-relative wind. | as `wstream` | Relative to the storm motion used, which the title shows. The direction is arbitrary where the storm-relative wind is near 0. |
| `bgen_x` | Baroclinic x-vorticity generation (10⁻⁴ s⁻²) | 10⁴ ∂B/∂y | as `buoy` | B as in buoy; the buoyancy torque only (no term from p′). |
| `bgen_y` | Baroclinic y-vorticity generation (10⁻⁴ s⁻²) | −10⁴ ∂B/∂x. Positive: B decreasing eastward makes positive η. | as `buoy` | B as in buoy; the buoyancy torque only (no term from p′). |

∂B/∂x and ∂B/∂y are built from the derivatives of B's inputs (B is linear in them), so
they equal the derivative of `buoy` taken like any other field.

## Vorticity tendencies

In 10⁻⁴ s⁻². ζ is CM1's `zvort` or WoFS's `REL_VORT`; ξ, η as above; f is the run's
Coriolis parameter (CM1's `fcor` when `icor` = 1, else 0; WoFS's `F` field).

| Name | Field | Equation as coded | Inputs | Leaves out / assumes |
|---|---|---|---|---|
| `zstretch` | ζ stretching | −10⁴ (ζ + f)(∂u/∂x + ∂v/∂y). Positive: convergence spinning up cyclonic ζ. | zvort, u, v (and F for WoFS) | Anelastic form; f is the run's Coriolis parameter. |
| `ztilt` | ζ tilting | 10⁴ (ξ ∂w/∂x + η ∂w/∂y) | as `hvort`, w | |
| `ztend` | ζ stretching + tilting | `zstretch` + `ztilt` | both | Not the full ζ tendency: advection, mixing and the baroclinic and solenoidal terms are left out. |
| `okubo` | Okubo–Weiss | 10⁴ (s<sub>n</sub>² + s<sub>s</sub>² − ω²), s<sub>n</sub> = ∂u/∂x − ∂v/∂y, s<sub>s</sub> = ∂v/∂x + ∂u/∂y, ω = ∂v/∂x − ∂u/∂y. Positive: strain dominates; negative: rotation dominates. | u, v | ω is from the winds, not the files' ζ. |

## Microphysics

| Name | Field (units) | Equation as coded | Inputs | Leaves out / assumes |
|---|---|---|---|---|
| `qcloud` | Cloud condensate (g/kg) | 1000 (qc + qi), of those in the output | qc, qi / QCLOUD, QICE | |
| `qprecip` | Precipitation (g/kg) | 1000 (qr + qs + qg + qhl), of those in the output | qr, qs, qg, qhl / QRAIN, QSNOW, QGRAUP, QHAIL | Snow counts as precipitation. |

## Column fields

2D fields over a layer of each column (heights above ground). Each model level counts
with the part of its grid cell inside the layer.

| Name | Field (units) | Equation as coded | Inputs | Leaves out / assumes |
|---|---|---|---|---|
| `uh25` | Updraft helicity 2–5 km (m²/s²) | Σ w ζ Δz over 2–5 km, where w > 0 and ζ > 0. Only when the output has no 2–5 km UH of its own (CM1's `uh`, WoFS's `UH`, listed instead). | w, zvort | ∫ w ζ dz where w > 0 and ζ > 0. |
| `uh01` | Updraft helicity 0–1 km (m²/s²) | as `uh25`, over 0–1 km | w, zvort | ∫ w ζ dz where w > 0 and ζ > 0. |

## Sounding parameters

2D fields from each column, computed as the [Soundings](soundings.md#what-is-computed)
tab computes them. The winds are ground-relative and linearly interpolated in height
to the layer top.

| Name | Field (units) | Equation as coded | Inputs | Leaves out / assumes |
|---|---|---|---|---|
| `shear0250`, `shear0500`, `shear01`, `shear03`, `shear06` | Bulk shear 0–250 m, 0–500 m, 0–1, 0–3, 0–6 km (m/s) | \|V(top) − V(bottom)\| | u, v (and u10, v10 / U10, V10) | From the 10 m winds when the output has them, else from the lowest model level. |
| `srh0250`, `srh0500`, `srh01`, `srh03` | Storm-relative helicity 0–250 m, 0–500 m, 0–1, 0–3 km (m²/s²) | Σ<sub>k</sub> [(u<sub>k+1</sub> − c<sub>x</sub>)(v<sub>k</sub> − c<sub>y</sub>) − (u<sub>k</sub> − c<sub>x</sub>)(v<sub>k+1</sub> − c<sub>y</sub>)] up to the layer top. Positive: winds veering with height relative to the storm. | as shear, the storm motion c | From the 10 m winds when the output has them, else from the lowest model level. Relative to the storm motion used, which the title shows. |
| `sbcape`, `mlcape`, `mucape` | CAPE (J/kg) | ∫ B dz from the LFC to the EL (net: negative pockets in between subtracted), B = g (Tv,parcel − Tv,env)/Tv,env | prs, th, qv | Pseudoadiabatic, liquid only (no ice), with the virtual-temperature correction and no condensate loading. |
| `sbcin`, `mlcin`, `mucin` | CIN (J/kg, ≤ 0) | ∫ B dz where B < 0, from the parcel's level to the LFC | prs, th, qv | Pseudoadiabatic, liquid only (no ice), with the virtual-temperature correction and no condensate loading. |
| `sblcl`, `mllcl`, `mulcl` | LCL height (m AGL) | the height where the parcel lifted dry adiabatically reaches T<sub>L</sub> (as in `thetae`) | prs, th, qv | |
| `stp` | Significant tornado parameter (fixed layer) | (SBCAPE/1500) · clip((2000 − SBLCL)/1000, 0, 1) · (SRH<sub>0–1</sub>/150) · S, S = 0 for 0–6 km shear < 12.5 m/s, else min(shear, 30)/20 | prs, th, qv, u, v, the storm motion | Fixed layers (not the effective layer); no CIN term. From the 10 m winds when the output has them, else from the lowest model level. |
| `scp` | Supercell composite parameter (fixed layer) | (MUCAPE/1000) · (SRH<sub>0–3</sub>/50) · S · C, S = 0 for 0–6 km shear < 10 m/s, else min(shear, 20)/20; C = 1 for MUCIN > −40, else −40/MUCIN | as `stp` | 0–3 km SRH and 0–6 km shear stand in for the effective-layer ones. From the 10 m winds when the output has them, else from the lowest model level. |

Parcels: SB starts at the lowest model level; ML is the pressure-weighted mean θ and qv
of the lowest 100 hPa; MU is the level of highest θe in the lowest 300 hPa. LFC: where
the first positive run above the LCL begins; EL: where the last one ends.

## Pressure decomposition (CM1)

The parts p<sub>b</sub>, p<sub>l</sub>, p<sub>nl</sub>, p<sub>c</sub> and their
accelerations come from the files, or are computed on request from CM1's equation
(buoyancy, linear, nonlinear and Coriolis forcing; a uniform horizontal grid without
terrain). Each part's mean is 0 at the top level. The accelerations are
−cp θv0 ∂π<sub>x</sub>/∂z (and B + that for `acc_b`, the net buoyant acceleration),
positive upward. The sums:

| Name | Field (units) | Equation as coded | Inputs | Leaves out / assumes |
|---|---|---|---|---|
| `p_dyn` | Dynamic p′ (Pa) | p<sub>l</sub> + p<sub>nl</sub> + p<sub>c</sub> | p_l, p_nl, p_c | |
| `acc_dyn` | Dynamic vertical pressure-gradient acceleration (m/s²) | acc<sub>l</sub> + acc<sub>nl</sub> + acc<sub>c</sub> | acc_l, acc_nl, acc_c | |
| `acc_tot` | Total acceleration (m/s²) | acc<sub>b</sub> + acc<sub>l</sub> + acc<sub>nl</sub> + acc<sub>c</sub> | acc_b, acc_l, acc_nl, acc_c | Leaves out the rest of w's equation: turbulence, damping and the compressible part. |

## Derivatives of any field

`ddx.<field>`, `ddy.<field>`, `ddz.<field>` and `gradh.<field>` (\|∇h\| =
√((∂/∂x)² + (∂/∂y)²)) are in the field's units per metre: centred differences on the
real grid spacing (stretched grids too), one-sided at the edges; ∂/∂z on each column's
own heights, for 3D fields only. The derivative of a derived field is taken of the field
itself. See [Notes on the fields](fields.md#derivatives-of-any-field).
