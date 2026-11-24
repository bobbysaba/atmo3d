"""The extension API's version rule and the conformance check of a data type
(atmo3d.testing.check_datatype): it lists the problems of one that breaks the contract.
(That it passes on each data type in this repo: tests/<type>/test_<type>_contract.py.)"""
import os
import types

import pytest

import atmo3d
from atmo3d.core import models
from atmo3d.core.models import Model
from atmo3d.testing import CheckFailed, check_datatype


# ------------------------------------------------------------------ the API version
@pytest.mark.parametrize("wanted, have, ok", [
    ("1.0", "1.0", True), ("1.0", "1.3", True), ("1.2", "1.3", True),
    ("1.4", "1.3", False),  # (needs what a newer core added)
    ("2.0", "1.3", False), ("1.0", "2.0", False),  # (another major)
])
def test_api_compatible(wanted, have, ok):
    assert models.api_compatible(wanted, have) is ok


def test_in_repo_data_types_declare_this_api():
    for key in ("cm1", "wofs", "radar"):
        if key in models.MODELS:
            assert models.MODELS[key].api == atmo3d.API_VERSION


class Toy(Model):
    key, label = "toy", "Toy"

    def count(self, path):
        return len([f for f in os.listdir(path) if f.endswith(".toy")])

    def looks(self, entries):
        return any(e.name.endswith(".toy") for e in entries)


@pytest.fixture
def toy_registered():
    yield
    dict.pop(models.MODELS, "toy", None)


@pytest.mark.parametrize("api", ["2.0", "1.99", "one"])
def test_register_refuses_another_api(api, toy_registered):
    m = Toy()
    m.api = api
    with pytest.raises(models.APIMismatch):
        models.register(m)
    assert "toy" not in models.MODELS


def test_load_leaves_out_a_package_of_another_api(monkeypatch, toy_registered):
    def register():
        m = Toy()
        m.api = "9.0"
        models.register(m)
    ep = types.SimpleNamespace(name="toy", load=lambda: register)
    import importlib.metadata as md
    monkeypatch.setattr(md, "entry_points", lambda group: [ep])
    monkeypatch.setattr(models, "_LOADED", False)
    monkeypatch.setattr(models, "SKIPPED", {})
    with pytest.warns(UserWarning, match="not loaded"):
        models.load()
    assert "toy" not in models.MODELS and "9.0" in models.SKIPPED["toy"]


# ------------------------------------------------------------------ the check
def test_check_lists_every_problem(tmp_path, toy_registered):
    (tmp_path / "a.toy").write_text("x", encoding="utf-8")

    class Broken:  # (the run class: opening fails)
        def __init__(self, path, **kw):
            raise OSError("cannot read a.toy")

    m = Toy()
    m.run_class = Broken
    models.register(m)  # (no api: accepted by register, a problem for the check)
    with pytest.raises(CheckFailed) as e:
        check_datatype("toy", str(tmp_path))
    msg = str(e.value)
    assert "Model.api is not set" in msg and "cannot read a.toy" in msg
    assert len(e.value.report.problems) == 2


def test_check_an_unregistered_key(tmp_path):
    with pytest.raises(CheckFailed, match="not registered"):
        check_datatype("nope", str(tmp_path))
