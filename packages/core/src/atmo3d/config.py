"""User settings: ~/.config/atmo3d/config.toml (or $ATMO3D_CONFIG).

Each setting comes from, in increasing precedence: the built-in default, the config
file, an environment variable ATMO3D_<NAME> (lists separated by ':'), and a
command-line flag.  `source(name)` says which one won.  Path settings take effect
on the next use; settings marked `restart` only when the server starts again."""

import fnmatch
import json
import os
import threading
import time
import tomllib

DEFAULT_PATH = os.path.join(os.path.expanduser("~"), ".config", "atmo3d", "config.toml")
SECTIONS = ("paths", "tracks", "data", "server")


class Key:
    def __init__(self, name, section, default, label, help, kind="str", restart=False,
                 advanced=False, required=False):
        self.name, self.section, self.default = name, section, default
        self.label, self.help, self.kind = label, help, kind
        self.restart, self.advanced, self.required = restart, advanced, required


KEYS = [
    Key("runs_root", "paths", [], "Where your runs live",
        "Folders searched for runs (folders holding model output files). The run "
        "picker starts here.", kind="dirs", required=True),
    Key("default_run", "paths", "", "Run to open on launch",
        "Optional: a run opened when atmo3d starts without a run argument.",
        kind="dir"),
    Key("figures_dir", "paths", "~/atmo3d/figures", "Figures",
        "Exported figures go to <this>/<parent>_<run>/ (image; script in scripts/, data "
        "and spec in _src/).", kind="outdir"),
    Key("exports_dir", "paths", "~/atmo3d/exports", "Saved data",
        "Saved series go to <this>/<parent>_<run>/series, data exports to .../data, "
        "sessions to .../sessions, parcel sets to .../parcels; tracks go to .../tracks when no track folder exists.",
        kind="outdir"),
    Key("cache_dir", "paths", "~/.cache/atmo3d", "Cache",
        "Throwaway files atmo3d can rebuild (computed series, parcel trajectories). Scratch is a good "
        "place: home quotas are small.", kind="outdir"),
    Key("pdecomp_script", "paths", "", "Pressure-decomposition script",
        "Optional: your own script for times whose files lack the decomposition, with "
        "cm1_pdecomp's run_decomposition (or the older pdecomp_solver.py functions). "
        "Empty: CM1's method (cm1_pdecomp.py), built in.", kind="file"),
    Key("fields_file", "paths", "", "Your own derived fields",
        "Optional: a TOML file of your own derived fields ([fields.<name>] tables with an "
        "expr). Empty: fields.toml beside this settings file, if there is one. Read when "
        "atmo3d starts.", kind="file", restart=True),
    Key("track_dirs", "tracks", ["storm_tracks"], "Track folders",
        "Where storm track files are looked for. A plain name (storm_tracks) is a "
        "folder of that name in the run folder or up to 4 folders above it; a full "
        "path is used as is. New tracks are saved to the first of these that "
        "exists (a full path is created).", kind="list"),
    Key("track_patterns", "tracks",
        ["{parent}_{name}.csv", "{parent}_{name}.txt", "{name}.csv", "{name}.txt"],
        "Track file names",
        "File names tried in each track folder: {name} = run folder, {parent} = the "
        "folder above it. Wildcards (*) are allowed; new tracks are named by the "
        "first name without one.", kind="list"),
    Key("track_motion_window", "tracks", "auto", "Storm-motion window (min)",
        "Storm motion from a track is the slope of a straight line fitted through the "
        "fixes within half this many minutes of each time, which steadies a jumpy "
        "track. 0: centred differences between neighbouring fixes. auto: 0 for CM1, "
        "30 for WoFS (every cycle is a fresh analysis, so its fixes jump).",
        kind="auto_float"),
    Key("output_glob", "data", "cm1out_[0-9]*.nc", "Output file names",
        "Which files in a run folder are CM1 output (applies to runs opened after "
        "saving)."),
    Key("parcel_glob", "data", "cm1out_pdata*.nc", "Parcel file names",
        "Which files in a run folder hold parcel (trajectory) output; several (e.g. "
        "one per restart) are joined by time."),
    Key("traj_max_interval", "data", 300, "Longest output interval for trajectories",
        "Runs without parcel output (WoFS) get trajectories that atmo3d traces through "
        "the 3D winds, with the winds between two outputs taken as a blend of the two. "
        "That goes wrong when the outputs are far apart, so trajectories are turned off "
        "for runs whose output comes less often than this many seconds. 0: never turn "
        "them off.", kind="int"),
    Key("wofs_member", "data", "1", "WoFS member opened first",
        "Which ensemble member a WoFS run opens on: a member number, or mean for the "
        "ensemble mean (slower: reads every member's file). A member the run lacks: "
        "its first. Switch members in the viewer's Member box."),
    Key("settle_seconds", "data", 60, "Seconds before a new output file is read",
        "A run still going is opened without the output file being written: the newest "
        "file is left out while it was changed within this many seconds or will not "
        "open yet. Reload run (the button by the run's name) adds files finished since. "
        "0: only files that will not open are left out.", kind="int", advanced=True),
    Key("allow_writes_to_output", "data", False, "Allow writing into output files",
        "Lets the pressure decomposition write its fields into the CM1 output files. "
        "Off: results stay in memory.", kind="bool"),
    Key("show_hidden_fields", "data", False, "Show hidden fields",
        "List the fields atmo3d hides (WoFS's static, land-surface, radiation and "
        "time-step fields, and WRF fields it does not know) under \"Hidden\" at the "
        "end of the field lists. Applies to runs opened after saving.", kind="bool"),
    Key("docs_url", "data", "", "Documentation site address",
        "Where the atmo3d documentation is published (an http or https address, e.g. "
        "https://example.org/atmo3d). Set, the field menus end with a link to the "
        "derived-fields page. Blank: no link.", advanced=True),
    Key("column_stride", "data", "auto", "Sounding-parameter stride",
        "CAPE, CIN, LCL, STP and SCP maps are computed on every n-th column in x and "
        "y (each n x n block shows its middle column). auto = as few as keep them to "
        "about 250 000 columns (every column up to 500 x 500 points).",
        kind="auto_int", advanced=True),
    Key("radar_max_gap_km", "data", "auto", "Radar: widest gap bridged between sweeps (km)",
        "Radar views that are not one sweep (constant-height maps, cross-sections, "
        "columns, 3D) take values between two sweeps linearly in elevation. Where the "
        "two sweeps around a point are further apart than this (vertically, at its "
        "range) the point is left empty instead. auto: every gap is bridged.",
        kind="auto_float"),
    Key("radar_sampling", "data", "linear", "Radar: sampling within a sweep",
        "linear: between the two nearest rays and gates; nearest: the nearest gate. "
        "Between sweeps it is always linear in elevation.", advanced=True),
    Key("radar_regrid_method", "data", "linear", "Radar regrid: sampling within a sweep",
        "How a radar run is regridded (Regridded in the toolbar; off unless chosen, and "
        "confirmed each time): linear between the nearest rays and gates, or nearest "
        "gate. Between sweeps it is linear in elevation."),
    Key("radar_regrid_dx", "data", 0.5, "Radar regrid: horizontal spacing (km)",
        "Grid spacing in x and y. auto: 0.5 km.", kind="auto_float"),
    Key("radar_regrid_dz", "data", 0.5, "Radar regrid: vertical spacing (km)",
        "Depth of the grid's layers, from the radar's level up. auto: 0.5 km.",
        kind="auto_float"),
    Key("radar_regrid_range", "data", 150.0, "Radar regrid: maximum range (km)",
        "The grid covers this far from the radar in x and y; points further away are "
        "left empty. auto: 150 km.", kind="auto_float"),
    Key("radar_regrid_max_gap", "data", 0.0, "Radar regrid: widest gap bridged (km)",
        "Grid points where the two sweeps around them are further apart than this are "
        "left empty. 0 or auto: every gap is bridged.", kind="auto_float"),
    Key("cache_gb", "server", "auto", "3D cache (GB)",
        "Memory for cached 3D fields. auto = a share of this job's memory, leaving "
        "room for the pressure decomposition.", kind="auto_float", restart=True,
        advanced=True),
    Key("workers", "server", "auto", "Reader processes",
        "Parallel file readers. auto = the CPUs this job was given (at most 16).",
        kind="auto_int", restart=True, advanced=True),
    Key("port", "server", 5006, "Port",
        "Server port; the next free one is used if it is taken.", kind="int",
        restart=True, advanced=True),
    Key("maxpix", "server", 900, "Map pixels",
        "Max map pixels sent per axis (zoom in for full resolution). Applies to "
        "pages opened after saving.", kind="int", advanced=True),
    Key("login_host", "server", "", "SSH login host",
        "Only for the SSH tunnel command printed at launch (the machine you ssh "
        "into, e.g. login.cluster.edu). Empty: a placeholder is printed.",
        advanced=True),
]
BY_NAME = {k.name: k for k in KEYS}
LEGACY_ENV = {"pdecomp_script": "ATMO3D_PDECOMP"}

