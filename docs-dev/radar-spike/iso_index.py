"""Native 3D isosurface without PyVista: marching cubes in (sweep, ray, gate) index
space, vertices placed by the beam model (the pattern terrain runs already use)."""
import sys, time, resource
import numpy as np
from scipy.ndimage import map_coordinates
from skimage.measure import marching_cubes
import sampler as S

vol = S.Volume.from_cfradial(sys.argv[1], "reflectivity")
t0 = time.perf_counter()
a = np.concatenate([vol.data, vol.data[:, :1]], axis=1)          # close the circle
az = np.concatenate([vol.az, vol.az[:, :1] + 360.0], axis=1)
a = np.where(np.isfinite(a), a, -40.0).astype(np.float32)
verts, faces, _, _ = marching_cubes(a, level=40.0)
k, j, i = verts.T
e = np.interp(k, np.arange(vol.elev.size), vol.elev)
azv = map_coordinates(az, np.stack([k, j]), order=1)
h, s = S.beam_height(vol.r0 + i * vol.dr, e)
x, y = s * np.sin(np.radians(azv)), s * np.cos(np.radians(azv))
dt = time.perf_counter() - t0
print(f"index-space marching cubes + placement: {dt:.2f} s, {len(faces)} triangles, "
      f"peak RSS {resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024:.0f} MB; "
      f"z range {h.min():.1f}-{h.max():.1f} km")
