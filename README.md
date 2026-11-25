# atmo3d

An interactive viewer for [CM1](https://www2.mmm.ucar.edu/people/bryan/cm1/) netCDF
output (`output_format = 2`, one time per file). It runs where your output is (usually
a cluster) and opens in your own browser. It also opens [WoFS and WRF ensembles](https://bobbysaba.com/docs/atmo3d/guides/wofs/)
and [radar volumes](https://bobbysaba.com/docs/atmo3d/guides/radar/): CfRadial, and NEXRAD Level II folders, which it can
download from the AWS archive, live as the radar scans.

- **Map**: layered plan views of any native or derived field (filled, contoured, wind
  arrows or streamlines), at a height, a model level, or a column max / min.
- **Soundings**: click for a skew-T, hodograph, SB / ML / MU parcels, shear, SRH, the
  effective inflow layer, STP / SCP and storm-relative profiles. Compare points, area
  means, times, or a spot that moves with the storm.
- **Storm tracking**: follow an updraft or mesocyclone through time, by hand or
  automatically, and save the track.
- **Cross-sections**, **3D** isosurfaces, vectors and streamlines, and **series** of a
  field reduced over a region (domain, 3D box, a disc around the storm) at every time.
- **Distributions**: every value of a field at a time (histogram, box plot, violin or
  cumulative), for a height, layer, region or range, compared side by side.
- **Figures**: publication figures from any of the above, across times and runs, started
  from a short quick-start form. Each saves with a stand-alone script and data that
  redraw the same image without atmo3d. Plan views and cross-sections can also be saved
  as animated GIFs.

## Quick start

```bash
git clone https://github.com/bobbysaba/atmo3d.git
cd atmo3d
conda env create -f environment.yml && conda activate atmo3d
atmo3d --demo                    # a real CM1 supercell, to try it out
atmo3d /path/to/cm1/run          # your own output
```

Open the URL it prints. On a cluster, start it in a batch or interactive job, or on any
compute node you can log in to when there is no scheduler. Memory depends on the size of
the grid (about 4 GB plus 0.12 GB per million grid points); the
[sizing table](https://bobbysaba.com/docs/atmo3d/help/performance/) has the rows.
Reach it through the SSH tunnel command it prints, or through JupyterHub.

Options (`atmo3d --help` lists them): `--port`, `--address`, `--config` (settings
file), `--cache-gb` and `--workers` (memory and reader processes), `--maxpix` (map
resolution sent to the browser) and `--pdecomp-script`. All but `--address` and
`--config` also have a setting; see [Settings](https://bobbysaba.com/docs/atmo3d/ref/settings/).

## Documentation

Everything else is at **<https://bobbysaba.com/docs/atmo3d/>**:

- [Installing](https://bobbysaba.com/docs/atmo3d/install/): conda or pip, disk space, checking the install
- [Running on a cluster](https://bobbysaba.com/docs/atmo3d/cluster/): Slurm / PBS jobs, SSH tunnels, JupyterHub,
  and what CPUs and memory to ask for ([sizing table](https://bobbysaba.com/docs/atmo3d/help/performance/))
- [Using atmo3d](https://bobbysaba.com/docs/atmo3d/interface/): the window, then a page for each tool
- [Settings](https://bobbysaba.com/docs/atmo3d/ref/settings/): the config file and every setting
- [Writing a data type](https://bobbysaba.com/docs/atmo3d/extend/data-types/): reading another model's or instrument's output

In this repository: [Contributing](CONTRIBUTING.md) (fork, change, test, open a pull
request), [Developing](DEVELOPING.md) (tests, code layout, releases) and
[Changes](CHANGELOG.md) (what is new in each release).

## Requirements

Python 3.11 or newer with the packages in `environment.yml` (conda-forge); tested on
Linux. Any modern browser.

## License and credits

atmo3d is free software under the [GNU General Public License v3.0 or later](LICENSE):
you may use, study, change and share it, and anything you distribute that is built on
it must stay under the same license, with its source.

The pressure-decomposition solver (`atmo3d/pdecomp/pdecomp_solver.py`) was written by Bobby
Saba, rewritten and corrected from earlier code by Dr. John Peters passed along by
Andrew Muehr.
