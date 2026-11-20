"""Phase 4 step 1: check that every CfRadial file in a folder shares one layout.

Reads metadata and 1D variables only (no (time, range) field data).
Usage: python check_layout.py /path/to/folder
"""
import sys, glob, os
import numpy as np
import netCDF4

def chars(v):
    return netCDF4.chartostring(v[:]).tolist() if v.ndim > 1 else str(netCDF4.chartostring(v[:]))

def describe(path):
    d = {}
    with netCDF4.Dataset(path) as nc:
        d["dims"] = {k: len(v) for k, v in nc.dimensions.items()}
        d["vars"] = {k: (str(v.dtype), v.dimensions, tuple(v.chunking()) if v.chunking() != "contiguous" else "contig",
                         getattr(v, "units", None)) for k, v in nc.variables.items()}
        d["gattrs"] = {k: str(nc.getncattr(k)) for k in ("instrument_name", "vcp_pattern", "field_names", "version")}
        d["site"] = tuple(round(float(nc[k][...]), 5) for k in ("latitude", "longitude", "altitude"))
        r = nc["range"][:]
        d["range"] = (float(r[0]), float(r[1] - r[0]), len(r), float(r[-1]), bool(np.allclose(np.diff(r), r[1] - r[0])))
        d["fixed_angle"] = tuple(np.round(nc["fixed_angle"][:], 2))
        s0, s1 = nc["sweep_start_ray_index"][:], nc["sweep_end_ray_index"][:]
        d["rays_per_sweep"] = tuple(int(b - a + 1) for a, b in zip(s0, s1))
        d["sweep_mode"] = tuple(chars(nc["sweep_mode"]))
        el, az = nc["elevation"][:], nc["azimuth"][:]
        nyq = nc["nyquist_velocity"][:]
        d["elev_err_max"] = round(float(max(np.abs(el[a:b + 1] - fa).max() for a, b, fa in zip(s0, s1, nc["fixed_angle"][:]))), 2)
        d["az_step"] = tuple(round(float(np.median(np.abs(np.diff(az[a:b + 1])) % 360)), 3) for a, b in zip(s0, s1))
        d["nyquist"] = tuple(round(float(np.median(nyq[a:b + 1])), 1) for a, b in zip(s0, s1))
        t = nc["time"]
        d["time_units"] = t.units
        d["duration_s"] = round(float(t[-1] - t[0]), 1)
        d["coverage"] = (chars(nc["time_coverage_start"]), chars(nc["time_coverage_end"]))
    return d

files = sorted(glob.glob(os.path.join(sys.argv[1], "*.nc")),
               key=lambda p: int(os.path.basename(p).split("_")[4]))
ref = describe(files[0])
print("reference:", os.path.basename(files[0]))
for k in ("dims", "site", "range", "fixed_angle", "rays_per_sweep", "elev_err_max", "az_step", "nyquist", "duration_s", "gattrs"):
    print(f"  {k}: {ref[k]}")
print(f"  sweep_mode: {set(ref['sweep_mode'])}")
print(f"  {len(ref['vars'])} variables")
always_differ = {"time_units", "duration_s", "coverage", "elev_err_max", "az_step", "nyquist"}
for f in files:
    d = describe(f)
    diffs = [k for k in d if k not in always_differ and d[k] != ref[k]]
    line = f"{os.path.basename(f)}: start {d['coverage'][0]} dur {d['duration_s']} s, elev err {d['elev_err_max']}"
    print(line + ("  SAME" if not diffs else "  DIFFERS: " + ", ".join(diffs)))
    for k in diffs:
        if k == "vars":
            a, b = set(ref["vars"]), set(d["vars"])
            print("    vars only in ref:", sorted(a - b), " only here:", sorted(b - a))
            print("    changed:", sorted(k2 for k2 in a & b if ref["vars"][k2] != d["vars"][k2]))
        else:
            print(f"    {k}: {d[k]}")
    for k in ("nyquist", "az_step"):
        if d[k] != ref[k]:
            print(f"    ({k}: {d[k]})")
