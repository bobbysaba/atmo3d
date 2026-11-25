# atmo3d-radar

The radar data type for atmo3d: reads a folder of CfRadial or NEXRAD Level II volumes (one
file per time; `cfradial.py`, `level2.py`) in their native polar geometry, with its field
catalog.

Views, all native (nothing is regridded):

- the map: one sweep (`ppi.py`), a constant height or the column max / min of the sweeps;
- the PPI panel (`panel.py`): the sweep table, the gate and the column under a click;
- cross-sections and constant-height maps through the sampler (`sampler.py`: linear in
  azimuth and range within a sweep, linear in elevation between sweeps, 4/3-earth beams,
  settings `radar_sampling` and `radar_max_gap_km`);
- 3D isosurfaces by marching cubes in (sweep, azimuth, gate) index space (`scene.py`).

Optional regrid (`regrid.py`, `regrid_ui.py`): **Regridded** in the toolbar, after a dialog
confirming the settings, opens the folder as a grid run (`<folder>/regrid_<method>_dx.._dz.._r.._gap..`)
that every grid feature works on, labelled "regridded: method, spacing". Regridded fields are
kept as `.npy` files under the cache folder (at most 4 GB per regridded run).

NEXRAD from AWS (`aws.py`, `aws_ui.py`): the run picker's **NEXRAD from AWS…** and the
`atmo3d-nexrad` command download Level II volumes from the public archive (plain HTTPS,
no AWS libraries) into `<radar_nexrad_dir>/<SITE>_<yyyymmdd>`, a folder that opens as a
radar run.

Live (`live.py`, `live_ui.py`): **Live** in that panel, or `atmo3d-nexrad SITE --live`,
keeps fetching a site's new volumes into the folder; the viewer follows them.

Dealiased velocity (`dealias.py`): `velocity_dealiased`, radial velocity unfolded sweep
by sweep (region based, numpy and scipy.ndimage), wherever the files have `velocity`.
