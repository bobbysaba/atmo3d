"""cm1_pdecomp: CM1's own pressure decomposition (pdcomp.F + poiss.F, identical in
cm1r19.5 and cm1r21.1), redone in numpy from CM1 output files, for runs that could not
use CM1's (output_pdcomp does not work with MPI, terrain or a stretched horizontal
grid).

One self-contained file (numpy, scipy, netCDF4): atmo3d uses it for its pressure
decomposition, and the same file is the stand-alone version (with a driver script).

Four parts, each a solve of CM1's anelastic pressure equation for the Exner function,

    cp [ H d2(pi)/dx2 + H d2(pi)/dy2 + d/dz( Hf d(pi)/dz ) ] = div( rho0 * T ),
    H = rho0 thv0 (scalar levels),  Hf = rf0 * avg(thv0) (w levels),

where T is the part's own momentum tendency on CM1's staggered grid:

- buoyancy  (b):  T = (0, 0, B),  B = g [ th'/th0 + (Rv/Rd - 1)(qv - qv0) - q_condensate ]
                  interpolated to w levels;
- linear    (l):  T = ( -w dU0/dz, -w dV0/dz, 0 )       (one copy of the linear term);
- nonlinear (nl): T = -(u . grad) u'  (u full, u' = u - U0; CM1's own advection: WENO5 or
                  5th order, as the run, in advective form via flux form + u' div);
- Coriolis  (c):  T = ( f v, -f u, 0 )                    (zero when f = 0).

The nonlinear part holds the second copy of the linear term (div(rho0 U0.grad u') =
rho0 dU0/dz dw/dx by continuity), as in CM1.

Outputs (Pa and m/s^2, on scalar points): p_b, p_l, p_nl, p_c and the vertical
accelerations acc_b, acc_l, acc_nl, acc_c, where pgrad_x = -cp thv0 d(pi_x)/dz as CM1
writes it (pgradb, pgraddl, pgraddn, pgradc), averaged from the w levels.  acc_b is
B + pgrad_b summed at the w levels (B there as the solver's source, c1/c2) and then
averaged: adding the scalar-level B to the averaged pgrad_b instead leaves B's
level-to-level structure as horizontal bands where the two nearly cancel (the
stratosphere; docs-dev/derived-fields.md section 5.3). pi is only defined up to a constant; these accelerations do not depend on it.
Mean pressure as CM1: each part's top-level mean is zero, except p_b, whose top level
carries the mean of the model's pi' there.

Same math as CM1, line for line where it matters (stencils, the fluxes next to the bottom
and top, interpolation weights, mean pressure), so with the staggered winds (output_u,
output_v, output_w) and the base state (output_basestate) in the files it reproduces what
CM1 would have written, except:

- within ~3 points of an open lateral boundary (CM1's inflow-boundary flux rule and its
  halo values are not redone: ghost points copy the edge);
- qc0 and qi0 (base-state cloud) are taken as zero: CM1 does not write them;
- the FFT and tridiagonal solve are this file's, with CM1's coefficients: round-off.

Without the staggered winds, u, v, w are interpolated back from uinterp, vinterp,
winterp (an approximation: info['winds'] says so). Without the base state, it comes
from the first output (horizontal means / domain corner), which includes any initial
perturbation. The horizontal grid must be uniform; no terrain, not axisymmetric.

Use:
    import cm1_pdecomp as P
    out = P.run_decomposition("/run/cm1out_000034.nc")     # reads /run/namelist.input
    P.write_data("/run/cm1out_000034.nc", out)              # or P.write_separate(...)

Threads: CM1_PDECOMP_THREADS (or PDECOMP_THREADS) sets how many threads the array
work and the FFTs use (default: every CPU this process may use). A 1280 x 1280 x 115
grid takes ~2 min with 4 CPUs and ~35 GB of memory.

Written for atmo3d by Bobby Saba, from CM1 (George Bryan, NSF NCAR); GPL-3.0-or-later.
"""

import os
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import netCDF4 as nc
from scipy.fft import fftn, ifftn, dctn, idctn

VERSION = 'cm1_pdecomp 1.1 (CM1 pdcomp.F method; acc_b summed at the w levels)'
NAMES = ('p_b', 'p_l', 'p_nl', 'p_c', 'acc_b', 'acc_l', 'acc_nl', 'acc_c')
LONG_NAMES = {
    'p_b': ('pressure perturbation: buoyancy part', 'Pa'),
    'p_l': ('pressure perturbation: linear dynamic part', 'Pa'),
    'p_nl': ('pressure perturbation: nonlinear dynamic part', 'Pa'),
    'p_c': ('pressure perturbation: Coriolis part', 'Pa'),
    'acc_b': ('vertical acceleration: buoyancy + buoyancy-pressure gradient', 'm/s^2'),
    'acc_l': ('vertical acceleration: linear dynamic pressure gradient', 'm/s^2'),
    'acc_nl': ('vertical acceleration: nonlinear dynamic pressure gradient', 'm/s^2'),
    'acc_c': ('vertical acceleration: Coriolis pressure gradient', 'm/s^2'),
}


def _cpus():
    try:
        return len(os.sched_getaffinity(0))
    except AttributeError:  # (not on macOS)
        return os.cpu_count() or 1


THREADS = int(os.environ.get('CM1_PDECOMP_THREADS',
                             os.environ.get('PDECOMP_THREADS', _cpus())))


def parallel_rows(func, n, threads=None):
    """func(slice) for strips covering range(n), on several threads (func writes its
    results into preallocated arrays; numpy releases the GIL)."""
    threads = threads or THREADS
    parts = 1 if threads <= 1 else min(n, 4 * threads)
    edges = np.linspace(0, n, parts + 1).astype(int)
    strips = [slice(a, b) for a, b in zip(edges[:-1], edges[1:]) if b > a]
    if threads <= 1:
        for s in strips:
            func(s)
        return
    with ThreadPoolExecutor(max_workers=threads) as ex:
        for f in [ex.submit(func, s) for s in strips]:
            f.result()


