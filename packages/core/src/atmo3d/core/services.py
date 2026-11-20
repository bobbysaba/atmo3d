"""Tools that only some data types bring, reached from shared code without importing them.

The viewer, figures and exports call the pressure decomposition (`pdecomp`) and the parcel
tools (`parcels`) where a run offers them (core.capabilities).  They live in the data-type
package that has them (atmo3d_cm1); the package calls provide() when it registers, and the
shared code writes

    from ..core.services import parcels as P

and calls P.chosen(...) as if it were the module.  Where no package provides a service,
the calls that ask "is there any?" answer no (the NULL entries) and any other raises
ServiceMissing, so a data type without the tools never reaches them.
"""


class ServiceMissing(AttributeError):
    pass


# what a service answers when no data-type package provides it (the "is it there?" calls)
NULL = {
    "pdecomp": {"NAMES": (), "is_pdecomp": lambda F, name: False,
                "can_compute": lambda run: False, "writes_allowed": lambda: False,
                "register": lambda run: None, "running": lambda run, t: None,
                "script_name": lambda: "", "writable": lambda run, t: False},
    "parcels": {"offered": lambda run: False},
}

_IMPL = {}


def provide(name, impl):
    """Register `impl` (a module or any object) as the service `name`."""
    _IMPL[name] = impl
    return impl


class Service:
    """A stand-in for a module: attribute lookups go to whatever provide() registered."""

    def __init__(self, name):
        object.__setattr__(self, "_name", name)

    def __getattr__(self, attr):
        name = object.__getattribute__(self, "_name")
        if not _IMPL:
            from . import models
            models.load()  # (the data-type packages register their services)
        impl = _IMPL.get(name)
        if impl is not None:
            return getattr(impl, attr)
        try:
            return NULL.get(name, {})[attr]
        except KeyError:
            raise ServiceMissing(f"{name}.{attr}: no installed data type provides {name!r}"
                                 ) from None


pdecomp = Service("pdecomp")
parcels = Service("parcels")
trajcalc = Service("trajcalc")
