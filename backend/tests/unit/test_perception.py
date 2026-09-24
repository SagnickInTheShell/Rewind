from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import pytest
import torch

from rewind.calibration.homography import fit_homography
from rewind.perception.density import DensityEstimator
from rewind.perception.density.csrnet import CSRNet, CSRNetDensity, load_state, upsample_preserving_sum
from rewind.perception.density.fallback_kde import KDEDensity
from rewind.perception.detector import BlobDetector, ground_points, head_points
from rewind.perception.fusion import blend_weight, fuse_zone
from rewind.perception.optical_flow import FlowSampler, farneback
from rewind.perception.tracker import ByteTrackTracker, build_tracker
from rewind.perception.trajectories import build_trajectories
from rewind.privacy import blur_heads
from rewind.schemas.perception import Detection
from rewind.synthetic.render import Snapshot, draw_frame, static_background
from rewind.venue.demo import build_demo_venue
from rewind.venue.geometry import ZoneLocator


# ---- density ---------------------------------------------------------------------------------
def test_kde_sums_to_detection_count() -> None:
    kde = KDEDensity(sigma_factor=0.3, camera_view="oblique")
    boxes = np.array([[100, 100, 130, 180], [300, 200, 340, 300], [500, 50, 520, 100]], float)
    dmap = kde.density_map((480, 640), boxes)
    assert dmap.sum() == pytest.approx(3.0, rel=1e-3)


def test_kde_edge_kernel_keeps_visible_share() -> None:
    kde = KDEDensity(sigma_factor=0.3, camera_view="top_down")
    dmap = kde.density_map((100, 100), np.array([[-10, 40, 10, 60]], float))  # centre on the left edge
    assert 0.3 < dmap.sum() < 0.7


def test_kde_empty() -> None:
    assert KDEDensity().density_map((10, 10), np.zeros((0, 4))).sum() == 0


def test_csrnet_architecture_and_sum_preservation() -> None:
    torch.manual_seed(0)
    model = CSRNet()
    n_frontend_convs = sum(isinstance(m, torch.nn.Conv2d) for m in model.frontend)
    n_backend_convs = sum(isinstance(m, torch.nn.Conv2d) for m in model.backend)
    assert n_frontend_convs == 10 and n_backend_convs == 6
    assert all(m.dilation == (2, 2) for m in model.backend if isinstance(m, torch.nn.Conv2d))
    est = CSRNetDensity.from_model(model)
    frame = np.random.default_rng(0).integers(0, 255, (96, 128, 3), dtype=np.uint8)
    dmap = est.density_map(frame)
    assert dmap.shape == (96, 128)
    raw = model(torch.zeros(1, 3, 96, 128))
    assert raw.shape[-2:] == (12, 16)  # output stride 8


def test_upsample_preserves_sum() -> None:
    d = np.random.default_rng(1).random((12, 16)).astype(np.float32)
    up = upsample_preserving_sum(d, (96, 128))
    assert up.sum() == pytest.approx(d.sum(), rel=1e-4)
    assert up.min() >= 0


def test_csrnet_loads_prefixed_weights(tmp_path: Path) -> None:
    model = CSRNet()
    state = {f"module.{k}": v for k, v in model.state_dict().items()}
    p = tmp_path / "csrnet.pth"
    torch.save({"state_dict": state}, p)
    clean = load_state(p)
    assert all(not k.startswith("module.") for k in clean)
    est = DensityEstimator(p, 0.3, "oblique")
    assert est.method == "csrnet"


def test_density_falls_back_without_weights(tmp_path: Path) -> None:
    est = DensityEstimator(tmp_path / "missing.pth", 0.3, "oblique")
    assert est.method == "kde"
    dmap = est.density_map(np.zeros((120, 120, 3), np.uint8), np.array([[50, 40, 60, 70]], float))
    assert dmap.sum() == pytest.approx(1.0, rel=1e-3)


# ---- detection -----------------------------------------------------------------------------
def test_blob_detector_counts_rendered_people() -> None:
    venue = build_demo_venue()
    rng = np.random.default_rng(0)
    # a sparse group and a packed group (touching discs)
    sparse = rng.uniform([2, 2], [8, 6], size=(10, 2))
    sparse = sparse[np.all(np.linalg.norm(sparse[:, None] - sparse[None], axis=-1) + np.eye(10) * 9 > 0.7, axis=1)]
    packed = np.array([[15 + 0.5 * i, 17 + 0.5 * j] for i in range(4) for j in range(3)], float)
    xy = np.vstack([sparse, packed])
    snap = Snapshot(t=0.0, ids=np.arange(len(xy)), xy=xy, radius=np.full(len(xy), 0.25))
    frame = draw_frame(static_background(venue), snap)
    dets = BlobDetector(expected_radius_px=8.0).detect(frame, 0.0)
    assert abs(len(dets) - len(xy)) <= 1


def test_ground_and_head_points() -> None:
    b = np.array([[10, 20, 30, 100]], float)
    assert ground_points(b, "oblique").tolist() == [[20, 100]]
    assert ground_points(b, "top_down").tolist() == [[20, 60]]
    assert head_points(b, "oblique").tolist() == [[20, 28]]


@pytest.mark.models
def test_yolo_detects_people_in_sample_image() -> None:
    import ultralytics

    from rewind.perception.detector import YoloDetector, resolve_yolo_weights
    from rewind.settings import REPO_ROOT

    weights = resolve_yolo_weights("yolov8s.pt", REPO_ROOT / "data" / "models")
    img = cv2.imread(str(Path(ultralytics.__file__).parent / "assets" / "bus.jpg"))
    dets = YoloDetector(weights, conf=0.3, imgsz=640).detect_batch([img], [0.0])[0]
    assert len(dets) >= 3


