"""Agent routing and waypoint selection through venue graph."""

from __future__ import annotations

import networkx as nx
import numpy as np

from rewind.schemas.venue import Venue
from rewind.venue.graph import VenueGraph


class AgentRouter:
    def __init__(self, venue: Venue, venue_graph: VenueGraph) -> None:
        self.venue = venue
        self.graph = venue_graph
        self.portal_lookup = {p.portal_id: p for p in venue.portals}
        self.zone_lookup = {z.zone_id: z for z in venue.zones}

    def compute_route(
        self,
        from_zone: str,
        target_sink: str,
        densities: dict[str, float] | None = None,
        blocked_portals: set[str] | None = None,
    ) -> list[str]:
        """Return list of zone_ids from from_zone to target_sink."""
        if from_zone == target_sink:
            return [from_zone]
        densities = densities or {}
        blocked = blocked_portals or set()

        def edge_weight(u: str, v: str, d: dict) -> float:
            portal_id = d.get("portal_id", "")
            if portal_id in blocked or not d.get("is_open", True):
                return 1e9
            length = float(d.get("length", 10.0))
            density = densities.get(v, 0.0)
            congestion = 1.0 + 1.5 * max(0.0, density / 4.0)
            return length * congestion

        try:
            path = nx.shortest_path(self.graph.g, source=from_zone, target=target_sink, weight=edge_weight)
            return list(path)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return [from_zone]

    def get_next_waypoint(self, current_zone: str, route: list[str]) -> np.ndarray:
        """Find the target point for the agent in current_zone heading along route."""
        if not route:
            # Fallback to current zone center
            z = self.zone_lookup.get(current_zone)
            if z:
                poly = np.array([[p.x, p.y] for p in z.polygon])
                return np.mean(poly, axis=0)
            return np.array([0.0, 0.0])

        try:
            idx = route.index(current_zone)
        except ValueError:
            idx = -1

        if idx >= 0 and idx < len(route) - 1:
            next_zone = route[idx + 1]
            # Portal between current_zone and next_zone
            portals = self.graph.connecting_portals(current_zone, next_zone)
            if portals:
                p = portals[0]
                a = np.array([p.segment[0].x, p.segment[0].y])
                b = np.array([p.segment[1].x, p.segment[1].y])
                return 0.5 * (a + b)

        # End of route or no connecting portal: head to zone exit portal or centroid
        z = self.zone_lookup.get(current_zone)
        if z:
            # Check if this zone has an exit portal to OUTSIDE
            for p in self.venue.portals:
                if (p.from_zone == current_zone and p.to_zone == "OUTSIDE") or (p.to_zone == current_zone and p.from_zone == "OUTSIDE"):
                    a = np.array([p.segment[0].x, p.segment[0].y])
                    b = np.array([p.segment[1].x, p.segment[1].y])
                    return 0.5 * (a + b)
            poly = np.array([[p.x, p.y] for p in z.polygon])
            return np.mean(poly, axis=0)

        return np.array([0.0, 0.0])
