"""Characterization of the capability flags and gates per data type (CM1 demo run, synthetic
WoFS run): docs-dev/hardcoded-names.md, "Model gates", sections A and B.

Phase 3 replaces the data-type tests with capability checks; these tests pin what each
type has now, so that the replacement changes nothing for CM1 and WoFS."""
import os

import pytest

from atmo3d import pdecomp
from atmo3d.core import parcels
from atmo3d.registry import Registry
from test_wofs import make_wofs


@pytest.fixture(scope="module")
def wofs_run(tmp_path_factory):
    root = make_wofs(str(tmp_path_factory.mktemp("exp") / "exp" / "20220523"))
    return Registry(os.path.dirname(root), 4, 2).get()[0]


def test_cm1_flags(reg):
    run = reg.get()[0]
    assert run.model == "cm1" and run.model_label == "CM1"
    assert run.terrain is False and run.traced_parcels is False
    assert run.storm_relative is True and run.geo is None


def test_wofs_flags(wofs_run):
    run = wofs_run
    assert run.model == "wofs" and run.model_label == "WoFS"
    assert run.terrain is True and run.traced_parcels is True
    assert run.storm_relative is False and run.geo is not None


def test_pressure_decomposition_is_cm1_only(wofs_run):
    assert pdecomp.can_compute(wofs_run) is False


def test_parcels_offered_where_traced(wofs_run):
    assert parcels.offered(wofs_run) is True  # traced through the winds


def test_parcels_of_the_cm1_demo_come_from_files(reg):
    run = reg.get()[0]
    assert parcels.offered(run) == bool(parcels.find_files(run.path))


def test_members_only_for_wofs(reg, wofs_run):
    from atmo3d.core import models
    assert models.parts(reg.get()[0].path) == []
    assert len(models.parts(os.path.dirname(os.path.dirname(wofs_run.path)))) >= 1 \
        or models.root_of(wofs_run.path) != wofs_run.path


def test_model_registry_keys():
    from atmo3d.core import models
    assert {"cm1", "wofs"} <= set(models.MODELS)
