"""Run routes: create/analyse, features, risk, explanations, timeline, overlay."""

from __future__ import annotations

from fastapi import APIRouter, Query

from rewind.api.deps import require_run, settings, store
from rewind.perception.overlay import OVERLAY_CACHE
from rewind.schemas.perception import OverlayFrame

router = APIRouter(tags=["runs"])


@router.get("/runs/{run_id}/overlay", response_model=OverlayFrame,
            summary="Tracks, zone densities, flow arrows and heatmap for one timestamp")
def get_overlay(run_id: str, t: float = Query(0.0, ge=0, examples=[42.0]),
                heatmap: bool = Query(True, description="include the coarse density heatmap")) -> OverlayFrame:
    st = store()
    require_run(st, run_id)
    return OVERLAY_CACHE.get(st, run_id, settings()).frame(t, with_heatmap=heatmap)
