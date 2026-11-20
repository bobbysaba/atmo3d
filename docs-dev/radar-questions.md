# Questions for the bistatic radar data providers

For Bobby's meeting with the people producing
`combined_radar_object_advcor_<n>_<YYYYMMDD_HHMMSS>.nc` (KTLX, 2026-04-04 01:06–03:00
UTC, 19 files). Each question says why we ask and what we saw in the files. Answers go
back into `radar-audit.md` (the open rows) and the radar reader.

## Most important

1. **Where are the receivers?** We need each receiver's latitude, longitude and
   height to draw the bistatic geometry. We didn't find them in the files.
   - How many receivers are in this dataset? The files have one β field and
     `doppler_degree` is never above 2, so it looks like KTLX plus one receiver.
   - Could the locations go in the file in future, for example as global attributes?
2. **How is `w` computed?**
   - Is it from continuity, integrated upward or downward? What is the boundary
     condition?
   - Its values reach ±75 m/s. Are values like that expected, or noise we should
     filter?
   - It is missing entirely in the first file (01:06). Why?
   - `w_direct` is 0 at every gate in all 19 files. Is it unused, or is that a bug?
3. **What do the QC fields mean?**
   - `receiver_qc_reason_flag_nwc`: we see the values 0, 2, 4, 5, 7, 9, 12, 13, 16,
     17 and 18. Is it a bit field? What does each bit (1, 2, 4, 8, 16) mean? 4 is by far
     the most common value.
   - `receiver_bistatic_velocity_mask_nwc`: does 1 mean "masked out" and 0 "kept"?
   - `beta_cutoff_nwc`: is it 0 where β is between 30° and 150°, i.e. usable? Is the
     30–150° window fixed?
4. **Should the viewer apply any masks to `u` and `v`, or are they ready to use as they
   are?** We ask because in one file (02:21), of the 421 k gates with a retrieved `u`:
   - 79 k have receiver mask = 1;
   - 80 k have a nonzero QC flag;
   - 21 k have `beta_cutoff` = 1.

## Field meanings and units

5. `receiver_ncp_nwc`: what does NCP stand for here? It goes up to 20, but a normalized
   coherent power is normally at most 1.
6. `receiver_rcp_nwc`: what is RCP, and what are its units (dB?)?
7. `original_bistatic_velocity_nwc`: is this the bistatic velocity before QC, before
   dealiasing, or something else? It has no units attribute; we assume m/s.
8. Bistatic velocity comes in three versions (smoothed, unsmoothed, original). What
   smoothing is used, and which one should people look at?
9. `u` and `v`: are they true east and north? At what height are they valid: each
   gate's beam height?
10. Has `velocity` (KTLX radial velocity) been dealiased by you, or is it as delivered
    in Level II? Its values go past the 8–33 m/s Nyquist velocity.
11. What does the `_nwc` suffix stand for?

## Time and advection correction

12. What does `advcor` in the file names mean? Which fields are advection-corrected:
    all of them, or only the retrievals? To what reference time, and with what storm
    motion?
13. We use the time in the file name as the volume's time. The first ray is about 17 s
    later, and the volume takes about 6 minutes. Is the file-name time the right
    reference?

## File layout (to make sure the reader is right)

14. The `time` dimension has extra rays beyond the sweep table (11160 or 12600 rays, but
    the sweeps cover 10080), with masked angles. Is it safe to always ignore rays outside
    `sweep_start_ray_index` to `sweep_end_ray_index`?
15. The last file (02:59) has 13 sweeps, missing 19.5°. Is that expected, for example a
    volume cut short?

## What people want to see

16. Which fields matter most to them in a viewer? Should anything we put under "Other"
    be up front?
17. Do they want any derived fields? For example composite reflectivity, echo tops,
    KDP, azimuthal shear, storm-relative velocity, or vorticity and divergence from the
    retrieved winds (which we would compute on a regridded grid).
18. Will future datasets have more receivers (`doppler_degree` > 2), other radars than
    KTLX, or a different file layout? We'd like the reader to handle them.
19. Is there a reference (paper, report, README) describing the processing that we could
    cite or link to?
