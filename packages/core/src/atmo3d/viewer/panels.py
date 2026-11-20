"""The viewer's analysis tools and their panels: a registry the layout is built from.

A tool is a button on the rail down the left of the map; it sets what a map click does
(its click mode) and, when it has one, opens its panel to the right of the map.  A data
type's package adds its own with register():

    from atmo3d.viewer import panels
    panels.register(panels.Tool(
        "PPI", "PPI", "radar", "Native radar sweeps", needs="native_polar",
        layout=lambda v: v._ppi_layout(), click=lambda v, x, y, shift: v._ppi_click(x, y)))

(atmo3d_radar's own; click: what a map click does while the tool is on, hint: the map's
hint then.)

The viewer (viewer.layout) asks for_run(run) for the tools a run gets, in registration
order.  A panel is built when the run's data type offers the tool's capability
(`needs`, core.capabilities.CAPS); its rail button shows when, beyond that, `shown(run)`
holds (default: run.can(needs), i.e. the run has the inputs too).

A panel's place in the registry (index()) is what a saved session records as its open
tab, so the built-in panels keep the order they had before the registry (0 Sounding to
5 Parcels, which the CM1 package registers before "3D region"); register new ones after them.
"""
from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass(frozen=True)
class Tool:
    key: str  # the click mode the button picks; also the panel's name
    label: str  # the button's label (short: the rail is 64 px wide)
    icon: str  # a Tabler icon name
    tip: str  # the button's tooltip
    # the panel's contents, made by the viewer: f(viewer) -> Panel viewable; None: a tool
    # with no panel (3D region)
    layout: Optional[Callable] = None
    title: str = ""  # the panel's heading ("" : key)
    # further click modes of this tool (e.g. "Area sounding"): they light its button and
    # open its panel
    modes: tuple = ()
    needs: Optional[str] = None  # a capability the data type must offer (None: any)
    # whether this run gets the rail button, f(run) -> bool (None: run.can(needs))
    shown: Optional[Callable] = field(default=None, compare=False)
    # what a map click does in this tool's modes, f(viewer, x, y, shift) (None: the
    # built-in tools, handled by viewer.events._on_tap)
    click: Optional[Callable] = field(default=None, compare=False)
    hint: str = ""  # the map's hint while the tool is on ("": the tooltip)

    @property
    def heading(self):
        return self.title or self.key

    def built(self, run):
        """Whether this run's viewer builds the tool's panel."""
        return self.needs is None or run.offers(self.needs)

    def on_rail(self, run):
        if not self.built(run):
            return False
        if self.shown is not None:
            return bool(self.shown(run))
        return self.needs is None or run.can(self.needs)


_TOOLS = []


def register(tool, before=None):
    """Add a tool (after those already registered, or before the one keyed `before`: the
    rail's order; the panels' order, which a saved session's tab number follows, is the
    same); a key registered again replaces the old entry in its place."""
    for i, t in enumerate(_TOOLS):
        if t.key == tool.key:
            _TOOLS[i] = tool
            return tool
    j = next((i for i, t in enumerate(_TOOLS) if t.key == before), len(_TOOLS))
    _TOOLS.insert(j, tool)
    return tool


def tools():
    return list(_TOOLS)


def get(key):
    return next((t for t in _TOOLS if t.key == key), None)


def for_run(run):
    """(panels, rail): the tools whose panels this run's viewer builds (in tab order),
    and the tools on its rail."""
    return ([t for t in _TOOLS if t.layout is not None and t.built(run)],
            [t for t in _TOOLS if t.on_rail(run)])


def tool_of(mode):
    """The tool (key) a click mode belongs to, or the mode itself (None stays None)."""
    for t in _TOOLS:
        if mode == t.key or mode in t.modes:
            return t.key
    return mode


def panel_of(mode):
    """The key of the panel a click mode opens, or None (no panel, or no mode)."""
    t = get(tool_of(mode)) if mode is not None else None
    return t.key if t is not None and t.layout is not None else None


def index(key):
    """A panel's place among the registered panels (a saved session's tab number)."""
    keys = [t.key for t in _TOOLS if t.layout is not None]
    return keys.index(key) if key in keys else None


def at(i):
    """The key of the panel registered at place i (a saved session's tab), or None."""
    keys = [t.key for t in _TOOLS if t.layout is not None]
    return keys[i] if 0 <= i < len(keys) else None


# ---- the built-in tools (their panels are the viewer's own mixins, viewer/*.py); those
# that sample a grid need one ("grid": a radar run gets them with its sampler, step 4)
def _builtins():
    register(Tool("Sounding", "Sounding", "balloon",
                  "Soundings: click the map (or drag a box for an area mean)",
                  layout=lambda v: v._snd_layout(), modes=("Area sounding",),
                  needs="soundings",
                  # (kept on the rail when a run lacks the inputs: the panel says so)
                  shown=lambda run: True))
    register(Tool("Cross-section", "Section", "slice",
                  "Vertical cross-section: click A, then B",
                  layout=lambda v: v._xs_layout(), needs="grid"))
    register(Tool("Track", "Track", "route",
                  "Storm track: click a storm to follow it through time",
                  layout=lambda v: v._trk_layout(), title="Storm track", needs="tracking"))
    register(Tool("Series", "Series", "chart-line", "Time series of a field over a region",
                  layout=lambda v: v._ser_layout(), title="Time series", needs="grid"))
    register(Tool("Distribution", "Distrib.", "chart-histogram",
                  "Distribution of a field over a region at one time: histogram, box, "
                  "violin, cumulative", layout=lambda v: v._dist_layout(), needs="grid"))
    register(Tool("3D region", "3D box", "cube", "Drag a box on the map to view it in 3D",
                  modes=("Seed box",), needs="grid"))


_builtins()
