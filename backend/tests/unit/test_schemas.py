from __future__ import annotations

from collections.abc import Callable

import pytest
from pydantic import BaseModel, ValidationError

from rewind import fixtures as fx
from rewind.schemas import (
    Intervention,
    ScenarioSpec,
    SimulationRequest,
    ZoneFeatures,
)

FACTORIES: list[Callable[[], BaseModel]] = [
    fx.fake_video_meta,
    fx.fake_venue,
    fx.fake_track,
    fx.fake_zone_timeseries,
    fx.fake_explanation,
    fx.fake_timeline,
    fx.fake_run_meta,
    fx.fake_job_status,
    fx.fake_progress_event,
    fx.fake_simulation_request,
    fx.fake_scenario_metrics,
    fx.fake_scenario_result,
    fx.fake_validation_report,
    fx.fake_prevention_plan,
]


@pytest.mark.parametrize("factory", FACTORIES, ids=lambda f: f.__name__)
def test_json_round_trip(factory: Callable[[], BaseModel]) -> None:
    obj = factory()
    again = type(obj).model_validate_json(obj.model_dump_json())
    assert again == obj


def test_list_fixtures_round_trip() -> None:
    for d in fx.fake_detections():
        assert type(d).model_validate_json(d.model_dump_json()) == d
    pts, glob = fx.fake_risk()
    assert pts and glob
    assert type(glob[0]).model_validate_json(glob[0].model_dump_json()) == glob[0]
    frames = fx.fake_agent_frames(n_frames=2, n_agents=3)
    assert type(frames[0]).model_validate_json(frames[0].model_dump_json()) == frames[0]


def test_feature_bounds_enforced() -> None:
    row = fx.fake_zone_timeseries(duration_s=1).rows[0].model_dump()
    row["direction_entropy"] = 1.5
    with pytest.raises(ValidationError):
        ZoneFeatures(**row)


def test_intervention_requirements() -> None:
    with pytest.raises(ValidationError, match="portal_id"):
        Intervention(type="OPEN_PORTAL", at_t=1.0)
    with pytest.raises(ValidationError, match="REDIRECT"):
        Intervention(type="REDIRECT", at_t=1.0, from_zone="B2")
    Intervention(type="RESTRICT_ENTRY", at_t=1.0, factor=0.5)


def test_intervention_before_t0_rejected() -> None:
    with pytest.raises(ValidationError, match="before t0"):
        SimulationRequest(run_id="r", t0=60, scenarios=[ScenarioSpec(
            scenario_id="s", name="s",
            interventions=[Intervention(type="OPEN_PORTAL", at_t=10, portal_id="GATE_C")])])


def test_venue_lookup() -> None:
    v = fx.fake_venue()
    assert v.zone("B2").name == "Zone B2"
    assert v.portal("GATE_A").to_zone == "A2"
    assert len(v.zone_ids) == 9
