"""Automatic ground-plane calibration from pedestrian heights (single-view metrology).

Used only when the venue's calibration does not fit the camera (most detected people fall outside
the floor plan). Densities computed on this basis are **estimates**, and runs say so.

Model (pinhole camera over a flat ground, no roll, small tilt): a person of height ``h_m`` whose
feet are at image row ``y`` appears ``h_px = a·(y − y_h)`` pixels tall, where ``y_h`` is the
horizon row and ``a = h_m / H_cam``. The ground position of pixel (x, y) is then

    Z = f·H_cam / (y − y_h)          (distance along the ground)
    X = (x − c_x)·H_cam / (y − y_h)  (lateral offset)

which is the homography  H = [[H_cam, 0, −c_x·H_cam], [0, 0, f·H_cam], [0, 1, −y_h]].
``f`` (focal length in pixels) is not observable from heights alone; it is taken from an
assumed horizontal field of view (config), which scales depth — hence "estimated".
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from rewind.calibration.homography import pixel_to_world
from rewind.schemas.venue import OUTSIDE, CameraCalibration, Point, Portal, Venue, Zone

ROWS = "ABC"


class AutoCalibrationError(ValueError):
    pass


@dataclass(frozen=True)
class HeightModel:
    slope: float  # a: pixel height per pixel of image row below the horizon
    horizon_y: float  # y_h (processed pixels)
    camera_height_m: float
    r2: float
    n_used: int


def fit_height_model(foot_y: np.ndarray, height_px: np.ndarray, person_height_m: float = 1.7,
                     iters: int = 5, min_samples: int = 30) -> HeightModel:
    """Robust linear fit h_px = a·y + b with iterative outlier rejection (occlusion, sitting, children)."""
    y = np.asarray(foot_y, dtype=np.float64)
    h = np.asarray(height_px, dtype=np.float64)
    keep = np.isfinite(y) & np.isfinite(h) & (h > 4)
    if keep.sum() < min_samples:
        raise AutoCalibrationError(f"need at least {min_samples} person detections, got {int(keep.sum())}")
    for _ in range(iters):
        a, b = np.polyfit(y[keep], h[keep], 1)
        resid = h - (a * y + b)
        mad = float(np.median(np.abs(resid[keep] - np.median(resid[keep])))) + 1e-6
        new_keep = keep & (np.abs(resid) <= 3.0 * 1.4826 * mad)
        if new_keep.sum() < min_samples or np.array_equal(new_keep, keep):
            break
        keep = new_keep
    a, b = np.polyfit(y[keep], h[keep], 1)
    if a <= 0:
        raise AutoCalibrationError("person heights do not grow towards the bottom of the frame; "
                                   "the camera is not a tilted view of a flat floor")
    pred = a * y[keep] + b
    ss_res = float(((h[keep] - pred) ** 2).sum())
    ss_tot = float(((h[keep] - h[keep].mean()) ** 2).sum()) + 1e-9
    y_h = -b / a
    if y_h >= float(np.min(y[keep])):
        raise AutoCalibrationError("estimated horizon lies below detected feet; calibration is inconsistent")
    return HeightModel(slope=float(a), horizon_y=float(y_h), camera_height_m=float(person_height_m / a),
                       r2=1.0 - ss_res / ss_tot, n_used=int(keep.sum()))


def focal_from_fov(width_px: float, hfov_deg: float) -> float:
    return width_px / (2.0 * math.tan(math.radians(hfov_deg) / 2.0))


def horizon_homography(model: HeightModel, width_px: float, hfov_deg: float) -> np.ndarray:
    """Image (processed px) → ground (m) homography from the height model."""
    f = focal_from_fov(width_px, hfov_deg)
    hc = model.camera_height_m
    cx = width_px / 2.0
    return np.array([[hc, 0.0, -cx * hc], [0.0, 0.0, f * hc], [0.0, 1.0, -model.horizon_y]], dtype=np.float64)


def camera_grid_venue(H: np.ndarray, frame_w: int, frame_h: int, y_top: float, scale: float,
                      venue_id: str = "camera_grid", name: str = "Camera grid (auto-calibrated)") -> Venue:
    """3×3 zones = image thirds of the visible ground region [y_top, frame_h], expressed on the ground plane.

    Every edge cell connects to ``OUTSIDE`` (people enter and leave the view at the frame border);
    adjacent cells connect through full-width openings. ``scale`` maps processed → original pixels
    (calibration points are stored in original video pixels).
    """
    xs = np.linspace(0.0, frame_w, 4)
    ys = np.linspace(y_top, frame_h, 4)

    def w(px: float, py: float) -> Point:
        p = pixel_to_world(np.array([[px, py]]), H)[0]
        return Point(x=round(float(p[0]), 3), y=round(float(p[1]), 3))

    grid = [[w(float(x), float(y)) for x in xs] for y in ys]  # grid[row][col]
    zones: list[Zone] = []
    for r in range(3):
        for c in range(3):
            zones.append(Zone(zone_id=f"{ROWS[r]}{c + 1}", name=f"Zone {ROWS[r]}{c + 1}", kind="floor",
                              polygon=[grid[r][c], grid[r][c + 1], grid[r + 1][c + 1], grid[r + 1][c]]))

    def seg_width(a: Point, b: Point) -> float:
        return max(float(math.hypot(b.x - a.x, b.y - a.y)), 0.1)

    portals: list[Portal] = []
    for r in range(3):
        for c in range(3):
            z = f"{ROWS[r]}{c + 1}"
            if c < 2:
                a, b = grid[r][c + 1], grid[r + 1][c + 1]
                portals.append(Portal(portal_id=f"C_{z}_{ROWS[r]}{c + 2}", name=f"{z}–{ROWS[r]}{c + 2}",
                                      from_zone=z, to_zone=f"{ROWS[r]}{c + 2}", segment=(a, b),
                                      width_m=seg_width(a, b), kind="corridor"))
            if r < 2:
                a, b = grid[r + 1][c], grid[r + 1][c + 1]
                portals.append(Portal(portal_id=f"C_{z}_{ROWS[r + 1]}{c + 1}", name=f"{z}–{ROWS[r + 1]}{c + 1}",
                                      from_zone=z, to_zone=f"{ROWS[r + 1]}{c + 1}", segment=(a, b),
                                      width_m=seg_width(a, b), kind="corridor"))
            edges = []
            if r == 0:
                edges.append(("N", grid[0][c], grid[0][c + 1]))
            if r == 2:
                edges.append(("S", grid[3][c], grid[3][c + 1]))
            if c == 0:
                edges.append(("W", grid[r][0], grid[r + 1][0]))
            if c == 2:
                edges.append(("E", grid[r][3], grid[r + 1][3]))
            for side, a, b in edges:
                portals.append(Portal(portal_id=f"EDGE_{z}_{side}", name=f"View edge {z} {side}", from_zone=z,
                                      to_zone=OUTSIDE, segment=(a, b), width_m=seg_width(a, b),
                                      bidirectional=True, kind="door"))
    edge_zones = [z.zone_id for z in zones if z.zone_id != "B2"]
    all_pts = [p for z in zones for p in z.polygon]
    bounds = (Point(x=min(p.x for p in all_pts), y=min(p.y for p in all_pts)),
              Point(x=max(p.x for p in all_pts), y=max(p.y for p in all_pts)))
    img = [(0.0, y_top), (float(frame_w), y_top), (float(frame_w), float(frame_h)), (0.0, float(frame_h)),
           (frame_w / 2.0, (y_top + frame_h) / 2.0)]
    calib = CameraCalibration(
        image_points=[Point(x=round(x / scale, 2), y=round(y / scale, 2)) for x, y in img],
        world_points=[w(x, y) for x, y in img])
    return Venue(venue_id=venue_id, name=name, bounds=bounds, zones=zones, portals=portals, walls=[],
                 sources=edge_zones, sinks=edge_zones, calibration=calib)


def ground_region_top(foot_y: np.ndarray, model: HeightModel, frame_h: int, min_gap_frac: float = 0.05) -> float:
    """Top of the analysed ground region: just above the farthest feet, but clear of the horizon."""
    far = float(np.percentile(foot_y, 2)) - 0.02 * frame_h
    return float(max(far, model.horizon_y + min_gap_frac * frame_h, 0.0))