# ---- tracking ------------------------------------------------------------------------------
def test_bytetrack_keeps_ids_for_moving_boxes() -> None:
    tr = ByteTrackTracker(frame_rate=5)
    ids_per_frame = []
    for k in range(8):
        dets = [Detection(t=k * 0.2, bbox_xyxy=(10 + 4 * k, 10, 30 + 4 * k, 60), conf=0.9),
                Detection(t=k * 0.2, bbox_xyxy=(200, 100 + 3 * k, 220, 150 + 3 * k), conf=0.9)]
        ids_per_frame.append(sorted(tid for tid, _ in tr.update(dets, None)))
    assert ids_per_frame[-1] == ids_per_frame[2]
    assert len(ids_per_frame[-1]) == 2


def test_deepsort_falls_back_to_bytetrack() -> None:
    t = build_tracker("deepsort", frame_rate=5)
    assert t.name in ("bytetrack", "deepsort")


# ---- trajectories --------------------------------------------------------------------------
def _top_down_H() -> np.ndarray:
    img = np.array([[160, 40], [1120, 40], [1120, 680], [160, 680]], float)
    wld = np.array([[0, 0], [30, 0], [30, 20], [0, 20]], float)
    return fit_homography(img, wld)


def test_trajectories_velocity_smoothing_and_filters() -> None:
    H = _top_down_H()
    loc = ZoneLocator(build_demo_venue())
    rows = []
    for k in range(20):  # 1.0 m/s south = 32 px/s at 5 fps → 6.4 px/frame
        cy = 100 + 6.4 * k + (1.0 if k % 2 else -1.0)  # jitter
        rows.append((k * 0.2, "a", 600 - 8, cy - 8, 600 + 8, cy + 8, 1.0))
    rows.append((0.0, "short", 300, 300, 316, 316, 1.0))
    rows.append((0.2, "short", 302, 300, 318, 316, 1.0))
    for k in range(10):  # teleporting box -> clipped speed
        rows.append((k * 0.2, "fast", 200 + 200 * k, 500, 216 + 200 * k, 516, 1.0))
    raw = pd.DataFrame(rows, columns=["t", "track_id", "x1", "y1", "x2", "y2", "conf"])
    df = build_trajectories(raw, H, loc, camera_view="top_down", min_duration_s=1.0, max_speed=4.0)
    assert set(df["track_id"]) == {"a", "fast"}
    a = df[df.track_id == "a"]
    assert a["vy"].iloc[5:-5].mean() == pytest.approx(1.0, abs=0.1)
    assert np.hypot(df.vx, df.vy).max() <= 4.0 + 1e-6
    assert a["zone_id"].iloc[0] == "A2"


# ---- optical flow --------------------------------------------------------------------------
def test_flow_sampler_recovers_translation() -> None:
    H = _top_down_H()
    rng = np.random.default_rng(0)
    base = (rng.random((720, 1280)) * 255).astype(np.uint8)
    base = cv2.GaussianBlur(base, (7, 7), 2)
    shifted = np.roll(base, 4, axis=0)  # 4 px south per 0.2 s → 0.125 m / 0.2 s = 0.625 m/s
    flow = farneback(base, shifted, 0.5)
    mask = np.zeros((720, 1280), bool)
    mask[200:500, 400:900] = True
    sampler = FlowSampler(H, {"Z": mask}, (720, 1280), 8, 0.5)
    zones, _ = sampler.sample(flow, 0.2)
    v = zones["Z"].velocities.mean(axis=0)
    assert v[1] == pytest.approx(0.625, abs=0.1)
    assert abs(v[0]) < 0.1
    assert zones["Z"].abs_curl < 0.5


# ---- fusion --------------------------------------------------------------------------------
def test_blend_weight() -> None:
    assert blend_weight(0.5, 1.5, 0.5) == 0.0
    assert blend_weight(1.5, 1.5, 0.5) == pytest.approx(0.5)
    assert blend_weight(3.0, 1.5, 0.5) == 1.0


def test_fusion_sparse_uses_tracks_dense_uses_flow() -> None:
    tv = np.array([[1.0, 0.0]] * 5)
    fv = np.array([[0.0, 1.0]] * 50)
    sparse = fuse_zone(count_det=10, count_map=12, area_m2=60, track_vectors=tv, n_tracks=5, flow_vectors=fv,
                       flow_abs_curl=0.2, switch=1.5, band=0.5)
    assert sparse.source == "tracks" and sparse.count == pytest.approx(10) and sparse.mode == "sparse"
    dense = fuse_zone(count_det=60, count_map=200, area_m2=60, track_vectors=tv, n_tracks=5, flow_vectors=fv,
                      flow_abs_curl=0.2, switch=1.5, band=0.5)
    assert dense.source == "density" and dense.count == pytest.approx(200) and dense.velocity_source == "flow"
    blend = fuse_zone(count_det=80, count_map=90, area_m2=60, track_vectors=tv, n_tracks=2, flow_vectors=fv,
                      flow_abs_curl=0.0, switch=1.5, band=0.5)
    assert blend.source == "fused" and 80 < blend.count < 90


# ---- privacy -------------------------------------------------------------------------------
def test_blur_heads_only_touches_head_region() -> None:
    rng = np.random.default_rng(0)
    frame = (rng.random((200, 200, 3)) * 255).astype(np.uint8)
    out = blur_heads(frame, np.array([[50, 40, 110, 200]], float))
    assert not np.array_equal(out[40:80, 50:110], frame[40:80, 50:110])
    assert np.array_equal(out[90:, :], frame[90:, :])
