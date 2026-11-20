"""User-defined derived fields: TOML expressions (docs/guide/user-fields.md).

A definition is a small dict (from the fields_file setting's [fields.<name>] tables, an
installed package's `atmo3d.fields` entry point, or a saved figure or session):

    name, label, units, expr        (expr: an expression over input names)
    group, cmap, vrange, diverging, note      (optional)
    source                          ("file", "package <name>", "figure"; set here)

`expr` is evaluated by a restricted evaluator (`compile_expr`): numbers, input names,
arithmetic, comparisons, `&` `|` `~` and the functions in FUNCS; nothing else (no
attributes, subscripts, strings, keyword arguments or builtins), because definitions
also arrive inside figures other people send.  Every number is a float, so `9**9**9**9`
overflows to inf instead of hanging.

Inputs are in **display units** (what the viewer shows: qv in g/kg): role names
(core.catalog.ROLES), the run's native names, built-in derived fields that are not column
fields, other user fields, and derivatives of natives or roles (`ddz.w`).

`bind` turns definitions into FieldDefs for one run (or the series worker), and says why
each one it cannot make is left out ("off": shown greyed out in the field menus)."""

import ast
import hashlib
import os
import re
import threading
import tomllib

import numpy as np

FUNCS = {n: getattr(np, n) for n in (
    "sqrt", "exp", "log", "log10", "abs", "sin", "cos", "tan", "arcsin", "arccos",
    "arctan", "arctan2", "hypot", "minimum", "maximum", "where", "clip", "isfinite",
    "floor", "ceil", "sign")}
CONSTS = {"pi": np.pi, "e": np.e, "nan": np.nan, "inf": np.inf}
MAX_EXPR = 500
KEYS = ("label", "units", "expr", "group", "cmap", "vrange", "diverging", "note")
USER_MARK = " (user)"
FIGURE_MARK = " (from figure)"
ENTRY_POINTS = "atmo3d.fields"
NOT_READ = "Fields not read"  # (the greyed entry of a file or package that failed)

_ALLOWED = (
    ast.Expression, ast.BinOp, ast.UnaryOp, ast.Compare, ast.Call, ast.Name,
    ast.Load, ast.Constant,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.Mod, ast.FloorDiv,
    ast.USub, ast.UAdd, ast.Invert, ast.BitAnd, ast.BitOr,
    ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Eq, ast.NotEq)
_DERIV = re.compile(r"\b(ddz|ddx|ddy|gradh)\.([A-Za-z]\w*)")
_SEP = "__d__"  # (a derivative's dot, while parsed: ddz.w -> ddz__d__w)
_NAME = re.compile(r"[A-Za-z]\w*\Z")


class Unsafe(ValueError):
    """An expression the evaluator refuses."""


def _input_name(ident):
    op, sep, base = ident.partition(_SEP)
    return f"{op}.{base}" if sep else ident


class _Floats(ast.NodeTransformer):
    """Every number as a numpy float, by a name of its own (_c0, _c1, ...; compile()
    takes no numpy constants): numpy's power overflows to inf where Python's integer one
    would hang and its float one raise.  No expression can name them (no _ names)."""

    def __init__(self):
        self.values = {}

    def visit_Constant(self, node):
        name = f"_c{len(self.values)}"
        self.values[name] = np.float64(node.value)
        return ast.copy_location(ast.Name(name, ast.Load()), node)


