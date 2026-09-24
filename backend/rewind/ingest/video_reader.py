"""Video ingest: metadata probing and timestamp-based frame sampling."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from rewind.schemas.video import VideoMeta

log = logging.getLogger(__name__)


class VideoOpenError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProcessedFrame:
    index: int  # index among processed frames
    t: float  # seconds from video start
    image: np.ndarray  # BGR, resized to processed size


def _open(path: Path) -> cv2.VideoCapture:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise VideoOpenError(f"cannot open video: {path}")
    return cap


def probe(path: Path, video_id: str, fps_processed: float, synthetic: bool = False) -> VideoMeta:
    cap = _open(path)
    try:
        fps = float(cap.get(cv2.CAP_PROP_FPS)) or 25.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if count <= 0:  # some containers do not report a count; walk the file
            count = 0
            while cap.grab():
                count += 1
    finally:
        cap.release()
    if width <= 0 or height <= 0:
        raise VideoOpenError(f"video has no readable frames: {path}")
    return VideoMeta(
        video_id=video_id,
        filename=path.name,
        fps_native=fps,
        fps_processed=min(fps_processed, fps),
        width=width,
        height=height,
        duration_s=count / fps if fps > 0 else 0.0,
        frame_count=count,
        synthetic=synthetic,
    )


def processed_size(width: int, height: int, max_width: int) -> tuple[int, int, float]:
    """Return (w, h, scale) such that w <= max_width and aspect ratio is preserved."""
    scale = min(1.0, max_width / float(width))
    return round(width * scale), round(height * scale), scale


class VideoReader:
    """Yields frames at ``fps_processed`` using container timestamps (robust to variable frame rate)."""

    def __init__(self, path: Path, fps_processed: float, max_width: int) -> None:
        self.path = Path(path)
        cap = _open(self.path)
        self.fps_native = float(cap.get(cv2.CAP_PROP_FPS)) or 25.0
        self.width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()
        self.fps_processed = min(fps_processed, self.fps_native)
        self.out_w, self.out_h, self.scale = processed_size(self.width, self.height, max_width)

    @property
    def interval(self) -> float:
        return 1.0 / self.fps_processed

    def to_original_px(self, pts: np.ndarray) -> np.ndarray:
        """Map processed-frame pixel coords back to original video pixels."""
        return np.asarray(pts, dtype=np.float64) / self.scale

    def frames(self, t_start: float = 0.0, t_end: float | None = None) -> Iterator[ProcessedFrame]:
        cap = _open(self.path)
        try:
            if t_start > 0:
                cap.set(cv2.CAP_PROP_POS_MSEC, t_start * 1000.0)
            next_t = t_start
            raw_idx = 0
            out_idx = 0
            half = 0.5 / self.fps_native
            while True:
                if not cap.grab():
                    break
                pos_ms = cap.get(cv2.CAP_PROP_POS_MSEC)
                # Some backends report the timestamp of the *next* frame or 0; fall back to index math.
                t = pos_ms / 1000.0 if pos_ms > 0 or raw_idx == 0 else raw_idx / self.fps_native
                raw_idx += 1
                if t_end is not None and t > t_end:
                    break
                if t + half < next_t:
                    continue
                ok, img = cap.retrieve()
                if not ok or img is None:
                    continue
                if self.scale < 1.0:
                    img = cv2.resize(img, (self.out_w, self.out_h), interpolation=cv2.INTER_AREA)
                yield ProcessedFrame(index=out_idx, t=round(next_t, 4), image=img)
                out_idx += 1
                next_t += self.interval
        finally:
            cap.release()

    def first_frame(self) -> np.ndarray:
        for f in self.frames():
            return f.image
        raise VideoOpenError(f"no frames in {self.path}")
