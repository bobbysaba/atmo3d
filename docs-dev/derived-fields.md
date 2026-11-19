# Phase 2b, step 2: derived-field audit

Status: **prepared 2026-11-19, for Bobby's review.** Nothing in the code has changed for
this step. For each field, mark **confirmed**, **corrected** (say how) or **dropped** in
the Decision column. Step 3 fixes the corrected ones and adds a test with an analytic
answer for each confirmed one (the "Test" lines are the proposed cases).

Scope: every derived field in `core/fields.py`, the pressure decomposition in
`pdecomp/cm1_pdecomp.py`, the derivatives (`ddx. ddy. ddz. gradh.`), and the fields the
WoFS reader computes on read (§7). The sounding panel (`thermo.analyze`: Bunkers
motion, effective layers, ...) is out of scope. The column fields below use the same
parcel and kinematics code it does.

Notation:
- Inputs are by **role** (`core/catalog.py` ROLES). CM1 / WoFS names:
  - theta: th / THETA; pres: prs / PRES; qv: qv / QVAPOR;
  - theta0, pres0, qv0: th0, prs0, qv0 / THETA0, PRES0, QVAPOR0;
  - u, v, w: uinterp, vinterp, winterp / U, V, W (grid-relative, on scalar points);
  - xvort, yvort, zvort: CM1's files only. WoFS has none: see §8.
- `hyd` is the hydrometeors present, of qc qr qi qs qg qhl. For WoFS these are QCLOUD,
  QRAIN, QICE, QSNOW, QGRAUP, QHAIL.
- Constants in `fields.py`: g = 9.81, ε = Rd/Rv = 287.04/461.5, κ = Rd/cp =
  287.04/1005.7 = 0.2854. These are CM1's. WRF uses Rd = 287, cp = 1004.5, κ = 2/7.
- A WoFS perturbation is the change since the member's first time (audit A5). Every
  "′" field below is that for WoFS.

---

## 0. Findings to settle first

These came up while writing the entries. Each one is also flagged in its entry.

| # | Finding | Proposal | Decision |
|---|---------|----------|----------|
| F1 | **UH counts negative values.** CM1's own `uh` adds up only points where w > 0 **and** ζ > 0. Checked on the demo at two times: done that way, ours matches CM1's to correlation 1.000, with the same max. Ours adds every point (corr 0.985–0.991, min −868 m²/s² where CM1's min is 0). | `uh25`, `uh01`: count w > 0 and ζ > 0 only, as CM1 does. Then CM1's `uh` and our `uh25` are the same field. Hide one of them (Other)? | |
| F2 | **Two buoyancies.** `buoy` is the full θρ form over θρ0 (§1.3). The B inside `acc_b` is CM1's linearised form, over θ0, with more condensate names (§5). They agree to first order, but `acc_b − buoy` is not exactly the buoyancy-pressure acceleration. | Make `buoy` CM1's form, so `acc_b = buoy + pgrad_b` exactly. Or keep θρ and label the two differently. | |
| F3 | **`hdiv`, `bgen_x`, `bgen_y` use the mean grid spacing** (`run.dx`, `run.dy`). That is wrong on a stretched horizontal grid. The derivatives (`hgrad`) use the real x, y. | Use `hgrad` (the real coordinates). Uniform grids, and so the image baselines, do not change. | |
| F4 | **ζ stretching is the Boussinesq form** ζ ∂w/∂z. The anelastic form is −ζ ∇h·V = ζ ∂w/∂z + ζ w ∂(ln ρ0)/∂z. The second term is about w/Hρ ≈ 10⁻³ s⁻¹ for w = 10 m/s, against ∂w/∂z ≈ 10⁻² s⁻¹. f is left out too. | Keep ζ ∂w/∂z and say "Boussinesq" in the label; or switch to −ζ ∇h·V (needs ∂u/∂x + ∂v/∂y, already computed for `hdiv`). f: leave out (CM1 runs here have f ≈ 1e-4, small next to ζ ≈ 1e-2). | |
| F5 | **Horizontal derivatives on WoFS's terrain-following levels.** On a height map, ∂/∂x is taken at constant height (the plane is interpolated first). On a model-level map, in 3D and in the volume path, it is taken along the model level. Views can disagree where the ground slopes. No map factor either (WRF's Lambert grid: MAPFAC_M ≈ 1 ± 0.02). | Along model levels plus the slope correction ∂/∂x\|z = ∂/∂x\|η − (∂z/∂x\|η) ∂/∂z, so every view gives ∂/∂x at constant height. Map factor: leave out, and say so. | |
| F6 | **Storm-relative fields default to the domain motion** (umove, vmove) when no motion is chosen. For a run that does not translate, that is (0, 0). The motion comes from the map's storm-motion select (custom / domain / sounding's Bunkers / track). | Keep, but show the motion used in the title (the note exists: `_storm_note`). Check that it is always shown. | |
| F7 | **Bands in the accelerations above ~12 km** (both decompositions; from the 2026-11-18 comparison). | Investigate before confirming the `acc_*` fields: §5.3. | |
| F8 | **θe**: `fields._thetae` does not clip Td ≤ T. `thermo.theta_e`, used by the soundings, does. A supersaturated point gives slightly different θe in the two. | Clip, as `thermo.theta_e` does. Better: `fields` calls `thermo.theta_e`, so there is one copy. | |

