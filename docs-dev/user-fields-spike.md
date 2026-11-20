# C1 spike: derived fields at the user level

2026-11-20. Report only; the throwaway evaluator prototype lived in the session scratchpad.

## Bobby's decisions

1. **Format: TOML expressions** (`~/.config/atmo3d/fields.toml`). Python files later, if
   people hit the limits, on the same registration call.
2. *(Phase B)*
3. *(Phase B)*
4. **Menus: their own section**, marked as user-defined and unreviewed; never `confirmed`.
5. **Figures and exports record and reuse the definition.** A figure opened where the field
   is missing uses its recorded definition; where the local one differs, the figure's own
   definition is used and a note says so.

## What the code does today (what C2 has to fit)

- `fields._make_fields(avail, cat)` builds every derived `FieldDef`, written with role
  names and bound to the catalog's names by `_bind`. Two callers: `Fields.__init__`
  (viewer, figures, export) and `series._field_def` (the series worker).
- A derived `func(f, c)` gets `f(name)` → a **native in raw units** (qv in kg/kg), or a
  derivative (`ddz.w`) in display units per m. It never gets another derived field:
  `thetae` calls `_tempk` itself.
- The series worker runs in **spawned** processes (`core/pool.py`), so anything only in
  the viewer process (a `--config` path, a figure's definitions) never reaches it unless
  the task carries it.
- `group_options` sorts definitions into kinds main / derived / other / hidden, each with
  a prefix (`Derived · <group>`). Tooltips come from `note`.
- Figures save field names in their layers; `bundle.upgrade_names` and
  `catalog.rename_fields` already walk every place a spec names a field, which is what
  decision 5 needs.

## Design

### The file

```toml
[fields.tempf]
label  = "Temperature"
units  = "°F"
expr   = "tempc * 9/5 + 32"
# optional: group (default "User"), cmap, vrange, diverging, note
```

- Where it lives: a new setting `fields_file` (restart needed), defaulting to `fields.toml`
  beside `config.toml` (`config.config_path()`'s folder, so `$ATMO3D_CONFIG` moves both).
- `ndim` is not written by the user: 3 if any input is 3D, else 2 (2D inputs broadcast
  against 3D ones, as numpy does).
- Names follow Python's rules for names (identifiers) and cannot start with `_`. A name already used for a native or built-in field
  of the run is not offered: the built-in one wins, and the user's is listed as shadowed
  (see "Fields that cannot be computed").

### Inputs

- Role names (`theta`, `qv`, `u`), the data type's native names, **built-in derived
  fields** (pointwise ones: `tempc`, `rh`, `thetae`, ...), earlier user fields (no cycles),
  and derivatives of any of these with the existing syntax (`ddz.w`, `gradh.tempc`).
- **Inputs are in display units**, the numbers the user sees in the viewer (qv in g/kg, p′
  in hPa), not the raw ones built-in funcs get. The evaluator scales natives by their
  `FieldDef.scale`; built-in derived fields and derivatives already come in display units.
  The docs page must say this in its first lines.
- A built-in derived input is computed by calling its `func` with the same fetch, so the
  user `FieldDef`'s `deps` are the union of the natives behind every input. Nothing in
  `Fields` or the series worker changes for this: they already read `deps` and call `func`.
- Out of scope (refused when the file is loaded, with the reason): column fields as inputs
  (`uh25`, `mlcape`, shears), and making a column field. Storm-relative inputs pass
  their `storm` flag on.
- Radar: the existing rule applies. Only pointwise fields are offered on a run with no
  grid, so `ddz.` inputs hide the field there.

### The evaluator (safety)

The user's own file is trusted, but definitions also arrive **inside figures other people
send**, so the evaluator must be safe for any input:

- `ast.parse(mode="eval")`, then every node must be one of a fixed list: numbers,
  names, `+ - * / // % **`, unary `-`/`+`/`~`, comparisons, `and`/`or`/`not`, `&`/`|`,
  `a if c else b`, and calls of functions named in the list (`sqrt exp log log10 abs sin cos tan
  arctan2 hypot minimum maximum where clip isfinite`, no keyword args). No attributes,
  subscripts, comprehensions, lambdas, strings or f-strings.
- Names must be one of the declared function or constant names (`pi`, `e`, `nan`) or a
  resolvable input. No name may start with `_`. Evaluated with `{"__builtins__": {}}`.
- **Every constant becomes a float.** The prototype blocked every escape tried
  (`__import__`, `().__class__`, `open`, subscripts, comprehensions, `np.sum`, keyword
  calls) but let `9**9**9**9` through: integer power hangs the process. As floats it
  overflows to `inf` at once. Expressions over 500 characters are refused.
- Run under `np.errstate(all="ignore")`. The result must be a float array of the
  input's shape (a scalar broadcasts); anything else is an error shown for that field.

### Where they show (decision 4)

- `FieldDef` gains `user`: the normalized definition (a dict: expr, label, units, group,
  where it came from: the user's file, a package or a figure). `derived` stays true;
  `confirmed=False`, but the field is **not** moved to the hidden tier the way unaudited
  built-in fields are.
- `group_options` gains a fifth kind, `user`, prefix `User · ` (`User · User` collapses to
  `User`), after the derived kinds. Labels end with ` (user)`; the tooltip is the note and
  then `= <expr>`.

### Fields that cannot be computed

A field is offered only when the run has its inputs, as built-in fields are. One the
run cannot compute is listed **greyed out** in the User section, with the reason as its
tooltip: "needs qr, which this run lacks", "parse error at column 12", "shadows the
built-in field rh", "uses uh25, a column field". File-level errors (bad TOML) are one
greyed entry plus a log line. Nothing fails silently, and the viewer still opens.

### Packages

Packages register fields through the entry-point group `atmo3d.fields`. The entry point
gives a list of definitions in the same dict schema as the file (data, not `FieldDef`s),
so one loader and one evaluator serve both and the extension API stays 1.0. Their section is
`User · <package>`. Python `FieldDef`s from packages wait for the Python form (decision 1)
and would bump the API to 1.1.

### The series worker

`_make_fields(avail, cat, user=())` takes the definitions as data. The series task carries
the definitions it needs (`task["user_fields"]`), and the worker binds them. It **does not
re-read the file**, because a spawned worker does not see `--config` and would miss a
figure's definitions.

### Figures, sessions, exports (decision 5)

- **Saving**: `write_spec` (and session save) collects the field names in the spec with
  the walker `rename_fields` uses, and records `user_fields: {name: definition}` for the
  user fields among them.
- **Opening**: each recorded definition is added to the runs' `Fields`
  (`Fields.add_user(defn)` → the name it got):
  - missing locally → added under its own name, its section label `(from figure)`;
  - identical locally → nothing to do;
  - different locally → added as `<name>_<6 hex of its hash>`, the spec renamed in place
    (`rename_fields`), and the figure shows a note: "tempf: this figure's definition
    differs from yours in fields.toml; the figure's was used".
  Definitions from a figure live only as long as the figure is open. They are never
  written into the user's file.
- **netCDF export**: a user field's variable gets the attributes `atmo3d_expr`,
  `atmo3d_inputs`, and `comment = "user-defined field, not reviewed"`.

## C2 work list

| Piece | Where |
|---|---|
| loader (file, packages), normalize, validate, cycle check | new `core/userfields.py` |
| evaluator (whitelisted AST, floats, errstate) | `core/userfields.py` |
| bind into `FieldDef`s; `_make_fields(..., user=())`; `FieldDef.user` | `core/fields.py` |
| `user` kind in `group_options`; greyed-out entries with reasons | `core/fields.py`, `viewer/fieldmenu` |
| `fields_file` setting | `config.py`, `docs/settings.md` |
| series task carries definitions | `core/series.py` |
| figures/sessions record and reuse; `Fields.add_user` | `figures/spec/bundle.py`, session save/open |
| export attributes | `core/export.py` |
| tests: analytic answers (°F, a ratio, `ddz.` of a user field), escape suite, missing input, cycle, shadowing, figure round trip (missing / identical / differs), series worker | `tests/test_user_fields.py` |

C3 adds the docs page "Your own derived fields" and the checklist for a repo-level derived
field, plus a line in the changelog.

## Choices made here (Bobby may overrule)

- Inputs in display units, not raw (the user writes what they see).
- Built-in derived fields can be inputs (`tempc * 9/5 + 32` needs it).
- Names that collide with a built-in or native field: the built-in wins, and the user's is
  shown as shadowed (no `user.` prefix on every name).
- Packages register data (dicts), not Python; the API stays 1.0.
- A restart is needed after editing the file (no "reload" button in C2).
