"""atmo3d's radar data type: CfRadial volumes read in their native polar geometry.

The one-line registration atmo3d finds through the "atmo3d.datatypes" entry point
(pyproject.toml): register() adds the data type's Model and its field catalog.
"""


def register():
    from atmo3d.core import models
    from . import catalog  # noqa: F401  (registers the field catalog)
    from .model import Radar
    return models.register(Radar())
