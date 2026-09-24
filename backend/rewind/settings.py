"""Typed configuration loader.

Values come from ``backend/config/default.yaml``; an alternative file can be selected with the
``REWIND_CONFIG`` environment variable, and individual values can be overridden with
``REWIND__SECTION__KEY=value`` environment variables (nested with double underscores).
"""

from __future__ import annotations

import hashlib
import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, model_validator

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent
DEFAULT_CONFIG = BACKEND_DIR / "config" / "default.yaml"


class AppSettings(BaseModel):
    data_dir: str = "data"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    log_level: str = "INFO"
    blur_heads_in_exports: bool = False
    max_upload_mb: int = 2048
    job_workers: int = 2


class VideoSettings(BaseModel):
    fps_processed: float = 5.0
    max_width: int = 1280


class FlowSettings(BaseModel):
    method: str = "farneback"
    downscale: float = 0.5
    grid_step_px: int = 8
    max_samples_per_zone: int = 200


class PerceptionSettings(BaseModel):
    yolo_model: str = "yolov8s.pt"
    yolo_conf: float = 0.25
    yolo_imgsz: int = 1280
    yolo_batch: int = 8
    detector: str = "auto"
    camera_view: str = "auto"
    person_radius_m: float = 0.25
    tracker: str = "bytetrack"
    density_model_path: str = "data/models/csrnet.pth"
    density_fallback: str = "kde"
    kde_sigma_factor: float = 0.3
    density_min_threshold: float = 0.1
    hybrid_switch_density: float = 1.5
    hybrid_blend_band: float = 0.5
    min_tracks_for_velocity: int = 3
    track_min_duration_s: float = 1.0
    track_max_speed: float = 4.0
    savgol_window: int = 5
    savgol_order: int = 2
    flow: FlowSettings = Field(default_factory=FlowSettings)


class OverlaySettings(BaseModel):
    heat_grid: tuple[int, int] = (64, 36)
    arrow_every: int = 6
    tail_s: float = 3.0


class FeatureSettings(BaseModel):
    window_s: float = 1.0
    direction_bins: int = 8
    counterflow_angle_deg: float = 120.0
    min_speed_for_direction: float = 0.1
    specific_flow_p_per_m_s: float = 1.3
    smoothing_window: int = 5


class Thresholds(BaseModel):
    medium: float = 0.35
    high: float = 0.55
    critical: float = 0.75


class EnsembleWeights(BaseModel):
    physics: float = 0.5
    temporal: float = 0.3
    xgb: float = 0.2


class DensityLevels(BaseModel):
    caution: float = 2.0
    high: float = 4.0
    critical: float = 5.0


class TemporalSettings(BaseModel):
    arch: str = "tcn"
    seq_len: int = 30
    tcn_channels: int = 64
    tcn_dilations: list[int] = Field(default_factory=lambda: [1, 2, 4, 8])
    lstm_hidden: int = 64
    lstm_layers: int = 2
    dropout: float = 0.2


class RiskSettings(BaseModel):
    weights: dict[str, float]
    norm: dict[str, float]
    thresholds: Thresholds = Field(default_factory=Thresholds)
    hysteresis: float = 0.05
    min_dwell_s: float = 3.0
    ensemble: EnsembleWeights = Field(default_factory=EnsembleWeights)
    escalation_horizon_s: float = 60.0
    density_levels: DensityLevels = Field(default_factory=DensityLevels)
    crowd_pressure_turbulence: float = 0.02
    temporal: TemporalSettings = Field(default_factory=TemporalSettings)
    models_dir: str = "data/models"
    occupancy_full_density: float = 1.0
    occupancy_gated: list[str] = Field(default_factory=lambda: ["counterflow_index", "flow_instability"])

    @model_validator(mode="after")
    def _weights_sum_to_one(self) -> RiskSettings:
        total = sum(self.weights.values())
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"risk.weights must sum to 1.0, got {total:.4f}")
        missing = set(self.weights) - set(self.norm)
        if missing:
            raise ValueError(f"risk.norm missing entries for {sorted(missing)}")
        return self


