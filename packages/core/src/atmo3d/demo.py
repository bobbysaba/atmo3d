"""The demo run atmo3d --demo opens: a real CM1 supercell, shipped in the repository.

demo_data/supercell/ (beside the atmo3d package) is CM1 r21.1's supercell case
(Weisman and Rotunno 2000, quarter-circle hodograph): 1 km grid spacing, 44 stretched
levels (100 m at the ground to 500 m above 6 km), 2 h, with parcels.  It is cut down from
the full run by tools/make_real_demo.py: an 80 x 80 km box around the storms, every 10 min,
16-bit packed fields, 1500 parcels.  A pip install has no copy (it is not in the
package): make() then says where to get one.

make() copies it into atmo3d's cache folder (once; again when the shipped copy changes)
with a stamp file beside it, so atmo3d treats it as a demo run (is_demo): never left out
as still being written however new its files, kept out of the recent runs, and never
written into inside the repository.

The tests use synthetic runs instead (tests/synthetic.py), whose answers are known in
advance; they are stamped the same way.
"""

import hashlib
import os
import shutil



def _data_dir():
    """demo_data/ at the top of a source checkout (a few folders above this file), or the
    place it would be (a pip install does not ship it)."""
    here = os.path.dirname(os.path.abspath(__file__))
    d = here
    for _ in range(5):
        d = os.path.dirname(d)
        if os.path.isdir(os.path.join(d, "demo_data")):
            return os.path.join(d, "demo_data")
    return os.path.join(here, "demo_data")


DATA = _data_dir()
RUN = "supercell"
STAMP = ".atmo3d-demo"
REPO = "https://github.com/bobbysaba/atmo3d"


def shipped():
    """The shipped demo run's folder, or None (a pip install: not in the package)."""
    path = os.path.join(DATA, RUN)
    return path if os.path.isfile(os.path.join(path, "namelist.input")) else None


def _stamp(src):
    """Names and contents of the shipped files: the cached copy is redone when it changes."""
    h = hashlib.sha1()
    for name in sorted(os.listdir(src)):
        h.update(name.encode() + b"\0")
        with open(os.path.join(src, name), "rb") as f:
            for block in iter(lambda: f.read(1 << 20), b""):
                h.update(block)
    return f"real {h.hexdigest()[:16]}"


def make(root, force=False):
    """Copy the demo run into root (skipped when an up-to-date copy is there); returns
    the run's path, root/supercell.  root: a folder of atmo3d's own (the cache)."""
    src = shipped()
    if src is None:
        raise FileNotFoundError(
            f"the demo run is not in this install (it ships with the atmo3d repository, "
            f"in demo_data/): clone {REPO} and run atmo3d from there, or open your own run")
    root = os.path.abspath(os.path.expanduser(root))
    stamp_file = os.path.join(root, STAMP)
    run = os.path.join(root, RUN)
    stamp = _stamp(src)
    try:
        if not force and open(stamp_file).read().strip() == stamp and os.path.isdir(run):
            return run
    except OSError:
        pass
    os.makedirs(root, exist_ok=True)
    tmp = run + ".part"
    if os.path.isdir(tmp):
        shutil.rmtree(tmp)  # (an earlier copy cut short: ours, in the cache)
    shutil.copytree(src, tmp)
    if os.path.isdir(run):
        shutil.rmtree(run)  # (the out-of-date copy of the demo: ours, in the cache)
    os.replace(tmp, run)
    with open(stamp_file, "w") as fh:
        fh.write(stamp + "\n")
    return run


def is_demo(run_path):
    """A demo run: this one (its stamp file is one folder up), a synthetic test run
    (tests/synthetic.py: two folders up), or one a data type wrote (Model.is_demo)."""
    run = os.path.abspath(run_path)
    for root in (os.path.dirname(run), os.path.dirname(os.path.dirname(run))):
        if os.path.exists(os.path.join(root, STAMP)):
            return True
    from .core import models
    return any(m.is_demo(run_path) for m in models.MODELS.values())
