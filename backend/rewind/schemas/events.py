"""Incident events and timeline (Section 5.7)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from rewind.schemas.risk import RiskState

EventType = Literal[
    "ENTRY_SURGE",
    "DENSITY_RISING",
    "DENSITY_THRESHOLD",
    "BOTTLENECK_FORMED",
    "COUNTERFLOW_EMERGED",
    "INSTABILITY_RISING",
    "RISK_STATE_CHANGE",
    "SPILLOVER",
    "PEAK_RISK",
    "DE_ESCALATION",
]


class IncidentEvent(BaseModel):
    event_id: str
    t_start: float
    t_end: float | None
    zone_id: str
    type: EventType
    severity: RiskState
    title: str
    detail: str
    evidence: dict[str, float]
    caused_by: list[str]


class IncidentTimeline(BaseModel):
    run_id: str
    events: list[IncidentEvent]
    origin_zone: str | None
    origin_time: float | None
    chain: list[str]
    summary: str
