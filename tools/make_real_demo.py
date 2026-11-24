"""Build atmo3d's real demo run from a CM1 run:  python tools/make_real_demo.py RUN OUT

Run once by a maintainer when the demo run changes; atmo3d itself only reads the result.
RUN is a finished CM1 run written with output_format = 2, output_filetype = 2 (one
cm1out_NNNNNN.nc per time, plus namelist.input and, optionally, cm1out_pdata.nc).
OUT receives a smaller copy in the same layout, small enough to ship in the repo:

  crop      a square box of --size grid points around the storms (by default centred on
            the run's 5 km updraft swath, `sus` >= 15 m/s in the last file), every level
            kept (stretched vertical grids stay as they are)
  times     every --every seconds of output (t = 0, the base state, always kept);
            the files are renumbered cm1out_000001.nc, ... in time order
  fields    everything but the staggered winds u, v, w (atmo3d uses uinterp, vinterp,
            winterp), the number concentrations nc*, the mixing coefficients km*/kh*,
            the duplicate ground-relative swaths (rain2, sws2, ...), the fields
            atmo3d derives itself (thpert = th - th0, prspert = prs - prs0, buoyancy)
            and the rarely used pi, rho; u0, v0 stay (the base-state wind profile)
  packing   each field as 16-bit integers (scale_factor, add_offset, both float32, as
            CF packing: every netCDF reader unpacks them), with zlib and shuffle, one
            horizontal level per chunk.  The step is the precision in PRECISION
            (e.g. 0.01 m/s, 0.01 K), coarsened by powers of two only where a field's
            range in a file needs more than 16 bits; fields not listed use their full
            range in 16 bits
  parcels   --parcels of the parcels seeded inside the box (most of them ones that
            reach w > 10 m/s, the rest at random; a fixed --seed, so a rebuild picks the
            same ones), every output time, their CM1 ID numbers kept in xh.  A parcel
            that leaves the box is written as -1e30 in x, y, z from then on, as CM1
            writes parcels that leave an open domain.  x, y, z stay float32 (0.1 m)

namelist.input is copied with nx, ny set to the box; the files' global attributes get
the same nx, ny and an atmo3d_demo note saying how the copy was made.

Example (the demo shipped with atmo3d):

    python tools/make_real_demo.py /path/to/real_demo demo_data/supercell
"""

import argparse
import glob
import os
import re

import netCDF4
import numpy as np

DROP = {"u", "v", "w", "nci", "ncs", "ncr", "ncg", "kmh", "kmv", "khh", "khv",
        "rain2", "sws2", "svs2", "sps2", "srs2", "sgs2", "sus2", "shs2",
        "thpert", "prspert", "buoyancy", "pi", "rho"}
PARCEL_DROP = {"nci", "ncs", "ncr", "ncg"}
FLOAT = {"x", "y", "z", "mtime"}  # parcel variables kept as float32

# absolute precision kept, in the variable's units
Q = 1e-7  # mixing ratios, kg/kg
PRECISION = {
    "th": 0.01, "thpert": 0.01, "th0": 0.01, "t": 0.01,
    "prs": 1.0, "prs0": 1.0, "psfc": 1.0, "sps": 1.0, "prspert": 0.1,
    "pi": 1e-5, "pi0": 1e-5, "rho": 1e-4, "buoyancy": 1e-4, "b": 1e-4, "vpg": 1e-5,
    "qv": Q, "qc": Q, "qr": Q, "qi": Q, "qs": Q, "qg": Q, "qv0": Q, "qsl": Q, "qsi": Q,
    "srs": Q, "sgs": Q,
    "dbz": 0.1, "cref": 0.1,
    "uinterp": 0.01, "vinterp": 0.01, "winterp": 0.01, "u0": 0.01, "v0": 0.01,
    "sws": 0.01, "sus": 0.01, "tke": 0.01, "cpc": 0.01, "cph": 1.0,
    "xvort": 1e-5, "yvort": 1e-5, "zvort": 1e-5, "svs": 1e-5,
    "shs": 0.1, "uh": 0.1, "rain": 1e-3, "cape": 1.0, "cin": 0.1, "lcl": 1.0, "lfc": 1.0,
}
PARCEL_PRECISION = dict(PRECISION, u=0.01, v=0.01, w=0.01)
MAXCODE = 65534  # uint16 codes used: 0..MAXCODE


def pack(a, step):
    """(codes uint16, scale, offset) for float array a at precision step (None: full
    16-bit range); step doubles until the range fits."""
    a = np.asarray(a, dtype=np.float64)
    lo, hi = float(a.min()), float(a.max())
    span = hi - lo
    if step is None:
        step = span / MAXCODE if span > 0 else 1.0
    while span / step > MAXCODE:
        step *= 2.0
    codes = np.round((a - lo) / step).astype(np.uint16)
    return codes, np.float32(step), np.float32(lo)