---

## 1. Thermodynamics

### 1.1 `thpert` θ′ (K)

- Coded: θ − θ0.
- Inputs: theta, theta0.
- CM1: the file's `thpert`, when written, is listed instead (`file_first`). CM1 writes
  th − th0, so the result is the same.
- WoFS: THETA − THETA0, the change since the first time.
- Test: θ = θ0 + 2 everywhere → 2.
- Decision:

### 1.2 `prspert` p′ (hPa)

- Coded: 0.01 (p − p0).
- Inputs: pres, pres0 (Pa).
- CM1: the file's `prspert` is listed instead, when written.
- WoFS: the change since the first time. This includes any domain-wide pressure trend
  (diurnal tide, synoptic change).
- Test: p = p0 + 150 Pa → 1.5.
- Decision:

### 1.3 `buoy` Buoyancy (θρ′, with loading) (m/s²)

- Coded: B = g (θρ − θρ0) / θρ0.
  - θρ = θ (1 + qv/ε) / (1 + qv + Σ hyd)
  - θρ0 = θ0 (1 + qv0/ε) / (1 + qv0)
- Reference: Emanuel (1994) §4.3 (θρ). The buoyancy is B ≈ g θρ′/θρ0, leaving out the
  pressure term −p′/(γ p0).
- Inputs: theta, qv, theta0, qv0, hyd.
- Assumptions to confirm:
  - **No hydrometeors in the base state.** CM1 writes no qc0, qi0. WoFS's first time does
    have cloud; it is left out.
  - **No p′ term.** CM1's own B leaves it out too; the decomposition puts it in p_b.
  - **Not linearised**, and divided by θρ0 rather than θ0. CM1's B (in `acc_b`) is
    g [θ′/θ0 + (Rv/Rd − 1) qv′ − Σ q_cond]. See F2.
  - Hydrometeors: only the six roles. CM1's B also counts qh, qi1, qi2, qi3 when
    present; P3 and other microphysics schemes write those.
  - WoFS: θ0 and qv0 are the first time's 3D fields (not horizontal means), so B is the
    change since the first time.
- Test: θ = θ0 (1 + 0.01), qv = qv0 = 0, no hydrometeors → 0.0981. Then qc = 1 g/kg alone
  → g (1/1.001 − 1).
- Decision:

### 1.4 `thrho`, `thrhopert` θρ, θρ′ (K)

- Coded: θρ as in 1.3, and θρ − θρ0 (base without loading).
- Inputs: theta, qv, hyd (+ theta0, qv0 for θρ′).
- Assumptions: the same base state as `buoy`. θρ′ is not θρ minus a horizontal mean.
- Test: qv = 0, no hydrometeors → θρ = θ. qv = 0.01 → θ (1 + 0.01/ε)/1.01.
- Decision:

