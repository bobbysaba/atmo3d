"""How a data-type package adds to the viewer: mixins that take the place of the no-op ones.

The Viewer is built from mixins (one per panel).  The shared code calls a few methods of
panels that only some data types bring (parcels); here are no-op versions of them, and a
data-type package registers its own mixin with register_mixin().  Those come before the
no-ops in the class the app builds (viewer_class()), so a registered method wins:

    from atmo3d.viewer import ext
    ext.register_mixin(ParcelsPanel)

A panel's tool and button are registered separately (viewer.panels.register).
"""

_MIXINS = []
_CLASS = None


class NoParcels:
    """What the shared viewer calls of the parcels panel: nothing, with no parcels."""

    def _build_parcels(self):
        pass

    def _par_saved_options(self):
        pass

    def _par_redraw(self):
        pass

    def _par_choose(self, x=None, y=None, box=None):
        pass

    def _par_drop(self, name):
        pass

    def _par_3d_traces(self, fig):
        pass

    def _par_state(self):
        return None

    def _put_parcels(self, pr, put):
        pass

    def _ext_modals(self):
        """Dialogs a data-type package's mixin puts on the page (out of the flow, like
        the viewer's own): none here."""
        return ()


def register_mixin(cls):
    """Add a class to the Viewer's bases, ahead of the no-op mixins."""
    global _CLASS
    if cls not in _MIXINS:
        _MIXINS.append(cls)
        _CLASS = None
    return cls


def viewer_class():
    """The Viewer class with every registered mixin (built on first use, once the data-type
    packages have registered)."""
    global _CLASS
    if _CLASS is None:
        from ..core import models
        models.load()
        from .app import BaseViewer
        _CLASS = type("Viewer", (*_MIXINS, BaseViewer), {})
    return _CLASS
