"""What a data type can do: named capabilities, declared by each data type's run class.

A data type says which features it offers with `Run.offers` (a frozenset of names from
CAPS).  `run.can(name)` is the question the viewer and figures ask: the data type
offers it AND this run has what it needs (its fields, its files).  `run.offers(name)`
asks only the first half: a feature a data type offers stays on screen when one run
lacks its inputs, so the panel can say what is missing.

Five capabilities are flags on the run, kept as attributes because they also say *how*
(a Geo object, terrain-following heights): `terrain`, `geo`, `storm_relative`,
`traced_parcels`, `grid`.  For those, offers() and can() read the flag.
"""

# name -> what it means (shown nowhere yet; the reference for data-type authors)
CAPS = {
    "soundings": "Skew-T soundings and their parameters (needs the sounding roles: "
                 "theta, pres, qv, u, v)",
    "parcels": "parcel trajectories: from parcel output files, or traced (traced_parcels)",
    "traced_parcels": "flag: the data type writes no parcel output; trajectories are "
                      "traced through the 3D winds",
    "pdecomp": "pressure decomposition (CM1's method; needs its input fields)",
    "tracking": "storm tracking (needs w)",
    "storm_relative": "flag: storm-relative winds and the fields that take the storm "
                      "motion",
    "terrain": "flag: levels follow the terrain (heights vary in space and time)",
    "geo": "flag: the grid sits on a map projection (run.geo)",
    "native_polar": "a native polar (PPI) view of single sweeps (radar: PolarRun)",
    "grid": "flag: a regular grid (core.run.Run).  The views that sample one (cross-"
            "sections, time series, distributions, 3D) need it until the data type "
            "brings a sampler (radar: Phase 6 step 4)",
}

FLAGS = ("terrain", "geo", "storm_relative", "traced_parcels", "grid")


def _flag(run, name):
    v = getattr(run, name, None)
    return v is not None if name == "geo" else bool(v)


def offers(run, name):
    """Whether run's data type offers capability `name` (a CAPS key)."""
    if name not in CAPS:
        raise KeyError(f"unknown capability {name!r} (see core.capabilities.CAPS)")
    if name in FLAGS:
        return _flag(run, name)
    return name in getattr(run, "OFFERS", ())


def can(run, name):
    """Whether run's data type offers `name` and this run has what it needs."""
    if not offers(run, name):
        return False
    test = _NEEDS.get(name)
    return test is None or bool(test(run))


def of(run):
    """The capabilities this run can use (a frozenset of CAPS keys)."""
    return frozenset(n for n in CAPS if can(run, n))


def _soundings(run):
    names = run.catalog.sounding_names()
    return names is not None and all(run.has(n) for n in names)


def _parcels(run):
    from .services import parcels
    return parcels.offered(run)


def _pdecomp(run):
    from .services import pdecomp
    return pdecomp.can_compute(run)


def _tracking(run):
    from . import track
    return track.available(run)


_NEEDS = {"soundings": _soundings, "parcels": _parcels, "pdecomp": _pdecomp,
          "tracking": _tracking}
