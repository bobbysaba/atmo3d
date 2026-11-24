"""Shared test setup: synthetic demo runs (tests/synthetic.py), a throwaway settings file, and
one Registry for the whole session.

  pytest                 tests on the demo data (the default), one at a time
  pytest -n auto         the same in parallel (pytest-xdist): a worker per CPU the job
                         may use, at most 8 (pytest_xdist_auto_num_workers); -n 4: four
  pytest tests/cm1       one package's tests (tests/core: the core's)
  pytest -m real         checks on your own run: ATMO3D_TEST_RUN=/path/to/run (slow)
                         (WoFS: ATMO3D_WOFS_ROOT; radar: ATMO3D_RADAR_ROOT)
  pytest -m browser      the viewer in headless Firefox, with screenshots (slow)
  pytest --make-baselines   rewrite the PNGs in tests/baseline (core/test_images.py)

The demo data is written once to $ATMO3D_TEST_DATA (default: <tmp>/atmo3d-demo-$USER)
and rewritten only when tests/synthetic.py changes.  (atmo3d --demo opens a real
run instead, demo_data/: cm1/test_real_demo.py.)
"""
import glob
import os
import re
import sys
import tempfile
import time

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
# the packages are imported from source (a pip install -e of each also registers their data
# types: the "atmo3d.datatypes" entry points)
for _src in sorted(glob.glob(os.path.join(os.path.dirname(HERE), "packages", "*", "src"))):
    sys.path.insert(0, _src)


def pytest_addoption(parser):
    parser.addoption("--make-baselines", action="store_true",
                     help="rewrite the baseline images of test_images.py")


@pytest.hookimpl(optionalhook=True)
def pytest_xdist_auto_num_workers(config):
    """pytest -n auto: one worker per CPU this job may use, at most 8 (each worker builds
    its own viewers; past that the gain is small).  The CPUs: those the process is
    allowed (a PBS or Slurm job's cpuset, taskset), else the machine's count; on a laptop
    of 4 cores, 4; on 1 CPU, 1 (as fast as without -n).  (Not PBS's NCPUS, nor nproc:
    they follow the threads per process, OMP_NUM_THREADS, often 1 in a job of 4 CPUs.)"""
    n = len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None
    return max(1, min(n or os.cpu_count() or 1, 8))


def pytest_configure(config):
    from importlib.metadata import entry_points
    if len(entry_points(group="atmo3d.datatypes")) < 2:
        pytest.exit("atmo3d's data-type packages are not installed; once, run:\n"
                    "  pip install --no-deps --no-build-isolation -e packages/core "
                    "-e packages/cm1 -e packages/wofs -e packages/radar", returncode=3)
    # before atmo3d.config is imported anywhere; spawned readers inherit these
    cfg = tempfile.mkdtemp(prefix="atmo3d-testcfg-")
    os.environ["ATMO3D_CONFIG"] = os.path.join(cfg, "config.toml")
    os.environ["ATMO3D_CACHE_DIR"] = os.path.join(cfg, "cache")
    os.environ["ATMO3D_ALLOW_WRITES_TO_OUTPUT"] = "1"
    # runs written by tests are opened at once: no file counts as still being written
    # for being new (test_running.py sets its own)
    os.environ["ATMO3D_SETTLE_SECONDS"] = "0"


def pytest_sessionfinish(session, exitstatus):
    # the reader processes stop with the tests (left to the interpreter's exit, the pool's
    # cleanup runs after its modules are gone: "'NoneType' object has no attribute 'util'")
    pool = sys.modules.get("atmo3d.core.pool")
    if pool is not None:
        pool.close()


@pytest.fixture(scope="session")
def demo_root():
    import synthetic as demo
    root = os.environ.get("ATMO3D_TEST_DATA") or os.path.join(
        tempfile.gettempdir(), f"atmo3d-demo-{os.environ.get('USER', 'user')}")
    demo.make(root)
    return root


@pytest.fixture(scope="session")
def demo_run(demo_root):
    return os.path.join(demo_root, "demo", "supercell")


@pytest.fixture(scope="session")
def reg(demo_run):
    from atmo3d.registry import Registry
    r = Registry(demo_run, 4, 2)
    yield r


@pytest.fixture
def viewer(reg):
    """A fresh Viewer on the demo supercell, at the first storm time."""
    from atmo3d.viewer import app as A
    run, F = reg.get()
    v = A.Viewer(run, F, reg=reg)
    v.main()
    v.tslider.value = 1
    yield v
    v.close()


