# Plan: making atmo3d easy to extend and contribute to

Status (2026-11-20): Phase A done; decision 3 = yes (API versioned); B1, B2 done; B3 next.
Decision 2 taken as recommended (both: packages/example and a scaffold). Decisions 1, 4,
5 still open (4 has a recommendation Bobby has not overruled).
B2 choices made without asking: the example is not installed with the app (not in
environment.yml, the root pyproject or CI's pip install); tests/test_example.py registers
it itself. Its synthetic writer lives in the package (atmo3d_example/synthetic.py), not in
tests/, so a copy carries it.
Start a fresh session with: "read docs-dev/extending-plan.md and continue with B3".

## Goal

Three things a newcomer should be able to do without asking Bobby:

1. **Collaborate**: fork, change, test, open a PR, know who reviews it and what "done" is.
2. **Add a data type** (a new package that reads some model's or instrument's output).
3. **Add a derived field**, at the user level where possible (no fork, no PR).

## What exists today (checked 2026-11-20)

- `CONTRIBUTING.md` (31 lines): set-up, branch and PR rules, which tests to run, and two
  lines on adding a data type.
- `docs/developing.md`: "Adding a data type" and the registration API table, "Adding a
  derived field", "Adding a vector". Written for someone who already knows the code.
- Data types register through the `atmo3d.datatypes` entry point. A package supplies a
  `Model` (about 30-70 lines), a `Catalog` (50-90 lines) and a `Run` or `Source` subclass
  (the real work). CM1, WoFS and radar are the three examples, all in this repo.
- Derived fields are `FieldDef`s inside `core/fields.py::_make_fields`. **Core only: there
  is no way for another package or a user to add one.** Every one has passed the 2b audit
  (analytic test in `tests/test_derived_analytic.py`, a row in `docs/guide/derived-fields.md`
  whose note is the field's `note`; a test checks they agree).
- User config lives in `~/.config/atmo3d/config.toml` (`config.py`). Nothing else is read
  from the user's home.
- Branch protection is on `master` (PR, code-owner review, `test` check). `CODEOWNERS`
  lists Bobby for everything. The tag `v*` ruleset and a second code owner are not set up.

## Decisions Bobby needs to make (the plan branches on these)

1. **User-level derived fields: what format?** (a) a Python file the user writes
   (`~/.config/atmo3d/fields.py`): full power, runs arbitrary code, hard to share safely;
   (b) a declarative TOML of expressions (`expr = "tempc * 9/5 + 32"` over role names, deps
   inferred, numpy functions only, evaluated by a restricted evaluator): safe to share,
   covers most wishes, cannot do column fields or loops; (c) both. **Recommendation: (b)
   first, (a) later if people hit its limits.** Both can ride on the same registration call.
2. **Data-type template: script, example package, or both?** **Recommendation: both.** A
   worked `packages/example` (tiny, real, tested in CI) is the documentation that cannot
   drift, and a `tools/new_datatype.py` copies it under a new name.
3. **How firm is the extension API?** If packages outside this repo will exist, the API
   needs a version (`atmo3d.API_VERSION`, checked at registration) and a rule that 1.x
   does not break it. **Recommendation: yes, say so in the docs; cheap now, costly later.**
4. **Where do user-defined fields show in the menus?** **Recommendation: their own
   "Derived · User" section, labelled as user-defined and unreviewed** (see Phase C).
5. **Figures and sessions** (Bobby is still pondering the upgrade path): decide whether
   a figure or session that uses a user field must carry the field's definition. Needed
   before Phase C ships; may fold into the upgrade-path decision.

## Phase A: collaboration docs (small; one session or less)

1. Rewrite `CONTRIBUTING.md` for a first-time contributor: fork and clone, environment,
   running the right tests (fast ones locally, the full suite in CI; say that heavy work
   goes on a batch node on NCAR systems), branch and PR flow, what review looks for, how
   long it takes, commit style, who owns what.
2. Add `.github/PULL_REQUEST_TEMPLATE.md` (what changed, tests run, baselines moved?) and
   issue templates (bug with the run type and versions; data-type request).
3. Document the maintainer side in `docs/developing.md`: adding a collaborator, the
   CODEOWNERS line for a package's owners, tag protection (`v*`), `enforce_admins` once
   there is a second owner, releases.
4. Link it from the docs site nav ("Contributing"). Do not build mkdocs locally (not
   installed); CI's `mkdocs build --strict` is the check, so keep links relative and valid.

Done when: someone who has never seen the repo can open a correct PR from the docs alone.

## Phase B: adding a data type

**B1. The contract, written down and tested.**
- Document exactly what a `Run` (gridded) or `Source` (non-grid) must provide, which
  capabilities it can claim (`CAPS`), and which core hooks a non-grid run answers
  (`map_plane`, `section_points`, `sample_section`, `build_scene`). The material is in the
  `Run` and `Source` docstrings and `docs/developing.md`; it needs one tutorial-shaped page.
- Write a **conformance check**, `atmo3d.testing.check_datatype(model, folder)`: opens
  the folder through the registry, lists times and fields, reads one field, builds one map
  and one section, checks the catalog roles resolve. A new package's test is then one line.
  It also catches core changes that break an existing package.
- `API_VERSION` and the compatibility rule (decision 3).

**B2. `packages/example` (the worked example).** A tiny but real data type (for example
a "gridded netCDF with named x, y, z, time" reader, so the most common newcomer case is
covered), a synthetic-data generator in the style of `tests/synthetic_radar.py`, its
tests and a `tests/example-tests.txt` for CI. Every file carries comments saying what is
required and what is optional.

**B3. Scaffold.** `tools/new_datatype.py <name>` copies the example into
`packages/<name>` (or an out-of-tree folder with `--out`), renames modules, writes the
`pyproject.toml` and entry point, adds the test list and a commented CODEOWNERS line.

**B4. Docs page "Adding a data type"**, replacing the stub in `developing.md`: a walk
through B2, with two clear paths: *contribute it to this repo* (CODEOWNERS, CI list) or
*publish your own package* (`pip install`, entry point, nothing in this repo changes).
Include what each existing type teaches: CM1 (a grid, many fields), WoFS (ensemble
members as virtual runs), radar (no grid, sampling, optional regrid).

**B5. A playbook for an AI agent that adds a data type** (Bobby's idea, 2026-11-20).
A markdown file shipped in the repo (proposed `docs/agents/add-datatype.md`, linked from
B4's page and from a short top-level `AGENTS.md` that agents read by convention). The user
tells their coding agent "follow this playbook for the files in `<path>`, name `<name>`",
and the agent builds the package and its tests the way core needs them. Written after
B1-B3, because it drives their tools rather than re-describing the code. Contents:
- **Inputs it asks for**: the data path, the package name, contribute here or out-of-tree,
  and which views matter.
- **Inspect, read-only and bounded**: headers only (`ncdump -h`, one or two files), never a
  whole file in memory; list times, dims, staggering, units, coordinates. On shared
  clusters, follow the site's rules (no recursive walks of big trees, heavy work on a
  compute node). It writes what it found to a short `NOTES.md` in the package.
- **Classify**: gridded (`Run`) or not (`Source` plus the hooks), which `CAPS` it can
  claim, and which existing type it is closest to (CM1, WoFS or radar).
- **Build**: run `tools/new_datatype.py`, then fill in `Model.looks`, the `Catalog` (native
  fields, the `refl`/`u`/`v`/`w` roles) and the reads, following the comments in
  `packages/example`. Write a synthetic generator that has the real files' layout (from
  the header, with no real values copied into the repo), and add a `-m real` test that reads the
  user's path.
- **Done** means `check_datatype` passes on the synthetic data and on the real path, the
  package's tests pass, and nothing in `packages/core` changed.
- **Stop and ask** on ambiguous units, staggering or vertical coordinate, role mapping,
  anything that seems to need a core change (report it, do not make it), and before any
  batch job.
- **Report at the end**: every assumption, with the header line it came from, so a
  reviewer can check them; the PR template filled in.
Test it once for real: have an agent follow it on a type we don't have yet (say a
plain gridded netCDF or MPAS sample) and fix the playbook where the agent went wrong.

Done when: a new package passes `check_datatype` in under a day's work for the gridded
case, from the docs alone, and CI fails if core breaks the example. For B5: an agent given
only the playbook and a data path produces a package that passes, without core edits.

## Phase C: derived fields at the user level

**C1. Design spike (report, no code to keep).** Decisions 1, 4 and 5 above, plus:
- Registration point: a second entry-point group (`atmo3d.fields`) so installed packages
  can add fields, and a loader for the user's `~/.config/atmo3d/fields.toml` that feeds
  the same call into `_make_fields` (today it takes only `avail` and `cat`).
- Inputs: role names (`theta`, `qv`, `u`) and native names; the derivative syntax
  (`ddz.w`) must work; pointwise 3D and 2D fields only to start; column fields (layer
  integrals, parcels) are out of scope for user fields.
- A field is offered only when the run has its inputs (already how built-in ones work);
  a user field that cannot be computed shows why instead of failing silently.
- Safety for the TOML form: a whitelisted AST (arithmetic, `np.` functions, comparisons,
  `where`), no attribute access, no imports, no names but the declared inputs. Unit tests
  that try to escape it.
- Trust and review: user fields are never `confirmed`; they are listed apart and marked
  user-defined, and exports and figure bundles record the definition (decision 5) so a
  shared figure says what the field was.

**C2. Implement**: loader, evaluator, registration, the menu section, tests (analytic
answers, as the built-in ones; an unsafe-expression suite; a missing-input case).

**C3. Docs**: a "Your own derived fields" page with recipes (unit conversions, a custom
index, a ratio) and the limits. Also write the **checklist for a repo-level derived
field** (the 2b audit as a contributor's list: the equation and its source, an analytic
test, the `note` and docs row, `CONFIRMED`) so a PR that adds one knows what review needs.

Done when: a user adds a field in one TOML entry, restarts, finds it in the menus, and
a figure made with it records its definition.

## Order and size

| Step | Size | Depends on |
|---|---|---|
| A (collaboration docs) | small | nothing; do first |
| B1 contract + conformance check + API_VERSION | medium | decision 3 |
| B2 example package, B3 scaffold, B4 docs | medium | B1 |
| B5 agent playbook, and one trial run of it | small | B2, B3 |
| C1 spike | small | decisions 1, 4, 5 |
| C2 implement, C3 docs | medium | C1 |

B and C are independent; A first, then either. Suggested: A, B1-B4, C. Each phase ends at a
checkpoint for Bobby, as the earlier plan did.

## Constraints that carry over

- NCAR shared systems: tests in this plan are small and run on a login node; the full
  suite and any heavy run are Bobby's. Show a `qcmd` or `qsub` before submitting.
- No push from the agent (no credentials here); Bobby pushes and runs CI.
- mkdocs is not installed locally; CI is the docs build. Keep docs links valid.
- Docs are on Bobby's own site as well as in `docs/`; keep one source (the repo's
  `docs/`) and let the site link or build from it.

## Open items carried in

- Upgrade path for figures and sessions (on hold, Bobby).
- Collaborator access: forks and PRs first (decided in principle 2026-11-20); add a tag
  ruleset and a second code owner when the first collaborator arrives.
- Receiver geometry for radar (positions not in the files): only if a second receiver
  needs it.
