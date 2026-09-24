"""Write data/venues/demo_venue.json from rewind.venue.demo.build_demo_venue()."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from rewind.venue.demo import build_demo_venue  # noqa: E402
from rewind.venue.graph import save_venue, validate_venue  # noqa: E402


def main() -> None:
    venue = build_demo_venue()
    errors = validate_venue(venue)
    if errors:
        raise SystemExit("demo venue invalid: " + "; ".join(errors))
    out = ROOT / "data" / "venues" / "demo_venue.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    save_venue(venue, out)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
