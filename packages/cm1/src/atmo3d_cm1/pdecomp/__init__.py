"""Pressure decomposition: CM1's own method (cm1_pdecomp.py: buoyancy p_b, linear
p_l, nonlinear p_nl and Coriolis p_c, and the matching vertical accelerations).

The fields come from the output files when cm1_pdecomp wrote them there, or are
computed here for one time on request (cm1_pdecomp.py, or the user's own script: the
pdecomp_script setting), in a separate process, so the viewer's memory is freed again
as soon as it is done.  With several CPUs and enough memory the script's inputs are
read in parallel first and its array work and FFTs use several threads (~2 min with 4
CPUs on a 1280 x 1280 x 115 grid).  The result is kept in memory (run.extra) for the
last MAX_TIMES times and, on request, written into the output file with the script's
own write_data (with its pdecomp_version attribute), replacing older values.

A script either has cm1_pdecomp's run_decomposition(path, run_dir=..., t0_path=...,
threads=...) or the older interface of pdecomp_solver.py (lbc_type, domain_info,
compute_base_state, setup_pressure_solver, pressure_decomposition), which gives the
first six fields only (no Coriolis part, and its own split: p_l twice CM1's, p_nl the
residual).  Values in a file count as current only when written by cm1_pdecomp; others
show with a note and can be recomputed.
"""

import contextlib
import importlib.util
import io
import os
import threading
import time
import uuid
from concurrent.futures import ProcessPoolExecutor, TimeoutError as FutTimeout

import numpy as np

from atmo3d import config
from atmo3d.core import pool as readers
from atmo3d.core.run import IO_LOCK, VarInfo, shared_dir

NAMES = ("p_b", "p_l", "p_nl", "p_c", "acc_b", "acc_l", "acc_nl", "acc_c")
CORE = ("p_b", "p_l", "p_nl", "acc_b", "acc_l", "acc_nl")   # (what every script gives)
NEEDS = ("th", "qv")
WINDS = (("u", "v", "w"), ("uinterp", "vinterp", "winterp"))
BASE = ("th0", "qv0", "pi0", "prs0", "u0", "v0")
CURRENT = "cm1_pdecomp"   # pdecomp_version prefix of values that count as current
BUILTIN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cm1_pdecomp.py")
# free memory wanted before starting on a 1280 x 1280 x 115 grid (serial reads / inputs
# read in parallel up front; a 64 GB job ran CM1's method and the older solver one
# after the other), scaled by the number of grid points (see need_gb)
NEED_GB = 36.0
NEED_GB_PAR = 46.0
REF_POINTS = 1280 * 1280 * 115
MAX_TIMES = 2      # computed times kept in memory (8 float32 volumes each)

_lock = threading.Lock()
_running = {}      # (run path, t) -> started (time.time())
_one = threading.Lock()  # one decomposition at a time per server (~40 GB each)


def script():
    """The decomposition script: the pdecomp_script setting when set (None if that file
    is missing), else the built-in solver."""
    p = config.pdecomp_script()
    if not p:
        return BUILTIN
    return p if os.path.isfile(p) else None


def script_name():
    return os.path.basename(config.pdecomp_script()) or "CM1's method (cm1_pdecomp.py)"


def need_gb(run, parallel):
    """Free memory (GB) a decomposition of this run's grid needs."""
    frac = run.ni * run.nj * run.nk / REF_POINTS
    return max(1.0, (NEED_GB_PAR if parallel else NEED_GB) * frac)


def can_compute(run):
    sp = script()
    if not run.offers("pdecomp") or sp is None or not all(run.has(n) for n in NEEDS):
        return False
    if not new_interface(sp):  # pdecomp_solver.py's interface: what it reads
        return all(run.has(n) for n in ("pi", "rho", "prs")) and \
            (run.has("w") or run.has("winterp"))
    return (run.has("pi") or run.has("prs")) and \
        any(all(run.has(n) for n in w) for w in WINDS)


def new_interface(path):
    """True for a script with cm1_pdecomp's run_decomposition."""
    if path == BUILTIN:
        return True
    return _has_run_decomposition(path)


def register(run):
    """Make the decomposition fields known to the run even where no file has them,
    so they can be chosen (and computed) anywhere."""
    if not can_compute(run):
        return
    units = {"p": "Pa", "a": "m/s^2"}
    for n in NAMES:  # (p_c, acc_c only from cm1_pdecomp)
        if n not in run.vars:
            run.vars[n] = VarInfo(n, n, units[n[0]], 3, None)
            run.var_times[n] = frozenset()


