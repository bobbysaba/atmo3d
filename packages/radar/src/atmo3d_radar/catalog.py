"""The radar field catalog (core.catalog): CfRadial field names as the files have them.

From the Phase 6 variable audit (docs-dev/radar-audit.md, "Decisions", 2026-11-19).
Rows marked "stopgap" wait on the data providers (docs-dev/radar-questions.md): the
bistatic QC fields show their raw values, and the retrieved w is shown as the file
gives it.  Receiver fields (a bistatic quantity plus the receiver's site as a suffix)
are described by rule, for any number of receivers (receiver_field).  Fields no entry
names (another radar's moments, e.g. KDP) are listed from the file's own long name and
units (core.catalog.tidy).
"""
from atmo3d.core.catalog import Catalog, register

MOMENTS, BISTATIC, WINDS, QC, GEOMETRY = (
    "Moments", "Bistatic", "Retrieved winds", "Bistatic QC", "Geometry")

# {name: (label, units, scale, cmap, vrange, diverging, group)}
NATIVES = {
    # the radar's own fields
    "reflectivity": ("Reflectivity", "dBZ", 1.0, "reflectivity", (0, 75), False, MOMENTS),
    "velocity": ("Radial velocity", "m/s", 1.0, "RdBu_r", (-30, 30), True, MOMENTS),
    "differential_reflectivity": ("ZDR", "dB", 1.0, "turbo", (-2, 6), False, MOMENTS),
    "cross_correlation_ratio": ("ρhv", "", 1.0, "turbo", (0.7, 1.0), False, MOMENTS),
    "spectrum_width": ("Spectrum width", "m/s", 1.0, "magma", (0, 10), False, MOMENTS),
    "differential_phase": ("ΦDP", "°", 1.0, "turbo", (0, 360), False, MOMENTS),
    "clutter_filter_power_removed": ("Clutter filter power removed", "dB", 1.0, "magma",
                                     (0, 40), False, MOMENTS),
    # retrievals (w: stopgap, as the file gives it)
    "u": ("Retrieved u (east)", "m/s", 1.0, "RdBu_r", (-30, 30), True, WINDS),
    "v": ("Retrieved v (north)", "m/s", 1.0, "RdBu_r", (-30, 30), True, WINDS),
    "w": ("Retrieved w", "m/s", 1.0, "RdBu_r", (-20, 20), True, WINDS),
    "w_direct": ("Retrieved w (direct)", "m/s", 1.0, "RdBu_r", (-20, 20), True, WINDS),
    "doppler_degree": ("Doppler degree (radars)", "", 1.0, "viridis", None, False, WINDS),
    # gate geometry from the beam model (atmo3d_radar.run.GEOMETRY; not in the files)
    "beam_height": ("Beam height (above the radar)", "km", 1.0, "cividis", (0, 20), False,
                    GEOMETRY),
    "ground_range": ("Ground range", "km", 1.0, "cividis", None, False, GEOMETRY),
    "ray_azimuth": ("Ray azimuth", "°", 1.0, "cividis", (0, 360), False, GEOMETRY),
}

ROLES = {"refl": "reflectivity", "u": "u", "v": "v", "w": "w"}

OTHER = ("differential_phase", "clutter_filter_power_removed")
OTHER_GROUPS = (QC,)

# The receiver network's fields are the bistatic quantity's name plus the receiver's
# site as a suffix (bistatic_velocity_nwc, beta_nwc): one set per receiver, however
# many the files have.  {base: (label, units, cmap, vrange, diverging, group, other)};
# the QC fields keep their raw names as labels (stopgap, as above).
RECEIVER_BASES = {
    "bistatic_velocity": ("Bistatic velocity", "m/s", "RdBu_r", (-30, 30), True, BISTATIC,
                          False),
    "bistatic_velocity_unsmoothed": ("Bistatic velocity (unsmoothed)", "m/s", "RdBu_r",
                                     (-30, 30), True, BISTATIC, True),
    "original_bistatic_velocity": ("Bistatic velocity (original)", "m/s", "RdBu_r",
                                   (-30, 30), True, BISTATIC, True),
    "beta": ("Bistatic angle β", "°", "viridis", (0, 180), False, BISTATIC, True),
    "beta_cutoff": (None, "", "viridis", None, False, QC, True),
    "receiver_bistatic_velocity_mask": (None, "", "viridis", None, False, QC, True),
    "receiver_qc_reason_flag": (None, "", "viridis", None, False, QC, True),
    "receiver_ncp": (None, "", "viridis", None, False, QC, True),
    "receiver_rcp": (None, "", "viridis", None, False, QC, True),
}
_BASES_LONGEST_FIRST = sorted(RECEIVER_BASES, key=len, reverse=True)


def receiver_field(name):
    """(base, receiver) of a receiver network field name ("beta_nwc": ("beta", "nwc")),
    or None for any other field."""
    for base in _BASES_LONGEST_FIRST:  # (beta_cutoff before beta)
        if name.startswith(base + "_") and len(name) > len(base) + 1:
            return base, name[len(base) + 1:]
    return None


def describe(name):
    """A natives entry for a receiver network field of any receiver, else None."""
    got = receiver_field(name)
    if got is None:
        return None
    base, rx = got
    label, units, cmap, vrange, div, group, _ = RECEIVER_BASES[base]
    return (name if label is None else f"{label} ({rx.upper()})", units, 1.0, cmap, vrange,
            div, group)


def _other(name):
    got = receiver_field(name)
    return got is not None and RECEIVER_BASES[got[0]][6]

HIDDEN = ("w_direct", "doppler_degree", "beam_height", "ground_range", "ray_azimuth")

CATALOG = register(Catalog("radar", NATIVES, ROLES, other=OTHER, other_groups=OTHER_GROUPS,
                           hidden=HIDDEN, describe=describe, other_match=_other))
