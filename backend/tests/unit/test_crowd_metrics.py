from __future__ import annotations

import math

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.extra.numpy import arrays

from rewind.features import crowd_metrics as cm

RNG = np.random.default_rng(0)


def uniform_flow(n: int = 200, speed: float = 1.2, angle: float = 0.3) -> np.ndarray:
    return np.tile([speed * math.cos(angle), speed * math.sin(angle)], (n, 1))


def opposing_streams(n: int = 200) -> np.ndarray:
    half = n // 2
    return np.vstack([np.tile([1.0, 0.0], (half, 1)), np.tile([-1.0, 0.0], (n - half, 1))])


def random_dirs(n: int = 20000) -> np.ndarray:
    a = RNG.uniform(0, 2 * math.pi, n)
    return np.stack([np.cos(a), np.sin(a)], 1)


def test_uniform_flow() -> None:
    v = uniform_flow()
    assert cm.direction_entropy(v) == pytest.approx(0.0, abs=1e-9)
    assert cm.counterflow_index(v) == 0.0
    assert cm.mean_speed(v) == pytest.approx(1.2)
    assert cm.speed_var(v) == pytest.approx(0.0, abs=1e-12)
    assert cm.velocity_var(v) == pytest.approx(0.0, abs=1e-12)
    assert cm.dominant_dir(v) == pytest.approx(0.3)


def test_opposing_streams() -> None:
    v = opposing_streams()
    v = v + RNG.normal(0, 0.01, v.shape)  # break the exact tie in the circular mean
    assert cm.counterflow_index(v) == pytest.approx(0.5, abs=0.02)
    assert cm.direction_entropy(v) == pytest.approx(math.log(2) / math.log(8), abs=0.02)
    assert cm.velocity_var(v) == pytest.approx(1.0, abs=0.02)


def test_counterflow_minority() -> None:
    v = np.vstack([np.tile([1.0, 0.0], (80, 1)), np.tile([-1.0, 0.0], (20, 1))])
    assert cm.counterflow_index(v) == pytest.approx(0.2)


def test_random_directions_max_entropy() -> None:
    assert cm.direction_entropy(random_dirs()) == pytest.approx(1.0, abs=0.01)


def test_slow_vectors_ignored_for_direction() -> None:
    v = np.vstack([uniform_flow(50), RNG.normal(0, 0.01, (500, 2))])
    assert cm.direction_entropy(v) == pytest.approx(0.0, abs=1e-9)
    assert cm.counterflow_index(v) == 0.0


def test_empty_inputs() -> None:
    e = np.zeros((0, 2))
    for fn in (cm.mean_speed, cm.speed_var, cm.velocity_var, cm.dominant_dir, cm.direction_entropy,
               cm.counterflow_index):
        assert fn(e) == 0.0


def test_crowd_pressure_and_bottleneck() -> None:
    assert cm.crowd_pressure(4.0, 0.01) == pytest.approx(0.04)
    assert cm.bottleneck_pressure(3.9, 3.9) == pytest.approx(1.0)
    assert cm.bottleneck_pressure(0.0, 0.0) == 0.0
    assert cm.bottleneck_pressure(5.0, 0.0) == cm.BOTTLENECK_CAP


def test_flow_instability() -> None:
    assert cm.flow_instability(np.array([1.0, 0]), None, 0.2, None, 1.0) == 0.0
    val = cm.flow_instability(np.array([1.0, 0]), np.array([0.0, 0]), 0.5, 0.3, 1.0)
    assert val == pytest.approx(0.5 * (1.0 + 0.2))
    same = cm.flow_instability(np.array([1.0, 0]), np.array([1.0, 0]), 0.3, 0.3, 1.0, abs_curl=0.4)
    assert same == pytest.approx(0.4)


def test_portal_flux() -> None:
    fwd, bwd = cm.portal_flux(np.array([1.0, 1.0, -1.0, -1.0]), density=2.0, width_m=3.0)
    assert fwd == pytest.approx(3.0) and bwd == pytest.approx(3.0)
    assert cm.portal_flux(np.array([]), 2.0, 3.0) == (0.0, 0.0)


vectors = arrays(np.float64, st.tuples(st.integers(0, 60), st.just(2)),
                 elements=st.floats(-5, 5, allow_nan=False, allow_infinity=False))


@given(vectors)
@settings(max_examples=150, deadline=None)
def test_property_ranges(v: np.ndarray) -> None:
    assert 0.0 <= cm.direction_entropy(v) <= 1.0
    assert 0.0 <= cm.counterflow_index(v) <= 1.0
    assert cm.velocity_var(v) >= 0 and cm.speed_var(v) >= -1e-12
    assert -math.pi - 1e-9 <= cm.dominant_dir(v) <= math.pi + 1e-9