def compile_expr(text):
    """(code, input names) of expression `text` (code: for evaluate); Unsafe (a
    ValueError) when it uses anything but the allowed syntax, or is not an expression."""
    if not isinstance(text, str) or not text.strip():
        raise Unsafe("expr is empty")
    if len(text) > MAX_EXPR:
        raise Unsafe(f"expr is longer than {MAX_EXPR} characters")
    if _SEP in text:
        raise Unsafe(f"names may not contain {_SEP}")
    src = _DERIV.sub(lambda m: f"{m[1]}{_SEP}{m[2]}", text.strip())
    try:
        tree = ast.parse(src, mode="eval")
    except SyntaxError as e:
        raise Unsafe(f"not an expression (column {e.offset}): {e.msg}") from None
    names = []
    for n in ast.walk(tree):
        if isinstance(n, (ast.BoolOp, ast.Not, ast.IfExp)):
            raise Unsafe("and, or, not, if-else do not work on fields: use &, |, ~ "
                         "(with brackets) and where(cond, a, b)")
        if not isinstance(n, _ALLOWED):
            raise Unsafe(f"not allowed in an expression: {type(n).__name__.lower()}")
        if isinstance(n, ast.Constant) and (isinstance(n.value, bool)
                                            or not isinstance(n.value, (int, float))):
            raise Unsafe("only numbers may be written as values")
        if isinstance(n, ast.Call):
            if not isinstance(n.func, ast.Name) or n.func.id not in FUNCS:
                what = n.func.id if isinstance(n.func, ast.Name) else "that"
                raise Unsafe(f"unknown function {what} (allowed: {', '.join(FUNCS)})")
            if n.keywords or any(isinstance(a, ast.Starred) for a in n.args):
                raise Unsafe("functions take plain arguments only")
        if isinstance(n, ast.Name):
            if n.id.startswith("_"):
                raise Unsafe(f"names may not start with _: {n.id}")
            if n.id in FUNCS and not _called(tree, n):
                raise Unsafe(f"{n.id} is a function: call it")
            if n.id not in FUNCS and n.id not in CONSTS:
                names.append(_input_name(n.id))
    floats = _Floats()
    tree = ast.fix_missing_locations(floats.visit(tree))
    return ((compile(tree, "<user field>", "eval"), floats.values),
            tuple(dict.fromkeys(names)))


def _called(tree, name):
    return any(isinstance(n, ast.Call) and n.func is name for n in ast.walk(tree))


def evaluate(code, get):
    """The value of compiled expression `code`, its input names fetched by get(name)."""
    code, numbers = code
    env = dict(FUNCS, **CONSTS, **numbers)

    class Names(dict):
        def __missing__(self, k):
            if k.startswith("_"):  # (never an input: compile_expr refuses them)
                raise KeyError(k)
            return get(_input_name(k))

    with np.errstate(all="ignore"):
        return eval(code, {"__builtins__": {}}, Names(env))  # noqa: S307 (checked AST)


# ------------------------------------------------------------------ definitions
def normalize(name, raw, source):
    """The definition dict of table `raw` named `name`; its "error" says why it is
    unusable (it is still listed, greyed out)."""
    d = dict(name=str(name), source=source, error="")
    raw = raw if isinstance(raw, dict) else {}
    d.update(label=str(raw.get("label") or name), units=str(raw.get("units") or ""),
             expr=raw.get("expr"), group=str(raw.get("group") or ""),
             cmap=str(raw.get("cmap") or "viridis"), vrange=raw.get("vrange"),
             diverging=bool(raw.get("diverging", False)), note=str(raw.get("note") or ""))
    bad = sorted(set(raw) - set(KEYS) - {"name", "source", "error"})
    if not isinstance(raw, dict) or not raw:
        d["error"] = "not a table of settings"
    elif not _NAME.match(d["name"]) or d["name"] in FUNCS or d["name"] in CONSTS:
        d["error"] = "a field's name is letters, digits and _, starting with a letter, " \
                     "and not a function's name"
    elif bad:
        d["error"] = f"unknown setting {', '.join(bad)} (known: {', '.join(KEYS)})"
    elif not isinstance(d["expr"], str):
        d["error"] = "expr is missing (a text: the expression)"
    else:
        vr = d["vrange"]
        if vr is not None:
            ok = (isinstance(vr, (list, tuple)) and len(vr) == 2
                  and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in vr))
            if ok:
                d["vrange"] = [float(vr[0]), float(vr[1])]
            else:
                d["error"] = "vrange is two numbers, [low, high]"
        if not d["error"]:
            try:
                compile_expr(d["expr"])
            except Unsafe as e:
                d["error"] = str(e)
    if d["error"] or not isinstance(d["expr"], str):
        d["expr"] = str(d["expr"] or "")
    return d


