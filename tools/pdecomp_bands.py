"""Where do the horizontal bands in the decomposition's accelerations above ~12 km come
from?  (Phase 2b step 2, docs-dev/derived-fields.md §5.3.)

Runs CM1's decomposition (atmo3d.pdecomp.cm1_pdecomp) on one output file, then writes,
for every model level:

- the grid: zh, dz, and how fast dz changes (dz_k / dz_k-1), so a kink in the stretching
  shows;
- the base state: thv0 and d(thv0)/dz (a tropopause jump shows);
- rms over the interior of B, pgrad_b (scalar levels), acc_b, acc_l, acc_nl, acc_c, and
  of pgrad_b at the w levels before averaging;
- acc_b_w: the candidate fix. B interpolated to the w levels (c1, c2, as the solver's
  source term) plus pgrad_b there, then both averaged to the scalar levels together;
- for each acceleration, a "banding" ratio: rms of its second difference across levels
  over rms of the field. Near 0 for smooth profiles, near 2 or more for level-to-level
  alternation.

and plots (bands.png): those profiles against height, and west–east sections of acc_b,
pgrad_b (w levels) and B through the strongest updraft at 3 km.

    python tools/pdecomp_bands.py RUN/cm1out_000034.nc --out DIR [--threads 4]

Memory: like the decomposition (~35 GB for 1280 x 1280 x 115). Run on a batch node.
"""

import argparse
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from atmo3d.pdecomp import cm1_pdecomp as P  # noqa: E402

EDGE = 10  # points left out next to the lateral boundaries (as compare_pdecomp.py)


def rms(a):
    return np.sqrt(np.mean(np.square(a, dtype=np.float64), axis=(1, 2)))


def banding(a):
    """rms of the second difference across levels / rms of the field, per level."""
    d2 = np.zeros(a.shape[0])
    d2[1:-1] = rms(a[2:] - 2.0 * a[1:-1] + a[:-2])
    return d2 / np.maximum(rms(a), 1e-30)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("file")
    ap.add_argument("--out", required=True)
    ap.add_argument("--threads", type=int, default=None)
    ap.add_argument("--namelist", default=None)
    a = ap.parse_args()
    os.makedirs(a.out, mode=0o755, exist_ok=True)

    out = P.run_decomposition(a.file, namelist=a.namelist, threads=a.threads)
    import netCDF4 as nc
    with nc.Dataset(a.file) as ds:
        G = P.grid(ds)
        B = P.base_state(ds, G, None, full=False)
        w = np.asarray(ds["winterp"][0] if "winterp" in ds.variables
                       else ds["w"][0, 1:], np.float32)
    s = (slice(None), slice(EDGE, -EDGE), slice(EDGE, -EDGE))
    pgw = P.pgrad_w(out["pi_b"].astype(np.float64), G, B)  # (nk + 1) w levels
    pg_b = out["acc_b"] - out["B"]
    accw = P.buoyancy_tendency(out["B"].astype(np.float64), G) + pgw
    acc_bw = (0.5 * (accw[:-1] + accw[1:])).astype(np.float32)

    zh, zf = G["zh"], G["zf"]
    dz = np.diff(zf)
    ratio = np.r_[np.nan, dz[1:] / dz[:-1]]
    thv0 = B["thv0"]
    dthv = np.gradient(thv0, zh)
    acc = {k: out[k][s] for k in ("acc_b", "acc_l", "acc_nl", "acc_c")}
    acc["acc_b_w"] = acc_bw[s]
    cols = {"B": rms(out["B"][s]), "pgrad_b": rms(pg_b[s]),
            **{k: rms(v) for k, v in acc.items()}}
    bands = {k: banding(v) for k, v in acc.items()}
    bands["B"] = banding(out["B"][s])
    bands["pgrad_b"] = banding(pg_b[s])
    pgw_rms = rms(pgw[1:-1][s])  # interior w levels 1..nk-1

    with open(os.path.join(a.out, "bands.txt"), "w") as fh:
        fh.write(f"file {a.file}\ninfo {out['info']}\n\n")
        names = list(cols)
        fh.write("  k   zh_km  dz_m  dz/dz-  thv0  dthv0/dz_K/km | rms: "
                 + " ".join(f"{n:>9}" for n in names) + " pgw_below | banding: "
                 + " ".join(f"{n:>7}" for n in bands) + "\n")
        for k in range(G["nk"]):
            pw = pgw_rms[k - 1] if 1 <= k <= G["nk"] - 1 else np.nan
            fh.write(f"{k:3d} {zh[k] / 1e3:7.3f} {dz[k]:5.0f} {ratio[k]:7.3f} "
                     f"{thv0[k]:6.1f} {1e3 * dthv[k]:8.2f}      | "
                     + " ".join(f"{cols[n][k]:9.2e}" for n in names)
                     + f" {pw:9.2e} | " + " ".join(f"{bands[n][k]:7.2f}" for n in bands)
                     + "\n")
    print("wrote", os.path.join(a.out, "bands.txt"))

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    k3 = int(np.argmin(np.abs(zh - 3000.0)))
    j, i = np.unravel_index(np.argmax(w[k3][s[1:]]), w[k3][s[1:]].shape)
    j += EDGE
    zk = zh / 1e3
    fig, ax = plt.subplots(2, 4, figsize=(20, 10), constrained_layout=True)
    ax[0, 0].plot(dz, zk, ".-"); ax[0, 0].set_title("dz (m)")
    ax[0, 1].plot(ratio, zk, ".-"); ax[0, 1].set_title("dz_k / dz_k-1")
    ax[0, 2].plot(1e3 * dthv, zk, ".-"); ax[0, 2].set_title("d(thv0)/dz (K/km)")
    for n, v in cols.items():
        ax[0, 3].semilogx(v, zk, ".-", label=n)
    ax[0, 3].semilogx(pgw_rms, zf[1:-1] / 1e3, "k:", label="pgrad_b (w levels)")
    ax[0, 3].legend(); ax[0, 3].set_title("rms (m/s²)")
    for n, v in bands.items():
        ax[1, 0].plot(v, zk, ".-", label=n)
    ax[1, 0].legend(); ax[1, 0].set_title("banding ratio")
    x = np.arange(G["ni"]) * G["dx"] / 1e3
    for axx, (lab, fld, zz) in zip(ax[1, 1:], (("acc_b", out["acc_b"][:, j], zk),
                                             ("acc_b_w (B at w levels)", acc_bw[:, j], zk),
                                             ("B", out["B"][:, j], zk))):
        lim = np.nanpercentile(np.abs(fld), 99.5) or 1.0
        m = axx.pcolormesh(x, zz, fld, cmap="RdBu_r", vmin=-lim, vmax=lim, shading="auto")
        axx.set_title(f"{lab}, y index {j}"); fig.colorbar(m, ax=axx)
    for axx in ax.flat:
        axx.set_ylabel("z (km)")
    fig.savefig(os.path.join(a.out, "bands.png"), dpi=110)
    print("wrote", os.path.join(a.out, "bands.png"))


if __name__ == "__main__":
    main()
