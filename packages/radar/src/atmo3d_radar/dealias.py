"""Radial velocity dealiasing (unfolding), one sweep at a time, region based.

A Doppler radar measures radial velocity only modulo twice its Nyquist velocity N: a
true velocity v is seen as v - 2Nk for the k that brings it into [-N, N).  Unfolding
finds each gate's k again.  The method is the region-based one (as Py-ART's
dealias_region_based; Helmus and Collis 2016), written here with numpy and
scipy.ndimage:

  1. Regions: the sweep's velocities are split into SPLITS equal intervals of
     [-N, N]; gates that touch (along a ray, or the same gate of the next ray, the last
     ray touching the first) and fall in one interval form a region.  A fold is a jump
     of about 2N between neighbouring gates, so it always lies on a region's edge.
  2. Merging: the two groups of regions with the most touching gate pairs are merged
     first, the smaller one shifted by the multiple of 2N that makes their velocities
     along the shared edge agree best; then the next strongest edge, until every group
     of regions that touches is one.  A long shared edge outvotes a short one, so a
     few noisy gates do not decide a fold.
  3. Each group (a stretch of echo not touching any other) is then shifted as a whole.
     The largest by the multiple of 2N that puts the most of its gates in [-N, N] (most
     of a storm's winds are within the Nyquist interval); another by the largest's
     gates along the same rays (the nearest within REACH gates, across a gap in the
     echo), on average; one with none of those near is put in [-N, N] too (an isolated
     echo is left as measured).

Gates without a velocity (NaN) stay NaN.  A sweep with no Nyquist velocity is returned
as it is.
"""
import heapq

import numpy as np
from scipy import ndimage

SPLITS = 3  # intervals of [-N, N] the regions are made of
SHIFTS = (0, 1, -1, 2, -2, 3, -3, 4, -4)  # whole-group shifts tried at the end (x 2N;
# the smaller first: a tie keeps it)
REACH = 80  # gates: how far along a ray a detached echo looks for the main one


def _regions(v, ok, nyq):
    """(labels (nr, ng) int64, 0 where no velocity; number of regions)."""
    width = 2.0 * nyq / SPLITS
    band = np.clip(np.floor((np.where(ok, v, 0.0) + nyq) / width), 0, SPLITS - 1)
    labels = np.zeros(v.shape, np.int64)
    n = 0
    for b in range(SPLITS):
        lab, m = ndimage.label(ok & (band == b))
        sel = lab > 0
        labels[sel] = lab[sel] + n
        n += m
    return labels, n


def _edges(v, labels, nray):
    """(a, b, count, sum of v[a side] - v[b side]) of each pair of touching regions,
    a < b: gate pairs along rays, between neighbouring rays, and from the last ray to
    the first."""
    lab = labels[:nray]
    val = v[:nray].astype(np.float64)
    pairs = [(lab[:, :-1], lab[:, 1:], val[:, :-1], val[:, 1:]),
             (lab[:-1], lab[1:], val[:-1], val[1:])]
    if nray > 2:
        pairs.append((lab[-1:], lab[:1], val[-1:], val[:1]))
    la, lb, d = [], [], []
    for a, b, va, vb in pairs:
        m = (a > 0) & (b > 0) & (a != b)
        a, b, va, vb = a[m], b[m], va[m], vb[m]
        swap = a > b
        la.append(np.where(swap, b, a))
        lb.append(np.where(swap, a, b))
        d.append(np.where(swap, vb - va, va - vb))
    la, lb, d = np.concatenate(la), np.concatenate(lb), np.concatenate(d)
    if not la.size:
        return la, lb, np.zeros(0), np.zeros(0)
    m = int(labels.max()) + 1
    uniq, inv = np.unique(la * m + lb, return_inverse=True)
    cnt = np.bincount(inv).astype(np.float64)
    tot = np.bincount(inv, weights=d)
    return uniq // m, uniq % m, cnt, tot


