# Settings

The first time atmo3d opens in a browser, it asks where your CM1 runs live; the
other settings are pre-filled (from your recent runs and `$SCRATCH`) and can be
changed then or later with the ⚙ button in the top bar (or the *Config file* tab, which
edits the file itself). They are saved in `~/.config/atmo3d/config.toml`
(`$ATMO3D_CONFIG` or `--config` for another file).

| Setting | Default | What it does |
|---|---|---|
| `runs_root` | (required) | folders searched for runs; the run picker starts there |
| `default_run` | none | run opened when no run is given |
| `figures_dir` | `~/atmo3d/figures` | figures go to `<this>/<parent>_<run>/` |
| `exports_dir` | `~/atmo3d/exports` | saved series / tracks / sessions / data exports / parcel sets go to `<this>/<parent>_<run>/series`, `/tracks`, `/sessions`, `/data`, `/parcels` |
| `cache_dir` | `~/.cache/atmo3d` | throwaway files (computed series, time-window swaths, parcel trajectories) |
| `pdecomp_script` | none | your own pressure-decomposition script instead of atmo3d's solver |
| `track_dirs` | `storm_tracks` | where storm track files are found (a plain name: that folder in the run folder or up to 4 above it) |
| `track_patterns` | `{parent}_{name}.csv`, `{name}.csv`, … | track file names tried in each folder |
| `track_motion_window` | auto | minutes of track a storm motion is fitted over (0: centred differences; auto: 0 for CM1, 30 for WoFS) |
| `output_glob` | `cm1out_[0-9]*.nc` | which files are CM1 output |
| `parcel_glob` | `cm1out_pdata*.nc` | which files hold parcel (trajectory) output; several are joined by time |
| `traj_max_interval` | `300` | runs without parcel output get trajectories traced through the 3D winds (no data type uses this now: WoFS has no parcels); turned off when the output comes less often than this many seconds (0: never) |
| `settle_seconds` | `60` | a run still going opens without the file being written: the newest file is left out while it changed within this many seconds or will not open (0: only files that will not open); Reload run adds files finished since |
| `allow_writes_to_output` | off | lets the pressure decomposition write into output files |
| `show_hidden_fields` | off | lists the hidden fields (WoFS's static, land-surface, radiation and time-step fields, and WRF fields atmo3d does not know) under "Hidden" at the end of the field lists |
| `docs_url` | blank | where the documentation is published (an http or https address); set, the field menus end with a link to the derived-fields page |
| `column_stride` | auto | CAPE, CIN, LCL, STP and SCP maps on every n-th column (auto: every column up to 500 × 500 points) |
| `radar_max_gap_km` | auto | radar views off the sweeps (constant heights, sections, columns, 3D) leave a point empty where the two sweeps around it are further apart than this many km; auto: every gap is bridged |
| `radar_sampling` | `linear` | radar values within a sweep: `linear` between the nearest rays and gates, or `nearest` gate |
| `radar_regrid_method`, `radar_regrid_dx`, `radar_regrid_dz`, `radar_regrid_range`, `radar_regrid_max_gap` | linear, 0.5, 0.5, 150, 0 | how a radar run is regridded (Regridded in the toolbar, confirmed in a dialog each time): sampling within a sweep, horizontal and vertical spacing (km), the grid's reach from the radar (km), the widest gap between sweeps bridged (km; 0: all). The regridded run's name holds them, so sessions, figures and exports keep them |
| `cache_gb`, `workers` | auto | from the job's memory and CPUs (restart to apply) |
| `port`, `maxpix` | 5006, 900 | server port (restart to apply), map pixels per axis |
| `login_host` | from the batch job | login node shown in the printed SSH tunnel command |

Each setting can also come from an environment variable `ATMO3D_<NAME>` (lists
separated by `:`) or a command-line flag, which win over the file; the settings window
says when one does. Path settings apply to the next save; save boxes that still point
at the old default folder follow a change. Saving over an existing file asks first.
A figure from several runs has no run folder of its own: choose its folder in *Save as*
(the last one chosen is offered next time).
