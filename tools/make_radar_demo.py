"""Build atmo3d's radar demo from a folder of CfRadial volumes:
python tools/make_radar_demo.py SRC OUT

Run once by a maintainer when the demo changes; atmo3d itself only reads the result.
SRC is a folder of CfRadial files, one volume per time (atmo3d_radar.cfradial); OUT
receives a smaller copy of each, under the same name, which atmo3d opens as it opens the
original.  Every volume, sweep, ray and gate is kept; the size comes down by:

  rays      only the rays the sweep table covers (files pad `time` past the last sweep
            with rays the reader never reads); azimuth, elevation and the other
            per-ray variables are cut to match
  fields    DROP left out (receiver QC and the uncorrected input velocity, which the
            demo does not need); field_names is updated to match
  packing   each (time, range) field as 16-bit integers at the step in STEP
            (scale_factor, add_offset, float32, as CF packing; the step coarsened by
            powers of two only where a field's range in a file needs more than 16 bits),
            65535 where the value is missing (_FillValue).  Fields holding only whole
            numbers 0..254 (flags, counts) are stored as bytes exactly, 255 missing.
            valid_min/valid_max are left out: netCDF readers compare them with the
            stored codes, not the values.  zlib and shuffle throughout.  A float field
            with no STEP is kept as float32

The global attributes are copied, with an atmo3d_demo note saying how the copy was made.
Each file is written beside its name and renamed when complete, so an interrupted build
leaves no half files; files already in OUT are skipped (--force rewrites them).

Example (the bistatic KTLX demo):

    python tools/make_radar_demo.py \\
        /glade/derecho/scratch/$USER/20260403_20260404_results \\
        /glade/work/$USER/radar_demo/ktlx_bistatic
"""

import argparse
import os
import sys

import netCDF4
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "packages", "radar", "src"))
from atmo3d_radar.cfradial import files_in  # noqa: E402

MAXCODE = 65534  # (65535 is the fill)
FIELD_DIMS = ("time", "range")

DROP = {"receiver_rcp_nwc", "receiver_ncp_nwc", "original_bistatic_velocity_nwc"}

# field -> step kept, in its units (at or finer than NEXRAD Level II's own resolution
# for the base moments)
STEP = {
    "reflectivity": 0.5, "clutter_filter_power_removed": 0.5,
    "velocity": 0.1, "spectrum_width": 0.5,
    "differential_reflectivity": 0.0625, "cross_correlation_ratio": 0.002,
    "differential_phase": 0.25,
    "beta_nwc": 0.05,
    "bistatic_velocity_nwc": 0.05, "bistatic_velocity_unsmoothed_nwc": 0.05,
    "u": 0.05, "v": 0.05, "w": 0.05, "w_direct": 0.05,
}
SKIP_ATTRS = {"_FillValue", "valid_min", "valid_max", "valid_range", "missing_value",
              "scale_factor", "add_offset"}


def values(v, n):
    """The first n rays of (time, range) variable v as float64, NaN where missing."""
    v.set_auto_maskandscale(True)
    return np.ma.filled(np.ma.asarray(v[:n]).astype(np.float64), np.nan)


def pack(a, step):
    """(codes u2, scale, offset): a's finite values in steps of `step` (doubled until
    the range fits in MAXCODE codes), 65535 where a is NaN."""
    ok = np.isfinite(a)
    codes = np.full(a.shape, MAXCODE + 1, np.uint16)
    if not ok.any():
        return codes, np.float32(step), np.float32(0.0)
    lo, hi = float(a[ok].min()), float(a[ok].max())
    while (hi - lo) / step > MAXCODE:
        step *= 2.0
    codes[ok] = np.round((a[ok] - lo) / step).astype(np.uint16)
    return codes, np.float32(step), np.float32(lo)


