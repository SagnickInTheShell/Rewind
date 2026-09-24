# Decisions Log

Ambiguities resolved during the build: what was chosen and why.

| # | Date | Decision | Rationale |
|---|---|---|---|
| D1 | 2026-09-24 | REWIND lives in its own git repo at `C:\Users\sagni\Rewind` (branch `main`). | The parent home directory is a git repo with unrelated staged files. Phase commits must not land there. |
| D2 | 2026-09-24 | The Makefile stays canonical, and `scripts/dev.ps1` mirrors its targets. | `make` is not installed on the Windows dev machine. It is available in Docker, CI and WSL. |
| D3 | 2026-09-24 | A minimal synthetic video renderer is built in Phase 3, not only in Phase 12. | Perception acceptance needs a 30 s clip, and no licensed real footage is bundled. |
| D5 | 2026-09-24 | Additive contract fields: `VideoMeta.synthetic`; `ScenarioResult.name` and `interventions`; `ValidationReport` UI context (`calibration_window`, `validation_window`, `worst_zone`, observed/simulated series); `RiskSeries` wrapper (`zones`, `global_risk`, `methods`). | The UI must label synthetic footage, name scenarios, and plot validation without extra round trips. No Section 5 field was removed or renamed. |
| D6 | 2026-09-24 | Strategy contracts (`Recommendation`, `PreventionPlan`) live in `schemas/validation.py`, alongside the shared `CAVEAT` string. | The Section 3 file list has no `schemas/strategy.py`, and the caveat is shared by both. |
| D7 | 2026-09-24 | Synthetic top-down renders are detected with a classical `BlobDetector` (saturation mask + distance-transform peaks). Real footage uses YOLOv8. `perception.detector: auto` picks blob when `VideoMeta.synthetic`, else YOLO. The run info shows the detector used. | YOLO is trained on photographs and does not detect rendered discs as people. Without this, the synthetic end-to-end pipeline would be empty. |
| D8 | 2026-09-24 | `perception.camera_view`: `oblique` uses the bbox bottom-centre as the ground point and a head point near the top; `top_down` uses the bbox centre for both. `auto` = top_down for synthetic runs. | The spec's bottom-centre foot point is wrong for overhead cameras. |
| D9 | 2026-09-24 | Synthetic videos are VP8/WebM. | The OpenCV wheels cannot encode H.264 on Windows (no OpenH264), and browsers cannot play `mp4v`. VP8 plays in Chrome, Firefox and Edge and reads back in OpenCV. |
| D10 | 2026-09-24 | Zone area for density uses the **visible** ground area (Σ pixel-area × mask), falling back to the polygon area when the zone is out of view. | Counts only cover the visible part of a zone, so dividing by the full polygon area would under-report density. |
| D11 | 2026-09-24 | Perception runs as 4 separate passes over the video (detect+track, density, flow, plus the trajectory post-process). Each writes its own artefact. | Independent caching and clear stage progress. Decoding at 5 fps is cheap compared with the models. |
| D12 | 2026-09-24 | Flow samples are masked by a coarse density heat grid (people/m², `density_min_threshold` = 0.1) and subsampled to ≤ 200 vectors per zone per frame (seeded). Mean \|curl\| per zone and frame goes in `flow_curl.parquet`. | "Ignore empty floor" works with either density method, and the size of `flow_zone.parquet` stays bounded. |
| D13 | 2026-09-24 | Overlay data is served from an in-memory per-run index (LRU of 4 runs) built from the Parquet/NPZ artefacts, instead of per-timestamp files. | Lookups take a few milliseconds after the first load, which meets the < 100 ms target without thousands of files. |
| D14 | 2026-09-24 | YOLO weights are fetched into `data/models/`. `supervision` is pinned below 0.31, where `sv.ByteTrack` is removed. | Keeps weights out of the working directory and the tracker API stable. |
| D4 | 2026-09-24 | The crowd-pressure turbulence threshold (0.02 s⁻²), specific flow (1.3 p/m/s) and social-force parameters (A, B, k, κ, τ, v0) are literature-derived defaults (Helbing et al. 2000, 2007; Weidmann). | Phase 10 calibrates them per venue. |
