from __future__ import annotations

import numpy as np
import pytest

from rewind.calibration.homography import (
    CalibrationError,
    fit_homography,
    pixel_area_m2,
    pixel_to_world,
    scale_homography,
    venue_homography,
    world_to_pixel,
    zone_masks,
)
from rewind.schemas.venue import Point
from rewind.venue.demo import build_demo_venue


def _perspective_setup() -> tuple[np.ndarray, np.ndarray]:
    img = np.array([[300, 200], [980, 200], [1200, 700], [80, 700], [640, 400]], dtype=float)
    # generate world points from a known homography so the fit is exact
    H_true = np.array([[0.05, 0.01, -10.0], [0.0, 0.08, -12.0], [0.0, 0.0012, 1.0]])
    hom = np.hstack([img, np.ones((len(img), 1))]) @ H_true.T
    wld = hom[:, :2] / hom[:, 2:3]
    return img, wld


def test_round_trip_under_half_pixel() -> None:
    img, wld = _perspective_setup()
    H = fit_homography(img, wld)
    H_inv = np.linalg.inv(H)
    rng = np.random.default_rng(0)
    px = rng.uniform([0, 150], [1280, 720], size=(500, 2))
    back = world_to_pixel(pixel_to_world(px, H), H_inv)
    assert np.max(np.linalg.norm(back - px, axis=1)) < 0.5


def test_needs_four_points() -> None:
    pts = [Point(x=0, y=0), Point(x=1, y=0), Point(x=1, y=1)]
    with pytest.raises(CalibrationError, match="at least 4"):
        fit_homography(pts, pts)


def test_degenerate_points_rejected() -> None:
    pts = np.array([[0, 0], [1, 1], [2, 2], [3, 3]], dtype=float)
    with pytest.raises(CalibrationError):
        fit_homography(pts, pts)


def test_known_square_area_top_down() -> None:
    # 32 px per metre, pure scaling: each pixel covers (1/32)^2 m²
    img = np.array([[0, 0], [320, 0], [320, 320], [0, 320]], dtype=float)
    wld = img / 32.0
    H = fit_homography(img, wld)
    area = pixel_area_m2(H, (320, 320))
    assert area.sum() == pytest.approx(100.0, rel=1e-6)  # 10 m × 10 m


def test_area_matches_polygon_under_perspective() -> None:
    img, wld = _perspective_setup()
    H = fit_homography(img, wld)
    H_inv = np.linalg.inv(H)
    square = np.array([[2, 3], [6, 3], [6, 7], [2, 7]], dtype=float)  # 16 m²
    poly_px = world_to_pixel(square, H_inv)
    import cv2

    mask = np.zeros((720, 1280), np.uint8)
    cv2.fillPoly(mask, [np.round(poly_px).astype(np.int32)], 1)
    area = pixel_area_m2(H, (720, 1280))
    assert float((area * mask).sum()) == pytest.approx(16.0, rel=0.05)


def test_scale_homography() -> None:
    img, wld = _perspective_setup()
    H = fit_homography(img, wld)
    Hs = scale_homography(H, 0.5)
    assert np.allclose(pixel_to_world(img * 0.5, Hs), pixel_to_world(img, H), atol=1e-6)


def test_demo_zone_masks_cover_expected_area() -> None:
    venue = build_demo_venue()
    H, H_inv = venue_homography(venue)
    masks = zone_masks(venue, H_inv, (720, 1280))
    area = pixel_area_m2(H, (720, 1280))
    assert set(masks) == set(venue.zone_ids)
    for m in masks.values():
        assert float((area * m).sum()) == pytest.approx(600.0 / 9.0, rel=0.05)
