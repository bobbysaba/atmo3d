"""CM1 as a data type: the Model that tells atmo3d where a CM1 run is and how to open it."""
import glob
import os

from atmo3d.core.models import Model, is_file


class CM1(Model):
    """CM1: a folder of netCDF output files (names by the output_glob setting)."""
    key, label = "cm1", "CM1"
    api = "1.1"  # (atmo3d.API_VERSION it is written for)

    @property
    def run_class(self):
        from .run import CM1Run
        return CM1Run

    def count(self, path):
        from atmo3d import config
        return len(glob.glob(os.path.join(path, config.get("output_glob"))))

    def looks(self, entries):
        from atmo3d import config
        return any(is_file(e) and config.is_output(e.name) for e in entries)

    def make_demo(self, root):
        from atmo3d import demo
        return demo.make(os.path.join(root, "cm1"))
