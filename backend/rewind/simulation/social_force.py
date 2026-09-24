"""Social Force model (Helbing, Molnár, Farkas, Vicsek formulation)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from rewind.simulation.spatial_hash import SpatialHash2D


@dataclass
class SocialForceParams:
    tau: float = 0.5
    A: float = 2000.0
    B: float = 0.08
    k_body: float = 120000.0
    kappa_friction: float = 240000.0
    mass: float = 80.0
    wall_A: float = 2000.0
    wall_B: float = 0.08
    dt: float = 0.05
    max_speed_factor: float = 1.3


def closest_point_on_segment(p: np.ndarray, a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Find closest point on line segment [a, b] to point p."""
    ab = b - a
    ab_len_sq = np.dot(ab, ab)
    if ab_len_sq < 1e-9:
        return a.copy()
    t = np.clip(np.dot(p - a, ab) / ab_len_sq, 0.0, 1.0)
    return a + t * ab


def step_social_force(
    pos: np.ndarray,            # (N, 2)
    vel: np.ndarray,            # (N, 2)
    desired_speed: np.ndarray,  # (N,)
    targets: np.ndarray,        # (N, 2)
    radii: np.ndarray,          # (N,)
    walls: list[tuple[np.ndarray, np.ndarray]],  # list of (a, b) segments
    params: SocialForceParams,
    spatial_hash: SpatialHash2D | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Execute one simulation step of Social Force.
    Returns: (new_pos, new_vel, local_density)
    """
    n = len(pos)
    if n == 0:
        return pos.copy(), vel.copy(), np.zeros(0, dtype=np.float32)

    if spatial_hash is None:
        spatial_hash = SpatialHash2D(cell_size=1.0)
    spatial_hash.build(pos)

    # 1. Desired driving force
    disp = targets - pos
    dist = np.linalg.norm(disp, axis=1, keepdims=True)
    dist_safe = np.maximum(dist, 1e-4)
    desired_dir = disp / dist_safe
    v_des = desired_dir * desired_speed[:, None]
    f_drive = params.mass * (v_des - vel) / params.tau

    # 2. Agent-agent forces + local density
    f_agent = np.zeros_like(pos)
    local_density = np.zeros(n, dtype=np.float32)
    density_radius = 1.0
    density_area = np.pi * (density_radius ** 2)

    for i in range(n):
        pi = pos[i]
        vi = vel[i]
        ri = radii[i]
        candidates = spatial_hash.query_radius(pi, radius=2.0)

        nbr_count = 0
        for j in candidates:
            if i == j:
                continue
            pj = pos[j]
            vj = vel[j]
            rj = radii[j]

            d_vec = pi - pj
            d = float(np.linalg.norm(d_vec))
            if d < density_radius:
                nbr_count += 1

            if d < 1e-4:
                # Random nudge if overlapping exactly
                d_vec = np.random.uniform(-0.01, 0.01, size=2)
                d = float(np.linalg.norm(d_vec))

            r_sum = ri + rj
            n_ij = d_vec / d
            t_ij = np.array([-n_ij[1], n_ij[0]])

            # Social repulsive force
            f_rep = params.A * np.exp((r_sum - d) / params.B) * n_ij

            # Physical contact forces if touching
            overlap = r_sum - d
            if overlap > 0:
                f_contact = params.k_body * overlap * n_ij
                dv = vj - vi
                f_friction = params.kappa_friction * overlap * np.dot(dv, t_ij) * t_ij
            else:
                f_contact = 0.0
                f_friction = 0.0

            f_agent[i] += f_rep + f_contact + f_friction

        local_density[i] = float(nbr_count) / density_area

    # 3. Wall forces
    f_wall = np.zeros_like(pos)
    if walls:
        for i in range(n):
            pi = pos[i]
            ri = radii[i]
            for a, b in walls:
                pw = closest_point_on_segment(pi, a, b)
                dw_vec = pi - pw
                dw = float(np.linalg.norm(dw_vec))
                if dw < 1e-4:
                    dw_vec = np.array([0.01, 0.01])
                    dw = float(np.linalg.norm(dw_vec))
                nw = dw_vec / dw
                f_w_rep = params.wall_A * np.exp((ri - dw) / params.wall_B) * nw
                overlap = ri - dw
                if overlap > 0:
                    f_w_contact = params.k_body * overlap * nw
                else:
                    f_w_contact = 0.0
                f_wall[i] += f_w_rep + f_w_contact

    # 4. Integrate
    f_total = f_drive + f_agent + f_wall
    acc = f_total / params.mass
    new_vel = vel + params.dt * acc

    # Speed cap
    max_speeds = params.max_speed_factor * desired_speed
    current_speeds = np.linalg.norm(new_vel, axis=1)
    scale = np.minimum(1.0, max_speeds / np.maximum(current_speeds, 1e-4))
    new_vel *= scale[:, None]

    new_pos = pos + params.dt * new_vel

    return new_pos, new_vel, local_density
