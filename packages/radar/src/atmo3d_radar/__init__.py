"""atmo3d's radar data type: CfRadial volumes read in their native polar geometry.

The one-line registration atmo3d finds through the "atmo3d.datatypes" entry point
(pyproject.toml): register() adds the data type's Model, its field catalog and the PPI
panel (the map shows a sweep; the panel lists them and the gate under a click).
"""


def register():
    from atmo3d.core import models
    from atmo3d.viewer import ext, panels
    from . import catalog  # noqa: F401  (registers the field catalog)
    from .model import Radar
    from .panel import PPIPanel

    # the PPI panel: its Viewer mixin, and its tool on the rail (after the built-in ones,
    # so a saved session's tab numbers stay as they were)
    ext.register_mixin(PPIPanel)
    panels.register(panels.Tool(
        "PPI", "PPI", "radar", "Radar sweeps: pick the one the map shows; click the map "
        "to see the gate there", layout=lambda v: v._ppi_layout(), title="PPI sweeps",
        needs="native_polar", click=lambda v, x, y, shift: v._ppi_click(x, y),
        hint="Click the map: the gate there, in the sweep shown · pick the sweep in the "
             "panel"))
    return models.register(Radar())
