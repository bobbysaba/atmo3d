"""atmo3d: interactive quicklook / sounding / cross-section / 3D viewer for CM1 output.

Copyright (C) 2026 Bobby Saba

This program is free software: you can redistribute it and/or modify it under the terms
of the GNU General Public License as published by the Free Software Foundation, either
version 3 of the License, or (at your option) any later version.  It is distributed in
the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied
warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the LICENSE file
or <https://www.gnu.org/licenses/>."""

import os as _os

__version__ = "2.2.0"

# The version of the extension API: what a data-type package may use (the registration
# calls, Model, Catalog, Source / Run and their hooks, the roles and capabilities, and
# atmo3d.testing; docs/datatypes.md lists it).  MAJOR.MINOR: a minor release only adds to
# it; anything a package could rely on changes only with the major number.  A Model says
# which version it was written for (Model.api); core.models.register refuses one whose
# major differs, or whose minor is newer than this core's.
API_VERSION = "1.0"

# numba's thread pool (sounding-parameter maps) starts one thread per CPU it sees; on a
# shared login node that is far more than this job may use (readers stop at 8 too)
if "NUMBA_NUM_THREADS" not in _os.environ and hasattr(_os, "sched_getaffinity"):
    _os.environ["NUMBA_NUM_THREADS"] = str(max(1, min(len(_os.sched_getaffinity(0)), 8)))
