"""Shared test helpers: synthetic clips and prepared runs."""

from __future__ import annotations

import shutil
from pathlib import Path

from rewind.ingest.video_reader import probe
from rewind.settings import Settings
from rewind.storage.run_store import RunStore
from rewind.synthetic.render import write_video
from rewind.synthetic.scripted import ScriptedConfig, ScriptedCrowd
from rewind.venue.demo import build_demo_venue
from rewind.venue.graph import save_venue


def busy_inflow(t: float) -> float:
    return 6.0 if t < 8 else 3.0


def render_clip(path: Path, duration: float = 6.0, seed: int = 0, fps: float = 10.0) -> Path:
    venue = build_demo_venue()
    cfg = ScriptedConfig(duration_s=duration, seed=seed, inflow=busy_inflow, counterflow_start=1e9)
    write_video(ScriptedCrowd(venue, cfg).run(fps), venue, path, fps=fps)
    return path


def install_clip(settings: Settings, clip: Path, video_id: str = "vid_test") -> str:
    """Copy a rendered clip into the data dir as an uploaded video, with metadata + demo venue."""
    store = RunStore(settings)
    dst = settings.videos_dir / f"{video_id}{clip.suffix}"
    shutil.copy(clip, dst)
    meta = probe(dst, video_id, settings.video.fps_processed, synthetic=True).model_copy(
        update={"filename": clip.name})
    store.video_meta_path(video_id).write_text(meta.model_dump_json(), encoding="utf-8")
    save_venue(build_demo_venue(), settings.venues_dir / "demo_venue.json")
    return video_id
