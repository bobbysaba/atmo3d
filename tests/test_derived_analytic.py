"""Derived fields against analytic answers (Phase 2b step 3; docs-dev/derived-fields.md):
each field's function on synthetic inputs whose answer is known, its inputs given by the
data type's own names (as Fields binds them).  Derivative inputs ("ddx.uinterp") are
given directly; hgrad and hgrad_level are tested on their own."""
import numpy as np
import pytest

from atmo3d.core import catalog as C
from atmo3d.core import fields as FF
from atmo3d.core import thermo

G = 9.81
EPS = 287.04 / 461.5
CM1 = ("uinterp", "vinterp", "winterp", "xvort", "yvort", "zvort", "th", "prs", "qv",
       "th0", "prs0", "qv0", "u0", "v0", "qc", "qr", "qi", "qs", "qg", "qhl", "qh",
       "u10", "v10")


def defs(model="cm1", avail=CM1):
    cat = C.of_model(model)
    return {d.name: d for d in FF._make_fields(set(avail), cat)}, cat


D, CAT = defs()


def ctx(**kw):
    return dict(dict(dx=1000.0, dy=1000.0, umove=0.0, vmove=0.0, kappa=CAT.kappa, f=0.0),
                **kw)


def call(name, values, c=None, d=D):
    """Field `name` with inputs `values` ({native or derivative name: value}); an input
    not given is 0."""
    shape = np.broadcast_shapes(*(np.shape(v) for v in values.values())) or ()

    def f(n):
        return np.asarray(values.get(n, np.zeros(shape)), np.float64)
    return np.asarray(d[name].func(f, c or ctx()))


def test_perturbations():
    assert call("thpert", {"th": 302.0, "th0": 300.0}) == pytest.approx(2.0)
    assert call("prspert", {"prs": 1e5 + 150.0, "prs0": 1e5}) == pytest.approx(1.5)


def test_buoyancy_is_cm1s():
    """g [θ′/θ0 + (Rv/Rd − 1) qv′ − Σ q_cond], every condensate CM1 loads (qh too)."""
    base = {"th": 303.0, "th0": 300.0}
    assert call("buoy", base) == pytest.approx(G * 0.01)
    assert call("buoy", {"th": 300.0, "th0": 300.0, "qv": 0.011, "qv0": 0.001}) == \
        pytest.approx(G * (461.5 / 287.04 - 1.0) * 0.01)
    for q in ("qc", "qr", "qi", "qs", "qg", "qhl", "qh"):
        assert call("buoy", {"th": 300.0, "th0": 300.0, q: 1e-3}) == \
            pytest.approx(-G * 1e-3), q
    assert "qh" in D["buoy"].deps and "qh" in D["thrho"].deps


def test_baroclinic_generation_is_the_curl_of_b():
    """B = c x (θ = θ0 (1 + c x / g)): ∂B/∂x = c, so bgen_y = −10⁴ c, bgen_x = 0;
    qv's derivative comes in g/kg per m (its display units) and counts as kg/kg."""
    c = 2e-6
    v = {"th": 300.0, "th0": 300.0, "ddx.th": 300.0 * c / G}
    assert call("bgen_y", v) == pytest.approx(-1e4 * c)
    assert call("bgen_x", v) == pytest.approx(0.0)
    q = {"th": 300.0, "th0": 300.0, "ddy.qv": 1000.0 * 1e-6}  # (1e-6 kg/kg per m)
    assert call("bgen_x", q) == pytest.approx(1e4 * G * (461.5 / 287.04 - 1.0) * 1e-6)
    assert call("bgen_x", {"th": 300.0, "th0": 300.0, "ddy.qc": 1000.0 * 1e-6}) == \
        pytest.approx(-1e4 * G * 1e-6)


def test_density_potential_temperature():
    assert call("thrho", {"th": 300.0}) == pytest.approx(300.0)
    assert call("thrho", {"th": 300.0, "qv": 0.01}) == \
        pytest.approx(300.0 * (1 + 0.01 / EPS) / 1.01)