_lock = threading.Lock()
_listeners = []
_state = dict(path=None, file={}, cli={}, exists=False, error="")


# ------------------------------------------------------------------ loading
def config_path():
    return _state["path"] or os.environ.get("ATMO3D_CONFIG") or DEFAULT_PATH


def load(path=None):
    """(Re)read the config file; keeps command-line overrides."""
    with _lock:
        _state["path"] = os.path.abspath(os.path.expanduser(path)) if path else \
            _state["path"]
        p = config_path()
        _state["file"], _state["exists"], _state["error"] = {}, os.path.isfile(p), ""
        if _state["exists"]:
            try:
                with open(p, "rb") as f:
                    _state["file"] = _flatten(tomllib.load(f))
            except (OSError, tomllib.TOMLDecodeError) as e:
                _state["error"] = f"{p}: {e}"


def _flatten(doc):
    out = {}
    for k, v in doc.items():
        if isinstance(v, dict) and k in SECTIONS:
            out.update({kk: vv for kk, vv in v.items() if kk in BY_NAME})
        elif k in BY_NAME:
            out[k] = v
    return {k: _coerce(BY_NAME[k], v) for k, v in out.items()}


def _coerce(key, v):
    kind = key.kind
    if kind in ("dirs", "list"):
        if isinstance(v, str):
            v = [s for s in v.split(os.pathsep if kind == "dirs" else ",") if s.strip()]
        return [str(s).strip() for s in v if str(s).strip()]
    if kind == "bool":
        return v if isinstance(v, bool) else str(v).strip().lower() in ("1", "true",
                                                                         "yes", "on")
    if kind in ("auto_float", "auto_int"):
        if v is None or str(v).strip().lower() in ("", "auto"):
            return "auto"
        return float(v) if kind == "auto_float" else int(v)
    if kind == "int":
        return int(v)
    return "" if v is None else str(v).strip()


