"""Venue floor-plan contract (Section 5.2)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

ZoneKind = Literal["floor", "corridor", "entry", "exit", "gate_area"]
PortalKind = Literal["gate", "door", "corridor"]


class Point(BaseModel):
    x: float
    y: float

    def as_tuple(self) -> tuple[float, float]:
        return (self.x, self.y)


class Zone(BaseModel):
    zone_id: str
    name: str
    polygon: list[Point] = Field(min_length=3)
    kind: ZoneKind


class Portal(BaseModel):
    """A gate, door, or corridor connection between zones.

    ``to_zone`` may be ``"OUTSIDE"`` for gates on the venue perimeter (sources/sinks).
    """

    portal_id: str
    name: str
    from_zone: str
    to_zone: str
    segment: tuple[Point, Point]
    width_m: float = Field(gt=0)
    is_open: bool = True
    bidirectional: bool = True
    kind: PortalKind


class Wall(BaseModel):
    a: Point
    b: Point


class CameraCalibration(BaseModel):
    image_points: list[Point]
    world_points: list[Point]

    @field_validator("world_points")
    @classmethod
    def _same_length(cls, v: list[Point], info: object) -> list[Point]:
        data = getattr(info, "data", {})
        img = data.get("image_points")
        if img is not None and len(img) != len(v):
            raise ValueError("image_points and world_points must have the same length")
        return v


OUTSIDE = "OUTSIDE"


class Venue(BaseModel):
    venue_id: str
    name: str
    bounds: tuple[Point, Point]
    zones: list[Zone]
    portals: list[Portal]
    walls: list[Wall]
    sources: list[str]
    sinks: list[str]
    calibration: CameraCalibration

    def zone(self, zone_id: str) -> Zone:
        for z in self.zones:
            if z.zone_id == zone_id:
                return z
        raise KeyError(zone_id)

    def portal(self, portal_id: str) -> Portal:
        for p in self.portals:
            if p.portal_id == portal_id:
                return p
        raise KeyError(portal_id)

    @property
    def zone_ids(self) -> list[str]:
        return [z.zone_id for z in self.zones]