# CM1 defaults (constants.F, set_constants: not the stratocumulus test cases)
Rd, Rv, cp, g, p00 = 287.04, 461.5, 1005.7, 9.81, 1.0e5
reps = Rv / Rd
repsm1 = reps - 1.0
WEPS = 100.0 * 1.0e-18   # CM1: weps = 100*epsilon, epsilon = 1e-18 (constants.F)

# mass mixing ratios of liquid and solid species (CM1 sums q3d over nql1..nql2 and
# nqs1..nqs2): whichever are in the file
CONDENSATE = ('qc', 'qr', 'qi', 'qs', 'qg', 'qh', 'qhl', 'qi1', 'qi2', 'qi3')

# what the method reads, by need
NEEDS = {
    'grid': ('xh', 'yh', 'xf', 'yf', 'zf'),
    'thermo': ('th', 'qv'),
    'pressure (pi or prs)': ('pi',),
    'staggered winds (output_u/v/w)': ('u', 'v', 'w'),
    'base state (output_basestate)': ('th0', 'qv0', 'pi0', 'prs0', 'u0', 'v0'),
    'Coriolis (f_cor; else f = 0)': ('f_cor',),
}
INTERP_WINDS = ('uinterp', 'vinterp', 'winterp')


def check_inputs(ds):
    """({need: [missing names]}, condensate names in the file, blocking problems)."""
    have = set(ds.variables)
    missing = {k: [n for n in v if n not in have] for k, v in NEEDS.items()}
    if 'zh' not in have and 'z' not in have:
        missing['grid'].append('zh (or z)')
    if 'pi' not in have and 'prs' in have:
        missing['pressure (pi or prs)'] = []
    hard = missing['grid'] + missing['thermo'] + missing['pressure (pi or prs)']
    if missing['staggered winds (output_u/v/w)'] and not all(n in have for n in INTERP_WINDS):
        hard += missing['staggered winds (output_u/v/w)']
    return missing, [q for q in CONDENSATE if q in have], hard


def _var(ds, name, t=0):
    """One time of a variable as float32 (a netCDF variable, or an array as read with
    its time axis: 4D for 3D fields)."""
    v = ds[name]
    dims = getattr(v, 'dimensions', None)
    has_t = dims[0] == 'time' if dims else np.ndim(v) == 4
    return np.asarray(v[t] if has_t else v[:], dtype=np.float32)


def exner(ds, t=0):
    """The model's pi (from prs where pi is not written)."""
    if 'pi' in ds.variables:
        return _var(ds, 'pi', t)
    return ((_var(ds, 'prs', t).astype(float) / p00) ** (Rd / cp)).astype(np.float32)


def winds(ds, G, periodic, t=0):
    """CM1's staggered u (nk, nj, ni+1), v (nk, nj+1, ni), w (nk+1, nj, ni), grid-relative.
    From u, v, w when written; otherwise interpolated back from uinterp, vinterp,
    winterp (grid-relative in CM1's output too): an approximation. Returns (dict, how)."""
    have = set(ds.variables)
    if all(n in have for n in ('u', 'v', 'w')):
        return {'u': _var(ds, 'u', t), 'v': _var(ds, 'v', t), 'w': _var(ds, 'w', t)}, \
            'staggered (from the file)'
    ui, vi, wi = (_var(ds, n, t) for n in INTERP_WINDS)

    def faces(a, axis):
        a2 = np.moveaxis(a, axis, -1)
        f = np.empty(a2.shape[:-1] + (a2.shape[-1] + 1,), np.float32)
        f[..., 1:-1] = 0.5 * (a2[..., :-1] + a2[..., 1:])
        if periodic:
            f[..., 0] = f[..., -1] = 0.5 * (a2[..., 0] + a2[..., -1])
        else:
            f[..., 0], f[..., -1] = a2[..., 0], a2[..., -1]
        return np.moveaxis(f, -1, axis)
    nk = G['nk']
    w = np.zeros((nk + 1,) + wi.shape[1:], np.float32)
    w[1:nk] = G['c1'][1:nk, None, None] * wi[:-1] + G['c2'][1:nk, None, None] * wi[1:]
    return {'u': faces(ui, 2), 'v': faces(vi, 1), 'w': w}, \
        'interpolated back from uinterp, vinterp, winterp (approximate)'


# ============================================================================
# grid and base state
# ============================================================================
def grid(ds):
    """CM1's vertical metrics from the file (heights in m)."""
    zname = 'zh' if 'zh' in ds.variables else 'z'
    zh = np.asarray(ds[zname][:], float).ravel() * 1000.0
    zf = np.asarray(ds['zf'][:], float).ravel() * 1000.0
    xf = np.asarray(ds['xf'][:], float).ravel() * 1000.0
    yf = np.asarray(ds['yf'][:], float).ravel() * 1000.0
    dxx, dyy = np.diff(xf), np.diff(yf)
    if np.ptp(dxx) > 0.01 * dxx.mean() or np.ptp(dyy) > 0.01 * dyy.mean():
        raise ValueError("stretched horizontal grid: the spectral solve needs uniform dx, dy")
    nk = zh.size
    c2 = np.zeros(nk + 1)      # weight of the upper scalar level at w level k (param.F)
    c2[1:nk] = (zf[1:nk] - zh[:-1]) / (zh[1:] - zh[:-1])
    rdzc = np.zeros(nk + 1)    # 1/(zh(k) - zh(k-1)) at w levels  (CM1 rdz*mf)
    rdzc[1:nk] = 1.0 / np.diff(zh)
    return {'zh': zh, 'zf': zf, 'nk': nk, 'nj': yf.size - 1, 'ni': xf.size - 1,
            'dx': dxx.mean(), 'dy': dyy.mean(), 'rdzl': 1.0 / np.diff(zf),  # CM1 rdz*mh
            'rdzc': rdzc, 'c2': c2, 'c1': 1.0 - c2}


