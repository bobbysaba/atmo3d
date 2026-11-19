# Notes on the fields

What the field lists contain, how winds are handled, and what the derived fields and the
pressure decomposition are.

## Which fields you get

The field lists (grouped by kind) hold

- every **native** variable in the run's output, with a sensible label, units, colormap
  and range for the usual CM1 names, and
- the **derived** fields below, each offered only if the variables it needs are in the
  output.

Native fields are grouped as **Radar** (`dbz`, `cref`), **Kinematics** (winds and
vorticity components), **Thermodynamics** (`th`, `prs`, `pi`, `rho`, `qv`),
**Microphysics** (the other mixing ratios), **Swaths & 2D** (surface and accumulated
fields such as `rain`, `sws`, `svs`, `sps`, `sus`, `shs` and the translated `…2`
versions), **Turbulence**, **Budgets**, **Base state** (`th0`, `prs0`, …) and **Pressure
decomposition**. Water-substance mixing ratios are shown in g/kg and pressure in hPa.
Each entry in a list reads `label [name]`, with the CM1 variable name in brackets.

A field box opens a short menu of the groups; hover a group to see its fields. The
fields atmo3d computes are under **Derived**, and the rarely used ones under **Other**
(each opening its groups first). Type in the search box at the top to list every field
whose name matches; Enter takes the first, Escape closes.

Fields you rarely need are under **Other** (Other · <group> in the lists): for CM1
`pi`, the turbulence fields (`tke`, `kmh`, ...), the budgets, `cref`, `rain` and the
swaths, and the staggered `u`, `v`, `w` when the run also has `uinterp`, `vinterp`,
`winterp` (a run with only the staggered winds uses those for everything). For WoFS most
of WRF's 2D diagnostics and the less used 3D fields go there. WoFS's static, land-surface,
radiation and time-step fields (and WRF fields atmo3d does not know) are **hidden**: turn
on **Show hidden fields** in Settings (`show_hidden_fields`) to list them under
**Hidden**. A saved figure that uses a hidden field still draws it.

## Winds and the moving grid

