"""Risk and explanation contracts (Sections 5.5, 5.6)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

RiskState = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
RISK_ORDER: dict[str, int] = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
RISK_STATES: list[RiskState] = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]


class RiskPoint(BaseModel):
    t: float
    zone_id: str
    physics_score: float = Field(ge=0, le=1)
    ml_score: float | None = Field(default=None, ge=0, le=1)
    ensemble_score: float = Field(ge=0, le=1)
    state: RiskState


class GlobalRiskPoint(BaseModel):
    t: float
    max_score: float = Field(ge=0, le=1)
    worst_zone: str
    state: RiskState


class RiskSeries(BaseModel):
    run_id: str
    zones: list[RiskPoint]
    global_risk: list[GlobalRiskPoint]
    methods: dict[str, bool]  # which scorers contributed: physics / temporal / xgb


class Contribution(BaseModel):
    feature: str
    label: str
    value: float
    contribution: float
    share: float = Field(ge=0, le=1)


class Explanation(BaseModel):
    t: float
    zone_id: str
    score: float
    state: RiskState
    contributions: list[Contribution]
    method: Literal["physics_weights", "shap"]
    narrative: str