def base_state(ds, G, t0_ds=None, full=True):
    """CM1's base state. From the file's th0, qv0, pi0, prs0, u0, v0 when written
    (output_basestate); otherwise estimated from the first output (t0_ds) as atmo3d's
    solver does (horizontal means / domain corner), which includes any initial bubble.

    Columns (nk,) for everything CM1 takes at (1,1,k); th0, qv0, u0, v0 also as the
    full 3D fields ('th0_3d' ...) when `full` and written, as CM1 uses them there."""
    have = set(ds.variables)
    out = {'from_file': all(n in have for n in NEEDS['base state (output_basestate)'])}
    if out['from_file']:
        for n in ('th0', 'qv0', 'pi0', 'prs0', 'u0', 'v0'):
            a = _var(ds, n)
            out[n] = a[:, 0, 0].astype(float)
            if full and n in ('th0', 'qv0', 'u0', 'v0'):
                out[n + '_3d'] = a
    else:
        if t0_ds is None:
            raise ValueError("no base state in the file (output_basestate) and no first "
                             "output given to estimate it from")
        th = _var(t0_ds, 'th')
        out['th0'] = th.mean(axis=(1, 2)).astype(float)
        out['qv0'] = _var(t0_ds, 'qv').mean(axis=(1, 2)).astype(float)
        out['pi0'] = exner(t0_ds)[:, 0, 0].astype(float)
        out['prs0'] = p00 * out['pi0'] ** (cp / Rd)
        for n, alt in (('u0', 'u'), ('v0', 'v')):
            src = alt if alt in t0_ds.variables else alt + 'interp'
            out[n] = _var(t0_ds, src)[:, 0, 0].astype(float)
    th0, qv0 = out['th0'], out['qv0']
    out['thv0'] = th0 * (1.0 + reps * qv0) / (1.0 + qv0)          # qc0 = qi0 = 0
    out['rho0'] = out['prs0'] / (Rd * th0 * out['pi0'] * (1.0 + qv0 * reps))
    rf0 = np.empty(G['nk'] + 1)
    rf0[1:-1] = G['c1'][1:-1] * out['rho0'][:-1] + G['c2'][1:-1] * out['rho0'][1:]
    rf0[0], rf0[-1] = out['rho0'][0], out['rho0'][-1]   # (not used: w = 0 there)
    out['rf0'] = rf0
    return out


def setup_solver(G, B, periodic):
    """The solver for CM1's equation (init3d.F: cfa, cfc with rf0 * avg(thv0) at w
    levels, ad1 = 1/(cp rho0 thv0)): a horizontal FFT (periodic) or cosine transform
    (open boundaries: CM1's mirror images) and a tridiagonal solve in the vertical."""
    nk = G['nk']
    H = B['rho0'] * B['thv0']
    Hf = B['rf0'][1:-1] * 0.5 * (B['thv0'][:-1] + B['thv0'][1:])
    dz, dzc = 1.0 / G['rdzl'], np.diff(G['zh'])
    cfa, cfc = np.zeros(nk), np.zeros(nk)
    cfa[1:] = Hf / (H[1:] * dz[1:] * dzc)
    cfc[:-1] = Hf / (H[:-1] * dz[:-1] * dzc)
    ky, kx = np.arange(G['nj']), np.arange(G['ni'])
    m = 2.0 if periodic else 1.0
    Ly = 2.0 * (np.cos(m * np.pi * ky / G['nj']) - 1.0) / G['dy'] ** 2
    Lx = 2.0 * (np.cos(m * np.pi * kx / G['ni']) - 1.0) / G['dx'] ** 2
    return {'cfa': cfa, 'cfc': cfc, 'L': Ly[:, None] + Lx[None, :], 'H': H, 'Hf': Hf,
            'dz': dz, 'dzc': dzc, 'periodic': periodic}


def solve_pressure_equation(F, solver, threads=None):
    """pi (z, y, x) for forcing F (CM1's def), volume mean removed."""
    threads = threads or THREADS
    cfa, cfc, L, H = solver['cfa'], solver['cfc'], solver['L'], solver['H']
    nz, ny = F.shape[0], F.shape[1]
    rhs = F / (cp * H[:, None, None])
    if solver['periodic']:
        rhs_hat = fftn(rhs, axes=(1, 2), workers=threads)
    else:
        rhs_hat = dctn(rhs, type=2, axes=(1, 2), norm='ortho', workers=threads)
    del rhs
    rhs_00 = rhs_hat[:, 0, 0].copy()   # (the singular mean mode: integrated below)
    L_safe = L.copy()
    L_safe[0, 0] = -1.0
    pi_hat = np.empty(rhs_hat.shape, dtype=rhs_hat.dtype)

    def sweep(rows):   # Thomas algorithm, each horizontal mode on its own
        Ls, r = L_safe[rows], rhs_hat[:, rows]
        cp_ = np.zeros(r.shape, dtype=r.dtype)
        dp_ = np.zeros(r.shape, dtype=r.dtype)
        den = Ls - cfa[0] - cfc[0]
        cp_[0], dp_[0] = cfc[0] / den, r[0] / den
        for k in range(1, nz):
            den = (Ls - cfa[k] - cfc[k]) - cfa[k] * cp_[k - 1]
            cp_[k] = cfc[k] / den
            dp_[k] = (r[k] - cfa[k] * dp_[k - 1]) / den
        for k in range(nz - 2, -1, -1):
            dp_[k] -= cp_[k] * dp_[k + 1]
        pi_hat[:, rows] = dp_
    parallel_rows(sweep, ny, threads)
    del rhs_hat
    w_col = H * solver['dz']   # mean mode: flux through each w level, no net source
    rhs_00 -= np.sum(w_col * rhs_00) / np.sum(w_col)
    flux = np.cumsum(w_col * rhs_00)[:-1]
    pi_00 = np.zeros(nz, dtype=pi_hat.dtype)
    pi_00[1:] = np.cumsum(flux * solver['dzc'] / solver['Hf'])
    pi_hat[:, 0, 0] = pi_00
    if solver['periodic']:
        pi = ifftn(pi_hat, axes=(1, 2), workers=threads).real
    else:
        pi = idctn(pi_hat, type=2, axes=(1, 2), norm='ortho', workers=threads)
    return pi - np.mean(pi)