### 1.5 `thetae` θe (K)

- Coded: Bolton (1980) eq. 43 (pseudo-equivalent potential temperature).
  - θe = T (p0/p)^(0.2854 (1 − 0.28 r)) · exp[(3.376/TL − 0.00254) · 1000 r (1 + 0.81 r)]
  - TL from Bolton eq. 15 (from Td)
  - T = θ (p/p0)^κ, Td as in 1.7, r = max(qv, 1e-10)
- Inputs: theta, pres, qv.
- Assumptions: r in kg/kg (the formula's 1000 r is g/kg). Td is not clipped to ≤ T
  (F8).
- Test: compare with MetPy's `equivalent_potential_temperature` (also Bolton 43) at a few
  (p, T, r) points.
- Decision:

### 1.6 `tempc` Temperature (°C)

- Coded: T = θ (p / 10⁵)^κ − 273.15, with κ = 0.2854.
- Inputs: theta, pres.
- Assumption: κ is CM1's. For WoFS (WRF's κ = 2/7), T comes out about 0.1 K off at
  200 hPa. Per-data-type constants, or accept it?
- Test: θ = 300, p = 10⁵ → 26.85. At p = 5·10⁴ → 300 · 0.5^κ − 273.15.
- Decision:

### 1.7 `dewc` Dewpoint (°C)

- Coded:
  - e = p qv / (ε + qv), with qv ≥ 1e-10
  - Td = 243.5 ln(e/611.2) / (17.67 − ln(e/611.2))
- Reference: Bolton (1980) eq. 10, inverted (saturation over liquid water).
- Inputs: pres, qv.
- Assumption: over liquid at every temperature (no frost point).
- Test: e = 611.2 Pa → 0 °C.
- Decision:

### 1.8 `rh` Relative humidity (liquid) (%)

- Coded: 100 e / es(T), with es = 611.2 exp(17.67 Tc / (Tc + 243.5)) (Bolton eq. 10).
- Inputs: theta, pres, qv.
- Assumptions:
  - **Over liquid at every temperature.** Below 0 °C this reads lower than RH over ice;
    in the anvil, ice-saturated air shows ~70–90 %.
  - Not clipped: it can go over 100 %.
  - RH as e/es, not qv/qvs (they differ by under 1 %).
- Option: RH over ice below 0 °C, as a second field `rhi`.
- Test: qv = qvs(T, p) → 100.
- Decision:

---

## 2. Kinematics

### 2.1 `wspd3d` Wind speed (ground-relative) (m/s)

