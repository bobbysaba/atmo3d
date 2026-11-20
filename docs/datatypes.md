# Writing a data type

A *data type* teaches atmo3d to read another model's or instrument's output. It is a
Python package of its own, found through an entry point: nothing in the core changes.
It can go two ways:

- **contributed to this repository**, as `packages/<name>/`: installed with atmo3d,
  tested in its CI, reviewed by its owners and the maintainer;
- **published on its own**: an ordinary Python package that users `pip install` next to
  atmo3d. Nothing in this repository changes.

The code is the same either way. The first half of this page is a walk-through, from an
empty folder to a data type that passes the contract check; the second half is the
contract itself: what a data type must provide and what it may (the **extension API**).

## The worked example

`packages/example` (`atmo3d_example`) is a small but real data type, written to be
copied: it reads gridded netCDF with named `x`, `y`, `z` and `time` dimensions, the most
common case. Every file marks what is **REQUIRED** and what is optional:

| File | What it shows |
|---|---|
| `pyproject.toml` | the entry point that registers the data type |
| `src/atmo3d_example/__init__.py` | `register()` |
| `model.py` | the Model: a file pattern for `looks`, a cheap `count`, a demo run |
| `catalog.py` | display defaults, and the roles that make the core's derived fields work |
| `run.py` | the reader: the grid in km, several times to a file (its own `source(t)`), a staggered field, a unit converted on read, fill values made NaN, a field only some files have |
| `synthetic.py` | a tiny run in the same layout with values from formulas, for the tests |

Its tests are `tests/test_example.py`: the contract check on the synthetic run, and
reads checked against the formulas. CI runs them on every core change, so the example
cannot drift from the core. It is not installed with atmo3d (it is no part of the app);
the tests register it themselves.

## Step by step

The steps below make a data type for files of your own, from a copy of the example. Run
them in the atmo3d environment (`conda activate atmo3d`).

**1. Look at your files' headers.** `ncdump -h` on one or two files, never a whole file:
the dimensions, the coordinate variables and their units, how time is written and how
many times a file holds, which fields are staggered (one more point along an axis), the
units of the fields you will map to roles, and fill values. Write down what you find;
every choice below follows from it. On a shared cluster, list folders without recursing
through big trees, and do anything heavy on a compute node.

**2. Start the package.** Pick a short lowercase name (it becomes the key, `atmo3d_<name>`
and `atmo3d-<name>`):

    python tools/new_datatype.py mytype --label "My model"                 # contributed
    python tools/new_datatype.py mytype --label "My model" --out ~/code   # your own

The copy is the example renamed, so its test passes before you change anything:
`pytest tests/test_mytype.py`. Its comments still describe the example's files.

**3. Decide which kind of reader it is.**

| Your data | Subclass | Read next |
|---|---|---|
| a regular grid in x and y, levels at the same height everywhere | `Run` | the example; `atmo3d_cm1` (one time per file, many fields) |
| a grid on a map projection, or levels that follow the terrain | `Run`, with `geo`, `terrain` and `heights()` | `atmo3d_wofs` (WRF output; ensemble members read as runs of their own inside one folder) |
| no grid (radar volumes, soundings, points) | `Source`, and the hooks the views need | `atmo3d_radar` (polar volumes the views sample themselves; an optional regridded run) |