def wait(pred, tmax=60, msg="condition"):
    """Poll pred() until true; fail the test after tmax seconds."""
    t0 = time.time()
    while not pred():
        if time.time() - t0 > tmax:
            raise AssertionError(f"timed out after {tmax}s waiting for {msg}")
        time.sleep(0.02)
    return time.time() - t0


def txt(html):
    return re.sub("<[^>]+>", "", html or "")


def tap(v, x, y, shift=False):
    v._on_tap(type("E", (), {"x": x, "y": y, "modifiers": {"shift": shift}})())


# ------------------------------------------------------------------ figure workspace
# A new Viewer takes most of a second (Bokeh's plots of every pane), and the figure tests
# use only its figure editor: so a test file's figure tests share one Viewer, and each
# test gets a new editor on it (fresh_editor): its figure, undo, dialogs and the figure's
# data and caches are new, as with a new Viewer.  A test that changes the Viewer itself
# (the map, the 3D camera, soundings) takes `viewer` instead.
def _module_viewer(reg):
    from atmo3d.viewer import app as A
    run, F = reg.get()
    v = A.Viewer(run, F, reg=reg)
    v.main()
    v._t_new = v.tslider.value  # (the time a new Viewer is at)
    return v


@pytest.fixture(scope="module")
def figure_viewer(reg):
    """The Viewer of a test file's `ed` tests."""
    v = _module_viewer(reg)
    yield v
    v.close()


class RunNow:
    """A pool that runs what is submitted to it at once (a figure drawn as it is asked)."""

    def submit(self, fn, *a):
        fn(*a)

    def shutdown(self, *a, **k):
        pass


@pytest.fixture(scope="module")
def shell_viewer(reg):
    """The Viewer of a test file's figure-shell tests: it draws as it is asked, not in the
    background.  (Apart from figure_viewer, so an `ed` test keeps the background.)"""
    v = _module_viewer(reg)
    v._schedule = lambda f: f()
    v.pools["fig"].shutdown(wait=False)
    v.pools["fig"] = RunNow()
    yield v
    v.close()


def fresh_editor(v, t=None):
    """A new figure editor on viewer v, at time index t (None: where a new Viewer is)."""
    from atmo3d.figures import editor
    from atmo3d.viewer.ui import out_of_flow
    old = v.figed
    # (as with a new Viewer: the editor is made at the Viewer's first time, and then the
    # slider moves; an editor made at t would start its figures there)
    v.tslider.value = v._t_new
    v.pools["figser"].shutdown(wait=False)  # (the new editor makes its own)
    v.figed = new = editor.FigureEditor(v)
    _old_start(new)
    v.fig_ws.objects = [out_of_flow(new.quick) if o is old.quick
                        else new.shell.panel if o is old.shell.panel else o
                        for o in v.fig_ws.objects]
    if t is not None:
        v.tslider.value = t
    return new


def _old_start(ed):
    """The tests are written on the figures the editor made before new figures started empty
    (docs-dev/figures-ui-plan.md, Phase 3): the page's figure a 2 x 3 grid in time of
    reflectivity with w contours, and a New dialog's plan view or section with a fill chosen
    drawing the w contours and (off) vectors too.  test_figure_blank.py checks the real start."""
    from atmo3d.figures import spec as fg
    ed.shell.start(ed._default())
    made = ed._quick_spec

    def quick_spec():
        s = made()
        if s["kind"] in ("plan", "xsec") and s["layers"]:
            s["layers"] = s["layers"][:1] + fg.default_spec(ed.run, ed.F, ed.v.t)["layers"][1:]
        return s
    ed._quick_spec = quick_spec


def fresh_shell(v, t=None):
    """A new editor's figure shell on viewer v, opened (the Figure workspace shown)."""
    ed = fresh_editor(v, t)
    ed.shell.open()
    return ed.shell


def at_tool(sh, tool, node=None):
    """The figure frame with its `tool` open at `node` (None: what is picked), every fold of
    its drawer open (lists, then their sections: made as they open)."""
    import panel as pn
    fr = sh.frame
    if fr.tool != tool:
        fr.open_tool(tool)
    if node is not None and node != sh.node:
        sh.select(node)
    elif fr.tool is not None:
        fr.show(sh.node)
    for _ in range(4):
        shut = [c for c in fr.body.select(pn.Card) if c.collapsed]
        if not shut:
            break
        for c in shut:
            c.collapsed = False
    return fr


