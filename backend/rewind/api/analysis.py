"""Run routes: create/analyse, status, features, risk, explanations, timeline, overlay, jobs."""

from __future__ import annotations

from typing import Literal

import numpy as np
from fastapi import APIRouter, Query

from rewind.api.deps import require_run, settings, store
from rewind.api.errors import ApiError, not_found
from rewind.explain.contributions import row_to_explanation
from rewind.perception.overlay import OVERLAY_CACHE
from rewind.pipeline.analyze import AnalysisPipeline, create_run
from rewind.pipeline.jobs import get_jobs
from rewind.schemas.events import IncidentTimeline
from rewind.schemas.features import ZoneFeatures
from rewind.schemas.perception import OverlayFrame
from rewind.schemas.risk import Explanation, GlobalRiskPoint, RiskPoint, RiskSeries
from rewind.schemas.run import CreateRunRequest, CreateRunResponse, JobStatus, RunMeta
from rewind.storage.run_store import read_model

router = APIRouter(tags=["runs"])


@router.post("/runs", response_model=CreateRunResponse, summary="Start an analysis job",
             openapi_extra={"requestBody": {"content": {"application/json": {"example": {
                 "video_id": "vid_1a2b3c4d5e", "venue_id": "demo_venue", "force": False}}}}})
def create_analysis(req: CreateRunRequest) -> CreateRunResponse:
    s, st = settings(), store()
    if not st.video_meta_path(req.video_id).exists():
        raise not_found("video", req.video_id)
    if not (s.venues_dir / f"{req.venue_id}.json").exists():
        raise not_found("venue", req.venue_id)
    meta = create_run(st, s, req.video_id, req.venue_id, sensitive=req.sensitive)

    def job(progress):  # type: ignore[no-untyped-def]
        AnalysisPipeline(st, s, meta.run_id, progress=progress, force=req.force).run()
        return meta.run_id

    jobs = get_jobs()
    job_id = jobs.new_id()
    meta.job_id = job_id
    st.save_meta(meta)  # before the job starts writing meta.json itself
    jobs.submit("analysis", job, result_id=meta.run_id, job_id=job_id)
    return CreateRunResponse(run_id=meta.run_id, job_id=job_id)


@router.get("/runs", response_model=list[RunMeta], summary="List runs")
def list_runs() -> list[RunMeta]:
    return store().list_runs()


@router.get("/runs/{run_id}", response_model=RunMeta, summary="Run metadata and status")
def get_run(run_id: str) -> RunMeta:
    st = store()
    require_run(st, run_id)
    return st.load_meta(run_id)


def _require(run_id: str, artefact: str) -> None:
    st = store()
    require_run(st, run_id)
    if not st.exists(run_id, artefact):
        raise ApiError(409, "not_ready", f"'{artefact}' is not available yet for run '{run_id}'")


@router.get("/runs/{run_id}/features", response_model=list[ZoneFeatures], summary="Zone feature rows")
def get_features(run_id: str, zone: str | None = None, t_from: float | None = None,
                 t_to: float | None = None) -> list[ZoneFeatures]:
    _require(run_id, "features")
    df = store().read_df(run_id, "features")
    if zone:
        df = df[df["zone_id"] == zone]
    if t_from is not None:
        df = df[df["t"] >= t_from]
    if t_to is not None:
        df = df[df["t"] <= t_to]
    return [ZoneFeatures.model_validate(r) for r in df.to_dict("records")]


@router.get("/runs/{run_id}/risk", response_model=RiskSeries, summary="Per-zone risk points and global risk")
def get_risk(run_id: str) -> RiskSeries:
    _require(run_id, "risk")
    st = store()
    r = st.read_df(run_id, "risk")
    g = st.read_df(run_id, "global_risk")
    r = r.astype({"ml_score": "float64"})
    zones = [RiskPoint(t=float(a), zone_id=str(b), physics_score=float(c),
                       ml_score=None if not np.isfinite(d) else float(d), ensemble_score=float(e), state=f)
             for a, b, c, d, e, f in zip(r["t"], r["zone_id"], r["physics_score"], r["ml_score"],
                                         r["ensemble_score"], r["state"], strict=True)]
    glob = [GlobalRiskPoint(t=float(a), max_score=float(b), worst_zone=str(c), state=d)
            for a, b, c, d in zip(g["t"], g["max_score"], g["worst_zone"], g["state"], strict=True)]
    label = st.load_meta(run_id).methods.get("risk", "physics")
    methods = {"physics": True, "temporal": "temporal" in label, "xgb": "xgboost" in label}
    return RiskSeries(run_id=run_id, zones=zones, global_risk=glob, methods=methods)


@router.get("/runs/{run_id}/explanations", response_model=Explanation, summary="Explanation for one moment")
def get_explanation(run_id: str, t: float = Query(..., ge=0), zone: str | None = None,
                    method: Literal["physics", "shap"] = "physics") -> Explanation:
    _require(run_id, "explanations")
    st, s = store(), settings()
    if zone is None:
        g = st.read_df(run_id, "global_risk")
        if g.empty:
            raise ApiError(409, "not_ready", "no risk data")
        zone = str(g.iloc[int(np.argmin(np.abs(g["t"].to_numpy() - t)))]["worst_zone"])
    if method == "shap":
        from rewind.explain.contributions import shap_explanation

        exp = shap_explanation(st, s, run_id, t, zone)
        if exp is None:
            raise ApiError(409, "shap_unavailable",
                           "SHAP explanations need the trained XGBoost model (run `make train`).")
        return exp
    ex = st.read_df(run_id, "explanations")
    ex = ex[ex["zone_id"] == zone]
    if ex.empty:
        raise not_found("zone", zone)
    row = ex.iloc[int(np.argmin(np.abs(ex["t"].to_numpy() - t)))].to_dict()
    return row_to_explanation(row)


@router.get("/runs/{run_id}/timeline", response_model=IncidentTimeline, summary="Incident timeline")
def get_timeline(run_id: str) -> IncidentTimeline:
    _require(run_id, "timeline")
    return read_model(store().path(run_id, "timeline"), IncidentTimeline)


@router.get("/runs/{run_id}/overlay", response_model=OverlayFrame,
            summary="Tracks, zone densities, flow arrows and heatmap for one timestamp")
def get_overlay(run_id: str, t: float = Query(0.0, ge=0, examples=[42.0]),
                heatmap: bool = Query(True, description="include the coarse density heatmap")) -> OverlayFrame:
    st = store()
    require_run(st, run_id)
    return OVERLAY_CACHE.get(st, run_id, settings()).frame(t, with_heatmap=heatmap)


@router.get("/jobs/{job_id}", response_model=JobStatus, tags=["runs"], summary="Job status")
def get_job(job_id: str) -> JobStatus:
    st = get_jobs().get(job_id)
    if st is None:
        raise not_found("job", job_id)
    return st
