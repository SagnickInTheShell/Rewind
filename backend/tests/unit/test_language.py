"""Section 13: UI copy and docs must never overclaim."""

from __future__ import annotations

from pathlib import Path

import pytest

from rewind.explain.narrator import BANNED_PHRASES
from rewind.schemas.validation import CAVEAT

ROOT = Path(__file__).resolve().parents[3]
SCANNED = [ROOT / "frontend" / "src", ROOT / "README.md", ROOT / "docs"]
EXCLUDED = {"REWIND_AGENT_PROMPT.md"}


def _files() -> list[Path]:
    out: list[Path] = []
    for p in SCANNED:
        if p.is_file():
            out.append(p)
        elif p.is_dir():
            out += [f for f in p.rglob("*") if f.suffix in {".ts", ".tsx", ".md"} and f.name not in EXCLUDED]
    return out


@pytest.mark.parametrize("path", _files(), ids=lambda p: str(p.relative_to(ROOT)))
def test_no_banned_phrases(path: Path) -> None:
    text = path.read_text(encoding="utf-8", errors="ignore").lower()
    found = [b for b in BANNED_PHRASES if b in text]
    assert not found, f"{path}: {found}"


def test_caveat_wording() -> None:
    assert "Not a guarantee of real-world outcomes" in CAVEAT
    assert "support, not replace, trained crowd-safety professionals" in CAVEAT
