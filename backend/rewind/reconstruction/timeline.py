"""Assemble the :class:`IncidentTimeline` (events + causal chain + narrated summary)."""

from __future__ import annotations

import pandas as pd

from rewind.explain.narrator import Narrator
from rewind.reconstruction.causal_chain import CausalChainBuilder
from rewind.reconstruction.event_detector import EventDetector, to_incident_events
from rewind.schemas.events import IncidentTimeline
from rewind.settings import Settings
from rewind.venue.graph import VenueGraph


def build_timeline(run_id: str, features: pd.DataFrame, risk_df: pd.DataFrame, global_df: pd.DataFrame,
                   graph: VenueGraph, settings: Settings) -> IncidentTimeline:
    narrator = Narrator(graph.venue, settings, graph)
    raw = EventDetector(graph, settings, narrator).detect(features, risk_df, global_df)
    events, _ = to_incident_events(raw)
    builder = CausalChainBuilder(graph, settings.events.causal_max_dt_s)
    dag = builder.build(events)
    chain = builder.main_chain(dag, events)
    builder.fill_caused_by(dag, events, chain)
    by_id = {e.event_id: e for e in events}
    origin = by_id[chain[0]] if chain else None
    peak = next((e for e in events if e.type == "PEAK_RISK"), None)
    summary = narrator.timeline_summary(
        origin.zone_id if origin and len(chain) > 1 else None,
        origin.t_start if origin and len(chain) > 1 else None,
        origin.title if origin else None,
        peak.zone_id if peak else None, peak.t_start if peak else None, peak.severity if peak else None,
        [by_id[c].title for c in chain])
    return IncidentTimeline(run_id=run_id, events=events,
                            origin_zone=origin.zone_id if origin else None,
                            origin_time=origin.t_start if origin else None, chain=chain, summary=summary)
