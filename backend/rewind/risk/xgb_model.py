"""XGBoost tabular classifier for crowd risk escalation."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

try:
    import xgboost as xgb
except ImportError:
    xgb = None  # type: ignore


class XGBRiskModel:
    def __init__(self, model_path: Path | None = None) -> None:
        self.model: Any = None
        if model_path and model_path.exists() and xgb is not None:
            self.model = xgb.XGBClassifier()
            self.model.load_model(str(model_path))

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if self.model is not None:
            return self.model.predict_proba(X)[:, 1]
        # Fallback heuristic if weights not loaded
        # Density and bottleneck pressure feature heuristic
        if X.ndim == 1:
            X = X.reshape(1, -1)
        dens_feature = X[:, 0] if X.shape[1] > 0 else np.zeros(len(X))
        return np.clip(dens_feature / 5.0, 0.0, 1.0)