def _env(name):
    for var in (f"ATMO3D_{name.upper()}", LEGACY_ENV.get(name)):
        if var and os.environ.get(var, "") != "":
            return var, os.environ[var]
    return None, None


def override(name, value, flag):
    """A command-line value (wins over everything else)."""
    _state["cli"][name] = (_coerce(BY_NAME[name], value), flag)


def source(name):
    """'command line (--flag)', 'environment (VAR)', 'config file' or 'default'."""
    if name in _state["cli"]:
        return f"command line ({_state['cli'][name][1]})"
    var, _ = _env(name)
    if var:
        return f"environment ({var})"
    if name in _state["file"]:
        return "config file"
    return "default"


def get(name):
    if name in _state["cli"]:
        return _state["cli"][name][0]
    var, val = _env(name)
    if var:
        try:
            return _coerce(BY_NAME[name], val)
        except ValueError:
            pass
    if name in _state["file"]:
        return _state["file"][name]
    d = BY_NAME[name].default
    return list(d) if isinstance(d, list) else d


def file_value(name):
    """What the config file says (or the default): what the settings form edits."""
    d = BY_NAME[name].default
    return _state["file"].get(name, list(d) if isinstance(d, list) else d)


def exists():
    return _state["exists"]


def read_error():
    return _state["error"]


