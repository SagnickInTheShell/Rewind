"""Venue listing, retrieval and validated save."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from rewind.api.deps import settings
from rewind.api.errors import ApiError, not_found
from rewind.schemas.venue import Venue
from rewind.venue.graph import load_venue, save_venue, validate_venue

router = APIRouter(tags=["venues"])


class VenueSummary(BaseModel):
    venue_id: str
    name: str
    zones: int
    portals: int


@router.get("/venues", response_model=list[VenueSummary], summary="List venues")
def list_venues() -> list[VenueSummary]:
    out = []
    for p in sorted(settings().venues_dir.glob("*.json")):
        try:
            v = load_venue(p, validate=False)
        except Exception:
            continue
        out.append(VenueSummary(venue_id=v.venue_id, name=v.name, zones=len(v.zones), portals=len(v.portals)))
    return out


@router.get("/venues/{venue_id}", response_model=Venue, summary="Get a venue")
def get_venue(venue_id: str) -> Venue:
    p = settings().venues_dir / f"{venue_id}.json"
    if not p.exists():
        raise not_found("venue", venue_id)
    return load_venue(p, validate=False)


@router.put("/venues/{venue_id}", response_model=Venue, summary="Save a venue (validated)")
def put_venue(venue_id: str, venue: Venue) -> Venue:
    if venue.venue_id != venue_id:
        raise ApiError(422, "id_mismatch", f"body venue_id '{venue.venue_id}' does not match path '{venue_id}'")
    errors = validate_venue(venue)
    if errors:
        raise ApiError(422, "invalid_venue", "venue failed validation", errors)
    try:
        from rewind.calibration.homography import fit_homography

        fit_homography(venue.calibration.image_points, venue.calibration.world_points)
    except ValueError as exc:
        raise ApiError(422, "invalid_calibration", str(exc)) from exc
    save_venue(venue, settings().venues_dir / f"{venue_id}.json")
    return venue
