"""Physics-based risk scorer: fully explainable weighted sum of saturating normalised features.

    n_f = clip(value_f / norm_f, 0, 1)
    physics_score = Σ_f weight_f · n_f
    contribution_f = weight_f · n_f   (exact decomposition of the score)
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from rewind.settings import RiskSettings


def feature_names(risk: RiskSettings) -> list[str]:
    return list(risk.weights)


def normalised(df: pd.DataFrame, risk: RiskSettings) -> np.ndarray:
    """(n_rows, n_features) matrix of n_f in [0, 1], columns ordered as ``feature_names``."""
    cols = feature_names(risk)
    vals = df[cols].to_numpy(dtype=np.float64)
    norms = np.array([risk.norm[c] for c in cols], dtype=np.float64)
    return np.asarray(np.clip(vals / np.maximum(norms, 1e-12), 0.0, 1.0))


def contribution_matrix(df: pd.DataFrame, risk: RiskSettings) -> np.ndarray:
    w = np.array([risk.weights[c] for c in feature_names(risk)], dtype=np.float64)
    return normalised(df, risk) * w


def physics_scores(df: pd.DataFrame, risk: RiskSettings) -> np.ndarray:
    if df.empty:
        return np.zeros(0)
    return np.asarray(np.clip(contribution_matrix(df, risk).sum(axis=1), 0.0, 1.0))


def score_one(values: dict[str, float], risk: RiskSettings) -> tuple[float, dict[str, float]]:
    """Score a single feature dict; returns (score, contribution per feature)."""
    contrib = {f: w * float(np.clip(values.get(f, 0.0) / max(risk.norm[f], 1e-12), 0.0, 1.0))
               for f, w in risk.weights.items()}
    return float(min(sum(contrib.values()), 1.0)), contrib
