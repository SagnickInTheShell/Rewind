"""Applies the trained temporal and XGBoost models (if present) to a features table.

Both models are optional: when their weights are missing the ensemble renormalises over the
remaining scorers (physics is always available).
"""

from __future__ import annotations

import importlib
import logging

import numpy as np
import pandas as pd

from rewind.risk.ensemble import ModelScores
from rewind.schemas.venue import Venue
from rewind.settings import Settings

log = logging.getLogger(__name__)


def available_models(s: Settings) -> dict[str, bool]:
    return {
        "physics": True,
        "temporal": (s.models_dir / f"temporal_{s.risk.temporal.arch}.pt").exists(),
        "xgb": (s.models_dir / "xgb.json").exists(),
    }


def predict_ml(features: pd.DataFrame, venue: Venue, s: Settings) -> tuple[ModelScores, str]:
    """Return aligned ML scores (rows sorted by zone_id, t — the order used by ``score_features``)."""
    avail = available_models(s)
    scores = ModelScores()
    used = ["physics"]
    if features.empty or not (avail["temporal"] or avail["xgb"]):
        return scores, "physics"
    f = features.sort_values(["zone_id", "t"]).reset_index(drop=True)
    if avail["temporal"]:
        try:
            mod = importlib.import_module("rewind.risk.temporal_model")
            scores.temporal = mod.TemporalScorer.load(s).predict(f, venue)
            used.append(f"temporal ({s.risk.temporal.arch})")
        except Exception as exc:
            log.warning("temporal model unavailable: %s", exc)
    if avail["xgb"]:
        try:
            mod = importlib.import_module("rewind.risk.xgb_model")
            scores.xgb = mod.XGBScorer.load(s).predict(f, venue)
            used.append("xgboost")
        except Exception as exc:
            log.warning("xgboost model unavailable: %s", exc)
    for arr in (scores.temporal, scores.xgb):
        if arr is not None and len(arr) != len(f):
            raise ValueError("ML scores are not aligned with the features table")
    label = "ensemble: " + " + ".join(used) if len(used) > 1 else "physics"
    return scores, label


def nan_array(n: int) -> np.ndarray:
    return np.full(n, np.nan)
