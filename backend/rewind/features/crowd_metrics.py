"""Pure crowd-dynamics metrics on sets of 2-D velocity vectors (m/s).

Every function accepts an ``(n, 2)`` array and returns a float; empty inputs return 0.
"""

from __future__ import annotations

import math

import numpy as np


def _v(vectors: np.ndarray) -> np.ndarray:
    return np.asarray(vectors, dtype=np.float64).reshape(-1, 2)


def speeds(vectors: np.ndarray) -> np.ndarray:
    return np.asarray(np.linalg.norm(_v(vectors), axis=1))


def mean_speed(vectors: np.ndarray) -> float:
    s = speeds(vectors)
    return float(s.mean()) if s.size else 0.0


def speed_var(vectors: np.ndarray) -> float:
    s = speeds(vectors)
    return float(s.var()) if s.size else 0.0


def velocity_var(vectors: np.ndarray) -> float:
    """mean ‖v_i − v̄‖² — variance of the velocity vector field."""
    v = _v(vectors)
    if not len(v):
        return 0.0
    return float(np.mean(np.sum((v - v.mean(axis=0)) ** 2, axis=1)))


def mean_velocity(vectors: np.ndarray) -> np.ndarray:
    v = _v(vectors)
    return v.mean(axis=0) if len(v) else np.zeros(2)


def _moving(vectors: np.ndarray, min_speed: float) -> np.ndarray:
    v = _v(vectors)
    return np.asarray(v[np.linalg.norm(v, axis=1) >= min_speed])


COHERENT_RESULTANT = 0.5


def dominant_dir(vectors: np.ndarray, min_speed: float = 0.1) -> float:
    """Dominant movement direction of moving samples (radians, atan2 convention).

    Coherent flows (mean resultant length ≥ 0.5) use the circular mean of unit vectors. For
    conflicting flows (e.g. two opposing streams) the circular mean is ill-defined, so the main
    movement *axis* is found with the doubled-angle (axial) mean, and the direction along that axis
    carrying the majority of samples is returned.
    """
    v = _moving(vectors, min_speed)
    if not len(v):
        return 0.0
    ang = np.arctan2(v[:, 1], v[:, 0])
    c, s = float(np.cos(ang).mean()), float(np.sin(ang).mean())
    if math.hypot(c, s) >= COHERENT_RESULTANT:
        return float(math.atan2(s, c))
    axis = 0.5 * math.atan2(float(np.sin(2 * ang).mean()), float(np.cos(2 * ang).mean()))
    along = np.cos(ang - axis)
    return float(axis if (along > 0).sum() >= (along < 0).sum() else math.atan2(-math.sin(axis), -math.cos(axis)))


def direction_entropy(vectors: np.ndarray, bins: int = 8, min_speed: float = 0.1) -> float:
    """Speed-weighted Shannon entropy of a ``bins``-bin direction histogram, divided by log(bins)."""
    v = _moving(vectors, min_speed)
    if not len(v):
        return 0.0
    # bins are centred on 0, 2π/bins, ... so axis-aligned flows do not straddle a bin edge
    ang = np.mod(np.arctan2(v[:, 1], v[:, 0]) + math.pi / bins, 2 * math.pi)
    w = np.linalg.norm(v, axis=1)
    hist, _ = np.histogram(ang, bins=bins, range=(0.0, 2 * math.pi), weights=w)
    total = hist.sum()
    if total <= 0:
        return 0.0
    p = hist[hist > 0] / total
    return float(np.clip(-(p * np.log(p)).sum() / math.log(bins), 0.0, 1.0))


def angle_diff(a: np.ndarray | float, b: float) -> np.ndarray:
    """Absolute angular difference in [0, π]."""
    d = np.mod(np.asarray(a) - b + math.pi, 2 * math.pi) - math.pi
    return np.asarray(np.abs(d))


def counterflow_index(vectors: np.ndarray, dominant: float | None = None, angle_deg: float = 120.0,
                      min_speed: float = 0.1) -> float:
    """Share of moving vectors whose direction differs from the dominant one by more than ``angle_deg``."""
    v = _moving(vectors, min_speed)
    if not len(v):
        return 0.0
    dom = dominant_dir(v, min_speed) if dominant is None else dominant
    ang = np.arctan2(v[:, 1], v[:, 0])
    return float(np.mean(angle_diff(ang, dom) > math.radians(angle_deg)))


def flow_instability(mean_v: np.ndarray, prev_mean_v: np.ndarray | None, entropy: float,
                     prev_entropy: float | None, dt: float, abs_curl: float = 0.0) -> float:
    """0.5·(‖v̄_t − v̄_{t−1}‖/Δt + |H_t − H_{t−1}|/Δt) + mean |curl| (curl only for optical-flow sources)."""
    if prev_mean_v is None or prev_entropy is None or dt <= 0:
        return float(max(abs_curl, 0.0))
    accel = float(np.linalg.norm(np.asarray(mean_v) - np.asarray(prev_mean_v))) / dt
    d_ent = abs(entropy - prev_entropy) / dt
    return float(0.5 * (accel + d_ent) + max(abs_curl, 0.0))


def bottleneck_pressure(inflow_rate: float, outgoing_capacity: float) -> float:
    """inflow / Σ capacity of open outgoing portals (capacity = width × specific flow).

    Capped at ``BOTTLENECK_CAP`` so dead-end zones (no open way out) stay finite.
    """
    inflow = max(inflow_rate, 0.0)
    if inflow <= 1e-9:
        return 0.0
    return float(min(inflow / max(outgoing_capacity, 1e-6), BOTTLENECK_CAP))


BOTTLENECK_CAP = 10.0


def crowd_pressure(density: float, vel_var: float) -> float:
    """Helbing et al. (2007): P = ρ · Var(v)."""
    return float(max(density, 0.0) * max(vel_var, 0.0))


def portal_flux(normal_velocities: np.ndarray, density: float, width_m: float) -> tuple[float, float]:
    """Directional flux across a portal (persons/s): (forward along the normal, backward).

    flux = ρ · ⟨max(±v·n, 0)⟩ · width
    """
    vn = np.asarray(normal_velocities, dtype=np.float64).ravel()
    if not vn.size or density <= 0:
        return 0.0, 0.0
    fwd = float(np.mean(np.maximum(vn, 0.0))) * density * width_m
    bwd = float(np.mean(np.maximum(-vn, 0.0))) * density * width_m
    return fwd, bwd
