"""Zone features - the central contract (Section 5.4)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

FeatureSource = Literal["tracks", "density", "fused", "sim"]

# The 12 numeric features used by the ML models, in fixed order.
NUMERIC_FEATURES: list[str] = [
    "count",
    "density",
    "mean_speed",
    "speed_var",
    "velocity_var",
    "direction_entropy",
    "counterflow_index",
    "flow_instability",
    "inflow_rate",
    "outflow_rate",
    "bottleneck_pressure",
    "crowd_pressure",
]

FEATURE_LABELS: dict[str, str] = {
    "count": "People count",
    "density": "Density",
    "mean_speed": "Mean speed",
    "speed_var": "Speed variance",
    "velocity_var": "Velocity variance",
    "dominant_dir": "Dominant direction",
    "direction_entropy": "Direction entropy",
    "counterflow_index": "Counterflow",
    "flow_instability": "Flow instability",
    "inflow_rate": "Inflow rate",
    "outflow_rate": "Outflow rate",
    "bottleneck_pressure": "Bottleneck pressure",
    "crowd_pressure": "Crowd pressure",
}

FEATURE_UNITS: dict[str, str] = {
    "count": "people",
    "density": "people/m²",
    "mean_speed": "m/s",
    "speed_var": "(m/s)²",
    "velocity_var": "(m/s)²",
    "dominant_dir": "rad",
    "direction_entropy": "",
    "counterflow_index": "",
    "flow_instability": "m/s²",
    "inflow_rate": "people/s",
    "outflow_rate": "people/s",
    "bottleneck_pressure": "× capacity",
    "crowd_pressure": "1/s²",
}


class ZoneFeatures(BaseModel):
    t: float
    zone_id: str
    count: float = Field(ge=0)
    density: float = Field(ge=0)
    mean_speed: float = Field(ge=0)
    speed_var: float = Field(ge=0)
    velocity_var: float = Field(ge=0)
    dominant_dir: float
    direction_entropy: float = Field(ge=0, le=1)
    counterflow_index: float = Field(ge=0, le=1)
    flow_instability: float = Field(ge=0)
    inflow_rate: float = Field(ge=0)
    outflow_rate: float = Field(ge=0)
    bottleneck_pressure: float = Field(ge=0)
    crowd_pressure: float = Field(ge=0)
    source: FeatureSource


class ZoneTimeseries(BaseModel):
    run_id: str
    origin: Literal["video", "simulation"]
    window_s: float = 1.0
    zones: list[str]
    rows: list[ZoneFeatures]
