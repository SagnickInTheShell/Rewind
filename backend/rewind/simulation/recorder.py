"""Recording simulation trajectories for twin playback (frames.npz)."""

from __future__ import annotations

from pathlib import Path

import numpy as np


class SimRecorder:
    def __init__(self, record_hz: float = 10.0) -> None:
        self.record_hz = record_hz
        self.interval = 1.0 / record_hz
        self.last_recorded_t = -1e9
        self.timestamps: list[float] = []
        self.frames_pos: list[np.ndarray] = []     # list of (N_i, 2) in float16
        self.frames_dens: list[np.ndarray] = []    # list of (N_i,) in float16

    def record_step(self, t: float, pos: np.ndarray, local_density: np.ndarray) -> None:
        if t - self.last_recorded_t >= self.interval - 1e-4:
            self.timestamps.append(round(t, 3))
            self.frames_pos.append(pos.astype(np.float16))
            self.frames_dens.append(local_density.astype(np.float16))
            self.last_recorded_t = t

    def save_npz(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        # Flatten or save as object array for variable agent counts
        np.savez_compressed(
            path,
            timestamps=np.array(self.timestamps, dtype=np.float32),
            positions=np.array(self.frames_pos, dtype=object),
            densities=np.array(self.frames_dens, dtype=object),
        )