def on_change(fn):
    """fn() after every save (from any session's thread)."""
    _listeners.append(fn)


def off(fn):
    if fn in _listeners:
        _listeners.remove(fn)


# ------------------------------------------------------------------ saving
def to_toml(values):
    """The config file text: every setting, with its help as a comment."""
    out = ["# atmo3d settings (edit here or with the gear button in the viewer).",
           "# Environment variables ATMO3D_<NAME> and command-line flags override these.",
           ""]
    for sec in SECTIONS:
        out.append(f"[{sec}]")
        for k in KEYS:
            if k.section != sec:
                continue
            out.append(f"# {k.label}: {k.help}" + (" (needs a restart)" if k.restart else ""))
            out.append(f"{k.name} = {_toml_value(values.get(k.name, k.default))}")
        out.append("")
    return "\n".join(out)


def _toml_value(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(json.dumps(str(s)) for s in v) + "]"
    return json.dumps(str(v))  # JSON string escapes are valid TOML basic strings


def save(values):
    """Write all settings (values: name -> value; missing ones keep the file's) and
    reload.  Raises ValueError for a bad value, OSError when the file can't be written."""
    merged = {k.name: file_value(k.name) for k in KEYS}
    for name, v in values.items():
        merged[name] = _coerce(BY_NAME[name], v)
    save_text(to_toml(merged))


def save_text(text):
    """Write the raw file text (checked first) and reload."""
    doc = tomllib.loads(text)
    _flatten(doc)  # raises ValueError for values of the wrong type
    p = config_path()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = f"{p}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, p)
    load()
    for fn in list(_listeners):
        try:
            fn()
        except Exception:  # noqa: BLE001  (a closed session must not stop the others)
            pass


def file_text():
    try:
        with open(config_path(), encoding="utf-8") as f:
            return f.read()
    except OSError:
        return to_toml({k.name: file_value(k.name) for k in KEYS})


def state(name, default=""):
    """Small remembered values (e.g. the last folder chosen for a figure), kept in
    state.json next to the config file."""
    try:
        with open(_state_path(), encoding="utf-8") as f:
            return json.load(f).get(name, default)
    except (OSError, ValueError, AttributeError):
        return default


def set_state(name, value):
    p = _state_path()
    try:
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError):
        d = {}
    d[name] = value
    try:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=1)
    except OSError:
        pass


def _state_path():
    return os.path.join(os.path.dirname(config_path()), "state.json")


# ------------------------------------------------------------------ checks
def expand(p):
    return os.path.abspath(os.path.expanduser(os.path.expandvars(p))) if p else ""


def check(name, value):
    """A problem with this value ('' when fine)."""
    key = BY_NAME[name]
    if key.kind == "dirs":
        if key.required and not value:
            return "Required: at least one folder."
        bad = [p for p in value if not os.path.isdir(expand(p))]
        return f"Not a folder: {', '.join(bad)}" if bad else ""
    if key.kind == "dir" and value and not os.path.isdir(expand(value)):
        return "Not a folder."
    if key.kind == "file" and value and not os.path.isfile(expand(value)):
        return "File not found."
    if key.kind == "outdir" and value and not _creatable(expand(value)):
        return "Can't create or write to this folder."
    if key.kind == "outdir" and not value:
        return "Required."
    return ""