CM1 writes winds relative to the moving grid. `umove` and `vmove` are read from
`namelist.input` in the run directory and added back for ground-relative winds,
hodographs and storm motions. The fields `uinterp`, `vinterp`, `winterp` are the winds
interpolated to the scalar points, and `xvort`, `yvort`, `zvort` the vorticity
components. Vectors can be shown ground-, grid- or storm-relative
([The map](map.md#vectors)).

## Derived fields

| Name | Field | Definition |
|---|---|---|
| `thpert` | θ′ (K) | `th − th0` (the base state `th0` is in the output) |
| `prspert` | p′ (hPa) | `prs − prs0` |
| `buoy` | Buoyancy (m/s²) | `g (θρ − θρ0) / θρ0` with θρ including the loading of all hydrometeors |
| `thrho`, `thrhopert` | θρ and θρ′ (K) | density potential temperature, and its departure from the base state |
| `thetae` | θe (K) | Bolton (1980) eq. 43 |
| `tempc`, `dewc` | Temperature and dewpoint (°C) | from θ, p and q<sub>v</sub> |
| `rh` | Relative humidity (%) | with respect to liquid water |
| `wspd3d` | Wind speed (m/s) | ground-relative, on every level (CM1's own `wspd` is the 2D surface-layer one) |
| `hdiv` | Horizontal divergence (10⁻³ s⁻¹) | ∂u/∂x + ∂v/∂y |
| `hvort` | Horizontal vorticity magnitude (1/s) | √(ξ² + η²) |
| `wstream`, `wcross` | Streamwise and crosswise vorticity (1/s) | the horizontal vorticity along and across the storm-relative horizontal wind (below) |
| `bgen_x`, `bgen_y` | Baroclinic generation of horizontal vorticity (10⁻⁴ s⁻²) | (∂B/∂y, −∂B/∂x): the buoyancy torque, also drawn as the *Baroclinic generation* vector |
| `zstretch`, `ztilt`, `ztend` | Vertical-vorticity stretching, tilting and their sum (10⁻⁴ s⁻²) | ζ ∂w/∂z, ξ ∂w/∂x + η ∂w/∂y (below) |
| `okubo` | Okubo–Weiss parameter (10⁻⁴ s⁻²) | s<sub>n</sub>² + s<sub>s</sub>² − ω² (below) |
| `qcloud`, `qprecip` | Cloud and precipitation condensate (g/kg) | qc + qi, and qr + qs + qg + qhl, where those are in the output |
| `p_dyn`, `acc_dyn`, `acc_tot` | Pressure decomposition sums (with the Coriolis part) | see below |

Other derived fields are defined in `atmo3d/core/fields.py` (`_make_fields`); see
[Developing](../developing.md) for how to add one.

### Derivatives of any field

The **Derivative** select beside a Field (the map's fill, a figure's fill, contour and
shading layers on plan views and cross-sections, the Series tab, and a figure's series and
profile cards) plots a derivative of that field instead, per metre:

| Derivative | Name | What |
|---|---|---|
| ∂/∂z | `ddz.<field>` | on each model level, centred between the levels above and below (one-sided at the bottom and top), on the stretched levels; at a height, interpolated between the two levels' values. 3-D fields only. |
| ∂/∂x, ∂/∂y | `ddx.<field>`, `ddy.<field>` | centred differences on the grid's x and y (stretched grids too), at the level shown |
| \|∇h\| | `gradh.<field>` | √((∂/∂x)² + (∂/∂y)²) |

Units are the field's per metre: a wind's (m/s per m) read 1/s, so ∂w/∂z of 0.005 is
5 m/s per km. Column max / min are of the derivative (the largest ∂w/∂z in the column), and
a cross-section's derivative is taken on the 3-D grid, so it agrees with the map at the
same level. Derivatives of derived fields work the same way (∂θ′/∂x, ∂B/∂z, ...). The
starting colour range is half the field's own range per km (written per metre); use
Auto range on the map.

In a series or profile the derivative is taken first and then reduced over the region:
the maximum ∂w/∂z at 2 km, not ∂/∂z of the maximum w. Horizontal derivatives are taken
with the grid points just outside the region, so the values at its edge are the map's.

### Vorticity tendencies

The *Vorticity tendencies* group has the terms of the vertical-vorticity equation that
make or concentrate ζ, in 10⁻⁴ s⁻² (a ζ of 0.02 s⁻¹ in ∂w/∂z of 0.01 s⁻¹ stretches at 2):

| Name | Term |
|---|---|
| `zstretch` | stretching, ζ ∂w/∂z |
| `ztilt` | tilting of horizontal vorticity into the vertical, ξ ∂w/∂x + η ∂w/∂y |
| `ztend` | stretching + tilting |
| `okubo` | Okubo–Weiss, W = s<sub>n</sub>² + s<sub>s</sub>² − ω², with s<sub>n</sub> = ∂u/∂x − ∂v/∂y, s<sub>s</sub> = ∂v/∂x + ∂u/∂y and ω = ∂v/∂x − ∂u/∂y: negative where rotation dominates the strain (a vortex), positive where strain dominates |

ζ, ξ and η are CM1's `zvort`, `xvort` and `yvort`; the derivatives are those of the
**Derivative** select (below), so ∂w/∂z is centred on the stretched levels and the
horizontal ones on the grid, and Okubo–Weiss uses the winds on the scalar points. Like
the other fields they work on the map, cross-sections, column max / min, 3D, series and
figures; in a series the horizontal derivatives use the points just outside the region.
Baroclinic generation of horizontal vorticity is `bgen_x`, `bgen_y` (above).

### Column fields

The *Column fields* group has 2D fields made from the 3D fields over a fixed layer of
each column, so they work wherever a 2D field does (the map, series, distributions,
figures), and a series of one reads only the levels of its layer in the region:

| Name | What | Layer |
|---|---|---|
| `uh25` | Updraft helicity, ∫ w ζ dz (m²/s²) | 2–5 km AGL |
| `uh01` | Updraft helicity, ∫ w ζ dz (m²/s²) | 0–1 km AGL |
| `zvmax01` | Maximum ζ (1/s) | 0–1 km AGL |
| `wmax` | Maximum w (m/s) | the whole column |

The integral is over the layer exactly: each model level counts with the part of its grid
cell (between the `zf` levels) inside the layer. A maximum is over the model levels whose
cells reach into the layer. w and ζ are `winterp` and `zvort`; updraft helicity is that of
Kain et al. (2008), so it is negative in an anticyclonic updraft or a cyclonic downdraft
(CM1's own `shs` swath is its running maximum). The layers are fixed for now.

### Sounding parameters

The *Sounding parameters* group has the bulk shear, storm-relative helicity, parcel
CAPE, CIN and LCL and the composite parameters of every column, as 2D column fields (so
on the map, series, distributions and figures):

| Name | What | Layer |
|---|---|---|
| `shear0250`, `shear0500` | Bulk shear (m/s) | 0–250 m, 0–500 m AGL |
| `shear01` | Bulk shear, \|V(1 km) − V(lowest level)\| (m/s) | 0–1 km AGL |
| `shear03`, `shear06` | Bulk shear (m/s) | 0–3 km, 0–6 km AGL |
| `srh0250`, `srh0500` | Storm-relative helicity (m²/s²) | 0–250 m, 0–500 m AGL |
| `srh01` | Storm-relative helicity (m²/s²) | 0–1 km AGL |
| `srh03` | Storm-relative helicity (m²/s²) | 0–3 km AGL |

They are computed as the [Soundings](soundings.md#what-is-computed) tab computes them:
from the lowest model level up to the layer top, with the wind linearly interpolated
between the levels (to the layer top exactly, where the sounding's 10 m grid can stop a
few metres short, so SRH may differ from the sounding's by about 1%). Helicity is
relative to the **tracked storm motion** at that time when the track has a fix there,
and otherwise to the domain motion, as for streamwise vorticity (below); the map title
and colorbar say which. Shear does not depend on it.

Parcel parameters, from the whole column:

| Name | What |
|---|---|
| `sbcape`, `mlcape`, `mucape` | CAPE (J/kg) of the surface-based, 100 hPa mixed-layer and most-unstable parcels |
| `sbcin`, `mlcin`, `mucin` | CIN (J/kg, negative) of those parcels |
| `sblcl`, `mllcl`, `mulcl` | LCL height (m AGL) of those parcels |
| `stp` | Significant tornado parameter, fixed layer: SBCAPE, SB LCL, 0–1 km SRH, 0–6 km shear |
| `scp` | Supercell composite parameter, fixed layer: MUCAPE, 0–3 km SRH, 0–6 km shear, MUCIN |

The parcels are those of the [Soundings](soundings.md#what-is-computed) tab, lifted the
same way, so a column's values are the sounding's there. CM1's own `cape`, `cin`, `lcl`,
`lfc` (output_cape ...), when the files have them, are of a different parcel: a 500 m
mixed layer, lifted pseudoadiabatically with liquid only; they are labelled so. STP is the sounding's *STP
(fixed)*. The sounding's *SCP* uses the effective inflow layer, which needs a parcel
lifted from every level of a column. That is too slow for a map, so the map's `scp`
takes its formula with 0–3 km SRH for effective SRH and 0–6 km shear for effective
shear. Both use helicity relative to the tracked storm motion, as `srh01` and `srh03`
do. The soundings' default storm motion is the Bunkers right mover; set the sounding's
*Storm motion* to *Tracked meso motion* to compare them.

Lifting a parcel through every column is slow: about 0.1 ms a column per parcel on one
CPU (more with more levels), spread over the reader CPUs (`workers`). A 1000 × 1000 domain
takes tens of seconds per parcel and time. So these fields are computed on every n-th
column in x and y (the `column_stride` [setting](../settings.md); each n × n block of
the map shows its middle column). With `auto`, that is every column up to 500 × 500
points and enough columns apart beyond that to keep to about 250 000. The fields of
one parcel and time share one lift (SB CAPE, SB CIN, SB LCL and STP lift once). A
series uses the same columns as the map.

### Streamwise and crosswise vorticity

These are relative to the **tracked storm motion** at that time when the track has a fix
there, and otherwise to the domain motion (`umove`, `vmove`). The map title, colorbar,
section title, 3D legend and streamline card say which was used. *Crosswise* is positive
to the left of the storm-relative wind.

## Parcels

Parcel calculations are pseudoadiabatic with a virtual-temperature correction. They were
checked against MetPy: CAPE agrees within about 3%. The definitions of the SB, ML and MU
parcels and the other sounding parameters are on the [Soundings](soundings.md#what-is-computed)
page.

## Pressure decomposition

The **Pressure decomposition** field group holds CM1's own decomposition (the method of
CM1's `output_pdcomp`, `pdcomp.F`):

- the pressure perturbation split into a buoyancy part `p_b`, a linear dynamic part `p_l`,
  a nonlinear dynamic part `p_nl` and a Coriolis part `p_c` (zero when f = 0);
- the matching vertical accelerations `acc_b` (B − cp θv0 ∂π_b/∂z), `acc_l`, `acc_nl` and
  `acc_c` (−cp θv0 ∂π/∂z of each part, as CM1 writes its `pgrad*` fields);
- `p_dyn` = p_l + p_nl + p_c, `acc_dyn` = acc_l + acc_nl + acc_c, and `acc_tot` = acc_b +
  acc_dyn.

### Where the values come from

Where atmo3d (or the stand-alone `cm1_pdecomp`) wrote them into the output files they
are read from there (any file subset). Values written by atmo3d's older solver show
with a note in the map title: they split the pressure differently (see below) and have
no Coriolis part, so the sums that need `p_c` ask for a recompute. Elsewhere, a
**Compute pressure decomposition** button (under the map or section) computes that time
in a separate process (`atmo3d/pdecomp/cm1_pdecomp.py`).

### What it does

Each part solves CM1's anelastic pressure equation for the Exner function,

```
cp [H ∂²π/∂x² + H ∂²π/∂y² + ∂/∂z(Hf ∂π/∂z)] = ∇·(ρ0 T)      with H = ρ0 θv0
```

by a horizontal FFT (periodic lateral boundaries, `wbc = 1`) or cosine transform (open
ones) and a tridiagonal solve in the vertical, where T is the part's momentum tendency on
CM1's staggered grid:

- `p_b`: the buoyancy B = g [θ′/θ0 + 0.61 (qv − qv0) − Σ q_condensate] at w levels;
- `p_l`: (−w ∂U0/∂z, −w ∂V0/∂z, 0);
- `p_nl`: −(u·∇)u′, with CM1's own advection (WENO5 or 5th order, as the run);
- `p_c`: (f v, −f u, 0).

`p_nl` holds a second copy of the linear term (advecting u′ by the base-state wind
gives it), as in CM1. It needs the horizontal grid uniform, no terrain, and the
momentum advection WENO5 or 5th order. With the staggered winds in the files
(`output_u`, `output_v`, `output_w`) and the base state (`output_basestate`) it matches
what CM1 would write; without them, u, v, w are interpolated back from `uinterp` …
(close, not exact) and the base state comes from the first output.

atmo3d's older solver (`pdecomp_solver.py`, still there for `pdecomp_script`) used twice
CM1's linear forcing for `p_l` and took `p_nl` as the residual p′ − p_b − p_l. Its sums
`p_l + p_nl` agree with CM1's `p_l + p_nl + p_c` to ~5% in a supercell.

### Cost

The inputs are read in parallel first, and the computation uses every CPU of the job:
about 2 minutes with 4 CPUs for a 1280 × 1280 × 115 grid, which needs about 35–45 GB of
free memory (less for smaller grids, in proportion). If the job lacks the memory, the 3D
cache is emptied first; if still short, it says so. See [Running on a
cluster](../hpc.md#resources) for the memory to ask for.

### Writing into the output file

*Write into the output file* (offered when `allow_writes_to_output` is on) writes the
result into the output file (float32, with a `pdecomp_version` attribute; about +40 s and
+6 GB per file for a 1280 × 1280 × 115 grid), replacing older values.

- While it writes, the viewer releases that one file and reports it as busy.
- **If the job is killed during a write, the file can be left damaged.**
- Unticked, the result is kept in memory only. The last 2 computed times stay in memory
  either way.
- For files written by the older solver the button offers *Recompute … and overwrite*.

### Outside the viewer, or your own solver

`cm1_pdecomp.py` is one self-contained file; it also runs on its own (its docstring
shows how, and a stand-alone copy with a driver script exists). To use another solver,
point the `pdecomp_script` setting (or `--pdecomp-script`, or `$ATMO3D_PDECOMP_SCRIPT`)
at a Python file with either

- cm1_pdecomp's `run_decomposition(path, run_dir=..., t0_path=..., threads=...)`,
  returning a dict with the fields above, and `write_data(ds, out)`; or
- the older interface of `pdecomp_solver.py` (`lbc_type`, `domain_info`,
  `compute_base_state`, `setup_pressure_solver`, `pressure_decomposition` and
  `write_data`), which gives the first six fields only,

and a module-level `nc` (`import netCDF4 as nc`) that it opens files with.