class EventSettings(BaseModel):
    surge_baseline_s: float = 60.0
    surge_sigma: float = 2.0
    min_duration_s: float = 5.0
    density_slope_window_s: float = 20.0
    density_slope_threshold: float = 0.05
    bottleneck_threshold: float = 1.0
    counterflow_threshold: float = 0.25
    instability_norm_fraction: float = 0.5
    spillover_window_s: float = 30.0
    causal_max_dt_s: float = 90.0
    trend_window_s: float = 30.0


class DesiredSpeed(BaseModel):
    mean: float = 1.34
    std: float = 0.26


class MacroSettings(BaseModel):
    dt: float = 0.5
    v_free: float = 1.34
    rho_jam: float = 5.4
    noise: float = 0.05


class SimulationSettings(BaseModel):
    dt: float = 0.05
    record_hz: float = 10.0
    agent_radius_m: tuple[float, float] = (0.22, 0.28)
    desired_speed: DesiredSpeed = Field(default_factory=DesiredSpeed)
    tau: float = 0.5
    A: float = 2000.0
    B: float = 0.08
    k_body: float = 120000.0
    kappa_friction: float = 240000.0
    mass: float = 80.0
    wall_A: float = 2000.0
    wall_B: float = 0.08
    reroute_every_s: float = 2.0
    reroute_prob: float = 0.3
    congestion_weight: float = 1.5
    max_agents: int = 3000
    hash_cell_m: float = 1.0
    local_density_radius_m: float = 1.0
    speed_cap_factor: float = 1.3
    open_reroute_radius_m: float = 30.0
    inflow_lookback_s: float = 30.0
    default_horizon_s: float = 240.0
    macro: MacroSettings = Field(default_factory=MacroSettings)
    max_parallel: int = 4


class ValidationSettings(BaseModel):
    good_rmse: float = 0.5
    fair_rmse: float = 1.0
    calib_fraction: float = 0.5
    calib_max_iter: int = 40


class Settings(BaseModel):
    app: AppSettings = Field(default_factory=AppSettings)
    video: VideoSettings = Field(default_factory=VideoSettings)
    perception: PerceptionSettings = Field(default_factory=PerceptionSettings)
    overlay: OverlaySettings = Field(default_factory=OverlaySettings)
    features: FeatureSettings = Field(default_factory=FeatureSettings)
    risk: RiskSettings
    events: EventSettings = Field(default_factory=EventSettings)
    simulation: SimulationSettings = Field(default_factory=SimulationSettings)
    validation: ValidationSettings = Field(default_factory=ValidationSettings)

    # ---- derived helpers -------------------------------------------------------------
    def resolve(self, rel: str) -> Path:
        """Resolve a repo-relative path from config into an absolute path."""
        p = Path(rel)
        return p if p.is_absolute() else (REPO_ROOT / p).resolve()

    @property
    def data_dir(self) -> Path:
        return self.resolve(self.app.data_dir)

    @property
    def runs_dir(self) -> Path:
        return self.data_dir / "runs"

    @property
    def videos_dir(self) -> Path:
        return self.data_dir / "videos"

    @property
    def venues_dir(self) -> Path:
        return self.data_dir / "venues"

    @property
    def models_dir(self) -> Path:
        return self.resolve(self.risk.models_dir)

    def config_hash(self) -> str:
        blob = json.dumps(self.model_dump(mode="json"), sort_keys=True).encode()
        return hashlib.sha256(blob).hexdigest()[:12]


def _set_nested(d: dict[str, Any], keys: list[str], value: Any) -> None:
    for k in keys[:-1]:
        d = d.setdefault(k, {})
    d[keys[-1]] = value


def _env_overrides(raw: dict[str, Any]) -> dict[str, Any]:
    for key, value in os.environ.items():
        if not key.startswith("REWIND__"):
            continue
        parts = [p.lower() for p in key[len("REWIND__") :].split("__") if p]
        if parts:
            _set_nested(raw, parts, yaml.safe_load(value))
    return raw


def load_settings(path: Path | None = None) -> Settings:
    cfg_path = path or Path(os.environ.get("REWIND_CONFIG", DEFAULT_CONFIG))
    with open(cfg_path, encoding="utf-8") as fh:
        raw: dict[str, Any] = yaml.safe_load(fh) or {}
    return Settings.model_validate(_env_overrides(raw))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()
