# Radar volumes

atmo3d opens a folder of radar volumes, one file per time, as one run: **CfRadial** files
(as the bistatic KTLX files `combined_radar_object_advcor_<n>_<YYYYMMDD_HHMMSS>.nc`) or
**NEXRAD Level II** files (`KTLX20130520_195111_V06`, as the archive has them, `.gz` or
not; see [NEXRAD Level II](#nexrad-level-ii)). The volumes are
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
- **Radial velocity (dealiased)** is offered wherever the files have `velocity` (below).

Off on a native radar run: Series and Distribution, 3D vectors and streamlines, the Figure
workspace and sessions. They work on a regridded run.

A radar without retrieved winds (`u`, `v`; every Level II folder) has no vectors: the
map's and the cross-section's *Vectors* menus are not shown.

## Dealiased velocity

A Doppler radar measures radial velocity only within ± its Nyquist velocity: faster winds
*fold* (wrap around) to the other end of the colour bar, as the sharp red–green edges in
a strong storm or jet. **Radial velocity (dealiased)** (`velocity_dealiased`, in
*Moments*) unfolds them, sweep by sweep, with each sweep's own Nyquist velocity (the PPI
tool lists them). It works on regions: gates next to each other with similar velocities
form a region, a fold always lies on a region's edge, and the regions are joined
strongest shared edge first, each shifted by the multiple of twice the Nyquist velocity
that makes it agree with its neighbours (the region-based method of Py-ART). An echo
that touches no other is set by the main echo along the same rays (across a gap of up to
20 km at 250 m gates), else left as measured.

It takes about 0.1 s a sweep, and is kept like any other field once read. Like every
dealiasing method it can be wrong where the echo is patchy or the shear is sharp (a
tornado's couplet); compare with *Radial velocity* when a value looks off. A sweep with
no Nyquist velocity in its file is shown as measured.

## NEXRAD Level II

A folder of WSR-88D Level II files (Archive II, from 2008 on: the files NOAA's archive on
AWS and the NCEI archive hold) opens like any radar folder. Each file is one volume; its
time is the one in its name. atmo3d decodes the files itself (it checks itself against
MetPy's reader in its tests).

- **Fields**: reflectivity, radial velocity, spectrum width, ZDR, ρhv, ΦDP and, where the
  file has it, clutter filter power removed, under the names CfRadial files use.
- **Split cuts**: the lowest elevations are scanned twice, once for reflectivity and the
  dual-pol moments (out to 460 km) and once for velocity and spectrum width. They are one
  sweep here: the reflectivity scan's rays, each with the velocity of the Doppler scan's
  ray nearest in azimuth (super-resolution rays are 0.5° apart, so within 0.25°). The PPI
  tool's Nyquist velocity is the Doppler scan's.
- **SAILS / MESO-SAILS**: a volume that repeats its lowest elevation lists each repeat as
  its own sweep, labelled with its time ("0.5° 04:03:02"), in the order scanned.
- **Gates**: every moment is on reflectivity's gates (250 m from 2.125 km); velocity and
  the dual-pol moments end sooner (about 300 km), and are empty beyond.
- **Velocity** is as the radar measured it, folded at the Nyquist velocity; see
  [Dealiased velocity](#dealiased-velocity) for it unfolded.
- **Not read**: files from before 2008 (Message 1).

### From the AWS archive

NOAA's Level II archive is public on AWS. In the run picker, **NEXRAD from AWS…** takes a
site (`KTLX`), a day and a time window in UTC (an end before the start is on the next
day; at most 24 hours), lists the volumes the archive has with their total size, and
**Fetch and open** downloads them and opens the folder. They go to
`<radar_nexrad_dir>/<SITE>_<yyyymmdd>` (blank setting: `nexrad/` in the cache folder, on
scratch at NCAR); files already there are not fetched again, so a window can be widened
and fetched again, and a cancelled fetch keeps the files it finished.

Downloading needs internet, which compute nodes often lack. From a login node (or any
shell), the same is a command:

```sh
atmo3d-nexrad KTLX 2013-05-20T19:30 2013-05-20T21:00          # fetch
atmo3d-nexrad KTLX 2013-05-20T19:30 2013-05-20T21:00 --list   # only list
atmo3d-nexrad KTLX 2013-05-20T19:30 2013-05-20T21:00 --into /glade/derecho/scratch/$USER/nexrad
```

It prints the folder; open it in atmo3d like any other. (`python -m atmo3d_radar.aws`
does the same where the command is not installed.)

### Live

The radar finishes a volume every 4 to 10 minutes, and the archive has it a few minutes
later. **Live** (next to *Fetch and open*) fetches the site's last hour, opens it, and
then keeps fetching each new volume while the atmo3d server runs (it checks the archive
every minute, and goes on past midnight in the same folder). A page showing the newest
time goes to each new volume as it comes, the view kept (the page reloads, as the reload
button ↻ does); a page looking at an earlier time stays there and says how many came.

The PPI tool shows it: **Follow new volumes** (on for a live folder), the newest volume
and the last check (or why it failed), and **Stop live fetching**. The fetching stops
with the server, too.

Where the server has no internet (a compute node), fetch live from a login node and
let the viewer follow the folder:

```sh
atmo3d-nexrad KTLX --live                       # the last hour, then each new volume
atmo3d-nexrad KTLX --live --hours 3 --every 120 # from 3 hours ago, checking every 2 min
```

and turn on **Follow new volumes** in the PPI tool of the page showing that folder.
`atmo3d-nexrad KTLX 2013-05-20T19:30 --live` starts from a given time instead; `--every`
is at least 15 s.
`Ctrl-C` stops the command. A live folder grows by about 10 MB a volume (some 3 GB a
day): delete old volumes when done.

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

There is no shipped radar demo run, but any past case can be fetched from the archive:
the 20 May 2013 Moore, Oklahoma tornado, for one, is

```sh
atmo3d-nexrad KTLX 2013-05-20T19:30 2013-05-20T20:30   # about 14 volumes, 120 MB
```

(or *NEXRAD from AWS…* in the run picker). The tests use small synthetic folders
(`tests/synthetic_radar.py`, CfRadial; `tests/synthetic_level2.py`, Level II); see
[Developing](../developing.md).
