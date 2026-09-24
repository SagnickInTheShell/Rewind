"""Training script for temporal TCN and LSTM classifiers."""

from __future__ import annotations

import logging
from pathlib import Path

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

from rewind.risk.temporal_model import LSTMClassifier, TCNClassifier

logger = logging.getLogger(__name__)


def train_temporal_models(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Training TCN and LSTM models on synthetic sequences...")

    # Create dummy tensor dataset
    n_samples, seq_len, n_feats = 200, 30, 24
    X = torch.randn(n_samples, n_feats, seq_len)
    y = (X[:, 0, -1] > 0.5).float().unsqueeze(1)

    dataset = TensorDataset(X, y)
    loader = DataLoader(dataset, batch_size=32, shuffle=True)

    # 1. Train TCN
    tcn = TCNClassifier(in_channels=n_feats)
    optimizer = torch.optim.Adam(tcn.parameters(), lr=1e-3)
    criterion = nn.BCELoss()

    tcn.train()
    for epoch in range(5):
        for batch_x, batch_y in loader:
            optimizer.zero_grad()
            pred = tcn(batch_x)
            loss = criterion(pred, batch_y)
            loss.backward()
            optimizer.step()

    torch.save(tcn.state_dict(), output_dir / "tcn.pt")
    logger.info("Saved TCN model to %s/tcn.pt", output_dir)

    # 2. Train LSTM
    lstm = LSTMClassifier(in_features=n_feats)
    optimizer = torch.optim.Adam(lstm.parameters(), lr=1e-3)
    lstm.train()
    for epoch in range(5):
        for batch_x, batch_y in loader:
            # transpose for LSTM: (batch, seq_len, n_feats)
            bx_trans = batch_x.transpose(1, 2)
            optimizer.zero_grad()
            pred = lstm(bx_trans)
            loss = criterion(pred, batch_y)
            loss.backward()
            optimizer.step()

    torch.save(lstm.state_dict(), output_dir / "lstm.pt")
    logger.info("Saved LSTM model to %s/lstm.pt", output_dir)


if __name__ == "__main__":
    train_temporal_models(Path("data/models"))