The rest of these steps are for a `Run`; for a `Source`, see
[With no grid](#with-no-grid-source) and copy from `atmo3d_radar`.

**4. Find the runs: `model.py`.** Set `PATTERN` to your files' names, and `TIME` to the
time dimension. `looks()` decides from file names alone and `count()` stays cheap: the
run picker calls them on many folders. See [The Model](#the-model).

**5. Read the grid and the fields: `run.py`.** Change the constants to your files: the
dimension names and their axes (`AXES`, with staggered dimensions marked), the
coordinate variables and the factor to km, and the unit changes (`CONVERT`) that bring a
field into its role's units. If your files are laid out differently (time in the file
name, fields split over files, heights that vary), change `__init__`, `_info` and
`TimeView` the same way. The core reads, caches and destaggers from what `source(t)`
opens. See [The reader](#the-reader).

**6. Name the fields: `catalog.py`.** Map every role your files have (`u`, `v`, `w`,
`theta`, `pres`, `qv`, `refl`...) in the role's units: the derived fields, soundings and
defaults are written by role, so each role mapped is more that works. Give display
defaults to the fields people will look at. See [The field catalog](#the-field-catalog).

**7. Write synthetic data: `synthetic.py`.** A tiny run in your files' layout: the same
dimension and variable names, units, attributes and quirks as the header, with values
from formulas so your tests know the answers. Copy no real values into the repository.

**8. Test it.** The written test runs the contract check on the synthetic run; add tests
of the reads against the formulas (as `tests/test_example.py` does). Then on a real run:

    ATMO3D_MYTYPE_ROOT=/path/to/a/run pytest -m real tests/test_mytype.py

(it reads one or two fields at one time; on a large grid, run it on a compute node).
[Checking it](#checking-it) says what the check covers.

**9. Open it in atmo3d.** Install it (`pip install -e packages/mytype`, or `pip install -e .`
in your own package's folder), start atmo3d and open a run; the run picker finds it.

**10. Ship it**: [contribute it, or publish it](#contributing-it-or-publishing-it).

## The extension API and its version

The extension API is what a data-type package may use:

- the registration calls (the table [below](#the-registration-calls));
- `core.models.Model`, `core.catalog.Catalog` and its roles (`core.catalog.ROLES`);
- `core.run.Source`, `core.run.Run`, `core.run.VarInfo`, and the attributes and hooks
  this page lists;
- the capability names (`core.capabilities.CAPS`);
- `atmo3d.testing.check_datatype`.

Its version is `atmo3d.API_VERSION`, `MAJOR.MINOR` (`"1.0"`), apart from atmo3d's own
version. **The rule:** a minor release only adds to the API; anything a package relies
on changes only with a new major number, and the changelog says what changed. A
data type says which version it is written for, on its Model:

```python
class MyType(Model):
    key, label = "mytype", "My model"
    api = "1.0"
```

When the package loads, `core.models.register` checks it: the major must match the
core's, and the minor must be no newer (a package written for 1.2 needs a core of 1.2
or later). A package that does not fit is left out with a warning, and atmo3d starts
without it (`core.models.SKIPPED` says why). Anything else in atmo3d's code may change
in any release: a package that reaches past this page does so at its own risk.

## The package

What `tools/new_datatype.py mytype` writes:

```
packages/mytype/
  pyproject.toml
  src/atmo3d_mytype/
    __init__.py        register(): the one function the entry point names
    model.py           the Model: is this folder mine, how many times, open it
    catalog.py         the field catalog: names, looks, roles
    run.py             the reader: a Run (grid) or Source (no grid) subclass
    synthetic.py       a small run in the files' layout, for the tests (optional, but
                       the tests need data)
tests/test_mytype.py   the contract check (with --out: in the package's own tests/)
tests/mytype-tests.txt the package's tests, for CI
```

`pyproject.toml` depends on `atmo3d-core` and names `register` in the
`atmo3d.datatypes` entry-point group:

```toml
[project]
name = "atmo3d-mytype"
dependencies = ["atmo3d-core", "netCDF4>=1.7", "numpy>=1.26"]

[project.entry-points."atmo3d.datatypes"]
mytype = "atmo3d_mytype:register"
```

```python
def register():
    from atmo3d.core import models
    from . import catalog  # noqa: F401  (registers the field catalog)
    from .model import MyType
    return models.register(MyType())
```

Installed (`pip install -e packages/mytype`), it is found when atmo3d starts. Packages
load in the alphabetical order of their entry-point names, which is the order
auto-detect tries them in.

### The registration calls

| Call | Adds |
|---|---|
| `core.models.register(Model())` | the data type |
| `core.catalog.register(Catalog(...))` | its field catalog |
| `viewer.panels.register(Tool(...))` | a rail button and its panel; `needs=` names a capability, `click=` handles map clicks while the tool is on |
| `viewer.ext.register_mixin(cls)` | methods added to the Viewer (or the figure editor), for a panel |
| `core.services.provide(name, impl)` | a service shared code reaches without importing the package (CM1's parcels) |

The first two are needed; the rest are for data types that bring tools of their own
(see `atmo3d_radar/__init__.py`).

## The Model

`core.models.Model`: what the run picker and auto-detect ask about a folder. Keep
`looks` and `count` cheap: the picker calls them on many folders.

| | Member | What it is |
|---|---|---|
| needed | `key`, `label` | the data type's key (also `Run.model` and the catalog's key) and its name in lists |
| needed | `api` | the extension API it is written for (`"1.0"`) |
| needed | `run_class` | the reader class (a property, so the module loads only when a run opens) |
| needed | `looks(entries)` | from one folder listing (`os.scandir` entries, no more reads): is it a run of this type? |
| needed | `count(path)` | the number of output times in the folder (0: none) |
| optional | `open(path, **kw)` | the run (default: `run_class(path, **kw)`) |
| optional | `summary(path)` | a few words for the picker ("36 members") |
| optional | `runs(path, entries)` | the runs in a folder that `looks` like one (default: the folder) |
| optional | `parts`, `virtual`, `part_label`, `parts_of`, `canonical`, `folder_label` | runs named inside one folder, not folders on disk (WoFS members, a radar's regridded run): see `atmo3d_wofs/model.py` |
| optional | `make_demo(root)`, `is_demo(path)` | a demo run for `atmo3d --demo <key>` |

## The field catalog

`core.catalog.Catalog(key, natives, roles, ...)`: what the fields are called and how
they show. The core never names a data type's fields: it names **roles** (`"w"`,
`"theta"`, `"refl"`, ...) and asks the catalog which field plays each. Derived fields,
soundings, vectors and the viewer's defaults are written by role, so a data type that
maps a role gets everything built on it.

- `natives`: `{name: (label, units, scale, cmap, (lo, hi), diverging[, group])}`, the
  display defaults of the fields its files hold. A field left out still shows, with a
  label and units from the file.
- `roles`: `{role: field name}` for the roles it has (`core.catalog.ROLES` lists them
  with their units: winds in m/s on scalar points, θ in K, pressure in Pa, mixing ratios
  in kg/kg). Map every one the files have; leave out the rest.
- optional: `other` and `hidden` (fields listed under *Other*, or not at all),
  `renamed` (old names in saved sessions and figures), `kappa` (R/cp of the model's own
  θ), and more: the docstring of `core/catalog.py` lists them all.

The roles decide what works: soundings need `theta`, `pres`, `qv`, `u` and `v`;
tracking needs `w`; perturbation fields need the base-state roles (`theta0`, ...).

## The reader

### On a regular grid: `Run`

Subclass `core.run.Run`. Its `__init__` calls `super().__init__(path, cache_gb, workers,
cache)`, then sets:

| Attribute | |
|---|---|
| `model`, `model_label` | (class attributes) the Model's key, and the type's name in run details |
| `files` | one entry per output time |
| `times` | seconds of each time since the first (strictly increasing) |
| `xh`, `yh` | scalar-point x and y (km, increasing) |
| `z`, `zf` | heights of the scalar and the staggered (w) levels (km above ground) |
| `vars` | `{name: VarInfo}` of the fields: `core.run.var_info(name, variable)` makes one from a netCDF variable whose first dimension is `time` (None for any other), or build `VarInfo(name, long_name, units, ndim, stag)` |
| `var_times` | `{name: frozenset of time indices}` for fields only some times have |
| `attrs`, `nml` | global attributes; the model's namelist (`{}` if none) |
| `umove`, `vmove`, `fcor` | optional: grid motion (m/s), and one Coriolis parameter (1/s) |

and then calls `self._grid_done()`. Reads come for free when each time is a netCDF file
whose fields are `(time, z, y, x)` with one time: the core reads `files[t]` in reader
processes and moves staggered fields (a dimension named in `core.run.STAG_DIMS`) to the
scalar points. Files of another shape: override `source(t)` to return a picklable object
whose `open()` gives a dataset-like view (`d.variables`, `d[name][0]` the field at time
t), as WoFS's `WRFSource` does (it adds the fields WRF splits in two).

Optional class attributes say what the run is: `OFFERS` (capabilities, below),
`terrain` (levels that follow the terrain: then override `heights(t, ref, w)` and
`terrain_height()`, as `WoFSRun`), `geo` (a `core.geo.Geo`: the map projection),
`storm_relative`, `traced_parcels`, `note`, `height_units`.

### With no grid: `Source`

Subclass `core.run.Source` (radar's `PolarRun`). It sets `files`, `times`, `vars`,
`var_times` and `attrs` as above, reads a field in `_read_volume_local(name, t)` (a
float32 array of any shape), and gives the neutral facts `extent` (x0, x1, y0, y1 km),
`ztop` (km), `size_label` and `field_bytes`. Only pointwise derived fields are offered
on it. The map draws through hooks on the run:

| Hook | |
|---|---|
| `map_window(view, maxpix)` | the map's pixels for a view (`win[4]` is the stride) |
| `map_plane(F, name, t, mode, level, win, storm)` | x, y and the `(ny, nx)` values of a field on those pixels |
| `level_text(t, mode, level)` | the level in the map's title |

With `sampled = True` (the run can give values at any x, y, z) it also answers
cross-sections and 3D:

| Hook | |
|---|---|
| `section_points(A, B, max_pts)` | distances, x, y and the direction of a section's points |
| `sample_section(vol, t, x, y, zq)` | `(len(zq), n)` values of a volume along them |
| `build_scene(F, scene, ...)` | a 3D scene (`core.volume3d.build_scene`'s result) |

Series, distributions and figures need a grid. Radar's `RegriddedRun(Run)` is the
pattern for a data type that also offers a gridded version of itself.

## Capabilities

What a run can do is a *capability*; `run.can(name)` is the question the viewer asks.
`core.capabilities.CAPS` lists them. A data type offers some by name in `OFFERS`
(`soundings`, `tracking`, `parcels`, `pdecomp`, `native_polar`); the rest are flags on
the run (`grid`, `sampled`, `terrain`, `geo`, `storm_relative`, `traced_parcels`). An
offered capability is usable only when the run also has its inputs (soundings: the
sounding roles), so a run without them shows why instead of failing.

## Checking it

`atmo3d.testing.check_datatype(key, folder)` opens a folder the way the viewer does and
goes through the contract: the package is registered and says its API version, the Model
finds the folder, the run has times, fields, a grid's coordinates (when it has a grid)
or the hooks (when it has none), the catalog's roles name its fields, the capabilities
are known, a field reads with the right shape, a derived field computes, and a map and a
cross-section build. It lists every problem it finds before failing, and returns a
report of what it checked, with warnings (roles the catalog names that this run lacks,
a folder auto-detect would give to another type).

A new data type's test is then one line on synthetic data its tests write (see
`tests/synthetic_radar.py`), and one on real data, run only when asked:

```python
from atmo3d.testing import check_datatype

def test_contract(synthetic_folder):
    check_datatype("mytype", synthetic_folder)

@pytest.mark.real
def test_contract_real():
    check_datatype("mytype", os.environ["ATMO3D_MYTYPE_ROOT"])
```

It reads one or two fields at one time; on a real run of a large grid, run it on a
compute node. `tests/test_datatype_check.py` runs it on CM1, WoFS and radar, so a core
change that breaks the contract fails there.

## Contributing it, or publishing it

**To contribute it** (in this repository, from `tools/new_datatype.py <name>`): open an
[issue](https://github.com/bobbysaba/atmo3d/issues) first (the *New data type* template), then
a pull request as [Contributing](contributing.md) describes. The scaffold wrote the
package, its test and `tests/<name>-tests.txt`; by hand, add

- in `.github/workflows/tests.yml`: a `<name>` filter (`packages/<name>/**` and its
  tests), its line in *Pick the tests*, and `-e packages/<name>` in the install step;
- `- -e ./packages/<name>` in `environment.yml`, and `"atmo3d-<name>"` in the
  dependencies of the root `pyproject.toml`;
- its owners in `.github/CODEOWNERS` (the scaffold left a commented line).

Review looks for the contract check passing on the synthetic run and on a real one (say
in the pull request which run, and how big), tests of the reads, every role in its
role's units, and no change in `packages/core`. A data type that seems to need a core
change says so in its issue: that is a change to the extension API, made on its own.

**To publish it on its own** (from `--out`): it is an ordinary Python package. Users
`pip install` it into the environment atmo3d is installed in, and its entry point does
the rest; nothing in this repository changes. Keep `Model.api` at the version you test
against: a core of another major version leaves the package out with a warning rather
than failing on it.
