"""User-defined derived fields: TOML expressions (https://bobbysaba.com/docs/atmo3d/guides/user-fields/).

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
# layer functions: a field (any pointwise expression of 3D fields) reduced over a layer
# of each column, km above ground, z1 `top`: the model top.  An expression using them
# is a column field (2D), as the built-in UH or shear are.
LAYER_FUNCS = ("layer_mean", "layer_integral", "layer_max", "layer_min", "at_height")
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


def _layer_spec(node):
    """(kind, z0, z1) of layer-function call `node` (z1 None: the model top; at_height:
    (kind, z, z)); Unsafe when its arguments are not a field and plain heights."""
    kind, args = node.func.id, node.args
    want = 2 if kind == "at_height" else 3
    usage = ("at_height(field, z)" if kind == "at_height"
             else f"{kind}(field, z0, z1)") + ": heights in km above ground"
    if node.keywords or len(args) != want:
        raise Unsafe(f"{kind} takes {want} arguments, {usage}")

    def height(a, top_ok):
        if top_ok and isinstance(a, ast.Name) and a.id == "top":
            return None
        neg = isinstance(a, ast.UnaryOp) and isinstance(a.op, ast.USub)
        c = a.operand if neg else a
        if not (isinstance(c, ast.Constant) and isinstance(c.value, (int, float))
                and not isinstance(c.value, bool)):
            raise Unsafe(f"{kind}'s heights are numbers (km)"
                         + (" or top" if top_ok else "") + f": {usage}")
        v = -float(c.value) if neg else float(c.value)
        if not 0.0 <= v < 1.0e4:
            raise Unsafe(f"{kind}'s heights are km above ground, 0 or more: {usage}")
        return v

    if kind == "at_height":
        z = height(args[1], False)
        return kind, z, z
    z0, z1 = height(args[1], False), height(args[2], True)
    if z1 is not None and z1 <= z0:
        raise Unsafe(f"{kind}'s layer is z0 to z1 km with z1 above z0")
    return kind, z0, z1


def compile_expr(text):
    """(code, input names) of expression `text` (code: for evaluate); Unsafe (a
    ValueError) when it uses anything but the allowed syntax, or is not an expression.
    Layer functions (LAYER_FUNCS) make it a column field: see layers_of."""
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
    names, outside, layers = [], [], []

    def check(n, inside):
        """Validate node n (inside: within a layer function's field argument)."""
        if isinstance(n, (ast.BoolOp, ast.Not, ast.IfExp)):
            raise Unsafe("and, or, not, if-else do not work on fields: use &, |, ~ "
                         "(with brackets) and where(cond, a, b)")
        if not isinstance(n, _ALLOWED):
            raise Unsafe(f"not allowed in an expression: {type(n).__name__.lower()}")
        if isinstance(n, ast.Constant) and (isinstance(n.value, bool)
                                            or not isinstance(n.value, (int, float))):
            raise Unsafe("only numbers may be written as values")
        if isinstance(n, ast.Call):
            fn = n.func.id if isinstance(n.func, ast.Name) else None
            if fn in LAYER_FUNCS:
                if inside:
                    raise Unsafe(f"{fn} inside another layer function: write them side "
                                 "by side, layer_mean(a, 0, 1) - layer_mean(a, 1, 3)")
                layers.append(_layer_spec(n))
                before = len(names)
                check(n.args[0], True)
                if len(names) == before:
                    raise Unsafe(f"{fn} needs a field: {fn}(w, ...)")
                return
            if fn not in FUNCS:
                raise Unsafe(f"unknown function {fn or 'that'} (allowed: "
                             f"{', '.join(FUNCS)}, and {', '.join(LAYER_FUNCS)})")
            if n.keywords or any(isinstance(a, ast.Starred) for a in n.args):
                raise Unsafe("functions take plain arguments only")
            for a in n.args:
                check(a, inside)
            return
        if isinstance(n, ast.Name):
            if n.id.startswith("_"):
                raise Unsafe(f"names may not start with _: {n.id}")
            if n.id in FUNCS or n.id in LAYER_FUNCS:
                raise Unsafe(f"{n.id} is a function: call it")
            if n.id not in CONSTS:
                names.append(_input_name(n.id))
                if not inside:
                    outside.append(_input_name(n.id))
            return
        for c in ast.iter_child_nodes(n):
            check(c, inside)

    check(tree, False)

    class _Layers(ast.NodeTransformer):
        """Each layer function's call as _L<i>(field): its heights are in `layers`."""
        i = 0

        def visit_Call(self, node):
            if isinstance(node.func, ast.Name) and node.func.id in LAYER_FUNCS:
                inner = self.visit(node.args[0])
                name, self.i = f"_L{self.i}", self.i + 1
                return ast.copy_location(ast.Call(ast.Name(name, ast.Load()), [inner], []),
                                         node)
            return self.generic_visit(node)

    if layers:
        tree = _Layers().visit(tree)
    floats = _Floats()
    tree = ast.fix_missing_locations(floats.visit(tree))
    return ((compile(tree, "<user field>", "eval"), floats.values, tuple(layers),
             tuple(dict.fromkeys(outside))),
            tuple(dict.fromkeys(names)))


def layers_of(code):
    """(layers, names outside them) of compiled code: layers [(kind, z0, z1)] (km above
    ground, z1 None: the model top), empty for a pointwise expression."""
    return code[2], code[3]


def evaluate(code, get, layer=None):
    """The value of compiled expression `code`, its input names fetched by get(name);
    layer(spec, value) reduces a layer function's field (spec: (kind, z0, z1))."""
    code, numbers, layers, _ = code
    env = dict(FUNCS, **CONSTS, **numbers)
    if layers:
        if layer is None:
            raise Unsafe("layer functions are computed on a column field only")
        env.update({f"_L{i}": (lambda v, sp=sp: layer(sp, v))
                    for i, sp in enumerate(layers)})

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
            text = f.read().decode("utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return [], f"{path}: {e}"
    defs, problem = parse_text(text)
    return defs, f"{path}: {problem}" if problem else ""


def parse_text(text):
    """(definitions, problem) of a fields file's text (the editor checks it unsaved)."""
    try:
        doc = tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        return [], str(e)
    tables = doc.get("fields", {})
    if not isinstance(tables, dict):
        return [], "[fields] must be a table of [fields.<name>] tables"
    return [normalize(n, t, "file") for n, t in tables.items()], ""


def write_file(text):
    """Save the fields file's text (the editor): refused (ValueError) when it is not
    TOML or not [fields.<name>] tables, so a file atmo3d cannot read is never written.
    A definition with an error is written (and listed greyed out, as on a restart)."""
    _, problem = parse_text(text)
    if problem:
        raise ValueError(problem)
    path = fields_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = f"{path}.tmp{os.getpid()}"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    os.replace(tmp, path)
    return path


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


def reload():
    """Read the fields file and the packages again (the editor's Save; atmo3d reads
    them once otherwise), keeping the definitions figures brought.  Every run's Fields
    picks the change up: core.fields.sync_all_user.  Returns problems()."""
    with _lock:
        _state["loaded"], _state["problems"] = None, []
    loaded()
    from .fields import sync_all_user
    sync_all_user()
    return problems()


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


def bind(defs, avail, cat, builtins, scales=None, ndims=None, mark=True):
    """(FieldDefs, off) of definitions `defs` for fields `avail` of a data type with
    catalog `cat` and built-in derived FieldDefs `builtins` (already bound to the
    catalog's names).  scales / ndims: {native: display scale / ndim} (default: the
    catalog's look, 3D).  off: [(definition, why)] of those that cannot be made, e.g.
    an input the run lacks.  A definition named like a native or built-in field is off
    (the built-in one wins).  mark: count the ones made as in use (record; not for the
    editor's check of text not saved)."""
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
            if d.column:
                raise _Off(f"uses {n}, a column field (column fields cannot be inputs)")
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
        layers, outside = layers_of(code)
        if layers:  # (a column field: every input inside a layer function, 3D, pointwise)
            try:
                if outside:
                    raise _Off(f"uses {', '.join(outside)} outside a layer function: in "
                               "an expression with layer functions every field goes "
                               "inside one, layer_mean(w, 0, 3)")
                for n, p in parts.items():
                    if any(split_deriv(x)[0] for x in p[1]):
                        raise _Off(f"uses {n}: derivatives cannot be used inside layer "
                                   "functions")
                    if p[2] != 3:
                        raise _Off(f"uses {n}, which is 2D: layer functions work on 3D "
                                   "fields")
            except _Off as e:
                off[name] = str(e)
                raise
            fd = _column_def(name, d, code, getters, deps, storm, layers)
        else:
            def func(f, c, code=code, getters=getters):
                got = {}

                def get(n):
                    if n not in got:
                        got[n] = np.asarray(getters[n](f, c))
                    return got[n]

                out = np.asarray(evaluate(code, get), dtype=np.float64)
                shape = np.broadcast_shapes(*(v.shape for v in got.values()))
                return np.broadcast_to(out, shape).astype(np.float32)

            vr = tuple(d["vrange"]) if d["vrange"] else None
            fd = FieldDef(name, d["label"], d["units"], d["group"] or "User", ndim=nd,
                          cmap=d["cmap"], vrange=vr, diverging=d["diverging"], deps=deps,
                          func=func, storm=storm, note=d["note"], confirmed=False)
        fd.user = d
        made[name] = fd
        if mark:
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


def layer_span(layers):
    """(z0, z1) km of the column levels a field with layer functions `layers` reads:
    the lowest and highest of their heights (z1 None: the model top)."""
    z0 = min(max(a - 1e-3, 0.0) if k == "at_height" else a for k, a, _ in layers)
    tops = [b + 1e-3 if k == "at_height" else b for k, _, b in layers]
    return z0, (None if any(b is None for b in tops) else max(tops))


def reduce_layer(spec, a, c):
    """Layer function spec (kind, z0, z1) of a field's values `a` on a column field's
    levels (context c: core.fields.Fields._column's: "faces" the levels' cell bottoms and
    tops, km; "zk" their heights; "top" the model top where z1 is None): (ny, nx).
    Each level counts with the part of its cell inside the layer (as the built-in column
    fields do); NaN where none is, and where a column has no value there."""
    from .fields import at_height
    kind, z0, z1 = spec
    a = np.asarray(a, dtype=np.float64)  # ((L, ...): its inputs are 3D)
    if kind == "at_height":
        return np.asarray(at_height(a, c["zk"], z0), dtype=np.float64)
    top = float(c["top"]) if z1 is None else float(z1)
    lo, hi = (np.asarray(x, dtype=np.float64) for x in c["faces"])
    th = 1000.0 * (np.clip(hi, z0, top) - np.clip(lo, z0, top))  # (m in the layer)
    th = th.reshape(th.shape + (1,) * (a.ndim - th.ndim))
    th = np.broadcast_to(th, a.shape)
    inl = th > 0
    ok = inl & np.isfinite(a)
    with np.errstate(all="ignore"):
        if kind == "layer_integral":
            s = np.where(ok, th * a, 0.0).sum(axis=0)
            return np.where(ok.any(axis=0), s, np.nan)
        if kind == "layer_mean":
            w = np.where(ok, th, 0.0)
            return np.where(ok.any(axis=0), np.where(ok, w * a, 0.0).sum(axis=0)
                            / np.where(ok.any(axis=0), w.sum(axis=0), 1.0), np.nan)
        fill = -np.inf if kind == "layer_max" else np.inf
        b = np.where(ok, a, fill)
        r = b.max(axis=0) if kind == "layer_max" else b.min(axis=0)
        return np.where(ok.any(axis=0), r, np.nan)


def _column_def(name, d, code, getters, deps, storm, layers):
    """The FieldDef of user field `name` (definition d) whose expression uses layer
    functions: a column field over layer_span(layers), with the levels just outside
    it too (edges: so at_height can interpolate)."""
    from .fields import FieldDef

    def func(f, c, code=code, getters=getters):
        got = {}

        def get(n):
            if n not in got:
                got[n] = np.asarray(getters[n](f, c))
            return got[n]

        out = np.asarray(evaluate(code, get, lambda sp, v: reduce_layer(sp, v, c)),
                         dtype=np.float64)
        shapes = [v.shape[1:] for v in got.values() if v.ndim >= 3]
        if shapes:
            out = np.broadcast_to(out, np.broadcast_shapes(*shapes))
        return out.astype(np.float32)

    fd = FieldDef(name, d["label"], d["units"], d["group"] or "User", ndim=2,
                  cmap=d["cmap"], vrange=tuple(d["vrange"]) if d["vrange"] else None,
                  diverging=d["diverging"], deps=deps, func=func, storm=storm,
                  layer=layer_span(layers), edges=True, note=d["note"], confirmed=False)
    return fd


def describe(d):
    """A user field's tooltip: its note, its expression, where it came from."""
    u = d.user
    src = {"file": "your fields file", "figure": "a saved figure"}.get(u["source"], u["source"])
    head = f"{u['note']}\n\n" if u.get("note") else ""
    return f"{head}= {u['expr']}\nUser-defined (from {src}), not reviewed."

