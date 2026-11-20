"""The models atmo3d can read, and which one a folder holds.

Each model (a data-type package registers its own: see register()) names its reader (a core.run.Run subclass) and how its output is found:
count(path) is the number of output times in a folder, and looks(entries) says from
one folder listing (os.scandir entries, no further reads) whether it is a run of the
model, which keeps the search for runs cheap.  "auto" picks the first model whose
output a folder holds.

A run's path is usually its folder.  A model may also name runs inside one folder
(WoFS: an experiment folder is one run in the picker, but each ensemble member is
read as <root>/memNN, and their mean as <root>/mean; no such folders on disk):
parts(path) lists them, virtual(path) says a path is one, and canonical(path) turns
the folder itself into the one to open."""

import glob
import os

AUTO = "auto"


class Model:
    key = ""
    label = ""
    run_class = None

    def count(self, path):
        return 0

    def looks(self, entries):
        return False

    def runs(self, path, entries):
        """The runs in a folder that looks(entries) like this model's."""
        return [path]

    def parts(self, path, entries=None):
        """The runs named inside a run folder (WoFS: members and mean); [] if none."""
        return []

    def summary(self, path):
        """A few words on a run folder for the picker (e.g. "36 members"), or ""."""
        return ""

    def part_label(self, path):
        """The name of a run named inside a folder (parts) in a list: e.g. "Member 5"."""
        return os.path.basename(path.rstrip("/"))

    def parts_of(self, path):
        """The runs next to virtual run `path`, itself among them (default: its
        folder's parts)."""
        return self.parts(os.path.dirname(os.path.abspath(path)))

    def folder_label(self, path):
        """The name in a list of parts of a run folder that is one of its own parts (a
        radar folder's native run), or None."""
        return None

    def virtual(self, path):
        """Is `path` a run of this model that is not a folder on disk?"""
        return False

    def canonical(self, path):
        """The run path to open for `path` (a folder holding several runs: its first)."""
        return path

    def open(self, path, **kw):
        return self.run_class(path, **kw)

    def make_demo(self, root):
        """Write (or find) this data type's demo run under `root`: its run path, or None
        if the data type has no demo (atmo3d --demo MODEL, core.models.demo_keys)."""
        return None

    def is_demo(self, path):
        """Is `path` a demo run this data type wrote (make_demo)?"""
        return False


GROUP = "atmo3d.datatypes"


class _Models(dict):
    """{key: Model} of the registered data types.  The first read loads the data-type
    packages that are installed (load()), so importing this module needs none of them."""

    def _ensure(self):
        if not _LOADED:
            load()

    def __getitem__(self, k):
        self._ensure()
        return super().__getitem__(k)

    def __iter__(self):
        self._ensure()
        return super().__iter__()

    def __len__(self):
        self._ensure()
        return super().__len__()

    def __contains__(self, k):
        self._ensure()
        return super().__contains__(k)

    def get(self, k, default=None):
        self._ensure()
        return super().get(k, default)

    def keys(self):
        self._ensure()
        return super().keys()

    def values(self):
        self._ensure()
        return super().values()

    def items(self):
        self._ensure()
        return super().items()


MODELS = _Models()
_LOADED = False


def register(model):
    """Add a data type (a Model instance).  A data-type package calls this from the function
    its entry point names:

        [project.entry-points."atmo3d.datatypes"]
        cm1 = "atmo3d_cm1:register"

    A key registered again replaces the old entry in its place."""
    dict.__setitem__(MODELS, model.key, model)
    return model


def load():
    """Import every installed data-type package: call the function each entry point of the
    group names.  Packages load in the alphabetical order of their entry-point names, which
    is the order "auto" tries their models in.  Called once, on first use."""
    global _LOADED
    if _LOADED:
        return
    _LOADED = True  # (set first: a package's register() may read MODELS)
    from importlib.metadata import entry_points
    for ep in sorted(entry_points(group=GROUP), key=lambda e: e.name):
        ep.load()()


