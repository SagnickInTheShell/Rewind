"""Builds :class:`OverlayFrame` payloads for the video overlay from a run's artefacts.

All artefacts are loaded once per run and indexed by processed-frame time, so a lookup is a few
array slices (well under 100 ms).
"""

from __future__ import annotations

import threading
from bisect import bisect_left
from collections import OrderedDict

import numpy as np
import pandas as pd

from rewind.calibration.homography import venue_homography, world_to_pixel
from rewind.perception.fusion import blend_weight
from rewind.schemas.perception import OverlayArrow, OverlayFrame, OverlayTrack, OverlayZone
from rewind.schemas.run import RunMeta
from rewind.schemas.venue import Venue
from rewind.settings import Settings
from rewind.storage.run_store import RunStore


class OverlayIndex:
    def __init__(self, store: RunStore, run_id: str, settings: Settings) -> None:
        self.s = settings
        meta: RunMeta = store.load_meta(run_id)
        self.venue = Venue.model_validate_json(store.path(run_id, "venue.json").read_text(encoding="utf-8"))
        from rewind.ingest.video_reader import processed_size

        self.w, self.h, scale = processed_size(meta.video.width, meta.video.height, settings.video.max_width)
        _, H_inv = venue_homography(self.venue, scale)
        self.zone_px = {z.zone_id: [(float(x), float(y)) for x, y in world_to_pixel(
            np.array([[p.x, p.y] for p in z.polygon]), H_inv)] for z in self.venue.zones}

        boxes = store.read_df(run_id, "track_boxes") if store.exists(run_id, "track_boxes") else pd.DataFrame(
            columns=["t", "track_id", "x1", "y1", "x2", "y2", "conf"])
        self.box_groups = {round(float(t), 4): g for t, g in boxes.groupby("t")}  # type: ignore[arg-type]
        tracks = store.read_df(run_id, "tracks") if store.exists(run_id, "tracks") else pd.DataFrame(
            columns=["track_id", "t", "px_x", "px_y"])
        self.tracks = tracks.sort_values("t") if not tracks.empty else tracks
        self.track_t = self.tracks["t"].to_numpy() if not tracks.empty else np.zeros(0)

        self.times = np.array(sorted(self.box_groups)) if self.box_groups else np.zeros(0)
        self.heat_t = np.zeros(0)
        self.heat = np.zeros((0, 1, 1), np.float16)
        if store.exists(run_id, "heat"):
            with np.load(store.path(run_id, "heat")) as z:
                self.heat_t, self.heat = z["t"], z["heat"]
            if len(self.heat_t) > len(self.times):
                self.times = self.heat_t
        self.arrow_t = np.zeros(0)
        self.arrow_off = np.zeros(1, np.int64)
        self.arrow_data = np.zeros((0, 4), np.float32)
        if store.exists(run_id, "arrows"):
            with np.load(store.path(run_id, "arrows")) as z:
                self.arrow_t, self.arrow_off, self.arrow_data = z["t"], z["offsets"], z["data"]

        # zone density/count per time: prefer fused features, else raw density stage
        self.zone_vals: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray, list[str]]] = {}
        if store.exists(run_id, "features"):
            f = store.read_df(run_id, "features")
            for z, g in f.groupby("zone_id"):
                g = g.sort_values("t")
                # sparse/dense follows the hybrid blend weight of the observed density, not the feature source
                p = settings.perception
                modes = ["sparse" if blend_weight(d, p.hybrid_switch_density, p.hybrid_blend_band) < 0.5 else "dense"
                         for d in g["density"]]
                self.zone_vals[str(z)] = (g["t"].to_numpy(), g["density"].to_numpy(), g["count"].to_numpy(), modes)
        elif store.exists(run_id, "density_zone"):
            d = store.read_df(run_id, "density_zone")
            p = settings.perception
            for z, g in d.groupby("zone_id"):
                g = g.sort_values("t")
                area = g["area_m2"].to_numpy()
                rho_map = g["count_map"].to_numpy() / np.maximum(area, 1e-6)
                w = np.array([blend_weight(r, p.hybrid_switch_density, p.hybrid_blend_band) for r in rho_map])
                count = (1 - w) * g["count_det"].to_numpy() + w * g["count_map"].to_numpy()
                modes = ["sparse" if wi < 0.5 else "dense" for wi in w]
                self.zone_vals[str(z)] = (g["t"].to_numpy(), count / np.maximum(area, 1e-6), count, modes)
        self.zone_state: dict[str, tuple[np.ndarray, list[str]]] = {}
        if store.exists(run_id, "risk"):
            r = store.read_df(run_id, "risk")
            for z, g in r.groupby("zone_id"):
                g = g.sort_values("t")
                self.zone_state[str(z)] = (g["t"].to_numpy(), list(g["state"]))

    @staticmethod
    def _nearest(times: np.ndarray, t: float) -> int | None:
        if len(times) == 0:
            return None
        i = bisect_left(times.tolist(), t)
        if i == 0:
            return 0
        if i >= len(times):
            return len(times) - 1
        return i if abs(times[i] - t) < abs(times[i - 1] - t) else i - 1

    @staticmethod
    def _at_or_before(times: np.ndarray, t: float) -> int | None:
        if len(times) == 0:
            return None
        i = int(np.searchsorted(times, t + 1e-6, side="right")) - 1
        return max(i, 0)

    def frame(self, t: float, with_heatmap: bool = True) -> OverlayFrame:
        ti = self._nearest(self.times, t)
        tt = float(self.times[ti]) if ti is not None else t
        tracks: list[OverlayTrack] = []
        g = self.box_groups.get(round(tt, 4))
        tail_s = self.s.overlay.tail_s
        tails: dict[str, list[tuple[float, float]]] = {}
        if len(self.track_t):
            lo, hi = np.searchsorted(self.track_t, [tt - tail_s, tt + 1e-6])
            seg = self.tracks.iloc[lo:hi]
            for tid, tg in seg.groupby("track_id"):
                tails[str(tid)] = [(float(x), float(y)) for x, y in zip(tg["px_x"], tg["px_y"], strict=True)]
        if g is not None:
            for r in g.itertuples():
                tid = str(r.track_id)
                tracks.append(OverlayTrack(track_id=tid, bbox_xyxy=(float(r.x1), float(r.y1), float(r.x2), float(r.y2)),  # type: ignore[arg-type]
                                           tail=tails.get(tid, [])))
        zones: list[OverlayZone] = []
        for zid, poly in self.zone_px.items():
            dens = cnt = 0.0
            mode = "sparse"
            if zid in self.zone_vals:
                zt, zd, zc, zm = self.zone_vals[zid]
                k = self._at_or_before(zt, tt)
                if k is not None:
                    dens, cnt, mode = float(zd[k]), float(zc[k]), zm[k]
            state = "LOW"
            if zid in self.zone_state:
                st, ss = self.zone_state[zid]
                k = self._at_or_before(st, tt)
                if k is not None:
                    state = ss[k]
            zones.append(OverlayZone(zone_id=zid, polygon_px=poly, density=dens, count=cnt, state=state, mode=mode))
        arrows: list[OverlayArrow] = []
        ai = self._nearest(self.arrow_t, tt)
        if ai is not None:
            for x, y, dx, dy in self.arrow_data[self.arrow_off[ai]: self.arrow_off[ai + 1]]:
                arrows.append(OverlayArrow(x=float(x), y=float(y), dx=float(dx), dy=float(dy)))
        heat = None
        hi_ = self._nearest(self.heat_t, tt)
        if with_heatmap and hi_ is not None:
            heat = np.round(self.heat[hi_].astype(np.float32), 3).tolist()
        return OverlayFrame(t=tt, frame_width=self.w, frame_height=self.h, tracks=tracks, zones=zones,
                            arrows=arrows, heatmap=heat)


class OverlayCache:
    """Small LRU of OverlayIndex objects keyed by (run_id, artefact mtimes)."""

    def __init__(self, size: int = 4) -> None:
        self.size = size
        self._d: OrderedDict[tuple[str, float], OverlayIndex] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, store: RunStore, run_id: str, settings: Settings) -> OverlayIndex:
        stamp = max((p.stat().st_mtime for p in store.run_dir(run_id).glob("*.*")), default=0.0)
        key = (run_id, stamp)
        with self._lock:
            if key in self._d:
                self._d.move_to_end(key)
                return self._d[key]
        idx = OverlayIndex(store, run_id, settings)
        with self._lock:
            self._d[key] = idx
            while len(self._d) > self.size:
                self._d.popitem(last=False)
        return idx


OVERLAY_CACHE = OverlayCache()