def _creatable(p):
    while p and not os.path.exists(p):
        p = os.path.dirname(p)
    return bool(p) and os.path.isdir(p) and os.access(p, os.W_OK | os.X_OK)


def problems():
    """{name: message} for the settings in effect."""
    return {k.name: m for k in KEYS if (m := check(k.name, get(k.name)))}


def needs_setup():
    """The first-run window is required: no config file yet, or no usable runs_root.
    Not when runs_root comes from the command line (atmo3d --demo)."""
    if "runs_root" in _state["cli"]:
        return bool(check("runs_root", get("runs_root")))
    return not exists() or bool(read_error()) or bool(check("runs_root", get("runs_root")))


# ------------------------------------------------------------------ paths
def run_key(path):
    """<parent>_<name>: one folder name per run for saved files."""
    path = os.path.abspath(path).rstrip("/\\")
    return f"{os.path.basename(os.path.dirname(path))}_{os.path.basename(path)}"


def figures_dir(run_path):
    return os.path.join(expand(get("figures_dir")), run_key(run_path))


def exports_dir(run_path, kind):
    return os.path.join(expand(get("exports_dir")), run_key(run_path), kind)


def cache_dir(*sub):
    return os.path.join(expand(get("cache_dir")), *sub)


def pdecomp_script():
    return expand(get("pdecomp_script"))


def _track_dirs(path, levels=4):
    """The folders searched for track files, closest first (see track_dirs)."""
    dirs = []
    for d in get("track_dirs"):
        if os.path.isabs(os.path.expanduser(d)):
            dirs.append(expand(d))
        else:
            up = path
            for _ in range(levels):
                dirs.append(os.path.join(up, d))
                up = os.path.dirname(up)
    return dirs


def _names(path):
    path = os.path.abspath(path).rstrip("/\\")
    return path, os.path.basename(path), os.path.basename(os.path.dirname(path))


def find_track(path, levels=4):
    """A storm track file for the run in `path` (see track_dirs / track_patterns)."""
    import glob
    path, name, parent = _names(path)
    for tdir in _track_dirs(path, levels):
        for pat in get("track_patterns"):
            hits = sorted(glob.glob(os.path.join(tdir, pat.format(name=name,
                                                                  parent=parent))))
            if hits:
                return hits[0]
    return None


def track_files(path, levels=4, limit=200):
    """The track files to offer for the run in `path`: those named for it, in find_track's
    order, then the others in the track folders (.csv, .txt), closest folder first.  Each
    folder is listed, not searched: nothing below it."""
    import fnmatch as fn
    path, name, parent = _names(path)
    pats = [p.format(name=name, parent=parent) for p in get("track_patterns")]
    own, other = [], []
    for tdir in dict.fromkeys(_track_dirs(path, levels)):
        try:
            with os.scandir(tdir) as it:
                names = sorted(e.name for e in it if _is(e, "file"))
        except OSError:
            continue
        for pat in pats:
            own += [os.path.join(tdir, n) for n in names if fn.fnmatch(n, pat)]
        other += [os.path.join(tdir, n) for n in names
                  if n.lower().endswith((".csv", ".txt"))]
    return list(dict.fromkeys(own + other))[:limit]


def track_save_path(path, levels=4):
    """Where a new track for the run in `path` is saved: the first track folder that
    exists (or is a full path), named by the first track file name without wildcards,
    so find_track picks it up next time.  The exports folder if there is no such
    folder or name."""
    path, name, parent = _names(path)
    pats = [p for p in get("track_patterns") if "*" not in p and "?" not in p]
    fname = pats[0].format(name=name, parent=parent) if pats else "meso_track.csv"
    for tdir in _track_dirs(path, levels):
        if os.path.isdir(tdir) and pats:
            return os.path.join(tdir, fname)
    for d in get("track_dirs"):
        if os.path.isabs(os.path.expanduser(d)) and pats:
            return os.path.join(expand(d), fname)
    return os.path.join(exports_dir(path, "tracks"), fname)


