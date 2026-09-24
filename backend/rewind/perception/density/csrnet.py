"""CSRNet crowd density estimation (Li, Zhang & Chen, CVPR 2018).

Front end: first 10 conv layers of VGG-16 (3 max-pools → output stride 8).
Back end: dilated convs 512-512-512-256-128-64 (dilation 2), then a 1×1 conv to one channel.
"""

from __future__ import annotations

import logging
from collections import OrderedDict
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import torch
from torch import nn

log = logging.getLogger(__name__)

FRONTEND_CFG: list[int | str] = [64, 64, "M", 128, 128, "M", 256, 256, 256, "M", 512, 512, 512]
BACKEND_CFG: list[int | str] = [512, 512, 512, 256, 128, 64]
IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


def _make_layers(cfg: list[int | str], in_channels: int, dilation: int) -> nn.Sequential:
    layers: list[nn.Module] = []
    c = in_channels
    for v in cfg:
        if v == "M":
            layers.append(nn.MaxPool2d(kernel_size=2, stride=2))
        else:
            assert isinstance(v, int)
            layers += [nn.Conv2d(c, v, kernel_size=3, padding=dilation, dilation=dilation), nn.ReLU(inplace=True)]
            c = v
    return nn.Sequential(*layers)


class CSRNet(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.frontend = _make_layers(FRONTEND_CFG, 3, dilation=1)
        self.backend = _make_layers(BACKEND_CFG, 512, dilation=2)
        self.output_layer = nn.Conv2d(64, 1, kernel_size=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return torch.as_tensor(self.output_layer(self.backend(self.frontend(x))))


def load_state(path: Path) -> dict[str, Any]:
    ckpt = torch.load(str(path), map_location="cpu", weights_only=False)
    state = ckpt.get("state_dict", ckpt) if isinstance(ckpt, dict) else ckpt
    clean: dict[str, Any] = OrderedDict()
    for k, v in state.items():
        clean[k[len("module."):] if k.startswith("module.") else k] = v
    return clean


class CSRNetDensity:
    """Wraps a CSRNet model and returns per-pixel density maps at frame resolution."""

    name = "csrnet"

    def __init__(self, weights: Path, device: str | None = None) -> None:
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model = CSRNet()
        self.model.load_state_dict(load_state(weights))
        self.model.to(self.device).eval()

    @classmethod
    def from_model(cls, model: CSRNet, device: str = "cpu") -> CSRNetDensity:
        obj = cls.__new__(cls)
        obj.device = device
        obj.model = model.to(device).eval()
        return obj

    @torch.inference_mode()
    def density_map(self, frame_bgr: np.ndarray) -> np.ndarray:
        h, w = frame_bgr.shape[:2]
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        x = torch.from_numpy(((rgb - IMAGENET_MEAN) / IMAGENET_STD).transpose(2, 0, 1)).unsqueeze(0).to(self.device)
        out = self.model(x)[0, 0].float().clamp_min(0).cpu().numpy()
        return upsample_preserving_sum(out, (h, w))


def upsample_preserving_sum(dmap: np.ndarray, size_hw: tuple[int, int]) -> np.ndarray:
    """Resize a density map to ``size_hw`` and rescale so the total count is unchanged."""
    total = float(dmap.sum())
    up = cv2.resize(dmap.astype(np.float32), (size_hw[1], size_hw[0]), interpolation=cv2.INTER_CUBIC)
    up = np.clip(up, 0, None)
    s = float(up.sum())
    if s > 0:
        up = up * (total / s)
    return up
