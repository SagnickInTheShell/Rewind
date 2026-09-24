"""Density estimation: CSRNet when weights exist, otherwise the KDE fallback."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

from rewind.perception.density.fallback_kde import KDEDensity

log = logging.getLogger(__name__)


class DensityEstimator:
    """Uniform interface: ``density_map(frame, bboxes)``; ``method`` is 'csrnet' or 'kde'."""

    def __init__(self, weights: Path, sigma_factor: float, camera_view: str, allow_csrnet: bool = True) -> None:
        self._csr = None
        self._kde = KDEDensity(sigma_factor=sigma_factor, camera_view=camera_view)
        if allow_csrnet and weights.exists():
            try:
                from rewind.perception.density.csrnet import CSRNetDensity
                self._csr = CSRNetDensity(weights)
            except Exception as exc:
                log.warning("failed to load CSRNet weights from %s (%s); using KDE fallback", weights, exc)
        elif allow_csrnet:
            log.warning("CSRNet weights not found at %s; using KDE fallback density", weights)

    @property
    def method(self) -> str:
        return "csrnet" if self._csr is not None else "kde"

    def density_map(self, frame: np.ndarray, bboxes: np.ndarray) -> np.ndarray:
        if self._csr is not None:
            return self._csr.density_map(frame)
        return self._kde.density_map((int(frame.shape[0]), int(frame.shape[1])), bboxes)

