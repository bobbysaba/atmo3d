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

    # the toolbar's Native / Regridded switch (core.models parts)
    parts_tip = ("Native sweeps, or the volumes regridded (off unless chosen: the "
                 "settings are confirmed first; radar_regrid_* in ⚙ Settings)")

    def count(self, path):
        from .run import count
        from . import regrid
        got = regrid.parse(path)
        return count(got[0] if got else path)

    def parts(self, path, entries=None):
        """The folder's native run and its regridded one (with the settings in
        core.config): the toolbar's switch."""
        from . import regrid
        got = regrid.parse(path)
        folder = got[0] if got else os.path.abspath(path)
        return [folder, regrid.path_of(folder, regrid.from_config())]

    def parts_of(self, path):
        """A regridded run's switch: the native run and itself (its own settings, which
        a session or figure may hold, not necessarily those in core.config)."""
        from . import regrid
        got = regrid.parse(path)
        return [got[0], os.path.abspath(path).rstrip("/")] if got else []

    def virtual(self, path):
        from . import regrid
        got = regrid.parse(path)
        return got is not None and os.path.isdir(got[0])

    def part_label(self, path):
        from . import regrid
        got = regrid.parse(path)
        return f"Regridded ({got[1].label})" if got else "Native sweeps"

    def folder_label(self, path):
        """The native run's name in the switch (a folder of volumes)."""
        return "Native sweeps" if self.count(path) else None

    def open(self, path, **kw):
        from . import regrid
        if regrid.parse(path) is not None:
            return regrid.RegriddedRun(path, **kw)
        return self.run_class(path, **kw)

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
