"""Dense optical flow (Farneback) converted to world-frame velocity samples per zone."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from rewind.calibration.homography import pixel_to_world


@dataclass
class ZoneFlow:
    """World velocity samples (m/s) in one zone for one frame pair, plus mean |curl|."""

    positions: np.ndarray  # (n, 2) world metres
    velocities: np.ndarray  # (n, 2) m/s
    abs_curl: float  # mean |∂vy/∂x − ∂vx/∂y| over occupied grid cells (1/s)


def farneback(prev_gray: np.ndarray, gray: np.ndarray, downscale: float) -> np.ndarray:
    """Flow in *full-resolution* pixel units, sampled on the downscaled grid (h', w', 2)."""
    if downscale != 1.0:
        size = (max(1, int(gray.shape[1] * downscale)), max(1, int(gray.shape[0] * downscale)))
        a = cv2.resize(prev_gray, size, interpolation=cv2.INTER_AREA)
        b = cv2.resize(gray, size, interpolation=cv2.INTER_AREA)
    else:
        a, b = prev_gray, gray
    flow = cv2.calcOpticalFlowFarneback(  # type: ignore[call-overload]
        a, b, None, pyr_scale=0.5, levels=3, winsize=15, iterations=3, poly_n=5, poly_sigma=1.2, flags=0)
    return np.asarray(flow / downscale, dtype=np.float32)


class FlowSampler:
    """Samples the flow field on a regular pixel grid and projects it into world velocities."""

    def __init__(self, H: np.ndarray, masks: dict[str, np.ndarray], frame_shape: tuple[int, int],
                 grid_step_px: int = 8, downscale: float = 0.5) -> None:
        self.H = H
        self.downscale = downscale
        h, w = frame_shape
        ys, xs = np.mgrid[grid_step_px // 2: h: grid_step_px, grid_step_px // 2: w: grid_step_px]
        self.grid_shape = ys.shape
        self.px = np.stack([xs.ravel(), ys.ravel()], axis=1).astype(np.float64)
        self.world = pixel_to_world(self.px, H)
        self.zone_idx: dict[str, np.ndarray] = {
            z: np.flatnonzero(m[ys.ravel(), xs.ravel()]) for z, m in masks.items()}
        self.step_world = self._grid_spacing_world(grid_step_px)

    def _grid_spacing_world(self, step: int) -> np.ndarray:
        right = pixel_to_world(self.px + np.array([step, 0]), self.H)
        down = pixel_to_world(self.px + np.array([0, step]), self.H)
        return np.stack([np.linalg.norm(right - self.world, axis=1), np.linalg.norm(down - self.world, axis=1)], 1)

    def occupancy_from_heat(self, heat: np.ndarray, frame_shape: tuple[int, int], min_density: float) -> np.ndarray:
        """Grid points whose coarse heat cell (persons/m²) exceeds ``min_density``."""
        rows, cols = heat.shape
        h, w = frame_shape
        r = np.clip((self.px[:, 1] / h * rows).astype(int), 0, rows - 1)
        c = np.clip((self.px[:, 0] / w * cols).astype(int), 0, cols - 1)
        return np.asarray(heat[r, c] > min_density)

    def sample(self, flow: np.ndarray, dt: float, occupied: np.ndarray | None = None
               ) -> tuple[dict[str, ZoneFlow], np.ndarray]:
        """Return per-zone flow and the full grid of world velocities (n_grid, 2).

        ``occupied`` (bool per grid point) excludes empty floor from the samples.
        """
        fh, fw = flow.shape[:2]
        fx = np.clip((self.px[:, 0] * self.downscale).astype(int), 0, fw - 1)
        fy = np.clip((self.px[:, 1] * self.downscale).astype(int), 0, fh - 1)
        disp = flow[fy, fx].astype(np.float64)
        end_world = pixel_to_world(self.px + disp, self.H)
        vel = (end_world - self.world) / max(dt, 1e-6)
        if occupied is None:
            occupied = np.ones(len(self.px), dtype=bool)
        curl_grid = self._curl(vel, occupied)
        out: dict[str, ZoneFlow] = {}
        for z, idx in self.zone_idx.items():
            sel = idx[occupied[idx]]
            curl_vals = curl_grid[sel]
            curl_vals = curl_vals[np.isfinite(curl_vals)]
            out[z] = ZoneFlow(positions=self.world[sel], velocities=vel[sel],
                              abs_curl=float(np.mean(np.abs(curl_vals))) if curl_vals.size else 0.0)
        return out, vel

    def _curl(self, vel: np.ndarray, occupied: np.ndarray) -> np.ndarray:
        gh, gw = self.grid_shape
        vx = vel[:, 0].reshape(gh, gw)
        vy = vel[:, 1].reshape(gh, gw)
        occ = occupied.reshape(gh, gw)
        sx = self.step_world[:, 0].reshape(gh, gw)
        sy = self.step_world[:, 1].reshape(gh, gw)
        curl = np.full((gh, gw), np.nan)
        if gh < 3 or gw < 3:
            return curl.ravel()
        dvy_dx = (vy[1:-1, 2:] - vy[1:-1, :-2]) / np.maximum(2 * sx[1:-1, 1:-1], 1e-6)
        dvx_dy = (vx[2:, 1:-1] - vx[:-2, 1:-1]) / np.maximum(2 * sy[1:-1, 1:-1], 1e-6)
        inner = dvy_dx - dvx_dy
        valid = occ[1:-1, 1:-1] & occ[1:-1, 2:] & occ[1:-1, :-2] & occ[2:, 1:-1] & occ[:-2, 1:-1]
        curl[1:-1, 1:-1] = np.where(valid, inner, np.nan)
        return curl.ravel()


def arrows_from_grid(sampler: FlowSampler, vel_world: np.ndarray, H_inv: np.ndarray, every: int = 6,
                     min_speed: float = 0.15, seconds: float = 1.0) -> list[tuple[float, float, float, float]]:
    """Coarse arrow set in pixel space for the overlay: (x, y, dx, dy) showing ``seconds`` of motion."""
    from rewind.calibration.homography import world_to_pixel

    gh, gw = sampler.grid_shape
    idx = np.arange(gh * gw).reshape(gh, gw)[::every, ::every].ravel()
    v = vel_world[idx]
    keep = np.linalg.norm(v, axis=1) >= min_speed
    idx, v = idx[keep], v[keep]
    if idx.size == 0:
        return []
    end_px = world_to_pixel(sampler.world[idx] + v * seconds, H_inv)
    start_px = sampler.px[idx]
    d = end_px - start_px
    return [(float(a), float(b), float(c), float(e)) for (a, b), (c, e) in zip(start_px, d, strict=True)]
