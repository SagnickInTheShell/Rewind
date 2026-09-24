"""Social force scenario runner generating snapshots for video rendering."""

from __future__ import annotations

from collections.abc import Iterator

from rewind.schemas.venue import Venue
from rewind.synthetic.render import Snapshot
from rewind.synthetic.scripted import ScriptedConfig, ScriptedCrowd


def social_force_snapshots(
    venue: Venue,
    duration_s: float = 180.0,
    fps: float = 25.0,
    seed: int = 0,
) -> Iterator[Snapshot]:
    """Yield snapshots using realistic crowd flow dynamics."""
    crowd = ScriptedCrowd(venue, ScriptedConfig(duration_s=duration_s, seed=seed))
    return crowd.run(fps=fps)
