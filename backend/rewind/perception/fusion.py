"""Hybrid sparse/dense fusion per zone.

Tracking where the crowd is sparse, density and flow where it is packed:

* count: ``(1 − w)·count_det + w·count_map`` with ``w = clip((ρ_map − (switch − band/2)) / band, 0, 1)``
* velocity: track velocities when ``w < 0.5`` and at least ``min_tracks`` tracks are in the zone,
  otherwise optical-flow vectors.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from rewind.schemas.features import FeatureSource


def blend_weight(rho_map: float, switch: float, band: float) -> float:
    if band <= 0:
        return 1.0 if rho_map >= switch else 0.0
    return float(np.clip((rho_map - (switch - band / 2.0)) / band, 0.0, 1.0))


@dataclass
class FusedZone:
    count: float
    density: float
    w: float
    source: FeatureSource
    velocity_source: str  # "tracks" | "flow" | "none"
    vectors: np.ndarray = field(default_factory=lambda: np.zeros((0, 2)))
    abs_curl: float = 0.0
    count_det: float = 0.0
    count_map: float = 0.0

    @property
    def mode(self) -> str:
        return "sparse" if self.velocity_source == "tracks" else "dense"


def fuse_zone(*, count_det: float, count_map: float, area_m2: float, track_vectors: np.ndarray,
              n_tracks: int, flow_vectors: np.ndarray, flow_abs_curl: float, switch: float, band: float,
              min_tracks: int = 3) -> FusedZone:
    area = max(area_m2, 1e-6)
    rho_map = count_map / area
    w = blend_weight(rho_map, switch, band)
    count = (1.0 - w) * count_det + w * count_map
    tv = np.asarray(track_vectors, dtype=np.float64).reshape(-1, 2)
    fv = np.asarray(flow_vectors, dtype=np.float64).reshape(-1, 2)
    if w < 0.5 and n_tracks >= min_tracks and len(tv):
        vectors, vsrc, curl = tv, "tracks", 0.0
    elif len(fv):
        vectors, vsrc, curl = fv, "flow", flow_abs_curl
    elif len(tv):
        vectors, vsrc, curl = tv, "tracks", 0.0
    else:
        vectors, vsrc, curl = np.zeros((0, 2)), "none", 0.0

    source: FeatureSource
    if vsrc == "tracks" and w == 0.0:
        source = "tracks"
    elif vsrc == "flow" and w >= 1.0:
        source = "density"
    else:
        source = "fused"
    return FusedZone(count=float(count), density=float(count / area), w=w, source=source, velocity_source=vsrc,
                     vectors=vectors, abs_curl=curl, count_det=float(count_det), count_map=float(count_map))
