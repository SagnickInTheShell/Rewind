"""Simulation state initialization from reconstructed video state at t0."""

from __future__ import annotations

from dataclasses import dataclass
import numpy as np

from rewind.schemas.venue import Venue
from rewind.venue.geometry import VenueGeometry


@dataclass
class InitialSimState:
    pos: np.ndarray             # (N, 2)
    vel: np.ndarray             # (N, 2)
    desired_speed: np.ndarray   # (N,)
    radii: np.ndarray           # (N,)
    agent_zones: list[str]      # zone_id per agent
    target_sinks: list[str]     # sink zone_id per agent
    routes: list[list[str]]     # route zone_ids per agent
    inflow_rates: dict[str, float]  # source zone_id -> persons/s


class StateInitializer:
    def __init__(self, venue: Venue, rng: np.random.Generator | None = None) -> None:
        self.venue = venue
        self.geom = VenueGeometry(venue)
        self.rng = rng or np.random.default_rng(0)

    def initialize(
        self,
        zone_counts: dict[str, float],
        zone_velocities: dict[str, tuple[float, float]] | None = None,
        source_inflows: dict[str, float] | None = None,
    ) -> InitialSimState:
        zone_velocities = zone_velocities or {}
        source_inflows = source_inflows or {}

        all_pos: list[np.ndarray] = []
        all_vel: list[np.ndarray] = []
        all_speeds: list[float] = []
        all_radii: list[float] = []
        all_zones: list[str] = []
        all_sinks: list[str] = []
        all_routes: list[list[str]] = []

        default_sinks = self.venue.sinks if self.venue.sinks else ["C2"]

        for z in self.venue.zones:
            count = int(round(zone_counts.get(z.zone_id, 0.0)))
            if count <= 0:
                continue

            pts = self.geom.sample_zone(z.zone_id, count, min_dist=0.35, rng=self.rng)
            if len(pts) == 0:
                continue

            base_v = zone_velocities.get(z.zone_id, (0.0, 0.5))
            for pt in pts:
                all_pos.append(pt)
                v = np.array(base_v) + self.rng.normal(0, 0.1, size=2)
                all_vel.append(v)
                all_speeds.append(float(np.clip(self.rng.normal(1.34, 0.2), 0.8, 2.0)))
                all_radii.append(float(self.rng.uniform(0.22, 0.28)))
                all_zones.append(z.zone_id)
                # Assign nearest sink
                chosen_sink = self.rng.choice(default_sinks)
                all_sinks.append(chosen_sink)
                all_routes.append([z.zone_id, chosen_sink])

        pos_arr = np.array(all_pos) if all_pos else np.zeros((0, 2), dtype=np.float32)
        vel_arr = np.array(all_vel) if all_vel else np.zeros((0, 2), dtype=np.float32)
        speed_arr = np.array(all_speeds) if all_speeds else np.zeros(0, dtype=np.float32)
        radii_arr = np.array(all_radii) if all_radii else np.zeros(0, dtype=np.float32)

        return InitialSimState(
            pos=pos_arr,
            vel=vel_arr,
            desired_speed=speed_arr,
            radii=radii_arr,
            agent_zones=all_zones,
            target_sinks=all_sinks,
            routes=all_routes,
            inflow_rates=source_inflows,
        )