def is_output(fname):
    return fnmatch.fnmatch(fname, get("output_glob"))


def _is(entry, kind):
    """entry.is_file() / is_dir(), False where it cannot be checked (e.g. a link into
    a project folder you cannot read)."""
    try:
        return entry.is_file() if kind == "file" else entry.is_dir()
    except OSError:
        return False


def searchable(path):
    """May atmo3d search (list, look inside the folders of) `path`?  Never a shared
    folder: "/", a top-level folder, a folder owned by root (on a cluster, the shared
    roots: /scratch, /work, /home, ...) or a folder above your home folder.  Searching
    those lists every user's folders, which slows the filesystem for everyone."""
    try:
        p = os.path.realpath(os.path.abspath(os.path.expanduser(path)))
        if p.count(os.sep) <= 1 or not os.path.isdir(p):
            return False
        home = os.path.realpath(os.path.expanduser("~"))
        if home.startswith(p.rstrip(os.sep) + os.sep):
            return False
        if os.name == "nt":  # (no root-owned folders: the drive and home checks above)
            return True
        return os.stat(p).st_uid != 0 or os.getuid() == 0
    except (OSError, ValueError):
        return False


def scan_runs(roots=None, depth=5, limit=500, seconds=4.0, model=None):
    """Run folders under the roots (breadth first, hidden folders skipped, no search
    inside a run), of `model` (a core.models key; None/"auto": any model).  Roots that
    are not searchable() (shared folders) are skipped.  Returns (runs, complete)."""
    from .core import models
    t0, runs, complete = time.time(), [], True
    level = [expand(r) for r in (get("runs_root") if roots is None else roots) if r]
    complete = all(searchable(r) for r in level)
    level = [r for r in level if searchable(r)]
    for _ in range(depth + 1):
        nxt = []
        for d in level:
            if time.time() - t0 > seconds or len(runs) >= limit:
                return sorted(runs), False
            try:
                ents = list(os.scandir(d))
            except OSError:
                continue
            if models.looks_like_run(ents, model):
                runs += models.runs_in(d, ents, model)  # (a WoFS root: its members)
                continue
            nxt += sorted(e.path for e in ents
                          if not e.name.startswith(".") and _is(e, "dir"))
        level = nxt
        if not level:
            break
    else:
        complete = complete and not level
    return sorted(runs), complete


# ------------------------------------------------------------------ auto values
def job_memory_gb():
    """Memory this job may use (the limit of its own memory cgroup, cgroup v1 or v2,
    else the node's)."""
    limit = job_memory_limit()
    if limit is None:
        limit = machine_memory()
    return limit / 1024**3


