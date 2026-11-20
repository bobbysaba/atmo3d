"""The radar field catalog (core.catalog): CfRadial field names as the files have them.

From the Phase 6 variable audit (docs-dev/radar-audit.md, "Decisions", 2026-11-19).
Rows marked "stopgap" wait on the data providers (docs-dev/radar-questions.md): the
bistatic QC fields show their raw values, and the retrieved w is shown as the file
gives it.  Fields no entry names (another radar's moments, e.g. KDP) are listed from
the file's own long name and units (core.catalog.tidy).
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
    # the receiver network's fields
    "bistatic_velocity_nwc": ("Bistatic velocity", "m/s", 1.0, "RdBu_r", (-30, 30), True,
                              BISTATIC),
    "bistatic_velocity_unsmoothed_nwc": ("Bistatic velocity (unsmoothed)", "m/s", 1.0,
                                         "RdBu_r", (-30, 30), True, BISTATIC),
    "original_bistatic_velocity_nwc": ("Bistatic velocity (original)", "m/s", 1.0,
                                       "RdBu_r", (-30, 30), True, BISTATIC),
    "beta_nwc": ("Bistatic angle β", "°", 1.0, "viridis", (0, 180), False, BISTATIC),
    # retrievals (w: stopgap, as the file gives it)
    "u": ("Retrieved u (east)", "m/s", 1.0, "RdBu_r", (-30, 30), True, WINDS),
    "v": ("Retrieved v (north)", "m/s", 1.0, "RdBu_r", (-30, 30), True, WINDS),
    "w": ("Retrieved w", "m/s", 1.0, "RdBu_r", (-20, 20), True, WINDS),
    "w_direct": ("Retrieved w (direct)", "m/s", 1.0, "RdBu_r", (-20, 20), True, WINDS),
    "doppler_degree": ("Doppler degree (radars)", "", 1.0, "viridis", None, False, WINDS),
    # bistatic QC (stopgap: raw values, data limits, meanings not guessed)
    "beta_cutoff_nwc": ("beta_cutoff_nwc", "", 1.0, "viridis", None, False, QC),
    "receiver_bistatic_velocity_mask_nwc": ("receiver_bistatic_velocity_mask_nwc", "", 1.0,
                                            "viridis", None, False, QC),
    "receiver_qc_reason_flag_nwc": ("receiver_qc_reason_flag_nwc", "", 1.0, "viridis",
                                    None, False, QC),
    "receiver_ncp_nwc": ("receiver_ncp_nwc", "", 1.0, "viridis", None, False, QC),
    "receiver_rcp_nwc": ("receiver_rcp_nwc", "", 1.0, "viridis", None, False, QC),
    # gate geometry from the beam model (atmo3d_radar.run.GEOMETRY; not in the files)
    "beam_height": ("Beam height (above the radar)", "km", 1.0, "cividis", (0, 20), False,
                    GEOMETRY),
    "ground_range": ("Ground range", "km", 1.0, "cividis", None, False, GEOMETRY),
    "ray_azimuth": ("Ray azimuth", "°", 1.0, "cividis", (0, 360), False, GEOMETRY),
}

ROLES = {"refl": "reflectivity", "u": "u", "v": "v", "w": "w"}

OTHER = ("differential_phase", "clutter_filter_power_removed",
         "bistatic_velocity_unsmoothed_nwc", "original_bistatic_velocity_nwc", "beta_nwc")
OTHER_GROUPS = (QC,)

HIDDEN = ("w_direct", "doppler_degree", "beam_height", "ground_range", "ray_azimuth")

CATALOG = register(Catalog("radar", NATIVES, ROLES, other=OTHER, other_groups=OTHER_GROUPS,
                           hidden=HIDDEN))
