from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _isolated_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Every test gets its own data dir so runs/videos never leak between tests."""
    data = tmp_path / "data"
    for sub in ("videos", "venues", "runs", "models", "synthetic"):
        (data / sub).mkdir(parents=True)
    monkeypatch.setenv("REWIND__APP__DATA_DIR", str(data))
    monkeypatch.setenv("REWIND__RISK__MODELS_DIR", str(data / "models"))
    from rewind.settings import get_settings

    get_settings.cache_clear()
    yield data
    get_settings.cache_clear()


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    try:
        import torch

        has_gpu = bool(torch.cuda.is_available())
    except Exception:
        has_gpu = False
    skip_gpu = pytest.mark.skip(reason="no CUDA GPU")
    for item in items:
        if "gpu" in item.keywords and (not has_gpu or os.environ.get("CI")):
            item.add_marker(skip_gpu)
