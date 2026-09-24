from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from rewind.features.zone_features import (
    FeatureEngine,
    WindowInput,
    compute_features,
    downstream_capacity,
    flux_by_zone,
    portal_geometry,
    video_window_inputs,
)
from rewind.schemas.features import ZoneFeatures
from rewind.schemas.simulation import Intervention
from rewind.settings import load_settings
from rewind.venue.demo import build_demo_venue
from rewind.venue.graph import VenueGraph


def test_downstream_capacity_targets_exits() -> None:
    g = VenueGraph(build_demo_venue(), specific_flow=1.3)
    caps = downstream_capacity(g)
    assert caps["C2"] == pytest.approx(3.0 * 1.3)  # only Gate B leads closer to the exit
    assert caps["B2"] == pytest.approx(10.0 * 1.3, rel=1e-3)  # full-width (10 m) opening B2→C2
    g2 = g.apply_interventions([Intervention(type="OPEN_PORTAL", at_t=0, portal_id="GATE_C")], 1)
    assert downstream_capacity(g2)["C3"] == pytest.approx(caps["C3"] + 3.5 * 1.3)  # Gate C adds capacity


def test_engine_rows_validate_against_contract() -> None:
    s = load_settings()
    venue = build_demo_venue()
    eng = FeatureEngine(venue, s)
    rng = np.random.default_rng(0)
    inputs = []
    for k in range(10):
        vec = np.tile([0.0, 1.0], (50, 1)) + rng.normal(0, 0.05, (50, 2))
        if k >= 5:
            vec[:20] = [0.0, -1.0]  # counterflow appears
        inputs.append(WindowInput(t=float(k + 1), zone_id="B2", count=100 + 10 * k, area_m2=66.67, vectors=vec,
                                  inflow=5.0, outflow=3.0, source="fused"))
    df = compute_features(inputs, eng)
    rows = [ZoneFeatures.model_validate(r) for r in df.to_dict("records")]
    assert len(rows) == 10
    assert df["counterflow_index"].iloc[-1] > 0.3 > df["counterflow_index"].iloc[0]
    assert df["density"].is_monotonic_increasing
    assert df["crowd_pressure"].iloc[-1] > df["crowd_pressure"].iloc[0]
    assert df["flow_instability"].max() > 0
    assert df["bottleneck_pressure"].iloc[0] == pytest.approx(5.0 / (10.0 * 1.3), rel=1e-3)


def test_smoothing_is_causal() -> None:
    s = load_settings()
    eng = FeatureEngine(build_demo_venue(), s)
    inputs = [WindowInput(t=float(k + 1), zone_id="A1", count=0 if k < 10 else 60, area_m2=60.0) for k in range(20)]
    df = compute_features(inputs, eng)
    assert (df["density"].iloc[:10] == 0).all()  # no leakage from the future
    assert df["density"].iloc[-1] == pytest.approx(1.0)


def test_flux_by_zone_direction() -> None:
    venue = build_demo_venue()
    portals = portal_geometry(venue)
    # samples straddling the B2→C2 boundary (y = 13.33) moving south at 1 m/s
    xs = np.linspace(11, 19, 40)
    samples = pd.DataFrame({"x": xs, "y": 13.0, "vx": 0.0, "vy": 1.0})
    flux = flux_by_zone(samples, {"B2": 2.0, "C2": 2.0}, portals)
    assert flux["B2"][1] == pytest.approx(2.0 * 1.0 * 10.0, rel=1e-3)  # outflow from B2 (10 m opening)
    assert flux["C2"][0] == pytest.approx(flux["B2"][1])


def test_video_window_inputs_track_mode() -> None:
    s = load_settings()
    venue = build_demo_venue()
    g = VenueGraph(venue)
    # 4 people walking from A2 into B2 across y = 6.67 during the second window
    rows_t, rows_d = [], []
    for pid in range(4):
        for k in range(10):
            t = 0.2 * (k + 1)
            y = 6.0 + 0.2 * k
            rows_t.append({"track_id": str(pid), "t": t, "px_x": 0, "px_y": 0, "wx": 14.0 + pid, "wy": y,
                           "vx": 0.0, "vy": 1.0, "zone_id": "A2" if y < 20 / 3 else "B2"})
    for k in range(10):
        t = 0.2 * (k + 1)
        for z in venue.zone_ids:
            n = 4.0 if (z == "A2" and t <= 1.0) or (z == "B2" and t > 1.0) else 0.0
            rows_d.append({"t": t, "zone_id": z, "count_det": n, "count_map": n, "area_m2": 66.67})
    inputs = video_window_inputs(pd.DataFrame(rows_d), pd.DataFrame(rows_t),
                                 pd.DataFrame(columns=["t", "zone_id", "x", "y", "vx", "vy"]),
                                 pd.DataFrame(columns=["t", "zone_id", "abs_curl"]), venue, g, s)
    by = {(i.t, i.zone_id): i for i in inputs}
    total_in_b2 = sum(i.inflow for (t, z), i in by.items() if z == "B2")
    total_out_a2 = sum(i.outflow for (t, z), i in by.items() if z == "A2")
    assert total_in_b2 == pytest.approx(4.0) and total_out_a2 == pytest.approx(4.0)
    assert by[(2.0, "B2")].source == "tracks"
