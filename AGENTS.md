# Notes for coding agents

atmo3d is a monorepo: `packages/core` (the `atmo3d` package: viewer, figures, the
data-type registry) and one package per data type (`packages/cm1`, `packages/wofs`,
`packages/radar`; `packages/example` is the worked example, not part of the app).
People's guide: [CONTRIBUTING.md](CONTRIBUTING.md); developer docs: [DEVELOPING.md](DEVELOPING.md).

- **Adding a data type** (a reader for another model's or instrument's output): follow
  the playbook at <https://bobbysaba.com/docs/atmo3d/extend/agent-playbook/>.
- The core never imports a data-type package, and a data type never needs a core edit:
  if one seems to, stop and say so.
- Tests: `pytest tests/<folder>/<file>` for what you changed (`tests/core/`, and a folder
  per package: `pytest tests/wofs` runs a package's); the full suite (`pytest -n auto`)
  is slow, and on a shared cluster belongs on a compute node: give the user the command
  rather than running it there.
- The documentation is on the site, not in this repository: add a line to
  [CHANGELOG.md](CHANGELOG.md) under *Unreleased* for anything a user sees, and do not
  look for pages to edit.
- Do not push, open pull requests or submit batch jobs unless the user asks.
