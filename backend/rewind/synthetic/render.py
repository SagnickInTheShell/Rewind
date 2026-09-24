"""Render crowd trajectories of the demo venue as a top-down synthetic video.

People are drawn as saturated discs on a desaturated grey floor so the classical blob detector can
find them. The output is H.264 MP4 (``+faststart``, via the ffmpeg binary bundled with
``imageio-ffmpeg``) so it plays in every browser; if that binary is unavailable it falls back to
OpenCV's VP8/WebM writer (use a ``.webm`` path then). A ground-truth sidecar
(``<name>.gt.parquet``: t, agent_id, x, y) is written next to it for perception accuracy tests.
"""

from __future__ import annotations

import colorsys
import json
import logging
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pandas as pd

from rewind.schemas.venue import Venue
from rewind.venue.demo import FRAME_SIZE, ORIGIN_PX, PX_PER_M

log = logging.getLogger(__name__)

FLOOR_BGR = (62, 64, 66)
GRID_BGR = (78, 80, 82)
WALL_BGR = (205, 205, 205)
GATE_OPEN_BGR = (150, 150, 150)
GATE_CLOSED_BGR = (95, 95, 95)


@dataclass
class Snapshot:
    t: float
    ids: np.ndarray  # (n,)
    xy: np.ndarray  # (n, 2) metres
    radius: np.ndarray  # (n,) metres


def _px(x: float, y: float) -> tuple[int, int]:
    return int(round(ORIGIN_PX[0] + x * PX_PER_M)), int(round(ORIGIN_PX[1] + y * PX_PER_M))


def static_background(venue: Venue, portal_open: dict[str, bool] | None = None, seed: int = 0) -> np.ndarray:
    w, h = FRAME_SIZE
    img = np.full((h, w, 3), FLOOR_BGR, np.uint8)
    rng = np.random.default_rng(seed)
    noise = rng.integers(-4, 5, size=(h, w, 1), dtype=np.int16)
    img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    for z in venue.zones:
        pts = np.array([_px(p.x, p.y) for p in z.polygon], np.int32)
        cv2.polylines(img, [pts], True, GRID_BGR, 1, cv2.LINE_AA)
    for wall in venue.walls:
        cv2.line(img, _px(wall.a.x, wall.a.y), _px(wall.b.x, wall.b.y), WALL_BGR, 4, cv2.LINE_AA)
    for p in venue.portals:
        if p.kind != "gate":
            continue
        is_open = (portal_open or {}).get(p.portal_id, p.is_open)
        a, b = p.segment
        cv2.line(img, _px(a.x, a.y), _px(b.x, b.y), GATE_OPEN_BGR if is_open else GATE_CLOSED_BGR, 2, cv2.LINE_AA)
    cv2.putText(img, "SYNTHETIC FOOTAGE - simulated crowd", (16, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                (170, 170, 170), 1, cv2.LINE_AA)
    return img


def _agent_colour(agent_id: int) -> tuple[int, int, int]:
    rng = np.random.default_rng(agent_id * 7919 + 13)
    hue = float(rng.uniform(0, 1))
    r, g, b = colorsys.hsv_to_rgb(hue, float(rng.uniform(0.75, 1.0)), float(rng.uniform(0.75, 1.0)))
    return int(b * 255), int(g * 255), int(r * 255)


def draw_frame(bg: np.ndarray, snap: Snapshot) -> np.ndarray:
    img = bg.copy()
    for aid, (x, y), r in zip(snap.ids, snap.xy, snap.radius, strict=True):
        c = _agent_colour(int(aid))
        rp = max(3, int(round(r * PX_PER_M)))
        centre = _px(float(x), float(y))
        cv2.circle(img, centre, rp, c, -1, cv2.LINE_AA)
        dark = tuple(int(v * 0.7) for v in c)
        cv2.circle(img, centre, max(2, rp // 3), dark, -1, cv2.LINE_AA)
    t = f"t = {int(snap.t // 60)}:{int(snap.t % 60):02d}"
    cv2.putText(img, t, (FRAME_SIZE[0] - 150, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (170, 170, 170), 1, cv2.LINE_AA)
    return img


class _FrameSink:
    """H.264 via imageio-ffmpeg when available, else OpenCV VP8/WebM."""

    def __init__(self, out_path: Path, fps: float) -> None:
        self._gen: Any = None
        self._cv: cv2.VideoWriter | None = None
        if out_path.suffix.lower() == ".mp4":
            try:
                import imageio_ffmpeg

                self._gen = imageio_ffmpeg.write_frames(
                    str(out_path), FRAME_SIZE, fps=fps, codec="libx264", pix_fmt_out="yuv420p", quality=None,
                    macro_block_size=8, ffmpeg_log_level="error",
                    output_params=["-crf", "23", "-preset", "veryfast", "-movflags", "+faststart"])
                self._gen.send(None)
                return
            except Exception as exc:  # pragma: no cover - depends on the environment
                raise RuntimeError(f"H.264 writer unavailable ({exc}); use a .webm output path") from exc
        self._cv = cv2.VideoWriter(str(out_path), cv2.VideoWriter.fourcc(*"VP80"), fps, FRAME_SIZE)
        if not self._cv.isOpened():
            raise RuntimeError("OpenCV VP8 writer unavailable")

    def write(self, bgr: np.ndarray) -> None:
        if self._gen is not None:
            self._gen.send(np.ascontiguousarray(bgr[:, :, ::-1]))
        elif self._cv is not None:
            self._cv.write(bgr)

    def close(self) -> None:
        if self._gen is not None:
            self._gen.close()
        if self._cv is not None:
            self._cv.release()


def write_video(snapshots: Iterator[Snapshot], venue: Venue, out_path: Path, fps: float = 25.0,
                portal_open: dict[str, bool] | None = None) -> dict[str, object]:
    """Render snapshots (one per output frame) to ``out_path`` (.mp4 or .webm) plus sidecars."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    bg = static_background(venue, portal_open)
    sink = _FrameSink(out_path, fps)
    gt: list[pd.DataFrame] = []
    n = 0
    last_t = 0.0
    try:
        for snap in snapshots:
            sink.write(draw_frame(bg, snap))
            gt.append(pd.DataFrame({"t": snap.t, "agent_id": snap.ids, "x": snap.xy[:, 0], "y": snap.xy[:, 1]}))
            n += 1
            last_t = snap.t
    finally:
        sink.close()
    gt_df = pd.concat(gt, ignore_index=True) if gt else pd.DataFrame(columns=["t", "agent_id", "x", "y"])
    gt_df.to_parquet(out_path.with_suffix(".gt.parquet"), index=False)
    info = {"synthetic": True, "frames": n, "duration_s": last_t, "fps": fps, "venue_id": venue.venue_id}
    out_path.with_suffix(".synthetic.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    log.info("synthetic video written", extra={"kv": {"path": str(out_path), "frames": n}})
    return info
