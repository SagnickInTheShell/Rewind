"""Venue graph: zones as nodes, portals as directed edges, plus loading and validation."""

from __future__ import annotations

import json
import math
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import networkx as nx
import numpy as np

from rewind.schemas.simulation import Intervention
from rewind.schemas.venue import OUTSIDE, Portal, Venue
from rewind.venue.geometry import portal_line, portal_midpoint, zone_polygon

BOUNDARY_TOLERANCE_M = 0.2


class VenueValidationError(ValueError):
    def __init__(self, errors: list[str]) -> None:
        super().__init__("; ".join(errors))
        self.errors = errors


@dataclass
class EdgeInfo:
    portal_ids: list[str]
    width_m: float
    capacity: float
    length: float
    is_open: bool


class VenueGraph:
    """Directed graph over zones (+ the virtual ``OUTSIDE`` node).

    Every portal contributes an edge ``from_zone -> to_zone`` (and the reverse when bidirectional).
    Parallel portals between the same pair of zones are merged: widths and capacities add up.
    ``is_open`` is True if any merged portal is open; closed portals do not add width.
    """

    def __init__(self, venue: Venue, specific_flow: float = 1.3) -> None:
        self.venue = venue
        self.specific_flow = specific_flow
        self.g: nx.DiGraph = nx.DiGraph()
        self.area: dict[str, float] = {}
        self.centroid: dict[str, np.ndarray] = {}
        for z in venue.zones:
            poly = zone_polygon(z)
            self.area[z.zone_id] = float(poly.area)
            self.centroid[z.zone_id] = np.array(poly.centroid.coords[0])
            self.g.add_node(z.zone_id, area_m2=poly.area, centroid=tuple(self.centroid[z.zone_id]),
                            polygon=[(p.x, p.y) for p in z.polygon], kind=z.kind)
        self.g.add_node(OUTSIDE, area_m2=math.inf, centroid=None, polygon=[], kind="outside")
        for p in venue.portals:
            self._add_edge(p.from_zone, p.to_zone, p)
            if p.bidirectional:
                self._add_edge(p.to_zone, p.from_zone, p)

    # ---- construction ---------------------------------------------------------------------
    def _node_pos(self, node: str, portal: Portal) -> np.ndarray:
        return self.centroid[node] if node != OUTSIDE else portal_midpoint(portal)

    def _add_edge(self, u: str, v: str, p: Portal) -> None:
        if u not in self.g or v not in self.g:
            return  # reported by validation
        length = float(np.linalg.norm(self._node_pos(u, p) - portal_midpoint(p))
                       + np.linalg.norm(portal_midpoint(p) - self._node_pos(v, p)))
        width = p.width_m if p.is_open else 0.0
        if self.g.has_edge(u, v):
            d = self.g.edges[u, v]
            d["portal_ids"].append(p.portal_id)
            d["width_m"] += width
            d["capacity"] = d["width_m"] * self.specific_flow
            d["is_open"] = d["is_open"] or p.is_open
            d["length"] = min(d["length"], length)
            d["portal_id"] = d["portal_ids"][0]
        else:
            self.g.add_edge(u, v, portal_id=p.portal_id, portal_ids=[p.portal_id], width_m=width,
                            capacity=width * self.specific_flow, length=length, is_open=p.is_open)

    # ---- queries --------------------------------------------------------------------------
    @property
    def zone_ids(self) -> list[str]:
        return [z.zone_id for z in self.venue.zones]

    def open_graph(self) -> nx.DiGraph:
        return self.g.edge_subgraph([(u, v) for u, v, d in self.g.edges(data=True) if d["is_open"]]).copy()

    def edge(self, u: str, v: str) -> EdgeInfo | None:
        if not self.g.has_edge(u, v):
            return None
        d = self.g.edges[u, v]
        return EdgeInfo(list(d["portal_ids"]), d["width_m"], d["capacity"], d["length"], d["is_open"])

    def upstream(self, zone: str) -> set[str]:
        og = self.open_graph()
        if zone not in og:
            return set()
        return {z for z in nx.ancestors(og, zone) if z != OUTSIDE}

    def downstream(self, zone: str) -> set[str]:
        og = self.open_graph()
        if zone not in og:
            return set()
        return {z for z in nx.descendants(og, zone) if z != OUTSIDE}

    def neighbours(self, zone: str) -> set[str]:
        """Physically adjacent zones through any portal (open or closed)."""
        nb = set(self.g.successors(zone)) | set(self.g.predecessors(zone))
        nb.discard(OUTSIDE)
        nb.discard(zone)
        return nb

    def outgoing_capacity(self, zone: str) -> float:
        """Σ capacity of open portals leaving ``zone`` (persons / s)."""
        return float(sum(d["capacity"] for _, _, d in self.g.out_edges(zone, data=True) if d["is_open"]))

    def portals_between(self, a: str, b: str) -> list[Portal]:
        return [p for p in self.venue.portals if {p.from_zone, p.to_zone} == {a, b}]

    def zone_portals(self, zone: str) -> list[Portal]:
        return [p for p in self.venue.portals if zone in (p.from_zone, p.to_zone)]

    def exit_portals(self, zone: str | None = None, open_only: bool = True) -> list[Portal]:
        out = []
        for p in self.venue.portals:
            leaves = p.to_zone == OUTSIDE or (p.bidirectional and p.from_zone == OUTSIDE)
            inner = p.from_zone if p.to_zone == OUTSIDE else p.to_zone
            if leaves and (zone is None or inner == zone) and (p.is_open or not open_only):
                out.append(p)
        return out

    def entry_portals(self, zone: str | None = None) -> list[Portal]:
        out = []
        for p in self.venue.portals:
            enters = p.from_zone == OUTSIDE or (p.bidirectional and p.to_zone == OUTSIDE)
            inner = p.to_zone if p.from_zone == OUTSIDE else p.from_zone
            if enters and (zone is None or inner == zone):
                out.append(p)
        return out

    def nearest_portal(self, zone: str, prefer_gates: bool = True) -> Portal | None:
        candidates = self.zone_portals(zone)
        if prefer_gates:
            gates = [p for p in candidates if p.kind == "gate"]
            candidates = gates or candidates
        if not candidates:
            return None
        c = self.centroid[zone]
        return min(candidates, key=lambda p: float(np.linalg.norm(portal_midpoint(p) - c)))

    def route(self, zone_from: str, densities: dict[str, float] | None = None,
              congestion_weight: float = 0.0, density_high: float = 4.0,
              via: str | None = None) -> list[str] | None:
        """Shortest open path ``zone_from -> ... -> OUTSIDE``.

        Edge weight = length × (1 + congestion_weight × density(target) / density_high).
        With ``via``, the path is forced through that zone. Returns None if no exit is reachable.
        """
        og = self.open_graph()
        if zone_from not in og or OUTSIDE not in og:
            return None
        dens = densities or {}

        def w(u: str, v: str, d: dict[str, float]) -> float:
            rho = dens.get(v, 0.0) if v != OUTSIDE else 0.0
            return float(d["length"]) * (1.0 + congestion_weight * rho / max(density_high, 1e-6))

        try:
            if via and via != zone_from:
                p1 = nx.shortest_path(og, zone_from, via, weight=w)
                p2 = nx.shortest_path(og, via, OUTSIDE, weight=w)
                return list(p1) + list(p2[1:])
            return list(nx.shortest_path(og, zone_from, OUTSIDE, weight=w))
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None

    # ---- interventions ---------------------------------------------------------------------
    def apply_interventions(self, interventions: Iterable[Intervention], t: float) -> VenueGraph:
        """New graph with all portal interventions effective at time ``t`` applied."""
        return VenueGraph(apply_portal_interventions(self.venue, interventions, t), self.specific_flow)


