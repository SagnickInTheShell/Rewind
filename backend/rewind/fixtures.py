"""Fixture factories producing plausible fake data for every contract.

Used by tests, the data-contract generator and early frontend development. All factories are
deterministic given ``seed``.
"""

from __future__ import annotations

import math

import numpy as np

from rewind.schemas.events import IncidentEvent, IncidentTimeline
from rewind.schemas.features import ZoneFeatures, ZoneTimeseries
from rewind.schemas.perception import Detection, Track, TrackPoint
from rewind.schemas.risk import Contribution, Explanation, GlobalRiskPoint, RiskPoint, RiskState
from rewind.schemas.run import JobStatus, ProgressEvent, RunMeta
from rewind.schemas.simulation import (
    AgentFrame,
    Intervention,
    ScenarioMetrics,
    ScenarioResult,
    ScenarioSpec,
    SimulationRequest,
)
from rewind.schemas.validation import PreventionPlan, Recommendation, ValidationReport
from rewind.schemas.venue import CameraCalibration, Point, Portal, Venue, Wall, Zone
from rewind.schemas.video import VideoMeta

ROWS = "ABC"


def _state(score: float) -> RiskState:
    if score >= 0.75:
        return "CRITICAL"
    if score >= 0.55:
        return "HIGH"
    if score >= 0.35:
        return "MEDIUM"
    return "LOW"


def fake_video_meta(video_id: str = "vid_fixture") -> VideoMeta:
    return VideoMeta(
        video_id=video_id,
        filename="fixture.mp4",
        fps_native=25.0,
        fps_processed=5.0,
        width=1280,
        height=720,
        duration_s=180.0,
        frame_count=4500,
    )


def fake_venue(width: float = 30.0, height: float = 20.0) -> Venue:
    """A 3x3 grid venue (rows A..C north to south, cols 1..3 west to east)."""
    cw, ch = width / 3, height / 3
    zones: list[Zone] = []
    for r, row in enumerate(ROWS):
        for c in range(3):
            x0, y0 = c * cw, r * ch
            zones.append(
                Zone(
                    zone_id=f"{row}{c + 1}",
                    name=f"Zone {row}{c + 1}",
                    polygon=[Point(x=x0, y=y0), Point(x=x0 + cw, y=y0),
                             Point(x=x0 + cw, y=y0 + ch), Point(x=x0, y=y0 + ch)],
                    kind="floor",
                )
            )
    portals: list[Portal] = []
    for r, row in enumerate(ROWS):
        for c in range(3):
            if c < 2:
                x = (c + 1) * cw
                portals.append(Portal(
                    portal_id=f"C_{row}{c + 1}_{row}{c + 2}", name=f"{row}{c + 1}-{row}{c + 2}",
                    from_zone=f"{row}{c + 1}", to_zone=f"{row}{c + 2}",
                    segment=(Point(x=x, y=r * ch), Point(x=x, y=(r + 1) * ch)),
                    width_m=ch, kind="corridor"))
            if r < 2:
                y = (r + 1) * ch
                nxt = ROWS[r + 1]
                portals.append(Portal(
                    portal_id=f"C_{row}{c + 1}_{nxt}{c + 1}", name=f"{row}{c + 1}-{nxt}{c + 1}",
                    from_zone=f"{row}{c + 1}", to_zone=f"{nxt}{c + 1}",
                    segment=(Point(x=c * cw, y=y), Point(x=(c + 1) * cw, y=y)),
                    width_m=cw, kind="corridor"))
    portals.append(Portal(portal_id="GATE_A", name="Gate A", from_zone="OUTSIDE", to_zone="A2",
                          segment=(Point(x=13.0, y=0.0), Point(x=17.0, y=0.0)), width_m=4.0,
                          bidirectional=False, kind="gate"))
    portals.append(Portal(portal_id="GATE_B", name="Gate B", from_zone="C2", to_zone="OUTSIDE",
                          segment=(Point(x=13.5, y=height), Point(x=16.5, y=height)), width_m=3.0,
                          bidirectional=False, kind="gate"))
    walls = [
        Wall(a=Point(x=0, y=0), b=Point(x=width, y=0)),
        Wall(a=Point(x=width, y=0), b=Point(x=width, y=height)),
        Wall(a=Point(x=width, y=height), b=Point(x=0, y=height)),
        Wall(a=Point(x=0, y=height), b=Point(x=0, y=0)),
    ]
    return Venue(
        venue_id="fixture_venue", name="Fixture Plaza",
        bounds=(Point(x=0, y=0), Point(x=width, y=height)),
        zones=zones, portals=portals, walls=walls, sources=["A2"], sinks=["C2"],
        calibration=CameraCalibration(
            image_points=[Point(x=0, y=0), Point(x=1280, y=0), Point(x=1280, y=720), Point(x=0, y=720)],
            world_points=[Point(x=0, y=0), Point(x=width, y=0), Point(x=width, y=height),
                          Point(x=0, y=height)],
        ),
    )


