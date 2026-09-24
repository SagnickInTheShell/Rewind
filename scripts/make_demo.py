"""Generate the full pre-computed demo run for instant presentation."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from rewind.ingest.video_reader import VideoReader  # noqa: E402
from rewind.logging_setup import setup_logging  # noqa: E402
from rewind.pipeline.analyze import AnalysisPipeline, create_run  # noqa: E402
from rewind.schemas.simulation import (  # noqa: E402
    Intervention,
    ScenarioSpec,
    SimulationRequest,
)
from rewind.schemas.venue import Venue  # noqa: E402
from rewind.settings import get_settings  # noqa: E402
from rewind.simulation.runner import SimulationRunner  # noqa: E402
from rewind.storage.run_store import RunStore  # noqa: E402
from rewind.synthetic.render import write_video  # noqa: E402
from rewind.synthetic.sf_scenario import social_force_snapshots  # noqa: E402
from rewind.validation.replay import compute_validation_report  # noqa: E402
from rewind.venue.demo import build_demo_venue  # noqa: E402

log = logging.getLogger("make_demo")


def main() -> None:
    setup_logging()
    settings = get_settings()
    store = RunStore(settings)

    demo_vid_path = settings.videos_dir / "demo_video.mp4"
    venue = build_demo_venue()

    # 1. Render synthetic video if not exists
    if not demo_vid_path.exists():
        log.info("Rendering demo video to %s...", demo_vid_path)
        snaps = social_force_snapshots(venue, duration_s=120.0, fps=25.0, seed=0)
        write_video(snaps, venue, demo_vid_path, fps=25.0)

    # Ingest video meta
    from rewind.ingest.video_reader import probe
    from rewind.pipeline.analyze import save_video_meta
    vmeta = probe(demo_vid_path, video_id="demo_video", fps_processed=settings.video.fps_processed, synthetic=True)
    save_video_meta(store, vmeta)

    # 2. Run analysis pipeline for run_id="demo"
    log.info("Running analysis pipeline for 'demo'...")
    meta = create_run(store, settings, video_id="demo_video", venue_id="demo_venue", run_id="demo")
    pipe = AnalysisPipeline(store, settings, "demo", force=False)
    pipe.run()

    # 3. Run default simulations for sim_id="sim_demo"
    log.info("Running demo simulations for 'sim_demo'...")
    t0 = 60.0  # 1 minute in
    scenarios = [
        ScenarioSpec(
            scenario_id="baseline",
            name="Baseline (Do nothing)",
            interventions=[],
        ),
        ScenarioSpec(
            scenario_id="open_gate_c",
            name="Open Gate C at 12:35",
            interventions=[
                Intervention(type="OPEN_PORTAL", at_t=t0, portal_id="GATE_C"),
            ],
        ),
        ScenarioSpec(
            scenario_id="open_gate_c_restrict",
            name="Open Gate C + Restrict Entry 50%",
            interventions=[
                Intervention(type="OPEN_PORTAL", at_t=t0, portal_id="GATE_C"),
                Intervention(type="RESTRICT_ENTRY", at_t=t0, factor=0.5),
            ],
        ),
        ScenarioSpec(
            scenario_id="redirect_b",
            name="Redirect via Zone B",
            interventions=[
                Intervention(type="REDIRECT", at_t=t0, from_zone="B2", to_zone="B3", fraction=0.4),
            ],
        ),
        ScenarioSpec(
            scenario_id="widen_gate_b",
            name="Widen Gate B x1.5",
            interventions=[
                Intervention(type="WIDEN_PORTAL", at_t=t0, portal_id="GATE_B", factor=1.5),
            ],
        ),
    ]

    sim_req = SimulationRequest(
        run_id="demo",
        t0=t0,
        horizon_s=60.0,
        scenarios=scenarios,
        seeds=[0, 1, 2],
        model="macro",
    )
    runner = SimulationRunner(store, settings, "sim_demo")
    results = runner.run(sim_req)

    # Save request.json and results.json
    sim_dir = store.sim_dir("demo", "sim_demo")
    sim_dir.mkdir(parents=True, exist_ok=True)
    with open(sim_dir / "request.json", "w", encoding="utf-8") as f:
        f.write(sim_req.model_dump_json(indent=2))
    with open(sim_dir / "results.json", "w", encoding="utf-8") as f:
        import json
        f.write(json.dumps([r.model_dump() for r in results], indent=2))

    # 4. Generate validation report
    log.info("Generating validation report for 'demo'...")
    val_report = compute_validation_report(store, "demo", t0=t0, horizon_s=60.0)
    with open(store.run_dir("demo") / "validation.json", "w", encoding="utf-8") as f:
        f.write(val_report.model_dump_json(indent=2))

    log.info("Demo run generation complete!")


if __name__ == "__main__":
    main()
