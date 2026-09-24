"""Unit tests for simulation and validation engines."""

from __future__ import annotations

import numpy as np

from rewind.simulation.macro_flow import MacroFlowSimulator
from rewind.simulation.social_force import SocialForceParams, step_social_force
from rewind.simulation.spatial_hash import SpatialHash2D
from rewind.venue.demo import build_demo_venue


def test_spatial_hash_neighbors():
    sh = SpatialHash2D(cell_size=1.0)
    pts = np.array([[0.0, 0.0], [0.5, 0.5], [5.0, 5.0]], dtype=np.float32)
    sh.build(pts)
    nbrs = sh.query_radius(np.array([0.0, 0.0]), radius=1.0)
    assert 0 in nbrs
    assert 1 in nbrs
    assert 2 not in nbrs


def test_social_force_step():
    params = SocialForceParams(dt=0.05)
    pos = np.array([[0.0, 0.0], [0.3, 0.0]], dtype=np.float32)
    vel = np.zeros((2, 2), dtype=np.float32)
    speeds = np.array([1.34, 1.34], dtype=np.float32)
    targets = np.array([[10.0, 0.0], [10.0, 0.0]], dtype=np.float32)
    radii = np.array([0.25, 0.25], dtype=np.float32)

    new_pos, new_vel, dens = step_social_force(pos, vel, speeds, targets, radii, walls=[], params=params)
    assert len(new_pos) == 2
    # Agent 0 should be pushed backwards or slowed by agent 1
    assert new_pos[0][0] < new_pos[1][0]


def test_macro_flow_conservation():
    venue = build_demo_venue()
    sim = MacroFlowSimulator(venue, dt=1.0)
    initial_counts = {"A2": 50.0}
    ts = sim.simulate(
        initial_counts=initial_counts,
        inflow_rates={"A2": 0.0},
        interventions=[],
        t0=0.0,
        horizon_s=10.0,
        run_id="test_run",
    )
    assert len(ts.rows) > 0
    # Last row total should not exceed initial plus inflows
    last_t = max(r.t for r in ts.rows)
    last_rows = [r for r in ts.rows if r.t == last_t]
    total_remaining = sum(r.count for r in last_rows)
    assert total_remaining <= 50.0 + 1e-4
