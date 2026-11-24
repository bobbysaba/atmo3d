"""Build atmo3d's WoFS demo from a WoFS run:  python tools/make_wofs_demo.py ROOT OUT

Run once by a maintainer when the demo changes; atmo3d itself only reads the result.
ROOT is a WoFS experiment folder (date folders YYYYMMDD of cycle folders YYYYMMDDHHMM,
each with wrfout_d01_<time>_<member>; atmo3d_wofs.run).  OUT receives a smaller copy in
the same layout (the same date and cycle folders, the same file names), which atmo3d
opens as it opens the original.  The domain is kept whole (a WoFS domain holds several
storms, so there is no one box to cut); the size comes down by:

  members   --members of them (default 1,2,3), so the member switch and the ensemble
            mean still have something to show
  times     the cycles from --start for --hours, every --every minutes
  fields    KEEP only: the 3D fields atmo3d reads (winds, T, P, PB, PH, PHB, moisture
            and hydrometeor mixing ratios, reflectivity, REL_VORT) and the 2D storm and
            surface fields that hold data in a cycled run's files (the hourly maxima,
            the UP_HELI_MAX family, are all zero there: each file starts a forecast),
            with terrain, lat/lon and the Times strings.  Every file keeps the same
            set (atmo3d lists the first file's fields)
  packing   each float field as 16-bit integers (scale_factor, add_offset, both
            float32, as CF packing: every netCDF reader unpacks them), with zlib and
            shuffle, one horizontal level per chunk, at the step in PRECISION (coarsened
            by powers of two only where a field's range in a file needs more than 16
            bits; make_real_demo.pack).  HGT, XLAT, XLONG and F stay float32

The global attributes (grid, map projection, times) are copied, with an atmo3d_demo note
saying how the copy was made.  Each file is written beside its name and renamed when
complete, so an interrupted build leaves no half files; files already in OUT are skipped
(--force rewrites them).

Example (the WoFS demo):

    python tools/make_wofs_demo.py /glade/derecho/scratch/$USER/test/bnrhf_ctrl \\
        /glade/derecho/scratch/$USER/wofs_demo/bnrhf_ctrl
"""

import argparse
import datetime
import os
import re
import sys

import netCDF4
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_real_demo import pack  # noqa: E402  (the CM1 demo's 16-bit packing)

FILE_RE = re.compile(r"^wrfout_d01_(\d{4}-\d\d-\d\d_\d\d:\d\d:\d\d)_(\d+)$")
CYCLE_RE = re.compile(r"^\d{12}$")
DATE_RE = re.compile(r"^\d{8}$")

Q = 1e-6  # mixing ratios, kg/kg (0.001 g/kg)
# field -> step kept, in its units; None: kept as it is (float32)
KEEP = {
    # 3D: what atmo3d reads (THETA = T + 300, PRES = P + PB, heights from PH + PHB)
    "U": 0.05, "V": 0.05, "W": 0.05, "T": 0.05,
    "P": 1.0, "PB": 1.0, "PH": 1.0, "PHB": 1.0,  # Pa; m2/s2 (0.1 m of height)
    "QVAPOR": Q, "QCLOUD": Q, "QRAIN": Q, "QICE": Q, "QSNOW": Q, "QGRAUP": Q, "QHAIL": Q,
    "REFL_10CM": 0.5, "REL_VORT": 1e-5,
    # 2D storm diagnostics
    "UH": 0.1, "UH02": 0.1, "UH03": 0.1, "UH16": 0.1,
    "COMPOSITE_REFL_10CM": 0.5, "REFL_10CM_1KM": 0.5, "REFL_10CM_4KM": 0.5,
    "REFD_MAX": 0.5,
    "W_UP_MAX": 0.05, "W_DN_MAX": 0.05, "W_MEAN": 0.05,
    "U10": 0.05, "V10": 0.05, "WSPD10MAX": 0.05,
    "HAIL_MAX2D": 1e-5, "GRPL_MAX": 0.01,
    "LTG1_MAX": 0.01, "LTG2_MAX": 0.01, "LTG3_MAX": 0.01,
    # 2D near-surface and boundary layer
    "T2": 0.05, "TH2": 0.05, "Q2": Q, "PSFC": 1.0,
    "PBLH": 1.0, "HFX": 0.1, "LH": 0.1,
    # grid: as they are
    "HGT": None, "XLAT": None, "XLONG": None, "F": None, "Times": None,
}