def test_temperature_dewpoint_rh_thetae():
    assert call("tempc", {"th": 300.0, "prs": 1e5}) == pytest.approx(26.85)
    assert call("tempc", {"th": 300.0, "prs": 5e4}) == \
        pytest.approx(300.0 * 0.5 ** (287.04 / 1005.7) - 273.15)
    # (WoFS: WRF's κ = 2/7)
    w = ctx(kappa=C.of_model("wofs").kappa)
    assert call("tempc", {"th": 300.0, "prs": 5e4}, w) == \
        pytest.approx(300.0 * 0.5 ** (2 / 7) - 273.15)
    q = EPS * 611.2 / (1e5 - 611.2)  # e = 611.2 Pa: dewpoint 0 °C
    assert call("dewc", {"prs": 1e5, "qv": q}) == pytest.approx(0.0, abs=1e-6)
    T = 300.0
    qs = EPS * thermo.esat(T) / (1e5 - thermo.esat(T))
    assert call("rh", {"th": T, "prs": 1e5, "qv": qs}) == pytest.approx(100.0)
    # θe of dry air is θ; a supersaturated point uses Td = T (one copy: thermo.theta_e)
    assert call("thetae", {"th": 300.0, "prs": 8e4, "qv": 0.0}) == pytest.approx(300.0, abs=0.1)
    a = call("thetae", {"th": 300.0, "prs": 1e5, "qv": 2 * qs})
    assert a == pytest.approx(thermo.theta_e(1e5, 300.0, 2 * qs))


def test_wind_speed_divergence_vorticity():
    assert call("wspd3d", {"uinterp": 3.0, "vinterp": 4.0}) == pytest.approx(5.0)
    assert call("wspd3d", {"uinterp": 3.0, "vinterp": 0.0}, ctx(vmove=4.0)) == \
        pytest.approx(5.0)
    assert call("hdiv", {"ddx.uinterp": 1e-3, "ddy.vinterp": 2e-3}) == pytest.approx(3.0)
    assert call("hvort", {"xvort": 3.0, "yvort": 4.0}) == pytest.approx(5.0)


def test_streamwise_crosswise():
    c = ctx(storm=(0.0, 0.0))
    w = {"uinterp": 10.0, "vinterp": 0.0}
    assert call("wstream", {**w, "yvort": 0.01}, c) == pytest.approx(0.0)
    assert call("wcross", {**w, "yvort": 0.01}, c) == pytest.approx(0.01)
    assert call("wstream", {**w, "xvort": 0.01}, c) == pytest.approx(0.01)
    assert call("wcross", {**w, "xvort": 0.01}, c) == pytest.approx(0.0)


def test_cloud_and_precipitation():
    assert call("qcloud", {"qc": 0.001, "qi": 0.002}) == pytest.approx(3.0)
    assert call("qprecip", {"qr": 0.001, "qs": 0.001, "qg": 0.001, "qhl": 0.001}) == \
        pytest.approx(4.0)


def test_vorticity_tendencies():
    """Stretching −(ζ + f) ∇h·V; tilting ξ ∂w/∂x + η ∂w/∂y; Okubo–Weiss signs."""
    v = {"zvort": 0.01, "ddx.uinterp": -0.001, "ddy.vinterp": -0.001}
    assert call("zstretch", v) == pytest.approx(1e4 * 0.01 * 0.002)
    assert call("zstretch", v, ctx(f=1e-4)) == pytest.approx(1e4 * 0.0101 * 0.002)
    assert call("ztilt", {"xvort": 0.01, "ddx.winterp": 0.001}) == pytest.approx(0.1)
    assert call("ztend", {**v, "xvort": 0.01, "ddx.winterp": 0.001}) == \
        pytest.approx(0.2 + 0.1)
    assert D["ztend"].note.startswith("Not the full ζ tendency")
    om, a = 0.01, 0.003
    rot = {"ddx.vinterp": om, "ddy.uinterp": -om}  # u = −Ω y, v = Ω x
    assert call("okubo", rot) == pytest.approx(-1e4 * (2 * om) ** 2)
    strain = {"ddx.uinterp": a, "ddy.vinterp": -a}  # u = a x, v = −a y
    assert call("okubo", strain) == pytest.approx(1e4 * (2 * a) ** 2)


