# Contributing to atmo3d

atmo3d is a monorepo: `packages/core` (the viewer, figures, caching, and the data-type
registry) and one package per data type (`packages/cm1`, `packages/wofs`, ...).

## Set up

    conda env create -f environment.yml && conda activate atmo3d
    pip install --no-deps -e packages/core -e packages/cm1 -e packages/wofs -e packages/radar

## Branch and pull request

1. Branch from `master` (`git switch -c my-change`); keep commits small, one step each.
2. Push the branch and open a pull request into `master`. Nobody pushes to `master`
   directly: it needs a pull request and the review of the code owners (`.github/CODEOWNERS`).
3. A change to `packages/core` is reviewed by the core owner; a change inside a data-type
   package by that package's owners.

## Which tests to run

- Changed a data-type package: run its tests, e.g. `pytest tests/test_wofs.py` for WoFS
  (the files each package owns are listed in `tests/<package>-tests.txt`).
- Changed the core, `tests/conftest.py` or `tests/synthetic.py`: run everything, `pytest`.
- CI repeats this: a core change runs all tests, a package change only its own.
- Image tests (`tests/test_images.py`) compare against `tests/baseline/`; do not rewrite
  baselines unless the change is meant to move them.

## Adding a data type

Add a folder `packages/<name>/` with its own `pyproject.toml` and an entry point in the
`atmo3d.datatypes` group (see `docs/developing.md`); no core file changes.