(The step 1 sheet called it `wspd`; the code's name is `wspd3d`.)

- Coded: |(u + umove, v + vmove)|.
- Inputs: u, v.
- Assumptions: horizontal only (no w). WoFS: umove = vmove = 0.
- Test: u = 3, v = 4, no motion → 5. With umove = −3 → 4.
- Decision:

### 2.2 `hdiv` Horizontal divergence (10⁻³ s⁻¹)

- Coded: 10³ (∂u/∂x + ∂v/∂y), from np.gradient with the **mean** dx, dy (F3).
- Differences: centred, one-sided at the edges. On WoFS: along whatever plane is drawn
  (F5).
- Inputs: u, v.
- Test: u = a x, v = b y → 10³ (a + b), exactly, edges included.
- Decision:

### 2.3 `bgen_x`, `bgen_y` Baroclinic generation (10⁻⁴ s⁻²)

- Coded: ∇ × (B k̂) = (∂B/∂y, −∂B/∂x), ×10⁴, B from 1.3. These are the horizontal
  vorticity generation terms in the Boussinesq equation (Klemp 1987;
  Markowski & Richardson 2010, eq. 2.70).
- Inputs: as `buoy`.
- Assumptions: whatever `buoy` settles (F2); mean grid spacing (F3).
- Sign: positive bgen_y (−∂B/∂x) means B decreasing eastward makes +η.
- Test: B = c x → bgen_x = 0, bgen_y = −10⁴ c.
- Decision:

### 2.4 `hvort` Horizontal vorticity magnitude (1/s)

- Coded: |(ξ, η)| from the file's xvort, yvort.
- Inputs: xvort, yvort.
- CM1's ξ = ∂w/∂y − ∂v/∂z and η = ∂u/∂z − ∂w/∂x, computed on its own grid and
  interpolated to scalar points.
- Test: ξ = 3, η = 4 → 5.
- Decision:

### 2.5 `wstream`, `wcross` Streamwise / crosswise vorticity (1/s)

- Coded:
  - s = (u + umove − cx, v + vmove − cy) / |…|, the storm-relative wind direction
  - streamwise = ξ sx + η sy
  - crosswise = −ξ sy + η sx, positive when ω_h points to the **left** of the
    storm-relative wind
- Reference: Davies-Jones (1984).
- Inputs: xvort, yvort, u, v, and the storm motion (cx, cy).
- Assumptions:
  - Storm motion: F6.
  - |s| is floored at 1e-6, so the direction is arbitrary where the storm-relative wind
    is ~0.
  - Not listed for WoFS (`storm_relative = False`, Phase 3).
- Sign convention to confirm: crosswise positive to the left (Davies-Jones' convention).
- Test: wind (10, 0), ω = (0, 0.01) → streamwise 0, crosswise +0.01. ω = (0.01, 0) →
  streamwise 0.01, crosswise 0.
- Decision:

### 2.6 `qcloud`, `qprecip` Cloud condensate, Precipitation (g/kg)

- Coded: 1000 (qc + qi), and 1000 (qr + qs + qg + qhl), each over those present.
- WoFS: QCLOUD + QICE, and QRAIN + QSNOW + QGRAUP + QHAIL.
- Assumption: snow counts as precipitation. Should snow go in "cloud" for anvil studies?
  No for now.
- Test: qc = 0.001, qi = 0.002 → 3.
- Decision:

---

## 3. Vorticity tendencies (10⁻⁴ s⁻²)

These need zvort (and xvort, yvort for tilting), so CM1 only, until §8. The derivatives
are per m, from `ddz.w`, `ddx.w`, ... (§6).

### 3.1 `zstretch` ζ stretching

- Coded: 10⁴ ζ ∂w/∂z.
- Reference: the ζ equation, e.g. Markowski & Richardson (2010) eq. 2.51, Boussinesq.
- Inputs: zvort, ddz.w.
- Assumptions: Boussinesq form, no f (F4).
- Test: ζ = 0.01, w = 0.002 z → 0.2.
- Decision:

### 3.2 `ztilt` ζ tilting

- Coded: 10⁴ (ξ ∂w/∂x + η ∂w/∂y).
  - This is −(∂w/∂x ∂v/∂z − ∂w/∂y ∂u/∂z) + ∂w/∂x ∂w/∂y − ∂w/∂y ∂w/∂x, and the last two
    cancel: the standard tilting term.
- Inputs: xvort, yvort, ddx.w, ddy.w.
- Assumption: ξ, η are the file's (interpolated to scalar points), while ∂w/∂x is ours
  (centred on scalar points).
- Test: ξ = 0.01, w = 0.001 x → 0.1.
- Decision:

### 3.3 `ztend` ζ stretching + tilting

- Coded: 3.1 + 3.2.
- The label should not say "ζ tendency": advection, baroclinic (zero for ζ),
  diffusion and f terms are left out.
- Decision:

### 3.4 `okubo` Okubo–Weiss

- Coded: 10⁴ (s_n² + s_s² − ζ²), with s_n = ∂u/∂x − ∂v/∂y, s_s = ∂v/∂x + ∂u/∂y,
  ζ = ∂v/∂x − ∂u/∂y from the winds (not the file's zvort).
- Reference: Okubo (1970), Weiss (1991). Some authors use a ¼ factor or the opposite
  sign: here strain-dominated > 0, rotation-dominated < 0.
- Inputs: u, v (derivatives).
- Test: solid rotation u = −Ω y, v = Ω x → −10⁴ (2Ω)². Pure strain u = a x, v = −a y →
  10⁴ (2a)².
- Decision:

---

## 4. Column fields and sounding parameters (2D)

Layer handling (all of them): the model levels whose cells (between zf faces) reach into
the layer, each weighted by its thickness inside it (`column_levels`; on WoFS, each
column's own heights, `column_levels_3d`). Heights are AGL. The UH check (F1) shows this
matches CM1's own layer handling exactly.

### 4.1 `uh25`, `uh01` Updraft helicity (m²/s²)

- Coded: Σ dz w ζ over 2–5 km / 0–1 km. Every point counts (F1).
- Reference: Kain et al. (2008).
- Inputs: w, zvort.
- Assumptions to confirm: count only w > 0 and ζ > 0 (CM1 does; check WRF's `UH` once
  WoFS has ζ, §8). 0–1 km over 0–1 km, not 0–3 km.
- Test: w = 10, ζ = 0.01 everywhere → uh25 = 300, uh01 = 100. With w < 0 in the layer →
  0 (if F1 is taken).
- Decision:

### 4.2 `zvmax01`, `wmax` Layer maxima

- Coded: max of ζ over 0–1 km, max of w over the whole column.
- Inputs: zvort / w.
- Assumption: "0–1 km" includes the level whose cell straddles 1 km, even when its
  centre is above 1 km. With CM1's ~100 m low levels that is up to ~1.05 km.
- Test: ζ rising linearly with height → the value at the highest such level.
- Decision:

### 4.3 `shear0250 … shear06` Bulk shear (m/s)

- Coded: |V(top) − V(lowest model level)|, with V(top) linearly interpolated in z.
  Ground-relative winds (the motion cancels).
- Inputs: u, v.
- Assumptions:
  - From the lowest model level (CM1 ~50 m, WoFS ~25 m AGL), not 10 m. On WoFS, U10 and
    V10 exist and could be used.
  - Layers 0–250 m, 0–500 m, 0–1 km, 0–3 km, 0–6 km.
- Test: u = 0.005 z (m) → shear06 = 30 (minus the lowest level's offset).
- Decision:

### 4.4 `srh0250 … srh03` Storm-relative helicity (m²/s²)

- Coded: Σ [(u_{k+1} − cx)(v_k − cy) − (u_k − cx)(v_{k+1} − cy)], from the lowest model
  level to the top. The top value is interpolated.
- Reference: Davies-Jones et al. (1990); the same discrete form as SHARPpy and MetPy.
- Inputs: u, v, storm motion (F6).
- Assumptions: from the lowest model level, not the ground; storm motion as F6.
- Test: a wind turning clockwise on a circle of radius R around the storm motion → R²
  times the angle turned.
- Decision:

### 4.5 `sbcape mlcape mucape`, `…cin`, `…lcl` (J/kg, m AGL)

- Coded: `thermo._column_parcel`, which is the same as the sounding panel's.
  - Parcels:
    - SB: the lowest model level.
    - ML: the pressure-weighted mean θ and qv of the lowest 100 hPa, lifted from the
      lowest level.
    - MU: the level of max θe in the lowest 300 hPa.
  - LCL: Bolton (1980) eq. 15 (from Td), then dry adiabatic to the LCL.
  - Above the LCL: pseudoadiabatic (RK4 in ln p). dT/dlnp = (Rd T + Lv rs) / (cp + Lv² rs ε / (Rd T²)).
  - B = g (Tv,parcel − Tv,env) / Tv,env.
    - Tv,parcel uses rs above the LCL.
    - Tv,env uses qv only.
  - B is put on a 10 m grid.
    - LFC: the start of the first positive run above the LCL.
    - EL: the end of the last positive run.
  - CAPE: the **positive** area from LFC to EL. Negative pockets in between are not
    subtracted.
  - CIN: the negative area from the parcel's level to the LFC, below the LCL too.
- Inputs: pres, theta, qv.
- Assumptions to confirm:
  1. Pseudoadiabatic, liquid only (no ice latent heat, no freezing), Lv constant
     (2.501e6).
  2. Virtual-temperature correction, but no condensate loading, in the parcel or in the
     environment.
  3. CAPE ignores negative areas between LFC and EL (SPC/SHARPpy subtract them).
  4. ML: 100 hPa, θ and qv mixed. CM1's own `cape` uses a 500 m mixed layer (audit).
  5. MU: searched in the lowest 300 hPa.
  6. Computed on every `column_stride(run)`-th column, then filled.
- Test: compare with MetPy (`parcel_profile`, `cape_cin`, `lcl`) on a Weisman–Klemp
  sounding. That also checks the virtual-temperature choices.
- Decision:

### 4.6 `stp` Significant tornado parameter (fixed layer)

- Coded: (sbCAPE/1500) · clip((2000 − sbLCL)/1000, 0, 1) · (SRH₀₋₁/150) · S.
  - S = 0 for BWD₀₋₆ < 12.5 m/s, else min(BWD₀₋₆, 30)/20.
- Reference: Thompson et al. (2003), the fixed-layer version (SPC's), without a CIN term.
- Inputs: pres, theta, qv, u, v, storm motion.
- Assumptions: fixed layers (not effective); SRH with F6's motion.
- Test: CAPE 1500, LCL 500, SRH 150, BWD 20 → 1. BWD 10 → 0.
- Decision:

### 4.7 `scp` Supercell composite parameter (fixed layer)

- Coded: (muCAPE/1000) · (SRH₀₋₃/50) · S · C.
  - S = 0 for BWD₀₋₆ < 10, else min(BWD, 20)/20.
  - C = 1 for muCIN > −40, else −40/muCIN.
- Reference: Thompson et al. (2004), with the CIN term of SPC's later version. It uses
  **0–3 km SRH and 0–6 km shear** in place of the effective layer and effective bulk
  shear.
- Assumption: the fixed layers stand in for the effective ones. The label says "fixed
  layer".
- Test: CAPE 1000, SRH 50, BWD 20, CIN 0 → 1. CIN −80 → 0.5.
- Decision:

---

## 5. Pressure decomposition (CM1)

Source: `pdecomp/cm1_pdecomp.py`, CM1's method (Bobby chose it on 2026-11-18;
`docs-dev/pdecomp-cm1-port.md`). Listed for CM1 runs whose files hold the parts, or which
can compute them.

### 5.1 The equation (all parts)

- cp [H ∇h²π + ∂z(Hf ∂zπ)] = ρ0 (∂x Tu + ∂y Tv) + ∂z(ρf Tw)
  - H = ρ0 θv0, Hf = ρf avg(θv0), on CM1's staggered grid.
  - FFT (periodic) or cosine transform horizontally, tridiagonal vertically.
- p_x (Pa) = p00 (π0 + π_x)^(cp/Rd) − p00 π0^(cp/Rd).
- Mean: each part's top-level mean is 0. p_b's carries the model's π′ mean there.

| part | forcing T | accelerations |
|---|---|---|
| b | (0, 0, B at w levels), B = g [θ′/θ0 + (Rv/Rd − 1)(qv − qv0) − Σ q_cond] | acc_b = B + pgrad_b |
| l | (−w dU0/dz, −w dV0/dz, 0), one copy | acc_l = pgrad_l |
| nl | −(u·∇)u′, u′ = u − U0, CM1's advection (WENO5 / 5th order) | acc_nl = pgrad_nl |
| c | (f v, −f u, 0) | acc_c = pgrad_c |

- pgrad_x = −cp θv0 ∂π_x/∂z at w levels, averaged to scalar levels. It does not depend on
  π's constant.
- Sums: `p_dyn` = p_l + p_nl + p_c; `acc_dyn` = acc_l + acc_nl + acc_c; `acc_tot` =
  acc_b + acc_dyn.

Assumptions to confirm:
1. **qc0 = qi0 = 0** (CM1 does not write them).
2. Condensate in B: qc qr qi qs qg qh qhl qi1 qi2 qi3, whichever are present (F2).
3. The base state is the file's th0, qv0, prs0, pi0, u0, v0. Without it, the first
   output's horizontal mean, which includes any initial bubble.
4. Without staggered winds (`output_u/v/w`), they are rebuilt from uinterp…, an
   approximation. The info note says so.
5. Uniform horizontal grid only; no terrain.
6. "Linear" is CM1's one copy. The other copy is in nl (port doc §3.1).
7. `acc_tot` leaves out everything else in w's equation: turbulence, damping, the
   compressible part. The 2026-11-18 comparison: CM1's four parts reproduce the model's
   p′ to 3% (box).

### 5.2 Fields

| Field | Coded | Decision |
|-------|-------|----------|
| `p_b` `p_l` `p_nl` `p_c` (Pa) | as 5.1 | |
| `acc_b` (m/s²) | B + pgrad_b: the net upward acceleration from buoyancy | |
| `acc_l` `acc_nl` `acc_c` (m/s²) | pgrad of each | |
| `p_dyn`, `acc_dyn`, `acc_tot` | sums, with Coriolis | |

Test (one for all): a horizontally uniform B → acc_b ≈ 0 (already a scratch self-check,
to 0.1% of B). A Gaussian B bubble in a periodic box → acc_b against the analytic
Poisson solution. U0 = a z with w = sin… → p_l against −2ρ0 a ∂w/∂x · ½ (one copy).

### 5.3 The bands above ~12 km (F7)

Seen in both methods on rm_tor_125m, cm1out_000034: thin horizontal bands in the
accelerations above ~12 km, where the vertical stretching ends. Not explained yet.
Possible causes, to test in this order:

1. **The vertical difference where the spacing changes.** Averaging w-level pgrad to
   scalar levels with ½, ½ is exact, because CM1's zh is midway between its zf faces.
   But going the other way is not centred: a w level is not midway between the two
   scalar levels around it. So ∂π/∂z = (π_k − π_{k−1}) / (zh_k − zh_{k−1}) is only
   first-order accurate at zf_k wherever dz changes from level to level. The same holds
   for the c1/c2 interpolation of B and θv0. A sharp end to the stretching would put
   that error in a few levels. Check: dz against k for this run; are the bands at the
   levels where it kinks? Plot pgrad_w itself, before averaging.
2. **B (scalar levels) plus pgrad (averaged from w levels).** If B and pgrad nearly
   cancel aloft, a half-level offset between them leaves a residual that alternates
   level by level. Check: horizontal-mean acc_b profile, B profile and pgrad_b profile
   against z, and whether the bands alternate in sign every level.
3. **Base state at the tropopause.** A kink in θ0 or ρ0 near 12 km would put the bands
   in the forcing, not the numerics. Check: does dθv0/dz jump at the level where the
   bands start, and does that coincide with the stretching change?
4. **CM1 itself.** If CM1's own `pgradb` (written with `output_pdcomp`) shows them, the
   port is faithful and they are CM1's.

All of these need one decomposed time of a real run (~2 min, 4 CPUs, ~35 GB): a batch
job. I'll write the script and show you the `qsub` before anything runs.

- Decision (how to proceed):

---

## 6. Derivatives `ddx.X ddy.X ddz.X gradh.X`

- Coded:
  - Units per metre (audit, step 1).
  - ∂/∂x, ∂/∂y: np.gradient on the real x, y (km → m). Centred, second-order on a
    stretched grid; one-sided at the edges.
  - ∂/∂z: the same three-point form on the column's own heights (each column's on WoFS).
  - |∇h| = hypot(∂/∂x, ∂/∂y).
- Applies to every listed field, the derived ones included. ∂/∂z only for 3D fields.
- Assumptions to confirm:
  1. ∂/∂z on WoFS is along the column at fixed (x, y). That is the true ∂/∂z, because
     the columns are vertical.
  2. ∂/∂x, ∂/∂y on WoFS: F5 (constant height on height maps, along the model level
     elsewhere; no map factor).
  3. The derivative of a derived field is the derivative of the field, not a field
     built from derivatives of its inputs.
  4. Edges are one-sided (first order). CM1's open boundaries are not special.
- Test: a = 2x + 3y + 4z on a stretched grid → 2, 3, 4 per km → 0.002, 0.003, 0.004 per m,
  exactly, edges included. |∇h| = 0.0036.
- Decision:

---

## 7. Computed by the WoFS reader (not `fields.py`, but equations too)

| Field | Coded | Assumptions | Decision |
|-------|-------|-------------|----------|
| `THETA` | T + 300 | WRF's T is θ − 300 (checked in step 1) | |
| `PRES` | P + PB | | |
| `zmsl` | (PH + PHB)/g on w levels, averaged ½, ½ to mass levels | g = 9.81 (WRF's). Mass levels are midway in η, not in height; the linear average is the usual approximation (wrf-python does the same) | |
| `zagl` | zmsl − HGT | | |
| `THETA0 PRES0 QVAPOR0 U0 V0` | the member's own 3D field at its first time | so θ′, p′, B are changes since then (A5) | |
| U, V, W on mass points | ½, ½ average of the staggered neighbours | the same as CM1's uinterp… | |

---

## 8. Proposed new derived fields for WoFS (step 1 asked for these)

WRF writes no ξ, η, ζ (REL_VORT went to Other: it does not match the winds at analysis
times). Computing them from the winds turns on, for WoFS:
- `hvort` (needs ξ, η);
- `zstretch`, `ztilt`, `ztend`;
- `uh25`, `uh01`, `zvmax01`;
- later `wstream`, `wcross` (once WoFS has a storm motion).

- Proposed:
  - ζ = ∂v/∂x − ∂u/∂y
  - ξ = ∂w/∂y − ∂v/∂z
  - η = ∂u/∂z − ∂w/∂x

  These would be derived fields that play the `xvort`, `yvort`, `zvort` roles for a data
  type whose files lack them. All on mass points, from the destaggered U, V, W.
- Choice A (simple): ∂/∂x, ∂/∂y along the model levels. Error ∝ the level slope:
  over the WoFS plains domains the slope is small near the ground, and it shrinks with
  height.
- Choice B (proposed): with the slope correction of F5. For example
  ∂v/∂x|z = ∂v/∂x|η − (∂z/∂x|η) ∂v/∂z, using zmsl.
- Units 1/s. Same display as CM1's.
- Check before confirming:
  - ζ against REL_VORT at a non-analysis time (if any file has one).
  - `uh25` against WRF's `UH` (2–5 km). That also settles whether WRF counts only
    w > 0, ζ > 0 (F1).
- Test: u = −Ω y, v = Ω x, w = 0 → ζ = 2Ω, ξ = η = 0. Then w = a y → ξ = a. On tilted
  levels (choice B), a field varying only in z → ∂/∂x|z = 0.
- Decision (A, B, or not for WoFS):

---

## Summary of what step 3 would change (if every proposal is taken)

| Change | Moves CM1 image baselines? |
|---|---|
| F1 UH positive-only | only if a baseline draws `uh25`/`uh01` (to check) |
| F2 `buoy` in CM1's form | small change wherever `buoy`, `bgen_*` are drawn (to check) |
| F3 real spacing in `hdiv`, `bgen_*` | no (the demo grid is uniform) |
| F4 stretching label (or form) | label only, or small change in `zstretch` |
| F5 slope correction | no (CM1 has no terrain); WoFS only |
| F8 θe clip | no (no supersaturation in the demo, to check) |
| §8 WoFS ζ, ξ, η | WoFS only: new fields |

Before step 3, I'll grep `tests/baseline/` specs for the fields concerned and give the
exact list.