# ============================================================================
# stencils (adv_routines.F)
# ============================================================================
def _weno5(s1, s2, s3, s4, s5):
    """CM1 weno5 with the Borges et al. (2008) smoothness indicators (siform = 2)."""
    b1 = (13.0 / 12.0) * (s1 - 2.0 * s2 + s3) ** 2 + 0.25 * (s1 - 4.0 * s2 + 3.0 * s3) ** 2
    b2 = (13.0 / 12.0) * (s2 - 2.0 * s3 + s4) ** 2 + 0.25 * (s2 - s4) ** 2
    b3 = (13.0 / 12.0) * (s3 - 2.0 * s4 + s5) ** 2 + 0.25 * (3.0 * s3 - 4.0 * s4 + s5) ** 2
    tau = np.abs(b1 - b3)
    w1 = 0.1 * (1.0 + np.minimum(1.0e30, tau / (b1 + WEPS)) ** 2)
    w2 = 0.6 * (1.0 + np.minimum(1.0e30, tau / (b2 + WEPS)) ** 2)
    w3 = 0.3 * (1.0 + np.minimum(1.0e30, tau / (b3 + WEPS)) ** 2)
    return (w1 * ((2.0 * s1 - 7.0 * s2 + 11.0 * s3) / 6.0)
            + w2 * ((-s2 + 5.0 * s3 + 2.0 * s4) / 6.0)
            + w3 * ((2.0 * s3 + 5.0 * s4 - s5) / 6.0)) / (w1 + w2 + w3)


def _flx5(s1, s2, s3, s4, s5):
    """5th-order upwind flux (Wicker and Skamarock 2002)."""
    return (2.0 * s1 - 13.0 * s2 + 47.0 * s3 + 27.0 * s4 - 3.0 * s5) / 60.0


def _flx3(s1, s2, s3):
    """3rd-order upwind flux (next to the bottom and top with flx5)."""
    return (-s1 + 5.0 * s2 + 2.0 * s3) / 6.0


def _upstrpd(s1, s2, s3):
    """CM1 upstrpd: positive-definite upstream scheme (Beets and Koren 1996), used for
    the fluxes next to the bottom and top."""
    dd = s2 - s1
    rr = (s3 - s2) / (np.where(dd >= 0.0, WEPS, -WEPS) + dd)
    phi = np.maximum(0.0, np.minimum(rr, np.minimum(1.0 / 6.0 + (2.0 / 6.0) * rr, 1.0)))
    return s2 + phi * (s2 - s1)


def _hflux(ap, vel, axis, off, nface, scheme):
    """Upwind fluxes at the faces between padded cells L and L+1, L = off .. off+nface-1,
    along `axis` (5-point stencils: needs L-2 >= 0 and L+3 < n)."""
    A = np.moveaxis(ap, axis, 0)
    s = lambda o: A[off + o: off + o + nface]
    pos = scheme(s(-2), s(-1), s(0), s(1), s(2))
    neg = scheme(s(3), s(2), s(1), s(0), s(-1))
    V = np.moveaxis(vel, axis, 0)
    return np.moveaxis(V * np.where(V >= 0.0, pos, neg), 0, axis)


def _vflux(a, vel, wup, scheme, low):
    """CM1's vertical fluxes (vadv_weno5 / vadv_flx5 with the lower-order fluxes next to
    the bottom and top) at the n-1 interior faces between cells L and L+1 of `a` along
    axis 0. vel: (n-1, ...) at those faces; wup: (n-1,) weight of the upper cell for the
    centred interpolation at the end faces; low: the 3-point flux next to them (upstrpd
    with WENO, flx3 with flx5)."""
    n = a.shape[0]
    F = np.empty(vel.shape)
    s = lambda o: a[2 + o: n - 3 + o]
    V = vel[2:n - 3]
    F[2:n - 3] = V * np.where(V >= 0.0, scheme(s(-2), s(-1), s(0), s(1), s(2)),
                              scheme(s(3), s(2), s(1), s(0), s(-1)))
    V = vel[0]
    F[0] = V * np.where(V >= 0.0, (1.0 - wup[0]) * a[0] + wup[0] * a[1],
                        low(a[2], a[1], a[0]))
    V = vel[1]
    F[1] = V * np.where(V >= 0.0, low(a[0], a[1], a[2]),
                        scheme(a[4], a[3], a[2], a[1], a[0]))
    V = vel[n - 3]
    F[n - 3] = V * np.where(V > 0.0, scheme(a[n - 5], a[n - 4], a[n - 3], a[n - 2], a[n - 1]),
                            low(a[n - 1], a[n - 2], a[n - 3]))
    V = vel[n - 2]
    F[n - 2] = V * np.where(V > 0.0, low(a[n - 3], a[n - 2], a[n - 1]),
                            (1.0 - wup[-1]) * a[n - 2] + wup[-1] * a[n - 1])
    return F


