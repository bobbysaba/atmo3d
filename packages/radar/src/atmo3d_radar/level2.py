"""NEXRAD Level II volumes (WSR-88D Archive II files, Message 31), decoded natively.

One file is one volume (one time), named like KTLX20130520_195111_V06 (sometimes .gz):
a 24-byte volume header, then LDM records (each a 4-byte size and a bzip2 stream) of
messages.  What the decoder relies on (RDA/RPG ICD 2620002 and 2620010):

  * Radials are Message 31 (Build 10, 2008, on; the older Message 1 is not read).  Other
    messages sit in fixed 2432-byte frames; Message 31 (and 29) take 12 + 2 x size bytes.
  * A radial's data header gives its azimuth, elevation, cut number (el_num) and time;
    its blocks (found through pointers from the data header) hold the site (VOL), the
    Nyquist velocity (RAD) and the moments (REF, VEL, SW, ZDR, PHI, RHO, CFP): gate
    count, range to the first gate's centre and gate spacing (m), word size, scale and
    offset; value = (raw - offset) / scale, raw 0 below threshold and 1 range folded.
  * Split cuts: the low elevations are scanned twice in a row, a surveillance cut
    (reflectivity, and the dual-pol moments, to 460 km) and then a Doppler cut
    (velocity and spectrum width).  The two become one sweep: the surveillance cut's
    rays, each Doppler moment taken from the Doppler cut's ray nearest in azimuth
    (super-resolution rays are 0.5 degrees apart: within 0.25 degrees).  A moment two
    merged cuts both have comes from the one with more gates.
  * SAILS / MESO-SAILS repeat the lowest elevation within a volume: each is its own
    sweep (labelled with its time).

Every moment is put on one range axis (the run's ranges): the first gate and spacing
of reflectivity, the moments with fewer gates padded with NaN (and one on other gates,
which current volumes do not have, taken at the nearest gate).

A decoded volume keeps the raw words (uint8/uint16) per sweep, made float32 per read;
the last few decoded files are kept (decoded).
"""
import bz2
import datetime as dt
import functools
import gzip
import os
import re
import struct
from collections import OrderedDict
import threading

import numpy as np

# Level II moment -> (the field name, as CfRadial files and the catalog have it; long
# name; units)
MOMENTS = {
    "REF": ("reflectivity", "Reflectivity", "dBZ"),
    "VEL": ("velocity", "Radial velocity", "m/s"),
    "SW": ("spectrum_width", "Spectrum width", "m/s"),
    "ZDR": ("differential_reflectivity", "Differential reflectivity", "dB"),
    "PHI": ("differential_phase", "Differential phase", "degrees"),
    "RHO": ("cross_correlation_ratio", "Cross-correlation ratio", ""),
    "CFP": ("clutter_filter_power_removed", "Clutter filter power removed", "dB"),
}
FIELD = {code: v[0] for code, v in MOMENTS.items()}
CODE = {v: k for k, v in FIELD.items()}


def code_of(name):
    """The Level II code of a field name ("reflectivity": "REF"; another moment's own
    code, as _level2_vars names it: lower case)."""
    return CODE.get(name, name.upper())

NAME = re.compile(r"^([A-Z0-9]{4})(\d{8})_(\d{6})(_V\d\d)?(\.gz|\.bz2)?$", re.I)

_FRAME, _CTM = 2432, 12
_MSG_HDR = struct.Struct(">HBBHHIHH")          # 16 bytes, after the 12-byte CTM
_DATA_HDR = struct.Struct(">4sIHHfBxHBBBBfBBH")  # Message 31 data header, 32 bytes
_BLOCK = struct.Struct(">4sIHHHHhBBff")        # a moment block's header, 28 bytes
_VCP = struct.Struct(">HHHHBBBB4xHH2x")        # Message 5 header, 22 bytes
_VCP_EL = 46                                   # bytes per Message 5 elevation cut
EPOCH = dt.datetime(1969, 12, 31)              # (modified Julian day 1 = 1970-01-01)


