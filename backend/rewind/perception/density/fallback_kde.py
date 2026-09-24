"""KDE density fallback: a normalised Gaussian at each detection's ground (foot) point.

The map sums to the number of detections; σ scales with local bbox height so distant (small)
people get narrower kernels. Used when CSRNet weights are unavailable.
"""

from __future__ import annotations

import numpy as np

from rewind.perception.detector import ground_points


class KDEDensity:
    name = "kde"

    def __init__(self, sigma_factor: float = 0.3, camera_view: str = "oblique") -> None:
        self.sigma_factor = sigma_factor
        self.camera_view = camera_view

    def density_map(self, shape_hw: tuple[int, int], bboxes: np.ndarray) -> np.ndarray:
        h, w = shape_hw
        dmap = np.zeros((h, w), dtype=np.float32)
        b = np.asarray(bboxes, dtype=np.float64).reshape(-1, 4)
        if len(b) == 0:
            return dmap
        # Kernels sit on the ground point so the map is a floor-occupancy density: zone counts then agree
        # with detection counts (on oblique cameras heads project into a different zone than feet).
        pts = ground_points(b, self.camera_view)
        heights = np.maximum(b[:, 3] - b[:, 1], 2.0)
        for (hx, hy), bh in zip(pts, heights, strict=True):
            sigma = max(1.0, self.sigma_factor * bh)
            rad = int(np.ceil(3 * sigma))
            cx, cy = int(hx), int(hy)
            # Kernel over the full (unclipped) window, normalised to 1; only the in-frame part is added,
            # so people partly outside the frame contribute their visible share.
            gx = np.exp(-((np.arange(cx - rad, cx + rad + 1) + 0.5 - hx) ** 2) / (2 * sigma**2))
            gy = np.exp(-((np.arange(cy - rad, cy + rad + 1) + 0.5 - hy) ** 2) / (2 * sigma**2))
            norm = gx.sum() * gy.sum()
            x0, x1 = max(0, cx - rad), min(w, cx + rad + 1)
            y0, y1 = max(0, cy - rad), min(h, cy + rad + 1)
            if x0 >= x1 or y0 >= y1 or norm <= 0:
                continue
            kx = gx[x0 - (cx - rad): x1 - (cx - rad)]
            ky = gy[y0 - (cy - rad): y1 - (cy - rad)]
            dmap[y0:y1, x0:x1] += (np.outer(ky, kx) / norm).astype(np.float32)
        return dmap