def is_pdecomp(F, name):
    """True for a decomposition field or one derived from them."""
    if not name or name not in F:
        return False
    return name in NAMES or any(d in NAMES for d in F[name].deps)


def available(run, t):
    return all((n, t) in run.extra or run.in_file(n, t) for n in NAMES)


_version_cache = {}


def source(run, t, block=True):
    """Where the decomposition at time t comes from: ('computed' | 'file-fixed' |
    'file-old' | 'busy' | 'pending' | None, description).  block=False (from the
    page-updating thread) never waits for the file lock: 'pending' if the file's
    version tag has not been read yet (the background jobs read it)."""
    from atmo3d.core.run import FileBusy

    kind = None
    if run.in_file("p_b", t):
        key = (run.path, t)
        if key not in _version_cache:
            if not IO_LOCK.acquire(blocking=block):
                return "pending", "checking the output file"
            try:
                v = run._ds(t)["p_b"]
                _version_cache[key] = getattr(v, "pdecomp_version", "")
            except FileBusy:
                return "busy", "being written to the output file"
            finally:
                IO_LOCK.release()
        ver = _version_cache[key]
        kind = "file-fixed" if ver.startswith(CURRENT) else "file-old"
    if all((n, t) in run.extra for n in CORE):
        if kind == "file-fixed":
            return "computed", (f"computed here with {script_name()} and written to the "
                                f"output file")
        return "computed", f"computed here with {script_name()} (in memory only)"
    if kind == "file-fixed":
        ver = _version_cache[(run.path, t)]
        if ver.startswith("cm1_pdecomp 1.0"):  # (acc_b only: B added after averaging)
            return kind, (f"from the output file ({ver}); its acc_b shows horizontal "
                          "bands where B is layered (the stratosphere): recompute for "
                          "the fixed acc_b")
        return kind, f"from the output file ({ver})"
    if kind == "file-old":
        ver = _version_cache[(run.path, t)]
        return kind, ("from the output file, written by an older method "
                      f"({ver or 'no pdecomp_version'}: p_l twice CM1's, p_nl the residual, "
                      "no Coriolis part); recompute for CM1's")
    return None, "not available"


def running(run, t=None):
    with _lock:
        if t is None:
            return [tt for (p, tt) in _running if p == run.path]
        return _running.get((run.path, t))


# ------------------------------------------------------------------ memory
def _cgroup_mem():
    """(limit, used) bytes of this job's memory cgroup (the one that limits it, found
    from the job's own cgroup up), or None.  used leaves out the page cache (e.g. of
    the netCDF files), which is reclaimable."""
    lim, used = config.job_memory_limit(), config.job_memory_used_gb()
    if lim is None or used is None:
        return None
    return lim, int(used * 1024**3)


def free_gb():
    m = _cgroup_mem()
    if m is not None:
        return (m[0] - m[1]) / 1024**3
    try:
        return os.sysconf("SC_AVPHYS_PAGES") * os.sysconf("SC_PAGE_SIZE") / 1024**3
    except (AttributeError, ValueError, OSError):  # (macOS, Windows: not known)
        return float("inf")


# ------------------------------------------------------------------ worker
class _Inputs:
    """A netCDF4.Dataset stand-in for the script: variables read beforehand (in
    parallel) come from memory, anything else from the file; heights are read as
    'zh' by the script but called 'z' in older CM1 files."""

    def __init__(self, path, arrays, mode="r"):
        self._d = nc_dataset(path, mode)
        self._a = arrays

    def __getitem__(self, k):
        if k == "zh" and "zh" not in self._d.variables:
            k = "z"
        return self._a[k] if k in self._a else self._d[k]

    def __getattr__(self, k):
        return getattr(self._d, k)

    def close(self):
        self._d.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def nc_dataset(path, mode="r"):
    import netCDF4
    return netCDF4.Dataset(path, mode)


def _load(paths):
    out = {}
    for n, p in paths.items():
        out[n] = np.load(p)
        os.remove(p)
    return out


