"""Phase 4 spike measurements on the real radar files (run as a batch job).

Usage: python bench.py DATA_DIR OUT_DIR
  DATA_DIR  the folder of CfRadial files
  OUT_DIR   scratch folder for cached regrids and figures (figures are copied into
            docs-dev/radar-spike by hand if wanted)
Prints a plain-text report (times in s, memory in MB).
"""
import glob
import os
import sys
import time

import numpy as np
import netCDF4

import sampler as S

DATA, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)
FILES = sorted(glob.glob(os.path.join(DATA, "*.nc")), key=lambda p: int(os.path.basename(p).split("_")[4]))


def rss():
    """(current, peak) resident memory in MB."""
    cur = peak = 0
    with open("/proc/self/status") as f:
        for line in f:
            if line.startswith("VmRSS:"):
                cur = int(line.split()[1]) / 1024
            elif line.startswith("VmHWM:"):
                peak = int(line.split()[1]) / 1024
    return cur, peak


def reset_peak():
    try:
        with open("/proc/self/clear_refs", "w") as f:
            f.write("5")
    except OSError:
        pass


def timed(fn, *a, repeat=1, **kw):
    ts = []
    for _ in range(repeat):
        t0 = time.perf_counter()
        r = fn(*a, **kw)
        ts.append(time.perf_counter() - t0)
    return r, float(np.median(ts))


print(f"numba threads: {S.numba.get_num_threads()}  files: {len(FILES)}")

# ------------------------------------------------------------------ A. contents of all files
print("\n== A. field contents per file (valid rays only)")
print("file  rays  read_s/field  w!=0  w_direct!=0  u_valid  dd==2  dd_values  dbz_max")
for path in FILES:
    n = os.path.basename(path).split("_")[4]
    with netCDF4.Dataset(path) as nc:
        nray = int(nc["sweep_end_ray_index"][-1]) + 1
        res, tread = {}, []
        for k in ("w", "w_direct", "u", "doppler_degree", "reflectivity"):
            t0 = time.perf_counter()
            a = np.ma.filled(nc[k][:nray, :].astype(np.float32), np.nan)
            tread.append(time.perf_counter() - t0)
            res[k] = a
        w, wd, u, dd, z = (res[k] for k in ("w", "w_direct", "u", "doppler_degree", "reflectivity"))
        ddv = np.unique(dd[np.isfinite(dd)])
        print(f"{n:>4} {nray:6d} {np.mean(tread):8.2f} {int(np.count_nonzero(np.nan_to_num(w))):9d}"
              f" {int(np.count_nonzero(np.nan_to_num(wd))):9d} {int(np.isfinite(u).sum()):9d}"
              f" {int((dd == 2).sum()):8d}  {ddv.tolist()[:6]}  {np.nanmax(z):.1f}")
        if n == "0":
            fin = {k: (int(np.isfinite(v).sum()), int(np.count_nonzero(np.isfinite(v) & (v != 0)))) for k, v in res.items()}
            print("      file 0 (finite, finite & nonzero):", fin)
    del res