def _pad(a, axis, n, periodic, stag=False):
    """Ghost points along `axis`: periodic wrap (a staggered array's last point repeats
    its first: dropped first) or a copy of the edge (open boundaries)."""
    if periodic and stag:
        a = np.take(a, np.arange(a.shape[axis] - 1), axis=axis)
    w = [(0, 0)] * a.ndim
    w[axis] = (n, n)
    return np.pad(a, w, mode='wrap' if periodic else 'edge')


# ============================================================================
# advection (adv.F advu / advv / advw)
# ============================================================================
def advection(U, G, B, periodic, perturbation=True, scheme='weno5', threads=None):
    """CM1's advective momentum tendencies -(u . grad) a on the staggered grid (m/s^2),
    a = u - u0, v - v0, w (perturbation, as pdcomp.F) or the full u, v, w (as the
    model's own ub_/vb_/wb_ hadv + vadv + hidiff + vidiff budgets).

    U: 'u' (nk, nj, ni+1), 'v' (nk, nj+1, ni), 'w' (nk+1, nj, ni): grid-relative, as
    CM1 writes u, v; with 'u0', 'v0' (column or 3D). Returns uten, vten, wten."""
    sch, low = {'weno5': (_weno5, _upstrpd), 'flx5': (_flx5, _flx3)}[scheme]
    nk, nj, ni, dx, dy = G['nk'], G['nj'], G['ni'], G['dx'], G['dy']
    rho0, rf0, rdzl, rdzc, c1, c2 = (B['rho0'], B['rf0'], G['rdzl'], G['rdzc'],
                                     G['c1'], G['c2'])
    u, v, w = U['u'], U['v'], U['w']

    def base(name, k=None, rows=None):
        """the base wind to remove at level k, or at all levels for a strip of rows"""
        b = U.get(name)
        if not perturbation or b is None:
            return 0.0
        if k is not None:
            return b[k] if b.ndim == 3 else b[k]
        return b[:, rows] if b.ndim == 3 else b[:, None, None]

    au = lambda k: u[k].astype(float) - base('u0', k=k)                # one level
    av = lambda k: v[k].astype(float) - base('v0', k=k)
    au_rows = lambda r: u[:, r].astype(float) - base('u0', rows=r)     # strip of rows
    av_rows = lambda r: v[:, r].astype(float) - base('v0', rows=r)
    col = lambda x: x[:, None, None]

    # mass divergence at scalar points (CM1 divx; rrw = 0 at the bottom and top)
    divx = np.empty((nk, nj, ni))

    def div_rows(r):
        rrw = col(rf0) * w[:, r].astype(float)
        rrw[0] = rrw[-1] = 0.0
        divx[:, r] = (col(rho0) * ((u[:, r, 1:] - u[:, r, :-1]) / dx
                                   + (v[:, r.start + 1:r.stop + 1] - v[:, r]) / dy)
                      + (rrw[1:] - rrw[:-1]) * col(rdzl))
    parallel_rows(div_rows, nj, threads)

    uten = np.empty(u.shape)
    vten = np.empty(v.shape)
    wten = np.zeros(w.shape)

    # ---- horizontal parts, level by level
    def h_levels(ks):
        for k in range(ks.start, ks.stop):
            rru = rho0[k] * u[k].astype(float)
            rrv = rho0[k] * v[k].astype(float)
            # u: x faces at scalar points, y faces at corners
            a = au(k)
            Fx = _hflux(_pad(a, 1, 3, periodic, stag=True), 0.5 * (rru[:, :-1] + rru[:, 1:]),
                        1, 3, ni, sch)
            adv = np.zeros(a.shape)
            adv[:, 1:ni] = -(Fx[:, 1:] - Fx[:, :-1]) / dx
            if periodic:
                adv[:, 0] = adv[:, ni] = -(Fx[:, 0] - Fx[:, -1]) / dx
            rrvp = _pad(rrv, 1, 1, periodic)
            Fy = _hflux(_pad(a, 0, 3, periodic), 0.5 * (rrvp[:, 1:] + rrvp[:, :-1]),
                        0, 2, nj + 1, sch)
            uten[k] = adv - (Fy[1:] - Fy[:-1]) / dy
            # v: x faces at corners, y faces at scalar points
            a = av(k)
            rrup = _pad(rru, 0, 1, periodic)
            Fx = _hflux(_pad(a, 1, 3, periodic), 0.5 * (rrup[1:] + rrup[:-1]),
                        1, 2, ni + 1, sch)
            adv = -(Fx[:, 1:] - Fx[:, :-1]) / dx
            Fy = _hflux(_pad(a, 0, 3, periodic, stag=True), 0.5 * (rrv[:-1] + rrv[1:]),
                        0, 3, nj, sch)
            advy = np.zeros(a.shape)
            advy[1:nj] = -(Fy[1:] - Fy[:-1]) / dy
            if periodic:
                advy[0] = advy[nj] = -(Fy[0] - Fy[-1]) / dy
            vten[k] = adv + advy
        for k in range(max(ks.start, 1), min(ks.stop, nk)):
            # w at interior w level k: faces at u- and v-points, mass flux from k-1 and k
            a = w[k].astype(float)
            rru = (rho0[k] * c2[k] * u[k].astype(float)
                   + rho0[k - 1] * c1[k] * u[k - 1].astype(float))
            rrv = (rho0[k] * c2[k] * v[k].astype(float)
                   + rho0[k - 1] * c1[k] * v[k - 1].astype(float))
            Fx = _hflux(_pad(a, 1, 3, periodic), rru, 1, 2, ni + 1, sch)
            Fy = _hflux(_pad(a, 0, 3, periodic), rrv, 0, 2, nj + 1, sch)
            wten[k] = -(Fx[:, 1:] - Fx[:, :-1]) / dx - (Fy[1:] - Fy[:-1]) / dy
    parallel_rows(h_levels, nk, threads)

    # ---- vertical parts, divergence term and 1/rho0, strip by strip of rows
    def u_rows(r):
        a = au_rows(r)
        rrw = col(rf0) * w[:, r].astype(float)
        rrw[0] = rrw[-1] = 0.0
        rrwp = _pad(rrw, 2, 1, periodic)
        wbar = 0.5 * (rrwp[1:nk, :, 1:] + rrwp[1:nk, :, :-1])
        Fz = np.zeros((nk + 1,) + a.shape[1:])
        Fz[1:nk] = _vflux(a, wbar, c2[1:nk], sch, low)
        dvp = _pad(divx[:, r], 2, 1, periodic)
        t = (uten[:, r] - (Fz[1:] - Fz[:-1]) * col(rdzl)
             + a * 0.5 * (dvp[:, :, 1:] + dvp[:, :, :-1])) / col(rho0)
        if not periodic:
            t[:, :, 0] = t[:, :, -1] = 0.0   # (CM1 open boundaries: i = 1, ni+1 not set)
        uten[:, r] = t
    parallel_rows(u_rows, nj, threads)

    def v_rows(r):
        rv = slice(r.start, r.stop + 1 if r.stop == nj else r.stop)  # (last v row too)
        a = av_rows(rv)
        # scalar rows j-1 and j around each v row j (ghost rows: wrap or edge copy)
        idx = np.arange(rv.start - 1, rv.stop)
        idx = idx % nj if periodic else np.clip(idx, 0, nj - 1)
        rrw = col(rf0) * w[:, idx].astype(float)
        rrw[0] = rrw[-1] = 0.0
        divr = divx[:, idx]
        wbar = 0.5 * (rrw[1:nk, 1:] + rrw[1:nk, :-1])
        Fz = np.zeros((nk + 1,) + a.shape[1:])
        Fz[1:nk] = _vflux(a, wbar, c2[1:nk], sch, low)
        t = (vten[:, rv] - (Fz[1:] - Fz[:-1]) * col(rdzl)
             + a * 0.5 * (divr[:, 1:] + divr[:, :-1])) / col(rho0)
        if not periodic:
            if rv.start == 0:
                t[:, 0] = 0.0
            if rv.stop == nj + 1:
                t[:, -1] = 0.0
        vten[:, rv] = t
    parallel_rows(v_rows, nj, threads)

    def w_rows(r):
        a = w[:, r].astype(float)
        rrw = col(rf0) * a
        rrw[0] = rrw[-1] = 0.0
        Fz = _vflux(a, 0.5 * (rrw[:-1] + rrw[1:]), np.full(nk, 0.5), sch, low)  # at scalar levels
        k = slice(1, nk)
        wten[k, r] = (wten[k, r] - (Fz[1:] - Fz[:-1]) * col(rdzc[1:nk])
                      + a[k] * (col(c2[1:nk]) * divx[1:, r] + col(c1[1:nk]) * divx[:-1, r])
                      ) / col(rf0[1:nk])
    parallel_rows(w_rows, nj, threads)
    return uten, vten, wten