def name_time(fname):
    """The UTC time in a Level II file name (KTLX20130520_195111_V06: 2013-05-20
    19:51:11), or None."""
    m = NAME.match(os.path.basename(fname))
    if not m:
        return None
    try:
        return dt.datetime.strptime(m.group(2) + m.group(3), "%Y%m%d%H%M%S")
    except ValueError:
        return None


def candidate(fname):
    """From the name alone: could this file be a Level II volume?  (Not the archive's
    _MDM metadata files.)"""
    return name_time(fname) is not None


def _head(path, n):
    with open(path, "rb") as f:
        b = f.read(max(n, 3))
    if b[:2] == b"\x1f\x8b":
        with gzip.open(path, "rb") as f:
            return f.read(n)
    if b[:3] == b"BZh":
        with bz2.open(path, "rb") as f:
            return f.read(n)
    return b[:n]


@functools.lru_cache(maxsize=256)
def _is_level2(path, _key):
    try:
        b = _head(path, 8)
    except (OSError, EOFError, ValueError):
        return False
    return b[:4] == b"AR2V" or b[:8] == b"ARCHIVE2"


def is_level2(path):
    """Whether `path` is a Level II volume (its header says Archive II)."""
    try:
        st = os.stat(path)
    except OSError:
        return False
    return _is_level2(os.fspath(path), (st.st_mtime_ns, st.st_size))


def files_in(path, names=None):
    """[(UTC time, file path)] of the Level II volumes in folder `path`, by time (the
    first candidate's header is read; the rest are taken on their names)."""
    if names is None:
        try:
            names = os.listdir(path)
        except OSError:
            return []
    cands = sorted(n for n in names if candidate(n))
    if not cands or not is_level2(os.path.join(path, cands[0])):
        return []
    return sorted((name_time(n), os.path.join(path, n)) for n in cands)


# ---------------------------------------------------------------------- the bytes
def _records(path):
    """The file's volume header (24 bytes) and its messages, decompressed."""
    with open(path, "rb") as f:
        data = f.read()
    if data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    elif data[:3] == b"BZh":
        data = bz2.decompress(data)
    if not (data[:4] == b"AR2V" or data[:8] == b"ARCHIVE2"):
        raise ValueError(f"{os.path.basename(path)} is not a NEXRAD Level II file")
    head, body = data[:24], memoryview(data)[24:]
    if len(body) < 8 or bytes(body[4:7]) != b"BZh":
        return head, bytes(body)  # (uncompressed records)
    parts, i = [], 0
    while i + 4 <= len(body):
        n = abs(int.from_bytes(body[i:i + 4], "big", signed=True))
        i += 4
        if n == 0 or i + n > len(body):
            break
        d = bz2.BZ2Decompressor()
        parts.append(d.decompress(body[i:i + n]))
        i += n
    return head, b"".join(parts)


def _messages(body):
    """(type, offset of its content, content bytes) of each message."""
    i, n = 0, len(body)
    while i + _CTM + _MSG_HDR.size <= n:
        size, _, typ, _, _, _, nseg, seg = _MSG_HDR.unpack_from(body, i + _CTM)
        step = _FRAME
        if size:
            if size == 65535:
                step = ((nseg << 16) | seg) + _CTM
            elif typ in (29, 31):
                step = _CTM + 2 * size
            yield typ, i + _CTM + _MSG_HDR.size, 2 * size - _MSG_HDR.size
        i += max(step, _CTM + _MSG_HDR.size)


class _Cut:
    """One elevation cut as read: its rays and the raw words of each moment."""

    def __init__(self, num):
        self.num = num
        self.az, self.el, self.ms = [], [], []
        self.nyq = []
        self.data = {}  # code -> [raw array of each ray]  (None where a ray lacks it)
        self.gates = {}  # code -> (first gate km, spacing km, word bits, scale, offset)