def canonical(expr):
    """Expression text written one way (spacing and brackets as Python prints it)."""
    try:
        return ast.unparse(ast.parse(_DERIV.sub(lambda m: f"{m[1]}{_SEP}{m[2]}",
                                                str(expr).strip()), mode="eval"))
    except (SyntaxError, ValueError):
        return " ".join(str(expr).split())


def same(a, b):
    """Whether definitions a and b give the same field (expression and units)."""
    return (canonical(a.get("expr", "")) == canonical(b.get("expr", ""))
            and a.get("units", "") == b.get("units", ""))


def digest(d):
    text = f"{canonical(d.get('expr', ''))}|{d.get('units', '')}"
    return hashlib.sha256(text.encode()).hexdigest()


def chain_digest(name):
    """A digest of user field `name`'s definition and those of the user fields it uses
    (cached results, such as a series', go stale when any changes); "" if not one."""
    defs = {d["name"]: d for d in current()}
    parts, todo, seen = [], [name], set()
    while todo:
        n = todo.pop()
        d = defs.get(n)
        if n in seen or d is None or d["error"]:
            continue
        seen.add(n)
        parts.append(f"{n}={digest(d)}")
        try:
            todo.extend(compile_expr(d["expr"])[1])
        except Unsafe:
            pass
    return hashlib.sha256("|".join(sorted(parts)).encode()).hexdigest() if parts else ""


def recorded(d):
    """Definition d as saved in a figure, session or export (no runtime keys)."""
    return {k: d[k] for k in ("label", "units", "expr", "group", "cmap", "vrange",
                              "diverging", "note")
            if d.get(k) not in (None, "") and not (k == "diverging" and not d[k])}


def fields_path():
    """The user's fields file: the fields_file setting, or fields.toml beside the
    config file."""
    from .. import config
    p = config.get("fields_file")
    return config.expand(p) if p else os.path.join(os.path.dirname(config.config_path()),
                                                   "fields.toml")


def read_file(path):
    """(definitions, problem) of a fields file: missing is no definitions, no problem."""
    if not os.path.isfile(path):
        return [], ""
    try:
        with open(path, "rb") as f:
            doc = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as e:
        return [], f"{path}: {e}"
    tables = doc.get("fields", {})
    if not isinstance(tables, dict):
        return [], f"{path}: [fields] must be a table of [fields.<name>] tables"
    return [normalize(n, t, "file") for n, t in tables.items()], ""


def read_packages():
    """Definitions from installed packages' `atmo3d.fields` entry points (a list of
    dicts with a "name", or a function returning one), and problems."""
    from importlib.metadata import entry_points
    out, problems = [], []
    for ep in sorted(entry_points(group=ENTRY_POINTS), key=lambda e: e.name):
        try:
            got = ep.load()
            got = got() if callable(got) else got
            for raw in got:
                raw = dict(raw)
                out.append(normalize(raw.pop("name", "?"), raw, f"package {ep.name}"))
        except Exception as e:  # (a broken package never stops the viewer)
            problems.append(f"{ENTRY_POINTS} entry point {ep.name}: {e}")
    return out, problems


_lock = threading.Lock()
_state = {"loaded": None, "problems": [], "figure": {}, "notes": [], "bound": set()}


def loaded():
    """The definitions this process has (the user's file, then packages; a name given
    twice: the first), read once."""
    with _lock:
        if _state["loaded"] is None:
            defs, problem = read_file(fields_path())
            more, problems = read_packages()
            seen, out = set(), []
            for d in defs + more:
                if d["name"] in seen:
                    continue
                seen.add(d["name"])
                out.append(d)
            _state["loaded"] = out
            _state["problems"] = ([problem] if problem else []) + problems
            for p in _state["problems"]:
                import logging
                logging.getLogger("atmo3d").warning("user fields: %s", p)
        return list(_state["loaded"])


