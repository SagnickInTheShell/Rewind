"""Template-based, hedged plain-language narratives (no LLM).

Language rules (Section 13): never claim prediction or prevention of disasters; speak of
*modelled* risk and *estimated* capacity; recommendations always carry the caveat.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from rewind.schemas.features import FEATURE_LABELS
from rewind.schemas.risk import RISK_ORDER
from rewind.schemas.venue import Venue
from rewind.settings import Settings
from rewind.venue.graph import VenueGraph

BANNED_PHRASES = ("predicts stampedes", "prevents disasters", "would have saved", "prevent disasters",
                  "predict stampedes", "will prevent", "guarantees safety")


def fmt_clock(t: float | None) -> str:
    if t is None or not math.isfinite(t):
        return "--:--"
    t = max(t, 0.0)
    return f"{int(t // 60)}:{int(t % 60):02d}"


class Narrator:
    def __init__(self, venue: Venue, settings: Settings, graph: VenueGraph | None = None) -> None:
        self.venue = venue
        self.s = settings
        self.graph = graph or VenueGraph(venue, settings.features.specific_flow_p_per_m_s)
        self._names = {z.zone_id: z.name for z in venue.zones}

    # ---- labels ---------------------------------------------------------------------------
    def zone_name(self, zone_id: str) -> str:
        return self._names.get(zone_id, f"Zone {zone_id}")

    def portal_near(self, zone_id: str) -> str | None:
        """The zone's own gate, else the exit gate one zone downstream on its route, else None."""
        own = [p for p in self.graph.zone_portals(zone_id) if p.kind == "gate"]
        if own:
            c = self.graph.centroid[zone_id]
            from rewind.venue.geometry import portal_midpoint

            return min(own, key=lambda p: float(((portal_midpoint(p) - c) ** 2).sum())).name
        route = self.graph.route(zone_id)
        if route and len(route) == 3:
            gates = self.graph.exit_portals(route[1])
            if gates:
                return gates[0].name
        return None

    def has_own_gate(self, zone_id: str) -> bool:
        return any(p.kind == "gate" for p in self.graph.zone_portals(zone_id))

    def zone_label(self, zone_id: str) -> str:
        near = self.portal_near(zone_id)
        return f"{self.zone_name(zone_id)} (near {near})" if near else self.zone_name(zone_id)

    # ---- trends ---------------------------------------------------------------------------
    def trend(self, feature: str, past: float, now: float) -> str:
        norm = self.s.risk.norm.get(feature, max(abs(past), abs(now), 1e-6))
        delta = now - past
        if abs(delta) < 0.08 * norm and (abs(past) < 1e-9 or abs(delta) / max(abs(past), 1e-9) < 0.15):
            return "stable"
        return "rising" if delta > 0 else "falling"

    def feature_phrase(self, feature: str, past: float, now: float) -> str:
        tr = self.trend(feature, past, now)
        if feature == "density":
            if tr == "rising":
                return f"density climbed from {past:.1f} to {now:.1f} people/m²"
            if tr == "falling":
                return f"density eased from {past:.1f} to {now:.1f} people/m²"
            return f"density held at about {now:.1f} people/m²"
        if feature == "crowd_pressure":
            verb = {"rising": "rose to", "falling": "fell to", "stable": "stayed near"}[tr]
            return f"crowd pressure (density × velocity variance) {verb} {now:.3f} s⁻²"
        if feature == "bottleneck_pressure":
            verb = {"rising": "rose to", "falling": "eased to", "stable": "stayed at"}[tr]
            return f"inflow {verb} an estimated {now:.1f}× the capacity of the way out"
        if feature == "counterflow_index":
            verb = {"rising": "increased", "falling": "decreased", "stable": "persisted"}[tr]
            return f"opposing movement {verb} (counterflow {now:.2f})"
        if feature == "flow_instability":
            verb = {"rising": "became more irregular", "falling": "became steadier", "stable": "stayed irregular"}[tr]
            return f"movement {verb} (instability {now:.2f})"
        label = FEATURE_LABELS.get(feature, feature).lower()
        return f"{label} was {tr} ({now:.2f})"

    # ---- explanations ---------------------------------------------------------------------
    def explain(self, zone_id: str, state: str, prev_state: str, ranked_features: Sequence[tuple[str, float]],
                values_now: dict[str, float], values_past: dict[str, float]) -> str:
        """``ranked_features``: [(feature, contribution)] sorted by contribution, descending."""
        label = self.zone_label(zone_id)
        if RISK_ORDER[state] > RISK_ORDER[prev_state]:
            head = f"Modelled risk in {label} rose to {state}"
        elif RISK_ORDER[state] < RISK_ORDER[prev_state]:
            head = f"Modelled risk in {label} fell to {state}"
        else:
            head = f"Modelled risk in {label} is {state}"
        top = [f for f, c in ranked_features if c > 1e-3][:2]
        if not top:
            return f"{head}; no crowd-dynamics indicator appears elevated."
        phrases = [self.feature_phrase(f, values_past.get(f, 0.0), values_now.get(f, 0.0)) for f in top]
        if state == "LOW":
            body = phrases[0] if len(phrases) == 1 else f"{phrases[0]}, and {phrases[1]}"
            text = f"{head}. The largest (still modest) contributions: {body}."
        else:
            body = phrases[0] if len(phrases) == 1 else f"{phrases[0]} while {phrases[1]}"
            text = f"{head}, mainly because {body}."
        bp = values_now.get("bottleneck_pressure", 0.0)
        gate = self.portal_near(zone_id)
        if bp >= 1.0 and "bottleneck_pressure" not in top:
            if gate and self.has_own_gate(zone_id):
                where = f"at {gate}"
            elif gate:
                where = f"on the way out towards {gate}"
            else:
                where = f"out of {self.zone_name(zone_id)}"
            text += f" Bottleneck pressure {where} is an estimated {bp:.1f}× its capacity."
        elif bp >= 1.0 and gate:
            text += f" The constraint appears to be on the way out towards {gate}."
        return _capitalise(text)

    # ---- timeline and strategy -------------------------------------------------------------
    def timeline_summary(self, origin_zone: str | None, origin_time: float | None, origin_title: str | None,
                         peak_zone: str | None, peak_time: float | None, peak_state: str | None,
                         chain_titles: Sequence[str]) -> str:
        if origin_zone is None or peak_time is None:
            if peak_time is None:
                return "No escalating risk pattern was identified in this footage."
            return (f"Modelled risk peaked at {peak_state} in {self.zone_label(peak_zone or '')} at "
                    f"{fmt_clock(peak_time)}; no clear causal chain was identified.")
        s1 = (f"The escalation appears to have started in {self.zone_label(origin_zone)} at {fmt_clock(origin_time)}"
              f" with {_decap(origin_title or 'a change in crowd dynamics')}.")
        mid = [c for c in chain_titles[1:-1]][:3]
        s2 = f" It then developed through {', '.join(_decap(m) for m in mid)}." if mid else ""
        s3 = (f" Modelled risk peaked at {peak_state} in {self.zone_label(peak_zone or origin_zone)} at "
              f"{fmt_clock(peak_time)}.")
        return s1 + s2 + s3


def _decap(s: str) -> str:
    """Lower-case the first word unless it is a proper noun (Zone/Gate names)."""
    return s if s.startswith(("Zone", "Gate")) else s[:1].lower() + s[1:]


def _capitalise(s: str) -> str:
    return s[:1].upper() + s[1:] if s else s


def check_language(text: str) -> list[str]:
    """Return banned phrases found in ``text`` (case-insensitive)."""
    low = text.lower()
    return [p for p in BANNED_PHRASES if p in low]
