"""Spatial hash for fast O(N) neighbour lookups in 2D."""

from __future__ import annotations

import numpy as np


class SpatialHash2D:
    def __init__(self, cell_size: float = 1.0) -> None:
        self.cell_size = float(cell_size)
        self.inv_cell = 1.0 / self.cell_size
        self.grid: dict[tuple[int, int], list[int]] = {}

    def build(self, positions: np.ndarray) -> None:
        self.grid.clear()
        if len(positions) == 0:
            return
        cell_coords = np.floor(positions * self.inv_cell).astype(np.int32)
        for idx, (cx, cy) in enumerate(cell_coords):
            key = (int(cx), int(cy))
            if key in self.grid:
                self.grid[key].append(idx)
            else:
                self.grid[key] = [idx]

    def query_radius(self, pos: np.ndarray, radius: float) -> list[int]:
        r = float(radius)
        min_cx = int(np.floor((pos[0] - r) * self.inv_cell))
        max_cx = int(np.floor((pos[0] + r) * self.inv_cell))
        min_cy = int(np.floor((pos[1] - r) * self.inv_cell))
        max_cy = int(np.floor((pos[1] + r) * self.inv_cell))

        r2 = r * r
        matches: list[int] = []
        for cx in range(min_cx, max_cx + 1):
            for cy in range(min_cy, max_cy + 1):
                agents = self.grid.get((cx, cy))
                if agents:
                    matches.extend(agents)
        return matches
