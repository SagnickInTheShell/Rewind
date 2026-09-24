"""Filesystem layout for runs, videos and simulations (Section 7.18)."""

from __future__ import annotations

import json
import secrets
import shutil
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypeVar

import pandas as pd
from pydantic import BaseModel

from rewind.schemas.run import RunMeta
from rewind.settings import Settings, get_settings

M = TypeVar("M", bound=BaseModel)

ARTEFACTS = {
    "meta": "meta.json",
    "detections": "detections.parquet",
    "track_boxes": "track_boxes.parquet",
    "tracks": "tracks.parquet",
    "density_zone": "density_zone.parquet",
    "flow_zone": "flow_zone.parquet",
    "flow_curl": "flow_curl.parquet",
    "heat": "overlay_heat.npz",
    "arrows": "overlay_arrows.npz",
    "zone_areas": "zone_areas.json",
    "features": "features.parquet",
    "features_meta": "features_meta.json",
    "risk": "risk.parquet",
    "global_risk": "global_risk.parquet",
    "explanations": "explanations.parquet",
    "timeline": "timeline.json",
    "validation": "validation.json",
}


def new_id(prefix: str) -> str:
    return f"{prefix}_{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}_{secrets.token_hex(3)}"


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _replace(tmp: Path, path: Path, attempts: int = 20) -> None:
    """Atomic replace, retrying briefly on Windows when a reader holds the target open."""
    for i in range(attempts):
        try:
            tmp.replace(path)
            return
        except PermissionError:
            if i == attempts - 1:
                raise
            time.sleep(0.05)


def write_json(path: Path, obj: BaseModel | dict[str, Any] | list[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    text = obj.model_dump_json(indent=2) if isinstance(obj, BaseModel) else json.dumps(obj, indent=2)
    tmp.write_text(text, encoding="utf-8")
    _replace(tmp, path)


def read_model(path: Path, model: type[M]) -> M:
    return model.model_validate_json(path.read_text(encoding="utf-8"))


def write_parquet(path: Path, df: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp.parquet")
    df.to_parquet(tmp, index=False)
    _replace(tmp, path)


class RunStore:
    def __init__(self, settings: Settings | None = None) -> None:
        self.s = settings or get_settings()
        for d in (self.s.runs_dir, self.s.videos_dir, self.s.venues_dir):
            d.mkdir(parents=True, exist_ok=True)

    # ---- videos -------------------------------------------------------------------------
    def video_path(self, video_id: str) -> Path:
        video_exts = {".mp4", ".webm", ".mov", ".avi", ".mkv", ".m4v"}
        matches = [m for m in self.s.videos_dir.glob(f"{video_id}.*") if m.suffix.lower() in video_exts]
        if not matches:
            raise FileNotFoundError(video_id)
        return matches[0]

    def video_meta_path(self, video_id: str) -> Path:
        return self.s.videos_dir / f"{video_id}.json"

    # ---- runs ---------------------------------------------------------------------------
    def run_dir(self, run_id: str) -> Path:
        return self.s.runs_dir / run_id

    def path(self, run_id: str, artefact: str) -> Path:
        return self.run_dir(run_id) / ARTEFACTS.get(artefact, artefact)

    def exists(self, run_id: str, artefact: str) -> bool:
        return self.path(run_id, artefact).exists()

    def run_exists(self, run_id: str) -> bool:
        return self.path(run_id, "meta").exists()

    def load_meta(self, run_id: str) -> RunMeta:
        return read_model(self.path(run_id, "meta"), RunMeta)

    def save_meta(self, meta: RunMeta) -> None:
        write_json(self.path(meta.run_id, "meta"), meta)

    def read_df(self, run_id: str, artefact: str) -> pd.DataFrame:
        return pd.read_parquet(self.path(run_id, artefact))

    def write_df(self, run_id: str, artefact: str, df: pd.DataFrame) -> None:
        write_parquet(self.path(run_id, artefact), df)

    def list_runs(self) -> list[RunMeta]:
        out = []
        for d in sorted(self.s.runs_dir.iterdir()) if self.s.runs_dir.exists() else []:
            if (d / "meta.json").exists():
                try:
                    out.append(read_model(d / "meta.json", RunMeta))
                except Exception:
                    continue
        return out

    def clear_artefacts(self, run_id: str, keep: tuple[str, ...] = ("meta.json",)) -> None:
        d = self.run_dir(run_id)
        if not d.exists():
            return
        for p in d.iterdir():
            if p.name in keep:
                continue
            if p.is_dir():
                shutil.rmtree(p)
            else:
                p.unlink()

    # ---- simulations --------------------------------------------------------------------
    def sim_dir(self, run_id: str, sim_id: str) -> Path:
        return self.run_dir(run_id) / "simulations" / sim_id

    def find_sim(self, sim_id: str) -> tuple[str, Path] | None:
        for d in self.s.runs_dir.glob(f"*/simulations/{sim_id}"):
            return d.parent.parent.name, d
        return None