def test_wofs_vorticity_and_f_from_its_fields():
    """WoFS: ζ is REL_VORT; ξ, η come from the winds; f is its F field."""
    d, cat = defs("wofs", ("U", "V", "W", "REL_VORT", "F", "THETA", "PRES", "QVAPOR"))
    assert cat.name("zvort") == "REL_VORT"
    assert call("xvort", {"ddy.W": 0.003, "ddz.V": 0.001}, d=d) == pytest.approx(0.002)
    assert call("yvort", {"ddz.U": 0.003, "ddx.W": 0.001}, d=d) == pytest.approx(0.002)
    assert call("hvort", {"ddy.W": 0.003, "ddz.U": 0.004}, d=d) == pytest.approx(0.005)
    v = {"REL_VORT": 0.01, "F": 1e-4, "ddx.U": -0.001, "ddy.V": -0.001}
    assert call("zstretch", v, d=d) == pytest.approx(1e4 * 0.0101 * 0.002)
    assert "F" in d["zstretch"].deps


def test_updraft_helicity_counts_cyclonic_updrafts_only():
    zk = np.array([2.5, 3.5, 4.5])
    c = ctx(dz=np.array([1000.0, 1000.0, 1000.0]), zk=zk, top=5.0)
    one = np.ones((3, 2, 2))
    assert np.allclose(call("uh25", {"winterp": 10 * one, "zvort": 0.01 * one}, c), 300.0)
    assert np.allclose(call("uh25", {"winterp": -10 * one, "zvort": 0.01 * one}, c), 0.0)
    assert np.allclose(call("uh25", {"winterp": 10 * one, "zvort": -0.01 * one}, c), 0.0)
    # a data type whose files have UH (the uh25 role): no derived uh25, uh01 still
    d, _ = defs("cm1", CM1 + ("uh",))
    assert "uh25" not in d and "uh01" in d
    assert "zvmax01" not in D and "wmax" not in D


def test_shear_starts_at_10_m_when_there():
    """u = 0.005 z (m): 0–6 km shear from the 10 m wind is 0.005 (6000 − 10)."""
    zk = np.array([0.05, 1.0, 3.0, 6.0, 7.0])
    u = (0.005 * 1000 * zk)[:, None, None] * np.ones((1, 2, 2))
    c = ctx(zk=zk, top=6.0, dz=np.ones(5))
    vals = {"uinterp": u, "vinterp": 0 * u, "u10": np.full((1, 2, 2), 0.05),
            "v10": np.zeros((1, 2, 2))}
    assert np.allclose(call("shear06", vals, c), 0.005 * (6000.0 - 10.0))
    d, _ = defs("cm1", tuple(n for n in CM1 if n not in ("u10", "v10")))
    assert np.allclose(call("shear06", vals, c, d), 0.005 * (6000.0 - 50.0))


def test_helicity_of_a_circular_hodograph():
    """Wind turning clockwise on a circle of radius R around the storm motion: SRH is
    R² times the angle turned (to the discretization)."""
    R, n = 10.0, 400
    ang = np.linspace(0.0, -np.pi / 2, n)  # (clockwise)
    zk = np.linspace(0.0, 1.0, n)
    u, v = R * np.cos(ang), R * np.sin(ang)
    got = FF.helicity(u, v, zk, 1.0, (0.0, 0.0))
    assert got == pytest.approx(R * R * np.pi / 2, rel=1e-4)


def test_cape_subtracts_negative_pockets():
    """B 0.1 to 1 km, −0.05 to 1.5 km, 0.1 to 3 km (LCL at the ground): CAPE is the net
    area, 100 − 25 + 150 = 225 J/kg (MetPy's way), in both the sounding's and the maps'
    integration."""
    z = np.arange(0.0, 3000.0, 10.0)
    B = np.where(z < 1000, 0.1, np.where(z < 1500, -0.05, 0.1))
    cape = thermo._integrate_buoyancy(z, B, 0.0)[0]
    assert cape == pytest.approx(225.0, abs=2.0)


def test_hgrad_exact_on_a_stretched_grid():
    x = np.cumsum(np.r_[0.0, np.linspace(0.5, 2.0, 20)])  # km, stretched
    y = np.cumsum(np.r_[0.0, np.linspace(1.0, 0.3, 15)])
    a = 2 * x[None, :] + 3 * y[:, None]
    assert np.allclose(FF.hgrad("ddx", a, x, y), 0.002)
    assert np.allclose(FF.hgrad("ddy", a, x, y), 0.003)
    assert np.allclose(FF.hgrad("gradh", a, x, y), np.hypot(0.002, 0.003))


