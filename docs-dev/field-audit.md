# Phase 2b, step 1: field audit (CM1 and WoFS)

Status: **decided 2026-11-18 (Bobby's notes, below), catalogs updated.** Rows not named
in the notes take the proposal. The tables further down are the sheet as prepared.

## Decisions (2026-11-18)

**Three tiers, not two.** Besides the main lists, an **Other** tier: still offered, but
out of the way. **Hidden** = static and internal fields, listed only with a new setting
`show_hidden_fields` (Settings, off by default), which replaces "hide unless in the
files" (A1/A2). Code: `Catalog(other=, other_groups=, other_if=, hidden=,
unknown_hidden=)`, `Catalog.tier`, `FieldDef.tier`, `fields.group_options` (groups "Derived · <group>", "Other · <group>", "Hidden ·
<group>" after the plain ones). The field boxes are `viewer.fieldmenu.FieldSelect`
(Bobby OK'd the design 2026-11-18): a button opening the sections, each showing its
fields on hover, with Derived / Other / Hidden entries opening their own sections, and a
search box. It keeps a Select's interface; parcel colour lists and run lists stay
Selects.

CM1:
- Other: staggered `u v w` (only when `uinterp vinterp winterp` are there), `pi`, the
  Turbulence group (`tke kmh kmv khh khv` ...), the Budgets group, `cref`, `rain rain2`,
  the swaths `sws svs sps srs sgs sus shs` (+ `*2`).
- `cape cin lcl lfc`: CM1 lifts a **500 m mixed-layer** parcel (getcape source 3,
  ml_depth 500 m, pseudoadiabatic liquid only; r19.5 and r21.1), labelled "MLCAPE (CM1's,
  500 m mixed layer)" etc. Ours (`mlcape`) mixes the lowest 100 hPa: kept, both listed.
- `buoy` vs `acc_b`: `buoy` is the buoyancy B itself (θρ′ form, with loading); `acc_b` is
  B minus the vertical gradient of the pressure B induces (−cp θv0 ∂π_b/∂z), i.e. the
  net upward acceleration from buoyancy. Both kept.
- `qcloud` = qc + qi (cloud water + cloud ice); the files' `qc` is cloud water only.
  Kept.
- New layers: `srh0250`, `srh0500` (0–250 m, 0–500 m), `shear0250`, `shear0500`,
  `shear03`.

WoFS:
- `THETA` = T + 300 K is right: WRF's T is "perturbation potential temperature
  (theta-t0)" in K (t0 = 300 K), not °C (checked: T + 300 ≈ 309 K near the ground, TH2
  ≈ 309 K). `PRES` = P ("perturbation pressure", Pa) + PB ("BASE STATE PRESSURE", Pa).
- (2026-11-19, step 2: the dataset's creator confirmed REL_VORT is ζ; it will be mapped to
  `zvort` in step 3. `derived-fields.md`, "Bobby's review".)
- `REL_VORT` ("RELATIVE VORTICITY", s-1, mass points; not absolute, no f offset) is
  **not** mapped to ζ: against ζ = ∂v/∂x − ∂u/∂y from the file's own U, V it
  correlates only 0.80–0.85 point by point (0.96–0.98 after 9 km smoothing) and its
  peaks are larger, at the 23:00 and 23:03 outputs. Likely cause, not confirmed: every
  file here is written at an analysis time, after DART updated U and V but not this
  diagnostic. It goes under Other. Proposal for step 2: ζ (and ξ, η) computed from the
  winds for WoFS, which turns on the ζ tendencies and UH there.
- Other: `*_DIABATIC`, the 3D rows QV/QC_DIABATIC to PH PHB WW (number concentrations,
  volumes, aerosol, CLDFRA, NONINDUC*, P_HYD, PH PHB WW), `REFL_10CM_1KM/4KM`,
  `REFD_MAX REFDM10C_MAX`, `UP_HELI_MAX*/MIN*`, `REL_VORT REL_VORT_MAX REL_VORT_MAX01`,
  `W_UP_MAX W_DN_MAX W_MEAN`, `WSPD10MAX WSPD80MAX`, `GRPL_MAX` and the 9 rows after it
  (hail, lightning, T2/TH2/Q2, PSFC, U10/V10/WSPD10/80, RAINNC..., PREC_ACC..., LWP IWP,
  MAXCLDFRA), the PBLH row to the end of C2 (and QFX, which the sheet missed).
- Main: THETA PRES QVAPOR, the hydrometeors, U V W, REFL_10CM, COMPOSITE_REFL_10CM (now
  the `cref` role), UH UH16 UH02 UH03, HGT, zagl zmsl, the base state.
- C3: hidden. WRF fields the catalog does not name: hidden (proposal).
- Derived for WoFS: ζ tendencies wait for the ζ equation (step 2); ξ, η, hvort, wstream,
  wcross computed from the winds (step 2 entry); SRH, STP, SCP once WoFS has a storm
  motion (Phase 3). (`wstream wcross` were listed twice in C4: a slip.) No pressure
  decomposition for WoFS.

Derivatives: every field gets ∂/∂x, ∂/∂y (and ∂/∂z when 3D), column fields too; ∂/∂z
along the model levels; **units per metre** (m/s → 1/s, K → K/m), done.

Bugs E1–E4: fixed (E1, E2 with the tables; E3 `Catalog.resolved`; E4 dewpoint now YlGnBu).

The lists come from what the readers produce today (`Fields(run).defs`):

- CM1: `demo_data/supercell` (82 fields: 41 from the files, 41 derived).
- WoFS: `/glade/derecho/scratch/rasaba/test/bnrhf_ctrl` member 1 (252 fields: 224 from
  the files, 28 derived).

CM1 fields that are in the catalog but not in the demo (staggered `u v w`, `pi`, `rho`,
the `*2` translated swaths, pressure decomposition) are listed too.

Columns: **now** = label · units · colormap · range · diverging (`div`), as the viewer
shows it today. `—` = no range (data limits). "file" = the reader's long name and units,
used because the catalog has no entry.

Derived-field **equations** are not covered here; they are step 2
(`docs-dev/derived-fields.md`). This step decides only whether a derived field is
listed, and how it looks.

---

## A. Policy questions (answer these first; they decide most rows)

| # | Question | Proposal | Decision |
|---|----------|----------|----------|
| A1 | What does "hidden" mean? | Gone from every field list, the figure editor and exports. A saved figure that uses a hidden field still draws it (no broken figures). | |
| A2 | Should a "show every field in the files" setting exist for hidden fields? | Yes, off by default (one setting, `show_all_fields`). A hidden WoFS field is otherwise unreachable. | |
| A3 | Base-state fields: units and colors | Same as the full field (`prs0` in hPa like `prs`, `th0` on the θ colormap, `qv0` like `qv`, `u0 v0` diverging), label "Base-state …". Today they are Pa, viridis and the file's long name. | |
| A4 | WoFS field labels | Clean labels in the catalog for every field kept (today most are WRF's ALL-CAPS descriptions), units written as `m/s`, `m²/s²` (not `m s-1`). | |
| A5 | WoFS base state "(first time)" | Keep the fields; keep "(first time)" in the label, so θ′, p′ and buoyancy read as "change since the first time" for WoFS. | |
| A6 | Where `zagl` / `zmsl` go | A new group "Heights" (they are in **Microphysics** today: a bug, nothing catches them). km, `cividis`. | |

---

## B. CM1

### B1. 3D fields in the files

| Field | now | Proposal | Decision |
|-------|-----|----------|----------|
| `dbz` | Reflectivity · dBZ · reflectivity · 0–75 | keep | |
| `uinterp` | u (grid-relative) · m/s · RdBu_r · ±30 · div | keep | |
| `vinterp` | v (grid-relative) · m/s · RdBu_r · ±30 · div | keep | |
| `winterp` | Vertical velocity · m/s · RdBu_r · ±20 · div | keep | |
| `u` `v` `w` (staggered) | "… (staggered)", as above | show only when the interpolated one is missing (a run without `output_uinterp`); otherwise hide. Today both show. Note: a run with only staggered `w` has no vertical-velocity role at all today (it is `also`, never `name`) — make the staggered one the role in that case. | |
| `xvort` `yvort` `zvort` | … · 1/s · RdBu_r · ±0.05 · div | keep | |
| `th` | Potential temperature · K · cmo.thermal · — | keep | |
| `prs` | Pressure · hPa · viridis · — | keep | |
| `pi` | Exner function · (none) · viridis · — | keep | |
| `rho` | Density · kg/m³ · viridis · — | keep | |
| `qv` | Water vapor mixing ratio · g/kg · YlGnBu · 0–20 | keep | |
| `qc` `qr` `qi` `qs` `qg` `qhl` | g/kg, ice/rain/amp maps, 0–2 … 0–5 | keep | |
| `tke` | Subgrid TKE · m²/s² · magma · 0–20 | keep | |
| `kmh` `kmv` `khh` `khv` | file (no catalog entry) | add labels: "Eddy viscosity (horizontal/vertical)", "Eddy diffusivity (horizontal/vertical)", m²/s, magma, — | |
| `b_*` budgets | file, group Budgets | keep as the file names them | |

### B2. Base state (files)

| Field | now | Proposal (A3) | Decision |
|-------|-----|----------|----------|
| `th0` | file · K · viridis | Base-state θ · K · cmo.thermal | |
| `prs0` | file · **Pa** · viridis | Base-state pressure · hPa · viridis | |
| `qv0` | file · g/kg · viridis | Base-state qv · g/kg · YlGnBu · 0–20 | |
| `u0` `v0` | file · m/s · viridis | Base-state u/v · m/s · RdBu_r · ±30 · div | |
| `pi0` | file · nondimensional · viridis | Base-state Exner function · (none) · viridis | |
| `rho0` | (not in demo) | Base-state density · kg/m³ · viridis | |

### B3. 2D fields in the files

| Field | now | Proposal | Decision |
|-------|-----|----------|----------|
| `cref` | Composite reflectivity · dBZ · 0–75 | keep | |
| `rain` / `rain2` | Accumulated rain (translated) · cm · cmo.rain · 0–5 | keep | |
| `sws` `svs` `sps` `srs` `sgs` `sus` `shs` (+ `*2`) | swath maxima/minima, catalog entries | keep | |
| `prate` | file · **kg/m²/s** · viridis | Surface precipitation rate · mm/h (×3600) · cmo.rain · 0–100 | |
| `uh` | file "integrated (2-5 km) AGL) updraft helicity" · m2/s2 | Updraft helicity 2–5 km (CM1's) · m²/s² · magma · 0–300. Overlaps derived `uh25`; keep both? | |
| `cpc` | file "cold pool intensity C" · m/s | Cold pool intensity C · m/s · viridis · 0–30 | |
| `cph` | file "cold pool depth h" · m AGL | Cold pool depth · m AGL · cividis · 0–3000 | |
| `psfc` | file · **Pa** | Surface pressure · hPa · viridis | |
| `pwat` | file · **m** | Precipitable water · mm (×1000) · YlGnBu · 0–60 | |
| `cape` `cin` `lcl` `lfc` | file · J/kg, m · viridis | CAPE · magma · 0–4000; CIN · cmo.ice · −300–0; LCL/LFC · m · cividis · 0–3000/0–4000. Which parcel does CM1 lift? They overlap derived `sbcape`/`mlcape`/`mucape`: keep both, or hide CM1's? | |

### B4. Pressure decomposition

`p_b p_l p_nl acc_b acc_l acc_nl` (+ derived `p_dyn acc_dyn acc_tot`). Listed when the
files have them, **or** when they can be computed: CM1 run with `th qv pi rho prs` and
`w`/`winterp`, and the solver present (`pdecomp.can_compute`). The demo lacks `pi` and
`rho`, so it lists none.

| Question | Proposal | Decision |
|----------|----------|----------|
| List them before they are computed? | Yes (as today), with "(computed on request)" added to the label until a time has them. | |
| Labels/colors | keep (PuOr_r for p′, RdBu_r for accelerations, data range, div) | |

### B5. Derived fields listed for CM1 (look only; equations in step 2)

| Field | now | Proposal | Decision |
|-------|-----|----------|----------|
| `thpert` | θ′ · K · RdBu_r · ±6 · div | keep | |
| `prspert` | p′ · hPa · PuOr_r · ±4 · div | keep | |
| `buoy` | Buoyancy (θρ′, with loading) · m/s² · RdBu_r · ±0.3 · div | keep | |
| `bgen_x` `bgen_y` | Baroclinic generation · 10⁻⁴ s⁻² · ±2 · div | keep | |
| `thrho` / `thrhopert` | θρ · K · cmo.thermal / θρ′ ±6 div | keep | |
| `thetae` | θe · K · Spectral_r · — | keep | |
| `tempc` | Temperature · °C · cmo.thermal | keep | |
| `dewc` | Dewpoint · °C · **BrBG** | cmo.haline or YlGnBu (BrBG is diverging, dewpoint is not centred on 0) | |
| `rh` | RH (liquid) · % · YlGnBu · 0–100 | keep | |
| `wspd` | Wind speed (ground-relative) · m/s · turbo · 0–40 | keep | |
| `hdiv` | Horizontal divergence · 10⁻³ s⁻¹ · PuOr_r · ±10 · div | keep | |
| `hvort` | Horizontal vorticity magnitude · 1/s · magma · 0–0.1 | keep | |
| `wstream` `wcross` | Streamwise/crosswise vorticity · 1/s · ±0.05 · div (storm motion) | keep | |
| `qcloud` `qprecip` | Cloud condensate / Precipitation · g/kg | keep | |
| `zstretch` `ztilt` `ztend` `okubo` | ζ tendencies · 10⁻⁴ s⁻² · ±5 · div | keep | |
| `uh25` `uh01` `zvmax01` `wmax` | column fields | keep | |
| `shear01` `shear06` | Bulk shear · m/s · viridis | keep | |
| `srh01` `srh03` | SRH · m²/s² · RdBu_r · ±300/±500 · div | keep | |
| `sb/ml/mu cape cin lcl` | magma / cmo.ice / cividis | keep | |
| `stp` `scp` | STP/SCP (fixed layer) · RdBu_r · ±6/±20 · div | keep | |

---

## C. WoFS

### C1. 3D fields

| Field | now | Proposal | Decision |
|-------|-----|----------|----------|
| `THETA` (= T + 300) | Potential temperature · K · cmo.thermal | keep | |
| `PRES` (= P + PB) | Pressure · hPa · viridis | keep | |
| `QVAPOR`, `QCLOUD QRAIN QICE QSNOW QGRAUP QHAIL` | as CM1's | keep | |
| `U V W` (destaggered) | as CM1's | keep | |
| `REFL_10CM` | Reflectivity · dBZ | keep | |
| `THETA0 PRES0 QVAPOR0 U0 V0` | file "base-state … (first time)" · PRES0 in **Pa** · viridis | per A3 + A5 | |
| `zmsl` `zagl` | height above sea level/ground · m · **group Microphysics** | per A6: group Heights, km, cividis | |
| `REL_VORT` | "RELATIVE VORTICITY" · s-1 · Other model fields | **map it to the `zvort` role** (label Vertical vorticity, 1/s, RdBu_r, ±0.05, div). That turns on `zstretch ztilt ztend uh25 uh01 zvmax01` for WoFS. Check first that it is on mass points and is ζ (not absolute). | |
| `H_DIABATIC` | MICROPHYSICS LATENT HEATING · K s-1 | Latent heating (microphysics) · K/h (×3600) · RdBu_r · ±50 · div | |
| `QV_DIABATIC` `QC_DIABATIC` | qv / qc tendency · g g-1 s-1 | hide (or keep, g/kg/h, div) | |
| `QNDROP QNRAIN QNICE QNSNOW QNGRAUPEL QNHAIL QNCCN` | number concentrations · kg-1 | keep in a group "Microphysics (number)", log-friendly cmap `magma`, label cleaned | |
| `QVGRAUPEL QVHAIL` | particle volume · m³/kg | keep in "Microphysics (number)" | |
| `QNWFA QNIFA` | aerosol number | hide | |
| `CLDFRA` | CLOUD FRACTION | Cloud fraction · (0–1) · Greys_r · 0–1 | |
| `NONINDUC NONINDUCN NONINDUCP` | noninductive charging · C m-3 | keep, group "Electrification", div for NONINDUC | |
| `P_HYD` | hydrostatic pressure · Pa | hide | |
| `PH PHB WW` | geopotential, eta-dot | hide (internal; heights come as `zagl`/`zmsl`) | |

### C2. 2D fields to keep (storm and surface diagnostics)

Proposal: keep these, with clean labels and units (A4).

| Fields | Proposed label · units · cmap · range | Decision |
|--------|---------------------------------------|----------|
| `COMPOSITE_REFL_10CM` | Composite reflectivity · dBZ · reflectivity · 0–75. **Map it to the `cref` role?** (Phase 2 left it unmapped.) | |
| `REFL_10CM_1KM` `REFL_10CM_4KM` | Reflectivity at 1 / 4 km AGL · dBZ · reflectivity · 0–75 | |
| `REFD_MAX` `REFDM10C_MAX` | Max reflectivity / at −10 °C (since last output) · dBZ | |
| `UH` `UH16` `UH02` `UH03` | Updraft helicity 2–5 / 1–6 / 0–2 / 0–3 km · m²/s² · magma · 0–300 | |
| `UP_HELI_MAX*` | Max UH (window) 2–5 / 1–6 / 0–2 / 0–3 km · m²/s² · magma · 0–300 | |
| `UP_HELI_MIN*` | Min UH (anticyclonic) · m²/s² · magma_r · −300–0 | |
| `REL_VORT_MAX` `REL_VORT_MAX01` | Max ζ 0–2 / 0–1 km · 1/s · magma · 0–0.05 | |
| `W_UP_MAX` `W_DN_MAX` `W_MEAN` | Max updraft / max downdraft / hourly mean w · m/s · turbo / RdBu_r | |
| `WSPD10MAX` `WSPD80MAX` | Max 10 m / 80 m wind speed · m/s · turbo · 0–40 (their U/V components: hide) | |
| `GRPL_MAX` | Max column graupel · kg/m² · cmo.amp | |
| `HAIL_MAXK1` `HAIL_MAX2D` `HAILCAST_DIAM_MAX` | Max hail diameter (surface / column / HAILCAST) · mm (×1000 for the first two) · cmo.amp · 0–75 | |
| `LTG1_MAX` `LTG2_MAX` `LTG3_MAX` `GLM_FED_AVG` `GLM_FED_MAX` | Lightning threat 1–3 / GLM FED proxy · flashes … · magma | |
| `T2` `TH2` `Q2` | 2 m temperature (°C) / θ (K) / qv (g/kg) | |
| `PSFC` | Surface pressure · hPa | |
| `U10` `V10` `WSPD10` `WSPD80` | 10 m u/v (div) / wind speed 10 m, 80 m | |
| `RAINNC` `SNOWNC` `GRAUPELNC` | Accumulated precipitation / snow+ice / graupel (grid scale) · mm · cmo.rain | |
| `PREC_ACC_NC` `SNOW_ACC_NC` `GRAUP_ACC_NC` (+ `…1`) | Precipitation / snow / graupel over the accumulation window · mm | |
| `LWP` `IWP` | Liquid / ice water path · g/m² | |
| `MAXCLDFRA` | Max cloud fraction · 0–1 | |
| `HGT` | Terrain height · m · terrain cmap | |
| `PBLH` `HFX` `LH` `UST` `TSK` `SST` `OLR` `SWDOWN` | PBL height, sensible/latent heat flux, u*, skin T, SST, OLR, downward SW | |
| `SR` | Frozen precipitation fraction · 0–1 | |
| `RSCGHIS_2D` (+ `N`, `P`) | Column noninductive charging · C/m² (group Electrification) | |

### C3. 2D fields to hide

Proposal: hide all of these (reachable only through A2's setting, if kept).

| Block | Fields | Decision |
|-------|--------|----------|
| Geography, static | `XLAT XLONG CLAT LU_INDEX VAR_SSO VAR TOPOSTDV TOPOSLPX TOPOSLPY SHDMAX SHDMIN SNOALB SLOPECAT SOILHGT SOILCAT VEGCAT IVGTYP ISLTYP LANDMASK LAKEMASK XLAND LAKE_DEPTH LAKEDEPTH2D MAPFAC_M MAPFAC_MX MAPFAC_MY F E SINALPHA COSALPHA ALBBCK EMISS TMN NEST_POS` | |
| Dynamics internals | `MU MUB MU0 PC PCB` | |
| Cumulus scheme (WoFS runs none) | `RAINC RAINCV PRATEC CUTOP CUBOT CUPPT PREC_ACC_C PREC_ACC_C1` | |
| Land surface, snow, lake | `SEAICE SFROFF UDROFF VEGFRA GRDFLX ACSNOW ACGRAUP ACRUNOFF ACSNOM SNOW SNOWH CANWAT RHOSNF SNOWFALLAC LAI SNOWDP2D H2OSNO2D SNL2D T_GRND2D SAVEDTKE12D SOILT1 SNOWC MAVAIL QVG QCG FLHC ZNT BR ZOL SST_INPUT` | |
| Radiation, aerosol | `COSZEN GSW GLW SWDDNI SWDDIF SWDDNIC SWDDIFC AOD5502D ANGEXP2D AERSSA2D AERASY2D TAOD5502D SWRADMEAN SWNORMMEAN ALBEDO ALBSOL ALBBCKSOL QNWFA2D QNN2D QNN2D_BASE` | |
| Time-step values and CI counters | `RAINNCV SNOWNCV GRAUPELNCV NCI_LTG NCA_LTG NCI_W NCA_W NCI_WQ NCA_WQ NCI_REFD NCA_REFD QR_MAX_CI QG_MAX_CI` | |
| Wind-max components | `WSPD10UMAX WSPD10VMAX WSPD80UMAX WSPD80VMAX` | |

A WRF field not named in the WoFS catalog (a different WoFS version's extra output):
proposal **hidden by default** for WoFS, so a new file version never floods the list.
CM1 keeps listing unknown file fields (its output is chosen by the user's namelist).
Decision: ______

### C4. Derived fields for WoFS

Listed today: `thpert prspert buoy bgen_x bgen_y thrho thrhopert thetae tempc dewc rh
wspd hdiv qcloud qprecip okubo wmax shear01 shear06 sb/ml/mu cape cin lcl`.

Missing, and why:

| Fields | Missing because | Proposal | Decision |
|--------|-----------------|----------|----------|
| `zstretch ztilt ztend uh25 uh01 zvmax01` | no `zvort` role | map `REL_VORT` (C1) | |
| `hvort` `wstream` `wcross` | no `xvort`/`yvort` in WRF files | compute ξ = ∂w/∂y − ∂v/∂z, η = ∂u/∂z − ∂w/∂x as derived fields on WoFS's terrain-following levels (needs a step-2 entry and a test), or leave them out for WoFS | |
| `srh01 srh03 stp scp wstream wcross` | storm-relative: `WoFSRun.storm_relative = False` | leave hidden until the storm-motion choice for WoFS (Phase 3 capabilities) | |
| `p_*` decomposition | CM1 only (`pdecomp.can_compute`) | leave CM1 only | |

---

## D. Derivatives (`ddz.X ddx.X ddy.X gradh.X`)

Today: offered for every listed field from a Derivative select (∂/∂z for 3D only), in
the field's units per km, colormap RdBu_r (div) or magma for |∇h|, starting range half
the field's per km.

| Question | Proposal | Decision |
|----------|----------|----------|
| Which fields get derivatives? | every listed continuous field; none for categorical or flag fields (none of those stay listed if C3 is taken) and none for the costly column fields (`*cape *cin *lcl stp scp`) | |
| ∂/∂z on WoFS | along the model levels today? Must be confirmed in step 2 (terrain-following levels: ∂/∂z at constant x, y needs the column's own heights) | |
| Units | per km as today (m/s → 10⁻³ s⁻¹) | |

---

## E. Found while preparing (bugs, to fix with the catalog update)

1. WoFS `zagl`/`zmsl` fall to the group "Microphysics" (`Catalog.group`'s last line).
2. Base-state pressure (`prs0`, `PRES0`) shows in Pa while full pressure shows in hPa,
   so `prs` and `prs0` can't share a colorbar.
3. A CM1 run with only staggered `u v w` has no wind roles (see B1).
4. `dewc` uses a diverging colormap (`BrBG`) but is not marked diverging.
