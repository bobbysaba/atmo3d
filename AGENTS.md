# Notes for coding agents

atmo3d is a monorepo: `packages/core` (the `atmo3d` package: viewer, figures, the
data-type registry) and one package per data type (`packages/cm1`, `packages/wofs`,
`packages/radar`; `packages/example` is the worked example, not part of the app).
People's guide: [CONTRIBUTING.md](CONTRIBUTING.md); developer docs: `docs/developing.md`.

- **Adding a data type** (a reader for another model's or instrument's output): follow
  the playbook [docs/agents/add-datatype.md](docs/agents/add-datatype.md).
- The core never imports a data-type package, and a data type never needs a core edit:
  if one seems to, stop and say so.
- Tests: `pytest tests/<file>` for what you changed (`tests/<package>-tests.txt` lists a
  package's); the full suite is slow, and on a shared cluster belongs on a compute node:
  give the user the command rather than running it there.
- Change the docs (`docs/`) with the code, and add a line to `docs/changelog.md` under
  *Unreleased* for anything a user sees.
- Do not push, open pull requests or submit batch jobs unless the user asks.
