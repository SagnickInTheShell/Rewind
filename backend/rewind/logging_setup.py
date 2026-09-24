"""Structured logging configuration (key=value style, one line per record)."""

from __future__ import annotations

import logging
import sys
from typing import Any

_CONFIGURED = False


class KeyValueFormatter(logging.Formatter):
    """Formats ``extra={"kv": {...}}`` as ``key=value`` pairs after the message."""

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        kv: dict[str, Any] | None = getattr(record, "kv", None)
        if kv:
            base += " " + " ".join(f"{k}={v}" for k, v in kv.items())
        return base


def setup_logging(level: str = "INFO") -> None:
    global _CONFIGURED
    if _CONFIGURED:
        logging.getLogger().setLevel(level)
        return
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(KeyValueFormatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    for noisy in ("ultralytics", "matplotlib", "PIL", "numba", "shap"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    _CONFIGURED = True


def kv(**fields: Any) -> dict[str, dict[str, Any]]:
    """Helper: ``log.info("stage done", extra=kv(stage="tracking", n=12))``."""
    return {"kv": fields}
