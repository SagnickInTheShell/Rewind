"""Validation and strategy contracts (Sections 5.9, 5.10)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

CAVEAT = (
    "Simulation output under modelled assumptions. Not a guarantee of real-world outcomes. "
    "Intended to support, not replace, trained crowd-safety professionals."
)


class ValidationReport(BaseModel):
    run_id: str
    t0: float
    horizon_s: float
    per_zone_density_rmse: dict[str, float]
    per_zone_density_corr: dict[str, float]
    overall_density_rmse: float
    peak_time_error_s: float
    peak_density_error_pct: float
    state_agreement: float = Field(ge=0, le=1)
    calibrated_params: dict[str, float]
    verdict: Literal["GOOD", "FAIR", "POOR"]
    # Extra context for the UI: the non-overlapping split and the worst-zone series.
    calibration_window: tuple[float, float] = (0.0, 0.0)
    validation_window: tuple[float, float] = (0.0, 0.0)
    worst_zone: str = ""
    observed_series: list[tuple[float, float]] = Field(default_factory=list)
    simulated_series: list[tuple[float, float]] = Field(default_factory=list)


class Recommendation(BaseModel):
    rank: int
    scenario_id: str
    headline: str
    deltas: dict[str, float]
    confidence_note: str
    caveat: str = CAVEAT


class PreventionPlan(BaseModel):
    run_id: str
    recommendations: list[Recommendation]
    key_lessons: list[str]
