# Radar design spike (Phase 4)

Status: decided (Bobby, 2026-11-19; see section 8). Nothing here is app code.
The prototype and the measurement scripts are in `docs-dev/radar-spike/`:

| File | What |
|---|---|
| `check_layout.py` | step 1: compares the metadata of every file in a folder |
| `sampler.py` | steps 2 and 4: the native volume, the beam model, the sampler, the views built on it, a PyVista sweep grid |
| `check_sampler.py` | synthetic checks with analytic answers (runs on a login node in seconds) |
| `bench.py`, `bench.log` | step 3: the measurements (run on a 4-CPU node, `NUMBA_NUM_THREADS=4`) and their output |
| `iso_index.py` | step 4: native isosurface without PyVista |
| `sampler_views.png`, `iso_compare.png` | figures from `bench.py` (file 9, 02:00 UTC) |

Data: `/glade/derecho/scratch/rasaba/20260403_20260404_results` (19 files). Numbers
below are for one field (reflectivity) of one volume unless said otherwise.

## 1. The 19 files (step 1)

All 19 share the site (35.33336 N, 97.27776 W, 389 m), the gates (1832, 250 m from
2.125 km), 720 rays per sweep at 0.5° spacing, the 42 variables (21 of them on
`(time, range)`), deflate level 4 and one storage chunk per ray. Differences, all of
which the reader must handle:

1. **Padding rays.** The `time` dimension is longer than the sweeps: files 0–8 have
   11160 rays and files 9–18 have 12600, but the sweep table covers only rays 0–10079
   (14 × 720). The rest have masked azimuth, elevation and data, and a repeated time.
   **The reader takes rays from `sweep_start/end_ray_index`, never from the `time`
   length.**
2. **File 18 has 13 sweeps.** It is missing 19.5°, so the sweep count varies by time.
3. **Measured elevations differ from `fixed_angle`** by up to 0.21°, e.g. 0.92° measured
   against 0.88° nominal. The sampler uses each sweep's median measured elevation.
   Medians also differ slightly between files (3.96 vs 4.00).
4. **Nyquist velocity varies by sweep and by file** (8.3 to 33 m/s).
5. **Timing.** Each volume takes 5.4–6.4 min from the first ray to the last. The first
   ray comes about 17 s after the time in the file name (`time` units, e.g. 01:06:35;
   `time_coverage_start` is 01:06:52).

Field contents (`bench.log` section A):

- **`u`, `v`, `doppler_degree`** are finite only where there is bistatic coverage. That
  is 1.7 k gates in file 0, rising to 421 k (file 12) and falling to 87 k (file 18), out
  of 18.4 M. Where finite, `doppler_degree` is always 2.
- **`w` is not always zero.** It is fully masked in file 0 and nonzero at 26–90 % of the
  u-valid gates in files 1–18. **`w_direct` is 0 everywhere it is finite, in all 19
  files.** (Section 5 of the plan said both were zero; that holds only for file 0.)
- Peak reflectivity is 64–76 dBZ.

## 2. The sampler (step 2)

`sample(vol, x, y, z)` returns field values at any points. x and y are in km east and
north of the radar; z is in km above the radar's level.

**Geometry: one explicit, shared choice.**
- **Beam model.** The 4/3 effective-earth-radius model (standard refraction). Beams are
  straight over a sphere of radius 4/3 × 6371 km, so gate → (ground distance, height)
  and its inverse are both closed-form. `polar_of` inverts `beam_height` to 1e-9.
- **Horizontal coordinates.** x, y lie on an azimuthal-equidistant plane centred on the
  radar: `hypot(x, y)` is the ground distance and `atan2(x, y)` the azimuth. Lat/lon go
  through pyproj `aeqd` centred on the site (already a dependency).
- **Heights.** z is above the radar level; MSL is z + 0.389 km. There is no terrain.

