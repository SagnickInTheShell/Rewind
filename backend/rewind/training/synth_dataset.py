"""Synthetic dataset generator for crowd risk ML models."""

from __future__ import annotations

import logging
from pathlib import Path
import numpy as np
import pandas as pd

from rewind.schemas.venue import Venue
from rewind.simulation.macro_flow import MacroFlowSimulator

logger = logging.getLogger(__name__)


def generate_synthetic_dataset(output_dir: Path, num_scenarios: int = 100) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Generating %d synthetic training scenarios...", num_scenarios)
    # Generate feature sequences
    all_records = []
    for sc_id in range(num_scenarios):
        t_steps = 60
        base_dens = np.random.uniform(0.5, 3.5)
        trend = np.linspace(0, np.random.uniform(-0.5, 2.0), t_steps)
        dens = np.clip(base_dens + trend + np.random.normal(0, 0.1, t_steps), 0.1, 6.0)
        bottleneck = dens * np.random.uniform(0.3, 0.8)
        will_escalate = int(any(dens[t_steps // 2:] > 4.0))

        for t_idx, (d, b) in enumerate(zip(dens, bottleneck)):
            all_records.append({
                "scenario_id": sc_id,
                "t": float(t_idx),
                "density": float(d),
                "bottleneck_pressure": float(b),
                "crowd_pressure": float(d * 0.05),
                "will_escalate": will_escalate,
            })

    df = pd.DataFrame(all_records)
    df.to_parquet(output_dir / "synthetic_dataset.parquet", index=False)
    logger.info("Dataset generated: %d samples saved to %s", len(df), output_dir)


if __name__ == "__main__":
    generate_synthetic_dataset(Path("data/synthetic"))