def test_hgrad_level_at_constant_height():
    """On tilted levels, a field that varies only with height has no horizontal
    derivative at constant height; one that varies only with x keeps its own."""
    x, y = np.linspace(0, 20, 21), np.linspace(0, 10, 11)
    hgt = 0.05 * x[None, :] + 0.0 * y[:, None]  # (km: a 50 m/km slope)
    zl = np.array([0.1, 0.5, 1.0, 2.0])
    Z = zl[:, None, None] + hgt[None]  # (km above sea level)
    a = 300.0 + 4.0 * Z  # (K, 4 K/km)
    dadz = FF.ddz_volume(a, Z)
    assert np.allclose(FF.hgrad_level("ddx", a, Z, x, y, dadz), 0.0, atol=1e-9)  # (float32)
    b = 0.002 * 1000 * x[None, None, :] * np.ones_like(Z)  # (0.002 per m in x only)
    db = FF.ddz_volume(b, Z)
    assert np.allclose(FF.hgrad_level("ddx", b, Z, x, y, db), 0.002)


# ---- step 4: the confirmed flag

def _every_derived():
    """Names of every derived field _make_fields can give, for CM1 and WoFS: with every
    role present, and without the files' ξ, η and 2–5 km UH (so the derived ones show)."""
    names = set()
    for model in ("cm1", "wofs"):
        cat = C.of_model(model)
        full = {cat.name(r) for r in C.ROLES} - {None}
        full |= set(getattr(cat, "condensate", ())) | {"p_l", "p_nl", "p_c", "acc_b",
                                                        "acc_l", "acc_nl", "acc_c"}
        bare = full - {cat.name(r) for r in ("xvort", "yvort", "uh25")}
        for avail in (full, bare):
            names |= {d.name for d in FF._make_fields(avail, cat)}
    return names


def test_confirmed_matches_the_fields():
    """CONFIRMED names only fields that exist, and (the audit being done) every derived
    field is in it: a new one is caught here until it is reviewed."""
    every = _every_derived()
    assert FF.CONFIRMED - every == set()
    assert every - FF.CONFIRMED == set()
    d, _ = defs()
    assert all(x.confirmed and x.tier == "main" for x in d.values())


def test_unconfirmed_is_hidden_and_marked(monkeypatch):
    monkeypatch.setattr(FF, "CONFIRMED", FF.CONFIRMED - {"thetae"})
    d, _ = defs()
    te = d["thetae"]
    assert not te.confirmed and te.tier == "hidden" and te.label.endswith(FF.UNVERIFIED)
    assert d["tempc"].confirmed and d["tempc"].tier == "main"
    dd = FF.deriv_def("ddx", te)  # (a derivative of it is unconfirmed too)
    assert not dd.confirmed
    # still computable (saved figures, the series worker): only its listing changes
    th, p, qv = 300.0, 85000.0, 0.012
    assert np.isfinite(call("thetae", {"th": th, "prs": p, "qv": qv}, d=d))


# ---- step 5: the derived-field docs page agrees with the code

def test_docs_page_lists_every_field_and_note():
    """docs/guide/derived-fields.md names every confirmed field, and holds each field's
    note (FieldDef.note) word for word."""
    from pathlib import Path
    page = (Path(__file__).resolve().parents[1] / "docs" / "guide"
            / "derived-fields.md").read_text()
    assert [n for n in sorted(FF.CONFIRMED) if f"`{n}`" not in page] == []
    notes = set()
    for model in ("cm1", "wofs"):
        cat = C.of_model(model)
        full = {cat.name(r) for r in C.ROLES} - {None}
        full |= {"p_l", "p_nl", "p_c", "acc_b", "acc_l", "acc_nl", "acc_c"}
        for avail in (full, full - {cat.name(r) for r in ("xvort", "yvort", "uh25")}):
            notes |= {d.note for d in FF._make_fields(avail, cat) if d.note}
    assert [n for n in sorted(notes) if n not in page] == []
