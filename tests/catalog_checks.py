"""Checks of a data type's field table and catalog that each package's tests run on its
own (tests/cm1/test_cm1_outputs.py, tests/wofs/test_wofs_outputs.py)."""
from atmo3d.core import catalog as C
from atmo3d.core.fields import CMAPS, GROUP_ORDER


def table_well_formed(table):
    for name, e in table.items():
        assert len(e) == 7, name
        label, units, scale, cmap, vr, div, group = e
        assert label and not (label.isupper() and len(label) > 6), name  # (no raw WRF)
        assert cmap in CMAPS, (name, cmap)
        assert scale > 0, name
        assert vr is None or (len(vr) == 2 and vr[0] < vr[1]), name
        assert group in GROUP_ORDER, (name, group)
        assert " s-1" not in units and "m-2" not in units, (name, units)  # plain units


def base_state_looks_like_its_field(key):
    """A3: a base-state field shows in its full field's units, scale and colours."""
    cat = C.of_model(key)
    for full, base in (("theta", "theta0"), ("pres", "pres0"), ("qv", "qv0"),
                       ("u", "u0"), ("v", "v0")):
        f, b = cat.look(cat.name(full)), cat.look(cat.name(base))
        assert f[1:] == b[1:], (full, f, b)
        assert b[0].startswith("Base-state")
        assert cat.group(cat.name(base), 3) == "Base state"


def fake_fields(model, names):
    """Fields of a run of `model` whose files hold `names` (no files read)."""
    from atmo3d.core.fields import Fields
    from atmo3d.core.run import VarInfo

    class FakeRun:
        dx, dy, umove, vmove, storm_relative = 1000.0, 1000.0, 0.0, 0.0, True
        var_times = {}  # (pdecomp.register adds its fields here)

        def offers(self, name):
            return False

        def __init__(self):
            self.model = model
            self.vars = {n: VarInfo(n, n, "", 2 if n.isupper() and n not in
                                    ("U", "V", "W", "THETA", "PRES", "QVAPOR")
                                    else 3, None) for n in names}

        @property
        def catalog(self):
            return C.of_model(model).resolved(self.vars)

        def has(self, n):
            return n in self.vars

    return Fields(FakeRun())