# ------------------------------------------------------------------ B. one volume
PATH = FILES[len(FILES) // 2]
print(f"\n== B. volume used below: {os.path.basename(PATH)}")
with netCDF4.Dataset(PATH) as nc:
    names = [k for k, v in nc.variables.items() if v.dimensions == ("time", "range")]
    nray = int(nc["sweep_end_ray_index"][-1]) + 1
    reset_peak()
    t0 = time.perf_counter()
    for k in names:
        np.ma.filled(nc[k][:nray, :].astype(np.float32), np.nan)
    tall = time.perf_counter() - t0
print(f"read all {len(names)} (time, range) fields of one file: {tall:.1f} s "
      f"({tall/len(names):.2f} s/field); peak RSS {rss()[1]:.0f} MB")

reset_peak()
vol, tvol = timed(S.Volume.from_cfradial, PATH, "reflectivity")
print(f"Volume.from_cfradial(reflectivity): {tvol:.2f} s, {vol.data.shape}, {vol.nbytes/1e6:.0f} MB in memory "
      f"(float32), peak RSS {rss()[1]:.0f} MB")
print(f"sweep elevations (median measured): {np.round(vol.elev, 2).tolist()}")
_, tsw = timed(S.Volume.from_cfradial, PATH, "reflectivity", sweeps=[0])
print(f"one sweep only: {tsw:.2f} s")

# compile once
S.sample(vol, np.zeros(10), np.zeros(10), np.ones(10))

# the storm: max of a 2 km CAPPI (smoothed by a 5 km box) within 200 km
xs, ys, c2 = S.cappi(vol, 2.0, half=200.0, d=1.0)
from scipy.ndimage import uniform_filter
cs = uniform_filter(np.nan_to_num(c2, nan=-30.0), 5)
j, i = np.unravel_index(np.argmax(cs), cs.shape)
xc, yc = float(xs[i]), float(ys[j])
print(f"storm centre (2 km CAPPI max): x {xc:.0f} km, y {yc:.0f} km, range {np.hypot(xc, yc):.0f} km")

print("\n-- sampler cost (median of 3; first call excluded)")
A, B = (xc - 75.0, yc), (xc + 75.0, yc)
for method in ("linear", "nearest"):
    (s, zq, sec), t = timed(S.cross_section, vol, A, B, ztop=18.0, dz=0.1, ds=0.25, method=method, repeat=3)
    print(f"cross-section 150 km x 18 km at 250 m x 100 m ({sec.size} pts, {method}): {t*1000:.0f} ms, "
          f"{np.isfinite(sec).mean():.2f} finite")
    if method == "linear":
        sec_lin = sec
    else:
        sec_near = sec
(zc, col), t = timed(S.column, vol, xc, yc, ztop=18.0, dz=0.05, repeat=3)
print(f"column 0-18 km at 50 m ({col.size} pts): {t*1000:.2f} ms")
(_, _, cp), t = timed(S.cappi, vol, 3.0, half=150.0, d=0.5, center=(xc, yc), repeat=3)
print(f"CAPPI 3 km, 300 x 300 km at 500 m ({cp.size} pts): {t*1000:.0f} ms")
(_, _, cpf), t = timed(S.cappi, vol, 3.0, half=460.0, d=0.5, repeat=3)
print(f"CAPPI 3 km, full 920 x 920 km at 500 m ({cpf.size} pts): {t*1000:.0f} ms")

print("\n-- regrid of one field (sampler at every grid point; 0-20 km)")
regrids = {}
for label, half, d, center in (("full 920 km, 1 km", 460.0, 1.0, (0, 0)),
                               ("full 920 km, 500 m", 460.0, 0.5, (0, 0)),
                               ("300 km box, 500 m", 150.0, 0.5, (xc, yc)),
                               ("300 km box, 250 m h / 250 m v", 150.0, 0.25, (xc, yc))):
    reset_peak()
    base = rss()[0]
    (gx, gy, gz, G), t = timed(S.regrid, vol, half=half, d=d, ztop=20.0, center=center)
    peak = rss()[1]
    f = os.path.join(OUT, f"regrid_{label.replace(' ', '_').replace(',', '').replace('/', '')}.npy")
    _, tsave = timed(np.save, f, G)
    _, tload = timed(np.load, f)
    print(f"{label}: grid {G.shape} = {G.size/1e6:.0f} M pts, {t:.1f} s, {G.nbytes/1e6:.0f} MB, "
          f"peak RSS +{peak - base:.0f} MB; save {tsave:.1f} s, load {tload:.1f} s")
    regrids[label] = (gx, gy, gz, G)
    if "250 m" in label:
        os.remove(f)
    del G

# ------------------------------------------------------------------ C. 3D
print("\n== C. 3D isosurfaces of 40 dBZ (whole volume)")
import pyvista as pv
from skimage.measure import marching_cubes
for mr, stride in ((None, 1), (None, 2)):
    reset_peak()
    g, t = timed(S.sweep_grid, vol, stride_gate=stride)
    gn = g.copy()
    a = gn.point_data["f"]
    gn.point_data["f"] = np.where(np.isfinite(a), a, -40.0)
    iso, tc = timed(gn.contour, [40.0], scalars="f")
    print(f"sweep grid (gate stride {stride}): {g.n_points/1e6:.1f} M pts, build {t:.1f} s; "
          f"contour {tc:.1f} s, {iso.n_cells} triangles; peak RSS {rss()[1]:.0f} MB")
    if stride == 1:
        iso_native = iso
for label in ("full 920 km, 1 km", "300 km box, 500 m"):
    gx, gy, gz, G = regrids[label]
    sub = np.where(np.isfinite(G), G, -40.0).astype(np.float32)
    (verts, faces, _, _), t = timed(marching_cubes, sub, level=40.0)
    print(f"regridded ({label}): marching_cubes {t:.1f} s, {len(faces)} triangles")

# gap between sweeps along the beam (geometry): vertical distance at ranges
print("\n-- vertical gap between neighbouring sweeps (km) vs beam depth (0.95 deg)")
rs = np.array([50.0, 100.0, 150.0, 200.0, 300.0])
print("pair            " + "  ".join(f"{r:5.0f}km" for r in rs))
for k in range(len(vol.elev) - 1):
    h0, _ = S.beam_height(rs, vol.elev[k])
    h1, _ = S.beam_height(rs, vol.elev[k + 1])
    print(f"{vol.elev[k]:5.2f}-{vol.elev[k+1]:5.2f}     " + "  ".join(f"{g:7.2f}" for g in h1 - h0))
print("beam depth      " + "  ".join(f"{r * np.radians(S.BEAMWIDTH):7.2f}" for r in rs))
for e in (vol.elev[0], vol.elev[-1]):
    h, _ = S.beam_height(rs, e)
    print(f"height of {e:5.2f} deg  " + "  ".join(f"{x:7.2f}" for x in h))

# ------------------------------------------------------------------ D. figures
print("\n== D. figures")
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(2, 2, figsize=(12, 9))
    k0 = 0
    az = np.radians(vol.az[k0]); r = vol.r0 + vol.dr * np.arange(vol.ng)
    _, s0 = S.beam_height(r, vol.elev[k0])
    X = s0[None, :] * np.sin(az)[:, None]; Y = s0[None, :] * np.cos(az)[:, None]
    m = ax[0, 0].pcolormesh(X, Y, vol.data[k0], vmin=-10, vmax=70, cmap="turbo", shading="auto")
    ax[0, 0].plot([A[0], B[0]], [A[1], B[1]], "k-", lw=2)
    ax[0, 0].set_xlim(xc - 100, xc + 100); ax[0, 0].set_ylim(yc - 100, yc + 100)
    ax[0, 0].set_title(f"native PPI {vol.elev[k0]:.2f} deg, reflectivity; section line"); fig.colorbar(m, ax=ax[0, 0])
    for a_, sec, ttl in ((ax[0, 1], sec_lin, "linear"), (ax[1, 0], sec_near, "nearest gate")):
        m = a_.pcolormesh(s + A[0], zq, sec, vmin=-10, vmax=70, cmap="turbo", shading="auto")
        a_.set_title(f"sampler cross-section ({ttl}), z above radar"); a_.set_xlabel("x (km)"); fig.colorbar(m, ax=a_)
        for e in vol.elev:  # where the sweeps cross the section
            rr = np.hypot(s + A[0], A[1])
            rg = np.linspace(0, 460, 400); hh, ss = S.beam_height(rg, e)
            a_.plot(s + A[0], np.interp(rr, ss, hh), "w-", lw=0.4)
        a_.set_ylim(0, 18)
    m = ax[1, 1].pcolormesh(np.arange(-150, 150.25, 0.5) + xc, np.arange(-150, 150.25, 0.5) + yc, cp,
                            vmin=-10, vmax=70, cmap="turbo", shading="auto")
    ax[1, 1].set_title("sampler CAPPI 3 km"); fig.colorbar(m, ax=ax[1, 1])
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "sampler_views.png"), dpi=80)
    print("wrote sampler_views.png")
