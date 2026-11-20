#!/usr/bin/env python
"""Compare atmo3d's pressure decomposition (pdecomp_solver.py: p_nl as the residual)
with CM1's own method redone in numpy (packages/cm1/src/atmo3d_cm1/pdecomp/cm1_pdecomp.py: p_nl solved
directly from CM1's advection, plus a Coriolis part) on one CM1 output file.

    python tools/compare_pdecomp.py RUN/cm1out_000034.nc [--heights 1 3] [--out DIR]

Needs the staggered winds in the file (output_u/v/w = 1); the base state
(output_basestate = 1) is used when written, else the first output stands in.
Reads namelist.input next to the file for the lateral boundaries (wbc) and the
momentum advection (advwenov, weno_order, hadvordrv). A 1280 x 1280 x 115 grid needs
~60 GB of memory and several minutes: run it on a batch node, not a login node.

Writes to --out (default ./pdecomp_compare_<file>):
  stats.txt            the numbers below, for the whole interior and the plot box
  <cmp>_z<h>km.png     2 x 3 panels at each height: pressure (top) and vertical
                       acceleration (bottom); atmo3d | CM1 method | atmo3d - CM1
  <cmp>_xz.png         the same in a west-east section through the strongest updraft
  conversion_z<h>km.png   the older solver's acc_* as it returns them vs -cp thv0 dpi/dz
                          of the same parts (identical since the 2026-11-18 fix; kept to
                          check files written before it with --ours file)
  advection_z<h>km.png    (--check-advection) the port's advection vs CM1's budgets

Comparisons (<cmp>):
  buoyancy      p_b vs p_b
  linear        p_l vs p_l                    (atmo3d uses twice CM1's forcing)
  nonlinear     p_nl (residual) vs p_nl (direct)
  linear2       p_l vs 2 x CM1 p_l            (same split as atmo3d)
  nonlinear2    p_nl vs CM1 p_nl - p_l + p_c  (same split; CM1's p_nl holds the
                                               second copy of the linear term)
  dynamic       p_l + p_nl vs CM1 p_l + p_nl + p_c
  total         model p' vs CM1 p_b + p_l + p_nl + p_c (atmo3d's sum is p' exactly,
                by construction; this shows what CM1's four parts leave out)
Pressures have their volume mean removed before comparing (each method fixes the
constant differently). Accelerations on both sides are -cp thv0 d(pi)/dz (+ B for the
buoyancy part), which does not depend on that constant.

Part of atmo3d, GPL-3.0-or-later.
"""

import argparse
import os
import sys
import time

import numpy as np
import netCDF4 as nc

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from atmo3d_cm1.pdecomp import cm1_pdecomp as M          # noqa: E402
from atmo3d_cm1.pdecomp import pdecomp_solver as S      # noqa: E402

PARTS = ('b', 'l', 'nl')


