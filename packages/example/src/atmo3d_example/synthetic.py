"""A small synthetic run in the example's layout (run.py), with fields known in closed
form, for the tests (tests/example/test_example.py) and the demo (atmo3d --demo example).

A copy for another data type writes its own files' layout: the same dimension and
variable names, units, attributes and quirks as the real files (from their header,
`ncdump -h`), at a tiny size, with values from formulas so the tests know the answers.
Copy no real values into the repository.

write(folder) makes two files of two times each, five minutes apart:

  gridded_20260520_2100.nc   21:00, 21:05
  gridded_20260520_2110.nc   21:10, 21:15   (and tke, which the first file lacks)

on a 24 x 20 x 12 grid, 1 km apart in x and y, 0.5 km in z.  At time t (s), height z,
x, y (km), with the bubble centred at (X0 + U_MOVE t, Y0 + V_MOVE t):

  u     = 10 + 2 z                     m/s
  v     = 5 - z                        m/s
  w     = W0 b(x, y, t) sin(pi zf / ZTOP)   on the staggered levels zf (0 at both ends)
  theta = 300 + 4 z + 2 b              K
  pres  = 1e5 exp(-z / 8)              Pa
  qv    = 14 exp(-z / 2.5)             g/kg in the files (the reader gives kg/kg)
  dbz   = 60 b - 5 z                   dBZ, the fill value where it is below 5
  rain  = t / 60 * b                   mm (2D)
  tke   = 1                            m²/s² (second file only)

where b = exp(-((x - xc)² + (y - yc)²) / R²)."""
import datetime as dt
import os

import netCDF4
import numpy as np

NX, NY, NZ = 24, 20, 12
DX, DZ = 1.0, 0.5            # km
ZTOP = NZ * DZ               # km (the top staggered level)
X0, Y0, R = 8.0, 8.0, 3.0    # km: the bubble at the first time, and its radius
U_MOVE, V_MOVE = 10.0, 5.0   # m/s: how the bubble moves
W0 = 20.0                    # m/s
START = dt.datetime(2026, 5, 20, 21, 0)
STEP = 300                   # s between times
FILES = {"gridded_20260520_2100.nc": (0, 1), "gridded_20260520_2110.nc": (2, 3)}
FILL = -9999.0
TIME_UNITS = f"seconds since {START:%Y-%m-%d %H:%M:%S}"


def coords():
    """x, y, z (scalar levels) and zf (staggered levels), km."""
    x = np.arange(NX) * DX
    y = np.arange(NY) * DX
    zf = np.arange(NZ + 1) * DZ
    return x, y, 0.5 * (zf[:-1] + zf[1:]), zf


def bubble(t, x, y):
    xc = X0 + U_MOVE * t / 1000.0
    yc = Y0 + V_MOVE * t / 1000.0
    return np.exp(-((x[None, :] - xc) ** 2 + (y[:, None] - yc) ** 2) / R**2)


def fields(t):
    """{name: array} of every field at time t (s), as the files hold it (qv in g/kg,
    w on the staggered levels, dbz with the fill value), and the 2D ones (ny, nx)."""
    x, y, z, zf = coords()
    b = bubble(t, x, y)
    Z = z[:, None, None] * np.ones((NZ, NY, NX))
    dbz = 60.0 * b[None] - 5.0 * Z
    return {
        "u": 10.0 + 2.0 * Z,
        "v": 5.0 - Z,
        "w": W0 * b[None] * np.sin(np.pi * zf / ZTOP)[:, None, None],
        "theta": 300.0 + 4.0 * Z + 2.0 * b[None],
        "pres": 1e5 * np.exp(-Z / 8.0),
        "qv": 14.0 * np.exp(-Z / 2.5),
        "dbz": np.where(dbz < 5.0, FILL, dbz),
        "rain": t / 60.0 * b,
        "tke": np.ones((NZ, NY, NX)),
    }


# name: (dimensions after time, long_name, units)
LAYOUT = {
    "u": (("z", "y", "x"), "x wind", "m/s"),
    "v": (("z", "y", "x"), "y wind", "m/s"),
    "w": (("z_stag", "y", "x"), "vertical velocity", "m/s"),
    "theta": (("z", "y", "x"), "potential temperature", "K"),
    "pres": (("z", "y", "x"), "pressure", "Pa"),
    "qv": (("z", "y", "x"), "water vapor mixing ratio", "g/kg"),
    "dbz": (("z", "y", "x"), "radar reflectivity", "dBZ"),
    "rain": (("y", "x"), "accumulated rain", "mm"),
    "tke": (("z", "y", "x"), "subgrid turbulence kinetic energy", "m2/s2"),
}


def write(folder):
    """Write the run into folder (made if need be); returns the file paths."""
    os.makedirs(folder, exist_ok=True)
    x, y, z, zf = coords()
    out = []
    for i, (name, ts) in enumerate(FILES.items()):
        path = os.path.join(folder, name)
        with netCDF4.Dataset(path, "w") as d:
            d.title = "atmo3d example: synthetic gridded run"
            d.createDimension("time", None)
            for dim, n in (("z", NZ), ("z_stag", NZ + 1), ("y", NY), ("x", NX)):
                d.createDimension(dim, n)
            tv = d.createVariable("time", "f8", ("time",))
            tv.units, tv.calendar = TIME_UNITS, "standard"
            for dim, vals in (("x", x), ("y", y), ("z", z), ("z_stag", zf)):
                c = d.createVariable(dim, "f4", (dim,))
                c[:], c.units = vals * 1000.0, "m"
            for n, (dims, long_name, units) in LAYOUT.items():
                if n == "tke" and i == 0:
                    continue  # (a field only the later file has)
                v = d.createVariable(n, "f4", ("time",) + dims,
                                     fill_value=FILL if n == "dbz" else None)
                v.long_name, v.units = long_name, units
            for k, ti in enumerate(ts):
                t = ti * STEP
                tv[k] = t
                for n, a in fields(t).items():
                    if n in d.variables:
                        d[n][k] = a
        out.append(path)
    return out
