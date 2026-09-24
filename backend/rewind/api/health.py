"""Health and environment info."""

from __future__ import annotations

import platform
from importlib import metadata
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from rewind import __version__
from rewind.settings import get_settings

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    version: str
    python: str
    gpu_available: bool
    gpu_name: str | None
    versions: dict[str, str]
    models: dict[str, Any]
    config_hash: str


def _pkg_version(name: str) -> str:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return "not installed"


def _gpu() -> tuple[bool, str | None]:
    try:
        import torch

        if torch.cuda.is_available():
            return True, str(torch.cuda.get_device_name(0))
    except Exception:  # torch missing or broken driver
        pass
    return False, None


def models_status() -> dict[str, Any]:
    s = get_settings()
    density = s.resolve(s.perception.density_model_path)
    return {
        "detector": s.perception.yolo_model,
        "tracker": s.perception.tracker,
        "density": "csrnet" if density.exists() else f"{s.perception.density_fallback} (fallback)",
        "temporal": (s.models_dir / f"temporal_{s.risk.temporal.arch}.pt").exists(),
        "xgb": (s.models_dir / "xgb.json").exists(),
    }


@router.get("/health", response_model=HealthResponse, summary="Service status, versions, GPU, models")
def health() -> HealthResponse:
    gpu, name = _gpu()
    pkgs = ["fastapi", "pydantic", "numpy", "opencv-python-headless", "torch", "ultralytics", "xgboost"]
    return HealthResponse(
        status="ok",
        version=__version__,
        python=platform.python_version(),
        gpu_available=gpu,
        gpu_name=name,
        versions={p: _pkg_version(p) for p in pkgs},
        models=models_status(),
        config_hash=get_settings().config_hash(),
    )
