"""CM1 output as a Run: a folder of netCDF files, one time per file."""
import glob
import hashlib
import json
import os

import netCDF4
import numpy as np

from atmo3d.core import pool
from atmo3d.core.run import IO_LOCK, Run, _var_info, finished, parse_namelist, scan_files


class CM1Run(Run):
    """A folder of CM1 netCDF output (one time per file, names by output_glob)."""

    model = "cm1"
    model_label = "CM1"
    OFFERS = frozenset({"soundings", "parcels", "pdecomp", "tracking"})

    def __init__(self, path, cache_gb=12.0, workers=None, cache=None):
        super().__init__(path, cache_gb, workers, cache)
        from atmo3d import config
        pat = config.get("output_glob")
        self.files = sorted(glob.glob(os.path.join(self.path, pat)))
        if not self.files:
            raise FileNotFoundError(f"no {pat} files found in {self.path}")
        # a run still going: its newest file is being written (left out until finished)
        n = finished(self.files, self.path)
        self.files, self.busy = self.files[:n], self.files[n:]
        if not self.files:
            raise FileNotFoundError(
                f"the only {pat} file{'s' if len(self.busy) > 1 else ''} in {self.path} "
                f"{'are' if len(self.busy) > 1 else 'is'} still being written; open the "
                f"run again once one is finished")

        with IO_LOCK, netCDF4.Dataset(self.files[0]) as d:
            self.xh = np.asarray(d["xh"][:], dtype=np.float64)  # km
            self.yh = np.asarray(d["yh"][:], dtype=np.float64)
            # scalar heights: "z" in CM1's own layout, "zh" in the CF-style one
            self.z = np.asarray(d["z" if "z" in d.variables else "zh"][:], dtype=np.float64)
            self.zf = np.asarray(d["zf"][:], dtype=np.float64)
            self.attrs = {k: d.getncattr(k) for k in d.ncattrs()}
            self.vars = {}
            for name, v in d.variables.items():
                info = _var_info(name, v)
                if info is not None:
                    self.vars[name] = info
            f_cor = (float(np.ravel(d["f_cor"][:])[0]) if "f_cor" in d.variables
                     else None)

        self._grid_done()
        self.nml = parse_namelist(os.path.join(self.path, "namelist.input"))
        # f: the file's f_cor (CM1 writes it), else the namelist's fcor when icor = 1
        if f_cor is None:
            f_cor = float(self.nml.get("fcor", 0.0)) if int(self.nml.get("icor", 0)) == 1 \
                else 0.0
        self.fcor = f_cor
        moving = int(self.nml.get("imove", 0)) == 1
        # CM1 writes winds relative to the (possibly translating) grid.
        self.umove = float(self.nml.get("umove", 0.0)) if moving else 0.0
        self.vmove = float(self.nml.get("vmove", 0.0)) if moving else 0.0
        self.times, names = self._scan()
        # fields written into only some files (e.g. by post-processing): which times
        self.var_times = {}
        for n in sorted(set().union(*names) - set(self.vars)):
            ts = [t for t, ns in enumerate(names) if n in ns]
            with IO_LOCK, netCDF4.Dataset(self.files[ts[-1]]) as d:
                info = _var_info(n, d[n])
            if info is not None:
                self.vars[n] = info
                self.var_times[n] = frozenset(ts)
        for n in self.vars:
            ts = frozenset(t for t, ns in enumerate(names) if n in ns)
            if len(ts) < len(self.files) and n not in self.var_times:
                self.var_times[n] = ts

    def _scan(self):
        """Simulation time (s) and field names of every file, cached on disk by file
        stat (one quick metadata pass over the files the first time)."""
        sig = hashlib.sha1(
            json.dumps(
                [(f, os.path.getsize(f), int(os.path.getmtime(f))) for f in self.files]
            ).encode()
        ).hexdigest()[:16]
        cdir = os.path.join(os.path.expanduser("~"), ".cache", "atmo3d")
        cfile = os.path.join(cdir, f"scan-{sig}.json")
        try:
            with open(cfile) as f:
                c = json.load(f)
            return np.array(c["times"], dtype=np.float64), [set(n) for n in c["vars"]]
        except (OSError, ValueError, KeyError):
            pass
        times, names = scan_files(self.files, self.workers)
        try:
            os.makedirs(cdir, exist_ok=True)
            with open(cfile, "w") as f:
                json.dump(dict(times=times, vars=names), f)
        except OSError:
            pass
        return np.array(times, dtype=np.float64), [set(n) for n in names]

    def begin_write(self, t):
        """Close this process's handle on file t and refuse reads of it until
        end_write(t), so another process can open it for writing."""
        with IO_LOCK:
            self._writing.add(t)
            d = self._open.pop(t, None)
            if d is not None:
                d.close()
        pool.release()  # (the reader processes keep the files they last read open)

    def end_write(self, t, names=()):
        """File t is readable again; `names` were written into it."""
        with IO_LOCK:
            self._writing.discard(t)
            if names:
                with netCDF4.Dataset(self.files[t]) as d:
                    for n in names:
                        if n in d.variables:
                            self.vars[n] = _var_info(n, d[n])
                            if n in self.var_times:
                                self.var_times[n] = self.var_times[n] | {t}
        self.forget(names, t)  # cached volumes of rewritten fields are stale