def log(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


# ----------------------------------------------------------------------------
# inputs
# ----------------------------------------------------------------------------
def data_check(path):
    ds = nc.Dataset(path)
    try:
        missing, cond, hard = M.check_inputs(ds)
        have = set(ds.variables)
        print("\nData check for", path)
        for need, miss in missing.items():
            print(f"  {need:34s} {'ok' if not miss else 'MISSING ' + ', '.join(miss)}")
        print(f"  {'condensate (buoyancy)':34s} {', '.join(cond) or 'none'}")
        bud = [f"{c}b_{t}" for c in 'uvw' for t in ('hadv', 'vadv', 'hidiff', 'vidiff')]
        nb = [b for b in bud if b not in have]
        print(f"  {'u/v/w budgets (advection check)':34s} "
              f"{'ok' if not nb else 'missing ' + ', '.join(nb)}")
        ours = [n for n in ('p_b', 'p_l', 'p_nl', 'acc_b', 'acc_l', 'acc_nl') if n in have]
        ver = getattr(ds['p_b'], 'pdecomp_version', 'no version attribute (older script)') \
            if 'p_b' in have else ''
        print(f"  {'atmo3d parts already in the file':34s} "
              f"{', '.join(ours) or 'none'}{'  [' + ver + ']' if ver else ''}")
        print(f"  {'CM1 parts in the file (pdcomp)':34s} "
              f"{', '.join(n for n in ('pipb', 'pipdl', 'pipdn', 'pipc') if n in have) or 'none'}")
        print()
        return not hard, missing
    finally:
        ds.close()


def namelist_settings(nl_path):
    sch, vals = M.scheme_from_namelist(nl_path)
    if not vals:
        sys.exit(f"cannot read {nl_path} (give --namelist)")
    wbc = int(float(vals.get('wbc', 1)))
    periodic = wbc == 1
    return periodic, sch, vals


# ----------------------------------------------------------------------------
# atmo3d's method
# ----------------------------------------------------------------------------
def ours(path, first, periodic, from_file, G, Bcm1):
    """atmo3d's p_b, p_l, p_nl and acc_* (as the viewer shows them), their Exner parts
    (inverting atmo3d's own conversion) and the constant-free accelerations."""
    d1 = nc.Dataset(first)
    base = S.compute_base_state(d1)
    d1.close()
    out = {}
    if from_file:
        ds = nc.Dataset(path)
        for n in ('p_b', 'p_l', 'p_nl', 'acc_b', 'acc_l', 'acc_nl'):
            out[n] = np.asarray(ds[n][0], np.float32)
        out['B'] = S.compute_buoyancy(ds, base).astype(np.float32)
        ds.close()
    else:
        ds = nc.Dataset(path)
        dom = S.domain_info(ds)
        out['B'] = S.compute_buoyancy(ds, base).astype(np.float32)
        ds.close()
        solver = S.setup_pressure_solver(dom, base, periodic)
        res = S.pressure_decomposition(path, dom, base, solver, write=False)
        for n, a in res.items():
            out[n] = a.astype(np.float32)
        del res
    # Exner parts: invert p_x = p00 (pi0 + pi_x)^(cp/Rd) - p00 pi0^(cp/Rd)
    pi0 = base['pi0_large']
    p_t0 = S.pbb * pi0 ** (S.cp / S.Rd)
    for k in PARTS:
        pik = ((p_t0 + out['p_' + k]) / S.pbb) ** (S.Rd / S.cp) - pi0
        acc = M.pgrad_scalar(pik, G, Bcm1)
        if k == 'b':
            acc += out['B']
        out['accpi_' + k] = acc.astype(np.float32)
    return out


# ----------------------------------------------------------------------------
# statistics and plots
# ----------------------------------------------------------------------------
class Acc:
    """running sums for x (atmo3d) and y (CM1 method) over chosen points"""

    def __init__(self):
        self.n = 0
        self.s = np.zeros(5)   # x, y, xx, yy, xy
        self.dd = 0.0
        self.dmax = 0.0

    def add(self, x, y):
        x = x.astype(np.float64).ravel()
        y = y.astype(np.float64).ravel()
        d = x - y
        self.n += x.size
        self.s += [x.sum(), y.sum(), (x * x).sum(), (y * y).sum(), (x * y).sum()]
        self.dd += (d * d).sum()
        self.dmax = max(self.dmax, float(np.abs(d).max()) if d.size else 0.0)

    def result(self):
        n = max(self.n, 1)
        sx, sy, sxx, syy, sxy = self.s / n
        vx, vy = sxx - sx * sx, syy - sy * sy
        corr = (sxy - sx * sy) / np.sqrt(max(vx * vy, 1e-300))
        return {'rms_atmo3d': np.sqrt(sxx), 'rms_cm1': np.sqrt(syy),
                'rms_diff': np.sqrt(self.dd / n), 'corr': corr,
                'slope': sxy / max(sxx, 1e-300),   # least squares cm1 = slope * atmo3d
                'max_diff': self.dmax}


def stats(x, y, margin, box, k_lo=1, k_hi=None):
    """(interior, box) statistics, level by level (skipping the bottom and top level)"""
    nk = x.shape[0]
    k_hi = k_hi or nk - 1
    a_int, a_box = Acc(), Acc()
    m = margin
    (j0, j1), (i0, i1) = box
    for k in range(k_lo, k_hi):
        a_int.add(x[k, m:-m, m:-m], y[k, m:-m, m:-m])
        a_box.add(x[k, j0:j1, i0:i1], y[k, j0:j1, i0:i1])
    return a_int.result(), a_box.result()


def fmt_stats(name, kind, units, r):
    rel = f"{100 * r['rms_diff'] / r['rms_atmo3d']:5.1f}%" if r['rms_atmo3d'] > 0 else '  n/a'
    return (f"  {name:12s} {kind:5s} rms atmo3d {r['rms_atmo3d']:10.4g} {units:5s} "
            f"CM1 {r['rms_cm1']:10.4g}  diff {r['rms_diff']:10.4g} ({rel})  "
            f"corr {r['corr']:6.3f}  slope {r['slope']:6.3f}  max|diff| {r['max_diff']:.4g}")


def plot_panels(fname, title, X, Y, rows, wslice=None, xlabel='x (km)', ylabel='y (km)',
                aspect='equal'):
    """rows: [(row label, units, atmo3d 2D, cm1 2D)] -> 3 columns with the difference"""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axs = plt.subplots(len(rows), 3, figsize=(15, 4.6 * len(rows)), squeeze=False,
                            constrained_layout=True)
    for r, (lab, units, a, b) in enumerate(rows):
        lim = float(np.nanpercentile(np.abs(np.r_[a.ravel(), b.ravel()]), 99.5)) or 1.0
        d = a - b
        for c, (fld, ttl) in enumerate(((a, f'atmo3d {lab}'), (b, f'CM1 method {lab}'),
                                        (d, 'atmo3d - CM1'))):
            ax = axs[r, c]
            pm = ax.pcolormesh(X, Y, fld, cmap='RdBu_r', vmin=-lim, vmax=lim,
                               shading='auto', rasterized=True)
            if wslice is not None:
                ax.contour(X, Y, wslice, levels=[5, 15, 30], colors='k', linewidths=0.6)
            extra = ''
            if c == 2:
                rms = np.sqrt(np.mean(d.astype(float) ** 2))
                ra = np.sqrt(np.mean(a.astype(float) ** 2))
                extra = f'\nrms {rms:.3g}' + (f' ({100 * rms / ra:.0f}% of atmo3d)' if ra > 0 else '')
            ax.set_title(ttl + extra, fontsize=10)
            ax.set_xlabel(xlabel)
            ax.set_ylabel(ylabel)
            ax.set_aspect(aspect)
            fig.colorbar(pm, ax=ax, shrink=0.85, label=units)
    fig.suptitle(title + ('   (black: w = 5, 15, 30 m/s)' if wslice is not None else ''))
    fig.savefig(fname, dpi=110)
    plt.close(fig)


# ----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('file', help='CM1 output file (one time)')
    ap.add_argument('--first', help='first output (base state for atmo3d\'s method; '
                    'default: cm1out_000001.nc next to the file)')
    ap.add_argument('--namelist', help='default: namelist.input next to the file')
    ap.add_argument('--heights', type=float, nargs='+', default=[1.0, 3.0],
                    help='heights (km) for the horizontal plots (default 1 3)')
    ap.add_argument('--box', type=float, nargs=4, metavar=('X0', 'X1', 'Y0', 'Y1'),
                    help='plot box (km); default: --halfwidth around the strongest '
                    'updraft at 3 km')
    ap.add_argument('--halfwidth', type=float, default=15.0, help='km (default 15)')
    ap.add_argument('--ours', choices=('recompute', 'file'), default='recompute',
                    help="atmo3d's parts: recompute with today's pdecomp_solver.py "
                    "(default) or read p_b ... from the file")
    ap.add_argument('--scheme', choices=('weno5', 'flx5'),
                    help="CM1's momentum advection (default: from the namelist)")
    ap.add_argument('--margin', type=int, default=10,
                    help='points left out next to the lateral boundaries in the '
                    'interior statistics (default 10)')
    ap.add_argument('--check-advection', action='store_true',
                    help="also compare the port's advection with CM1's u/v/w budgets "
                    "(hadv + vadv + hidiff + vidiff), when the file has them")
    ap.add_argument('--out', help='output folder (default ./pdecomp_compare_<file>)')
    a = ap.parse_args()

    path = os.path.abspath(a.file)
    run = os.path.dirname(path)
    first = a.first or os.path.join(run, 'cm1out_000001.nc')
    nl = a.namelist or os.path.join(run, 'namelist.input')
    out = a.out or os.path.join(os.getcwd(), 'pdecomp_compare_' +
                                os.path.splitext(os.path.basename(path))[0])
    os.makedirs(out, exist_ok=True)

    ok, missing = data_check(path)
    if not ok:
        sys.exit("The file lacks what CM1's method needs (see above).")
    periodic, sch, vals = namelist_settings(nl)
    scheme = a.scheme or sch
    if scheme is None:
        sys.exit("The run's momentum advection is not WENO5 or 5th order "
                 f"(advwenov={vals.get('advwenov')}, weno_order={vals.get('weno_order')}, "
                 f"hadvordrv={vals.get('hadvordrv')}): give --scheme to approximate it.")
    for key, why in (('terrain_flag', 'terrain'), ('axisymm', 'axisymmetric')):
        v = vals.get(key, '0').strip('.').lower()
        if v in ('true', 't', '1'):
            sys.exit(f"This run uses {why}: neither method supports it.")
    log(f"lateral boundaries {'periodic' if periodic else 'open'}; advection {scheme}; "
        f"{S.THREADS} threads")

    ds = nc.Dataset(path)
    G = M.grid(ds)
    Bcm1 = M.base_state(ds, G, full=False)
    xh = np.asarray(ds['xh'][:], float)
    yh = np.asarray(ds['yh'][:], float)
    wname = 'winterp' if 'winterp' in ds.variables else None
    ds.close()
    if not Bcm1['from_file'] and not os.path.exists(first):
        sys.exit(f"no base state in the file and no first output at {first} (give --first)")

    # ---- atmo3d's method
    log(f"atmo3d's method ({'read from the file' if a.ours == 'file' else 'recomputed'})...")
    O = ours(path, first, periodic, a.ours == 'file', G, Bcm1)

    # ---- CM1's method
    log("CM1's method...")
    t_cm1 = time.time()
    C = M.decompose(path, periodic, t0_path=None if Bcm1['from_file'] else first,
                    scheme=scheme, log=log)
    log(f"  done in {time.time() - t_cm1:.0f} s")
    has_c = 'p_c' in C

    # volume means out of the pressures
    for D, names in ((O, ('p_b', 'p_l', 'p_nl')),
                     (C, ('p_b', 'p_l', 'p_nl', 'p_c', 'pprime'))):
        for n in names:
            if n in D:
                D[n] -= np.float32(np.mean(D[n], dtype=np.float64))

    # plot box and levels
    ds = nc.Dataset(path)
    k3 = int(np.argmin(np.abs(G['zh'] - 3000.0)))
    w3 = np.asarray(ds[wname][0, k3], float) if wname else \
        0.5 * np.asarray(ds['w'][0, k3] + ds['w'][0, k3 + 1], float)
    if a.box:
        x0, x1, y0, y1 = a.box
    else:
        jm, im = np.unravel_index(np.argmax(w3), w3.shape)
        x0, x1 = xh[im] - a.halfwidth, xh[im] + a.halfwidth
        y0, y1 = yh[jm] - a.halfwidth, yh[jm] + a.halfwidth
    i0, i1 = np.searchsorted(xh, x0), np.searchsorted(xh, x1)
    j0, j1 = np.searchsorted(yh, y0), np.searchsorted(yh, y1)
    jm_box = j0 + int(np.argmax(w3[j0:j1, i0:i1].max(axis=1)))
    levels = [int(np.argmin(np.abs(G['zh'] - 1000.0 * h))) for h in a.heights]
    wl = {k: (np.asarray(ds[wname][0, k], float) if wname else
              0.5 * np.asarray(ds['w'][0, k] + ds['w'][0, k + 1], float)) for k in levels}
    wxz = np.asarray(ds[wname][0, :, jm_box, :], float) if wname else None
    ds.close()
    log(f"plot box x {xh[i0]:.1f}..{xh[i1 - 1]:.1f} km, y {yh[j0]:.1f}..{yh[j1 - 1]:.1f} km; "
        f"section at y = {yh[jm_box]:.1f} km; levels "
        + ", ".join(f"{G['zh'][k] / 1000:.2f} km" for k in levels))

    # ---- comparisons: name -> (atmo3d pressure, CM1 pressure, atmo3d acc, CM1 acc)
    c_or0 = lambda D, n: D[n] if n in D else 0.0
    comps = {
        'buoyancy': (lambda: O['p_b'], lambda: C['p_b'],
                     lambda: O['accpi_b'], lambda: C['acc_b']),
        'linear': (lambda: O['p_l'], lambda: C['p_l'],
                   lambda: O['accpi_l'], lambda: C['acc_l']),
        'nonlinear': (lambda: O['p_nl'], lambda: C['p_nl'],
                      lambda: O['accpi_nl'], lambda: C['acc_nl']),
        'linear2': (lambda: O['p_l'], lambda: 2.0 * C['p_l'],
                    lambda: O['accpi_l'], lambda: 2.0 * C['acc_l']),
        'nonlinear2': (lambda: O['p_nl'], lambda: C['p_nl'] - C['p_l'] + c_or0(C, 'p_c'),
                       lambda: O['accpi_nl'],
                       lambda: C['acc_nl'] - C['acc_l'] + c_or0(C, 'acc_c')),
        'dynamic': (lambda: O['p_l'] + O['p_nl'],
                    lambda: C['p_l'] + C['p_nl'] + c_or0(C, 'p_c'),
                    lambda: O['accpi_l'] + O['accpi_nl'],
                    lambda: C['acc_l'] + C['acc_nl'] + c_or0(C, 'acc_c')),
        'total': (lambda: C['pprime'],
                  lambda: C['p_b'] + C['p_l'] + C['p_nl'] + c_or0(C, 'p_c'),
                  lambda: total_acc_model(path, G, Bcm1, C['B']),
                  lambda: C['acc_b'] + C['acc_l'] + C['acc_nl'] + c_or0(C, 'acc_c')),
    }

    lines = [f"atmo3d vs CM1's method: {path}",
             f"lateral boundaries {'periodic' if periodic else 'open'}; advection {scheme}; "
             f"f = {C['info']['f']:.3g}; base state from "
             f"{'the file' if C['info']['base_from_file'] else 'the first output'}; "
             f"condensate {', '.join(C['info']['condensate'])}",
             f"interior: all but {a.margin} points next to the lateral boundaries; box: "
             f"x {xh[i0]:.1f}..{xh[i1 - 1]:.1f}, y {yh[j0]:.1f}..{yh[j1 - 1]:.1f} km; "
             "levels 2..nk-1",
             "slope: least-squares CM1 = slope x atmo3d. 'total': atmo3d column = model p'.",
             ""]
    X, Y = xh[i0:i1], yh[j0:j1]
    for name, (fo, fc, fao, fac) in comps.items():
        po, pc = fo(), fc()
        so_i, so_b = stats(po, pc, a.margin, ((j0, j1), (i0, i1)))
        ao, ac = fao(), fac()
        sa_i, sa_b = stats(ao, ac, a.margin, ((j0, j1), (i0, i1)))
        lines += [f"{name}:",
                  fmt_stats('p', 'int', 'Pa', so_i), fmt_stats('p', 'box', 'Pa', so_b),
                  fmt_stats('acc', 'int', 'm/s2', sa_i), fmt_stats('acc', 'box', 'm/s2', sa_b),
                  ""]
        log(f"{name}: p corr {so_i['corr']:.3f} slope {so_i['slope']:.3f}; "
            f"acc corr {sa_i['corr']:.3f} slope {sa_i['slope']:.3f}")
        for k in levels:
            plot_panels(os.path.join(out, f"{name}_z{G['zh'][k] / 1000:.1f}km.png"),
                        f"{name}, z = {G['zh'][k] / 1000:.2f} km", X, Y,
                        [("p'", 'Pa', po[k, j0:j1, i0:i1], pc[k, j0:j1, i0:i1]),
                         ('vertical accel.', 'm/s²', ao[k, j0:j1, i0:i1],
                          ac[k, j0:j1, i0:i1])],
                        wslice=wl[k][j0:j1, i0:i1])
        Z = G['zh'] / 1000.0
        plot_panels(os.path.join(out, f"{name}_xz.png"),
                    f"{name}, section at y = {yh[jm_box]:.1f} km", X, Z,
                    [("p'", 'Pa', po[:, jm_box, i0:i1], pc[:, jm_box, i0:i1]),
                     ('vertical accel.', 'm/s²', ao[:, jm_box, i0:i1], ac[:, jm_box, i0:i1])],
                    wslice=None if wxz is None else wxz[:, i0:i1], ylabel='z (km)',
                    aspect='auto')
        del po, pc, ao, ac

    # ---- atmo3d's acc_* as written today vs the constant-free form
    lines += ["atmo3d acc_* as written (-(1/rho) dp/dz from p in Pa) vs -cp thv0 dpi/dz "
              "of the same parts (atmo3d column = as written):"]
    for k3_ in PARTS:
        s_i, s_b = stats(O['acc_' + k3_], O['accpi_' + k3_], a.margin, ((j0, j1), (i0, i1)))
        lines += [fmt_stats('acc_' + k3_, 'int', 'm/s2', s_i),
                  fmt_stats('acc_' + k3_, 'box', 'm/s2', s_b)]
    lines.append("")
    for k in levels:
        plot_panels(os.path.join(out, f"conversion_z{G['zh'][k] / 1000:.1f}km.png"),
                    f"atmo3d accelerations: as written (left) vs -cp thv0 dpi/dz (middle), "
                    f"z = {G['zh'][k] / 1000:.2f} km", X, Y,
                    [(f'acc_{p}', 'm/s²', O['acc_' + p][k, j0:j1, i0:i1],
                      O['accpi_' + p][k, j0:j1, i0:i1]) for p in PARTS],
                    wslice=wl[k][j0:j1, i0:i1])

    # ---- the port's advection vs CM1's own budgets
    if a.check_advection:
        lines += advection_check(path, G, Bcm1, periodic, scheme, levels, out, X, Y,
                                 (j0, j1, i0, i1), wl, a.margin)

    with open(os.path.join(out, 'stats.txt'), 'w') as fh:
        fh.write('\n'.join(lines) + '\n')
    print('\n'.join(lines))
    log(f"figures and stats.txt in {out}")


def total_acc_model(path, G, B, Bz):
    """B + (-cp thv0 d(pi')/dz) of the model's own pi' (the 'total' comparison's
    atmo3d column: what the four parts should add up to)."""
    ds = nc.Dataset(path)
    pi = M.exner(ds).astype(np.float64) - B['pi0'][:, None, None]
    ds.close()
    return (Bz + M.pgrad_scalar(pi, G, B)).astype(np.float32)


def advection_check(path, G, B, periodic, scheme, levels, out, X, Y, box, wl, margin):
    ds = nc.Dataset(path)
    names = {c: [f"{c}b_{t}" for t in ('hadv', 'vadv', 'hidiff', 'vidiff')] for c in 'uvw'}
    if any(n not in ds.variables for v in names.values() for n in v):
        ds.close()
        return ["advection check: the file lacks the u/v/w budgets", ""]
    log("advection check: the port's -(u.grad)u with the full winds...")
    U = {'u': M._var(ds, 'u'), 'v': M._var(ds, 'v'), 'w': M._var(ds, 'w')}
    ds.close()
    ten = dict(zip('uvw', M.advection(U, G, B, periodic, perturbation=False, scheme=scheme)))
    del U
    j0, j1, i0, i1 = box
    lines = ["advection: the port (full winds, as the model) vs CM1's budgets "
             "hadv + vadv + hidiff + vidiff (budgets: last Runge-Kutta stage of the step "
             "before output, so close but not identical); atmo3d column = budgets:"]
    ds = nc.Dataset(path)
    kept = []
    for c in 'uvw':
        bud = sum(np.asarray(ds[n][0], np.float32) for n in names[c])
        mine = ten[c].astype(np.float32)
        sl = (slice(None), slice(None), slice(0, -1)) if c == 'u' else \
            (slice(None), slice(0, -1), slice(None)) if c == 'v' else \
            (slice(0, -1), slice(None), slice(None))
        s_i, s_b = stats(bud[sl], mine[sl], margin, ((j0, j1), (i0, i1)))
        lines += [fmt_stats(c + ' adv', 'int', 'm/s2', s_i), fmt_stats(c + ' adv', 'box', 'm/s2', s_b)]
        if c == 'w':
            for k in levels:
                plot_panels(os.path.join(out, f"advection_z{G['zh'][k] / 1000:.1f}km.png"),
                            f"advective tendency: CM1 budgets (left) vs the port (middle), "
                            f"level {k + 1} (u, v: z = {G['zh'][k] / 1000:.2f} km; "
                            f"w: z = {G['zf'][k] / 1000:.2f} km)", X, Y,
                            [(f'{q} adv', 'm/s²', bq[k, j0:j1, i0:i1], mq[k, j0:j1, i0:i1])
                             for q, bq, mq in kept + [('w', bud, mine)]],
                            wslice=wl[k][j0:j1, i0:i1])
        else:
            kept.append((c, bud[sl], mine[sl]))
    ds.close()
    lines.append("")
    return lines


if __name__ == '__main__':
    main()
