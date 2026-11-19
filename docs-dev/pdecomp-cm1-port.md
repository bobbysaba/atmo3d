# CM1's pressure decomposition, ported (Phase 2b side task, 2026-11-18)

Bobby's request: port CM1's own decomposition (`pdcomp.F`, `poiss.F`) into atmo3d,
compare it with today's method (`pdecomp_solver.py`), first checking that the output
files hold everything it needs.

- Code: `atmo3d/pdecomp/cm1_method.py` (not wired into the viewer yet).
- Comparison script: `tools/compare_pdecomp.py`.
- Nothing has run on real data yet: the comparison needs a batch node (see the end).

## 1. Does the output hold what CM1's method needs?

Checked on `rm_tor_125m/cm1out_000034.nc` (CM1 r19.5, 1280 × 1280 × 115, 125 m,
stretched z, open lateral boundaries, f = 8e-5, WENO5 momentum advection on the final
Runge–Kutta step: `advwenov = 2`, `weno_order = 5`).

| CM1 uses | in the file | notes |
|---|---|---|
| staggered u, v, w (`u3d, v3d, w3d`) | `u`, `v`, `w` | grid-relative, as CM1 holds them (`uinterp` is ground-relative) |
| base state th0, qv0, pi0, rho0, u0, v0 | `th0`, `qv0`, `pi0`, `prs0`, `u0`, `v0` | rho0 = prs0 / (Rd th0 pi0 (1 + qv0 Rv/Rd)), CM1's formula |
| qc0, qi0 (base-state cloud) | not written | taken as 0 (CM1 soundings are normally subsaturated) |
| th, qv, every condensate species | `th`, `qv`, `qc qr qi qs qg qhl` | |
| model pi' (mean pressure of p_b) | `pi`, `pi0` | |
| f (Coriolis) | `f_cor` | |
| grid (zh, zf, dx, dy) | `z`, `zf`, `xf`, `yf` | |
| advection scheme | `namelist.input` | `advwenov`, `weno_order`, `hadvordrv` |

**Yes, everything is there.** This needs `output_u/v/w = 1` (staggered winds) and
`output_basestate = 1`. Without the base state, the method falls back to the first
output, as `pdecomp_solver.py` does. Runs that only write `uinterp/vinterp/winterp`
cannot use CM1's advection stencils as written: an interpolated-wind version would only
approximate it.

Bonus: this file also has the momentum budgets (`ub_/vb_/wb_ hadv, vadv, hidiff,
vidiff`). Their sums are CM1's own advective tendency, so the script can check the
ported advection against the model itself (`--check-advection`).

## 2. What CM1 does, and what the port does

Each part solves the same anelastic equation for the Exner function as ours. In flux
form on CM1's grid:

    cp [ H ∇h²π + ∂z(Hf ∂zπ) ] = ρ0 (∂x Tu + ∂y Tv) + ∂z(ρf Tw)
    H = ρ0 θv0 at scalar levels,  Hf = ρf · avg(θv0) at w levels

| part | tendency T on the staggered grid |
|---|---|
| b | (0, 0, B at w levels), B = g [θ′/θ0 + (Rv/Rd − 1)(qv − qv0) − Σq_cond] |
| l | (−w dU0/dz, −w dV0/dz, 0): **one** copy of the linear term |
| nl | −(u·∇)u′ with u full and u′ = u − U0, using CM1's advection (WENO5 here), in advective form via flux form + u′∇·(ρ0u) |
| c | (f v, −f u, 0) |

The port follows CM1 line by line. It reuses atmo3d's FFT / cosine-transform +
tridiagonal solver, with CM1's coefficients set. Two pieces keep CM1's convention:
- **Mean pressure**: each part's top-level mean is set to 0. For p_b, it is set to the
  model's pi′ mean there.
- **Accelerations**: CM1's `pgrad*` form, −cp θv0 ∂π/∂z at w levels. The port averages
  it to scalar levels and adds B for the buoyancy part.

