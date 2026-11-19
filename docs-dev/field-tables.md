# Field tables (Phase 2b, step 1, after Bobby's answers to A1–A6)

Written 2026-11-18, before Bobby's row-by-row review of `field-audit.md` came back.

## Rule (A1, A2)

A field is listed when it is in the run's files, or when it is derived (with confirmed
equations, step 4) and its inputs are in the files; plus derivatives, the pressure
decomposition atmo3d can compute, and the other exceptions in `field-audit.md`.
Nothing a file holds is hidden.

## What changed

- `atmo3d/core/cm1_outputs.py`: every field CM1 can write, 394 entries, from
  `src/writeout.F` (fields) and `src/param.F` (microphysics `qname`) of r19.5 and r21.1
  (the builds in `~/cm1_builds`; `_mod`, `_demo`, `_test` and `cm1_tn_test` write the
  same as their base version). Each entry: label, display units, scale, colormap,
  range, diverging, group; the namelist switch is noted by block. Numbered fields
  (`pt1..`, `out2d1..`, 3D `out1..`) come from `describe()`.
- `atmo3d/core/wofs_outputs.py`: every field of the WoFS files (224), WRF names kept,
  labels rewritten (A4), units plain (`m/s`, `W/m²`, hPa for pressures, g/kg for mixing
  ratios, mm for hail diameter).
- `core/catalog.py`: a natives entry may carry its group; `Catalog.look()` gives a
  field's look (table, then `describe`, then `tidy()` from the file's long name and
  units, for a field a newer CM1/WRF writes); a field no table places goes to "Other
  model fields" (was "Microphysics": how `zagl` ended up there).
- A3: base-state fields share their full field's units, scale and colours (CM1 `prs0`
  and WoFS `PRES0` now hPa). A5: WoFS keeps "(first time)". A6: "Heights" group
  (`zagl`, `zmsl`, CM1 `zh`/`zhval`), in km.
- New groups: Microphysics (number & moments), Boundary layer, Radiation, Cumulus,
  Electrification, Time averages, Heights.
- `tests/test_catalog_outputs.py` (not run yet).

## Decided 2026-11-18 (Bobby's answers to the questions below)

1. A derived field that a file holds under the same name (same quantity) gives way to
   the file's: `Catalog(file_first=...)`, CM1 `thpert`, `prspert`. Otherwise the derived
   one is offered, once its formula is confirmed (step 2).
2. CM1's own decomposition is listed when the files have it; whether atmo3d's solver can
   follow CM1's math is below.
3. One convention: θ and qv budgets and tendencies per hour (K/h, g/kg/h), like the
   heating rates; u/v/w budgets in m/s².

4. `wspd`: CM1's `wspd` (output_sfcdiags) is the 2D surface-layer wind speed, so the
   derived 3D ground-relative wind speed is now `wspd3d`. Saved sessions and figures
   carry `"field_names": 2` (core.catalog.FIELD_NAMES, written by write_spec, the
   editor's state() and session_state); one without it was saved when `wspd` meant the
   derived field and is renamed on load (derived_renames: bundle.upgrade_names,
   session.upgrade). A later rename of a derived field adds a version to
   RENAMED_DERIVED.

## CM1's pressure decomposition vs atmo3d's (`pdcomp.F` r21.1 vs `pdecomp_solver.py`)

Same core: each part solves the anelastic pressure equation weighted by θv0 ρ0, with a
horizontal FFT and a vertical tridiagonal solve (CM1 `poiss.F`; ours FFT or a cosine
transform for open boundaries, conservative on the stretched grid).

What CM1 does differently:

- It runs **inside the model**, on the model state at output time, with the model's
  own staggered grid and operators. The nonlinear part is solved directly, from the
  model's advection routines (`advu/advv/advw`, the run's advection order), and there is
  a fourth part, Coriolis (`pipc`). Ours gets p_nl as the residual p′ − p_b − p_l (two
  solves, not four).
- Buoyancy forcing: g[θ′/θ0 + 0.61(qv − qv0) − (Σq_condensate − qc0 − qi0)]
  (linearized, base-state condensate removed). To compare with ours in step 2.
- Linear forcing: it builds only the −w dV0/dz term of the horizontal momentum
  equations (wten = 0), which looks like LINEAR_FACTOR = 1 in our terms, where ours
  uses 2. **To verify in step 2** before drawing a conclusion (the other half may sit in
  CM1's nonlinear part, which advects the full wind).
- Output is π′ (Exner, nondimensional) and the vertical PGF parts (m/s²); ours is p′
  (Pa) and accelerations. p′ ≈ cp ρ0 θv0 π′ converts them.

What CM1 does not allow (param.F stops the model): `output_pdcomp` with **MPI**, with
**terrain**, axisymmetric runs, or a stretched horizontal grid; its solve is
periodic laterally. So the large MPI supercell runs never have it, which is why the
offline solver exists.

Options:

1. **Use CM1's math in our solver** (recommended): solve p_nl directly from the
   advection forcing (one more solve: about +50% solve time over today's two), add
   the Coriolis part where f ≠ 0, and settle the buoyancy and linear-factor
   differences in step 2. The forcing stencils are cheap array work. Matching CM1's
   numbers to round-off would need the staggered u, v, w in the files and CM1's
   advection order; with only the interpolated winds it is close but not identical.
2. Compile CM1's Fortran (`pdcomp.F`, `poiss.F`, `adv*.F`) with f2py: they depend on
   CM1's modules, MPI layout and halo setup, so this is a large job for little gain
   over option 1.
3. Keep both as they are: CM1's when the files have it, ours otherwise.

Measuring option 1's cost needs a batch job on a full-size run (not on a login node).

**Update 2026-11-18:** Bobby chose to port CM1's math and compare. Done:
`atmo3d/pdecomp/cm1_method.py` (all four parts, CM1's WENO5 advection) and
`tools/compare_pdecomp.py`; write-up in `docs-dev/pdecomp-cm1-port.md`. Outcomes so far:
- The linear-factor question is settled: CM1's nonlinear part holds the second copy.
- Our acc_* depend on the arbitrary constant in π: a new step 2 item.
- The run on real data waits for a batch job.

## Notes

- `buoyancy` (CM1's, linearized) and derived `buoy` (θρ, full) are both listed: not the
  same formula, so step 2 decides whether CM1's stands in for ours.
- The meaning of `qi` depends on the scheme (P3: total ice; ISHMAEL: `qi1..3` by
  habit). Labels follow the most common meaning.
- Image baselines: none of the demo's plotted fields changed look, but labels, units
  and colours did change for CM1 `prate uh cpc cph psfc pwat cape cin lcl lfc` and the
  base state, so a baseline that draws one of those will move.
