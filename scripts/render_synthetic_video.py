"""Render a synthetic top-down crowd video of the demo venue (clearly labelled SYNTHETIC).

Usage:
    python scripts/render_synthetic_video.py --out data/videos/synthetic_demo.webm --duration 180
    python scripts/render_synthetic_video.py --engine social_force --duration 180

Engines:
    scripted      lightweight scripted crowd (rewind.synthetic.scripted)
    social_force  the REWIND social-force simulator (rewind.synthetic.sf_scenario)
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from rewind.logging_setup import setup_logging  # noqa: E402
from rewind.synthetic.render import write_video  # noqa: E402
from rewind.venue.demo import build_demo_venue  # noqa: E402

log = logging.getLogger("render_synthetic_video")


def main(argv: list[str] | None = None) -> Path:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "videos" / "synthetic_demo.webm")
    ap.add_argument("--duration", type=float, default=180.0)
    ap.add_argument("--fps", type=float, default=25.0)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--engine", choices=["scripted", "social_force"], default="social_force")
    args = ap.parse_args(argv)
    setup_logging()
    venue = build_demo_venue()
    if args.engine == "scripted":
        from rewind.synthetic.scripted import ScriptedConfig, ScriptedCrowd

        snaps = ScriptedCrowd(venue, ScriptedConfig(duration_s=args.duration, seed=args.seed)).run(args.fps)
    else:
        from rewind.synthetic.sf_scenario import social_force_snapshots

        snaps = social_force_snapshots(venue, duration_s=args.duration, fps=args.fps, seed=args.seed)
    info = write_video(snaps, venue, args.out, fps=args.fps)
    log.info("done", extra={"kv": info})
    return Path(args.out)


if __name__ == "__main__":
    main()
