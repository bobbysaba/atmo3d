"""The Model: what the run picker and auto-detect ask about a folder.

Keep looks() and count() cheap: the picker calls them on every folder it lists, often
on a shared filesystem.  Decide from file names, never by opening files.  And keep this
module light: atmo3d imports it at start-up, so the reader (run.py, netCDF4) is
imported only when a run opens."""
import fnmatch
import glob
import os

from atmo3d.core.models import Model, is_file

# the files of a run: what looks() and count() go by, and what the reader opens
PATTERN = "gridded_*.nc"
# the files' time dimension (and coordinate variable)
TIME = "time"
# a file make_demo() leaves in the demo run it writes (is_demo)
DEMO_MARKER = ".atmo3d-example-demo"


class Example(Model):
    """A folder of gridded netCDF files named by PATTERN."""

    # REQUIRED: the key (also the run class's `model` and the catalog's key) and the
    # name lists show
    key, label = "example", "Example (gridded netCDF)"
    # REQUIRED: the extension API this is written for (atmo3d.API_VERSION)
    api = "1.0"

    @property
    def run_class(self):
        """REQUIRED: the reader class.  A property, so run.py (and netCDF4) load only
        when a run opens, not when atmo3d starts."""
        from .run import ExampleRun
        return ExampleRun

    def looks(self, entries):
        """REQUIRED: from one folder listing (os.scandir entries; read nothing else), is
        this a run of this type?"""
        return any(is_file(e) and fnmatch.fnmatch(e.name, PATTERN) for e in entries)

    def count(self, path):
        """REQUIRED: the number of output times in the folder (0: none).  The picker
        shows it ("8 output times") and auto-detect asks it of a folder chosen, so it
        may read a little, but not every file of a long run: here, the files times the
        times in the first (one header read; exact when the files hold the same number
        of times, as most models write them).  The run counts them all when it opens."""
        files = sorted(glob.glob(os.path.join(path, PATTERN)))
        if not files:
            return 0
        import netCDF4  # (here, not at the top: this module loads at start-up)
        from atmo3d.core.run import IO_LOCK
        try:
            with IO_LOCK, netCDF4.Dataset(files[0]) as d:
                per_file = len(d.dimensions[TIME])
        except (OSError, KeyError):
            per_file = 1  # (unreadable now, perhaps being written: the run will say)
        return len(files) * max(per_file, 1)

    # ---------------------------------------------------------------- optional
    def summary(self, path):
        """A few words on the folder for the picker ("" for none)."""
        n = len(glob.glob(os.path.join(path, PATTERN)))
        return f"{n} file{'s' if n != 1 else ''}"

    def make_demo(self, root):
        """A demo run (atmo3d --demo example): the synthetic one, written under root."""
        from . import synthetic
        folder = os.path.join(root, "example")
        if not os.path.isfile(os.path.join(folder, DEMO_MARKER)):
            synthetic.write(folder)
            with open(os.path.join(folder, DEMO_MARKER), "w") as f:
                f.write("written by atmo3d_example.synthetic\n")
        return folder

    def is_demo(self, path):
        return os.path.isfile(os.path.join(path, DEMO_MARKER))

    # Not needed here (see atmo3d_wofs/model.py): runs(), parts(), virtual(),
    # part_label(), parts_of(), canonical(), folder_label(), for runs named inside one
    # folder rather than folders of their own (ensemble members, a regridded run).