**Interpolation.**
- Within a sweep, values are interpolated across the two nearest azimuths and gates
  (`method="linear"`) or taken from the nearest gate (`"nearest"`).
- Between sweeps, values are linear in elevation across the two sweeps around the
  point.
- Up to half a beamwidth (0.475°) below the lowest sweep or above the highest, a point
  takes that sweep's value; beyond that it is NaN.
- **Missing data:** a value needs valid neighbours carrying at least half the weight, so
  echo edges fall halfway between gates or sweeps rather than shrinking or smearing.
- An azimuth hole wider than 2° gives NaN.
- `max_gap_km > 0` optionally gives NaN where the two sweeps are further apart
  vertically than that.

The interpolation is numba-compiled (`parallel=True`); numba is already a dependency.

Checks (`check_sampler.py`):
- **Height field.** Sampling a field equal to each gate's height returns z within 9 m
  (0.2 m mean) at 200 k random points.
- **`sin(az) × range` field.** Relative error is at most 1e-5.
- **NaN wedge.** Points inside a NaN wedge are NaN and points outside are finite.

What the views look like (`sampler_views.png`):
- Section tops show the expected sawtooth of the 19.56° sweep (no data above it), and
  the 3 km CAPPI has the hole over the radar.
- `linear` and `nearest` differ only in fine detail.
- One section has a small unexplained hole at x ≈ −90 km, 7–10 km up, probably missing
  gates in one sweep. To check in Phase 6.

## 3. Measurements (step 3; 4 threads)

**Reading** (netCDF4, one field to float32 (sweeps, rays, gates)):

| What | Time | Memory |
|---|---|---|
| one field, whole volume | 0.52–0.56 s (all 19 files) | 74 MB |
| one sweep of one field | 0.05 s | 5 MB |
| all 21 fields of one file | 14 s | ~1.0 GB peak |

All 21 fields at all 19 times would be 29.5 GB. Like CM1, radar needs the LRU cache of
whole fields, not an everything-in-memory model. One sweep is cheap, so a native PPI
can read only the sweep it shows.

**Sampler** (after compiling; median of 3):

| View | Points | Time |
|---|---|---|
| cross-section, 150 km × 18 km at 250 m × 100 m | 109 k | 11 ms (nearest 9 ms) |
| column, 0–18 km at 50 m | 361 | 0.07 ms |
| constant-height map (CAPPI), 300 × 300 km at 500 m | 361 k | 38 ms |
| CAPPI, full 920 × 920 km at 500 m | 3.4 M | 200 ms |

These costs are small enough to sample on demand every time: no regrid is needed for
any 2D view. The first call in a process pays a numba compile of about 1–2 s; with
`cache=True` that happens only once per installation.

**Regrid** (the sampler at every grid point, one level at a time; 0–20 km;
`dz = dx`):

| Grid | Points | Time | Size | Extra peak memory | Save / load (`.npy`) |
|---|---|---|---|---|---|
| full 920 km, 1 km | 21 × 921² = 18 M | 1.4 s | 71 MB | (under the earlier peak) | 0.1 / 0.0 s |
| full 920 km, 500 m | 41 × 1841² = 139 M | 10.8 s | 556 MB | +776 MB | 0.6 / 0.1 s |
| 300 km box, 500 m | 41 × 601² = 15 M | 1.4 s | 59 MB | (under the earlier peak) | 0.1 / 0.0 s |
| 300 km box, 250 m | 81 × 1201² = 117 M | 10.6 s | 467 MB | +530 MB | 0.4 / 0.1 s |

A regridded field is 1–8 times the native 74 MB. A full-range 500 m regrid of all 21
fields at one time would be 11.7 GB, so the regrid settings should include a maximum
range or box (the plan already lists maximum range). Caching to disk as `.npy` is
fast. The cost is in computing, not in storing.

## 4. 3D isosurfaces (step 4)

Three ways to draw the 40 dBZ surface of the whole volume:

| Method | Time | Triangles | Peak memory |
|---|---|---|---|
| PyVista `StructuredGrid` of gate centres (`sweep_grid`) + `contour` | 0.8 s build + 0.2 s | 456 k | ~4 GB |
| **marching cubes in (sweep, ray, gate) index space, vertices placed by the beam model** (`iso_index.py`) | **0.35 s** | 497 k | **0.42 GB** |
| regridded 1 km (full) / 500 m (300 km box) + marching cubes | 1.4 s / 1.4 s regrid + 0.2 s | 48 k / 183 k | as regrid |

**Recommendation: index-space marching cubes.**
- It is the same surface PyVista gives: trilinear in index space.
- It needs a tenth of the memory and no new dependency (skimage and plotly are already
  used).
- It follows the pattern terrain runs already use in `volume3d.isosurface`: find the
  surface on the levels, then place the vertices.
- PyVista is not needed.
- `iso_compare.png` shows the native and the 500 m regridded surfaces agree. The native
  one keeps finer detail.
- About 500 k triangles is more than plotly draws comfortably; the existing `MAX_FACES`
  step-size logic would apply.

**The gap between sweeps at long range.** A structured grid's cells join neighbouring
sweeps, so the surface is interpolated linearly across the gap, however wide.
Vertical gap (km) between neighbouring sweeps, against the 0.95° beam depth:

| sweeps | 50 km | 100 km | 150 km | 200 km | 300 km |
|---|---|---|---|---|---|
| 0.48–0.88 | 0.35 | 0.69 | 1.03 | 1.38 | 2.07 |
| 1.85–2.42 | 0.50 | 1.00 | 1.49 | 1.99 | 2.98 |
| 3.96–5.14 | 1.03 | 2.06 | 3.09 | 4.12 | 6.17 |
| 8.04–10.02 | 1.70 | 3.40 | 5.10 | 6.79 | 10.16 |
| 15.62–19.56 | 3.27 | 6.52 | 9.76 | 12.99 | 19.42 |
| beam depth | 0.83 | 1.66 | 2.49 | 3.32 | 4.97 |

(All pairs are in `bench.log`.)

- **Below about 4° the gaps are smaller than the beam at any range**, so bridging them
  invents nothing the beam didn't already smear.
- **Above 4° the gaps grow past the beam depth.** At 100 km, 8–10° leaves 3.4 km
  unobserved. A surface there is a linear guess drawn as a smooth sheet, and at long
  range a storm top becomes a slanted facet joining two sweeps (the "terracing" of
  long-range 3D radar).
- The lowest sweep is 1.4 km up at 100 km and 4 km up at 200 km, and the highest
  (19.56°) tops out at 17 km by 50 km range. Near the radar the volume has a cone of
  silence; far away it has no low levels.

The storm in this spike was 34 km from the radar, where none of this shows. The same
choice (`max_gap_km`) applies to sections and to 3D. Proposal for Phase 6: interpolate
across gaps by default (as now) with a "max gap" setting, plus a "native: interpolated
between sweeps" note on 3D views, like the "regridded: method, spacing" label.

## 5. The radar run object (step 5)

**Recommendation: a sibling base class, not a subclass of `Run`.**

`Run` is regular-grid through and through:
- `xh`, `yh`, `z`, `zf`, `ni`/`nj`/`nk`, `dx`/`dy`;
- level reads (`read_level(s)`, `read_height(s)`, `interp_height`, `column_weights`);
- `read_box`, `ij`, `reduce_levels`, `mean_profiles`;
- 3D volumes assumed to be (nk, nj, ni) by every consumer.

A radar subclass would have to synthesize that grid. Every view (the map window
`render.view_window`, sections through `fi`/`fj` and `map_coordinates`, 3D boxes,
sounding box averages, `fields.py` derivatives using `dx`) would then sample the
synthesized grid. That is an always-on regrid behind the user's back, which breaks
two settled decisions: native polar is the truth, and regridding is off by default. It
would also hold 1–8 times the memory per field (section 3).

