"""Run metadata and job progress contracts."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from rewind.schemas.video import VideoMeta

JobState = Literal["QUEUED", "RUNNING", "DONE", "FAILED"]


class JobStatus(BaseModel):
    job_id: str
    kind: str  # "analysis" | "simulation" | "validation"
    state: JobState
    stage: str
    percent: float = Field(ge=0, le=100)
    message: str = ""
    eta_s: float | None = None
    error: str | None = None
    result_id: str | None = None  # run_id / sim_id produced by the job


class ProgressEvent(BaseModel):
    """Message pushed on ``/ws/jobs/{job_id}``."""

    stage: str
    percent: float
    message: str = ""
    eta_s: float | None = None
    done: bool = False
    error: str | None = None


class RunMeta(BaseModel):
    run_id: str
    video: VideoMeta
    venue_id: str
    methods: dict[str, str] = Field(default_factory=dict)  # detector, tracker, density, flow, risk
    config_hash: str = ""
    timings_s: dict[str, float] = Field(default_factory=dict)
    status: JobState = "QUEUED"
    job_id: str | None = None
    created_at: str = ""
    notes: list[str] = Field(default_factory=list)  # e.g. synthetic-footage / sensitive-footage notes


class CreateRunRequest(BaseModel):
    video_id: str
    venue_id: str
    force: bool = False
    sensitive: bool = False  # footage of a real incident with casualties -> respectful note in UI


class CreateRunResponse(BaseModel):
    run_id: str
    job_id: str


class CreateSimResponse(BaseModel):
    sim_id: str
    job_id: str


class ValidateRequest(BaseModel):
    t0: float | None = None
    horizon_s: float | None = None