def every_node(doc):
    """Every place of figure document doc an edit can be made at, in reading order: the figure,
    the runs, then each kind, its panels, their layers and insets."""
    from atmo3d.figures import draw as figdraw
    from atmo3d.figures.shell import nodes
    panels = nodes.in_order(doc)
    out = [nodes.FIGURE, nodes.RUNS]
    for kind in dict.fromkeys(p["kind"] for p in panels):
        out.append(nodes.KIND_PREFIX + kind)
        for p in (p for p in panels if p["kind"] == kind):
            out.append(f"panel:{p['id']}")
            out += [f"layer:{p['id']}:{j}" for j in range(len(figdraw.panel_layers(doc, p)))]
            out += [f"inset:{p['id']}:{ins['id']}" for ins in p.get("insets") or []]
    return out


def control(sh, name, tool=None, node=None, n=0):
    """The n-th widget called `name` in the frame's drawer (tool at node: at_tool's first)."""
    if tool is not None:
        at_tool(sh, tool, node)
    got = [w for w in sh.frame.body.select()
           if getattr(w, "name", None) == name and hasattr(w, "value")]
    if len(got) <= n:
        raise AssertionError(f"no {name} in {sh.frame.tool} at {sh.node}")
    return got[n]


def row_ctl(sh, row_id, where=None):
    """The control of schema row row_id in the frame's drawers (at where, if given; its
    section opened), and its ↺ button."""
    for d in sh.frame.drawers:
        if where is not None and d.where != where:
            continue
        for sec in d.sections:
            if row_id in {r.id for r in sec.rows}:
                sec.card.collapsed = False
                return sec.ctls[row_id], sec.lines[row_id][1]
    raise AssertionError(f"no row {row_id} in {sh.frame.tool} at {sh.node}")


def drawer_text(sh):
    """Every hint and heading the frame's drawer shows, in one string."""
    import panel as pn
    return " ".join(str(o.object or "") for o in sh.frame.body.select(pn.pane.HTML))


def press(sh, name, n=0):
    """Click the n-th button called `name` in the frame's drawer."""
    import panel as pn
    got = [b for b in sh.frame.body.select(pn.widgets.Button) if b.name == name]
    if len(got) <= n:
        raise AssertionError(f"no button {name} in {sh.frame.tool} at {sh.node}")
    got[n].clicks += 1


@pytest.fixture(scope="module")
def _two_plans_kept():
    return {}


@pytest.fixture
def two_plans(shell_viewer, _two_plans_kept):
    """fresh_shell at the 5th time, with a figure of two plan views side by side: the quick
    dialog's plan, and a panel added in a new column.  The first test of a file makes it;
    the others get a copy, with the same undo steps (making it again: ~1.5 s a test)."""
    import json
    v, kept = shell_viewer, _two_plans_kept
    sh = fresh_shell(v, min(4, len(v.run.times) - 1))
    ed = sh.ed
    ed.qs_kind.value = "plan"
    if kept:
        ed.quick.hide()
        sh._take(json.loads(kept["doc"]), render=False, fit=False)
        sh._hist, sh._base, sh._kept = list(kept["hist"]), kept["base"], None
        sh._show(kept["node"])
        return sh
    ed.open_quick()
    ed._quick_make()
    sh.grid.add_panel("plan", "new column")
    kept.update(doc=json.dumps(sh.doc, default=float), hist=list(sh._hist), base=sh._base,
                node=sh.node)
    return sh


@pytest.fixture
def ed(figure_viewer):
    e = fresh_editor(figure_viewer, 1)
    e.shell.auto.value = False  # renders only when a test asks
    return e


def doc_now(ed):
    """A copy of the figure the editor holds, as a file has it."""
    from atmo3d.figures import spec as fg
    return fg.plain_copy(ed.shell.doc)


def new_spec(ed, kind="plan", rows=2, cols=3, vary="times"):
    """The version-1 spec the New dialog starts a figure of a kind from (time series and
    time-height: with two series, as nothing is computed without one)."""
    from atmo3d.figures import spec as fg
    from atmo3d.figures.kinds import KINDS
    ed.open_quick()
    ed.quick.hide()
    ed.qs_kind.value = kind
    ed.qs_vary.value = vary
    ed.qs_rows.value, ed.qs_cols.value = rows, cols
    s = ed._quick_spec()
    if kind in ("th", "line"):
        s["series"] = [dict(fg.series_defaults(ed.F, ed._new_recipe(), n),
                            panel=n if kind == "th" else 0) for n in range(2)]
        if kind == "th":
            s.update(rows=2, cols=1)
    size = KINDS[kind].size
    if size:
        s["size"] = [round(min(16.0, float(v)), 2) for v in size(s["rows"], s["cols"])]
    return fg.plain_copy(ed.shell.new_form(s))


