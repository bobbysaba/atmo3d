"""Small synthetic NEXRAD Level II volumes (Archive II, Message 31), with known values,
for the Level II decoder's tests (atmo3d_radar.level2).

One volume has five cuts (the ICD's layout, a few gates each):
  1  0.5 deg  surveillance: REF (40 gates), ZDR (30)        ┐ one sweep
  2  0.48 deg Doppler: VEL, SW (30), rays 0.3 deg further on ┘
  3  1.5 deg  batch: REF (36), VEL (30)
  4  0.5 deg  surveillance again (SAILS)                     ┐ one sweep
  5  0.5 deg  Doppler again                                  ┘
Rays are 1 degree apart, starting at azimuth 10.5 (so sorting them by azimuth matters).
A gate's raw word is a function of its ray and gate (REF_RAW, VEL_RAW), with raw 0
(below threshold) and 1 (range folded) at a few gates.
"""
import bz2
import datetime as dt
import gzip
import os
import struct

import numpy as np

SITE = (35.3331, -97.2778, 370, 19)  # lat, lon, site height m, feedhorn height m
VCP = 212
NYQ = 26.1
FIRST, GAP = 2125, 250  # m
NRAY = 360
REF_SCALE, REF_OFF = 2.0, 66.0
VEL_SCALE, VEL_OFF = 2.0, 129.0
ZDR_SCALE, ZDR_OFF = 16.0, 128.0
EPOCH = dt.datetime(1969, 12, 31)

# cut: (elevation, start azimuth, {code: gates}, seconds after the volume start)
CUTS = [
    (0.5, 10.5, {"REF": 40, "ZDR": 30}, 0),
    (0.48, 10.8, {"VEL": 30, "SW": 30}, 20),
    (1.5, 10.5, {"REF": 36, "VEL": 30}, 40),
    (0.5, 10.5, {"REF": 40, "ZDR": 30}, 60),
    (0.48, 10.8, {"VEL": 30, "SW": 30}, 80),
]


def ray_key(az):
    """The ray's whole degree (rays at k + 0.5 and k + 0.8 share it)."""
    return int(np.floor(az - 0.5)) % 360


def ref_raw(key, g, cut=0):
    """REF's raw word at a ray key and gate (0 and 1 at a few gates)."""
    if g == 3 and key % 7 == 0:
        return 0
    if g == 4 and key % 11 == 0:
        return 1
    return 2 + (key + 3 * g + 5 * cut) % 200


def vel_raw(key, g, cut=1):
    if g == 5 and key % 13 == 0:
        return 1
    return 2 + (2 * key + g + 7 * cut) % 250


def other_raw(key, g, code):
    return 2 + (key + g + len(code) * 17) % 240


def value(raw, scale, off):
    return np.nan if raw <= 1 else (raw - off) / scale


def _data_block(code, ng, raws, scale, off):
    bits = 16 if code == "PHI" else 8
    data = np.asarray(raws, dtype=">u2" if bits == 16 else ">u1").tobytes()
    if len(data) % 2:
        data += b"\0"
    name = ("D" + code.ljust(3)).encode()
    return struct.pack(">4sIHHHHhBBff", name, 0, ng, FIRST, GAP, 0, 0, 0, bits, scale,
                       off) + data


def _scale(code):
    return {"REF": (REF_SCALE, REF_OFF), "VEL": (VEL_SCALE, VEL_OFF),
            "ZDR": (ZDR_SCALE, ZDR_OFF)}.get(code, (2.0, 129.0))


def raw_of(code, key, g, cut):
    if code == "REF":
        return ref_raw(key, g, cut)
    if code == "VEL":
        return vel_raw(key, g, cut)
    return other_raw(key, g, code)


