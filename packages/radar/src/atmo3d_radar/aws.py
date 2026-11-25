"""NEXRAD Level II volumes from the public archive on AWS, fetched into a local folder.

The archive is an S3 bucket open to anonymous reads (BUCKET), laid out by day and site:
YYYY/MM/DD/SITE/SITEyyyymmdd_hhmmss_V06[.gz].  It is read over plain HTTPS with the
standard library (S3's ListObjectsV2 for the listings, a GET per file): no boto3 or
s3fs.  Files go to <folder>/<SITE>_<yyyymmdd> (one folder per site and day, as the radar
run opens a folder: a time window that spans midnight lands in the first day's folder),
written as <name>.part and renamed when complete, so a folder never holds half a file;
a file already there with the archive's size is not fetched again.

  sites(day)                         the sites with volumes that day
  volumes(site, start, end)          [Remote] of the volumes in [start, end] (UTC)
  fetch(vols, folder, progress, cancelled)   download into folder: the paths
  folder_for(root, site, start)      where a window's volumes go
  default_root()                     the radar_nexrad_dir setting, else cache_dir/nexrad

Compute nodes on HPC systems often have no route to the internet: a failed request
raises Offline, whose message says so.
"""
import datetime as dt
import os
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from . import level2

BUCKET = "https://unidata-nexrad-level2.s3.amazonaws.com"
TIMEOUT = 30  # s, per request
AGENT = "atmo3d"
SITE = re.compile(r"^[A-Z0-9]{4}$")
CHUNK = 1 << 20
LIVE_MIN_EVERY = 15.0  # s: the command line's --every at least


class Offline(OSError):
    """The archive could not be reached (no network here, or the bucket refused)."""


@dataclass(frozen=True)
class Remote:
    """A volume in the archive: its time (UTC, from its name), key and size (bytes)."""
    time: dt.datetime
    key: str
    size: int

    @property
    def name(self):
        return self.key.rsplit("/", 1)[-1]

    @property
    def url(self):
        return f"{BUCKET}/{urllib.parse.quote(self.key)}"


def _get(url, timeout=TIMEOUT):
    req = urllib.request.Request(url, headers={"User-Agent": AGENT})
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        raise Offline(f"the NEXRAD archive answered {e.code} {e.reason} for {url}") from e
    except (urllib.error.URLError, OSError) as e:
        why = getattr(e, "reason", e)
        raise Offline(f"could not reach the NEXRAD archive ({why}). Compute nodes often "
                      f"have no internet: fetch from a login node (or your own computer) "
                      f"and open the folder here.") from e


def _list(prefix, delimiter=None):
    """(keys [(key, size)], common prefixes) under `prefix`, every page."""
    keys, prefixes, token = [], [], None
    while True:
        q = {"list-type": "2", "prefix": prefix}
        if delimiter:
            q["delimiter"] = delimiter
        if token:
            q["continuation-token"] = token
        with _get(f"{BUCKET}/?{urllib.parse.urlencode(q)}") as r:
            root = ET.fromstring(r.read())
        ns = root.tag[:root.tag.index("}") + 1] if root.tag.startswith("{") else ""
        for c in root.iter(f"{ns}Contents"):
            keys.append((c.findtext(f"{ns}Key"), int(c.findtext(f"{ns}Size") or 0)))
        for c in root.iter(f"{ns}CommonPrefixes"):
            prefixes.append(c.findtext(f"{ns}Prefix"))
        if (root.findtext(f"{ns}IsTruncated") or "").lower() != "true":
            return keys, prefixes
        token = root.findtext(f"{ns}NextContinuationToken")
        if not token:
            return keys, prefixes


def check_site(site):
    s = (site or "").strip().upper()
    if not SITE.match(s):
        raise ValueError(f"a NEXRAD site is four letters (e.g. KTLX), not {site!r}")
    return s


def sites(day):
    """The sites with volumes on `day` (a date), sorted."""
    _, prefixes = _list(f"{day:%Y/%m/%d}/", "/")
    return sorted(p.rstrip("/").rsplit("/", 1)[-1] for p in prefixes)


def volumes(site, start, end):
    """[Remote] of site's volumes with times in [start, end] (UTC datetimes), by time.
    (The archive's _MDM metadata files are left out.)"""
    site = check_site(site)
    if end < start:
        start, end = end, start
    out, day = [], start.date()
    while day <= end.date():
        keys, _ = _list(f"{day:%Y/%m/%d}/{site}/")
        for key, size in keys:
            t = level2.name_time(key.rsplit("/", 1)[-1])
            if t is not None and start <= t <= end:
                out.append(Remote(t, key, size))
        day += dt.timedelta(days=1)
    return sorted(out, key=lambda v: v.time)


def default_root():
    """Where fetched volumes go: the radar_nexrad_dir setting, else cache_dir/nexrad."""
    from atmo3d import config
    d = str(config.get("radar_nexrad_dir") or "").strip()
    return config.expand(d) if d else config.cache_dir("nexrad")


def folder_for(root, site, start):
    """The folder of a site's volumes from `start`'s day: <root>/<SITE>_<yyyymmdd>."""
    return os.path.join(root, f"{check_site(site)}_{start:%Y%m%d}")


