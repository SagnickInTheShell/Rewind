from __future__ import annotations

from itertools import pairwise

import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from rewind.explain.contributions import physics_explanations, row_to_explanation
from rewind.explain.narrator import Narrator, check_language
from rewind.fixtures import fake_zone_timeseries
from rewind.risk.ensemble import ModelScores, combine, ensemble_weights, score_features
from rewind.risk.physics_scorer import contribution_matrix, physics_scores, score_one
from rewind.risk.states import RiskStateMachine, level_for
from rewind.schemas.features import NUMERIC_FEATURES
from rewind.settings import load_settings
from rewind.venue.demo import build_demo_venue

S = load_settings()
R = S.risk


def feat_row(**kw: float) -> dict[str, float]:
    base = {f: 0.0 for f in NUMERIC_FEATURES}
    base.update(kw)
    return base


def test_score_bounds_and_saturation() -> None:
    zero, _ = score_one(feat_row(), R)
    assert zero == 0.0
    huge, contrib = score_one(feat_row(**{f: 1e6 for f in NUMERIC_FEATURES}), R)
    assert huge == pytest.approx(1.0)
    assert sum(contrib.values()) == pytest.approx(1.0)


@pytest.mark.parametrize("feature", list(R.weights))
def test_monotone_in_each_feature(feature: str) -> None:
    vals = np.linspace(0, 2 * R.norm[feature], 30)
    base = {"density": 2.0} if feature != "density" else {}  # occupied zone (motion features are gated)
    scores = [score_one(feat_row(**{**base, feature: v}), R)[0] for v in vals]
    assert all(b >= a - 1e-12 for a, b in pairwise(scores))
    assert scores[-1] > scores[0]


def test_more_density_higher_score() -> None:
    df = pd.DataFrame([feat_row(density=d, crowd_pressure=0.01) for d in (1.0, 2.0, 4.0)])
    s = physics_scores(df, R)
    assert s[0] < s[1] < s[2]


def test_contributions_are_exact_decomposition() -> None:
    df = pd.DataFrame(fake_zone_timeseries(duration_s=30).model_dump()["rows"])
    c = contribution_matrix(df, R)
    assert np.allclose(c.sum(axis=1), physics_scores(df, R))


@given(st.lists(st.floats(0, 100, allow_nan=False), min_size=12, max_size=12))
@settings(max_examples=100, deadline=None)
def test_property_score_in_unit_interval(values: list[float]) -> None:
    s, _ = score_one(dict(zip(NUMERIC_FEATURES, values, strict=True)), R)
    assert 0.0 <= s <= 1.0


def test_level_for() -> None:
    th = [0.35, 0.55, 0.75]
    assert [level_for(x, th) for x in (0.1, 0.35, 0.6, 0.9)] == [0, 1, 2, 3]


def test_no_flicker_on_noisy_input() -> None:
    sm = RiskStateMachine(R)
    rng = np.random.default_rng(0)
    t = np.arange(300, dtype=float)
    scores = 0.55 + rng.normal(0, 0.03, 300)  # hovering around the HIGH threshold
    states = sm.run(t, scores)
    changes = sum(a != b for a, b in pairwise(states))
    naive = sum(level_for(a, sm.thresholds) != level_for(b, sm.thresholds) for a, b in pairwise(scores))
    assert changes <= 2 < naive


def test_hysteresis_and_dwell() -> None:
    sm = RiskStateMachine(R)
    t = np.arange(20, dtype=float)
    scores = [0.6] * 5 + [0.52] * 5 + [0.45] * 10  # 0.52 is inside the band (0.55 - 0.05)
    states = sm.run(t, scores)
    assert states[1] == "LOW" and states[2] == "HIGH"  # held for min_dwell_s (3 windows) first
    assert states[8] == "HIGH"  # within hysteresis band
    assert states[14] == "MEDIUM"
    # dwell: an isolated spike does not flip the state
    states2 = sm.run([0, 1, 2, 3, 4], [0.9, 0.1, 0.1, 0.1, 0.1])
    assert states2 == ["LOW"] * 5