def set_look(ed, kind, block, **values):
    """Settings of a kind's look changed in the figure the editor holds, as its card does."""
    ed.shell.edit(lambda d: d["kinds"][kind][block].update(values))


def put(s, key, value):
    """Spec s with setting `key` (a schema row's key, without look.: "axes.xstep") as if typed
    in its control."""
    from atmo3d.figures import schema as S
    r = S.row_for("look." + key) or S.row(key)
    block, name = r.block
    held = s.setdefault(block, {}) if block else s
    if r.packed:
        held.update(r.as_.read(value))
    else:
        held[name] = r.as_.read(value)
    return s


def render(ed, figure=None):
    """Draw a figure (default: the one the editor holds) as the preview does (raises on errors):
    (the figure, its data, the matplotlib figure)."""
    from atmo3d.figures import draw as figdraw
    figure = doc_now(ed) if figure is None else figure
    data = ed.panel_data(figure)
    return figure, data, figdraw.draw(figure, data)


def settled(ed, figure):
    """What the figure's series need, computed."""
    ed.panel_data(figure)
    wait(lambda: not ed.series_pending(), 120, "the series")
    return figure


@pytest.fixture(scope="module")
def coarse_run(demo_root, tmp_path_factory):
    """The demo supercell with every other output (600 s apart, from 3600 s): a run
    whose output times differ from the viewer's."""
    import os
    main = os.path.join(demo_root, "demo", "supercell")
    d = tmp_path_factory.mktemp("coarse") / "supercell_coarse"
    d.mkdir()
    for f in ["namelist.input"] + [f"cm1out_{n:06d}.nc" for n in (2, 4, 6, 8, 10)]:
        os.symlink(os.path.join(main, f), d / f)
    return str(d)


def difference_layer(ed, s):
    """Spec s's first fill as a difference: minus the run's first output, diverging about 0."""
    from atmo3d.figures.choices import _nice
    lay = next(x for x in s["layers"] if x["type"] == "fill")
    a = _nice(0.25 * (float(lay["vmax"]) - float(lay["vmin"])))
    lay.update(minus=dict(run=None, time_s=float(ed.run.times[0]), grid="ask"), cmap="RdBu",
               reverse=True, white_first=False, vmin=-a, vmax=a, scale="linear", mask_below=None)
    return s


def swath_layer(ed, s):
    """Spec s's first fill as a swath: its maximum from the run's first output to each panel's
    time."""
    lay = next(x for x in s["layers"] if x["type"] == "fill")
    lay["reduce"] = dict(op="max", t0=float(ed.run.times[0]), t1=None, every=1)
    return s


def edited_v1():
    """A version 1 plan spec of two runs with per-panel edits."""
    fill = dict(type="fill", on=True, field="dbz", mode="height", z=1.0, cmap="viridis",
                vmin=0.0, vmax=60.0, extend="neither")
    cont = dict(type="contour", on=True, field="w", mode="height", z=3.0, levels="5")
    edits = {"1": dict(run=1, time_s=900.0, z=2.0, title="B",
                       layers={"0": dict(cmap="magma", run=0, time_s=60.0)},
                       extra=[cont])}
    return dict(version=1, kind="plan", rows=1, cols=3, vary="time",
                times_s=[0.0, 300.0, 600.0], run=0, layers=[fill], titles=["A"],
                runs=[dict(path="/a"), dict(path="/b")], size=[9, 3], edits=edits)


def spy_parts(monkeypatch, trajcalc):
    """Record the boxes the winds are read in and the parcels traced again (left a
    box) while trajcalc.trace runs."""
    boxes, redone = [], []
    real_w, real_adv = trajcalc._Winds, trajcalc._advance

    class Spy(real_w):
        def __init__(self, run, t, box=None):
            boxes.append(box)
            super().__init__(run, t, box)

    def adv(*a):
        r = real_adv(*a)
        redone.append(int(r[3].sum()))
        return r

    monkeypatch.setattr(trajcalc, "_Winds", Spy)
    monkeypatch.setattr(trajcalc, "_advance", adv)
    return boxes, redone