r19.5 and r21.1 have the same pdcomp/poiss/WENO math. r21.1 only adds
immersed-boundary arguments.

Self-checks on small synthetic grids (scratch, not tests):
- Uniform flow gives zero advection.
- Each direction and wind component matches −(u·∇)a to ~1e-6 relative.
- A horizontally uniform B gives zero net acceleration, to 0.1% of B.

Known gaps:
- **Lateral boundaries:** within ~3 points of an open boundary, CM1's inflow-flux rule and
  halo values are not redone (ghost points copy the edge). The script leaves 10 points
  out of its statistics.
- **Solver round-off:** our transform and tridiagonal solve stand in for CM1's own.

## 3. How it differs from atmo3d's method (what the comparison will show)

1. **Linear part: CM1 uses half of ours.** Ours forces with
   −2ρ0(dU0/dz ∂w/∂x + dV0/dz ∂w/∂y) (`LINEAR_FACTOR = 2`). CM1 uses one copy. The
   other copy sits in CM1's nonlinear part, because advecting u′ by the full wind
   includes U0·∇u′, and with anelastic continuity
   ∇·(ρ0 U0·∇u′) = ρ0(dU0/dz ∂w/∂x + dV0/dz ∂w/∂y). This settles the step 2 question
   from field-tables.md:
   - CM1's p_l is about ½ of ours.
   - CM1's (p_nl − p_l) matches our split.
   - CM1's p_l + p_nl is the same total.
   The script shows both ways (`linear` / `nonlinear` and `linear2` / `nonlinear2`).
2. **Nonlinear part: direct vs residual.** Ours is p′ − p_b − p_l. Besides advection, it
   therefore holds everything else in the model's pressure:
   - Coriolis (CM1 solves it separately);
   - turbulence and diffusion;
   - Rayleigh damping;
   - compressibility (this run is compressible, psolver = 3);
   - numerical effects.

   The `total` comparison shows how much of p′ CM1's four parts leave out.
3. **Buoyancy, small differences:**
   - θ0, qv0: the file's base state (CM1) vs the horizontal mean of the first output
     (ours, which includes any initial bubble).
   - Interpolation: B is moved to w levels and then multiplied by ρf (CM1), where ours
     interpolates ρ0B.
   - The condensate species are the same.
4. **Mean pressure:** CM1 fixes the top-level mean; ours removes the volume mean. Only a
   constant per part changes; the script removes volume means before comparing.

## 4. Found along the way: our accelerations depend on an arbitrary constant

`pdecomp_solver.post_process` converts each part to Pa with
p_x = p00(π0 + π_x)^(cp/Rd) − p00 π0^(cp/Rd), then takes −(1/ρ)∂p_x/∂z. Because π0
varies with height, this adds a term ∝ π_x · dπ0/dz to the acceleration. π_x is only
defined up to a constant (we remove its volume mean), so acc_b, acc_l and acc_nl shift
with that choice.

On a synthetic case with a horizontally uniform B, acc_b came out at ~8% of B instead
of ~0, from this term alone. The CM1 form −cp θv0 ∂π_x/∂z has no such term.

The script measures it on real data (`conversion_z*.png` and the end of `stats.txt`).
This is a **step 2 item** (derived-equation audit). The likely fix is to compute acc_*
in the CM1 form; p_* in Pa can stay as they are.

## 5. Cost

- Ours today: two solves, ~45–85 s on this grid.
- CM1's method: four solves (three when f = 0), plus WENO5 advection of three wind
  components in numpy.
- Rough estimate, to be measured: a few minutes with 8 threads, ~25–30 GB.
- The comparison script runs both methods plus the plots: allow ~60 GB and up to an
  hour.

## 6. Running the comparison

    python tools/compare_pdecomp.py RUN/cm1out_000034.nc --heights 1 3 --check-advection

- Defaults: `--first` is `RUN/cm1out_000001.nc` (base state for ours) and `--namelist`
  is `RUN/namelist.input`.
