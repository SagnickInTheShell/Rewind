"""Ensemble of physics / temporal / XGBoost scores, per-zone states and the global (worst-zone) series."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from rewind.risk.physics_scorer import physics_scores
from rewind.risk.states import RiskStateMachine
from rewind.schemas.risk import RISK_ORDER, RISK_STATES
from rewind.settings import RiskSettings

RISK_COLUMNS = ["t", "zone_id", "physics_score", "ml_score", "ensemble_score", "state"]
GLOBAL_COLUMNS = ["t", "max_score", "worst_zone", "state"]


@dataclass
class ModelScores:
    """Optional ML scores aligned with the feature rows (NaN where a model has no prediction)."""

    temporal: np.ndarray | None = None
    xgb: np.ndarray | None = None


def ensemble_weights(risk: RiskSettings, has_temporal: bool, has_xgb: bool) -> dict[str, float]:
    w = {"physics": risk.ensemble.physics}
    if has_temporal:
        w["temporal"] = risk.ensemble.temporal
    if has_xgb:
        w["xgb"] = risk.ensemble.xgb
    total = sum(w.values())
    return {k: v / total for k, v in w.items()} if total > 0 else {"physics": 1.0}


def combine(physics: np.ndarray, models: ModelScores, risk: RiskSettings) -> tuple[np.ndarray, np.ndarray]:
    """Row-wise ensemble. Rows where a model is NaN renormalise over the available scorers.

    Returns (ensemble, ml) where ml is the weighted mean of the available ML scores (NaN if none).
    """
    n = len(physics)
    parts = {"physics": physics}
    if models.temporal is not None:
        parts["temporal"] = np.asarray(models.temporal, dtype=float)
    if models.xgb is not None:
        parts["xgb"] = np.asarray(models.xgb, dtype=float)
    base = {"physics": risk.ensemble.physics, "temporal": risk.ensemble.temporal, "xgb": risk.ensemble.xgb}
    num = np.zeros(n)
    den = np.zeros(n)
    ml_num = np.zeros(n)
    ml_den = np.zeros(n)
    for k, arr in parts.items():
        ok = np.isfinite(arr)
        num += np.where(ok, base[k] * np.nan_to_num(arr), 0.0)
        den += np.where(ok, base[k], 0.0)
        if k != "physics":
            ml_num += np.where(ok, base[k] * np.nan_to_num(arr), 0.0)
            ml_den += np.where(ok, base[k], 0.0)
    ens = np.where(den > 0, num / np.maximum(den, 1e-12), physics)
    ml = np.where(ml_den > 0, ml_num / np.maximum(ml_den, 1e-12), np.nan)
    return np.clip(ens, 0, 1), ml


def score_features(features: pd.DataFrame, risk: RiskSettings, models: ModelScores | None = None
                   ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """features.parquet → (risk df [RISK_COLUMNS], global df [GLOBAL_COLUMNS])."""
    if features.empty:
        return pd.DataFrame(columns=RISK_COLUMNS), pd.DataFrame(columns=GLOBAL_COLUMNS)
    f = features.sort_values(["zone_id", "t"]).reset_index(drop=True)
    phys = physics_scores(f, risk)
    ens, ml = combine(phys, models or ModelScores(), risk)
    f = f.assign(physics_score=phys, ml_score=ml, ensemble_score=ens)
    sm = RiskStateMachine(risk)
    states: list[str] = []
    for _, g in f.groupby("zone_id", sort=False):
        states.extend(sm.run(g["t"].to_numpy(), g["ensemble_score"].to_numpy(), g["density"].to_numpy(),
                             g["crowd_pressure"].to_numpy()))
    f["state"] = states
    risk_df = f[RISK_COLUMNS].sort_values(["t", "zone_id"]).reset_index(drop=True)
    return risk_df, global_risk(risk_df)


def global_risk(risk_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for t, g in risk_df.groupby("t", sort=True):
        i = int(np.argmax(g["ensemble_score"].to_numpy()))
        worst = g.iloc[i]
        lvl = max(RISK_ORDER[s] for s in g["state"])
        rows.append({"t": float(t), "max_score": float(worst["ensemble_score"]), "worst_zone": str(worst["zone_id"]),
                     "state": RISK_STATES[lvl]})
    return pd.DataFrame(rows, columns=GLOBAL_COLUMNS)
