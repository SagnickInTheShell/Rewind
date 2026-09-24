"""Applies interventions dynamically to simulation state."""

from __future__ import annotations

from rewind.schemas.simulation import Intervention
from rewind.schemas.venue import Venue


class InterventionManager:
    def __init__(self, venue: Venue, interventions: list[Intervention]) -> None:
        self.venue = venue
        self.interventions = sorted(interventions, key=lambda x: x.at_t)
        self.open_portals: set[str] = {p.portal_id for p in venue.portals if p.is_open}
        self.portal_widths: dict[str, float] = {p.portal_id: p.width_m for p in venue.portals}
        self.inflow_factors: dict[str, float] = {s: 1.0 for s in venue.sources}

    def update_at_time(self, t: float) -> list[Intervention]:
        """Apply any interventions scheduled up to time t."""
        applied: list[Intervention] = []
        for iv in self.interventions:
            if iv.type != "NONE" and iv.at_t <= t:
                if iv.type == "OPEN_PORTAL" and iv.portal_id:
                    self.open_portals.add(iv.portal_id)
                    applied.append(iv)
                elif iv.type == "CLOSE_PORTAL" and iv.portal_id:
                    self.open_portals.discard(iv.portal_id)
                    applied.append(iv)
                elif iv.type == "WIDEN_PORTAL" and iv.portal_id and iv.factor:
                    if iv.portal_id in self.portal_widths:
                        self.portal_widths[iv.portal_id] *= iv.factor
                    applied.append(iv)
                elif iv.type == "RESTRICT_ENTRY" and iv.factor is not None:
                    for s in self.venue.sources:
                        self.inflow_factors[s] = iv.factor
                    applied.append(iv)
        return applied
