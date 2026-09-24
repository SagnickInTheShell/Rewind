"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from rewind import __version__
from rewind.api import health
from rewind.api.errors import install_error_handlers
from rewind.logging_setup import setup_logging
from rewind.settings import Settings, get_settings

OPENAPI_TAGS = [
    {"name": "health", "description": "Service status"},
    {"name": "videos", "description": "Video upload and streaming"},
    {"name": "venues", "description": "Venue floor plans and calibration"},
    {"name": "runs", "description": "Analysis runs: features, risk, explanations, timeline"},
    {"name": "simulations", "description": "What-if simulations in the digital twin"},
    {"name": "validation", "description": "Do-nothing replay vs observed footage"},
    {"name": "demo", "description": "Pre-computed demo run"},
]


def _include_routers(app: FastAPI) -> None:
    app.include_router(health.router, prefix="/api")
    # Routers from later phases register themselves here when importable.
    from importlib import import_module

    for name in ("videos", "venues", "analysis", "simulations", "validation", "demo"):
        try:
            mod = import_module(f"rewind.api.{name}")
        except ModuleNotFoundError as exc:
            if exc.name == f"rewind.api.{name}":
                continue
            raise
        app.include_router(mod.router, prefix="/api")
    try:
        ws = import_module("rewind.api.ws")
        app.include_router(ws.router)
    except ModuleNotFoundError as exc:
        if exc.name != "rewind.api.ws":
            raise


def create_app(settings: Settings | None = None) -> FastAPI:
    s = settings or get_settings()
    setup_logging(s.app.log_level)
    app = FastAPI(
        title="REWIND API",
        version=__version__,
        description="AI Incident Reconstruction & Prevention Engine. "
        "Identifies escalating risk patterns in crowd dynamics and simulates modelled alternatives.",
        openapi_tags=OPENAPI_TAGS,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.app.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    install_error_handlers(app)
    _include_routers(app)
    return app


app = create_app()