def _radial(el_num, i, az, el, status, date, ms, moments, cut):
    blocks = [
        struct.pack(">4sHBBffhHfffffHH", b"RVOL", 44, 1, 0, SITE[0], SITE[1], SITE[2],
                    SITE[3], 0, 0, 0, 0, 0, VCP, 0),
        struct.pack(">4sHhf", b"RELV", 12, 0, 0.0),
        struct.pack(">4sHHffHH", b"RRAD", 20, 4600, 0, 0, int(NYQ * 100), 0),
    ]
    key = ray_key(az)
    for code, ng in moments.items():
        s, o = _scale(code)
        blocks.append(_data_block(code, ng, [raw_of(code, key, g, cut) for g in range(ng)],
                                  s, o))
    hdr_size = 32 + 4 * len(blocks)
    ptrs, at = [], hdr_size
    for b in blocks:
        ptrs.append(at)
        at += len(b)
    hdr = struct.pack(">4sIHHfBxHBBBBfBBH", b"KTLX", ms, date, i + 1, az, 0, at, 1, status,
                      el_num, 1, el, 0, 0, len(blocks))
    body = hdr + struct.pack(f">{len(ptrs)}I", *ptrs) + b"".join(blocks)
    return _message(31, body, date, ms, frame=False)


def _message(typ, content, date, ms, frame=True):
    if len(content) % 2:
        content += b"\0"
    msg = b"\0" * 12 + struct.pack(">HBBHHIHH", (16 + len(content)) // 2, 8, typ, 0, date,
                                   ms, 1, 1) + content
    return msg.ljust(2432, b"\0") if frame else msg


def _vcp_message(cuts, date, ms):
    head = struct.pack(">HHHHBBBB4xHH2x", (22 + 46 * len(cuts)) // 2, 2, VCP, len(cuts),
                       1, 1, 2, 2, 0, 0)
    els = b""
    for el, _, moments, _ in cuts:
        wave = 2 if "VEL" in moments and "REF" not in moments else (
            1 if "VEL" not in moments else 4)
        els += struct.pack(">HBB", int(round(el / 360.0 * 65536)), 0, wave).ljust(46, b"\0")
    return _message(5, head + els, date, ms)


def volume_bytes(start, cuts=CUTS, compress="bz2", msg5=True, ref_gates=None):
    """The bytes of a Level II file whose volume starts at datetime `start`: compress
    "bz2" (LDM records, as the archive's files have them), "none" (records not
    compressed), or "gzip" (bz2 records in a gzip file, as the archive's older files)."""
    date = (start - EPOCH).days
    ms0 = (start - dt.datetime(start.year, start.month, start.day)).seconds * 1000
    meta = _vcp_message(cuts, date, ms0) if msg5 else b""
    records = [meta] if meta else []
    last = len(cuts) - 1
    for c, (el, az0, moments, secs) in enumerate(cuts):
        if ref_gates is not None and "REF" in moments:
            moments = dict(moments, REF=ref_gates)
        msgs = []
        for i in range(NRAY):
            az = (az0 + i) % 360.0
            status = (3 if c == 0 else 0) if i == 0 else (
                (4 if c == last else 2) if i == NRAY - 1 else 1)
            ms = ms0 + 1000 * secs + 50 * i
            msgs.append(_radial(c + 1, i, az, el + 0.01 * np.sin(i), status, date, ms,
                                moments, c))
        records.append(b"".join(msgs))
    head = b"AR2V0006." + b"001" + struct.pack(">II", date, ms0) + b"KTLX"
    if compress == "none":
        return head + b"".join(records)
    out = [head]
    for j, r in enumerate(records):
        z = bz2.compress(r)
        n = len(z) if j < len(records) - 1 else -len(z)
        out.append(struct.pack(">i", n) + z)
    data = b"".join(out)
    return gzip.compress(data) if compress == "gzip" else data


def name(start, gz=False):
    return f"KTLX{start:%Y%m%d_%H%M%S}_V06" + (".gz" if gz else "")


def write(folder, starts=None, **kw):
    """Level II files in `folder`, one per start time; their paths."""
    starts = starts or [dt.datetime(2013, 5, 20, 19, 51, 11),
                        dt.datetime(2013, 5, 20, 19, 55, 27)]
    out = []
    for s in starts:
        p = os.path.join(folder, name(s, kw.get("compress") == "gzip"))
        with open(p, "wb") as f:
            f.write(volume_bytes(s, **kw))
        out.append(p)
    return out
