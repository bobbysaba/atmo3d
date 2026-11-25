"""atmo3d's radar data type: CfRadial or NEXRAD Level II volumes read in their native
polar geometry.

The one-line registration atmo3d finds through the "atmo3d.datatypes" entry point
(pyproject.toml): register() adds the data type's Model, its field catalog and the PPI
panel (the map shows a sweep, a height or the column max; the panel lists the sweeps,
and the gate and column under a click).  Sections and 3D sample the volumes natively
(atmo3d_radar.sampler, atmo3d_radar.scene) through core hooks on the run.  The
optional regrid (atmo3d_radar.regrid, regrid_ui) is another run of the same folder.
The run picker gets "NEXRAD from AWS…" (atmo3d_radar.aws, aws_ui): Level II volumes
downloaded from the public archive into a folder, then opened; or Live (atmo3d_radar.live,
live_ui): the last hour, then each new volume as it comes, the view following.  Radial
velocity is also offered dealiased (atmo3d_radar.dealias).
"""


def register():
    from atmo3d.core import models
    from atmo3d.viewer import ext, panels, picker
    from . import catalog  # noqa: F401  (registers the field catalog)
    from .model import Radar
    from .panel import PPIPanel
    from .regrid_ui import RegridSwitch
    from .live_ui import LiveFollow

    # the PPI panel: its Viewer mixin, and its tool on the rail (after the built-in ones,
    # so a saved session's tab numbers stay as they were)
    ext.register_mixin(PPIPanel)
    ext.register_mixin(RegridSwitch)  # (the Native / Regridded switch's dialog)
    ext.register_mixin(LiveFollow)  # (a folder of NEXRAD volumes followed live)
    panels.register(panels.Tool(
        "PPI", "PPI", "radar", "Radar sweeps: pick the one the map shows; click the map "
        "to see the gate and the column there", layout=lambda v: v._ppi_layout(),
        title="PPI sweeps", needs="native_polar", click=lambda v, x, y, shift: v._ppi_click(x, y),
        hint="Click the map: the gate there (in the sweep shown) and the column above it · "
             "pick the sweep in the panel"))
    from . import aws_ui
    picker.register_source(aws_ui.LABEL, aws_ui.TIP, aws_ui.build)
    return models.register(Radar())
