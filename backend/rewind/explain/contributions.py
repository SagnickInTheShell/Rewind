"""Explanations: exact physics contributions (always) and SHAP values (when the XGBoost model exists)."""

from __future__ import annotations

import json
from typing import Any

import numpy as np
import pandas as pd

from rewind.explain.narrator import Narrator
from rewind.risk.physics_scorer import contribution_matrix, feature_names
from rewind.schemas.features import FEATURE_LABELS
from rewind.schemas.risk import Contribution, Explanation
from rewind.settings import Settings

EXPLANATION_COLUMNS = ["t", "zone_id", "score", "state", "method", "narrative", "contributions"]


def make_contributions(features: list[str], values: np.ndarray, contribs: np.ndarray) -> list[Contribution]:
    pos = float(np.sum(np.maximum(contribs, 0.0)))
    items = [Contribution(feature=f, label=FEATURE_LABELS.get(f, f), value=float(v), contribution=float(c),
                          share=float(max(c, 0.0) / pos) if pos > 0 else 0.0)
             for f, v, c in zip(features, values, contribs, strict=True)]
    return sorted(items, key=lambda c: c.contribution, reverse=True)


def physics_explanations(features: pd.DataFrame, risk_df: pd.DataFrame, narrator: Narrator,
                         settings: Settings) -> pd.DataFrame:
    """Explanation row for every (t, zone): exact physics contributions + narrative."""
    if features.empty:
        return pd.DataFrame(columns=EXPLANATION_COLUMNS)
    risk = settings.risk
    names = feature_names(risk)
    lookback = max(1, int(round(settings.events.trend_window_s / settings.features.window_s)))
    f = features.merge(risk_df[["t", "zone_id", "physics_score", "state"]], on=["t", "zone_id"], how="left")
    f = f.sort_values(["zone_id", "t"]).reset_index(drop=True)
    rows: list[dict[str, Any]] = []
    for zid, g in f.groupby("zone_id", sort=False):
        g = g.reset_index(drop=True)
        contribs = contribution_matrix(g, risk)
        vals = g[names].to_numpy()
        states = g["state"].fillna("LOW").tolist()
        for i in range(len(g)):
            j = max(0, i - lookback)
            now = {n: float(g.at[i, n]) for n in names}
            past = {n: float(g.at[j, n]) for n in names}
            items = make_contributions(names, vals[i], contribs[i])
            text = narrator.explain(str(zid), states[i], states[j], [(c.feature, c.contribution) for c in items],
                                    now, past)
            rows.append({"t": float(g.at[i, "t"]), "zone_id": str(zid), "score": float(g.at[i, "physics_score"]),
                         "state": states[i], "method": "physics_weights", "narrative": text,
                         "contributions": json.dumps([c.model_dump() for c in items])})
    return pd.DataFrame(rows, columns=EXPLANATION_COLUMNS).sort_values(["t", "zone_id"]).reset_index(drop=True)


def row_to_explanation(row: dict[str, Any]) -> Explanation:
    return Explanation(t=float(row["t"]), zone_id=str(row["zone_id"]), score=float(row["score"]),
                       state=row["state"], method=row["method"], narrative=str(row["narrative"]),
                       contributions=[Contribution.model_validate(c) for c in json.loads(row["contributions"])])
