# Installing atmo3d

atmo3d is a Python web app. It runs wherever your CM1 output is (usually a cluster),
and you look at it in your own browser. It needs Python 3.11 or newer and the packages
listed in `environment.yml`.

## With conda (recommended)

`environment.yml` pins the conda-forge versions atmo3d is tested with. Use
[Miniforge](https://github.com/conda-forge/miniforge), or any conda / mamba you already
have:

```bash
git clone https://github.com/bobbysaba/atmo3d.git
cd atmo3d
conda env create -f environment.yml      # once; about 2.7 GB
conda activate atmo3d
atmo3d --demo                           # check it works (see below)
```

This installs atmo3d in editable mode, so `git pull` updates it. After a pull that
changes `environment.yml`, run `conda env update -f environment.yml --prune`.

**Disk space.** Miniforge plus the environment take about 4 GB. Many clusters give home
folders a small quota. If yours does, install Miniforge (or put the environment, with
`conda env create -p /path/to/envs/atmo3d -f environment.yml`) in a work or project
folder instead.

**Clusters with a site conda.** If your site provides conda through a module
(`module load conda` or similar), you can use that instead of Miniforge. Creating the
environment from `environment.yml` is the same either way.

## With pip

Into an existing environment (Python 3.11 or newer):

```bash
git clone https://github.com/bobbysaba/atmo3d.git
pip install -e ./atmo3d/packages/core -e ./atmo3d/packages/cm1 -e ./atmo3d/packages/wofs -e ./atmo3d/packages/radar
pip install pytest websocket-client   # for the tests and the browser tests
```

The versions in `pyproject.toml` are looser than the pins in `environment.yml`. If
something misbehaves, try the conda environment first. netCDF4 and numba ship binary
wheels for common platforms. If pip has to build them from source, conda is the easier
route.

## On your own computer

atmo3d runs on Linux, macOS and Windows, so a run small enough for your machine can be
viewed there: install as above, start `atmo3d /path/to/run` and open
`http://localhost:5006/atmo3d`. No job or tunnel is needed.

- **Memory and CPUs** are taken from the machine: the 3D cache is about 40% of its
  memory and the reader processes one per CPU, at most 16 (`--cache-gb` and
  `--workers` to change them). Size a run by its grid as in the
  [cluster table](hpc.md#resources): 16 GB is comfortable up to about 512 × 512 × 100,
  and larger grids still work, read in parts ([Grids larger than the job](hpc.md#grids-larger-than-the-job)).
- **macOS and Windows** have no `/dev/shm`: the reader processes hand their reads back
  through the system's temporary folder, so it needs free disk space of about a 3D
  field per reader at once.
- **Windows**: `atmo3d.sh` is a bash script; run `atmo3d` (or `python -m atmo3d`) from
  an Anaconda / Miniforge prompt instead.

## 3D scene figures and OpenGL

3D scene figures ([3D scenes](guide/figures-panels.md#3d-scenes)) are rendered off-screen
by PyVista (VTK), installed with the rest. VTK draws with the machine's OpenGL library
(`libGL`/`libEGL`), which cluster login and compute nodes usually have even without a
display. On a machine with none, everything else works and a 3D scene shows an error in
the preview; install the system's Mesa OpenGL libraries (e.g. `libgl1-mesa-dri`,
`mesa-libGL`) or ask your site's help desk.

## Check the install

```bash
atmo3d --demo
```

This opens the demo run, a real CM1 supercell that ships with the repository
(`demo_data/supercell`): CM1 r21.1's supercell case (Weisman and Rotunno 2000,
quarter-circle hodograph) at 1 km grid spacing, with 44 stretched levels, 2 h of output
every 10 min and parcels, cut to an 80 × 80 km box around the storms. It is copied to the
cache folder once and the viewer starts on it. A pip install has no copy; clone the
repository to get it. Open the URL it
prints. On a cluster, see [Running on a cluster](hpc.md) for how to reach it from your
laptop. `atmo3d --demo wofs` opens a small synthetic WoFS ensemble instead
([WoFS](guide/wofs.md)).

To run the tests as well, see [Developing](developing.md).
