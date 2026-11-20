"""atmo3d's worked example of a data type: gridded netCDF with named x, y, z and time.

It is real (it reads such files, and its tests run in CI on every core change) and as
small as a data type gets.  It is not part of the atmo3d app: it is the pattern to copy
(tools/new_datatype.py) and the documentation that cannot drift from the code.  Every
file says what is REQUIRED and what is optional.

  model.py      the Model: is a folder one of these runs, how many times, how to open it
  catalog.py    the field catalog: the files' names, how they show, which field plays
                each role (u, v, w, theta, ...)
  run.py        the reader: a core.run.Run subclass
  synthetic.py  writes a small run with known values, for the tests and the demo

The contract is docs/datatypes.md; atmo3d.testing.check_datatype checks it.
"""


def register():
    """REQUIRED: the function the entry point names (pyproject.toml).  It registers the
    field catalog and the Model, and returns the Model."""
    from atmo3d.core import models
    from . import catalog  # noqa: F401  (importing it registers the field catalog)
    from .model import Example

    # optional: a data type with tools of its own registers them here too (a rail button
    # and its panel: viewer.panels.register, viewer.ext.register_mixin; a service shared
    # code reaches: core.services.provide).  See atmo3d_radar/__init__.py.
    return models.register(Example())
