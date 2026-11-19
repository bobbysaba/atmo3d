#!/bin/bash
# Launch atmo3d:  ./atmo3d.sh [/path/to/cm1/run] [--port 5006] [--cache-gb 16]
# Uses the active Python; create it once with:  conda env create -f environment.yml
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if ! python -c "import panel, netCDF4, metpy, numba, plotly" >/dev/null 2>&1; then
    echo "atmo3d: this Python lacks atmo3d's packages. Create the environment once," >&2
    echo "  conda env create -f $HERE/environment.yml" >&2
    echo "then run:  conda activate atmo3d" >&2
    exit 1
fi
export PYTHONPATH="$HERE${PYTHONPATH:+:$PYTHONPATH}"
exec python -m atmo3d "$@"