def _decode(body):
    """(site, vcp, cuts, vcp cut table) from the messages: site (lat, lon, alt m),
    cuts [_Cut] by cut number, the table [(elevation, waveform)] of Message 5 (or [])."""
    cuts, site, vcp, table = OrderedDict(), None, None, []
    for typ, at, size in _messages(body):
        if typ == 5 and not table and size >= _VCP.size:
            h = _VCP.unpack_from(body, at)
            ncut = h[3]
            if 0 < ncut < 64 and size >= _VCP.size + ncut * _VCP_EL:
                for c in range(ncut):
                    o = at + _VCP.size + c * _VCP_EL
                    ang, _, wave = struct.unpack_from(">HBB", body, o)
                    table.append((ang * 360.0 / 65536.0, wave))
            continue
        if typ != 31:
            continue
        (_, ms, date, _, az, _, _, _, _, el_num, _, el, _, _, nblk) = \
            _DATA_HDR.unpack_from(body, at)
        cut = cuts.get(el_num)
        if cut is None:
            cut = cuts[el_num] = _Cut(el_num)
        r = len(cut.az)
        cut.az.append(az)
        cut.el.append(el)
        cut.ms.append((date, ms))
        cut.nyq.append(np.nan)
        ptrs = struct.unpack_from(f">{min(nblk, 16)}I", body, at + _DATA_HDR.size)
        for p in ptrs:
            if not p or p + 4 > size:
                continue
            o = at + p
            kind = bytes(body[o:o + 4])
            if kind == b"RVOL" and site is None:
                lat, lon, amsl, feed = struct.unpack_from(">ffhH", body, o + 8)
                site = (float(lat), float(lon), float(amsl + feed))
                vcp = struct.unpack_from(">H", body, o + 40)[0]
            elif kind == b"RRAD":
                cut.nyq[r] = struct.unpack_from(">H", body, o + 16)[0] / 100.0
            elif kind[:1] == b"D":
                code = kind[1:].decode("ascii", "replace").strip()
                (_, _, ng, first, gap, _, _, _, bits, scale, off) = \
                    _BLOCK.unpack_from(body, o)
                if bits not in (8, 16) or not ng:
                    continue
                raw = np.frombuffer(body, dtype=">u1" if bits == 8 else ">u2", count=ng,
                                    offset=o + _BLOCK.size)
                lst = cut.data.get(code)
                if lst is None:
                    lst = cut.data[code] = []
                    cut.gates[code] = (first / 1000.0, gap / 1000.0, bits, scale, off)
                lst.extend([None] * (r - len(lst)))
                lst.append(raw.astype(np.uint8 if bits == 8 else np.uint16))
    for cut in cuts.values():  # (rays at the end of a cut without a moment)
        for lst in cut.data.values():
            lst.extend([None] * (len(cut.az) - len(lst)))
    return site, vcp, list(cuts.values()), table


# ---------------------------------------------------------------------- the volume
def _ang_diff(a, b):
    return np.abs((np.asarray(a) - np.asarray(b) + 180.0) % 360.0 - 180.0)


def _cut_time(cut):
    date, ms = cut.ms[0]
    return EPOCH + dt.timedelta(days=int(date), milliseconds=int(ms))


class Table:
    """A Level II volume's sweep table, like cfradial.Sweeps (the same order: by
    elevation, rays by azimuth), without the data.

    index    (ns,) the cut number of each sweep (its surveillance cut's, when merged)
    cuts     [ns] the cut numbers each sweep is made of
    elev     (ns,) median measured elevation (deg)
    fixed    (ns,) the VCP's elevation angle (deg; NaN if Message 5 does not line up)
    nyquist  (ns,) median Nyquist velocity (m/s; the Doppler cut's)
    times    [ns] the UTC time of each sweep's first ray
    az       (ns, nr) ray azimuths (deg), ascending; NaN padding
    nr       rays of the longest sweep"""

    def __len__(self):
        return len(self.elev)

    def label(self, k):
        """A sweep's name in a list: its elevation ("0.5°"), and its time when the
        elevation repeats in the volume (SAILS: "0.5° 19:53:20")."""
        s = f"{self.elev[k]:.1f}°"
        return f"{s} {self.times[k]:%H:%M:%S}" if k in self.repeat else s