except Exception as e:  # figures are a bonus
    print("figure failed:", e)
try:
    pv.OFF_SCREEN = True
    p = pv.Plotter(off_screen=True, window_size=(1200, 600), shape=(1, 2))
    box = (xc - 60, xc + 60, yc - 60, yc + 60, 0, 18)
    p.subplot(0, 0); p.add_mesh(iso_native.clip_box(box, invert=False), color="orange")
    p.add_text("native sweep grid, 40 dBZ", font_size=10); p.set_scale(zscale=3); p.view_xz()
    gx, gy, gz, G = regrids["300 km box, 500 m"]
    img = pv.ImageData(dimensions=(gx.size, gy.size, gz.size), spacing=(0.5, 0.5, 0.5), origin=(gx[0], gy[0], 0))
    img.point_data["f"] = np.where(np.isfinite(G), G, -40.0).transpose(2, 1, 0).ravel(order="F")
    p.subplot(0, 1); p.add_mesh(img.contour([40.0]).clip_box(box, invert=False), color="orange")
    p.add_text("regridded 500 m, 40 dBZ", font_size=10); p.set_scale(zscale=3); p.view_xz()
    p.screenshot(os.path.join(OUT, "iso_compare.png")); print("wrote iso_compare.png")
except Exception as e:
    print("3D figure failed:", e)
print("\ndone; final RSS", rss())
