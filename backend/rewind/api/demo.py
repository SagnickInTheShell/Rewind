"""Demo mode: load the pre-computed demo run instantly."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from rewind.api.deps import store
from rewind.api.errors import ApiError
from rewind.schemas.run import RunMeta

router = APIRouter(tags=["demo"])

DEMO_RUN_ID = "demo"


class DemoLoadResponse(BaseModel):
    run: RunMeta
    sim_id: str | None
    has_validation: bool


@router.post("/demo/load", response_model=DemoLoadResponse, summary="Load the pre-computed demo run")
def load_demo() -> DemoLoadResponse:
    st = store()
    if not st.run_exists(DEMO_RUN_ID) or not st.exists(DEMO_RUN_ID, "timeline"):
        raise ApiError(404, "demo_missing", "The demo run has not been generated yet. Run `make demo` "
                       "(or `powershell -File scripts/dev.ps1 demo`) first.")
    sims = sorted((st.run_dir(DEMO_RUN_ID) / "simulations").glob("*/results.json"))
    sim_id = sims[-1].parent.name if sims else None
    preferred = st.run_dir(DEMO_RUN_ID) / "simulations" / "sim_demo" / "results.json"
    if preferred.exists():
        sim_id = "sim_demo"
    return DemoLoadResponse(run=st.load_meta(DEMO_RUN_ID), sim_id=sim_id,
                            has_validation=st.exists(DEMO_RUN_ID, "validation"))
