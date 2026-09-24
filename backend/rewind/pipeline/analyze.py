"""Full analysis job: ingest → calibration → detection + tracking → density → flow → fusion → features
→ risk → explanations → events → timeline.

Each stage writes its artefact(s) into ``data/runs/{run_id}/`` and is skipped when they already exist
(unless ``force``).
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from rewind.pipeline.perception_stage import (
    PerceptionContext,
    stage_density,
    stage_detect_track,
    stage_flow,
    stage_trajectories,
)
from rewind.schemas.run import RunMeta
from rewind.schemas.venue import Venue
from rewind.schemas.video import VideoMeta
from rewind.settings import Settings
from rewind.storage.run_store import RunStore, now_iso, read_model, write_json
from rewind.venue.graph import load_venue

log = logging.getLogger(__name__)

ProgressFn = Callable[[str, float, str], None]  # (stage, overall percent 0..100, message)


@dataclass(frozen=True)
class Stage:
    key: str
    label: str
    weight: float
    artefacts: tuple[str, ...]


STAGES: list[Stage] = [
    Stage("detect", "Detecting people", 0.34, ("detections", "track_boxes")),
    Stage("track", "Tracking", 0.03, ("tracks",)),
    Stage("density", "Density", 0.2, ("density_zone", "heat")),
    Stage("motion", "Motion", 0.25, ("flow_zone", "flow_curl", "arrows")),
    Stage("features", "Features", 0.08, ("features", "features_meta")),
    Stage("risk", "Risk", 0.06, ("risk", "global_risk", "explanations")),
    Stage("reconstruction", "Reconstruction", 0.04, ("timeline",)),
]

SENSITIVE_NOTE = ("This footage may show a real incident in which people were harmed. It is analysed "
                  "respectfully, to understand crowd dynamics and support future safety planning.")
SYNTHETIC_NOTE = "Synthetic footage: a simulated crowd rendered for testing and demonstration."


def create_run(store: RunStore, settings: Settings, video_id: str, venue_id: str, *, run_id: str | None = None,
               sensitive: bool = False) -> RunMeta:
    from rewind.storage.run_store import new_id

    video = read_model(store.video_meta_path(video_id), VideoMeta)
    venue = load_venue(settings.venues_dir / f"{venue_id}.json")
    rid = run_id or new_id("run")
    d = store.run_dir(rid)
    d.mkdir(parents=True, exist_ok=True)
    write_json(d / "venue.json", venue)  # snapshot: later venue edits do not change this run
    notes = []
    if video.synthetic:
        notes.append(SYNTHETIC_NOTE)
    if sensitive:
        notes.append(SENSITIVE_NOTE)
    meta = RunMeta(run_id=rid, video=video, venue_id=venue_id, config_hash=settings.config_hash(),
                   status="QUEUED", created_at=now_iso(), notes=notes)
    store.save_meta(meta)
    return meta


class AnalysisPipeline:
    def __init__(self, store: RunStore, settings: Settings, run_id: str, progress: ProgressFn | None = None,
                 force: bool = False, t_end: float | None = None) -> None:
        self.store = store
        self.s = settings
        self.run_id = run_id
        self.progress_cb = progress
        self.force = force
        self.t_end = t_end
        self.meta = store.load_meta(run_id)
        self.venue = Venue.model_validate_json(store.path(run_id, "venue.json").read_text(encoding="utf-8"))
        self._ctx: PerceptionContext | None = None
        self._done_weight = 0.0

    # ---- helpers --------------------------------------------------------------------------
    @property
    def ctx(self) -> PerceptionContext:
        if self._ctx is None:
            self._ctx = PerceptionContext(self.store.video_path(self.meta.video.video_id), self.venue, self.s,
                                          synthetic=self.meta.video.synthetic, t_end=self.t_end)
        return self._ctx

    def _report(self, stage: Stage, frac: float, msg: str) -> None:
        if self.progress_cb:
            pct = 100.0 * (self._done_weight + stage.weight * min(max(frac, 0.0), 1.0))
            self.progress_cb(stage.key, min(pct, 99.9), msg)

    def _cached(self, stage: Stage) -> bool:
        return not self.force and all(self.store.exists(self.run_id, a) for a in stage.artefacts)

    def _save_meta(self) -> None:
        self.store.save_meta(self.meta)

    # ---- stages ---------------------------------------------------------------------------
    def _detect(self, st: Stage) -> None:
        det, boxes, dname, tname = stage_detect_track(self.ctx, lambda f, m: self._report(st, f, m))
        self.store.write_df(self.run_id, "detections", det)
        self.store.write_df(self.run_id, "track_boxes", boxes)
        self.meta.methods.update({"detector": dname, "tracker": tname, "camera_view": self.ctx.camera_view})

    def _check_calibration(self) -> None:
        """After detection: verify the venue calibration fits the camera; otherwise auto-calibrate.

        People whose ground point lies outside the floor plan are never counted. When most detections
        fall outside, the run switches to an auto-calibrated camera grid and labels density as ESTIMATED.
        """
        from rewind.pipeline.perception_stage import check_calibration, trace_frames

        det = self.store.read_df(self.run_id, "detections")
        if "calibration" not in self.meta.methods or self.force:
            chk = check_calibration(self.ctx, det)
            self.meta.methods["calibration_fit"] = f"{chk.fit:.0%} of {chk.n} detections inside plan"
            self.meta.methods["calibration"] = chk.label
            self.meta.methods["density_basis"] = chk.density_basis
            if chk.note and chk.note not in self.meta.notes:
                self.meta.notes.append(chk.note)
            if chk.venue is not None:
                original = self.store.path(self.run_id, "venue_original.json")
                if not original.exists():
                    original.write_text(self.store.path(self.run_id, "venue.json").read_text(encoding="utf-8"),
                                        encoding="utf-8")
                write_json(self.store.path(self.run_id, "venue.json"), chk.venue)
                self.venue = chk.venue
                self._ctx = None  # rebuild masks / homography for the new zones
            self._save_meta()
            log.info("calibration check", extra={"kv": {"run": self.run_id, "fit": round(chk.fit, 3),
                                                        "calibration": chk.label}})
        if self.s.perception.debug_trace:
            trace_frames(self.ctx, det, self.store.read_df(self.run_id, "track_boxes"))

    def _track(self, st: Stage) -> None:
        boxes = self.store.read_df(self.run_id, "track_boxes")
        tracks = stage_trajectories(self.ctx, boxes)
        self.store.write_df(self.run_id, "tracks", tracks)
        self.meta.methods["tracks"] = str(tracks["track_id"].nunique()) if not tracks.empty else "0"

    def _density(self, st: Stage) -> None:
        det = self.store.read_df(self.run_id, "detections")
        dz, ht, heat, method = stage_density(self.ctx, det, lambda f, m: self._report(st, f, m))
        self.store.write_df(self.run_id, "density_zone", dz)
        np.savez_compressed(self.store.path(self.run_id, "heat"), t=ht, heat=heat)
        write_json(self.store.path(self.run_id, "zone_areas"), self.ctx.zone_area)
        self.meta.methods["density"] = method

    def _motion(self, st: Stage) -> None:
        with np.load(self.store.path(self.run_id, "heat")) as z:
            ht, heat = z["t"], z["heat"]
        flow, curl, arrows = stage_flow(self.ctx, ht, heat, lambda f, m: self._report(st, f, m))
        self.store.write_df(self.run_id, "flow_zone", flow)
        self.store.write_df(self.run_id, "flow_curl", curl)
        np.savez_compressed(self.store.path(self.run_id, "arrows"), **arrows)
        self.meta.methods["flow"] = self.s.perception.flow.method

    def _features(self, st: Stage) -> None:
        from rewind.pipeline.stages_analysis import run_features

        run_features(self.store, self.s, self.run_id, self.venue, self.meta)

    def _risk(self, st: Stage) -> None:
        from rewind.pipeline.stages_analysis import run_risk

        run_risk(self.store, self.s, self.run_id, self.venue, self.meta)

    def _reconstruction(self, st: Stage) -> None:
        from rewind.pipeline.stages_analysis import run_reconstruction

        run_reconstruction(self.store, self.s, self.run_id, self.venue)

    def run(self, until: str | None = None) -> RunMeta:
        self.meta.status = "RUNNING"
        self._save_meta()
        handlers: dict[str, Callable[[Stage], None]] = {
            "detect": self._detect, "track": self._track, "density": self._density, "motion": self._motion,
            "features": self._features, "risk": self._risk, "reconstruction": self._reconstruction,
        }
        try:
            for st in STAGES:
                if self._cached(st):
                    self._report(st, 1.0, f"{st.label}: cached")
                else:
                    self._report(st, 0.0, f"{st.label}...")
                    t0 = time.perf_counter()
                    handlers[st.key](st)
                    self.meta.timings_s[st.key] = round(time.perf_counter() - t0, 2)
                    self._save_meta()
                    log.info("stage done", extra={"kv": {"run": self.run_id, "stage": st.key,
                                                         "secs": self.meta.timings_s[st.key]}})
                self._done_weight += st.weight
                self._report(st, 0.0, f"{st.label}: done")
                if st.key == "detect":
                    self._check_calibration()
                if until == st.key:
                    break

            # Fail-safe check: raw detections alone are not sufficient for crowd analysis.
            # Require observations across multiple frames and at least one usable trajectory.
            det_df = (
                self.store.read_df(self.run_id, "detections")
                if self.store.exists(self.run_id, "detections")
                else None
            )
            track_df = (
                self.store.read_df(self.run_id, "tracks")
                if self.store.exists(self.run_id, "tracks")
                else None
            )
            detections_ok = (
                det_df is not None
                and len(det_df) >= 3
                and det_df["t"].nunique() >= 2
            )
            tracks_ok = (
                track_df is not None
                and not track_df.empty
                and track_df["track_id"].nunique() >= 1
                and track_df["t"].nunique() >= 2
            )
            if not detections_ok or not tracks_ok:
                self.meta.status = "INCOMPLETE"
                note = "Insufficient detection or tracking data for reliable crowd analysis."
                if note not in self.meta.notes:
                    self.meta.notes.append(note)
            else:
                self.meta.status = "DONE"
        except Exception:
            self.meta.status = "FAILED"
            self._save_meta()
            raise
        self._save_meta()
        return self.meta


def save_video_meta(store: RunStore, meta: VideoMeta) -> None:
    store.video_meta_path(meta.video_id).write_text(json.dumps(meta.model_dump(), indent=2), encoding="utf-8")
