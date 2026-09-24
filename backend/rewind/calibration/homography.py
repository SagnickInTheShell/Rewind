"""Pixel <-> world (metres) mapping via a planar homography.

Calibration ``image_points`` are given in *original* video pixels; use :func:`scale_homography` to
get the homography for the processed (resized) frames.
"""

from __future__ import annotations

from collections.abc import Sequence

import cv2
import numpy as np

from rewind.schemas.venue import Point, Venue


class CalibrationError(ValueError):
    pass


def _as_array(points: Sequence[Point] | np.ndarray) -> np.ndarray:
    if isinstance(points, np.ndarray):
        return points.astype(np.float64).reshape(-1, 2)
    return np.array([[p.x, p.y] for p in points], dtype=np.float64)


def fit_homography(image_points: Sequence[Point] | np.ndarray,
                   world_points: Sequence[Point] | np.ndarray) -> np.ndarray:
    """Fit H mapping image pixels -> world metres. Requires >= 4 correspondences."""
    img = _as_array(image_points)
    wld = _as_array(world_points)
    if len(img) != len(wld):
        raise CalibrationError(f"got {len(img)} image points but {len(wld)} world points")
    if len(img) < 4:
        raise CalibrationError(f"need at least 4 point correspondences, got {len(img)}")
    method = cv2.RANSAC if len(img) > 4 else 0
    H, _ = cv2.findHomography(img, wld, method, 3.0)
    if H is None or not np.all(np.isfinite(H)) or abs(np.linalg.det(H)) < 1e-12:
        raise CalibrationError("calibration points are degenerate (collinear or duplicated)")
    return np.asarray(H / H[2, 2], dtype=np.float64)


def scale_homography(H: np.ndarray, scale: float) -> np.ndarray:
    """H for pixels in a frame resized by ``scale`` (processed px = scale * original px)."""
    S_inv = np.diag([1.0 / scale, 1.0 / scale, 1.0])
    return np.asarray(H @ S_inv, dtype=np.float64)


def _apply(pts: np.ndarray, M: np.ndarray) -> np.ndarray:
    p = np.asarray(pts, dtype=np.float64).reshape(-1, 2)
    hom = np.hstack([p, np.ones((len(p), 1))]) @ M.T
    w = hom[:, 2:3]
    w = np.where(np.abs(w) < 1e-12, 1e-12, w)
    return np.asarray(hom[:, :2] / w, dtype=np.float64)


def pixel_to_world(pts: np.ndarray, H: np.ndarray) -> np.ndarray:
    return _apply(pts, H)


def world_to_pixel(pts: np.ndarray, H_inv: np.ndarray) -> np.ndarray:
    return _apply(pts, H_inv)


def venue_homography(venue: Venue, scale: float = 1.0) -> tuple[np.ndarray, np.ndarray]:
    """(H, H_inv) for the processed frame of a video at the given resize scale."""
    H = scale_homography(fit_homography(venue.calibration.image_points, venue.calibration.world_points), scale)
    return H, np.linalg.inv(H)


def zone_masks(venue: Venue, H_inv: np.ndarray, frame_shape: tuple[int, ...]) -> dict[str, np.ndarray]:
    """Rasterise each zone polygon (world) into a boolean image mask."""
    h, w = int(frame_shape[0]), int(frame_shape[1])
    masks: dict[str, np.ndarray] = {}
    for z in venue.zones:
        poly_px = world_to_pixel(_as_array(z.polygon), H_inv)
        m = np.zeros((h, w), dtype=np.uint8)
        if np.all(np.isfinite(poly_px)):
            clipped = np.clip(poly_px, -4 * max(w, h), 4 * max(w, h))
            cv2.fillPoly(m, [np.round(clipped).astype(np.int32)], 1)
        masks[z.zone_id] = m.astype(bool)
    return masks


def zone_polygons_px(venue: Venue, H_inv: np.ndarray) -> dict[str, np.ndarray]:
    return {z.zone_id: world_to_pixel(_as_array(z.polygon), H_inv) for z in venue.zones}


def pixel_area_m2(H: np.ndarray, frame_shape: tuple[int, ...]) -> np.ndarray:
    """Ground area (m²) covered by each pixel, from the homography Jacobian.

    For a projective map with denominator w = h31 u + h32 v + h33, |det J| = |det H| / |w|^3.
    Evaluated at pixel centres.
    """
    h, w = int(frame_shape[0]), int(frame_shape[1])
    u = np.arange(w, dtype=np.float64) + 0.5
    v = np.arange(h, dtype=np.float64) + 0.5
    uu, vv = np.meshgrid(u, v)
    denom = H[2, 0] * uu + H[2, 1] * vv + H[2, 2]
    det = abs(float(np.linalg.det(H)))
    area = det / np.maximum(np.abs(denom) ** 3, 1e-12)
    return np.asarray(area, dtype=np.float64)


def ground_speed_scale(H: np.ndarray, px: np.ndarray) -> np.ndarray:
    """Approximate metres-per-pixel at given pixel positions (sqrt of local area)."""
    p = np.asarray(px, dtype=np.float64).reshape(-1, 2)
    denom = H[2, 0] * p[:, 0] + H[2, 1] * p[:, 1] + H[2, 2]
    det = abs(float(np.linalg.det(H)))
    return np.asarray(np.sqrt(det / np.maximum(np.abs(denom) ** 3, 1e-12)), dtype=np.float64)