def apply_portal_interventions(venue: Venue, interventions: Iterable[Intervention], t: float) -> Venue:
    v = venue.model_copy(deep=True)
    by_id = {p.portal_id: p for p in v.portals}
    for iv in sorted(interventions, key=lambda i: i.at_t):
        if iv.at_t > t or iv.portal_id is None or iv.portal_id not in by_id:
            continue
        p = by_id[iv.portal_id]
        if iv.type == "OPEN_PORTAL":
            p.is_open = True
        elif iv.type == "CLOSE_PORTAL":
            p.is_open = False
        elif iv.type == "WIDEN_PORTAL" and iv.factor:
            p.width_m = p.width_m * iv.factor
    return v


# ---- loading and validation ----------------------------------------------------------------
def validate_venue(venue: Venue) -> list[str]:
    errors: list[str] = []
    ids = [z.zone_id for z in venue.zones]
    if len(ids) != len(set(ids)):
        errors.append("zone_ids must be unique")
    if OUTSIDE in ids:
        errors.append(f"'{OUTSIDE}' is reserved and cannot be used as a zone_id")
    pids = [p.portal_id for p in venue.portals]
    if len(pids) != len(set(pids)):
        errors.append("portal_ids must be unique")
    known = set(ids) | {OUTSIDE}
    for p in venue.portals:
        for side in (p.from_zone, p.to_zone):
            if side not in known:
                errors.append(f"portal {p.portal_id} references unknown zone '{side}'")
        if p.from_zone == p.to_zone:
            errors.append(f"portal {p.portal_id} connects zone '{p.from_zone}' to itself")
    for s in venue.sources:
        if s not in ids:
            errors.append(f"source '{s}' is not a zone")
    for s in venue.sinks:
        if s not in ids:
            errors.append(f"sink '{s}' is not a zone")
    if not venue.sources:
        errors.append("venue needs at least one source zone")
    if not venue.sinks:
        errors.append("venue needs at least one sink zone")
    if len(venue.calibration.image_points) < 4:
        errors.append("calibration needs at least 4 image/world point pairs")
    for z in venue.zones:
        if not zone_polygon(z).is_valid or zone_polygon(z).area <= 0:
            errors.append(f"zone {z.zone_id} polygon is invalid or has zero area")
    if errors:
        return errors

    # Portal segments must lie on the boundary of the zones they connect.
    for p in venue.portals:
        line = portal_line(p)
        for side in (p.from_zone, p.to_zone):
            if side == OUTSIDE:
                continue
            boundary = zone_polygon(venue.zone(side)).exterior
            dist = max(boundary.distance(line.interpolate(f, normalized=True)) for f in (0.0, 0.5, 1.0))
            if dist > BOUNDARY_TOLERANCE_M:
                errors.append(f"portal {p.portal_id} segment is {dist:.2f} m from the boundary of zone {side} "
                              f"(tolerance {BOUNDARY_TOLERANCE_M} m)")

    # Reachability with every portal open.
    all_open = venue.model_copy(deep=True)
    for p in all_open.portals:
        p.is_open = True
    g = VenueGraph(all_open).open_graph()
    reachable: set[str] = set()
    for s in venue.sources:
        if s in g:
            reachable |= {s} | set(nx.descendants(g, s))
    for zid in ids:
        if zid not in reachable:
            errors.append(f"zone {zid} is not reachable from any source")
    for s in venue.sources:
        if s not in g or OUTSIDE not in g or not nx.has_path(g, s, OUTSIDE):
            errors.append(f"source {s} cannot reach an exit")
    for s in venue.sinks:
        if not any((p.from_zone == s and p.to_zone == OUTSIDE) or (p.bidirectional and p.to_zone == s
                   and p.from_zone == OUTSIDE) for p in venue.portals):
            errors.append(f"sink {s} has no exit portal to {OUTSIDE}")
    return errors


def load_venue(path: Path | str, validate: bool = True) -> Venue:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    venue = Venue.model_validate(data)
    if validate:
        errs = validate_venue(venue)
        if errs:
            raise VenueValidationError(errs)
    return venue


def save_venue(venue: Venue, path: Path | str) -> None:
    Path(path).write_text(venue.model_dump_json(indent=2), encoding="utf-8")
