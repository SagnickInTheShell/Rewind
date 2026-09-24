"""Privacy-by-design helpers.

REWIND never performs face recognition or identity inference; track IDs are anonymous and per run.
When ``app.blur_heads_in_exports`` is enabled, every frame image served or exported by the API is
blurred over the top 25 % of each person bounding box (the head region).
"""

from __future__ import annotations

import cv2
import numpy as np

HEAD_FRACTION = 0.25


def blur_heads(frame: np.ndarray, bboxes: np.ndarray, fraction: float = HEAD_FRACTION,
               kernel_frac: float = 0.5) -> np.ndarray:
    out = frame.copy()
    h, w = out.shape[:2]
    for x1, y1, x2, y2 in np.asarray(bboxes, dtype=np.float64).reshape(-1, 4):
        bh = y2 - y1
        xa, xb = max(0, int(x1)), min(w, int(np.ceil(x2)))
        ya, yb = max(0, int(y1)), min(h, int(np.ceil(y1 + fraction * bh)))
        if xb - xa < 2 or yb - ya < 2:
            continue
        k = max(3, int(max(xb - xa, yb - ya) * kernel_frac) | 1)
        out[ya:yb, xa:xb] = cv2.GaussianBlur(out[ya:yb, xa:xb], (k, k), 0)
    return out