# ============================================================================
# the four forcings
# ============================================================================
def buoyancy(ds, B, condensate=None, t=0):
    """CM1's buoyancy on scalar levels: g [th'/th0 + (Rv/Rd - 1)(qv - qv0) - q_cond]
    (qc0 = qi0 = 0)."""
    th0 = B.get('th0_3d', B['th0'][:, None, None])
    qv0 = B.get('qv0_3d', B['qv0'][:, None, None])
    names = condensate if condensate is not None else \
        [q for q in CONDENSATE if q in ds.variables]
    qc = np.zeros(_var(ds, 'th', t).shape)
    for q in names:
        qc += _var(ds, q, t)
    th = _var(ds, 'th', t)
    out = g * ((th - th0) / th0 + repsm1 * (_var(ds, 'qv', t) - qv0) - qc)
    return out, names


def forcing(G, B, uten=None, vten=None, wten=None, threads=None):
    """CM1 poiss: def = rho0 (d uten/dx + d vten/dy) + d(rf0 wten)/dz at scalar points."""
    nk, nj, ni = G['nk'], G['nj'], G['ni']
    F = np.zeros((nk, nj, ni))
    col = lambda x: x[:, None, None]

    def rows(r):
        f = np.zeros((nk, r.stop - r.start, ni))
        if uten is not None:
            f += col(B['rho0']) * (uten[:, r, 1:] - uten[:, r, :-1]) / G['dx']
        if vten is not None:
            f += col(B['rho0']) * (vten[:, r.start + 1:r.stop + 1] - vten[:, r]) / G['dy']
        if wten is not None:
            rw = col(B['rf0']) * wten[:, r]
            f += (rw[1:] - rw[:-1]) * col(G['rdzl'])
        F[:, r] = f
    parallel_rows(rows, nj, threads)
    return F


def buoyancy_tendency(Bz, G):
    """B interpolated to the interior w levels (c1, c2), zero at the bottom and top."""
    nk = G['nk']
    wt = np.zeros((nk + 1,) + Bz.shape[1:])
    wt[1:nk] = G['c1'][1:nk, None, None] * Bz[:-1] + G['c2'][1:nk, None, None] * Bz[1:]
    return wt


def linear_tendencies(U, G, B, periodic):
    """pdcomp.F: -w dU0/dz, -w dV0/dz at u- and v-points (base-state shear at w levels,
    averaged to scalar levels); one copy of the linear term."""
    nk = G['nk']
    w = U['w']
    rf0, rdzc, rho0 = B['rf0'], G['rdzc'], B['rho0']
    out = []
    for name, axis in (('u0', 2), ('v0', 1)):
        b = B[name]
        sh = np.zeros(nk + 1)
        sh[1:nk] = -0.5 * rf0[1:nk] * (b[1:] - b[:-1]) * rdzc[1:nk]
        wp = _pad(w, axis, 1, periodic)
        ws = (wp[:, :, :-1] + wp[:, :, 1:]) if axis == 2 else (wp[:, :-1] + wp[:, 1:])
        dum = sh[:, None, None] * ws
        out.append((0.5 / rho0)[:, None, None] * (dum[:-1] + dum[1:]))
    return out[0], out[1]


