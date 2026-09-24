from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from rewind.explain.narrator import check_language
from rewind.reconstruction.causal_chain import CausalChainBuilder, plausible
from rewind.reconstruction.event_detector import RawEvent, merge_events, rolling_slope, runs
from rewind.reconstruction.timeline import build_timeline
from rewind.risk.ensemble import score_features
from rewind.schemas.events import IncidentEvent
from rewind.schemas.features import NUMERIC_FEATURES
from rewind.settings import load_settings
from rewind.venue.demo import build_demo_venue
from rewind.venue.graph import VenueGraph

S = load_settings()


def ramp(t: np.ndarray, start: float, end: float, lo: float, hi: float) -> np.ndarray:
    return lo + (hi - lo) * np.clip((t - start) / (end - start), 0, 1)


def escalation_features(duration: int = 200) -> pd.DataFrame:
    """Hand-built escalation: surge at Gate A (t=70) → density rises in B2 → bottleneck at C2 →
    counterflow in B2 → peak in B2 around t=160."""
    t = np.arange(1, duration + 1, dtype=float)
    rows = []
    rng = np.random.default_rng(0)
    for z in [f"{r}{c}" for r in "ABC" for c in (1, 2, 3)]:
        f = {k: np.zeros_like(t) for k in NUMERIC_FEATURES}
        f["density"] = np.full_like(t, 0.4)
        f["mean_speed"] = np.full_like(t, 1.2)
        f["velocity_var"] = np.full_like(t, 0.02)
        if z == "A2":
            f["inflow_rate"] = np.where(t >= 70, 6.0, 2.0) + rng.normal(0, 0.05, len(t))
            f["density"] = ramp(t, 70, 100, 0.4, 1.2)
        if z == "B2":
            f["density"] = ramp(t, 85, 160, 0.4, 5.3)
            f["velocity_var"] = ramp(t, 110, 160, 0.02, 0.012)
            f["counterflow_index"] = ramp(t, 125, 150, 0.0, 0.5)
            f["flow_instability"] = ramp(t, 130, 160, 0.1, 0.9)
            f["bottleneck_pressure"] = ramp(t, 100, 150, 0.3, 1.6)
        if z == "C2":
            f["density"] = ramp(t, 90, 150, 0.4, 3.8)
            f["bottleneck_pressure"] = ramp(t, 85, 110, 0.4, 1.8)
        f["crowd_pressure"] = f["density"] * f["velocity_var"]
        f["count"] = f["density"] * 66.7
        for i, tt in enumerate(t):
            rows.append({"t": tt, "zone_id": z, "dominant_dir": 1.57, "source": "fused",
                         **{k: float(v[i]) for k, v in f.items()}})
    return pd.DataFrame(rows)


def test_runs_and_slope() -> None:
    t = np.arange(1, 21, dtype=float)
    cond = (t >= 5) & (t <= 12)
    assert runs(t, cond, 5.0, 1.0) == [(5.0, 12.0)]
    assert runs(t, cond, 10.0, 1.0) == []
    assert rolling_slope(t, 2 * t, 5.0)[-1] == pytest.approx(2.0)


def test_merge_consecutive_duplicates() -> None:
    a = RawEvent(10, 20, "B2", "BOTTLENECK_FORMED", "MEDIUM", "x", "", {"bottleneck_pressure": 1.2})
    b = RawEvent(23, 30, "B2", "BOTTLENECK_FORMED", "HIGH", "x", "", {"bottleneck_pressure": 1.5})
    c = RawEvent(80, 90, "B2", "BOTTLENECK_FORMED", "HIGH", "x", "", {})
    m = merge_events([a, b, c], gap_s=5)
    assert len(m) == 2 and m[0].t_end == 30 and m[0].severity == "HIGH"
    assert m[0].evidence["bottleneck_pressure"] == 1.5


def test_cause_matrix() -> None:
    assert plausible("ENTRY_SURGE", "DENSITY_RISING")
    assert plausible("BOTTLENECK_FORMED", "COUNTERFLOW_EMERGED")
    assert plausible("INSTABILITY_RISING", "RISK_STATE_CHANGE")
    assert not plausible("DE_ESCALATION", "PEAK_RISK")
    assert not plausible("PEAK_RISK", "ENTRY_SURGE")


def test_synthetic_escalation_chain_and_origin() -> None:
    venue = build_demo_venue()
    graph = VenueGraph(venue)
    feats = escalation_features()
    risk_df, glob = score_features(feats, S.risk)
    tl = build_timeline("r", feats, risk_df, glob, graph, S)
    types = [e.type for e in tl.events]
    for expected in ("ENTRY_SURGE", "DENSITY_RISING", "DENSITY_THRESHOLD", "BOTTLENECK_FORMED",
                     "COUNTERFLOW_EMERGED", "RISK_STATE_CHANGE", "PEAK_RISK"):
        assert expected in types, expected
    assert [e.t_start for e in tl.events] == sorted(e.t_start for e in tl.events)
    assert tl.origin_zone == "A2"
    assert tl.origin_time == pytest.approx(70.0, abs=2)
    by = {e.event_id: e for e in tl.events}
    chain = [by[i] for i in tl.chain]
    assert chain[0].type == "ENTRY_SURGE" and chain[-1].type == "PEAK_RISK"
    assert chain[-1].zone_id == "B2"
    assert all(a.t_start <= b.t_start for a, b in zip(chain, chain[1:], strict=False))
    assert len(chain) >= 3
    for prev, nxt in zip(chain, chain[1:], strict=False):
        assert prev.event_id in nxt.caused_by
    assert "Zone A2" in tl.summary and "started" in tl.summary
    assert not check_language(tl.summary)
    bottleneck = next(e for e in tl.events if e.type == "BOTTLENECK_FORMED" and e.zone_id == "C2")
    assert bottleneck.title == "Bottleneck detected at Gate B"


def test_no_escalation_quiet_timeline() -> None:
    venue = build_demo_venue()
    feats = escalation_features()
    feats[NUMERIC_FEATURES] = 0.0
    feats["density"] = 0.2
    risk_df, glob = score_features(feats, S.risk)
    tl = build_timeline("r", feats, risk_df, glob, VenueGraph(venue), S)
    assert tl.chain == [] and "No escalating risk pattern" in tl.summary


def test_spillback_edge_allowed() -> None:
    g = VenueGraph(build_demo_venue())
    b = CausalChainBuilder(g)
    e_c2 = IncidentEvent(event_id="a", t_start=10, t_end=None, zone_id="C2", type="BOTTLENECK_FORMED",
                         severity="HIGH", title="", detail="", evidence={}, caused_by=[])
    e_b2 = IncidentEvent(event_id="b", t_start=30, t_end=None, zone_id="B2", type="DENSITY_RISING",
                         severity="MEDIUM", title="", detail="", evidence={}, caused_by=[])
    e_a1 = IncidentEvent(event_id="c", t_start=30, t_end=None, zone_id="A1", type="DENSITY_RISING",
                         severity="MEDIUM", title="", detail="", evidence={}, caused_by=[])
    assert b.related(e_c2, e_b2)  # C2 queue spills back into adjacent B2
    assert not b.related(e_c2, e_a1)
    assert b.weight(e_c2, e_b2) > 0