def machine_memory():
    """Bytes of memory the machine has (Linux, macOS: sysconf; Windows: the API)."""
    if hasattr(os, "sysconf"):
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    import ctypes

    class _Status(ctypes.Structure):  # MEMORYSTATUSEX
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong)] + [
            (n, ctypes.c_ulonglong) for n in (
                "ullTotalPhys", "ullAvailPhys", "ullTotalPageFile", "ullAvailPageFile",
                "ullTotalVirtual", "ullAvailVirtual", "ullAvailExtendedVirtual")]

    st = _Status()
    st.dwLength = ctypes.sizeof(_Status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
        return 8 * 1024**3  # (unknown: a modest machine)
    return st.ullTotalPhys


def job_memory_limit():
    """Bytes the job's memory cgroup allows, or None where none limits it."""
    cg = _job_cgroup()
    if cg is None:
        return None
    try:
        return int(open(os.path.join(cg[0], cg[1]), encoding="utf-8").read())
    except (OSError, ValueError):
        return None


def _job_cgroup():
    """(folder, limit file, the two memory.stat rows) of the memory cgroup that limits
    this job, or None where nothing does (a laptop, a node with no memory limit)."""
    try:
        lines = [line.strip().split(":", 2) for line in open("/proc/self/cgroup", encoding="utf-8")]
    except OSError:
        return None
    for line in lines:
        if len(line) < 3:
            continue
        _, ctl, rel = line
        if ctl == "":  # cgroup v2
            base, names = "/sys/fs/cgroup", ("memory.max", "anon", "shmem")
        elif "memory" in ctl.split(","):  # cgroup v1
            base = "/sys/fs/cgroup/memory"
            names = ("memory.limit_in_bytes", "total_rss", "total_shmem")
        else:
            continue
        d = os.path.normpath(base + "/" + rel)
        while d.startswith(base):  # (the limit can be set on a parent)
            try:
                if int(open(os.path.join(d, names[0]), encoding="utf-8").read()) < 1 << 50:
                    return (d, *names)
            except (OSError, ValueError):  # ("max", or no such file here)
                pass
            d = os.path.dirname(d)
    return None


def job_memory_used_gb():
    """Memory the job's processes hold now: this process, the readers and the fields
    cached in shared memory, without the file cache (which the system gives back).
    None where no cgroup limits the job."""
    cg = _job_cgroup()
    if cg is None:
        return None
    d, _, *rows = cg
    try:
        stat = dict(line.split()[:2] for line in open(os.path.join(d, "memory.stat"), encoding="utf-8"))
        return sum(int(stat[r]) for r in rows) / 1024**3
    except (OSError, KeyError, ValueError):
        return None


def job_cpus():
    try:
        return len(os.sched_getaffinity(0))
    except AttributeError:
        return os.cpu_count() or 1


def cache_gb():
    """(GB, how it was chosen)."""
    v = get("cache_gb")
    if v != "auto":
        return float(v), "set"
    mem = job_memory_gb()
    gb = float(max(2.0, min(48.0, 0.4 * mem)))
    return gb, f"auto: {gb:.0f} GB of {mem:.0f} GB job memory"


def workers():
    v = get("workers")
    if v != "auto":
        return int(v), "set"
    n = max(1, min(16, job_cpus()))
    return n, f"auto: {n} of {job_cpus()} CPUs"


# ------------------------------------------------------------------ first run
def suggestions(run_path=None):
    """Values to pre-fill the first-run window with (the config file's where set)."""
    from . import registry
    out = {k.name: file_value(k.name) for k in KEYS}
    if not exists():
        from . import demo
        recent = [os.path.abspath(p) for p in ([run_path] if run_path else [])
                  + registry.recent_runs() if p and not demo.is_demo(p)]
        if recent:
            # the folder that holds the runs: their common parent, or the grandparent
            # of a single run (e.g. cm1/ for cm1/project/run1); never one as broad
            # as a filesystem root, whose scan would take long and cross into other projects
            try:
                common = os.path.commonpath(recent)
            except ValueError:  # (on Windows, runs on different drives)
                common = ""
            if len(set(recent)) == 1 or common in recent or common.count(os.sep) < 3:
                common = os.path.dirname(os.path.dirname(recent[0]))
            out["runs_root"] = [common]
            if run_path:
                out["default_run"] = os.path.abspath(run_path)
        scratch = os.environ.get("SCRATCH")
        if scratch and os.path.isdir(scratch):
            out["cache_dir"] = os.path.join(scratch, ".cache", "atmo3d")
        out["login_host"] = out["login_host"] or submit_host()
    return out


def submit_host():
    """The login node this batch job was submitted from (PBS / Slurm), else ""."""
    import socket
    h = os.environ.get("PBS_O_HOST") or os.environ.get("SLURM_SUBMIT_HOST") or ""
    if h and "." not in h:
        domain = socket.getfqdn().partition(".")[2]
        h = f"{h}.{domain}" if domain else h
    return h


load()
