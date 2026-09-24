"""Post-perception analysis stages: features → risk + explanations → reconstruction."""

from __future__ import annotations

import logging

import pandas as pd

from rewind.explain.contributions import physics_explanations
from rewind.explain.narrator import Narrator
from rewind.features.zone_features import FeatureEngine, compute_features, to_timeseries, video_window_inputs
from rewind.risk.ensemble import score_features
from rewind.schemas.run import RunMeta
from rewind.schemas.venue import Venue
from rewind.settings import Settings
from rewind.storage.run_store import RunStore, write_json
from rewind.venue.graph import VenueGraph

log = logging.getLogger(__name__)


def run_features(store: RunStore, s: Settings, run_id: str, venue: Venue, meta: RunMeta) -> None:
    graph = VenueGraph(venue, s.features.specific_flow_p_per_m_s)
    inputs = video_window_inputs(
        store.read_df(run_id, "density_zone"), store.read_df(run_id, "tracks"),
        store.read_df(run_id, "flow_zone"), store.read_df(run_id, "flow_curl"), venue, graph, s)
    df = compute_features(inputs, FeatureEngine(venue, s, graph))
    store.write_df(run_id, "features", df)
    ts = to_timeseries(df, run_id, "video", s.features.window_s, venue.zone_ids, include_rows=False)
    write_json(store.path(run_id, "features_meta"), ts)
    counts = df["source"].value_counts().to_dict() if not df.empty else {}
    meta.methods["fusion"] = ", ".join(f"{k}: {v}" for k, v in sorted(counts.items()))


def score_run_features(features: pd.DataFrame, venue: Venue, s: Settings) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    """Physics + (optional) ML ensemble → (risk df, global df, method label)."""
    from rewind.risk.ml_scoring import predict_ml

    models, label = predict_ml(features, venue, s)
    risk_df, glob = score_features(features, s.risk, models)
    return risk_df, glob, label


def run_risk(store: RunStore, s: Settings, run_id: str, venue: Venue, meta: RunMeta) -> None:
    features = store.read_df(run_id, "features")
    risk_df, glob, label = score_run_features(features, venue, s)
    store.write_df(run_id, "risk", risk_df)
    store.write_df(run_id, "global_risk", glob)
    narrator = Narrator(venue, s)
    store.write_df(run_id, "explanations", physics_explanations(features, risk_df, narrator, s))
    meta.methods["risk"] = label