def cycles(root):
    """[(cycle time, cycle folder)] of root, in time order (date folders, or cycle
    folders straight in root)."""
    out = []
    for n in sorted(os.listdir(root)):
        p = os.path.join(root, n)
        if DATE_RE.match(n) and os.path.isdir(p):
            out += [(datetime.datetime.strptime(c, "%Y%m%d%H%M"), os.path.join(p, c))
                    for c in sorted(os.listdir(p)) if CYCLE_RE.match(c)]
        elif CYCLE_RE.match(n) and os.path.isdir(p):
            out.append((datetime.datetime.strptime(n, "%Y%m%d%H%M"), p))
    return sorted(out)


def member_file(folder, member):
    for n in sorted(os.listdir(folder)):
        m = FILE_RE.match(n)
        if m and int(m.group(2)) == member:
            return os.path.join(folder, n)
    raise SystemExit(f"no wrfout_d01_*_{member} in {folder}")


def copy_file(src, dst, note):
    with netCDF4.Dataset(src) as s, netCDF4.Dataset(dst + ".part", "w") as d:
        s.set_auto_mask(False)
        missing = [n for n in KEEP if n not in s.variables]
        if missing:
            raise SystemExit(f"{src} has no {', '.join(missing)}")
        d.setncatts(dict({k: s.getncattr(k) for k in s.ncattrs()}, atmo3d_demo=note))
        used = {dim for n in KEEP for dim in s[n].dimensions}
        for n, dim in s.dimensions.items():
            if n in used:
                d.createDimension(n, None if dim.isunlimited() else len(dim))
        for n, step in KEEP.items():
            v = s[n]
            attrs = {k: v.getncattr(k) for k in v.ncattrs() if k != "_FillValue"}
            a = np.asarray(v[:])
            chunk = (1, 1) + a.shape[2:] if v.ndim == 4 else None
            if step is None or a.dtype.kind != "f":
                nv = d.createVariable(n, a.dtype, v.dimensions, zlib=True, complevel=6,
                                      shuffle=True, chunksizes=chunk)
                nv.setncatts(attrs)
                nv[:] = a
                continue
            codes, scale, offset = pack(a, step)
            nv = d.createVariable(n, "u2", v.dimensions, zlib=True, complevel=6,
                                  shuffle=True, chunksizes=chunk)
            nv.setncatts(attrs)
            nv.scale_factor, nv.add_offset = scale, offset
            nv.set_auto_scale(False)
            nv[:] = codes
    os.replace(dst + ".part", dst)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", help="the WoFS experiment folder")
    ap.add_argument("out", help="the demo's folder (created; its name is the run's name)")
    ap.add_argument("--members", default="1,2,3", help="members kept (default 1,2,3)")
    ap.add_argument("--start", default="202205240000",
                    help="first cycle kept, YYYYMMDDHHMM (default 202205240000)")
    ap.add_argument("--hours", type=float, default=2.0, help="hours kept (default 2)")
    ap.add_argument("--every", type=int, default=15,
                    help="minutes between the cycles kept (default 15)")
    ap.add_argument("--force", action="store_true", help="rewrite files already in OUT")
    a = ap.parse_args(argv)

    members = [int(m) for m in a.members.split(",")]
    start = datetime.datetime.strptime(a.start, "%Y%m%d%H%M")
    end = start + datetime.timedelta(hours=a.hours)
    root = os.path.abspath(a.root)
    keep = [(t, f) for t, f in cycles(root) if start <= t <= end
            and int((t - start).total_seconds()) % (60 * a.every) == 0]
    if not keep:
        raise SystemExit(f"no cycles in {root} from {a.start} for {a.hours} h")
    note = (f"atmo3d demo: {os.path.basename(root)}, members {a.members}, "
            f"{keep[0][0]:%Y-%m-%d %H:%M} to {keep[-1][0]:%H:%M} UTC every {a.every} "
            f"min; fields cut to atmo3d's and 16-bit packed (tools/make_wofs_demo.py)")
    total = 0
    for t, folder in keep:
        dst_dir = os.path.join(a.out, os.path.relpath(folder, root))
        os.makedirs(dst_dir, mode=0o755, exist_ok=True)
        for m in members:
            src = member_file(folder, m)
            dst = os.path.join(dst_dir, os.path.basename(src))
            if a.force or not os.path.exists(dst):
                copy_file(src, dst, note)
            size = os.path.getsize(dst)
            total += size
            print(f"{os.path.relpath(dst, a.out)}  {size / 1e6:.1f} MB", flush=True)
    print(f"{len(keep)} cycles x {len(members)} members: {total / 1e6:.0f} MB in {a.out}")


if __name__ == "__main__":
    main()
