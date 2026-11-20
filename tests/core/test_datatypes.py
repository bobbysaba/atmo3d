"""Data types plug into the core through the registry, with no core edits: the entry-point
group is read, a Model registered on the spot is found like any other, and no core module
imports a data-type package."""
import glob
import os
import re

from atmo3d.core import models
from atmo3d.core.models import Model

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
CORE = os.path.join(REPO, "packages", "core", "src", "atmo3d")


def test_installed_data_types_register_through_entry_points():
    from importlib.metadata import entry_points
    names = {e.name for e in entry_points(group=models.GROUP)}
    assert {"cm1", "wofs"} <= names
    assert {"cm1", "wofs"} <= set(models.MODELS)


def test_core_imports_no_data_type_package():
    pat = re.compile(r"^\s*(from|import)\s+atmo3d_(?!\w*\s*#\s*noqa)\w+", re.M)
    bad = []
    for f in glob.glob(os.path.join(CORE, "**", "*.py"), recursive=True):
        with open(f) as fh:
            if pat.search(fh.read()):
                bad.append(os.path.relpath(f, CORE))
    assert not bad, bad


class Toy(Model):
    key, label = "toy", "Toy"

    def count(self, path):
        return len([f for f in os.listdir(path) if f.endswith(".toy")])

    def looks(self, entries):
        return any(e.name.endswith(".toy") for e in entries)


def test_a_model_registered_without_core_edits_is_detected(tmp_path):
    (tmp_path / "a.toy").write_text("x")
    try:
        models.register(Toy())
        assert "toy" in models.choices().values()
        assert models.detect(str(tmp_path)).key == "toy"
        assert models.count(str(tmp_path)) == 1
        assert models.looks_like_run(list(os.scandir(tmp_path)), "toy")
    finally:
        dict.pop(models.MODELS, "toy", None)
