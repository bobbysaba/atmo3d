"""Radar as a data type: the Model that tells atmo3d a folder holds radar volumes."""
import os

from atmo3d.core.models import Model, is_file


class Radar(Model):
    """A folder of CfRadial volumes, one file per time (atmo3d_radar.cfradial)."""
    key, label = "radar", "Radar"

    @property
    def run_class(self):
        from .run import PolarRun
        return PolarRun

    def count(self, path):
        from .run import count
        return count(path)

    def looks(self, entries):
        # (the names, then the header of the first file that could be a volume)
        from . import cfradial
        for e in sorted((e for e in entries if is_file(e) and cfradial.candidate(e.name)),
                        key=lambda e: e.name):
            return cfradial.is_cfradial(e.path)
        return False

    def summary(self, path):
        n = self.count(path)
        return f"{n} volume{'s' * (n != 1)}" if n else ""
