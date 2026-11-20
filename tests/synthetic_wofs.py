"""A tiny synthetic WoFS run for the tests (WRF's own grids and names): make_wofs writes
cycle folders of wrfout_d01_<time>_<member> files beside DART files that must be ignored.
Its values (_expect) are what tests/wofs/test_wofs.py checks the reader against."""
import datetime
import os

import netCDF4
import numpy as np

from atmo3d_wofs.demo import PROJ

NI, NJ, NK, NC = 8, 6, 5, 3  # mass points, levels, cycles (every 3 minutes)
G = 9.81
START = datetime.datetime(2022, 5, 23, 22, 0)
# WoFS's projection, the grid centred on the Texas / New Mexico border (103.06° W)
ON_MAP = dict(PROJ, CEN_LON=np.float32(-103.03), CEN_LAT=np.float32(34.0))


def _expect(m, c):
    """The synthetic fields of member m at cycle c (on WRF's own grids)."""
    k = np.arange(NK, dtype=np.float32)[:, None, None]
    kw = np.arange(NK + 1, dtype=np.float32)[:, None, None]
    i = np.arange(NI, dtype=np.float32)
    hgt = np.broadcast_to(100.0 + 100.0 * i, (NJ, NI)).astype(np.float32)  # a slope
    shape = (NK, NJ, NI)
    return dict(
        T=np.broadcast_to(m + 0.1 * c + k, shape),
        P=np.full(shape, 100.0 * c, np.float32),
        PB=np.broadcast_to(1.0e5 - 1000.0 * k, shape),
        QVAPOR=np.full(shape, 0.01 + 0.001 * m + 0.0001 * c, np.float32),
        QCLOUD=np.zeros(shape, np.float32), QRAIN=np.zeros(shape, np.float32),
        QICE=np.zeros(shape, np.float32), QSNOW=np.zeros(shape, np.float32),
        QGRAUP=np.zeros(shape, np.float32), QHAIL=np.zeros(shape, np.float32),
        REFL_10CM=np.full(shape, 10.0 * c, np.float32),
        U=np.broadcast_to(np.arange(NI + 1, dtype=np.float32) + c + m, (NK, NJ, NI + 1)),
        V=np.broadcast_to(np.arange(NJ + 1, dtype=np.float32)[:, None] - c,
                          (NK, NJ + 1, NI)),
        W=np.broadcast_to(kw + c, (NK + 1, NJ, NI)),
        # levels 500 m apart above the ground at first, then stretched by c (20 + 5 i)
        # m a level: heights that change with time and from column to column
        PH=(G * c * (20.0 + 5.0 * i) * kw).astype(np.float32),
        PHB=(G * (hgt + 500.0 * kw)).astype(np.float32),
        HGT=hgt,
        UP_HELI_MAX=np.full((NJ, NI), float(c), np.float32),
    )


_DIMS = dict(T="zyx", P="zyx", PB="zyx", QVAPOR="zyx", QCLOUD="zyx", QRAIN="zyx",
             QICE="zyx", QSNOW="zyx", QGRAUP="zyx", QHAIL="zyx", REFL_10CM="zyx",
             U="zyX", V="zYx", W="Zyx", PH="Zyx", PHB="Zyx", HGT="yx", UP_HELI_MAX="yx")
_NAMES = dict(z="bottom_top", Z="bottom_top_stag", y="south_north", Y="south_north_stag",
              x="west_east", X="west_east_stag")


def make_wofs(root, members=(1, 2, 3), cycles=NC):
    """A synthetic WoFS run folder: `cycles` cycle folders of member files, each beside
    the DART files a real run has (left empty: they must not be read)."""
    os.makedirs(root, exist_ok=True)
    open(os.path.join(root, "add_noise.csh"), "w").close()
    for c in range(cycles):
        when = START + datetime.timedelta(minutes=3 * c)
        cyc = os.path.join(root, f"{when:%Y%m%d%H%M}")
        os.makedirs(cyc, exist_ok=True)
        for junk in (f"output_mean.nc.{when:%Y%m%d%H%M}", f"obs_seq.final.{when:%Y%m%d%H%M}",
                     "rsl.out.integration.1"):
            open(os.path.join(cyc, junk), "w").close()
        for m in members:
            open(os.path.join(cyc, f"wrfinput_d01.{m}"), "w").close()
            fn = os.path.join(cyc, f"wrfout_d01_{when:%Y-%m-%d_%H:%M:%S}_{m}")
            with netCDF4.Dataset(fn, "w", format="NETCDF3_64BIT_OFFSET") as d:
                d.createDimension("Time", None)
                d.createDimension("DateStrLen", 19)
                for dim, n in (("west_east", NI), ("south_north", NJ), ("bottom_top", NK),
                               ("west_east_stag", NI + 1), ("south_north_stag", NJ + 1),
                               ("bottom_top_stag", NK + 1), ("soil_layers_stag", 4)):
                    d.createDimension(dim, n)
                d.setncatts(dict(DX=np.float32(1000.0), DY=np.float32(1000.0),
                                 TITLE=" OUTPUT FROM WRF V3.9 MODEL", MP_PHYSICS=18,
                                 **ON_MAP))
                ts = d.createVariable("Times", "S1", ("Time", "DateStrLen"))
                ts[0] = netCDF4.stringtochar(np.array([f"{when:%Y-%m-%d_%H:%M:%S}"], "S19"))
                for name, a in _expect(m, c).items():
                    v = d.createVariable(name, "f4", ("Time",) + tuple(
                        _NAMES[ch] for ch in _DIMS[name]))
                    v.setncatts(dict(description=f"synthetic {name}", units="x",
                                     stagger=""))
                    v[0] = a
                # fields that are not on the model grid: left out
                d.createVariable("TSLB", "f4", ("Time", "soil_layers_stag", "south_north",
                                                "west_east"))[0] = 0.0
                d.createVariable("XLAT_U", "f4", ("Time", "south_north",
                                                  "west_east_stag"))[0] = 0.0
                d.createVariable("XTIME", "f4", ("Time",))[0] = 0.0
    return root