def out_files(run):
    files = sorted(glob.glob(os.path.join(run, "cm1out_[0-9][0-9][0-9][0-9][0-9][0-9].nc")))
    if not files:
        raise SystemExit(f"no cm1out_NNNNNN.nc files in {run}")
    return files


def choose_box(last, size, center):
    """(i0, j0): the box's first scalar column and row."""
    with netCDF4.Dataset(last) as d:
        x, y = d["xh"][:], d["yh"][:]
        if center is None:
            sus = d["sus"][0]
            jj, ii = np.nonzero(sus >= 15.0)
            if not len(ii):
                raise SystemExit("no sus >= 15 m/s in the last file: give --center X,Y")
            center = (float(x[ii].mean()), float(y[jj].mean()))
    if size > min(len(x), len(y)):
        raise SystemExit(f"--size {size} is larger than the domain ({len(x)} x {len(y)})")
    i0 = int(np.clip(np.argmin(np.abs(x - center[0])) - size // 2, 0, len(x) - size))
    j0 = int(np.clip(np.argmin(np.abs(y - center[1])) - size // 2, 0, len(y) - size))
    return i0, j0, center


def crop_slices(dims, i0, j0, size):
    return tuple(slice(i0, i0 + size) if n == "xh" else slice(i0, i0 + size + 1) if n == "xf"
                 else slice(j0, j0 + size) if n == "yh" else slice(j0, j0 + size + 1)
                 if n == "yf" else slice(None) for n in dims)


def copy_var(d, n, v, a, precision, chunk=None):
    """Write a (already cropped) as variable n of d: float coordinates as they are,
    other floats packed."""
    attrs = {k: v.getncattr(k) for k in v.ncattrs() if k != "_FillValue"}
    if a.dtype.kind != "f" or n in d.dimensions or v.ndim <= 1 or precision is False:
        nv = d.createVariable(n, a.dtype, v.dimensions, zlib=v.ndim > 1, complevel=6,
                              shuffle=True, chunksizes=chunk)
        nv.setncatts(attrs)
        nv[:] = a
        return
    codes, scale, offset = pack(a, precision)
    nv = d.createVariable(n, "u2", v.dimensions, zlib=True, complevel=6, shuffle=True,
                          chunksizes=chunk)
    nv.setncatts(attrs)
    nv.scale_factor, nv.add_offset = scale, offset
    nv.set_auto_scale(False)
    nv[:] = codes


def crop_file(src, dst, i0, j0, size, note):
    with netCDF4.Dataset(src) as s, netCDF4.Dataset(dst + ".part", "w") as d:
        s.set_auto_mask(False)
        atts = {k: s.getncattr(k) for k in s.ncattrs()}
        atts.update(nx=np.int32(size), ny=np.int32(size), atmo3d_demo=note)
        d.setncatts(atts)
        for n, dim in s.dimensions.items():
            L = None if dim.isunlimited() else len(dim)
            L = size if n in ("xh", "yh") else size + 1 if n in ("xf", "yf") else L
            d.createDimension(n, L)
        for n, v in s.variables.items():
            if n in DROP:
                continue
            a = np.asarray(v[crop_slices(v.dimensions, i0, j0, size)])
            chunk = (1, 1) + a.shape[2:] if v.ndim == 4 else None
            copy_var(d, n, v, a, PRECISION.get(n), chunk)
    os.replace(dst + ".part", dst)


def parcels(src, dst, box, n_keep, seed, note):
    """box: (x0, x1, y0, y1) in m."""
    x0, x1, y0, y1 = box
    with netCDF4.Dataset(src) as s:
        s.set_auto_mask(False)
        x, y, w = s["x"][:], s["y"][:], s["w"][:]
        inside = (x >= x0) & (x <= x1) & (y >= y0) & (y <= y1)
        cand = np.nonzero(inside[0])[0]
        # leaves the box: gone from its first time outside onwards
        gone = np.cumsum(~inside[:, cand], axis=0) > 0
        wmax = np.where(gone, -np.inf, w[:, cand]).max(axis=0)
        rng = np.random.default_rng(seed)
        up = cand[wmax > 10.0]
        rest = cand[wmax <= 10.0]
        n_up = min(len(up), int(round(0.8 * n_keep)))
        keep = np.concatenate([rng.choice(up, n_up, replace=False),
                               rng.choice(rest, min(len(rest), n_keep - n_up), replace=False)])
        keep.sort()
        gone = (np.cumsum(~inside[:, keep], axis=0) > 0)
        with netCDF4.Dataset(dst + ".part", "w") as d:
            d.setncatts(dict({k: s.getncattr(k) for k in s.ncattrs()}, atmo3d_demo=note))
            for n, dim in s.dimensions.items():
                d.createDimension(n, None if dim.isunlimited() else
                                  len(keep) if n == "xh" else len(dim))
            for n, v in s.variables.items():
                if n in PARCEL_DROP:
                    continue
                a = np.asarray(v[:])
                if n == "xh":
                    a = a[keep]
                elif v.dimensions == ("time", "xh"):
                    a = a[:, keep]
                    if n in ("x", "y", "z"):
                        a = np.where(gone, np.float32(-1e30),
                                     np.round(a, 1)).astype(np.float32)
                copy_var(d, n, v, a, False if n in FLOAT else PARCEL_PRECISION.get(n))
    os.replace(dst + ".part", dst)
    return len(keep), int(n_up)


def write_namelist(src, dst, size):
    text = open(src, encoding="utf-8").read()
    for key in ("nx", "ny"):
        text, n = re.subn(rf"(?im)^(\s*{key}\s*=\s*)\d+", lambda m: m.group(1) + str(size),
                          text, count=1)
        if n != 1:
            raise SystemExit(f"{src}: no {key} = ... line")
    with open(dst, "w", encoding="utf-8") as fh:
        fh.write(text)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python tools/make_real_demo.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run", help="the CM1 run folder")
    ap.add_argument("out", help="folder to write the demo copy into (made if missing)")
    ap.add_argument("--size", type=int, default=80, help="box size, grid points (80)")
    ap.add_argument("--center", help="box centre X,Y in km (default: the updraft swath)")
    ap.add_argument("--every", type=float, default=600.0,
                    help="seconds between the output times kept (600)")
    ap.add_argument("--parcels", type=int, default=1500, help="parcels kept (1500)")
    ap.add_argument("--seed", type=int, default=1, help="parcel choice seed (1)")
    ap.add_argument("--force", action="store_true", help="write into a non-empty OUT, replacing the "
                    "cm1out_*.nc files there")
    a = ap.parse_args(argv)

    files = out_files(a.run)
    if os.path.isdir(a.out) and os.listdir(a.out) and not a.force:
        raise SystemExit(f"{a.out} is not empty (--force to write into it)")
    os.makedirs(a.out, exist_ok=True)
    for old in glob.glob(os.path.join(a.out, "cm1out_*.nc")):  # (--force: an earlier copy's)
        os.remove(old)
    center = tuple(float(c) for c in a.center.split(",")) if a.center else None
    i0, j0, center = choose_box(files[-1], a.size, center)
    with netCDF4.Dataset(files[0]) as d:
        xf, yf = d["xf"][:], d["yf"][:]
    box = (float(xf[i0]), float(xf[i0 + a.size]), float(yf[j0]), float(yf[j0 + a.size]))
    note = (f"atmo3d demo: cropped to x {box[0]:g}..{box[1]:g} km, y {box[2]:g}..{box[3]:g} "
            f"km, every {a.every:g} s, fields packed to 16 bits (tools/make_real_demo.py)")
    print(f"box centre ({center[0]:.1f}, {center[1]:.1f}) km: x {box[0]:g}..{box[1]:g}, "
          f"y {box[2]:g}..{box[3]:g} km ({a.size} x {a.size})")

    kept = []
    for f in files:
        with netCDF4.Dataset(f) as d:
            t = float(d["time"][0])
        if abs(t / a.every - round(t / a.every)) < 1e-6:
            kept.append((t, f))
    total = 0
    for n, (t, f) in enumerate(kept, 1):
        dst = os.path.join(a.out, f"cm1out_{n:06d}.nc")
        crop_file(f, dst, i0, j0, a.size, note)
        mb = os.path.getsize(dst) / 1e6
        total += mb
        print(f"  t = {t:6.0f} s  {os.path.basename(f)} -> {os.path.basename(dst)}  {mb:5.2f} MB")

    nml = os.path.join(a.run, "namelist.input")
    if os.path.exists(nml):
        write_namelist(nml, os.path.join(a.out, "namelist.input"), a.size)
    else:
        print("  (no namelist.input in the run)")
    pdata = os.path.join(a.run, "cm1out_pdata.nc")
    if os.path.exists(pdata):
        dst = os.path.join(a.out, "cm1out_pdata.nc")
        nk, nup = parcels(pdata, dst, tuple(1000.0 * b for b in box), a.parcels, a.seed, note)
        mb = os.path.getsize(dst) / 1e6
        total += mb
        print(f"  parcels: {nk} kept ({nup} reach w > 10 m/s)  {mb:5.2f} MB")
    print(f"{len(kept)} times, {total:.1f} MB in {a.out}")


if __name__ == "__main__":
    main()