def fake_detections(t: float = 0.0, n: int = 5, seed: int = 0) -> list[Detection]:
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        x, y = rng.uniform(0, 1200), rng.uniform(0, 640)
        out.append(Detection(t=t, bbox_xyxy=(x, y, x + 30, y + 80), conf=float(rng.uniform(0.3, 1))))
    return out


def fake_track(track_id: str = "1", n: int = 10) -> Track:
    pts = [
        TrackPoint(t=i * 0.2, px=(100 + 5 * i, 200.0), world=(5 + 0.25 * i, 3.0),
                   vel=(1.25, 0.0), zone_id="A1")
        for i in range(n)
    ]
    return Track(track_id=track_id, points=pts)


def escalation_profile(t: float, zone: str, t_peak: float = 120.0) -> float:
    """0..1 intensity: B2/C2 escalate first, neighbours follow later and weaker."""
    lag = {"A2": -20.0, "B2": 0.0, "C2": 5.0, "B1": 20.0, "B3": 25.0, "C1": 30.0, "C3": 30.0}
    amp = {"A2": 0.5, "B2": 1.0, "C2": 0.95, "B1": 0.6, "B3": 0.55, "C1": 0.45, "C3": 0.45}
    a = amp.get(zone, 0.25)
    x = (t - (t_peak - 60.0 + lag.get(zone, 40.0))) / 25.0
    return a / (1.0 + math.exp(-x))


def fake_zone_timeseries(run_id: str = "run_fixture", duration_s: float = 180.0,
                         seed: int = 0) -> ZoneTimeseries:
    rng = np.random.default_rng(seed)
    zones = [f"{r}{c}" for r in ROWS for c in (1, 2, 3)]
    rows: list[ZoneFeatures] = []
    for k in range(int(duration_s)):
        t = float(k + 1)
        for z in zones:
            e = escalation_profile(t, z)
            dens = 0.5 + 5.0 * e + float(rng.normal(0, 0.05))
            vvar = 0.02 + 0.3 * e * e
            area = 66.67
            rows.append(ZoneFeatures(
                t=t, zone_id=z, count=max(dens, 0) * area, density=max(dens, 0.0),
                mean_speed=max(1.3 * (1 - 0.8 * e), 0.0), speed_var=0.05 + 0.1 * e,
                velocity_var=vvar, dominant_dir=math.pi / 2,
                direction_entropy=min(0.2 + 0.7 * e, 1.0), counterflow_index=min(0.05 + 0.5 * e, 1.0),
                flow_instability=0.1 + 0.8 * e, inflow_rate=2.0 + 6.0 * e, outflow_rate=2.0 + 2.0 * e,
                bottleneck_pressure=0.3 + 2.0 * e, crowd_pressure=max(dens, 0) * vvar * 0.1,
                source="fused" if dens > 1.5 else "tracks",
            ))
    return ZoneTimeseries(run_id=run_id, origin="video", window_s=1.0, zones=zones, rows=rows)


def fake_risk(ts: ZoneTimeseries | None = None) -> tuple[list[RiskPoint], list[GlobalRiskPoint]]:
    ts = ts or fake_zone_timeseries()
    pts: list[RiskPoint] = []
    by_t: dict[float, list[RiskPoint]] = {}
    for r in ts.rows:
        score = min(max(escalation_profile(r.t, r.zone_id) * 0.95, 0.0), 1.0)
        rp = RiskPoint(t=r.t, zone_id=r.zone_id, physics_score=score, ml_score=min(score * 1.05, 1.0),
                       ensemble_score=score, state=_state(score))
        pts.append(rp)
        by_t.setdefault(r.t, []).append(rp)
    glob = []
    for t, group in sorted(by_t.items()):
        w = max(group, key=lambda p: p.ensemble_score)
        glob.append(GlobalRiskPoint(t=t, max_score=w.ensemble_score, worst_zone=w.zone_id, state=w.state))
    return pts, glob


def fake_explanation(t: float = 120.0, zone_id: str = "B2") -> Explanation:
    contribs = [
        Contribution(feature="density", label="Density", value=4.6, contribution=0.19, share=0.35),
        Contribution(feature="crowd_pressure", label="Crowd pressure", value=0.03, contribution=0.15,
                     share=0.28),
        Contribution(feature="bottleneck_pressure", label="Bottleneck pressure", value=1.7,
                     contribution=0.12, share=0.22),
        Contribution(feature="counterflow_index", label="Counterflow", value=0.41, contribution=0.05,
                     share=0.09),
        Contribution(feature="flow_instability", label="Flow instability", value=0.2,
                     contribution=0.03, share=0.06),
    ]
    return Explanation(
        t=t, zone_id=zone_id, score=0.54, state="MEDIUM", contributions=contribs,
        method="physics_weights",
        narrative="Risk in Zone B2 (near Gate B) appears to have risen mainly because density climbed "
        "from 2.8 to 4.6 people/m² while opposing movement increased (counterflow 0.41).",
    )


