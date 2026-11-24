"""Figure editor: what a 3D scene figure takes from the viewer (from_3d, its camera as the user left
it, its parcel sets), and the first isosurface, vectors and parcels a scene's Add gives.

A mixin of the FigureEditor (figures/editor.py)."""

from . import draw as figdraw, spec as fg
from ..core.services import parcels as P
from .choices import _dark
from .sources import parcel_pick

ISO_MAX = VEC_MAX = PAR_MAX = 6


def next_iso(F, isos):
    """A new isosurface after `isos`: reflectivity 30 dBZ first, then updraft 10 m/s, then the
    last one's field."""
    have = [(e.get("var"), e.get("val")) for e in isos]
    return next((dict(var=v, val=x, color=c, op=o) for v, x, c, o in (
        (F.role(r), x, c, o) for r, x, c, o in (
            ("refl", 30.0, "#7dd3fc", 0.25), ("w", 10.0, "#f97316", 0.85),
            ("w", -5.0, "#3b82f6", 0.7))) if v and (v, x) not in have),
        dict(var=have[-1][0] if have else None, val=0.0, color="#a3a3a3", op=0.5))


def next_vec(run, vecs):
    """A new plane of vectors after `vecs`."""
    lv = [float(e.get("level") or 0.0) for e in vecs]
    return dict(level=max(lv) + 1.0 if lv else 0.0,
                frame="grid" if (run.umove or run.vmove) else "ground",
                color=("#000000", "#b45309", "#0e7490")[len(lv) % 3])


class FigureScene:
    """What a 3D scene figure takes from the viewer."""

    def _build_scene(self):
        """Follow the 3D workspace's camera."""
        # the 3D workspace's camera as the user leaves it (plotly's relayout after a drag)
        self._cam3d = None
        v = self.v
        if hasattr(v, "plot3d"):
            v.plot3d.param.watch(self._on_3d_relayout, "relayout_data")
        if hasattr(v, "v3_cam"):  # (a preset picked there: the latest camera)
            v.v3_cam.param.watch(lambda e: setattr(self, "_cam3d", None), "value")

    def next_parcels(self, have, say):
        """A new parcel set of a scene holding the sets named `have`: the viewer's next one,
        else the run's first saved set (None: there is none; say(html, True) says so)."""
        e = next((e for e in self._scene_parcels() if e["name"] not in have), None)
        if e is not None:
            return e
        v = self.v
        saved = P.list_sets(v.run.path) if v.pf is not None else []
        if not saved:
            say("Choose parcels in the viewer's <b>Parcels</b> tab first (or save a set "
                "there).", True)
            return None
        src = parcel_pick(self, "f:" + saved[0])
        return None if src is None else dict(fg.layer_defaults("parcels", self.F), lw=1.5, **src)

    def _scene_parcels(self):
        """The viewer's parcel sets as entries of a scene (as its 2D layers, lines a
        little wider)."""
        return [dict(lay, lw=round(1.5 * float(self.v.par_width.value or 1.0), 3))
                for lay in self._parcel_layers()]

    def _on_3d_relayout(self, ev):
        d = ev.new or {}
        if isinstance(d.get("scene.camera"), dict):
            self._cam3d = d["scene.camera"]

    def _view_camera(self):
        """CAMERA keys of the 3D workspace's camera: as it was left after a drag, else
        its preset view."""
        v = self.v
        preset = v.v3_cam.value if hasattr(v, "v3_cam") else "oblique"
        cam = dict(figdraw.CAMERA, preset=preset)
        cam.update(figdraw.camera_from_plotly(self._cam3d))
        return cam

    def viewer_scene(self):
        """The scene block of what the 3D workspace shows (its box, top, exaggeration,
        smoothing, resolution, surfaces, floor, vectors, streamlines, parcel sets when
        it shows them, and camera); light vector colours chosen for its dark background
        turn black."""
        v = self.v
        try:
            box = [float(x) for x in v.box] if v.box is not None else None
            isos = [dict(on=bool(d["on"].value), var=d["var"].value,
                         val=float(d["val"].value or 0.0), color=d["color"].value,
                         op=float(d["op"].value)) for d in v.isos]
            vecs = [dict(on=bool(o["on"].value), q=o["q"].value, level=float(o["level"].value),
                         frame=o["frame"].value, density=int(o["density"].value),
                         ref=float(o["ref"].value or 0.0) or None,
                         color=_dark(o["color"].value)) for o in v.svs]
            sb = v._seed_in_box()
            stream = dict(on=bool(v.st_on.value), z=float(v.st_z.value), n=int(v.st_n.value),
                          length=float(v.st_len.value), dir=v.st_dir.value,
                          frame=v.st_frame.value, color_by=v.st_color.value,
                          seed_box=list(sb) if sb else None)
            ground = dict(on=bool(v.v3_ground.value), var=v.v3_floor.value,
                          z=float(v.v3_floor_z.value), cmap=v.v3_floor_cmap.value,
                          rev=bool(v.v3_floor_rev.value), range=v.v3_floor_range.value,
                          lo=float(v.v3_floor_min.value or 0.0),
                          hi=float(v.v3_floor_max.value or 0.0))
            sc = dict(box=box, ztop=float(v.v3_ztop.value), exag=float(v.v3_exag.value),
                      smooth=float(v.v3_smooth.value), res=int(v.v3_res.value), isos=isos,
                      vecs=vecs, stream=stream, ground=ground,
                      parcels=self._scene_parcels() if getattr(v, "par_3d", None) is not None
                      and v.par_3d.value else [])
        except AttributeError:  # (a viewer without the 3D workspace)
            sc = dict(isos=[dict(on=True, var=self.F.role("refl"), val=30.0,
                                 color="#7dd3fc", op=0.25)] if self.F.role("refl") else [])
        for e in sc.get("vecs", []):
            if e["ref"] is None:
                e.pop("ref")
        return fg.scene3d_of(dict(scene3d=dict(sc, camera=self._view_camera(), look={})))

    def from_3d(self):
        """A 3D scene figure of the 3D workspace (its box, settings and camera) at the
        shown time."""
        t = self.v.t
        s = self._keep_runs(fg.default_spec(self.run, self.F, t))
        self._times(s, [t], t)
        s.update(kind="scene", rows=1, cols=1, size=[6.5, 5.2], size_auto=False,
                 vary="time", scene3d=self.viewer_scene())
        s["axes"] = dict(s["axes"], xlabel="", ylabel="", ticklabels="all", equal=False)
        s["colorbar"] = dict(s["colorbar"], mode="none")
        s["letters"] = dict(s["letters"], on=False)
        self.shell.open_new(s)
