# atmo3d-radar

The radar data type for atmo3d: reads a folder of CfRadial volumes (one file per time)
in their native polar geometry, with its field catalog.

Views, all native (nothing is regridded):

- the map: one sweep (`ppi.py`), a constant height or the column max / min of the sweeps;
- the PPI panel (`panel.py`): the sweep table, the gate and the column under a click;
- cross-sections and constant-height maps through the sampler (`sampler.py`: linear in
  azimuth and range within a sweep, linear in elevation between sweeps, 4/3-earth beams,
  settings `radar_sampling` and `radar_max_gap_km`);
- 3D isosurfaces by marching cubes in (sweep, azimuth, gate) index space (`scene.py`).