def choices():
    """{label: key} for a model picker, auto-detect first."""
    return {"Auto-detect": AUTO, **{m.label: k for k, m in MODELS.items()}}


def demo_keys():
    """Keys of the data types that have a demo run, in registration order."""
    return [k for k, m in MODELS.items() if type(m).make_demo is not Model.make_demo]


def make_demo(key, root):
    """The demo run of data type `key`, written under `root` if need be."""
    path = get(key).make_demo(root)
    if path is None:
        raise ValueError(f"{key!r} has no demo run (one of: {', '.join(demo_keys())})")
    return path


def get(key):
    """The Model of a key (None or "auto": None)."""
    if not key or key == AUTO:
        return None
    try:
        return MODELS[key]
    except KeyError:
        raise ValueError(f"unknown model {key!r} (one of: {', '.join(MODELS)})") from None


def detect(path):
    """The Model whose output is in `path`, or None."""
    if not exists(path):
        return None
    return next((m for m in MODELS.values() if m.count(path) > 0), None)


def exists(path):
    """A folder, or a run a model names inside one (see virtual())."""
    return bool(path) and (os.path.isdir(path)
                           or any(m.virtual(path) for m in MODELS.values()))


def canonical(path, key=None):
    """The run to open for `path`: a folder holding several runs (a WoFS experiment)
    gives the one its model opens first; anything else is returned as is."""
    if not path or not os.path.isdir(path):
        return path
    m = get(key) or detect(path)
    return m.canonical(path) if m is not None else path


def root_of(path):
    """The run folder a virtual run is named in (a WoFS member's experiment), else
    `path` itself."""
    for m in MODELS.values():
        if m.virtual(path):
            return os.path.dirname(os.path.abspath(path))
    return path


def runs_in(path, entries, key=None):
    """The runs in a folder whose listing looks like a run (of `key`, or any model)."""
    ms = [get(key)] if get(key) else MODELS.values()
    m = next((m for m in ms if m.looks(entries)), None)
    return m.runs(path, entries) if m is not None else []


def siblings(path):
    """The other runs named inside the same folder as a virtual run (else [])."""
    for m in MODELS.values():
        if m.virtual(path):
            return m.parts_of(path)
    return []


def parts(path, key=None):
    """The runs named inside a run folder or next to a virtual run (WoFS members and
    mean), else []."""
    if not exists(path):
        return []
    if not os.path.isdir(path):
        return siblings(path)
    m = get(key) or detect(path)
    return m.parts(path) if m is not None else []


def part_label(path):
    """A virtual run's name in its folder's list ("Member 5"), else its folder name."""
    for m in MODELS.values():
        if m.virtual(path):
            return m.part_label(path)
    for m in MODELS.values():  # (a folder that is one of its own parts: a radar's)
        lab = m.folder_label(path)
        if lab:
            return lab
    return os.path.basename(os.path.abspath(path).rstrip("/"))


def summary(path, key=None):
    m = get(key) or detect(path)
    return m.summary(path) if m is not None and exists(path) else ""


def resolve(path, key=None):
    """The Model to open `path` with: `key` if given, else the detected one, else
    FileNotFoundError."""
    m = get(key) or detect(path)
    if m is None:
        raise FileNotFoundError(f"no model output found in {path}")
    return m


def count(path, key=None):
    """Output times in `path` (of model `key`, else of the model detected there)."""
    m = get(key) or detect(path)
    return m.count(path) if m is not None and exists(path) else 0


def looks_like_run(entries, key=None):
    """From one folder listing: is it a run (of model `key`, or of any model)?"""
    ms = [get(key)] if get(key) else MODELS.values()
    return any(m.looks(entries) for m in ms)


def open_run(path, key=None, **kw):
    """The Run in `path`, read by model `key` (auto-detected when None or "auto")."""
    path = canonical(path, key)
    return resolve(path, key).open(path, **kw)


def is_file(entry):
    try:
        return entry.is_file()
    except OSError:
        return False