def coriolis_tendencies(U, f, periodic):
    """pdcomp.F: f v at u-points, -f u at v-points (full grid-relative winds)."""
    vp = _pad(U['v'], 2, 1, periodic)
    up = _pad(U['u'], 1, 1, periodic)
    ut = 0.25 * f * (vp[:, :-1, :-1] + vp[:, 1:, :-1] + vp[:, :-1, 1:] + vp[:, 1:, 1:])
    vt = -0.25 * f * (up[:, :-1, :-1] + up[:, :-1, 1:] + up[:, 1:, :-1] + up[:, 1:, 1:])
    return ut, vt


# ============================================================================
# the decomposition
# ============================================================================
def pgrad_w(pi_part, G, B):
    """CM1's vertical pressure-gradient acceleration of one part at w levels
    (writeout.F pgradb / pgraddl / pgraddn / pgradc): -cp thv0 d(pi)/dz, zero at the
    bottom and top. Does not depend on the constant pi is defined up to."""
    nk = G['nk']
    thv0w = G['c2'][1:nk] * B['thv0'][1:] + G['c1'][1:nk] * B['thv0'][:-1]
    pg = np.zeros((nk + 1,) + pi_part.shape[1:])
    pg[1:nk] = (-cp * thv0w * G['rdzc'][1:nk])[:, None, None] * (pi_part[1:] - pi_part[:-1])
    return pg


def pgrad_scalar(pi_part, G, B):
    """pgrad_w averaged to the scalar levels (CM1's zh is midway between zf levels)."""
    pg = pgrad_w(pi_part, G, B)
    return 0.5 * (pg[:-1] + pg[1:])


def _top_mean(a):
    return float(np.mean(a[-1], dtype=np.float64))


def decompose(path, periodic, t0_path=None, t=0, scheme=None, threads=None, log=print):
    """CM1's decomposition of one output time. Returns float32 (z, y, x) fields:
    pi_b, pi_l, pi_nl, pi_c (Exner parts; pi_c absent when f = 0), p_b ... (Pa, from
    the parts as atmo3d converts its own) and acc_b ... (m/s^2, scalar levels: CM1's
    pgrad -cp thv0 d(pi)/dz averaged from the w levels; acc_b: B + pgrad_b at the w
    levels, averaged), with 'B' (scalar-level buoyancy) and 'info'.

    Mean pressure as CM1: each part's top-level mean set to zero, except p_b whose top
    level carries the mean of the model's pi' there.

    scheme: the run's momentum advection, 'weno5' (default) or 'flx5'
    (scheme_from_namelist reads it from namelist.input)."""
    ds = nc.Dataset(path)
    t0 = nc.Dataset(t0_path) if t0_path else None
    try:
        missing, cond, hard = check_inputs(ds)
        if hard:
            raise ValueError(f"the file lacks {', '.join(hard)}")
        G = grid(ds)
        B = base_state(ds, G, t0)
        solver = setup_solver(G, B, periodic)
        U, how = winds(ds, G, periodic, t)
        U.update(u0=B.get('u0_3d', B['u0']), v0=B.get('v0_3d', B['v0']))
        log(f"  winds {how}; base state from "
            f"{'the file' if B['from_file'] else 'the first output'}; "
            f"condensate: {', '.join(cond) or 'none'}")
        f = float(np.ravel(ds['f_cor'][:])[0]) if 'f_cor' in ds.variables else 0.0
        pi = exner(ds, t)
        pi0 = B['pi0'][:, None, None]
        ppi_top = float(np.mean(pi[-1] - B['pi0'][-1], dtype=np.float64))
        Bz, _ = buoyancy(ds, B, cond, t)
    finally:
        ds.close()
        if t0 is not None:
            t0.close()
    scheme = scheme or 'weno5'
    out = {'info': {'periodic': periodic, 'f': f, 'scheme': scheme, 'condensate': cond,
                    'base_from_file': B['from_file'], 'winds': how, 'version': VERSION}}

    def solve(F, top):
        p = solve_pressure_equation(F, solver, threads)
        return p + (top - _top_mean(p))

    p_t0 = p00 * pi0 ** (cp / Rd)

    def keep(k, pk):
        """float32 outputs of one part, made as soon as it is solved (memory)"""
        out['pi_' + k] = pk.astype(np.float32)
        out['p_' + k] = (p00 * (pi0 + pk) ** (cp / Rd) - p_t0).astype(np.float32)
        if k == 'b':  # (B and pgrad_b added at the w levels, then averaged together)
            acc = pgrad_w(pk, G, B) + buoyancy_tendency(Bz, G)
            acc = 0.5 * (acc[:-1] + acc[1:])
        else:
            acc = pgrad_scalar(pk, G, B)
        out['acc_' + k] = acc.astype(np.float32)

    log("  buoyancy part...")
    keep('b', solve(forcing(G, B, wten=buoyancy_tendency(Bz, G), threads=threads), ppi_top))
    log("  linear part...")
    ut, vt = linear_tendencies(U, G, B, periodic)
    keep('l', solve(forcing(G, B, ut, vt, threads=threads), 0.0))
    del ut, vt
    log(f"  nonlinear part ({scheme} advection)...")
    ut, vt, wt = advection(U, G, B, periodic, True, scheme, threads)
    F = forcing(G, B, ut, vt, wt, threads=threads)
    del ut, vt, wt
    if f == 0.0:
        del U
    keep('nl', solve(F, 0.0))
    del F
    if f != 0.0:
        log("  Coriolis part...")
        ut, vt = coriolis_tendencies(U, f, periodic)
        del U
        keep('c', solve(forcing(G, B, ut, vt, threads=threads), 0.0))
        del ut, vt
    else:   # (f = 0: no Coriolis part, kept as zeros so every output has the same fields)
        for n in ('pi_c', 'p_c', 'acc_c'):
            out[n] = np.zeros(out['p_b'].shape, np.float32)

    out['B'] = Bz.astype(np.float32)
    out['pprime'] = (p00 * (pi0 + (pi - pi0)) ** (cp / Rd) - p_t0).astype(np.float32)
    return out


