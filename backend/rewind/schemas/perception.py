"""Perception contracts (Section 5.3). Tracks are persisted as ``tracks.parquet``."""

from __future__ import annotations

from pydantic import BaseModel, Field

TRACK_COLUMNS = ["track_id", "t", "px_x", "px_y", "wx", "wy", "vx", "vy", "zone_id"]


class Detection(BaseModel):
    t: float
    bbox_xyxy: tuple[float, float, float, float]
    conf: float = Field(ge=0, le=1)


class TrackPoint(BaseModel):
    t: float
    px: tuple[float, float]
    world: tuple[float, float]
    vel: tuple[float, float]
    zone_id: str | None


class Track(BaseModel):
    track_id: str
    points: list[TrackPoint]


class OverlayTrack(BaseModel):
    track_id: str
    bbox_xyxy: tuple[float, float, float, float] | None
    tail: list[tuple[float, float]]  # recent foot points in pixels, oldest first


class OverlayZone(BaseModel):
    zone_id: str
    polygon_px: list[tuple[float, float]]
    density: float
    count: float
    state: str
    mode: str  # "sparse" (tracking) | "dense" (density + flow)


class OverlayArrow(BaseModel):
    x: float
    y: float
    dx: float
    dy: float


class OverlayFrame(BaseModel):
    """Everything the video overlay canvas needs for one timestamp (pixel coords, processed scale)."""

    t: float
    frame_width: int
    frame_height: int
    tracks: list[OverlayTrack]
    zones: list[OverlayZone]
    arrows: list[OverlayArrow]
    heatmap: list[list[float]] | None = None  # coarse density grid, rows x cols, normalised 0..1
