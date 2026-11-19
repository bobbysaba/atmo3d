"""Pressure decomposition: CM1's method (cm1_pdecomp.py, built in) or the pdecomp_script setting's.
Works on copies of the demo run's first files (never on real output): computing one
time, one decomposition at a time, writing into the file and reading it back, and a
failed write that keeps the result in memory."""
import os
import shutil
import stat
import threading

import netCDF4
import numpy as np
import pytest

from atmo3d import pdecomp
from atmo3d.registry import Registry
from conftest import txt, wait


@pytest.fixture
def copy_run(demo_run, tmp_path):
    """A writable copy of the demo run: namelist + the first three files."""
    dst = tmp_path / "pd_copy"
    dst.mkdir()
    shutil.copy(os.path.join(demo_run, "namelist.input"), dst)
    for n in (1, 2, 3):
        shutil.copy(os.path.join(demo_run, f"cm1out_{n:06d}.nc"), dst)
    reg = Registry(str(dst), 4, 1)
    run, F = reg.get()
    yield run, F, reg


def test_compute_from_the_map(copy_run):
    from atmo3d.viewer import app as A
    run, F, reg = copy_run
    v = A.Viewer(run, F, reg=reg)
    v.main()
    try:
        v.tslider.value = 1
        v.fill_var.value = "p_b"
        v.fill_mode.value, v.fill_lvl.value = "level", 10.0
        v.request_map()
        wait(lambda: v.pd_row.visible, 120, "compute button")
        v.pd_write.value = False
        v._on_pd_compute(None)
        wait(lambda: any(s in txt(v.status.object) for s in
                         ("computed in", "failed", "needs about")), 900, "decomposition")
        assert "computed in" in txt(v.status.object), txt(v.status.object)
        assert all((n, 1) in run.extra for n in pdecomp.NAMES)
        for n in ("acc_dyn", "acc_tot", "p_dyn"):
            assert np.isfinite(np.nanmax(F.plane(n, 1, "height", 3.0)))
    finally:
        v.close()


def test_one_at_a_time(copy_run):
    run, _, _ = copy_run
    phases = {1: [], 2: []}
    res, err = {}, {}

    def job(t):
        try:
            res[t] = pdecomp.compute(run, t, lambda s, ph: phases[t].append(ph))
        except Exception as e:  # noqa: BLE001
            err[t] = e

    a = threading.Thread(target=job, args=(1,))
    a.start()
    wait(lambda: phases[1], 300, "first started")
    b = threading.Thread(target=job, args=(2,))
    b.start()
    with pytest.raises(RuntimeError):
        pdecomp.compute(run, 1)  # the same time again
    a.join()
    b.join()
    assert not err, err
    assert "waiting for another decomposition" in phases[2]
    assert pdecomp.running(run) == []
    assert all((n, t) in run.extra for n in pdecomp.NAMES for t in (1, 2))


def test_write_and_read_back(copy_run):
    from atmo3d.core.fields import Fields
    from atmo3d.core.run import CM1Run
    run, _, _ = copy_run
    r = pdecomp.compute(run, 1, write=True)
    assert r["wrote"], r.get("write_error")
    assert not run._writing
    with netCDF4.Dataset(run.files[1]) as d:
        for n in pdecomp.NAMES:
            assert getattr(d[n], "pdecomp_version", "")
            assert np.abs(np.asarray(d[n][0, 10]) - run.extra[(n, 1)][10]).max() < 1e-3
    run2 = CM1Run(run.path, cache_gb=1, workers=1)
    assert run2.in_file("p_b", 1)
    a = Fields(run2).plane("p_b", 1, "level", 10)
    assert np.abs(a - run.extra[("p_b", 1)][10]).max() < 1e-3


