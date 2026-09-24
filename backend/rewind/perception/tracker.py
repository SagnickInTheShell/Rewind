"""Multi-object tracking behind a swappable :class:`Tracker` protocol."""

from __future__ import annotations

import logging
import warnings
from collections.abc import Sequence
from typing import Protocol

import numpy as np

from rewind.schemas.perception import Detection

log = logging.getLogger(__name__)

TrackOutput = list[tuple[str, tuple[float, float, float, float]]]


class Tracker(Protocol):
    name: str

    def update(self, detections: Sequence[Detection], frame: np.ndarray | None) -> TrackOutput: ...


class ByteTrackTracker:
    """ByteTrack (Zhang et al., 2022) via ``supervision``."""

    name = "bytetrack"

    def __init__(self, frame_rate: float = 5.0, activation_threshold: float = 0.25,
                 lost_track_buffer_s: float = 2.0, matching_threshold: float = 0.8) -> None:
        import supervision as sv

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self._bt = sv.ByteTrack(
                track_activation_threshold=activation_threshold,
                lost_track_buffer=max(1, round(lost_track_buffer_s * frame_rate)),
                minimum_matching_threshold=matching_threshold,
                frame_rate=max(1, round(frame_rate)),
                minimum_consecutive_frames=1,
            )
        self._sv = sv

    def update(self, detections: Sequence[Detection], frame: np.ndarray | None = None) -> TrackOutput:
        if detections:
            xyxy = np.array([d.bbox_xyxy for d in detections], dtype=np.float32)
            conf = np.array([d.conf for d in detections], dtype=np.float32)
        else:
            xyxy = np.zeros((0, 4), dtype=np.float32)
            conf = np.zeros(0, dtype=np.float32)
        dets = self._sv.Detections(xyxy=xyxy, confidence=conf, class_id=np.zeros(len(conf), dtype=int))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            tracked = self._bt.update_with_detections(dets)
        if tracked.tracker_id is None:
            return []
        return [(str(int(tid)), tuple(float(v) for v in box))  # type: ignore[misc]
                for tid, box in zip(tracked.tracker_id, tracked.xyxy, strict=True)]


class DeepSortTracker:
    """DeepSORT via ``deep-sort-realtime`` (optional extra ``rewind[deepsort]``).

    Only appearance embeddings of the person crop are used, and they are discarded after
    association; IDs are anonymous and per run (no re-identification across videos).
    """

    name = "deepsort"

    def __init__(self, frame_rate: float = 5.0, max_age_s: float = 2.0) -> None:
        try:
            from deep_sort_realtime.deepsort_tracker import DeepSort
        except ImportError as exc:  # pragma: no cover - depends on optional extra
            raise NotImplementedError(
                "DeepSORT requires the optional 'deep-sort-realtime' package (pip install -e 'backend[deepsort]')"
            ) from exc
        self._ds = DeepSort(max_age=max(1, int(max_age_s * frame_rate)), embedder="mobilenet", half=False)

    def update(self, detections: Sequence[Detection], frame: np.ndarray | None) -> TrackOutput:  # pragma: no cover
        raw = [([d.bbox_xyxy[0], d.bbox_xyxy[1], d.bbox_xyxy[2] - d.bbox_xyxy[0], d.bbox_xyxy[3] - d.bbox_xyxy[1]],
                d.conf, 0) for d in detections]
        tracks = self._ds.update_tracks(raw, frame=frame)
        out: TrackOutput = []
        for tr in tracks:
            if tr.is_confirmed() and tr.time_since_update == 0:
                x1, y1, x2, y2 = (float(v) for v in tr.to_ltrb())
                out.append((str(tr.track_id), (x1, y1, x2, y2)))
        return out


class CentroidTracker:
    """Lightweight Euclidean distance tracker for bounding boxes (fallback when supervision is unavailable)."""

    name = "centroid"

    def __init__(self, frame_rate: float = 5.0, max_distance_px: float = 60.0, max_disappeared: int = 10) -> None:
        self.frame_rate = frame_rate
        self.max_distance_px = max_distance_px
        self.max_disappeared = max_disappeared
        self.next_id = 1
        self.tracks: dict[int, tuple[float, float, float, float]] = {}  # id -> xyxy
        self.disappeared: dict[int, int] = {}

    def update(self, detections: Sequence[Detection], frame: np.ndarray | None = None) -> TrackOutput:
        if not detections:
            for tid in list(self.disappeared.keys()):
                self.disappeared[tid] += 1
                if self.disappeared[tid] > self.max_disappeared:
                    del self.tracks[tid]
                    del self.disappeared[tid]
            return []

        boxes = [d.bbox_xyxy for d in detections]
        if not self.tracks:
            out: TrackOutput = []
            for b in boxes:
                tid = self.next_id
                self.next_id += 1
                self.tracks[tid] = b
                self.disappeared[tid] = 0
                out.append((str(tid), b))
            return out

        # Match existing tracks to new detections by center distance
        track_ids = list(self.tracks.keys())
        track_centers = np.array([[(self.tracks[i][0] + self.tracks[i][2]) / 2, (self.tracks[i][1] + self.tracks[i][3]) / 2] for i in track_ids])
        det_centers = np.array([[(b[0] + b[2]) / 2, (b[1] + b[3]) / 2] for b in boxes])

        # Pairwise distance matrix
        dists = np.linalg.norm(track_centers[:, None, :] - det_centers[None, :, :], axis=2)
        used_tracks = set()
        used_dets = set()
        out = []

        if dists.size > 0:
            flat_indices = np.argsort(dists, axis=None)
            for flat_idx in flat_indices:
                t_idx, d_idx = np.unravel_index(flat_idx, dists.shape)
                if t_idx in used_tracks or d_idx in used_dets:
                    continue
                if dists[t_idx, d_idx] > self.max_distance_px:
                    break
                tid = track_ids[t_idx]
                self.tracks[tid] = boxes[d_idx]
                self.disappeared[tid] = 0
                used_tracks.add(t_idx)
                used_dets.add(d_idx)
                out.append((str(tid), boxes[d_idx]))

        for t_idx, tid in enumerate(track_ids):
            if t_idx not in used_tracks:
                self.disappeared[tid] = self.disappeared.get(tid, 0) + 1
                if self.disappeared[tid] > self.max_disappeared:
                    del self.tracks[tid]
                    del self.disappeared[tid]

        for d_idx, b in enumerate(boxes):
            if d_idx not in used_dets:
                tid = self.next_id
                self.next_id += 1
                self.tracks[tid] = b
                self.disappeared[tid] = 0
                out.append((str(tid), b))

        return out


def build_tracker(kind: str, frame_rate: float) -> Tracker:
    """Factory with graceful fallback to ByteTrack and CentroidTracker."""
    if kind == "deepsort":
        try:
            return DeepSortTracker(frame_rate=frame_rate)
        except (NotImplementedError, ImportError) as exc:
            log.warning("DeepSORT unavailable, falling back to ByteTrack: %s", exc)
    try:
        return ByteTrackTracker(frame_rate=frame_rate)
    except (ImportError, ModuleNotFoundError, Exception) as exc:
        log.warning("ByteTrack unavailable (%s), falling back to CentroidTracker", exc)
        return CentroidTracker(frame_rate=frame_rate)