def fake_timeline(run_id: str = "run_fixture") -> IncidentTimeline:
    specs = [
        ("e1", 40.0, "A2", "ENTRY_SURGE", "MEDIUM", "Entry surge at Gate A"),
        ("e2", 55.0, "B2", "DENSITY_RISING", "MEDIUM", "Density rising in Zone B2"),
        ("e3", 75.0, "C2", "BOTTLENECK_FORMED", "HIGH", "Bottleneck detected at Gate B"),
        ("e4", 90.0, "B2", "COUNTERFLOW_EMERGED", "HIGH", "Counterflow emerged in Zone B2"),
        ("e5", 100.0, "B2", "RISK_STATE_CHANGE", "HIGH", "Zone B2 risk rose to HIGH"),
        ("e6", 120.0, "B2", "PEAK_RISK", "CRITICAL", "Peak modelled risk in Zone B2"),
    ]
    events = []
    prev: str | None = None
    for eid, t, z, typ, sev, title in specs:
        events.append(IncidentEvent(
            event_id=eid, t_start=t, t_end=t + 10, zone_id=z, type=typ, severity=sev,  # type: ignore[arg-type]
            title=title, detail=title + ".", evidence={"density": 3.0}, caused_by=[prev] if prev else []))
        prev = eid
    return IncidentTimeline(
        run_id=run_id, events=events, origin_zone="A2", origin_time=40.0,
        chain=[e.event_id for e in events],
        summary="The escalation appears to have originated with an entry surge at Gate A at 0:40.",
    )


def fake_run_meta(run_id: str = "run_fixture") -> RunMeta:
    return RunMeta(run_id=run_id, video=fake_video_meta(), venue_id="fixture_venue",
                   methods={"detector": "yolov8s", "tracker": "bytetrack", "density": "kde"},
                   config_hash="abc123", status="DONE", created_at="2026-01-01T00:00:00Z")


def fake_job_status() -> JobStatus:
    return JobStatus(job_id="job_1", kind="analysis", state="RUNNING", stage="tracking", percent=42.0)


def fake_progress_event() -> ProgressEvent:
    return ProgressEvent(stage="tracking", percent=42.0, message="Tracking people", eta_s=30.0)


def fake_simulation_request(run_id: str = "run_fixture") -> SimulationRequest:
    return SimulationRequest(
        run_id=run_id, t0=60.0, horizon_s=120.0,
        scenarios=[ScenarioSpec(scenario_id="open_c", name="Open Gate C",
                                interventions=[Intervention(type="OPEN_PORTAL", at_t=60.0,
                                                            portal_id="GATE_C")])],
        seeds=[0, 1], model="macro",
    )


def fake_agent_frames(n_frames: int = 20, n_agents: int = 50, seed: int = 0) -> list[AgentFrame]:
    rng = np.random.default_rng(seed)
    xy = rng.uniform([0, 0], [30, 20], size=(n_agents, 2))
    frames = []
    for k in range(n_frames):
        xy = xy + rng.normal(0, 0.1, size=xy.shape)
        frames.append(AgentFrame(t=60 + k * 0.1, xy=[(float(a), float(b)) for a, b in xy],
                                 local_density=[float(v) for v in rng.uniform(0, 5, n_agents)]))
    return frames


def fake_scenario_metrics() -> ScenarioMetrics:
    return ScenarioMetrics(peak_density=4.8, peak_density_zone="B2", peak_crowd_pressure=0.031,
                           time_in_high_s=45.0, time_in_critical_s=12.0, max_state="CRITICAL",
                           mean_evacuation_rate=2.1, agents_remaining=120,
                           seed_std={"peak_density": 0.2, "time_in_high_s": 5.0})


def fake_scenario_result(scenario_id: str = "baseline") -> ScenarioResult:
    return ScenarioResult(scenario_id=scenario_id, name=scenario_id, timeseries_path="x/features.parquet",
                          risk_path="x/risk.parquet", frames_path="x/frames.npz",
                          metrics=fake_scenario_metrics())


def fake_validation_report(run_id: str = "run_fixture") -> ValidationReport:
    return ValidationReport(
        run_id=run_id, t0=90.0, horizon_s=90.0, per_zone_density_rmse={"B2": 0.4},
        per_zone_density_corr={"B2": 0.9}, overall_density_rmse=0.42, peak_time_error_s=6.0,
        peak_density_error_pct=8.0, state_agreement=0.82, calibrated_params={"tau": 0.5},
        verdict="GOOD", calibration_window=(0.0, 90.0), validation_window=(90.0, 180.0),
    )


def fake_prevention_plan(run_id: str = "run_fixture") -> PreventionPlan:
    return PreventionPlan(
        run_id=run_id,
        recommendations=[Recommendation(
            rank=1, scenario_id="open_c",
            headline="Opening Gate C at 1:00 lowered modelled peak risk from CRITICAL to MEDIUM",
            deltas={"peak_density": -1.4}, confidence_note="Low variability across seeds; validation GOOD.")],
        key_lessons=["Gate B capacity was exceeded about 45 s before the modelled peak."],
    )