Proposed shape (Phase 5 does the split; Phase 6 adds the radar side):

```
core/source.py   Source         path, files, times, time_label, vars/VarInfo, var_times,
                                attrs, catalog, OFFERS/offers/can, geo, note, extra,
                                the VolumeCache + in-flight locks + open-file LRU,
                                volume(name, t) -> the data type's native array,
                                cached/forget/fits/cache_info/clear_cache,
                                plus small neutral facts the viewer needs:
                                extent (km box), ztop, size_label, field_bytes
core/run.py      Run(Source)    the regular grid, unchanged (CM1Run, WoFSRun)
radar/...        PolarRun(Source)  site, per-time sweeps (elevations; 13 or 14),
                                gates; volume() -> (sweeps, rays, gates);
                                read_sweep(name, t, k) for the PPI panel
```

**The seam is a sampler per run** (`run.sampler`). It answers the questions the
non-native views ask, in km:

```
points(name, t, x, y, z)            -> values           (columns, probes)
section(name, t, x, y, zq)          -> (nz, n) array    (cross-sections)
plane(name, t, z, view, maxpix)     -> x, y, (ny, nx)   (constant-height maps)
isosurface(name, t, value, box)     -> verts, faces     (3D)
```

- The grid sampler wraps code that exists today: `render.sample_section`,
  `volume3d.sample_points` / `point_index`, `volume3d.isosurface`, and
  `Fields.plane` + `_crop`. CM1 and WoFS images stay pixel-identical.
- The polar sampler is `sampler.py`, with index-space marching cubes for 3D.

**Fields.** `fields.py` splits into:
- a neutral part: the catalog `FieldDef`s, the plane cache, `auto_range`, display
  scales, element-wise derived fields (e.g. speed from `u`, `v`), which work on any
  geometry;
- the grid part: derivatives (`ddx`/`ddy`/`ddz`, vorticity and the like), column
  integrals, storm-relative fields, which need `dx`/`dz`.

Radar gets the neutral part only, until it is regridded.

**Regrid** becomes a `RegriddedRun(Run)`: a grid `Run` backed by the cached regridded
arrays, with the radar catalog. With regrid on, the views swap to it and every grid
feature works unchanged, derivatives of the retrieved winds included. The views carry
the "regridded: method, spacing" label. This keeps the regrid optional and isolated:
nothing in the radar path depends on it.

**What the core, viewer and figures need to accept either** (from a grep of
`run.xh|yh|z|zf|dx|dy|ni|nj|nk`, `read_level`, `read_box`, `ij`):

| Where | Today | Change |
|---|---|---|
| `core/render.py` `compute_map`, `view_window`, `_crop` | index window on `xh`/`yh` | ask `run.sampler.plane` for x, y and the array |
| `core/render.py` `section_coords`, `sample_section`, `section_field` | `fi`/`fj` + `map_coordinates` | x, y points + `run.sampler.section` |
| `core/volume3d.py` `isosurface`, `sample_points`, `point_index`, `box_indices` | index boxes | `run.sampler.isosurface` / `points` |
| `core/fields.py` `Fields` | (nk, nj, ni) everywhere | neutral / grid split (above) |
| `viewer/app.py:73` | extent from `xh`/`yh` | `run.extent` |
| `viewer/widgets.py` (height slider, level mode, run info), `layout.py`, `dist.py`, `series.py`, `xsec.py`, `tracking.py` | `run.z[-1]`, `nk`, `ni×nj×nk`, `dx` | `run.ztop`, `run.size_label`; "level" mode becomes "sweep" on radar |
| `viewer/app.py:389`, `figures/render.py:263`, `viewer/sounding.py:171` | memory estimate `nk·nj·ni·4` | `run.field_bytes` |
| `viewer/mapview.py:460`, `viewer/export.py:186` | level labels from `run.z[k]` | a run-provided label |
| `figures/spec/arrays.py`, `figures/spec/sections.py`, `figures/shell/docedit.py`, `figures/shell/inspector.py` | crops and extents from `xh`/`yh`, `ni×nj×nk` | `run.extent`, the sampler, `run.size_label` |
| `viewer/sounding.py`, `figures/spec/panels.py` (sounding box averages) | grid boxes | grid-only: gated by the `soundings` capability (radar offers none) |
| `core/trajcalc.py`, `track.py`, `azim.py`, `swath.py`, `series.py`, `export.py`, `pdecomp/` | grid | grid-only; gated by capability (the Phase 3 mechanism), or available on `RegriddedRun` |