class Volume(Table):
    """A decoded Level II volume: its sweep table (Table; .table: the table alone) and
    the moments.

    site      (lat, lon, altitude m) of the antenna
    vcp       the volume coverage pattern number
    ranges    (ng,) the gate centres (km): reflectivity's
    codes     the moments the volume has (Level II codes)
    """

    def __init__(self, path):
        head, body = _records(path)
        self.path = path
        site, self.vcp, cuts, table = _decode(body)
        if not cuts:
            raise ValueError(f"{os.path.basename(path)} has no Message 31 radials (a "
                             f"Level II file from before 2008 is not read)")
        self.site = site or (np.nan, np.nan, np.nan)
        self.station = head[20:24].decode("ascii", "replace").strip("\x00 ") or "radar"
        fixed = {}
        if len(table) == len(cuts):  # (the VCP's own angles, when they line up)
            fixed = {c.num: table[i][0] for i, c in enumerate(cuts)}
        sweeps = self._merge(cuts)
        # one range axis: reflectivity's (else the moment reaching farthest)
        best = None
        for s in sweeps:
            for code, src in s["src"].items():
                first, gap, *_ = src.gates[code]
                n = max((len(a) for a in src.data[code] if a is not None), default=0)
                key = (code == "REF", first + gap * n)
                if best is None or key > best[0]:
                    best = (key, first, gap)
        _, first, gap = best
        reach = [src.gates[c][0] + src.gates[c][1] * max(
            (len(a) for a in src.data[c] if a is not None), default=0)
            for s in sweeps for c, src in s["src"].items()]
        nmax = int(round((max(reach) - first) / gap))
        self.ranges = first + gap * np.arange(nmax, dtype=np.float64)
        self._first, self._gap = first, gap
        self.codes = tuple(c for c in MOMENTS if any(c in s["src"] for s in sweeps)) + \
            tuple(sorted({c for s in sweeps for c in s["src"]} - set(MOMENTS)))
        # the sweep table, by elevation (stable: SAILS repeats keep their time order)
        elev = np.array([float(np.median(s["base"].el)) for s in sweeps])
        keep = np.argsort(elev, kind="stable")
        self._sweeps = [sweeps[k] for k in keep]
        self.elev = elev[keep]
        self.fixed = np.array([fixed.get(s["base"].num, np.nan) for s in self._sweeps])
        self.nyquist = np.array([s["nyquist"] for s in self._sweeps])
        self.times = [_cut_time(s["base"]) for s in self._sweeps]
        self.order = [np.argsort(np.asarray(s["base"].az), kind="stable")
                      for s in self._sweeps]
        self.nr = max(len(o) for o in self.order)
        self.az = np.full((len(keep), self.nr), np.nan)
        for i, (s, o) in enumerate(zip(self._sweeps, self.order)):
            self.az[i, :len(o)] = np.asarray(s["base"].az, np.float64)[o]
        self.index = np.array([s["base"].num for s in self._sweeps])
        self.cuts = [tuple(c.num for c in s["cuts"]) for s in self._sweeps]
        self.repeat = {k for k in range(len(self)) if
                       np.sum(np.abs(self.elev - self.elev[k]) < 0.05) > 1}
        t = self.table = Table()
        for a in ("index", "cuts", "elev", "fixed", "nyquist", "times", "az", "nr",
                  "repeat"):
            setattr(t, a, getattr(self, a))

    @staticmethod
    def _merge(cuts):
        """The sweeps of the cuts: [{"base": cut whose rays the sweep has, "cuts": its
        cuts, "src": {code: cut it comes from}, "nyquist"}], a surveillance cut (no
        velocity) and the Doppler cut after it at the same elevation made one."""
        out, i = [], 0
        while i < len(cuts):
            c = cuts[i]
            group = [c]
            nxt = cuts[i + 1] if i + 1 < len(cuts) else None
            if (nxt is not None and "VEL" not in c.data and "VEL" in nxt.data
                    and abs(np.median(c.el) - np.median(nxt.el)) < 0.25):
                group.append(nxt)
            src = {}
            for g in group:
                for code, lst in g.data.items():
                    n = max((len(a) for a in lst if a is not None), default=0)
                    if code not in src or n > src[code][1]:
                        src[code] = (g, n)
            dop = [g for g in group if "VEL" in g.data]
            nyq = np.asarray(dop[0].nyq if dop else c.nyq, np.float64)
            out.append({"base": c, "cuts": group, "src": {k: v[0] for k, v in src.items()},
                        "nyquist": float(np.nanmedian(nyq)) if np.isfinite(nyq).any()
                        else np.nan})
            i += len(group)
        return out

    def has(self, code, k=None):
        if k is None:
            return any(code in s["src"] for s in self._sweeps)
        return code in self._sweeps[k]["src"]

    def sweep(self, code, k):
        """Sweep k of moment `code`: (nr, ng) float32, rays by azimuth (NaN padding,
        below threshold and range folded)."""
        s = self._sweeps[k]
        out = np.full((self.nr, len(self.ranges)), np.nan, np.float32)
        src = s["src"].get(code)
        if src is None:
            return out
        first, gap, _, scale, off = src.gates[code]
        rows = src.data[code]
        if src is s["base"]:
            take = list(self.order[k])
        else:  # (a Doppler cut's moment on the surveillance cut's rays)
            take = self._nearest(np.asarray(s["base"].az, np.float64)[self.order[k]],
                                 np.asarray(src.az, np.float64))
        same = abs(first - self._first) < 1e-6 and abs(gap - self._gap) < 1e-6
        for j, r in enumerate(take):
            a = rows[r] if r is not None and r >= 0 else None
            if a is None:
                continue
            v = a.astype(np.float32)
            v = (v - np.float32(off)) / np.float32(scale) if scale else v
            v[a <= 1] = np.nan
            if same:
                n = min(len(v), out.shape[1])
                out[j, :n] = v[:n]
            else:  # (other gates: the nearest of them)
                g = np.rint((self.ranges - first) / gap).astype(np.int64)
                ok = (g >= 0) & (g < len(v))
                out[j, ok] = v[g[ok]]
        return out

    @staticmethod
    def _nearest(want, have):
        """For each azimuth in want, the ray of `have` nearest it (-1 when none is within
        0.75 of the rays' spacing)."""
        if not len(have):
            return [-1] * len(want)
        o = np.argsort(have)
        hs = have[o]
        spacing = 360.0 / max(len(have), 1)
        i = np.searchsorted(hs, want) % len(hs)
        cand = np.stack([o[i], o[(i - 1) % len(hs)]])
        d = _ang_diff(have[cand], want[None, :])
        pick = cand[np.argmin(d, axis=0), np.arange(len(want))]
        far = d.min(axis=0) > 0.75 * spacing
        return [(-1 if f else int(p)) for p, f in zip(pick, far)]

    def volume(self, code):
        """Every sweep of moment `code`: (ns, nr, ng) float32."""
        return np.stack([self.sweep(code, k) for k in range(len(self))])


_LOCK = threading.Lock()
_DECODED = OrderedDict()
KEEP = 3  # decoded volumes kept


def volume(path):
    """The decoded Volume of a file (the last KEEP decoded are kept)."""
    st = os.stat(path)
    key = (os.fspath(path), st.st_mtime_ns, st.st_size)
    with _LOCK:
        v = _DECODED.get(key)
        if v is not None:
            _DECODED.move_to_end(key)
            return v
    v = Volume(os.fspath(path))
    with _LOCK:
        _DECODED[key] = v
        while len(_DECODED) > KEEP:
            _DECODED.popitem(last=False)
    return v
