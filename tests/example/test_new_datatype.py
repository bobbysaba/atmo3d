"""tools/new_datatype.py, the scaffold: the package it writes (in a copy of this
repository, and out of tree) is the example renamed, and passes the contract check as it
is; it refuses names in use and leaves nothing of the example's names behind."""
import importlib
import os
import shutil
import subprocess
import sys
import tomllib

import pytest

from atmo3d.core import catalog, models
from atmo3d.testing import check_datatype

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "tools"))
import new_datatype as ND  # noqa: E402


@pytest.fixture
def fake_repo(tmp_path):
    """The parts of the repository the scaffold reads and writes."""
    root = tmp_path / "repo"
    shutil.copytree(os.path.join(REPO, "packages", "example"), root / "packages" / "example",
                    ignore=shutil.ignore_patterns("__pycache__", "*.egg-info"))
    (root / "tests").mkdir()
    (root / ".github").mkdir()
    shutil.copy(os.path.join(REPO, ".github", "CODEOWNERS"), root / ".github" / "CODEOWNERS")
    return root


@pytest.fixture
def load_package():
    """Import a written package from its src/ and register it; undone afterwards."""
    done = []

    def load(src, name):
        sys.path.insert(0, src)
        mod = importlib.import_module(f"atmo3d_{name}")
        models.MODELS.get("cm1")  # (the installed ones first)
        mod.register()
        done.append((src, name))
        return mod

    yield load
    for src, name in done:
        sys.path.remove(src)
        dict.pop(models.MODELS, name, None)
        catalog.CATALOGS.pop(name, None)
        for m in [m for m in sys.modules if m == f"atmo3d_{name}"
                  or m.startswith(f"atmo3d_{name}.")]:
            del sys.modules[m]


def test_in_repo(fake_repo, load_package, tmp_path, capsys):
    dest = ND.main(["toyna", "--label", "Toy NA"], root=str(fake_repo))
    assert dest == str(fake_repo / "packages" / "toyna")
    out = capsys.readouterr().out
    assert "tests.yml" in out and "environment.yml" in out
    assert "still name the example" not in out
    # the entry point, the names, the test's folder, the CODEOWNERS line
    with open(os.path.join(dest, "pyproject.toml"), "rb") as f:
        meta = tomllib.load(f)
    assert meta["project"]["name"] == "atmo3d-toyna"
    assert meta["project"]["authors"] == [{"name": "<your name>"}]
    assert meta["project"]["entry-points"][models.GROUP] == {"toyna": "atmo3d_toyna:register"}
    assert os.listdir(fake_repo / "tests" / "toyna") == ["test_toyna.py"]
    assert "pytest tests/toyna " in out and "'tests/toyna/**'" in out
    assert "# /packages/toyna/" in (fake_repo / ".github" / "CODEOWNERS").read_text(encoding="utf-8")
    assert not ND.leftovers(dest)
    # it is the example, renamed: it passes the contract on its synthetic run
    mod = load_package(os.path.join(dest, "src"), "toyna")
    m = models.MODELS["toyna"]
    assert type(m).__name__ == "Toyna" and m.label == "Toy NA"
    from atmo3d_toyna import synthetic
    synthetic.write(str(tmp_path / "run"))
    rep = check_datatype("toyna", str(tmp_path / "run"))
    assert "ToynaRun" in " ".join(rep.notes) and mod.__doc__.startswith("atmo3d data type")


def test_written_test_passes(fake_repo, tmp_path):
    """The test file it writes runs (on the package from source, unregistered)."""
    ND.main(["toyrun"], root=str(fake_repo))
    test = fake_repo / "tests" / "toyrun" / "test_toyrun.py"
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(
        [str(fake_repo / "packages" / "toyrun" / "src")]
        + [os.path.join(REPO, "packages", p, "src") for p in ("core", "cm1", "wofs", "radar")]))
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                        "-m", "not real", str(test)], cwd=tmp_path, env=env,
                       capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "1 passed" in r.stdout


def test_out_of_tree(fake_repo, tmp_path):
    out = tmp_path / "mine"
    before = (fake_repo / ".github" / "CODEOWNERS").read_text(encoding="utf-8")
    dest = ND.main(["toyout", "--out", str(out)], root=str(fake_repo))
    assert dest == str(out / "atmo3d-toyout")
    assert os.path.isfile(os.path.join(dest, "tests", "test_toyout.py"))
    with open(os.path.join(dest, "pyproject.toml"), "rb") as f:
        meta = tomllib.load(f)
    assert "real" in meta["tool"]["pytest"]["ini_options"]["markers"][0]
    # nothing in the repository changed
    assert (fake_repo / ".github" / "CODEOWNERS").read_text(encoding="utf-8") == before
    assert sorted(os.listdir(fake_repo / "tests")) == []
    assert sorted(os.listdir(fake_repo / "packages")) == ["example"]


@pytest.mark.parametrize("name", ["cm1", "example", "Bad", "9lives", "a", "x-y", "end_"])
def test_refuses_names(fake_repo, name):
    with pytest.raises(SystemExit):
        ND.main([name], root=str(fake_repo))
    assert sorted(os.listdir(fake_repo / "packages")) == ["example"]


def test_refuses_an_existing_package(fake_repo):
    ND.main(["twice"], root=str(fake_repo))
    with pytest.raises(SystemExit, match="exists"):
        ND.main(["twice"], root=str(fake_repo))
