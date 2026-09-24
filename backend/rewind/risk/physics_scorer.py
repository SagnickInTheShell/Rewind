"""Physics-based risk scorer: fully explainable weighted sum of saturating normalised features.

    n_f = clip(value_f / norm_f, 0, 1) · g_f
    physics_score = Σ_f weight_f · n_f
    contribution_f = weight_f · n_f   (exact decomposition of the score)

``g_f`` is an occupancy gate for motion-pattern features (``risk.occupancy_gated``): it equals
clip(density / ``risk.occupancy_full_density``, 0, 1), so counterflow or instability measured
among a handful of people in a near-empty zone does not register as crowd risk.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from rewind.settings import RiskSettings


def feature_names(risk: RiskSettings) -> list[str]:
    return list(risk.weights)


def _gate(density: np.ndarray, risk: RiskSettings) -> np.ndarray:
    return np.asarray(np.clip(density / max(risk.occupancy_full_density, 1e-9), 0.0, 1.0))


def normalised(df: pd.DataFrame, risk: RiskSettings) -> np.ndarray:
    """(n_rows, n_features) matrix of gated n_f in [0, 1], columns ordered as ``feature_names``."""
    cols = feature_names(risk)
    vals = df[cols].to_numpy(dtype=np.float64)
    norms = np.array([risk.norm[c] for c in cols], dtype=np.float64)
    n = np.clip(vals / np.maximum(norms, 1e-12), 0.0, 1.0)
    if "density" in df.columns and risk.occupancy_gated:
        gate = _gate(df["density"].to_numpy(dtype=np.float64), risk)
        for j, c in enumerate(cols):
            if c in risk.occupancy_gated:
                n[:, j] *= gate
    return np.asarray(n)


def contribution_matrix(df: pd.DataFrame, risk: RiskSettings) -> np.ndarray:
    w = np.array([risk.weights[c] for c in feature_names(risk)], dtype=np.float64)
    return normalised(df, risk) * w


def physics_scores(df: pd.DataFrame, risk: RiskSettings) -> np.ndarray:
    if df.empty:
        return np.zeros(0)
    return np.asarray(np.clip(contribution_matrix(df, risk).sum(axis=1), 0.0, 1.0))


def score_one(values: dict[str, float], risk: RiskSettings) -> tuple[float, dict[str, float]]:
    """Score a single feature dict; returns (score, contribution per feature)."""
    gate = float(_gate(np.array([values.get("density", 0.0)]), risk)[0])
    contrib = {}
    for f, w in risk.weights.items():
        n = float(np.clip(values.get(f, 0.0) / max(risk.norm[f], 1e-12), 0.0, 1.0))
        if f in risk.occupancy_gated:
            n *= gate
        contrib[f] = w * n
    return float(min(sum(contrib.values()), 1.0)), contrib
