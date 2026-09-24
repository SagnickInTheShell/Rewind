# Model weights

Weights are **not** committed. This directory is gitignored, except for this README.

| File | Used by | How to obtain |
|---|---|---|
| `yolov8s.pt` | Person detection | Downloaded automatically by Ultralytics on first use (AGPL-3.0). To pre-fetch it: `python -c "from ultralytics import YOLO; YOLO('yolov8s.pt')"`, then move the file here or set `perception.yolo_model` to its path |
| `csrnet.pth` | Density estimation (dense crowds) | See below. If it is missing, REWIND logs a warning and uses the KDE fallback. The run info panel shows which method was used |
| `temporal_tcn.pt`, `temporal_lstm.pt`, `xgb.json` (+ `*.card.json`) | Risk ML models | Produced by `make train` (`rewind.training.*`) from simulator data |

## CSRNet weights (ShanghaiTech)

REWIND implements CSRNet (Li, Zhang & Chen, CVPR 2018): the VGG-16 front end (first 10 conv layers) plus a dilated back end. It needs weights trained on **ShanghaiTech**:

- **Part A**: dense, congested crowds. Recommended for incidents.
- **Part B**: sparse street scenes.

Options:

1. **Train your own.** Get ShanghaiTech from its authors (Zhang et al., "Single-Image Crowd Counting via Multi-Column CNN", CVPR 2016). The dataset is for research use; check its terms. Then train with any public CSRNet training recipe.
2. **Use a published checkpoint** whose licence you have verified. Community re-implementations (e.g. `leeyeehoo/CSRNet-pytorch`) publish Part A/B checkpoints.

Place the file at `data/models/csrnet.pth`, or set `perception.density_model_path`. The loader accepts:

- a raw `state_dict`;
- a dict with a `state_dict` key;
- keys prefixed with `module.`, which are stripped automatically.

Layer names must follow `frontend.*`, `backend.*` and `output_layer.*`, as in the reference implementation.

REWIND does **not** download or bundle these weights, because their licensing is unclear.
