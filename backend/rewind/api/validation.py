"""Validation API endpoints."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from rewind.api.deps import store
from rewind.api.errors import ApiError, not_found
from rewind.schemas.validation import ValidationReport
from rewind.validation.replay import compute_validation_report

router = APIRouter(tags=["validation"])


class ValidateRequest(BaseModel):
    t0: float = Field(ge=0, default=60.0)
    horizon_s: float = Field(gt=0, default=120.0)


@router.post("/runs/{run_id}/validate", response_model=ValidationReport, summary="Run validation replay against footage")
def run_validation(run_id: str, req: ValidateRequest) -> ValidationReport:
    st = store()
    if not st.exists(run_id, "features"):
        raise ApiError(409, "not_ready", f"Features not ready for run '{run_id}'")

    report = compute_validation_report(st, run_id, t0=req.t0, horizon_s=req.horizon_s)
    # Save validation report
    val_file = st.run_dir(run_id) / "validation.json"
    with open(val_file, "w", encoding="utf-8") as f:
        f.write(report.model_dump_json(indent=2))
    return report


@router.get("/runs/{run_id}/validation", response_model=ValidationReport, summary="Get latest validation report")
def get_validation(run_id: str) -> ValidationReport:
    st = store()
    val_file = st.run_dir(run_id) / "validation.json"
    if val_file.exists():
        with open(val_file, encoding="utf-8") as f:
            return ValidationReport.model_validate_json(f.read())
    # Compute on the fly if not cached
    if st.exists(run_id, "features"):
        return run_validation(run_id, ValidateRequest(t0=60.0, horizon_s=120.0))
    raise not_found("validation", run_id)
