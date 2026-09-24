"""Perception stages: detection+tracking, trajectories, density, optical flow.

Each stage reads the video (cheap relative to the models) and writes one artefact, so stages
cache independently.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import pandas as pd

from rewind.calibration.homography import ground_speed_scale, pixel_area_m2, venue_homography, zone_masks
from rewind.ingest.video_reader import ProcessedFrame, VideoReader
from rewind.perception.density import DensityEstimator
from rewind.perception.detector import build_detector, ground_points
from rewind.perception.optical_flow import FlowSampler, arrows_from_grid, farneback
from rewind.perception.tracker import build_tracker
from rewind.perception.trajectories import RAW_COLUMNS, build_trajectories
from rewind.schemas.venue import Venue
from rewind.settings import Settings
from rewind.venue.geometry import ZoneLocator, zone_polygon

log = logging.getLogger(__name__)

Progress = Callable[[float, str], None]


def _noop(_: float, __: str) -> None:
    pass


@dataclass
class PerceptionContext:
    """Everything the perception stages share for one run."""

    video_path: Path
    venue: Venue
    settings: Settings
    synthetic: bool
    t_end: float | None = None

    def __post_init__(self) -> None:
        s = self.settings
        self.reader = VideoReader(self.video_path, s.video.fps_processed, s.video.max_width)
        self.frame_shape = (self.reader.out_h, self.reader.out_w)
        self.H, self.H_inv = venue_homography(self.venue, self.reader.scale)
        self.masks = zone_masks(self.venue, self.H_inv, self.frame_shape)
        self.pixel_area = pixel_area_m2(self.H, self.frame_shape)
        self.locator = ZoneLocator(self.venue)
        pv = s.perception
        self.camera_view = pv.camera_view if pv.camera_view != "auto" else ("top_down" if self.synthetic else "oblique")
        self.detector_kind = pv.detector if pv.detector != "auto" else ("blob" if self.synthetic else "yolo")
        self.zone_area: dict[str, float] = {}
        for z in self.venue.zones:
            visible = float((self.pixel_area * self.masks[z.zone_id]).sum())
            self.zone_area[z.zone_id] = visible if visible > 1e-3 else float(zone_polygon(z).area)
        cap = cv2.VideoCapture(str(self.video_path))
        n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.release()
        dur = n / self.reader.fps_native if self.reader.fps_native else 0.0
        if self.t_end is not None:
            dur = min(dur, self.t_end)
        self.n_frames_est = max(1, int(dur * self.reader.fps_processed))

    def frames(self) -> Iterator[ProcessedFrame]:
        return self.reader.frames(t_end=self.t_end)

    def blob_radius_px(self) -> float:
        centre = np.array([[self.frame_shape[1] / 2, self.frame_shape[0] / 2]])
        mpp = float(ground_speed_scale(self.H, centre)[0])
        return self.settings.perception.person_radius_m / max(mpp, 1e-6)


def stage_detect_track(ctx: PerceptionContext, progress: Progress = _noop
                       ) -> tuple[pd.DataFrame, pd.DataFrame, str, str]:
    """Returns (detections, track_boxes, detector_name, tracker_name)."""
    s = ctx.settings.perception
    detector = build_detector(ctx.detector_kind, model=s.yolo_model, conf=s.yolo_conf, imgsz=s.yolo_imgsz,
                              batch=s.yolo_batch, blob_radius_px=ctx.blob_radius_px(),
                              models_dir=ctx.settings.models_dir)
    tracker = build_tracker(s.tracker, frame_rate=ctx.reader.fps_processed)
    det_rows: list[tuple[float, ...]] = []
    box_rows: list[tuple[object, ...]] = []
    total = ctx.n_frames_est
    buf_f: list[np.ndarray] = []
    buf_t: list[float] = []
    done = 0
    t0 = time.perf_counter()

    def flush() -> None:
        nonlocal done
        if not buf_f:
            return
        for frame, t, dets in zip(buf_f, buf_t, detector.detect_batch(buf_f, buf_t), strict=True):
            det_rows.extend((t, *d.bbox_xyxy, d.conf) for d in dets)
            for tid, box in tracker.update(dets, frame):
                box_rows.append((t, tid, *box, 1.0))
            done += 1
        buf_f.clear()
        buf_t.clear()
        progress(min(done / total, 1.0), f"Detecting and tracking people: frame {done}/{total}")

    for fr in ctx.frames():
        buf_f.append(fr.image)
        buf_t.append(fr.t)
        if len(buf_f) >= max(1, s.yolo_batch):
            flush()
    flush()
    log.info("detection done", extra={"kv": {"frames": done, "detections": len(det_rows),
                                             "secs": round(time.perf_counter() - t0, 1)}})
    detections = pd.DataFrame(det_rows, columns=["t", "x1", "y1", "x2", "y2", "conf"])
    boxes = pd.DataFrame(box_rows, columns=RAW_COLUMNS)
    return detections, boxes, detector.name, getattr(tracker, "name", "bytetrack")


def stage_trajectories(ctx: PerceptionContext, boxes: pd.DataFrame) -> pd.DataFrame:
    s = ctx.settings.perception
    return build_trajectories(boxes, ctx.H, ctx.locator, camera_view=ctx.camera_view,
                              min_duration_s=s.track_min_duration_s, max_speed=s.track_max_speed,
                              savgol_window=s.savgol_window, savgol_order=s.savgol_order)


def _detection_zone_counts(ctx: PerceptionContext, dets: pd.DataFrame | None) -> dict[str, int]:
    if dets is None or dets.empty:
        return {z.zone_id: 0 for z in ctx.venue.zones}
    gp = ground_points(dets[["x1", "y1", "x2", "y2"]].to_numpy(), ctx.camera_view)
    xs = np.clip(gp[:, 0].astype(int), 0, ctx.frame_shape[1] - 1)
    ys = np.clip(gp[:, 1].astype(int), 0, ctx.frame_shape[0] - 1)
    # People whose ground point falls outside every zone are outside the floor plan and are not counted.
    return {z: int(m[ys, xs].sum()) for z, m in ctx.masks.items()}


def coarse_heat(dmap: np.ndarray, pixel_area: np.ndarray, grid: tuple[int, int]) -> np.ndarray:
    """Persons / m² on a coarse (rows, cols) grid."""
    cols, rows = grid
    h, w = dmap.shape
    ys = np.linspace(0, h, rows + 1).astype(int)[:-1]
    xs = np.linspace(0, w, cols + 1).astype(int)[:-1]
    cnt = np.add.reduceat(np.add.reduceat(dmap.astype(np.float64), ys, axis=0), xs, axis=1)
    area = np.add.reduceat(np.add.reduceat(pixel_area, ys, axis=0), xs, axis=1)
    return np.asarray(np.where(area > 0, cnt / np.maximum(area, 1e-9), 0.0), dtype=np.float32)


def stage_density(ctx: PerceptionContext, detections: pd.DataFrame, progress: Progress = _noop
                  ) -> tuple[pd.DataFrame, np.ndarray, np.ndarray, str]:
    """Per-zone per-frame counts from detections and from the density map.

    Returns (density_zone df, heat times, heat grids (persons/m²), method).
    """
    s = ctx.settings
    est = DensityEstimator(s.resolve(s.perception.density_model_path), s.perception.kde_sigma_factor,
                           ctx.camera_view)
    by_t = {round(float(t), 4): g for t, g in detections.groupby("t")} if not detections.empty else {}  # type: ignore[arg-type]
    empty = np.zeros((0, 4))
    rows: list[tuple[float, str, float, float, float]] = []
    heat_t: list[float] = []
    heat: list[np.ndarray] = []
    total = ctx.n_frames_est
    for i, fr in enumerate(ctx.frames()):
        dets = by_t.get(round(fr.t, 4))
        boxes = dets[["x1", "y1", "x2", "y2"]].to_numpy() if dets is not None else empty
        dmap = est.density_map(fr.image, boxes)
        det_counts = _detection_zone_counts(ctx, dets) if dets is not None else {}
        for z, m in ctx.masks.items():
            rows.append((fr.t, z, float(det_counts.get(z, 0)), float(dmap[m].sum()), ctx.zone_area[z]))
        heat_t.append(fr.t)
        heat.append(coarse_heat(dmap, ctx.pixel_area, s.overlay.heat_grid))
        if i % 10 == 0:
            progress(min((i + 1) / total, 1.0), f"Estimating density ({est.method}): frame {i + 1}/{total}")
    df = pd.DataFrame(rows, columns=["t", "zone_id", "count_det", "count_map", "area_m2"])
    grids = np.stack(heat).astype(np.float16) if heat else np.zeros((0, 1, 1), np.float16)
    return df, np.array(heat_t, dtype=np.float64), grids, est.method


def stage_flow(ctx: PerceptionContext, heat_times: np.ndarray, heat: np.ndarray, progress: Progress = _noop,
               seed: int = 0) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, np.ndarray]]:
    """Farneback flow -> world velocity samples per zone (subsampled), mean |curl|, overlay arrows.

    Only grid points whose coarse density (from the density stage) exceeds
    ``perception.density_min_threshold`` persons/m² are used, so empty floor is ignored.
    """
    s = ctx.settings.perception.flow
    sampler = FlowSampler(ctx.H, ctx.masks, ctx.frame_shape, s.grid_step_px, s.downscale)
    rng = np.random.default_rng(seed)
    min_d = ctx.settings.perception.density_min_threshold
    heat_index = {round(float(t), 4): i for i, t in enumerate(heat_times)}
    samples: list[pd.DataFrame] = []
    curls: list[tuple[float, str, float]] = []
    arrow_t: list[float] = []
    arrow_off: list[int] = [0]
    arrow_data: list[tuple[float, float, float, float]] = []
    prev_gray: np.ndarray | None = None
    prev_t = 0.0
    total = ctx.n_frames_est
    for i, fr in enumerate(ctx.frames()):
        gray = cv2.cvtColor(fr.image, cv2.COLOR_BGR2GRAY)
        if prev_gray is not None:
            flow = farneback(prev_gray, gray, s.downscale)
            hi = heat_index.get(round(fr.t, 4))
            occupied = (sampler.occupancy_from_heat(heat[hi].astype(np.float32), ctx.frame_shape, min_d)
                        if hi is not None else None)
            zones, vel = sampler.sample(flow, fr.t - prev_t, occupied)
            for z, zf in zones.items():
                n = len(zf.velocities)
                curls.append((fr.t, z, zf.abs_curl))
                if n == 0:
                    continue
                keep = (rng.choice(n, size=s.max_samples_per_zone, replace=False) if n > s.max_samples_per_zone
                        else np.arange(n))
                samples.append(pd.DataFrame({"t": fr.t, "zone_id": z, "x": zf.positions[keep, 0],
                                             "y": zf.positions[keep, 1], "vx": zf.velocities[keep, 0],
                                             "vy": zf.velocities[keep, 1]}))
            vel_shown = vel if occupied is None else np.where(occupied[:, None], vel, 0.0)
            arrow_t.append(fr.t)
            arrow_data.extend(arrows_from_grid(sampler, vel_shown, ctx.H_inv, every=ctx.settings.overlay.arrow_every))
            arrow_off.append(len(arrow_data))
        prev_gray, prev_t = gray, fr.t
        if i % 10 == 0:
            progress(min((i + 1) / total, 1.0), f"Estimating motion: frame {i + 1}/{total}")
    if samples:
        flow_df = pd.concat(samples, ignore_index=True)
    else:
        flow_df = pd.DataFrame({"t": pd.Series(dtype="float64"), "zone_id": pd.Series(dtype="object"),
                                "x": pd.Series(dtype="float64"), "y": pd.Series(dtype="float64"),
                                "vx": pd.Series(dtype="float64"), "vy": pd.Series(dtype="float64")})
    curl_df = pd.DataFrame(curls, columns=["t", "zone_id", "abs_curl"])
    arrows_npz: dict[str, np.ndarray] = {
        "t": np.array(arrow_t, dtype=np.float64),
        "offsets": np.array(arrow_off, dtype=np.int64),
        "data": np.array(arrow_data, dtype=np.float32).reshape(-1, 4),
    }
    return flow_df, curl_df, arrows_npz


# ---- calibration fit ------------------------------------------------------------------------
@dataclass
class CalibrationCheck:
    fit: float  # share of confident person detections whose ground point lies inside the floor plan
    n: int
    venue: Venue | None  # replacement (auto-calibrated) venue, or None when the venue calibration applies
    label: str
    density_basis: str
    note: str | None


def check_calibration(ctx: PerceptionContext, detections: pd.DataFrame) -> CalibrationCheck:
    """Does the venue calibration fit this camera? If not, auto-calibrate from pedestrian heights."""
    from rewind.calibration.auto_calibrate import (
        AutoCalibrationError,
        camera_grid_venue,
        fit_height_model,
        ground_region_top,
        horizon_homography,
    )
    from rewind.calibration.homography import pixel_to_world
    from rewind.venue.graph import validate_venue

    ac = ctx.settings.perception.auto_calibration
    det = detections[detections["conf"] >= ac.min_conf] if not detections.empty else detections
    if det.empty:
        return CalibrationCheck(0.0, 0, None, "venue", "calibrated", None)
    boxes = det[["x1", "y1", "x2", "y2"]].to_numpy()
    gp = ground_points(boxes, ctx.camera_view)
    inside = ctx.locator.locate_many(pixel_to_world(gp, ctx.H)) >= 0
    fit = float(inside.mean())
    if fit >= ctx.settings.perception.calibration_min_fit or ctx.camera_view == "top_down":
        return CalibrationCheck(fit, len(det), None, "venue", "calibrated", None)
    msg = (f"The venue calibration does not fit this camera: only {fit:.0%} of detected people fall inside "
           f"the floor plan.")
    try:
        model = fit_height_model(gp[:, 1], boxes[:, 3] - boxes[:, 1], ac.person_height_m,
                                 min_samples=ac.min_detections)
        H = horizon_homography(model, ctx.frame_shape[1], ac.hfov_deg)
        y_top = ground_region_top(gp[:, 1], model, ctx.frame_shape[0])
        venue = camera_grid_venue(H, ctx.frame_shape[1], ctx.frame_shape[0], y_top, ctx.reader.scale)
        errs = validate_venue(venue)
        if errs:
            raise AutoCalibrationError("; ".join(errs))
    except AutoCalibrationError as exc:
        return CalibrationCheck(fit, len(det), None, "venue (does not fit camera)", "UNRELIABLE",
                                f"{msg} Automatic calibration failed ({exc}); densities are unreliable. "
                                f"Calibrate the camera on the Upload page.")
    label = (f"auto from {model.n_used} pedestrian heights: camera ≈ {model.camera_height_m:.1f} m, "
             f"horizon row {model.horizon_y:.0f}, fit R² {model.r2:.2f}")
    note = (f"{msg} Zones are a 3×3 grid over the visible ground and density is ESTIMATED from pedestrian "
            f"heights (camera ≈ {model.camera_height_m:.1f} m high, assumed {ac.hfov_deg:.0f}° field of view). "
            f"Calibrate the camera on the Upload page for physical measurements.")
    return CalibrationCheck(fit, len(det), venue, label, "ESTIMATED", note)


# ---- debug trace ----------------------------------------------------------------------------
def trace_frames(ctx: PerceptionContext, detections: pd.DataFrame, boxes: pd.DataFrame, every: int = 1) -> None:
    """Log, per sampled frame: detections, active tracks, ids, ground points, world points, zones, counts."""
    from rewind.calibration.homography import pixel_to_world

    det_by_t = {round(float(t), 4): len(g) for t, g in detections.groupby("t")} if not detections.empty else {}
    times = sorted(det_by_t)
    box_by_t = {round(float(t), 4): g for t, g in boxes.groupby("t")} if not boxes.empty else {}
    for i, t in enumerate(times):
        if i % every:
            continue
        g = box_by_t.get(t)
        lines = [f"FRAME {i} t={t:.1f}s person detections={det_by_t[t]} active tracks={0 if g is None else len(g)}"]
        counts: dict[str, int] = {}
        if g is not None:
            gp = ground_points(g[["x1", "y1", "x2", "y2"]].to_numpy(), ctx.camera_view)
            wd = pixel_to_world(gp, ctx.H)
            for tid, (px, py), (wx, wy), z in zip(g["track_id"], gp, wd, ctx.locator.locate_ids(wd), strict=True):
                zone = z or "OUTSIDE_PLAN"
                counts[zone] = counts.get(zone, 0) + 1
                lines.append(f"  ID {tid}: ground px ({px:.0f},{py:.0f}) world ({wx:.1f},{wy:.1f}) m zone {zone}")
        lines.append(f"  zone counts: {counts}")
        log.info("\n".join(lines))