def test_overrides_force_high() -> None:
    sm = RiskStateMachine(R)
    t = [0, 1, 2, 3]
    assert sm.run(t, [0.0] * 4, densities=[5.5] * 4)[-1] == "HIGH"
    assert sm.run(t, [0.0] * 4, densities=[2.5] * 4, crowd_pressures=[0.03] * 4)[-1] == "HIGH"
    assert sm.run(t, [0.0] * 4, densities=[0.3] * 4, crowd_pressures=[0.05] * 4)[-1] == "LOW"  # sparse
    assert sm.run(t, [0.9] * 4, densities=[5.5] * 4)[-1] == "CRITICAL"


def test_ensemble_renormalises_missing_models() -> None:
    assert ensemble_weights(R, False, False) == {"physics": 1.0}
    w = ensemble_weights(R, True, False)
    assert w["physics"] == pytest.approx(0.5 / 0.8) and w["temporal"] == pytest.approx(0.3 / 0.8)
    phys = np.array([0.2, 0.8])
    ens, ml = combine(phys, ModelScores(temporal=np.array([0.6, np.nan])), R)
    assert ens[0] == pytest.approx((0.5 * 0.2 + 0.3 * 0.6) / 0.8)
    assert ens[1] == pytest.approx(0.8) and np.isnan(ml[1])


def test_score_features_global_series() -> None:
    df = pd.DataFrame(fake_zone_timeseries(duration_s=180).model_dump()["rows"])
    risk_df, glob = score_features(df, R)
    assert len(risk_df) == len(df) and len(glob) == 180
    assert risk_df["ensemble_score"].between(0, 1).all()
    peak = glob.loc[glob["max_score"].idxmax()]
    assert peak["worst_zone"] in ("B2", "C2")
    assert glob["state"].iloc[-1] in ("HIGH", "CRITICAL")


def test_explanations_and_narratives() -> None:
    venue = build_demo_venue()
    df = pd.DataFrame(fake_zone_timeseries(duration_s=150).model_dump()["rows"])
    risk_df, _ = score_features(df, R)
    ex = physics_explanations(df, risk_df, Narrator(venue, S), S)
    assert len(ex) == len(df)
    row = ex[(ex.zone_id == "B2") & (ex.t == 120.0)].iloc[0].to_dict()
    e = row_to_explanation(row)
    assert e.contributions[0].contribution >= e.contributions[-1].contribution
    assert sum(c.share for c in e.contributions) == pytest.approx(1.0)
    assert e.score == pytest.approx(sum(c.contribution for c in e.contributions), abs=1e-6)
    assert "Zone B2 (near Gate B)" in e.narrative and "Modelled risk" in e.narrative
    for text in ex["narrative"]:
        assert not check_language(text)
        assert text.strip()


def test_narrator_phrases() -> None:
    n = Narrator(build_demo_venue(), S)
    txt = n.explain("B2", "HIGH", "MEDIUM", [("density", 0.2), ("counterflow_index", 0.1)],
                    {"density": 4.6, "counterflow_index": 0.41, "bottleneck_pressure": 1.7},
                    {"density": 2.8, "counterflow_index": 0.1, "bottleneck_pressure": 0.5})
    assert "rose to HIGH" in txt and "climbed from 2.8 to 4.6" in txt and "counterflow 0.41" in txt
    assert "1.7×" in txt
    assert n.trend("density", 3.0, 3.05) == "stable"
    assert check_language("This predicts stampedes") == ["predicts stampedes"]


def test_motion_features_gated_by_occupancy() -> None:
    empty, _ = score_one(feat_row(density=0.01, counterflow_index=0.6, flow_instability=1.0), R)
    busy, _ = score_one(feat_row(density=2.0, counterflow_index=0.6, flow_instability=1.0), R)
    assert empty < 0.01 < busy