def _merge(n, a, b, cnt, tot, two_n):
    """The fold of each region (1..n): (n + 1,) int64, groups merged strongest edge
    first; and each region's group (its root)."""
    fold = np.zeros(n + 1, np.int64)
    root = np.arange(n + 1)
    members = {r: [r] for r in range(1, n + 1)}
    # adj[g][h] = [gate pairs, sum of (g side - h side)] between groups g and h
    adj = {r: {} for r in range(1, n + 1)}
    for x, y, c, s in zip(a.tolist(), b.tolist(), cnt.tolist(), tot.tolist()):
        adj[x][y] = [c, s]
        adj[y][x] = [c, -s]
    heap = [(-c, x, y) for x, y, c in zip(a.tolist(), b.tolist(), cnt.tolist())]
    heapq.heapify(heap)
    while heap:
        c, g, h = heapq.heappop(heap)
        if root[g] != g or root[h] != h:
            continue
        e = adj[g].get(h)
        if e is None or e[0] != -c:
            continue  # (stale: the edge grew, or went, since)
        if len(members[g]) < len(members[h]):
            g, h = h, g  # (h, the smaller, is shifted and folded into g)
            e = adj[g][h]
        # g side - h side, on average: h is shifted by the folds that best cancel it
        shift = int(np.rint(e[1] / (e[0] * two_n)))
        if shift:
            for r in members[h]:
                fold[r] += shift
            for k, f in adj[h].items():  # (h's side of each edge moved by shift)
                f[1] += f[0] * two_n * shift
                adj[k][h][1] -= adj[k][h][0] * two_n * shift
        del adj[g][h], adj[h][g]
        for k, f in adj.pop(h).items():
            back = adj[k].pop(h)
            got = adj[g].get(k)
            if got is None:
                adj[g][k] = f
                adj[k][g] = back
            else:
                got[0] += f[0]
                got[1] += f[1]
                adj[k][g][0] += back[0]
                adj[k][g][1] += back[1]
            heapq.heappush(heap, (-adj[g][k][0], g, k))
        for r in members[h]:
            root[r] = g
        members[g].extend(members.pop(h))
    return fold, root


def dealias(v, nyq, nray=None, reach=REACH):
    """Sweep v (rays, gates; rays in azimuth order, NaN padding rays after the last)
    unfolded: float32, the same shape.  nyq: the sweep's Nyquist velocity (m/s); nray:
    the rays that are not padding (default every ray); reach: gates along a ray a
    detached echo looks for the main one."""
    v = np.asarray(v, np.float32)
    out = v.copy()
    if not (np.isfinite(nyq) and nyq > 0) or v.ndim != 2:
        return out
    nray = v.shape[0] if nray is None else int(min(nray, v.shape[0]))
    ok = np.isfinite(v)
    ok[nray:] = False
    if not ok.any():
        return out
    nyq = float(nyq)
    two_n = 2.0 * nyq
    labels, n = _regions(v, ok, nyq)
    a, b, cnt, tot = _edges(v, labels, nray)
    fold, root = _merge(n, a, b, cnt, tot, two_n)
    # each group as a whole: the largest by the shift that puts most of its gates
    # within [-N, N]; the others by the largest's gates along their rays, else so too
    lab = labels[ok]
    vals = v[ok].astype(np.float64) + two_n * fold[lab]
    grp = root[lab]
    size = np.bincount(grp, minlength=n + 1)
    main = int(np.argmax(size))
    best, score = np.zeros(n + 1, np.int64), np.full(n + 1, -1.0)
    for s in SHIFTS:
        inside = np.bincount(grp, weights=(np.abs(vals + two_n * s) <= nyq),
                             minlength=n + 1)
        better = inside > score
        best[better], score[better] = s, inside[better]
    ref, near = _along_rays(ok, grp == main, vals + two_n * best[main])
    use = (grp != main) & (near <= reach)
    if use.any():
        w = np.bincount(grp[use], minlength=n + 1)
        d = np.bincount(grp[use], weights=(ref[use] - vals[use]) / two_n, minlength=n + 1)
        has = w > 0
        best[has] = np.rint(d[has] / w[has]).astype(np.int64)
    out[ok] = (vals + two_n * best[grp]).astype(np.float32)
    return out


def _along_rays(ok, main, values):
    """For each gate with a velocity (in ok's order): the main group's value at the
    nearest of its gates on the same ray, and how many gates away that is (inf: none
    on the ray)."""
    nr, ng = ok.shape
    have = np.zeros(ok.shape, bool)
    have[ok] = main
    val = np.zeros(ok.shape)
    val[ok] = np.where(main, values, 0.0)
    idx = np.where(have, np.arange(ng)[None, :], -1)
    before = np.maximum.accumulate(idx, axis=1)
    idx = np.where(have, np.arange(ng)[None, :], ng)
    after = np.minimum.accumulate(idx[:, ::-1], axis=1)[:, ::-1]
    g = np.broadcast_to(np.arange(ng)[None, :], ok.shape)
    db = np.where(before >= 0, g - before, np.inf)
    da = np.where(after < ng, after - g, np.inf)
    pick = np.where(db <= da, before, after).clip(0, ng - 1)
    rows = np.broadcast_to(np.arange(nr)[:, None], ok.shape)
    return val[rows, pick][ok], np.minimum(db, da)[ok]


def dealias_volume(vol, sweeps):
    """Every sweep of vol (sweeps, rays, gates) unfolded, with the sweep table's
    Nyquist velocities and rays (cfradial.Sweeps or a level2 Table)."""
    out = np.empty_like(np.asarray(vol, np.float32))
    for k in range(vol.shape[0]):
        out[k] = dealias(vol[k], sweeps.nyquist[k], int(np.isfinite(sweeps.az[k]).sum()))
    return out