def read_namelist(path):
    """{name: value string} from a namelist.input (lower-case names)."""
    vals = {}
    with open(path) as fh:
        for line in fh:
            line = line.split('!')[0].strip().rstrip(',')
            if '=' in line:
                k, _, v = line.partition('=')
                vals[k.strip().lower()] = v.strip().strip("'\"")
    return vals


def scheme_from_namelist(path):
    """(scheme, namelist values): the run's momentum advection as this module names it
    ('weno5' or 'flx5'; None when it is neither), from namelist.input."""
    try:
        vals = read_namelist(path)
    except OSError:
        return None, {}
    num = lambda k, d: int(float(vals.get(k, d)))
    if num('advwenov', 0) >= 1:
        sch = 'weno5' if num('weno_order', 5) == 5 else None
    else:
        sch = 'flx5' if num('hadvordrv', 5) == 5 and num('vadvordrv', 5) == 5 else None
    return sch, vals


def settings(namelist):
    """(periodic, scheme) from namelist.input; raises ValueError for runs this method
    cannot do (terrain, axisymmetric, advection other than WENO5 / 5th order)."""
    sch, vals = scheme_from_namelist(namelist)
    if not vals:
        raise ValueError(f"cannot read {namelist}")
    for key, why in (('terrain_flag', 'terrain'), ('axisymm', 'an axisymmetric grid')):
        if vals.get(key, '0').strip('.').lower() in ('true', 't', '1'):
            raise ValueError(f"the run uses {why}: CM1's decomposition does not support it")
    if sch is None:
        raise ValueError("the run's momentum advection is neither WENO5 nor 5th order "
                         f"(advwenov={vals.get('advwenov')}, weno_order={vals.get('weno_order')},"
                         f" hadvordrv={vals.get('hadvordrv')})")
    return int(float(vals.get('wbc', 1))) == 1, sch


def run_decomposition(path, namelist=None, t0_path=None, t=0, threads=None, log=print,
                      run_dir=None):
    """CM1's decomposition of one output file, with the run's settings from its
    namelist.input (default: next to the file) and, if the file has no base state, the
    first output (default: cm1out_000001.nc next to the file). See decompose() for
    what it returns."""
    run_dir = run_dir or os.path.dirname(os.path.abspath(path))
    namelist = namelist or os.path.join(run_dir, 'namelist.input')
    periodic, scheme = settings(namelist)
    if t0_path is None:
        cand = os.path.join(run_dir, 'cm1out_000001.nc')
        t0_path = cand if os.path.exists(cand) else None
    with nc.Dataset(path) as d:
        if all(n in d.variables for n in NEEDS['base state (output_basestate)']):
            t0_path = None
        elif t0_path is None:
            raise ValueError("no base state in the file (output_basestate) and no first "
                             "output to estimate it from")
    log(f"{os.path.basename(path)}: lateral boundaries "
        f"{'periodic' if periodic else 'open'}, advection {scheme}, {threads or THREADS} threads")
    return decompose(path, periodic, t0_path=t0_path, t=t, scheme=scheme,
                     threads=threads, log=log)


def _dims(ds):
    """the scalar-grid dimension names (newer CM1: zh, yh, xh; older: nk, nj, ni)"""
    return ('time', 'zh', 'yh', 'xh') if 'zh' in ds.dimensions else ('time', 'nk', 'nj', 'ni')


def _put(ds, out, dims, names, t=0):
    for n in names:
        v = ds[n] if n in ds.variables else ds.createVariable(n, 'f4', dims)
        v.long_name, v.units = LONG_NAMES[n]
        v.pdecomp_version = VERSION
        v[t] = out[n]


def write_data(ds, out, names=NAMES, t=0):
    """Write the parts into a CM1 output file (a path, or a netCDF4.Dataset open 'r+'),
    float32 with a pdecomp_version attribute, replacing older values. A file written
    this way grows by 8 x 4 bytes per grid point (~6 GB for 1280 x 1280 x 115).
    Careful: a job killed during the write can leave the file damaged."""
    own = isinstance(ds, (str, os.PathLike))
    d = nc.Dataset(ds, 'r+') if own else ds
    try:
        _put(d, out, _dims(d), names, t)
        d.sync()
    finally:
        if own:
            d.close()


def write_separate(out, path, like, names=NAMES):
    """Write the parts into a new netCDF file `path`, with the grid and time of the CM1
    output file `like` (which is left untouched)."""
    with nc.Dataset(like) as src, nc.Dataset(path, 'w') as d:
        dims = _dims(src)
        for n in dims[1:]:
            d.createDimension(n, len(src.dimensions[n]))
        d.createDimension('time', None)
        coords = ['time', 'xh', 'yh', 'zh' if 'zh' in src.variables else 'z']
        for n in coords:
            if n in src.variables:
                s = src[n]
                v = d.createVariable(n, s.dtype, s.dimensions)
                v.setncatts({a: s.getncattr(a) for a in s.ncattrs()})
                v[:] = s[:]
        d.source = os.path.abspath(like)
        d.pdecomp_version = VERSION
        _put(d, out, dims, names)
