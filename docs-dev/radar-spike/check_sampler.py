"""Synthetic checks of sampler.py (analytic answers; light, runs anywhere)."""
import time
import numpy as np
import sampler as S

# a VCP-212-like volume: 14 sweeps x 720 rays x 1832 gates (250 m from 2.125 km)
elev = np.array([0.48, 0.88, 1.27, 1.8, 2.42, 3.08, 4.0, 5.1, 6.42, 8.0, 10.02, 12.48, 15.6, 19.51])
nr, ng = 720, 1832
az = np.tile(np.arange(nr) * 0.5 + 0.25, (elev.size, 1))
r = 2.125 + 0.25 * np.arange(ng)
H, Sg = S.beam_height(r[None, None, :], elev[:, None, None])

# 1) round trip: polar_of inverts beam_height
for e in (0.48, 5.1, 19.51):
    for rr in (10.0, 150.0, 459.875):
        h, s = S.beam_height(rr, e)
        a, ee, r2 = S.polar_of(s * np.sin(np.radians(30)), s * np.cos(np.radians(30)), h)
        assert abs(ee - e) < 1e-9 and abs(r2 - rr) < 1e-9 and abs(a - 30) < 1e-9, (e, rr, ee, r2)
print("round trip ok")

# 2) field = gate height: the sampler should return z wherever it is inside the sweeps
vol = S.Volume(elev, az, np.broadcast_to(H, (elev.size, nr, ng)).astype(np.float32).copy(), 2.125, 0.25)
x, y, z = np.random.default_rng(0).uniform([-300, -300, 0], [300, 300, 15], (200000, 3)).T
v = S.sample(vol, x, y, z, beam_extend=False)
ok = np.isfinite(v)
err = np.abs(v[ok] - z[ok])
print(f"height field: {ok.mean():.2f} of points inside sweeps, max |err| {err.max()*1000:.1f} m, mean {err.mean()*1000:.2f} m")
assert err.max() < 0.05

# 3) field = sin(az) * range: bilinear in az/range, linear in elevation -> small error
F = (np.sin(np.radians(az))[:, :, None] * r[None, None, :]).astype(np.float32)
vol2 = S.Volume(elev, az, F, 2.125, 0.25)
v2 = S.sample(vol2, x, y, z, beam_extend=False)
a, e, rr = S.polar_of(x, y, z)
exact = np.sin(np.radians(a)) * rr
ok2 = np.isfinite(v2)
rel = np.abs(v2[ok2] - exact[ok2]) / np.maximum(rr[ok2], 1)
print(f"sin(az)*r field: max rel err {rel.max():.2e}")
assert rel.max() < 1e-3

# 4) NaN rule: a wedge of NaN (no echo); points well inside it NaN, well outside finite
F3 = F.copy(); F3[:, 100:200, :] = np.nan  # azimuth 50-100 deg missing
vol3 = S.Volume(elev, az, F3, 2.125, 0.25)
v3 = S.sample(vol3, x, y, z, beam_extend=False)
inside = ok2 & (a > 51) & (a < 99); outside = ok2 & ((a < 49) | (a > 101))
assert np.isnan(v3[inside]).all() and np.isfinite(v3[outside]).all()
print("NaN rule ok")

# 5) gaps: max_gap_km masks where sweeps are far apart
vg = S.sample(vol, x, y, z, beam_extend=False, max_gap_km=1.0)
print(f"max_gap_km=1: {np.isfinite(vg).mean():.2f} of points kept (vs {ok.mean():.2f})")

# 6) speed on synthetic data (numba, after compile)
for n in (10_000, 1_000_000):
    xx, yy, zz = x[:n] if n <= x.size else np.resize(x, n), np.resize(y, n), np.resize(z, n)
    t0 = time.perf_counter(); S.sample(vol2, xx, yy, zz); dt = time.perf_counter() - t0
    print(f"{n:>9} points: {dt*1000:.1f} ms")