def problems():
    """Why the fields file or a package's definitions could not be read."""
    loaded()
    return list(_state["problems"])


def reset():
    """Forget what was read (tests; a changed fields_file)."""
    with _lock:
        _state["loaded"], _state["problems"], _state["figure"] = None, [], {}
        _state["notes"], _state["bound"] = [], set()


def current():
    """Every definition in use: loaded() then those adopted from figures."""
    out = loaded()
    names = {d["name"] for d in out}
    return out + [d for n, d in _state["figure"].items() if n not in names]


def by_name(name):
    return next((d for d in current() if d["name"] == name), None)


def adopt(doc):
    """Take in the definitions recorded in saved figure or session `doc`
    ("user_fields": {name: definition}), renaming its fields in place where the local
    definition differs.  They stay in use (current()) until atmo3d stops, and are never
    written to the user's file.  Returns notes for the user, kept for take_notes too."""
    from .catalog import rename_fields
    rec = doc.get("user_fields") if isinstance(doc, dict) else None
    if not isinstance(rec, dict):
        return []
    notes, table = [], {}
    for name, raw in rec.items():
        d = normalize(name, raw, "figure")
        if d["error"]:
            notes.append(f"{name}: its recorded definition is unusable ({d['error']})")
            continue
        mine = by_name(name)
        if mine is not None and same(mine, d):
            continue
        if mine is not None:
            new = f"{name}_{digest(d)[:6]}"
            d = dict(d, name=new)
            table[name] = new
            notes.append(f"{name}: this figure's definition ({d['expr']}) differs from "
                         f"yours ({mine['expr']}); the figure's was used, as {new}")
        with _lock:
            _state["figure"][d["name"]] = d
    if table:
        rename_fields(doc, table)
        doc["user_fields"] = {table.get(n, n): v for n, v in rec.items()}
    with _lock:
        _state["notes"].extend(notes)
    return notes


def take_notes():
    """The notes adopt() gave since last asked (for the page that opened the file)."""
    with _lock:
        out, _state["notes"] = _state["notes"], []
    return out


def record(doc):
    """{name: definition} of the user fields saved figure or session `doc` names (under
    the field keys core.catalog.rename_fields walks): what saving it records.  Only
    definitions a run has made into a field (bind): one that shadows a built-in field
    never is, so a figure of the built-in one does not record it."""
    from .catalog import field_names_in
    names = field_names_in(doc)
    with _lock:
        bound = set(_state["bound"])
    return {d["name"]: recorded(d) for d in current()
            if d["name"] in names and d["name"] in bound and not d["error"]}


# ------------------------------------------------------------------ binding
class _Off(Exception):
    """A definition that cannot be made for this run, and why."""


