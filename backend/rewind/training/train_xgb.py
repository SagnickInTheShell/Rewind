"""Training script for XGBoost risk escalation model."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)


def train_xgb_model(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Training XGBoost tabular model...")

    try:
        import xgboost as xgb
        X = np.random.randn(200, 12)
        y = (X[:, 0] > 0.3).astype(int)

        model = xgb.XGBClassifier(n_estimators=50, max_depth=3, learning_rate=0.1)
        model.fit(X, y)
        model.save_model(str(output_dir / "xgb_model.json"))
        logger.info("Saved XGBoost model to %s/xgb_model.json", output_dir)
    except ImportError:
        logger.warning("xgboost not installed, skipping.")


if __name__ == "__main__":
    train_xgb_model(Path("data/models"))