def small_ints(a):
    """Whether a's finite values are all whole numbers 0..254 (or there are none)."""
    f = a[np.isfinite(a)]
    return f.size == 0 or (f.min() >= 0 and f.max() <= 254 and (f == np.round(f)).all())


def copy_file(src, dst, note):
    with netCDF4.Dataset(src) as s, netCDF4.Dataset(dst + ".part", "w") as d:
        s.set_auto_mask(False)
        nray = int(np.asarray(s["sweep_end_ray_index"][:]).max()) + 1
        attrs = {k: s.getncattr(k) for k in s.ncattrs()}
        if "field_names" in attrs:
            attrs["field_names"] = ", ".join(
                f for f in str(attrs["field_names"]).split(", ") if f not in DROP)
        attrs["atmo3d_demo"] = note
        d.setncatts(attrs)
        for n, dim in s.dimensions.items():
            d.createDimension(n, None if dim.isunlimited() and n != "time"
                              else (nray if n == "time" else len(dim)))
        for n, v in s.variables.items():
            if n in DROP:
                continue
            vattrs = {k: v.getncattr(k) for k in v.ncattrs()}
            kw = dict(zlib=True, complevel=6, shuffle=True)
            if v.dimensions != FIELD_DIMS:  # coordinates, sweep table, site, strings
                cut = (slice(0, nray),) if v.dimensions[:1] == ("time",) else ...
                a = v[cut]
                fill = vattrs.pop("_FillValue", None)
                nv = d.createVariable(n, v.dtype, v.dimensions, fill_value=fill,
                                      **(kw if v.ndim else {}))
                nv.setncatts(vattrs)
                nv.set_auto_maskandscale(False)
                nv[...] = a
                continue
            a = values(v, nray)
            keep = {k: x for k, x in vattrs.items() if k not in SKIP_ATTRS}
            chunk = (min(360, nray), a.shape[1])
            if small_ints(a):
                codes = np.where(np.isfinite(a), a, 255).astype(np.uint8)
                nv = d.createVariable(n, "u1", FIELD_DIMS, fill_value=np.uint8(255),
                                      chunksizes=chunk, **kw)
                nv.setncatts(keep)
            elif n in STEP:
                codes, scale, offset = pack(a, STEP[n])
                nv = d.createVariable(n, "u2", FIELD_DIMS, fill_value=np.uint16(65535),
                                      chunksizes=chunk, **kw)
                nv.setncatts(keep)
                nv.scale_factor, nv.add_offset = scale, offset
            else:
                codes = a.astype(np.float32)
                nv = d.createVariable(n, "f4", FIELD_DIMS, fill_value=np.float32(np.nan),
                                      chunksizes=chunk, **kw)
                nv.setncatts(keep)
            nv.set_auto_maskandscale(False)
            nv[:] = codes
    os.replace(dst + ".part", dst)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src", help="the folder of CfRadial volumes")
    ap.add_argument("out", help="the demo's folder (created; its name is the run's name)")
    ap.add_argument("--force", action="store_true", help="rewrite files already in OUT")
    a = ap.parse_args(argv)

    src = os.path.abspath(a.src)
    found = files_in(src)
    if not found:
        raise SystemExit(f"no CfRadial volumes in {src}")
    note = (f"atmo3d demo: {os.path.basename(src)}, padding rays and "
            f"{', '.join(sorted(DROP))} removed, fields 16-bit packed "
            f"(tools/make_radar_demo.py)")
    os.makedirs(a.out, mode=0o755, exist_ok=True)
    total = 0
    for _, f in found:
        dst = os.path.join(a.out, os.path.basename(f))
        if a.force or not os.path.exists(dst):
            copy_file(f, dst, note)
        size = os.path.getsize(dst)
        total += size
        print(f"{os.path.basename(dst)}  {size / 1e6:.1f} MB", flush=True)
    print(f"{len(found)} volumes: {total / 1e6:.0f} MB in {a.out}")


if __name__ == "__main__":
    main()