- Plot box: ±15 km around the strongest updraft at 3 km (`--box` to choose another).
- Ours is recomputed with today's `pdecomp_solver.py`. The `p_b` ... already in this
  file have no version attribute (an older script); `--ours file` uses them anyway.

What comes out (in `--out`):
- `stats.txt`: rms of each side and of the difference, correlation, slope and max
  difference, over the interior and over the box.
- For each comparison: 2 × 3 panel PNGs at each height plus a west–east section. Rows:
  pressure, vertical acceleration. Columns: atmo3d, CM1 method, difference.

## 7. Decisions for Bobby after the comparison

- Adopt CM1's method in the viewer (all four parts, CM1's split), keep ours, or offer
  both? If adopted, the field names and labels change (p_c / acc_c added, "linear"
  means one copy). That goes through the Phase 2b catalog review.
- Accelerations in the CM1 form (§4), for whichever method stays.

## 8. Results on rm_tor_125m cm1out_000034 (run 2026-11-18, 4 CPUs / 64 GB node)

CM1's method took just under 2 min. Figures and stats.txt are in the scratch folder
`pdecomp_compare/cm1out_000034`. Box = ±15 km around the main updraft; rms differences
are relative to atmo3d.

| comparison | p, box | acc, box | acc, interior |
|---|---|---|---|
| buoyancy | 17% (corr 0.986) | 2% | 3% |
| linear (CM1 / ours slope) | 0.49 | 0.50 | 0.50 |
| linear2 (2 × CM1) | 2% | 2% | 3% |
| nonlinear2 (CM1 nl − l + c vs our residual) | 16% (corr 0.985) | 5% | 8% |
| dynamic (l + nl) | 13% | 5% | 8% |
| total (CM1's 4 parts vs model p′) | 3% | 5% | 6% |

- The factor 2 is confirmed: CM1's linear part is half of ours, with the other half in its nl.
- Our residual p_nl is within ~5% (acceleration) of CM1's direct advection + Coriolis.
  Turbulence, compressibility, damping etc. are small in this storm.
- CM1's four parts reproduce the model's p′ to 3% (box).
- Pressure differences over the whole interior look larger (35–67%) because they are
  mostly horizontally uniform layer offsets. These come from the base-state profile
  (file th0 vs first-output mean) and mean handling. They do not touch the
  accelerations; see buoyancy_xz.png.
- §4 is confirmed on real data. Our acc_* as written differ from the constant-free form
  by 17% / 26% / 10% rms (b / l / nl) at 1 km in the box, and 37–58% over the interior.
- Both methods show thin horizontal bands in the accelerations above ~12 km (where the
  vertical stretching ends). This is to look at in step 2.
- The advection check (`--check-advection`) has not been run yet.

## 9. Decided and done (2026-11-18)

- Bobby chose **CM1's method** for the viewer, and the acceleration fix.
- `atmo3d/pdecomp/cm1_method.py` became `cm1_pdecomp.py`: self-contained, and the
  viewer's built-in decomposition.
  - Fields: p_b, p_l, p_nl, p_c and acc_b, acc_l, acc_nl, acc_c.
  - The sums p_dyn, acc_dyn and acc_tot include the Coriolis part.
  - Without staggered winds it interpolates them back from uinterp…; without `pi`, it
    uses `prs`.
- File values count as current only with `pdecomp_version` starting "cm1_pdecomp".
  Older ones show with a note ("older method"); the sums needing p_c ask for a recompute.
- A `pdecomp_script` with the old interface still works (six fields).
- `pdecomp_solver.py` accelerations now use −cp θv0 ∂π/∂z (`vertical_pgf`).
- Stand-alone copy, kept identical: `/glade/work/rasaba/cm1_pdecomp/` (`cm1_pdecomp.py`,
  `run_pdecomp.py` driver, README).
- Bobby's own atmo3d settings point `pdecomp_script` at
  `phd_scripts/pdecomp_new_fixed_mp.py`. The viewer uses that until the setting is
  cleared.
