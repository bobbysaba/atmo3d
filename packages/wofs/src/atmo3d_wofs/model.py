"""WoFS as a data type: the Model that tells atmo3d where a WoFS experiment is and how to open it."""
import os

from atmo3d.core.models import Model


class WoFS(Model):
    """WoFS (DART-cycled WRF): an experiment folder of date folders of cycle folders of
    member wrfouts.  The experiment is one run; its members (and their mean) are read
    as runs of their own (parts)."""
    key, label = "wofs", "WoFS"

    @property
    def run_class(self):
        from .run import WoFSRun
        return WoFSRun

    def count(self, path):
        from . import run as wofs
        return wofs.count(path)

    def looks(self, entries):
        from . import run as wofs
        entries = list(entries)
        # (one or two more listings: the first date folder, the first cycle folder)
        return bool(entries) and bool(wofs.members(os.path.dirname(entries[0].path), entries))

    def runs(self, path, entries):
        return [path]  # (the experiment: one run)

    def parts(self, path, entries=None):
        from . import run as wofs
        return wofs.run_paths(path, entries)

    def summary(self, path):
        from . import run as wofs
        root = path if os.path.isdir(path) else (wofs.mean_of(path)
                                                 or (wofs.member_of(path) or ("",))[0])
        n = len(wofs.members(root)) if root else 0
        return f"{n} member{'s' * (n != 1)}" if n else ""

    def part_label(self, path):
        from . import run as wofs
        rm = wofs.member_of(path)
        return f"Member {rm[1]}" if rm else "Ensemble mean"

    def virtual(self, path):
        from . import run as wofs
        return wofs.is_member(path) or wofs.is_mean(path)

    def open(self, path, **kw):
        from . import run as wofs
        return wofs.open_run(path, **kw)

    def canonical(self, path):
        from . import run as wofs
        return wofs.open_path(path) if os.path.isdir(path) else path

    def make_demo(self, root):
        from . import demo
        return demo.make(root)

    def is_demo(self, path):
        from . import demo
        return demo.is_demo(path)
