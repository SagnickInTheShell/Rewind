from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from rewind.settings import DEFAULT_CONFIG, load_settings


def test_default_config_loads() -> None:
    s = load_settings()
    assert s.video.fps_processed == 5.0
    assert abs(sum(s.risk.weights.values()) - 1.0) < 1e-9
    assert s.risk.thresholds.critical > s.risk.thresholds.high > s.risk.thresholds.medium


def test_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REWIND__VIDEO__FPS_PROCESSED", "2.5")
    assert load_settings().video.fps_processed == 2.5


def test_bad_weights_rejected(tmp_path: Path) -> None:
    raw = yaml.safe_load(DEFAULT_CONFIG.read_text(encoding="utf-8"))
    raw["risk"]["weights"]["density"] = 0.9
    p = tmp_path / "bad.yaml"
    p.write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="sum to 1"):
        load_settings(p)


def test_config_hash_stable() -> None:
    assert load_settings().config_hash() == load_settings().config_hash()
