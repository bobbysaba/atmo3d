"""atmo3d's WoFS data type (DART-cycled WRF output): reader, field catalog, demo data.

The one-line registration atmo3d finds through the "atmo3d.datatypes" entry point
(pyproject.toml): register() adds the data type's Model and its field catalog.
"""


def register():
    from atmo3d.core import models
    from . import catalog  # noqa: F401  (registers the field catalog)
    from .model import WoFS
    return models.register(WoFS())
