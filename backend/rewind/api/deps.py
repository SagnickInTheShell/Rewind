"""Shared API dependencies."""

from __future__ import annotations

from rewind.api.errors import not_found
from rewind.settings import Settings, get_settings
from rewind.storage.run_store import RunStore


def store() -> RunStore:
    return RunStore(get_settings())


def settings() -> Settings:
    return get_settings()


def require_run(st: RunStore, run_id: str) -> None:
    if not st.run_exists(run_id):
        raise not_found("run", run_id)
