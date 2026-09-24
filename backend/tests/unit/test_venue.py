from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from rewind.schemas.simulation import Intervention
from rewind.schemas.venue import OUTSIDE, Point
from rewind.venue.demo import build_demo_venue
from rewind.venue.geometry import (
    ZoneLocator,
    portal_normal,
    sample_points_in_polygon,
    wall_segments,
    zone_polygon,
)
from rewind.venue.graph import (
    VenueGraph,
    VenueValidationError,
    load_venue,
    save_venue,
    validate_venue,
)

REPO_DEMO = Path(__file__).resolve().parents[3] / "data" / "venues" / "demo_venue.json"


def test_demo_venue_is_valid() -> None:
    assert validate_venue(build_demo_venue()) == []


def test_committed_demo_json_matches_builder() -> None:
    assert REPO_DEMO.exists(), "run scripts/gen_demo_venue.py"
    assert load_venue(REPO_DEMO) == build_demo_venue()


def test_unknown_zone_reported() -> None:
    v = build_demo_venue()
    v.portals[0].to_zone = "Z9"
    errs = validate_venue(v)
    assert any("unknown zone 'Z9'" in e for e in errs)


def test_unreachable_zone_reported() -> None:
    v = build_demo_venue()
    v.portals = [p for p in v.portals if "B3" not in (p.from_zone, p.to_zone)
                 and "C3" not in (p.from_zone, p.to_zone) and "A3" not in (p.from_zone, p.to_zone)]
    v.sinks = ["C2"]
    errs = validate_venue(v)
    assert any("A3 is not reachable" in e for e in errs)


def test_portal_off_boundary_reported() -> None:
    v = build_demo_venue()
    gate = v.portal("GATE_B")
    gate.segment = (Point(x=13.5, y=18.0), Point(x=16.5, y=18.0))
    errs = validate_venue(v)
    assert any("GATE_B" in e and "boundary" in e for e in errs)


def test_sink_without_exit_reported() -> None:
    v = build_demo_venue()
    v.sinks = ["B2"]
    assert any("sink B2 has no exit" in e for e in validate_venue(v))


def test_load_venue_raises_readable_errors(tmp_path: Path) -> None:
    v = build_demo_venue()
    v.sources = ["NOPE"]
    p = tmp_path / "bad.json"
    p.write_text(v.model_dump_json(), encoding="utf-8")
    with pytest.raises(VenueValidationError) as ei:
        load_venue(p)
    assert "source 'NOPE' is not a zone" in ei.value.errors


def test_save_load_round_trip(tmp_path: Path) -> None:
    p = tmp_path / "v.json"
    save_venue(build_demo_venue(), p)
    assert json.loads(p.read_text())["venue_id"] == "demo_venue"
    assert load_venue(p) == build_demo_venue()


def test_graph_routing_uses_gate_b_when_c_closed() -> None:
    g = VenueGraph(build_demo_venue())
    path = g.route("A2")
    assert path is not None and path[-1] == OUTSIDE and path[-2] == "C2"
    assert g.route("A3", via="C3") is not None  # via C3, still exits through C2 (Gate C closed)


def test_opening_gate_c_offers_new_exit() -> None:
    g = VenueGraph(build_demo_venue())
    assert g.edge("C3", OUTSIDE) is not None and not g.edge("C3", OUTSIDE).is_open  # type: ignore[union-attr]
    g2 = g.apply_interventions([Intervention(type="OPEN_PORTAL", at_t=10, portal_id="GATE_C")], t=20)
    assert g2.route("C3") == ["C3", OUTSIDE]
    # intervention not yet effective
    g3 = g.apply_interventions([Intervention(type="OPEN_PORTAL", at_t=10, portal_id="GATE_C")], t=5)
    assert g3.route("C3") != ["C3", OUTSIDE]


def test_congestion_diverts_route() -> None:
    v = build_demo_venue()
    v.portal("GATE_C").is_open = True
    g = VenueGraph(v)
    assert g.route("B3") == ["B3", "C3", OUTSIDE]
    congested = g.route("B2", densities={"C2": 6.0}, congestion_weight=10.0)
    assert congested is not None and "C3" in congested


def test_widen_updates_capacity() -> None:
    g = VenueGraph(build_demo_venue(), specific_flow=1.3)
    cap = g.outgoing_capacity("C2")
    g2 = g.apply_interventions([Intervention(type="WIDEN_PORTAL", at_t=0, portal_id="GATE_B", factor=1.5)], t=1)
    e1, e2 = g.edge("C2", OUTSIDE), g2.edge("C2", OUTSIDE)
    assert e1 is not None and e2 is not None
    assert e2.capacity == pytest.approx(e1.capacity * 1.5)
    assert g2.outgoing_capacity("C2") > cap


def test_upstream_downstream_neighbours() -> None:
    g = VenueGraph(build_demo_venue())
    assert "A2" in g.upstream("C2")
    assert "C2" in g.downstream("A2")
    assert g.neighbours("B2") == {"A2", "B1", "B3", "C2"}
    assert g.nearest_portal("C2") is not None and g.nearest_portal("C2").portal_id == "GATE_B"  # type: ignore[union-attr]


def test_zone_locator() -> None:
    v = build_demo_venue()
    loc = ZoneLocator(v)
    assert loc.locate(15, 10) == "B2"
    assert loc.locate(-1, -1) is None
    ids = loc.locate_ids(np.array([[1, 1], [29, 19], [15, 10]]))
    assert ids == ["A1", "C3", "B2"]


def test_sampling_spacing_and_containment() -> None:
    v = build_demo_venue()
    poly = zone_polygon(v.zone("B2"))
    pts = sample_points_in_polygon(poly, 60, 0.5, np.random.default_rng(1))
    assert pts.shape == (60, 2)
    d = np.linalg.norm(pts[:, None] - pts[None], axis=-1) + np.eye(60) * 9
    assert d.min() >= 0.5 - 1e-9
    assert all(poly.covers(__import__("shapely").Point(*p)) for p in pts)


def test_sampling_relaxes_when_overfull() -> None:
    v = build_demo_venue()
    poly = zone_polygon(v.zone("B2"))  # ~66 m²
    pts = sample_points_in_polygon(poly, 400, 0.6, np.random.default_rng(1), max_tries=5)
    assert len(pts) == 400


def test_closed_portal_is_wall() -> None:
    v = build_demo_venue()
    segs = wall_segments(v)
    assert len(segs) == len(v.walls) + 1  # Gate C is closed


def test_portal_normal_points_into_to_zone() -> None:
    v = build_demo_venue()
    n = portal_normal(v.portal("GATE_B"), v)  # C2 -> OUTSIDE (south)
    assert n[1] > 0.9
    n = portal_normal(v.portal("GATE_A"), v)  # OUTSIDE -> A2 (south, into the plaza)
    assert n[1] > 0.9