def _worker(script_path, run_path, file0, file_t, pre0, pre_t, nthreads, outdir, write,
            ready, go):
    """Process-pool worker: the script's decomposition of file_t (write=False), then,
    with `write`, its write_data into file_t once the viewer has let go of the file
    (ready -> go).  Saves the fields as float32 .npy; returns paths, log, wrote."""
    import types
    import scipy.fft

    spec = importlib.util.spec_from_file_location("atmo3d_user_pdecomp", script_path)
    P = importlib.util.module_from_spec(spec)
    log = io.StringIO()
    with contextlib.redirect_stdout(log):
        spec.loader.exec_module(P)
        a0, at = _load(pre0), _load(pre_t)
        # the script opens the files itself: hand it the pre-read inputs
        P.nc = types.SimpleNamespace(
            Dataset=lambda p, mode="r": _Inputs(
                p, at if p == file_t else a0 if p == file0 else {}, mode))
        with scipy.fft.set_workers(nthreads):
            if hasattr(P, "run_decomposition"):  # cm1_pdecomp
                out = P.run_decomposition(file_t, run_dir=run_path, t0_path=file0,
                                          threads=nthreads)
            else:  # the older interface (pdecomp_solver.py)
                d0 = _Inputs(file0, a0)
                periodic = P.lbc_type(run_path.rstrip("/") + "/")
                dom = P.domain_info(d0)
                base = P.compute_base_state(d0)
                d0.close()
                solver = P.setup_pressure_solver(dom, base, periodic)
                out = P.pressure_decomposition(file_t, dom, base, solver, write=False)
        del at, a0
    # the in-memory copy first: a failed write must not lose the computation
    paths, tag = {}, uuid.uuid4().hex
    for n in (n for n in NAMES if n in out):
        p = os.path.join(outdir, f"atmo3d-pdecomp-{os.getpid()}-{tag}-{n}.npy")
        np.save(p, np.asarray(out[n], dtype=np.float32))
        paths[n] = p
    wrote, werr = False, None
    if write:
        ready.set()
        if not go.wait(600):
            return paths, log.getvalue(), False, "the viewer did not release the file"
        try:
            with contextlib.redirect_stdout(log):
                ds = nc_dataset(file_t, "r+")
                try:
                    P.write_data(ds, out)
                finally:
                    ds.close()
            wrote = True
        except Exception as e:  # noqa: BLE001  (e.g. the file is open elsewhere)
            werr = f"{type(e).__name__}: {e}"
    return paths, log.getvalue(), wrote, werr


def writes_allowed():
    return bool(config.get("allow_writes_to_output"))


def writable(run, t):
    return writes_allowed() and os.access(run.files[t], os.W_OK)


def compute(run, t, progress=None, write=False):
    """Decompose time t (with pdecomp_solver.py or the user's script); stores the fields in run.extra and,
    with `write`, writes them into the output file (replacing older values).
    progress(elapsed_s, phase) is called about once a second.  Returns dict(elapsed,
    wrote, parallel, log).  Raises RuntimeError with a readable message on failure."""
    key = (run.path, t)
    with _lock:
        if key in _running:
            raise RuntimeError(f"already being computed for {run.time_label(t)}")
        _running[key] = time.time()
    try:
        t_wait = time.time()
        while not _one.acquire(timeout=1.0):  # another one is running: wait for it
            if progress:
                progress(time.time() - t_wait, "waiting for another decomposition")
        try:
            return _compute(run, t, progress, write)
        finally:
            _one.release()
    finally:
        with _lock:
            _running.pop(key, None)


def _inputs(run, t, new=True):
    """Fields the script reads from file t and from the first file (read in parallel
    beforehand)."""
    hyd = [n for n in ("qc", "qr", "qi", "qs", "qg", "qh", "qhl", "qi1", "qi2", "qi3")
           if run.has(n)]
    pres = "pi" if run.has("pi") else "prs"
    if not new:  # pdecomp_solver.py
        at = ["th", "qv", *hyd, "pi", "rho", "w" if run.has("w") else "winterp"]
        return at, [pres, "th", "qv"]
    winds = next(list(w) for w in WINDS if all(run.has(n) for n in w))
    base = all(run.has(n) for n in BASE)
    at = ["th", "qv", *hyd, pres, *winds, *(BASE if base else ())]
    a0 = [] if base else [pres, "th", "qv", *winds]
    return at, a0


