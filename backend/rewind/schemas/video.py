"""Video metadata contract (Section 5.1)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class VideoMeta(BaseModel):
    video_id: str
    filename: str
    fps_native: float = Field(gt=0)
    fps_processed: float = Field(gt=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    duration_s: float = Field(ge=0)
    frame_count: int = Field(ge=0)
    synthetic: bool = False  # True for renderer-generated footage; shown in the UI
