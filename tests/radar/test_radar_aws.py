"""NEXRAD from AWS (atmo3d_radar.aws, aws_ui) and the run picker's sources, without the
network: aws._get answers from a fake bucket."""
import datetime as dt
import io
import os

import pytest

from atmo3d_radar import aws, aws_ui

pytest.importorskip("panel")

D = dt.datetime


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


def _listing(keys, prefixes=(), token=None):
    ns = "http://s3.amazonaws.com/doc/2006-03-01/"
    body = "".join(f"<Contents><Key>{k}</Key><Size>{s}</Size></Contents>" for k, s in keys)
    body += "".join(f"<CommonPrefixes><Prefix>{p}</Prefix></CommonPrefixes>"
                    for p in prefixes)
    more = (f"<IsTruncated>true</IsTruncated><NextContinuationToken>{token}"
            f"</NextContinuationToken>" if token else "<IsTruncated>false</IsTruncated>")
    return f'<?xml version="1.0"?><ListBucketResult xmlns="{ns}">{more}{body}' \
           f'</ListBucketResult>'.encode()


@pytest.fixture
def bucket(monkeypatch):
    """A fake archive: {key: bytes}; listings come in pages of 2 keys."""
    files = {
        "2013/05/20/KTLX/KTLX20130520_234500_V06.gz": b"a" * 10,
        "2013/05/20/KTLX/KTLX20130520_235401_V06.gz": b"b" * 20,
        "2013/05/20/KTLX/KTLX20130520_235836_V06.gz": b"c" * 30,
        "2013/05/20/KTLX/KTLX20130520_235900_V06_MDM": b"m",
        "2013/05/21/KTLX/KTLX20130521_000249_V06.gz": b"d" * 40,
        "2013/05/20/KFWS/KFWS20130520_235000_V06.gz": b"e",
    }
    seen = []

    def get(url, timeout=aws.TIMEOUT):
        seen.append(url)
        from urllib.parse import parse_qs, unquote, urlparse
        u = urlparse(url)
        if u.query:
            q = {k: v[0] for k, v in parse_qs(u.query).items()}
            pre = q["prefix"]
            if q.get("delimiter"):
                subs = sorted({k[len(pre):].split("/")[0] for k in files if k.startswith(pre)})
                return _Resp(_listing([], [f"{pre}{s}/" for s in subs]))
            keys = sorted((k, len(b)) for k, b in files.items() if k.startswith(pre))
            i = int(q.get("continuation-token", 0))
            page = keys[i:i + 2]
            return _Resp(_listing(page, token=str(i + 2) if i + 2 < len(keys) else None))
        key = unquote(u.path.lstrip("/"))
        if key not in files:
            raise aws.Offline("404")
        return _Resp(files[key])

    monkeypatch.setattr(aws, "_get", get)
    return files, seen


def test_volumes_pages_filters_and_crosses_midnight(bucket):
    vols = aws.volumes("ktlx", D(2013, 5, 20, 23, 50), D(2013, 5, 21, 0, 10))
    assert [v.name for v in vols] == ["KTLX20130520_235401_V06.gz",
                                      "KTLX20130520_235836_V06.gz",
                                      "KTLX20130521_000249_V06.gz"]  # (no _MDM, no 23:45)
    assert [v.size for v in vols] == [20, 30, 40]
    assert vols[0].time == D(2013, 5, 20, 23, 54, 1)
    # an end before the start: the same window
    assert aws.volumes("KTLX", D(2013, 5, 21, 0, 10), D(2013, 5, 20, 23, 50)) == vols


def test_sites(bucket):
    assert aws.sites(dt.date(2013, 5, 20)) == ["KFWS", "KTLX"]


def test_bad_site():
    with pytest.raises(ValueError, match="four letters"):
        aws.volumes("OKC", D(2013, 5, 20), D(2013, 5, 20, 1))


def test_fetch_writes_skips_and_cancels(bucket, tmp_path):
    files, seen = bucket
    vols = aws.volumes("KTLX", D(2013, 5, 20, 23, 50), D(2013, 5, 21, 0, 10))
    folder = aws.folder_for(str(tmp_path), "KTLX", vols[0].time)
    assert folder.endswith("KTLX_20130520")
    got = []
    paths = aws.fetch(vols, folder, lambda d, t, n: got.append((d, t)))
    assert [os.path.basename(p) for p in paths] == [v.name for v in vols]
    assert open(paths[2], "rb").read() == b"d" * 40
    assert got[-1] == (90, 90)
    n = len(seen)
    assert aws.fetch(vols, folder) == paths  # (all there with the archive's size)
    assert len(seen) == n
    # a file of the wrong size is fetched again; a cancel keeps no .part
    with open(paths[1], "wb") as f:
        f.write(b"short")
    assert aws.fetch(vols, folder, cancelled=lambda: True) == paths[:1]
    assert not [p for p in os.listdir(folder) if p.endswith(".part")]
    assert os.path.getsize(paths[1]) == 5  # (left as it was)


