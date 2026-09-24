"""Simulation contracts (Section 5.8)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from rewind.schemas.risk import RiskState

InterventionType = Literal[
    "NONE", "OPEN_PORTAL", "CLOSE_PORTAL", "REDIRECT", "RESTRICT_ENTRY", "WIDEN_PORTAL"
]
BASELINE_ID = "baseline"


class Intervention(BaseModel):
    type: InterventionType
    at_t: float
    portal_id: str | None = None
    from_zone: str | None = None
    to_zone: str | None = None
    fraction: float | None = Field(default=None, ge=0, le=1)
    factor: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _required_fields(self) -> Intervention:
        t = self.type
        if t in ("OPEN_PORTAL", "CLOSE_PORTAL", "WIDEN_PORTAL") and not self.portal_id:
            raise ValueError(f"{t} requires portal_id")
        if t == "WIDEN_PORTAL" and (self.factor is None or self.factor <= 0):
            raise ValueError("WIDEN_PORTAL requires factor > 0")
        if t == "REDIRECT" and (not self.from_zone or not self.to_zone or self.fraction is None):
            raise ValueError("REDIRECT requires from_zone, to_zone and fraction")
        if t == "RESTRICT_ENTRY" and self.factor is None:
            raise ValueError("RESTRICT_ENTRY requires factor")
        return self


class ScenarioSpec(BaseModel):
    scenario_id: str
    name: str
    interventions: list[Intervention]


class SimulationRequest(BaseModel):
    run_id: str
    t0: float = Field(ge=0)
    horizon_s: float = Field(default=240.0, gt=0)
    scenarios: list[ScenarioSpec]
    seeds: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4], min_length=1)
    model: Literal["social_force", "macro"] = "social_force"

    @model_validator(mode="after")
    def _interventions_after_t0(self) -> SimulationRequest:
        for sc in self.scenarios:
            for iv in sc.interventions:
                if iv.type != "NONE" and iv.at_t < self.t0 - 1e-6:
                    raise ValueError(
                        f"intervention {iv.type} in '{sc.scenario_id}' at {iv.at_t}s is before t0={self.t0}s"
                    )
        return self


class AgentFrame(BaseModel):
    t: float
    xy: list[tuple[float, float]]
    local_density: list[float]


class ScenarioMetrics(BaseModel):
    peak_density: float
    peak_density_zone: str
    peak_crowd_pressure: float
    time_in_high_s: float
    time_in_critical_s: float
    max_state: RiskState
    mean_evacuation_rate: float
    agents_remaining: int
    seed_std: dict[str, float]


class ScenarioResult(BaseModel):
    scenario_id: str
    name: str = ""
    timeseries_path: str
    risk_path: str
    frames_path: str
    metrics: ScenarioMetrics
    interventions: list[Intervention] = Field(default_factory=list)


class SimulationStatus(BaseModel):
    sim_id: str
    run_id: str
    status: Literal["QUEUED", "RUNNING", "DONE", "FAILED"]
    request: SimulationRequest
    results: list[ScenarioResult]
    error: str | None = None


class ComparisonRow(BaseModel):
    scenario_id: str
    name: str
    peak_density: float
    peak_crowd_pressure: float
    time_in_high_s: float
    time_in_critical_s: float
    max_state: RiskState
    seed_std: dict[str, float]
    is_best: bool
    risk_series: list[tuple[float, float]]  # (t, global max ensemble score), mean over seeds


class Comparison(BaseModel):
    sim_id: str
    t0: float
    horizon_s: float
    rows: list[ComparisonRow]
    validation_verdict: Literal["GOOD", "FAIR", "POOR"] | None = None
