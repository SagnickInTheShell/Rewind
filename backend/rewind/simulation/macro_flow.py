"""Macro flow simulation model for rapid scenario evaluations."""

from __future__ import annotations

import numpy as np

from rewind.schemas.features import ZoneFeatures, ZoneTimeseries
from rewind.schemas.simulation import Intervention
from rewind.schemas.venue import Venue
from rewind.venue.graph import VenueGraph


class MacroFlowSimulator:
    def __init__(
        self,
        venue: Venue,
        v_free: float = 1.34,
        rho_jam: float = 5.4,
        dt: float = 1.0,
    ) -> None:
        self.venue = venue
        self.graph = VenueGraph(venue)
        self.v_free = v_free
        self.rho_jam = rho_jam
        self.dt = dt

        self.zone_areas = {z.zone_id: self.graph.area.get(z.zone_id, 100.0) for z in venue.zones}
        self.portal_lookup = {p.portal_id: p for p in venue.portals}

    def simulate(
        self,
        initial_counts: dict[str, float],
        inflow_rates: dict[str, float],
        interventions: list[Intervention],
        t0: float,
        horizon_s: float,
        run_id: str,
        seed: int = 0,
    ) -> ZoneTimeseries:
        rng = np.random.default_rng(seed)
        n_steps = int(np.ceil(horizon_s / self.dt))
        zones = [z.zone_id for z in self.venue.zones]

        # Current counts
        counts = {z: float(initial_counts.get(z, 0.0)) for z in zones}

        # Track active interventions and portal states
        portal_widths = {p.portal_id: p.width_m for p in self.venue.portals}
        portal_open = {p.portal_id: p.is_open for p in self.venue.portals}
        inflow_factors = {s: 1.0 for s in self.venue.sources}

        rows: list[ZoneFeatures] = []

        for step in range(n_steps):
            current_t = t0 + step * self.dt

            # Apply interventions effective at or before current_t
            for iv in interventions:
                if iv.type != "NONE" and abs(iv.at_t - current_t) < self.dt * 0.5:
                    if iv.type == "OPEN_PORTAL" and iv.portal_id in portal_open:
                        portal_open[iv.portal_id] = True
                    elif iv.type == "CLOSE_PORTAL" and iv.portal_id in portal_open:
                        portal_open[iv.portal_id] = False
                    elif iv.type == "WIDEN_PORTAL" and iv.portal_id in portal_widths and iv.factor:
                        portal_widths[iv.portal_id] *= iv.factor
                    elif iv.type == "RESTRICT_ENTRY" and iv.factor is not None:
                        for s in self.venue.sources:
                            inflow_factors[s] = iv.factor

            # Step 1: Compute densities and desired speeds
            densities = {z: counts[z] / max(self.zone_areas[z], 1.0) for z in zones}
            speeds = {z: max(0.1, self.v_free * (1.0 - min(1.0, densities[z] / self.rho_jam))) for z in zones}

            # Step 2: Compute portal flows
            # Outgoing portal capacities = width * specific_flow (default 1.3)
            flows: dict[str, float] = {}  # portal_id -> flow rate (persons/s)
            zone_inflows = {z: 0.0 for z in zones}
            zone_outflows = {z: 0.0 for z in zones}

            # Sources injection
            for s in self.venue.sources:
                base_in = inflow_rates.get(s, 0.0) * inflow_factors[s]
                zone_inflows[s] += base_in

            for p in self.venue.portals:
                if not portal_open[p.portal_id]:
                    flows[p.portal_id] = 0.0
                    continue

                u, v = p.from_zone, p.to_zone
                cap = portal_widths[p.portal_id] * 1.3
                
                # Flow from u to v
                if u in densities and v in densities:
                    # Flow driven by density gradient and speed
                    demand = densities[u] * speeds[u] * portal_widths[p.portal_id]
                    supply = max(0.0, (self.rho_jam - densities[v])) * speeds[v] * portal_widths[p.portal_id]
                    rate = min(demand, supply, cap)
                    flows[p.portal_id] = rate
                    zone_outflows[u] += rate
                    zone_inflows[v] += rate
                elif u in densities and v == "OUTSIDE":
                    # Exit portal
                    demand = densities[u] * speeds[u] * portal_widths[p.portal_id]
                    rate = min(demand, cap)
                    flows[p.portal_id] = rate
                    zone_outflows[u] += rate

            # Step 3: Mass balance update
            for z in zones:
                net = (zone_inflows[z] - zone_outflows[z]) * self.dt
                counts[z] = max(0.0, counts[z] + net)

            # Step 4: Emit ZoneFeatures for this time step
            for z in zones:
                dens = counts[z] / max(self.zone_areas[z], 1.0)
                spd = speeds[z]
                # Stochastics for realistic metrics
                spd_var = float(np.clip(0.05 + 0.1 * (dens / 3.0), 0.01, 0.5))
                vel_var = float(np.clip(0.04 + 0.08 * (dens / 2.5), 0.01, 0.6))
                dir_entropy = float(np.clip(0.1 + 0.3 * (dens / 3.5), 0.05, 0.95))
                counterflow = float(np.clip(0.05 + 0.25 * (dens / 4.0), 0.0, 0.8))
                instability = float(np.clip(0.05 + 0.3 * (dens / 4.5), 0.0, 1.5))
                
                # Outgoing capacity
                out_cap = sum(portal_widths[p.portal_id] * 1.3 for p in self.venue.portals if p.from_zone == z and portal_open[p.portal_id])
                bottleneck = (zone_inflows[z] / max(out_cap, 0.1)) if out_cap > 0 else 0.0
                crowd_press = dens * vel_var

                rows.append(
                    ZoneFeatures(
                        t=round(current_t, 2),
                        zone_id=z,
                        count=round(counts[z], 1),
                        density=round(dens, 3),
                        mean_speed=round(spd, 3),
                        speed_var=round(spd_var, 3),
                        velocity_var=round(vel_var, 3),
                        dominant_dir=1.57,  # Southbound default
                        direction_entropy=round(dir_entropy, 3),
                        counterflow_index=round(counterflow, 3),
                        flow_instability=round(instability, 3),
                        inflow_rate=round(zone_inflows[z], 2),
                        outflow_rate=round(zone_outflows[z], 2),
                        bottleneck_pressure=round(bottleneck, 3),
                        crowd_pressure=round(crowd_press, 4),
                        source="sim",
                    )
                )

        return ZoneTimeseries(
            run_id=run_id,
            origin="simulation",
            window_s=self.dt,
            zones=zones,
            rows=rows,
        )
