# Radar volumes

atmo3d opens a folder of **CfRadial volumes** (one file per time, as the bistatic KTLX
files `combined_radar_object_advcor_<n>_<YYYYMMDD_HHMMSS>.nc`) as one run. The volumes are
read in their native polar geometry (sweeps × rays × gates, heights from the beam model, the
radar at the origin); the map, cross-sections, columns and 3D views sample them where they
are asked to, and an optional regrid makes a regular grid of them. This page covers what is
different from a CM1 run.

## Opening a folder

Give atmo3d the folder (`atmo3d /path/to/folder`, or pick it in the run picker; the model
box can be set to *Radar*). Auto-detect looks at the file names and the first file's header.
The picker lists the folder as *N volumes*. Times are the files' times, in UTC.

## What the views show

- **The map** draws one **sweep** (the level control's "Sweep" mode: the nearest ray and gate
  to each pixel). Two more modes sample the volume: **Height (km)**, a constant-height map
  (km above the radar), and **Column max / min**, the extreme over the sweeps at each ground
  point (composite reflectivity is *Column max* of reflectivity).
- **The PPI tool** (rail) lists the sweeps of the shown time (elevation, fixed angle, Nyquist
  velocity, rays, height of the last gate), picks the one the map shows, and for a click on
  the map gives the gate there and draws the column above it: the sampled values from the
  ground up, and each sweep's own gate value at its beam height.
- **Cross-sections** and the **3D region** sample the volume along the section or inside the
  box. Points the sweeps do not cover are left empty.
- **Fields** are the files' own, in groups: *Moments* (reflectivity, radial velocity, ZDR,
  ρhv, spectrum width), *Bistatic*, *Retrieved winds* (`u`, `v`, `w`) and *Bistatic QC*
  (shown as the files give them; their meanings are not yet confirmed). Each receiver's
  bistatic fields carry its site as a suffix in the file (`beta_nwc`), and show it in the
  field's name ("Bistatic velocity (NWC)"): a file with more receivers lists each one's. Wind speed is derived
  from the retrieved `u` and `v`.

Off on a native radar run: Series and Distribution, 3D vectors and streamlines, the Figure
workspace and sessions. They work on a regridded run.

## Sampling settings

How a value between gates is made, and where the views leave gaps (⚙ Settings, see
[Settings](../settings.md)):

| Setting | Meaning |
|---|---|
| `radar_sampling` | `linear` between the nearest rays and gates, or `nearest` gate |
| `radar_max_gap_km` | leave a point empty where the two sweeps around it are further apart than this (auto: every gap is bridged) |

## Regridding

Regridding is **off unless you ask for it**; native sweeps stay the source. Choose
**Regridded** in the toolbar's *Native sweeps | Regridded* switch. A dialog shows the settings
and the grid's size; only its **Regrid** button opens the regridded run, so the settings are
confirmed every time.

| Setting | Default | Meaning |
|---|---|---|
| `radar_regrid_method` | linear | sampling within a sweep (as `radar_sampling`) |
| `radar_regrid_dx` | 0.5 km | horizontal spacing |
| `radar_regrid_dz` | 0.5 km | vertical spacing |
| `radar_regrid_range` | 150 km | the grid's reach from the radar |
| `radar_regrid_max_gap` | 0 | the widest gap between sweeps bridged, km (0: all) |

The regridded run is an ordinary grid run: every grid feature works (series, distributions,
figures, sessions) together with derived wind fields (vorticity, divergence and the other
derivatives of the retrieved winds). Its views are labelled **regridded: method, spacing**.
Each field and time is regridded when first shown (a few seconds at the defaults) and kept in
the cache folder, which holds at most 4 GB for each regridded run; a rewritten volume is
regridded again.

The settings are part of the regridded run's name (`regrid_linear_dx0.5_dz0.5_r150_gap0`), so
sessions, figure bundles, exports (`atmo3d_regrid*` attributes) and the address keep them.
Switching between native and regridded changes sweep-mode map layers to a 1 km height.

## Trying it

There is no shipped radar demo run. The tests use a small synthetic radar
(`tests/synthetic_radar.py`); see [Developing](../developing.md).