def test_fetch_failure_keeps_no_part(bucket, tmp_path):
    bad = [aws.Remote(D(2013, 5, 20), "2013/05/20/KTLX/KTLX20130520_000000_V06", 9)]
    with pytest.raises(aws.Offline):
        aws.fetch(bad, str(tmp_path / "f"))
    assert os.listdir(tmp_path / "f") == []


def test_offline_message(monkeypatch):
    import urllib.error
    import urllib.request

    def boom(*a, **k):
        raise urllib.error.URLError("Network is unreachable")
    monkeypatch.setattr(urllib.request, "urlopen", boom)
    with pytest.raises(aws.Offline, match="Compute nodes often have no internet"):
        aws.sites(dt.date(2013, 5, 20))


def test_parse_window():
    day = dt.date(2013, 5, 20)
    assert aws_ui.parse_window(day, "19:30", "2100") == (D(2013, 5, 20, 19, 30),
                                                         D(2013, 5, 20, 21, 0))
    assert aws_ui.parse_window(day, "23:30", "00:30")[1] == D(2013, 5, 21, 0, 30)
    for a, b in (("24:00", "01:00"), ("x", "01:00")):
        with pytest.raises(ValueError, match="HH:MM"):
            aws_ui.parse_window(day, a, b)
    # an end at the start: the whole day after it (MAX_HOURS = 24)
    assert aws_ui.parse_window(day, "10:00", "10:00")[1] == D(2013, 5, 21, 10, 0)
    assert aws_ui.parse_window(day, "10:00", "09:59")[1] == D(2013, 5, 21, 9, 59)
    lim = aws_ui.MAX_HOURS
    try:
        aws_ui.MAX_HOURS = 1.0
        with pytest.raises(ValueError, match="at most"):
            aws_ui.parse_window(day, "10:00", "11:30")
    finally:
        aws_ui.MAX_HOURS = lim


def test_cli_list(bucket, capsys):
    assert aws.main(["KTLX", "2013-05-20T23:50", "2013-05-21T00:10", "--list"]) == 0
    out = capsys.readouterr().out
    assert "3 volumes" in out and "KTLX20130521_000249_V06.gz" in out


def test_cli_fetch(bucket, tmp_path, capsys):
    assert aws.main(["KTLX", "2013-05-20T23:50", "2013-05-20T23:59",
                     "--into", str(tmp_path)]) == 0
    assert sorted(os.listdir(tmp_path / "KTLX_20130520")) == [
        "KTLX20130520_235401_V06.gz", "KTLX20130520_235836_V06.gz"]


def test_cli_bad_time():
    with pytest.raises(SystemExit) as e:
        aws.main(["KTLX", "yesterday", "today"])
    assert e.value.code == 2


def test_picker_source_button_and_done(tmp_path):
    from atmo3d.viewer import picker
    assert aws_ui.LABEL in [s[0] for s in picker.sources()]
    opened, built = [], []

    def build(done, back):
        built.append((done, back))
        import panel as pn
        return pn.pane.HTML("x")
    picker.register_source("Test source", "tip", build)
    try:
        p = picker.RunPicker(on_open=opened.append)
        b = next(o for o in p._sources.objects if getattr(o, "name", "") == "Test source")
        b.clicks += 1
        b.clicks += 1
        assert len(built) == 1  # (built once per picker)
        assert not p._main.visible and p._other.visible
        done, back = built[0]
        back()
        assert p._main.visible and not p._other.visible
        done(str(tmp_path))  # (an empty folder: says so, opens nothing)
        assert opened == [] and "No run" in p.msg.object
    finally:
        picker._SOURCES[:] = [s for s in picker._SOURCES if s[0] != "Test source"]


def test_register_source_replaces():
    from atmo3d.viewer import picker
    n = len(picker.sources())
    picker.register_source("Twice", "a", lambda d, b: None)
    picker.register_source("Twice", "b", lambda d, b: None)
    try:
        assert len(picker.sources()) == n + 1
        assert [s[1] for s in picker._SOURCES if s[0] == "Twice"] == ["b"]
    finally:
        picker._SOURCES[:] = [s for s in picker._SOURCES if s[0] != "Twice"]