Most viewer and figure changes are swapping a grid attribute for one of four neutral
facts (`extent`, `ztop`, `size_label`, `field_bytes`). The real work is the four
sampler calls in `render.py` / `volume3d.py` and the `Fields` split.

## 6. What to build first (step 6)

1. **Phase 5, before any radar code.** Split `Source` / `Run` and add the sampler seam
   with only the grid implementation. This is a pure refactor checked by the image
   baselines (pixel-identical) and the existing tests. Do it in the core before the
   monorepo move, or as the move's first step.
2. **Phase 6, in this order:**
   1. variable audit;
   2. reader → `PolarRun` (sweep table, not the `time` length; 13 or 14 sweeps;
      measured elevations; site and pyproj `aeqd` geo);
   3. **native PPI panel** (one sweep, 0.05 s read, no sampler: the quickest useful
      radar view);
   4. polar sampler → cross-sections, columns, CAPPI maps;
   5. 3D via index-space marching cubes;
   6. **regrid last**, as `RegriddedRun`.
3. **Dependencies:** none new (numba, scipy, skimage, pyproj, plotly are in already).
   PyVista is not needed.

## 7. For Bobby to decide

1. **Run object:** sibling base class (`Source` → `Run`, `PolarRun`) with a sampler
   seam, as above? (Recommended.) The alternative, a `Run` subclass with a synthesized
   grid, amounts to an always-on regrid.
2. **3D:** index-space marching cubes (recommended) or PyVista?
3. **Gaps between sweeps:** interpolate by default with a "max gap" setting and a note
   on 3D views, or mask by default?
4. **Heights:** above the radar level (as prototyped) or above sea level?
5. **Time of a volume:** the time in the file name, the first ray, or the middle? A
   volume spans about 6 min, so at 15 m/s storm motion the top sweeps see the storm
   about 5 km from where the bottom ones did. Is any correction wanted, or is the
   `advcor` in the file names already that for the retrievals?
6. **Missing-data rule** (valid neighbours need at least half the weight) and the
   half-beamwidth extension above and below the sweeps: keep them?
7. **Still open from the plan:** receiver locations for the bistatic geometry.
8. **The prototype files** in `docs-dev/radar-spike/`: keep them as the Phase 6
   reference (proposed) or delete them after the decision?

## 8. Decisions (Bobby, 2026-11-19)

1. **Run object:** sibling base class (`Source` → `Run`, `PolarRun`) with a sampler seam.
2. **3D:** index-space marching cubes; no PyVista.
3. **Gaps between sweeps:** bridged by default (linear in elevation), with a "max gap"
   setting; may change later.
4. **Heights:** above the radar level.
5. **Time of a volume:** the time in the file name.
6. **Missing-data rule** (valid neighbours need at least half the weight) and the
   half-beamwidth extension: both kept.
7. **Receiver locations:** open. Bobby will check. Note: the per-gate bistatic angle
   `beta_nwc` should let the reader solve for each receiver's position (least squares
   over the gates where it is valid), which would be firmer than inferring it from
   where the data is missing.
8. **Prototype files:** kept in `docs-dev/radar-spike/` as the Phase 6 reference.