def _compute(run, t, progress, write):
    import multiprocessing as mp

    sp = script()
    if sp is None:
        raise RuntimeError("pressure decomposition script not found: "
                           f"{config.pdecomp_script()}")
    if write and not writable(run, t):
        raise RuntimeError(f"no write permission for {run.files[t]}")
    ncpu = config.job_cpus()
    free = free_gb()
    want = need_gb(run, ncpu > 1)
    if free < want:  # make room from the 3D cache first
        run.trim_cache(int((want - free) * 1024**3))
        time.sleep(0.5)
        free = free_gb()
    parallel = ncpu > 1 and free >= need_gb(run, True)
    if not parallel and free < need_gb(run, False):
        raise RuntimeError(
            f"needs about {need_gb(run, False):.0f} GB of free memory, the job has {free:.0f} GB free "
            f"after emptying the 3D cache (start the viewer in a job with more memory, or "
            f"with a smaller --cache-gb)")
    outdir = shared_dir()[0]
    ctx = mp.get_context("spawn")
    t0 = time.time()
    pre0, pre_t, began, wrote = {}, {}, False, False

    def tick(phase):
        if progress:
            progress(time.time() - t0, phase)

    try:
        if parallel:  # read the script's inputs in parallel, straight to /dev/shm
            at, a0 = _inputs(run, t, new_interface(sp))
            run._not_writing(t)
            ex = readers.get(max(2, run.workers))  # (the reader processes every run uses)
            futs = {("t", n): ex.submit(_read_raw, run.files[t], n, outdir) for n in at}
            futs.update({("0", n): ex.submit(_read_raw, run.files[0], n, outdir)
                         for n in a0})
            try:
                while not all(f.done() for f in futs.values()):
                    tick("reading")
                    time.sleep(1.0)
                for (w, n), f in futs.items():
                    (pre_t if w == "t" else pre0)[n] = f.result()
            except BaseException:
                for f in futs.values():  # (those read meanwhile: their files removed)
                    if not f.cancel():
                        f.add_done_callback(_remove_raw)
                raise
        mgr = ctx.Manager()
        ready, go = mgr.Event(), mgr.Event()
        pool = ProcessPoolExecutor(max_workers=1, mp_context=ctx)
        try:
            fut = pool.submit(_worker, sp, run.path, run.files[0], run.files[t], pre0,
                              pre_t, min(ncpu, 8), outdir, write, ready, go)
            pre0, pre_t = {}, {}  # the worker owns (and removes) them now
            while True:
                try:
                    paths, log, wrote, werr = fut.result(timeout=1.0)
                    break
                except FutTimeout:
                    if write and not began and ready.is_set():
                        run.begin_write(t)  # let go of the file, then let it write
                        began = True
                        go.set()
                    tick("writing to the file" if began else "computing")
        finally:
            pool.shutdown(wait=True)  # the worker exits: its memory is freed
            mgr.shutdown()
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"pressure decomposition failed: {type(e).__name__}: {e}") from e
    finally:
        for p in list(pre0.values()) + list(pre_t.values()):
            with contextlib.suppress(OSError):
                os.remove(p)
        if began:
            run.end_write(t, NAMES if wrote else ())
            _version_cache.pop((run.path, t), None)
    try:
        vols = _load(paths)
    finally:
        for p in paths.values():
            with contextlib.suppress(OSError):
                os.remove(p)
    with run._cache_lock:
        for n, a in vols.items():
            run.extra[(n, t)] = a
        times = list(dict.fromkeys(tt for (n, tt) in run.extra if n in NAMES))
        for old in times[:-MAX_TIMES]:
            for n in NAMES:
                run.extra.pop((n, old), None)
    source(run, t)  # read the (new) version tag here, not in the page-updating thread
    return dict(elapsed=time.time() - t0, wrote=wrote, parallel=parallel, log=log,
                write_error=werr)


def _has_run_decomposition(path):
    """True for a script with cm1_pdecomp's interface (a cheap look at its text)."""
    try:
        with open(path) as fh:
            return "def run_decomposition(" in fh.read()
    except OSError:
        return False


def _remove_raw(fut):
    with contextlib.suppress(Exception):
        os.remove(fut.result())


def _read_raw(path, name, outdir):
    """Process-pool worker: one variable exactly as stored (time axis kept), to .npy."""
    import netCDF4
    with netCDF4.Dataset(path) as d:
        d.set_auto_mask(False)
        a = np.asarray(d[name][:])
    out = os.path.join(outdir, f"atmo3d-pdin-{os.getpid()}-{uuid.uuid4().hex}.npy")
    np.save(out, a)
    return out
