# Phase 6, step 1: radar variable audit

Status: **sheet prepared 2026-11-19, waiting for Bobby's decisions.** Same template as
`field-audit.md`. Fill the Decision column, or write "ok" for a whole section, and rows you
leave blank take the proposal. The result becomes the radar field catalog
(`packages/radar/src/atmo3d_radar/catalog.py`).

The data is the 19 CfRadial files in `/glade/derecho/scratch/rasaba/20260403_20260404_results`.
The numbers below come from file 12 (02:21 UTC, the file with the most bistatic
coverage), counting only the 10080 rays in the sweep table. Coverage in the other files is
in `radar-spike/bench.log` section A.

Columns:

- **file**: the long name or standard name and the units in the file.
- **values**: finite gates out of 18.47 M, then p1 / p50 / p99, then min..max.
- **Proposal**: label · units · colormap · range · `div` (diverging) · tier. The tiers
  are the ones CM1 and WoFS use: Main, Other, and Hidden (listed only with
  `show_hidden_fields`).

---

## A. Policy questions (answer these first; they decide most rows)

| # | Question | Proposal | Decision |
|---|----------|----------|----------|
| A1 | **Groups** | **Moments** (the radar's own fields: reflectivity, velocity, dual-pol); **Bistatic** (the receiver network's fields); **Retrieved winds** (`u v w`); **Bistatic QC** (flags and receiver signal quality). The group name marks a field as retrieved or observed, so labels need no "(retrieved)" suffix. | |
| A2 | **Roles** (what the core treats as wind and reflectivity) | `refl` = `reflectivity`; `u v w` = the retrieved `u v w`. This turns on wind vectors, speed and the 3D defaults. The files have no composite, so `cref` has no role (see D3). | |
| A3 | **Masks on the retrieved winds** | Use the file's mask as it is and add none. `u v` are finite only where `doppler_degree` = 2, and they are 2 everywhere they are finite, so a `doppler_degree` < 2 rule removes nothing. `w` is finite at a subset of the `u` gates (365 k of 421 k). **But** 79 k of the 421 k `u` gates have receiver mask = 1, 80 k have a QC flag other than 0, and 21 k have `beta_cutoff` = 1 (see A4). So the retrieval does not require those three to pass. Should the viewer drop those gates, or trust the retrieval? | |
| A4 | **What the QC fields mean** (needed for A3 and for their colours) | My reading of the numbers, to confirm: `beta_cutoff_nwc` 0 = β is inside 30–150° (usable) and 1 = outside; `receiver_bistatic_velocity_mask_nwc` 0 = kept and 1 = masked; `receiver_qc_reason_flag_nwc` 0 = passed, and other values are reasons. The values seen are 2, 4, 5, 7, 9, 12, 13, 16, 17 and 18. These look like bit sums (bits 1, 2, 4, 8, 16), and 4 is the most common reason (5.38 M gates). **What does each bit mean?** If nobody knows, the field goes to Hidden. | |
| A5 | **How many receivers** | The file has one β field, one set of receiver fields and `doppler_degree` ≤ 2. That suggests KTLX plus **one** receiver. Is that right? (Its location is still open: radar-spike.md section 8, item 7.) | |
| A6 | **Velocity colours** | Radial and bistatic velocities, and `u v w`, use `RdBu_r` (red = positive, i.e. away from the radar for radial velocity), as CM1's winds do. The alternative is the NWS green/red velocity table, which would be a new colormap in `fields.CMAPS`. | |
| A7 | **Per-ray fields** (`nyquist_velocity`, `unambiguous_range`) | Not field-list entries, because they are per ray and not per gate. Show the sweep's Nyquist velocity in the PPI panel's title or run info. | |
| A8 | **Gate geometry as fields** (height above the radar, ground range, azimuth, from the beam model) | Hidden, for checking the geometry. They cost nothing because they come from the sweep table. | |
| A9 | **Labels and units style** | As WoFS after its audit: short labels, symbols where usual (Z<sub>DR</sub> is written `ZDR`, ρ<sub>hv</sub> as `ρhv`, Φ<sub>DP</sub> as `ΦDP`), units `dBZ`, `dB`, `m/s`, `°`. | |