def bind(defs, avail, cat, builtins, scales=None, ndims=None):
    """(FieldDefs, off) of definitions `defs` for fields `avail` of a data type with
    catalog `cat` and built-in derived FieldDefs `builtins` (already bound to the
    catalog's names).  scales / ndims: {native: display scale / ndim} (default: the
    catalog's look, 3D).  off: [(definition, why)] of those that cannot be made, e.g.
    an input the run lacks.  A definition named like a native or built-in field is off
    (the built-in one wins)."""
    from .catalog import ROLES
    from .fields import FieldDef, split_deriv
    avail = avail if isinstance(avail, dict) else {n: None for n in avail}
    scales, ndims = dict(scales or {}), dict(ndims or {})
    built = {d.name: d for d in builtins}
    file_first = getattr(cat, "file_first", frozenset())
    specs = {d["name"]: d for d in defs}
    made, off, busy = {}, {}, []

    def scale(n):
        if n not in scales:
            try:
                scales[n] = float(cat.look(n)[2] or 1.0)
            except Exception:
                scales[n] = 1.0
        return scales[n]

    def ndim(n):
        if n not in ndims:
            info = avail.get(n)
            ndims[n] = int(getattr(info, "ndim", 3) or 3)
        return ndims[n]

    def native(n):
        """The native field input n names: a role first (as the built-in fields bind
        them: CM1's "w" is winterp), else a native of that name."""
        if n in ROLES:
            got = cat.name(n)
            if got in avail:
                return got
        return n if n in avail else None

    def resolve(n):
        """(get(f, c), deps, ndim, storm) of input n."""
        op, base = split_deriv(n)
        if op:
            nat = native(base)
            if nat is None:
                if base in built or base in specs:
                    raise _Off(f"uses {n}: derivatives of derived fields cannot be inputs")
                raise _Off(f"needs {base}, which this run lacks")
            if op == "ddz" and ndim(nat) != 3:
                raise _Off(f"uses {n}: {base} is 2D")
            key = f"{op}.{nat}"
            return (lambda f, c: f(key)), (key,), ndim(nat), False
        if n in specs and n not in built and n not in avail:
            d = make(n)
            return d.func, d.deps, d.ndim, d.storm
        nat = native(n)
        if n in built and (nat is None or n in file_first):
            b = built[n]
            if b.column:
                raise _Off(f"uses {n}, a column field (column fields cannot be inputs)")
            return b.func, b.deps, b.ndim, b.storm
        if nat is not None:
            s = scale(nat)
            return (lambda f, c: f(nat) * s), (nat,), ndim(nat), False
        if n in ROLES:
            raise _Off(f"needs {n} ({ROLES[n]}), which this run lacks")
        raise _Off(f"needs {n}, which this run lacks")

    def make(name):
        if name in made:
            return made[name]
        if name in off:
            raise _Off(off[name])
        if name in busy:
            raise _Off("its inputs use it in turn: " + " → ".join(busy + [name]))
        d = specs[name]
        busy.append(name)
        try:
            if d["error"]:
                raise _Off(d["error"])
            if name in avail or name in built:
                raise _Off(f"shadows the built-in field {name}; give it another name")
            code, names = compile_expr(d["expr"])
            if not names:
                raise _Off("uses no field")
            parts = {n: resolve(n) for n in names}
        except _Off as e:
            off[name] = str(e)
            raise
        finally:
            busy.pop()
        getters = {n: p[0] for n, p in parts.items()}
        deps = tuple(dict.fromkeys(x for p in parts.values() for x in p[1]))
        nd = max(p[2] for p in parts.values())
        storm = any(p[3] for p in parts.values())

        def func(f, c, code=code, getters=getters):
            got = {}

            def get(n):
                if n not in got:
                    got[n] = np.asarray(getters[n](f, c))
                return got[n]

            out = np.asarray(evaluate(code, get), dtype=np.float64)
            shape = np.broadcast_shapes(*(v.shape for v in got.values()))
            return np.broadcast_to(out, shape).astype(np.float32)

        fd = FieldDef(name, d["label"], d["units"], d["group"] or "User", ndim=nd,
                      cmap=d["cmap"], vrange=tuple(d["vrange"]) if d["vrange"] else None,
                      diverging=d["diverging"], deps=deps, func=func, storm=storm,
                      note=d["note"], confirmed=False)
        fd.user = d
        made[name] = fd
        with _lock:
            _state["bound"].add(name)
        return fd

    out = []
    for name in specs:
        try:
            out.append(make(name))
        except _Off:
            pass
    return out, [(specs[n], why) for n, why in off.items()]


def describe(d):
    """A user field's tooltip: its note, its expression, where it came from."""
    u = d.user
    src = {"file": "your fields file", "figure": "a saved figure"}.get(u["source"], u["source"])
    head = f"{u['note']}\n\n" if u.get("note") else ""
    return f"{head}= {u['expr']}\nUser-defined (from {src}), not reviewed."

