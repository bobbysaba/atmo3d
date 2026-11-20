# Contributing to atmo3d

Thank you for helping. This page takes you from nothing to a merged pull request: set
up, change, test, open the pull request, and what review looks for. It is also on the
documentation site as *Contributing*.

## Before you start

- **Ask first for anything big.** Open an [issue](https://github.com/bobbysaba/atmo3d/issues)
  for a bug, a new data type, or a change that touches many files, and say what you have
  in mind. A short conversation first saves a pull request that has to be redone. Small
  fixes (a typo, a wrong label, a clear bug with a one-line cause) can go straight to a
  pull request.
- **Questions** go in an issue too; there is a blank template for them.
- **Licence.** atmo3d is GPL-3.0-or-later ([LICENSE](LICENSE)). By opening a pull
  request you agree that your contribution is licensed under the same terms.

## How the repository is laid out

A monorepo: `packages/core` (import name `atmo3d`: the viewer, figures, caching and the
data-type registry) and one package per data type: `packages/cm1` (`atmo3d_cm1`),
`packages/wofs` (`atmo3d_wofs`) and `packages/radar` (`atmo3d_radar`). `tests/`, `docs/`
and `tools/` are shared. The core never imports a data-type package; a data type plugs
in through an entry point. The file-by-file layout is in
[Developing](docs/developing.md#layout).

## Set up

1. **Fork** the repository on GitHub (the *Fork* button), then clone your fork and add
   this repository as `upstream`, so you can stay current with it:

        git clone https://github.com/<you>/atmo3d.git
        cd atmo3d
        git remote add upstream https://github.com/bobbysaba/atmo3d.git

2. **Make the environment.** It pins the versions atmo3d is tested with and installs the
   four packages editable, so your changes take effect without reinstalling:

        conda env create -f environment.yml
        conda activate atmo3d

   After `environment.yml` changes: `conda env update -f environment.yml --prune`.

3. **Check it works:** `atmo3d --demo` opens a real CM1 supercell, and
   `pytest tests/core/test_settings.py` should pass in well under a minute.

## Make a change

1. Start from an up-to-date `master` and branch:

        git switch master
        git pull upstream master
        git switch -c short-name-of-change

2. Keep each commit to one step that works on its own. A pull request may hold several.
3. **Change the documentation with the code.** If what the user sees changes, change the
   page in `docs/` that describes it in the same commit, and add a line under
   *Unreleased* in [Changes](docs/changelog.md).
4. If your branch falls behind `master`, rebase it (`git pull --rebase upstream master`)
   rather than merging `master` into it.

### Commit messages

The subject says what changed, in plain words, starting with the area when that helps:

    Radar: receiver fields described by rule, so a second receiver is listed like the first
    Field menus show a field's note as its tooltip

No full stop at the end. Add a body (after a blank line) when the reason is not obvious
from the subject.

## Test

The suite runs on synthetic data written by `tests/synthetic.py`,
`tests/synthetic_wofs.py` and `tests/synthetic_radar.py`, whose answers are known in
advance; it needs no data of your own. The core's tests are in `tests/core/`, each
data-type package's in its own folder (`tests/cm1/`, `tests/wofs/`, `tests/radar/`,
`tests/example/`). What to run depends on what you changed:

| You changed | Run locally |
|---|---|
| one data-type package | its folder, e.g. `pytest tests/wofs` |
| a test you are writing | that file, `pytest tests/core/test_x.py -k name` |
| `packages/core`, or the shared files in `tests/` | the tests near your change; CI runs the whole suite |

CI (GitHub Actions) repeats this on every pull request: a core change runs every test,
a package change runs that package's folder. The check is called `test`, and it must
pass before a pull request can merge. You can run the whole suite yourself with
`pytest -n auto`: it runs the tests in parallel, a worker per CPU you have (at most 8),
so it is as fast as the machine allows; plain `pytest` runs them one at a time.

- **On a shared cluster** (NSF NCAR's Derecho or Casper, for example), run the tests on
  a compute node, not a login node: they start reader processes and draw figures. Use an
  interactive job (`qinteractive` on NCAR systems) or a batch command such as
  `qcmd -A <project> -- pytest -n auto`.
- **Image tests** (`tests/core/test_images.py`) compare figures with the PNGs in
  `tests/baseline/`. Do not rewrite baselines unless your change is meant to move a
  figure; when it is, say so in the pull request. How to rewrite them is in
  [Developing](docs/developing.md#tests).
- **A new feature needs a test**, and a fix a test that failed before it. For a derived
  field, the test checks it against an answer worked out by hand (see
  `tests/core/test_derived_analytic.py`); the rest of what its review needs is the
  [checklist](docs/developing.md#checklist-for-a-new-derived-field). A field only you
  need can stay [your own](docs/guide/user-fields.md), with no pull request.

## Open a pull request

1. Push the branch to your fork: `git push -u origin short-name-of-change`.
2. On GitHub, open a pull request from it into `bobbysaba/atmo3d` `master`. The form asks
   what changed, which tests you ran, and whether image baselines moved.
3. Nobody pushes to `master` directly, maintainers included: every change arrives by pull
   request, with the `test` check passing and a code owner's approval.

### Who reviews

`.github/CODEOWNERS` names who must approve a change to each part of the repository.
GitHub requests their review automatically when the pull request opens. Today the
maintainer, Bobby Saba (@bobbysaba), owns everything; a data-type package can gain
owners of its own, who then review changes inside it.

### What review looks for

- **It is right.** Physics and numbers are checked against a source (an equation with a
  reference, a hand-worked case, a test with a known answer). Say where yours come from.
- **It is tested** as above, and the existing tests still pass.
- **It stays in its place.** Core code does not import a data-type package; a data type
  adds itself through the registration API
  ([Writing a data type](docs/datatypes.md#the-registration-calls)) instead of editing the core.
- **The documentation matches**, and the changelog has a line for anything a user notices.
- **It is no bigger than it needs to be.** Unrelated clean-ups go in a pull request of
  their own.

### How long it takes

atmo3d has one maintainer, and reviews happen as time allows. If a pull request has had
no response after a week, add a comment to it as a reminder. Expect questions or requests
for changes; push new commits to the same branch to answer them, and the pull request
updates itself.

### When it is done

A pull request is ready to merge when the `test` check passes, the code owners have
approved it, and every review comment is answered. The maintainer merges it.

## Adding a data type

A data type (a reader for another model's or instrument's output) is a package of its
own under `packages/<name>/`, with a `pyproject.toml` and an entry point in the
`atmo3d.datatypes` group; no core file changes. Start it with

    python tools/new_datatype.py <name> --label "<Its name>"

which copies the worked example (`packages/example`) under the new name, with its tests
and test list, and prints the few lines left to add by hand (CI, `environment.yml`, the
root `pyproject.toml`, yourself as its owner in `.github/CODEOWNERS`). Then follow
[Writing a data type](docs/datatypes.md#step-by-step). CM1, WoFS and radar are the
examples of what more a data type can do.