def fetch(vols, folder, progress=None, cancelled=None):
    """Download `vols` ([Remote]) into `folder` (made if missing).  progress(done bytes,
    total bytes, name) after each chunk; cancelled() -> True stops at the next chunk
    (the file being fetched is not kept).  Returns the paths of the volumes now in the
    folder, by time (those fetched before a cancel included)."""
    os.makedirs(folder, mode=0o755, exist_ok=True)
    total = sum(v.size for v in vols)
    done, paths = 0, []
    for v in vols:
        dest = os.path.join(folder, v.name)
        if os.path.exists(dest) and os.path.getsize(dest) == v.size:
            done += v.size
            paths.append(dest)
            if progress is not None:
                progress(done, total, v.name)
            continue
        part = dest + ".part"
        try:
            with _get(v.url, timeout=TIMEOUT) as r, open(part, "wb") as f:
                while True:
                    if cancelled is not None and cancelled():
                        raise _Cancelled
                    b = r.read(CHUNK)
                    if not b:
                        break
                    f.write(b)
                    done += len(b)
                    if progress is not None:
                        progress(done, total, v.name)
            os.replace(part, dest)
        except _Cancelled:
            _drop(part)
            return paths
        except BaseException:
            _drop(part)
            raise
        paths.append(dest)
    return paths


class _Cancelled(Exception):
    pass


def _drop(path):
    try:
        os.remove(path)
    except OSError:
        pass


# ---------------------------------------------------------------------- the command line
def _when(text):
    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y%m%d_%H%M"):
        try:
            return dt.datetime.strptime(text, fmt)
        except ValueError:
            pass
    raise ValueError(f"a time is YYYY-MM-DDTHH:MM (UTC), not {text!r}")


def main(argv=None):
    """atmo3d-nexrad SITE START END [--into FOLDER] [--list]: fetch a time window's
    Level II volumes (UTC) into <FOLDER or radar_nexrad_dir>/<SITE>_<yyyymmdd>.
    atmo3d-nexrad SITE --live [--hours H] [--every S]: the last H hours (default 1),
    then each new volume as the archive gets it, until Ctrl-C (atmo3d_radar.live)."""
    import argparse
    import sys
    ap = argparse.ArgumentParser(
        prog="atmo3d-nexrad", description="Download NEXRAD Level II volumes from the "
        "public AWS archive into a folder atmo3d opens as a radar run.")
    ap.add_argument("site", help="four-letter radar ID, e.g. KTLX")
    ap.add_argument("start", nargs="?", help="UTC, e.g. 2013-05-20T19:30 (with --live: "
                    "default --hours ago)")
    ap.add_argument("end", nargs="?", help="UTC, e.g. 2013-05-20T21:00 (not with --live)")
    ap.add_argument("--into", help="the folder that holds the per-site, per-day folders "
                    "(default: the radar_nexrad_dir setting, else <cache_dir>/nexrad)")
    ap.add_argument("--list", action="store_true", help="only list the volumes")
    ap.add_argument("--live", action="store_true", help="then keep fetching new volumes "
                    "as they come, until Ctrl-C")
    ap.add_argument("--hours", type=float, default=1.0, help="with --live and no START: "
                    "how far back to begin (default 1)")
    ap.add_argument("--every", type=float, default=60.0, help="with --live: seconds "
                    "between checks of the archive (default 60, at least 15)")
    a = ap.parse_args(argv)
    try:
        site = check_site(a.site)
        if a.live:
            if a.end:
                raise ValueError("--live goes on from START: give no END")
            now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
            t0 = _when(a.start) if a.start else now - dt.timedelta(hours=max(a.hours, 0))
            t1 = now
        elif not (a.start and a.end):
            raise ValueError("give START and END (UTC), or --live")
        else:
            t0, t1 = _when(a.start), _when(a.end)
        vols = volumes(site, t0, t1)
    except (ValueError, Offline) as e:
        ap.exit(2, f"atmo3d-nexrad: {e}\n")
    size = sum(v.size for v in vols)
    print(f"{len(vols)} volumes, {size / 1e6:,.0f} MB")
    if a.list or (not vols and not a.live):
        for v in vols:
            print(f"  {v.name}  {v.size / 1e6:6.1f} MB")
        return 0
    from atmo3d import config
    folder = folder_for(config.expand(a.into) if a.into else default_root(), site, t0)

    def progress(done, total, name):
        sys.stderr.write(f"\r{100 * done / max(total, 1):5.1f}%  {name}   ")
    try:
        paths = fetch(vols, folder, progress)
    except (Offline, OSError) as e:
        ap.exit(1, f"\natmo3d-nexrad: {e}\n")
    except KeyboardInterrupt:
        ap.exit(130, "\natmo3d-nexrad: stopped (fetch again to get the rest)\n")
    sys.stderr.write("\n")
    print(f"{len(paths)} volumes in {folder}")
    if a.live:
        return _live(site, folder, max((v.time for v in vols), default=t1),
                     max(LIVE_MIN_EVERY, a.every))
    return 0


def _live(site, folder, since, every):
    """The command line's --live: a follower in the foreground, until Ctrl-C."""
    from . import live
    f = live.Follower(site, folder, since, every)
    print(f"Live: checking every {every:g} s for {site} volumes after {f.last:%H:%M:%S} "
          f"UTC (Ctrl-C stops)", flush=True)
    said = ""
    try:
        while True:
            try:
                for p in f.check():
                    print(f"  {os.path.basename(p)}", flush=True)
                f.error = ""
            except (Offline, OSError, ValueError) as e:
                f.error = str(e)
            if f.error and f.error != said:
                print(f"  (check failed, trying again: {f.error})", flush=True)
            said = f.error
            f._halt.wait(every)
    except KeyboardInterrupt:
        print(f"\nStopped: {f.fetched} new volumes in {folder}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
