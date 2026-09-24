"""Turn raw per-frame track boxes into smoothed world trajectories (``tracks.parquet``)."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.signal import savgol_filter

from rewind.calibration.homography import pixel_to_world
from rewind.perception.detector import ground_points
from rewind.schemas.perception import TRACK_COLUMNS, Track, TrackPoint
from rewind.venue.geometry import ZoneLocator

RAW_COLUMNS = ["t", "track_id", "x1", "y1", "x2", "y2", "conf"]


def empty_tracks() -> pd.DataFrame:
    return pd.DataFrame({c: pd.Series(dtype="object" if c in ("track_id", "zone_id") else "float64")
                         for c in TRACK_COLUMNS})


def build_trajectories(raw: pd.DataFrame, H: np.ndarray, locator: ZoneLocator, *, camera_view: str,
                       min_duration_s: float = 1.0, max_speed: float = 4.0, savgol_window: int = 5,
                       savgol_order: int = 2) -> pd.DataFrame:
    """raw: columns RAW_COLUMNS (processed-frame pixels). Returns TRACK_COLUMNS dataframe."""
    if raw.empty:
        return empty_tracks()
    raw = raw.sort_values(["track_id", "t"]).reset_index(drop=True)
    foot = ground_points(raw[["x1", "y1", "x2", "y2"]].to_numpy(), camera_view)
    world = pixel_to_world(foot, H)
    raw = raw.assign(px_x=foot[:, 0], px_y=foot[:, 1], wx=world[:, 0], wy=world[:, 1])

    parts: list[pd.DataFrame] = []
    for tid, g in raw.groupby("track_id", sort=False):
        g = g.drop_duplicates("t")
        if len(g) < 2 or g["t"].iloc[-1] - g["t"].iloc[0] < min_duration_s:
            continue
        t = g["t"].to_numpy()
        xy = g[["wx", "wy"]].to_numpy()
        if len(g) >= savgol_window:
            xy = savgol_filter(xy, savgol_window, savgol_order, axis=0, mode="interp")
        vel = np.gradient(xy, t, axis=0)
        speed = np.linalg.norm(vel, axis=1)
        over = speed > max_speed
        if over.any():
            vel[over] *= (max_speed / speed[over])[:, None]
        parts.append(pd.DataFrame({
            "track_id": str(tid), "t": t, "px_x": g["px_x"].to_numpy(), "px_y": g["px_y"].to_numpy(),
            "wx": xy[:, 0], "wy": xy[:, 1], "vx": vel[:, 0], "vy": vel[:, 1],
        }))
    if not parts:
        return empty_tracks()
    df = pd.concat(parts, ignore_index=True)
    df["zone_id"] = locator.locate_ids(df[["wx", "wy"]].to_numpy())
    return df[TRACK_COLUMNS]


def tracks_to_models(df: pd.DataFrame) -> list[Track]:
    out = []
    for tid, g in df.groupby("track_id", sort=False):
        pts = []
        for rec in g.to_dict("records"):
            zid = rec["zone_id"]
            pts.append(TrackPoint(t=float(rec["t"]), px=(float(rec["px_x"]), float(rec["px_y"])),
                                  world=(float(rec["wx"]), float(rec["wy"])),
                                  vel=(float(rec["vx"]), float(rec["vy"])),
                                  zone_id=zid if isinstance(zid, str) else None))
        out.append(Track(track_id=str(tid), points=pts))
    return out