---

## B. Moments (the radar's own fields)

| Field | file | values | Proposal | Decision |
|-------|------|--------|----------|----------|
| `reflectivity` | Reflectivity · dBZ · valid −32..94.5 | 3.76 M · −1 / 23 / 53.5 · −18.5..76 | Reflectivity · dBZ · reflectivity · 0–75 · Main (the `refl` role; same look as CM1's `dbz`) | |
| `velocity` | Corrected mean doppler velocity · m/s | 2.81 M · −30 / −1 / 29 · −59..56 | Radial velocity · m/s · RdBu_r · ±30 · div · Main. The values go past the 8–33 m/s Nyquist, so the field is already dealiased ("Corrected"). | |
| `differential_reflectivity` | log_differential_reflectivity_hv · dB | 3.69 M · −1.6 / 0.5 / 4.4 · −7.9..7.9 | ZDR · dB · turbo · −2–6 · Main | |
| `cross_correlation_ratio` | Cross correlation_ratio (RHOHV) · ratio | 3.40 M · 0.72 / 0.992 / 0.998 · 0.21..1 | ρhv · (none) · turbo · 0.7–1.0 · Main | |
| `differential_phase` | differential_phase_hv · degrees | 3.71 M · 51 / 82 / 225 · 0..360 | ΦDP · ° · turbo · 0–360 · Other (raw ΦDP is hard to read; no KDP in the files) | |
| `spectrum_width` | Spectrum Width · m/s | 3.60 M · 0 / 2 / 7 · 0..19 | Spectrum width · m/s · magma · 0–10 · Main | |
| `clutter_filter_power_removed` | Clutter filter power removed · dB | 0.20 M · 0 / 0 / 41 · 0..73 (72 % zero) | Clutter filter power removed · dB · magma · 0–40 · Other | |

## C. Bistatic (receiver network)

| Field | file | values | Proposal | Decision |
|-------|------|--------|----------|----------|
| `bistatic_velocity_nwc` | bistatic velocity · m/s | 0.44 M · −30 / −9 / 14 · −36..70 | Bistatic velocity · m/s · RdBu_r · ±30 · div · Main. It is finite at every `u` gate plus 22 k others. | |
| `bistatic_velocity_unsmoothed_nwc` | bistatic velocity unsmoothed · m/s | 0.66 M · −30 / −4.6 / 19 · −66..156 | Bistatic velocity (unsmoothed) · m/s · RdBu_r · ±30 · div · Other | |
| `original_bistatic_velocity_nwc` | original bistatic velocity · (no units) | 5.97 M · −30 / −1.8 / 30 · −124..174 | Bistatic velocity (before QC) · m/s · RdBu_r · ±30 · div · Other. Is this "before QC"? It is finite wherever the receiver fields are. | |
| `beta_nwc` | (no name) · degrees | 18.47 M (every gate) · 0.09 / 3.6 / 107 · 0..180 | Bistatic angle β · ° · viridis · 0–180 · Other. It is pure geometry and finite everywhere. It is also the input for solving the receiver's location (spike section 8, item 7). | |

## D. Retrieved winds

| Field | file | values | Proposal | Decision |
|-------|------|--------|----------|----------|
| `u` | u component of wind · m/s | 0.42 M · −12 / 12.7 / 34 · −52..52 | Retrieved u (east) · m/s · RdBu_r · ±30 · div · Main (`u` role). Earth-relative east, which is x on the radar-centred plane. | |
| `v` | v component of wind · m/s | 0.42 M · −21 / −2.1 / 23 · −66..65 | Retrieved v (north) · m/s · RdBu_r · ±30 · div · Main (`v` role) | |
| `w` | (no attributes) | 0.36 M · −11.7 / −0.02 / 22.7 · **−74..78** | Retrieved w · m/s · RdBu_r · ±20 · div · Main (`w` role). The ±75 m/s extremes look like noise. How is `w` computed (continuity from the ground up or down?), and should it be shown at all? It is entirely missing in file 0. | |
| `w_direct` | direct-retrieval w component of wind · m/s | 0.42 M, **all 0, in all 19 files** | Hidden | |
| `doppler_degree` | degree of multi-doppler analysis · number of radars | 0.42 M, all 2 | Hidden (it says only where `u` is valid) | |

## E. Bistatic QC

| Field | file | values | Proposal | Decision |
|-------|------|--------|----------|----------|
| `beta_cutoff_nwc` | (int64) · n/a | every gate: 0 = 0.95 M (β 30–150°), 1 = 17.5 M | Hidden (follows from β; A4) | |
| `receiver_bistatic_velocity_mask_nwc` | receiver bistatic velocity mask | 5.97 M: 0 = 0.49 M, 1 = 5.48 M | Other · categorical 0/1 · Greys_r · 0–1 (A4) | |
| `receiver_qc_reason_flag_nwc` | qc reason flags | 5.97 M: 0 = 0.35 M, 4 = 5.38 M, 17 = 0.14 M, 16 = 39 k, 7 = 20 k, the rest < 20 k each | Other with labelled values if A4 gives the meanings; Hidden otherwise | |
| `receiver_ncp_nwc` | receiver NCP · (none) | 5.97 M · 0.48 / 0.73 / 0.99 · 0..**20** | Receiver NCP · (none) · viridis · 0–1 · Other. NCP should be at most 1, so what are the values up to 20? | |
| `receiver_rcp_nwc` | receiver RCP · (none) | 5.97 M · 29 / 43 / 57 · −6..83 | Receiver RCP · **dB?** · viridis · 20–60 · Other. What is RCP, and what are its units? | |

## F. Derived fields

Proposals only. Derived equations get their own entries, as in `derived-fields.md`, once
the list is agreed.

| # | Field | Proposal | Decision |
|---|-------|----------|----------|
| D1 | Horizontal wind speed from the retrieved `u v` | Yes. This is the core's existing `wspd3d` ("Wind speed (ground-relative)", turbo, 0–40). It is pointwise, so it works on polar data, with the radar run's domain motion (`umove`, `vmove`) set to 0. | |
| D2 | Grid derived fields from `u v w` (vorticity, divergence, the other derivatives) | Offered **only on a regridded run**, because they need `dx` and `dz` (spike section 5). They come from the core's existing definitions through the roles in A2, so they need no new code. The thermodynamic derived fields never appear, because the radar has no θ, p or qv. | |
| D3 | Composite reflectivity (column maximum) | A derived 2D field, computed as the maximum over the sweeps at each ground point through the sampler, on the plane view's points. It plays the `cref` role, which the 2D defaults use. Wanted? | |
| D4 | Echo tops (for example the 18 dBZ top) | Not now (list it for later)? | |
| D5 | Radial velocity minus the storm motion (storm-relative velocity) | Not now. Radar has no storm motion yet. | |
| D6 | Anything else? (KDP, hydrometeor class, azimuthal shear ...) | Nothing unless you name it. | |

---

## G. Not fields (for the reader, recorded here so nothing is forgotten)

- `time`, `azimuth`, `elevation`, `range`, `sweep_*`, `fixed_angle`, `latitude`,
  `longitude`, `altitude`, `time_coverage_*`, `volume_number`, `vcp_pattern`,
  `instrument_name`: the reader uses these for geometry, times and run info.
- `advcor` in the file names: are all fields advection-corrected, or only the
  retrievals? This matters for how a section through two sweeps should be read.
