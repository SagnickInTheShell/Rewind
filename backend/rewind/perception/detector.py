"""Person detection.

* :class:`YoloDetector` wraps Ultralytics YOLOv8 (COCO class 0 = person) for real footage.
* :class:`BlobDetector` is a classical colour-blob detector for the synthetic top-down renders
  produced by ``scripts/render_synthetic_video.py`` (people drawn as saturated discs on a grey
  floor). YOLO is trained on photographs and does not recognise such blobs as people, so synthetic
  runs use this detector automatically; the run info panel always shows which detector ran.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Protocol, cast

import cv2
import numpy as np

from rewind.schemas.perception import Detection

log = logging.getLogger(__name__)


class Detector(Protocol):
    name: str

    def detect_batch(self, frames: Sequence[np.ndarray], times: Sequence[float]) -> list[list[Detection]]: ...


class YoloDetector:
    name = "yolov8"

    def __init__(self, model: str = "yolov8s.pt", conf: float = 0.25, imgsz: int = 1280,
                 batch: int = 8, device: str | None = None) -> None:
        from ultralytics import YOLO  # type: ignore[attr-defined]

        self.model = YOLO(model)
        self.conf = conf
        self.imgsz = imgsz
        self.batch = batch
        try:
            import torch

            self.device = device or ("cuda:0" if torch.cuda.is_available() else "cpu")
        except Exception:
            self.device = device or "cpu"
        self.half = self.device.startswith("cuda")
        self.name = f"yolov8 ({model.split('/')[-1].split(chr(92))[-1]}, {self.device})"

    def detect_batch(self, frames: Sequence[np.ndarray], times: Sequence[float]) -> list[list[Detection]]:
        out: list[list[Detection]] = []
        step = self.batch if self.device != "cpu" else 1
        for i in range(0, len(frames), step):
            chunk = list(frames[i : i + step])
            results = self.model.predict(chunk, imgsz=self.imgsz, conf=self.conf, classes=[0],
                                         device=self.device, half=self.half, verbose=False)
            for res, t in zip(cast(list[Any], results), times[i : i + step], strict=True):
                boxes = res.boxes
                xyxy = boxes.xyxy.cpu().numpy() if boxes is not None else np.zeros((0, 4))
                confs = boxes.conf.cpu().numpy() if boxes is not None else np.zeros(0)
                out.append([Detection(t=float(t), bbox_xyxy=tuple(map(float, b)), conf=float(c))  # type: ignore[arg-type]
                            for b, c in zip(xyxy, confs, strict=True)])
        return out


class BlobDetector:
    """Detects saturated disc-shaped blobs (synthetic top-down renders).

    Touching blobs are split with distance-transform peaks, so dense clusters are counted per
    person rather than per connected component. Each detection's bbox is the disc's bounding box;
    for top-down footage the ground point is the bbox centre (see ``camera_view``).
    """

    name = "blob (synthetic top-down)"

    def __init__(self, min_saturation: int = 80, min_value: int = 60, expected_radius_px: float = 8.0) -> None:
        self.min_s = min_saturation
        self.min_v = min_value
        self.r = expected_radius_px

    def detect(self, frame: np.ndarray, t: float) -> list[Detection]:
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask: np.ndarray = ((hsv[:, :, 1] >= self.min_s) & (hsv[:, :, 2] >= self.min_v)).astype(np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        if not mask.any():
            return []
        dist = cv2.distanceTransform(mask, cv2.DIST_L2, 3)
        k = max(3, round(self.r * 1.2) | 1)
        peaks = (dist == cv2.dilate(dist, np.ones((k, k), np.uint8))) & (dist >= self.r * 0.45)
        n, labels = cv2.connectedComponents(peaks.astype(np.uint8))
        dets: list[Detection] = []
        for lbl in range(1, n):
            ys, xs = np.nonzero(labels == lbl)
            cx, cy = float(xs.mean()), float(ys.mean())
            rad = float(max(dist[ys, xs].max(), self.r * 0.6))
            conf = float(min(1.0, rad / self.r))
            dets.append(Detection(t=t, bbox_xyxy=(cx - rad, cy - rad, cx + rad, cy + rad), conf=min(conf, 1.0)))
        return dets

    def detect_batch(self, frames: Sequence[np.ndarray], times: Sequence[float]) -> list[list[Detection]]:
        return [self.detect(f, t) for f, t in zip(frames, times, strict=True)]


def resolve_yolo_weights(model: str, models_dir: Path) -> str:
    """Prefer ``models_dir/<model>``; download it there (Ultralytics release asset) if missing."""
    p = Path(model)
    if p.is_absolute() or p.exists():
        return str(p)
    local = models_dir / p.name
    if local.exists():
        return str(local)
    try:
        import os

        from ultralytics.utils.downloads import attempt_download_asset

        models_dir.mkdir(parents=True, exist_ok=True)
        cwd = os.getcwd()
        os.chdir(models_dir)
        try:
            attempt_download_asset(p.name)
        finally:
            os.chdir(cwd)
        if local.exists():
            return str(local)
    except Exception as exc:  # offline: let Ultralytics resolve / fail with its own message
        log.warning("could not pre-fetch %s into %s: %s", model, models_dir, exc)
    return model


def build_detector(kind: str, *, model: str, conf: float, imgsz: int, batch: int,
                   blob_radius_px: float = 8.0, models_dir: Path | None = None) -> Detector:
    if kind == "blob":
        return BlobDetector(expected_radius_px=blob_radius_px)
    weights = resolve_yolo_weights(model, models_dir) if models_dir is not None else model
    return YoloDetector(model=weights, conf=conf, imgsz=imgsz, batch=batch)


def ground_points(bboxes: np.ndarray, camera_view: str) -> np.ndarray:
    """Ground contact point per bbox: bottom-centre (oblique) or centre (top-down)."""
    b = np.asarray(bboxes, dtype=np.float64).reshape(-1, 4)
    cx = (b[:, 0] + b[:, 2]) / 2
    y = (b[:, 1] + b[:, 3]) / 2 if camera_view == "top_down" else b[:, 3]
    return np.stack([cx, y], axis=1)


def head_points(bboxes: np.ndarray, camera_view: str) -> np.ndarray:
    """Head point per bbox (used for KDE density): 10% below the top (oblique) or centre (top-down)."""
    b = np.asarray(bboxes, dtype=np.float64).reshape(-1, 4)
    cx = (b[:, 0] + b[:, 2]) / 2
    if camera_view == "top_down":
        return np.stack([cx, (b[:, 1] + b[:, 3]) / 2], axis=1)
    return np.stack([cx, b[:, 1] + 0.1 * (b[:, 3] - b[:, 1])], axis=1)
