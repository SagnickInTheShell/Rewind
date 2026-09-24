"""Causal chain over incident events (Section 7.11).

e1 → e2 is a candidate causal edge when e1 precedes e2 by at most ``causal_max_dt_s``, e1's type is a
plausible cause of e2's type (``CAUSES``), and the zones are related: same zone, e1 upstream of e2
(flow propagation), or — for congestion types — e1 adjacent downstream of e2 (queue spill-back).
Edges are weighted by temporal proximity and e1's severity; the main chain is the highest-weight
path ending at PEAK_RISK.
"""

from __future__ import annotations

import networkx as nx

from rewind.schemas.events import EventType, IncidentEvent
from rewind.schemas.risk import RISK_ORDER
from rewind.venue.graph import VenueGraph

CAUSES: dict[str, set[str]] = {
    "ENTRY_SURGE": {"DENSITY_RISING", "DENSITY_THRESHOLD", "BOTTLENECK_FORMED", "RISK_STATE_CHANGE"},
    "DENSITY_RISING": {"DENSITY_THRESHOLD", "BOTTLENECK_FORMED", "COUNTERFLOW_EMERGED", "INSTABILITY_RISING",
                       "RISK_STATE_CHANGE", "SPILLOVER"},
    "DENSITY_THRESHOLD": {"DENSITY_THRESHOLD", "BOTTLENECK_FORMED", "COUNTERFLOW_EMERGED", "INSTABILITY_RISING",
                          "RISK_STATE_CHANGE", "SPILLOVER"},
    "BOTTLENECK_FORMED": {"DENSITY_RISING", "DENSITY_THRESHOLD", "COUNTERFLOW_EMERGED", "INSTABILITY_RISING",
                          "RISK_STATE_CHANGE", "SPILLOVER"},
    "COUNTERFLOW_EMERGED": {"INSTABILITY_RISING", "RISK_STATE_CHANGE", "DENSITY_THRESHOLD"},
    "INSTABILITY_RISING": {"RISK_STATE_CHANGE", "SPILLOVER"},
    "RISK_STATE_CHANGE": {"RISK_STATE_CHANGE", "SPILLOVER"},
    "SPILLOVER": {"RISK_STATE_CHANGE", "DENSITY_THRESHOLD"},
    "DE_ESCALATION": set(),
    "PEAK_RISK": set(),
}
# Every escalation-type event may lead to the peak.
for _k in CAUSES:
    if _k not in ("DE_ESCALATION", "PEAK_RISK"):
        CAUSES[_k].add("PEAK_RISK")

SPILLBACK_TYPES: set[str] = {"BOTTLENECK_FORMED", "DENSITY_THRESHOLD", "DENSITY_RISING", "RISK_STATE_CHANGE"}
SAME_ZONE_BONUS = 1.2
MAX_CAUSES_LISTED = 3


def plausible(cause: EventType, effect: EventType) -> bool:
    return effect in CAUSES.get(cause, set())


class CausalChainBuilder:
    def __init__(self, graph: VenueGraph, max_dt_s: float = 90.0) -> None:
        self.graph = graph
        self.max_dt = max_dt_s
        self._up = {z: graph.upstream(z) for z in graph.zone_ids}
        self._nb = {z: graph.neighbours(z) for z in graph.zone_ids}

    def related(self, e1: IncidentEvent, e2: IncidentEvent) -> bool:
        if e1.zone_id == e2.zone_id:
            return True
        if e1.zone_id in self._up.get(e2.zone_id, set()) and (
                e2.zone_id in self._nb.get(e1.zone_id, set()) or e1.type == "ENTRY_SURGE"
                or e2.type == "PEAK_RISK"):
            return True
        # queue spill-back: congestion downstream raises density/risk in the adjacent upstream zone
        return e1.type in SPILLBACK_TYPES and e2.zone_id in self._nb.get(e1.zone_id, set())

    def weight(self, e1: IncidentEvent, e2: IncidentEvent) -> float:
        dt = e2.t_start - e1.t_start
        w = (1.0 - dt / self.max_dt) * (0.5 + 0.5 * RISK_ORDER[e1.severity] / 3.0)
        return w * (SAME_ZONE_BONUS if e1.zone_id == e2.zone_id else 1.0)

    def build(self, events: list[IncidentEvent]) -> nx.DiGraph:
        dag = nx.DiGraph()
        for e in events:
            dag.add_node(e.event_id, event=e)
        for i, e1 in enumerate(events):
            for e2 in events[i + 1:]:
                dt = e2.t_start - e1.t_start
                if dt < 0 or dt > self.max_dt or e1.event_id == e2.event_id:
                    continue
                if dt == 0 and e1.type == e2.type:
                    continue
                if plausible(e1.type, e2.type) and self.related(e1, e2):
                    dag.add_edge(e1.event_id, e2.event_id, weight=self.weight(e1, e2))
        return dag

    def main_chain(self, dag: nx.DiGraph, events: list[IncidentEvent]) -> list[str]:
        peaks = [e for e in events if e.type == "PEAK_RISK"]
        if not peaks:
            return []
        target = peaks[0].event_id
        best: dict[str, float] = {}
        prev: dict[str, str | None] = {}
        for n in nx.topological_sort(dag):
            cands = [(best[p] + d["weight"], p) for p, _, d in dag.in_edges(n, data=True) if p in best]
            if cands:
                score, p = max(cands)
                best[n], prev[n] = score, p
            else:
                best[n], prev[n] = 0.0, None
        chain: list[str] = []
        cur: str | None = target
        while cur is not None:
            chain.append(cur)
            cur = prev.get(cur)
        return list(reversed(chain))

    def fill_caused_by(self, dag: nx.DiGraph, events: list[IncidentEvent], chain: list[str]) -> None:
        on_chain_prev = {chain[i]: chain[i - 1] for i in range(1, len(chain))}
        for e in events:
            preds = sorted(dag.in_edges(e.event_id, data=True), key=lambda x: -x[2]["weight"])
            ids = [p for p, _, _ in preds[:MAX_CAUSES_LISTED]]
            main = on_chain_prev.get(e.event_id)
            if main and main not in ids:
                ids = [main, *ids[: MAX_CAUSES_LISTED - 1]]
            elif main:
                ids = [main] + [i for i in ids if i != main]
            e.caused_by = ids
