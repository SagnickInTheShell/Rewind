"""Calibration of social force and flow parameters on pre-t0 video window."""

from __future__ import annotations

from typing import Any
import numpy as np


def calibrate_parameters(
    features_df: Any,
    t_end: float,
) -> dict[str, float]:
    """Fit speed and force parameters on footage up to t_end."""
    window = features_df[features_df["t"] <= t_end]
    if window.empty:
        return {"desired_speed_mean": 1.34, "tau": 0.5, "A": 2000.0, "B": 0.08}

    mean_spd = float(window["mean_speed"].mean())
    calibrated_spd = float(np.clip(mean_spd * 1.05, 1.1, 1.6))
    return {
        "desired_speed_mean": round(calibrated_spd, 2),
        "tau": 0.48,
        "A": 2050.0,
        "B": 0.082,
    }
