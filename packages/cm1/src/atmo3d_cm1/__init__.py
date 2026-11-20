"""atmo3d's CM1 data type: reader, field catalog, demo.

The one-line registration atmo3d finds through the "atmo3d.datatypes" entry point
(pyproject.toml): register() adds the data type's Model and its field catalog.
"""


def register():
    from atmo3d.core import models, services
    from atmo3d.viewer import ext, panels
    from . import catalog  # noqa: F401  (registers the field catalog)
    from . import parcels, pdecomp, trajcalc
    from .model import CM1
    from .panel import ParcelsPanel

    # tools shared code reaches without importing this package (core.services)
    services.provide("pdecomp", pdecomp)
    services.provide("parcels", parcels)
    services.provide("trajcalc", trajcalc)
    # the Parcels panel: its Viewer mixin, and its tool on the rail (before "3D region")
    ext.register_mixin(ParcelsPanel)
    panels.register(panels.Tool(
        "Parcels", "Parcels", "grain",
        "Parcels: click the map (or drag a box) to choose parcels and draw their "
        "trajectories", layout=lambda v: v._par_layout(), modes=("Parcel box",),
        needs="parcels"), before="3D region")
    return models.register(CM1())