def test_failed_write_keeps_the_result(copy_run):
    run, F, _ = copy_run
    T, path = 1, run.files[1]
    with netCDF4.Dataset(path) as d:
        before = set(d.variables)
    mode = os.stat(path).st_mode
    begin = run.begin_write

    def read_only_then_begin(t):
        # after the permission check, just before the worker opens the file to write
        os.chmod(path, mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
        begin(t)

    run.begin_write = read_only_then_begin
    try:
        res = pdecomp.compute(run, T, None, write=True)
    finally:
        os.chmod(path, mode)
        del run.begin_write
    assert not res["wrote"] and res["write_error"]
    assert all((n, T) in run.extra for n in pdecomp.NAMES) and not run._writing
    with netCDF4.Dataset(path) as d:
        assert set(d.variables) == before
    assert np.isfinite(np.nanmax(F.plane("p_b", T, "level", 10)))


def test_solver_satisfies_the_pressure_equation(demo_run):
    """The solved Exner perturbation, put back into the discrete operator, gives the
    forcing (open lateral boundaries: zero-gradient images)."""
    from atmo3d.pdecomp import pdecomp_solver as P
    files = sorted(f for f in os.listdir(demo_run) if f.startswith("cm1out_"))
    with netCDF4.Dataset(os.path.join(demo_run, files[0])) as d0:
        dom, base = P.domain_info(d0), P.compute_base_state(d0)
    solver = P.setup_pressure_solver(dom, base, P.lbc_type(demo_run + "/"))
    assert not solver["isperiodic"]
    with netCDF4.Dataset(os.path.join(demo_run, files[4])) as d:
        B = P.compute_buoyancy(d, base)
    rho0 = base["rho0"][:, None, None]
    rb = P.interp_to_w_levels(rho0 * B, dom)
    F = (rb[1:] - rb[:-1]) / dom["dz_layer"][:, None, None]
    pi = P.solve_pressure_equation(F, solver)

    def lap(a, axis, h):
        e = np.concatenate([a.take([0], axis), a, a.take([-1], axis)], axis)
        n = a.shape[axis]
        return (e.take(range(2, n + 2), axis) - 2 * a + e.take(range(n), axis)) / h ** 2

    H, Hf = base["H"], solver["Hf"]
    flux = np.zeros((pi.shape[0] + 1,) + pi.shape[1:])
    flux[1:-1] = Hf[:, None, None] * np.diff(pi, axis=0) / dom["dz_center"][:, None, None]
    lhs = P.cp * (H[:, None, None] * (lap(pi, 2, dom["dx"]) + lap(pi, 1, dom["dy"]))
                  + np.diff(flux, axis=0) / dom["dz_layer"][:, None, None])
    assert np.abs(lhs - F).max() < 1e-6 * np.abs(F).max()


# ---- CM1's method (cm1_pdecomp.py), the built-in since 2026-11-18 -----------------
def _grid(nk=20, n=32, dx=500.0):
    from atmo3d.pdecomp import cm1_pdecomp as M
    zf = np.concatenate([[0.0], np.cumsum(np.linspace(100.0, 400.0, nk))])
    zh = 0.5 * (zf[1:] + zf[:-1])
    c2 = np.zeros(nk + 1)
    c2[1:nk] = (zf[1:nk] - zh[:-1]) / (zh[1:] - zh[:-1])
    G = dict(nk=nk, nj=n, ni=n, dx=dx, dy=dx, zh=zh, zf=zf, rdzl=1 / np.diff(zf), c2=c2,
             c1=1 - c2, rdzc=np.r_[0, 1 / np.diff(zh), 0])
    th0 = 300 + 0.004 * zh
    qv0 = 0.014 * np.exp(-zh / 2500)
    pi0 = 1 - M.g * zh / (M.cp * 300)
    prs0 = M.p00 * pi0 ** (M.cp / M.Rd)
    rho0 = prs0 / (M.Rd * th0 * pi0 * (1 + qv0 * M.reps))
    rf0 = np.r_[rho0[0], G['c1'][1:nk] * rho0[:-1] + c2[1:nk] * rho0[1:], rho0[-1]]
    B = dict(rho0=rho0, rf0=rf0, thv0=th0 * (1 + M.reps * qv0) / (1 + qv0), pi0=pi0)
    return M, G, B


@pytest.mark.parametrize("periodic", [True, False])
def test_cm1_advection_of_uniform_flow_is_zero(periodic):
    M, G, B = _grid()
    nk, n = G['nk'], G['ni']
    U = {'u': np.full((nk, n, n + 1), 7.0), 'v': np.full((nk, n + 1, n), -3.0),
         'w': np.zeros((nk + 1, n, n))}
    for t in M.advection(U, G, B, periodic, perturbation=False):
        assert np.abs(t).max() < 1e-12


def test_cm1_advection_matches_analytic():
    """-u du/dx, -v du/dy, -w du/dz on smooth fields (WENO5: ~1e-3 relative or better)."""
    M, G, B = _grid(nk=40, n=48)
    B = dict(B, rho0=np.ones(40), rf0=np.ones(41))
    nk, n, L = G['nk'], G['ni'], G['ni'] * G['dx']
    xf = np.arange(n + 1) * G['dx']
    yh = (np.arange(n) + 0.5) * G['dx']
    k2 = 2 * np.pi / L
    u = (5 + np.sin(k2 * xf))[None, None, :] * np.ones((nk, n, 1))
    ut, _, _ = M.advection({'u': u, 'v': np.zeros((nk, n + 1, n)),
                            'w': np.zeros((nk + 1, n, n))}, G, B, True, perturbation=False)
    ex = -(5 + np.sin(k2 * xf)) * k2 * np.cos(k2 * xf)
    assert np.abs(ut - ex).max() < 1e-2 * np.abs(ex).max()
    u = np.sin(k2 * yh)[None, :, None] * np.ones((nk, 1, n + 1))
    ut, _, _ = M.advection({'u': u, 'v': np.full((nk, n + 1, n), 4.0),
                            'w': np.zeros((nk + 1, n, n))}, G, B, True, perturbation=False)
    ex = -4 * k2 * np.cos(k2 * yh)[None, :, None]
    assert np.abs(ut - ex).max() < 1e-2 * np.abs(ex).max()


@pytest.mark.parametrize("periodic", [True, False])
def test_cm1_solver_satisfies_its_equation(periodic):
    """cp [H lap_h(pi) + d/dz(Hf dpi/dz)] = F with CM1's coefficients."""
    M, G, B = _grid()
    rng = np.random.default_rng(1)
    F = rng.standard_normal((G['nk'], G['nj'], G['ni']))
    dz = 1.0 / G['rdzl']   # (a solution needs no net source: the dz-weighted mean)
    F -= np.sum(F.mean(axis=(1, 2)) * dz) / dz.sum()
    s = M.setup_solver(G, B, periodic)
    pi = M.solve_pressure_equation(F, s, threads=1)
    mode = 'wrap' if periodic else 'edge'

    def lap(a, axis, h):
        w = [(0, 0)] * 3
        w[axis] = (1, 1)
        e = np.pad(a, w, mode=mode)
        sl = lambda o: np.take(e, range(o, o + a.shape[axis]), axis)
        return (sl(2) - 2 * a + sl(0)) / h ** 2
    flux = np.zeros((G['nk'] + 1, G['nj'], G['ni']))
    flux[1:-1] = s['Hf'][:, None, None] * np.diff(pi, axis=0) / s['dzc'][:, None, None]
    lhs = M.cp * (s['H'][:, None, None] * (lap(pi, 2, G['dx']) + lap(pi, 1, G['dy']))
                  + np.diff(flux, axis=0) / s['dz'][:, None, None])
    assert np.abs(lhs - F).max() < 1e-6 * np.abs(F).max()


def test_cm1_acceleration_does_not_depend_on_the_constant():
    """acc from -cp thv0 dpi/dz: adding a constant to pi changes nothing (the older
    solver's -(1/rho) dp/dz with p from pi did)."""
    M, G, B = _grid()
    pi = np.random.default_rng(2).standard_normal((G['nk'], 4, 4)) * 1e-4
    a, b = M.pgrad_scalar(pi, G, B), M.pgrad_scalar(pi + 3e-4, G, B)
    assert np.abs(a - b).max() < 1e-12


def test_cm1_buoyancy_part_balances_uniform_buoyancy():
    """Horizontally uniform B: its pressure gradient takes it all (acc_b ~ 0), also for
    a B that alternates level by level (the bands of section 5.3: acc_b is B + pgrad_b
    summed at the w levels, then averaged)."""
    M, G, B = _grid()
    one = np.ones((1, G['nj'], G['ni']))
    s = M.setup_solver(G, B, True)
    smooth = 0.03 * np.exp(-G['zh'] / 3000)
    for prof in (smooth, smooth * (1 + 0.5 * (-1.0) ** np.arange(G['nk']))):
        Bz = prof[:, None, None] * one
        pi = M.solve_pressure_equation(M.forcing(G, B, wten=M.buoyancy_tendency(Bz, G)),
                                       s, 1)
        aw = M.pgrad_w(pi, G, B) + M.buoyancy_tendency(Bz, G)
        acc = 0.5 * (aw[:-1] + aw[1:])
        assert np.abs(acc[1:-1]).max() < 0.01 * np.abs(Bz).max()
    # (the older form, B + averaged pgrad_b, leaves the alternation)
    old = Bz + M.pgrad_scalar(pi, G, B)
    assert np.abs(old[1:-1]).max() > 0.1 * np.abs(Bz).max()


def test_old_method_values_in_a_file_are_flagged(copy_run):
    """Values written by the older solver show, flagged, and need a recompute for p_c."""
    from atmo3d.core.fields import Fields
    from atmo3d.core.run import CM1Run
    run, _, _ = copy_run
    with netCDF4.Dataset(run.files[1], "a") as d:
        for n in pdecomp.CORE:
            v = d.createVariable(n, "f8", d["th"].dimensions)
            v[:] = 1.0
            v.pdecomp_version = "atmo3d pdecomp_solver.py (= pdecomp_new_fixed_mp.py)"
    old = os.stat(run.files[0]).st_mtime   # (not "still being written")
    os.utime(run.files[1], (old, old))
    run2 = CM1Run(run.path, cache_gb=1, workers=1)
    kind, desc = pdecomp.source(run2, 1)
    assert kind == "file-old" and "older method" in desc
    F = Fields(run2)
    assert np.nanmax(F.plane("p_b", 1, "level", 5)) == 1.0
    with pytest.raises(Exception):
        F.plane("p_dyn", 1, "level", 5)   # (needs p_c)
