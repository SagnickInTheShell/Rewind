# REWIND — Build Plan

_Living document. Updated at the end of every phase to reflect what was actually built._

## 1. What we are building

REWIND turns uploaded CCTV footage of a crowd plus a venue floor plan into:

1. **Perception**: people detected (YOLOv8) and tracked (ByteTrack) where the crowd is sparse, with density (CSRNet, KDE fallback) and optical flow (Farneback) where it is packed. A per-zone fusion step blends the two.
2. **Crowd features** per zone per 1 s window, in one central contract (`ZoneFeatures`): density, speed stats, velocity variance, direction entropy, counterflow, flow instability, in/outflow, bottleneck pressure, crowd pressure.
3. **Risk**: an explainable physics scorer (weighted, normalised features), plus TCN/LSTM and XGBoost models trained on simulator data, combined in an ensemble. A hysteresis state machine yields LOW / MEDIUM / HIGH / CRITICAL without flicker.
4. **Reconstruction**: rule-based event detection, a causal chain over the venue graph (origin zone and time to peak), and a narrated timeline.
5. **Explanation**: exact physics contributions or SHAP, with template-based hedged narratives (no LLM).
6. **Rewind and what-if**: initialise a digital twin from the reconstructed state at `t0`, apply interventions (open/close/widen portal, redirect, restrict entry), and simulate with social force (micro) or a macro flow model (fast). The sim emits the **same `ZoneTimeseries`**, so the same scorer and charts apply.
7. **Comparison, prevention plan, validation**: scenario metrics with seed spread, ranked recommendations with a mandatory caveat, and a do-nothing replay against observed footage with calibration and validation on non-overlapping halves.

## 2. Core architecture decisions

- **One contract for real and simulated data.** `ZoneTimeseries` / `features.parquet` is the pivot. Everything downstream of features (risk, explain, events, charts) is origin-agnostic.
- **Artefact-cached pipeline.** Each stage writes to `data/runs/{run_id}/` and is skipped if its artefact exists (`force` overrides). This makes `/api/demo/load` instant.
- **Pure functions at the core.** `crowd_metrics.py`, the physics scorer, the state machine, event triggers and the social-force kernels are pure and unit-tested with synthetic inputs. The I/O-heavy code (video, models) wraps them thinly.
- **Graceful degradation.** Missing CSRNet weights → KDE fallback. Missing ML models → ensemble renormalises to physics only. DeepSORT unavailable → ByteTrack. Each fallback is recorded in `meta.json` and shown in the UI.
- **Config-driven.** All tunables are in `backend/config/default.yaml`, loaded into a typed `Settings` (pydantic-settings, env override `REWIND__SECTION__KEY`). Config hash is stored per run and per model card.
- **Frontend state.** A single Zustand `currentTime` drives the video, overlay, chart, zone grid and explanations. Canvas renderers (`OverlayRenderer`, `TwinRenderer`) are framework-free classes.
- **Binary agent frames.** float16 little-endian positions plus a JSON header, decoded with `DataView` in the browser, so 3,000 agents play back at 60 fps.

## 3. Phase order

Each phase ends with its acceptance checks, a report, and a commit (`phase-N: ...`).

| # | Phase | Key deliverables | Acceptance |
|---|---|---|---|
| 0 | Scaffold | Tree, `pyproject.toml`, `package.json`, Makefile (+ `scripts/dev.ps1` fallback), Docker/compose, settings loader, logging, `/api/health`, React shell with routing and theme, CI workflow | Both apps start; health OK; `docker compose up`; ruff + mypy + tsc + eslint pass |
| 1 | Contracts | All pydantic schemas, mirrored TS types, `DATA_CONTRACTS.md` generator, fixture factories (py + ts) | Round-trip tests; frontend renders fixture timeline/risk/twin |
| 2 | Ingest, calibration, venue | Video reader (timestamp sampling, resize), homography, zone masks, pixel area map, venue loader/validator/graph, `demo_venue.json` | Homography round trip < 0.5 px, area test, validation errors, routing tests |
| 3 | Perception | YOLO detector, ByteTrack + DeepSORT interface, trajectories (SavGol, speed clip), CSRNet + KDE fallback, optical flow, fusion, overlay data | 30 s clip → tracks/density/flow Parquet; fallback works with no weights |
| 4 | Features | Crowd metrics (pure), zone feature engine, portal crossings/continuity, smoothing | Synthetic vector-field tests; `features.parquet` for the clip |
| 5 | Physics risk, states, explanations | Physics scorer, hysteresis + dwell + overrides, contributions, narrator | Monotonicity, no flicker on noisy input, narratives present |
| 6 | Reconstruction | Event detector, causal chain (cause-type matrix, weighted DAG), timeline summary | Synthetic escalation → expected ordered chain and origin zone |
| 7 | API, jobs, Analysis UI | `analyze.py` orchestration, job manager, WebSocket progress, all run routes, Upload and Analysis pages | Upload → analyse → scrub with synced overlay, chart, grid, events, explanations |
| 8 | Simulation | Spatial hash, social force (NumPy, optional Numba), routing, macro model, initializer, interventions, recorder, runner (process pool) | Conservation, wall, two-room tests; 1,000 agents × 240 s < 60 s CPU; macro < 2 s |
| 9 | Rewind UI | Intervention builder and presets, side-by-side twin, comparison table, prevention plan | 5 scenarios from `t0`, 60 fps playback, table and plan populated |
| 10 | Validation and calibration | Replay, Nelder–Mead calibration on first 50 %, validation card | Report with non-overlapping windows |
| 11 | ML | Synthetic dataset (≥ 2,000 macro, ≥ 100 SF), TCN + LSTM + XGBoost, evaluation (PR-AUC, lead time), ensemble, SHAP toggle | Model cards, eval report, ensemble shown in UI |
| 12 | Demo and polish | Synthetic top-down video renderer, `make demo`, `/api/demo/load`, DEMO_SCRIPT, README, ARCHITECTURE (Mermaid), perf pass | Clean clone → `make setup && make demo && make dev` works; full suite green |

### Dependency notes
- Phase 3 needs a test clip. Until real footage is available, a **minimal version of `scripts/render_synthetic_video.py` is pulled forward into Phase 3** (simple scripted agents, no social force yet). It becomes the full social-force renderer in Phase 12.
- Phase 7's risk columns show physics-only scores until Phase 11 adds the ML models. The ensemble already renormalises when models are missing.
- The Phase 11 training labels come from the physics state machine running on simulator output, so Phases 5 and 8 must be solid first.

## 4. Environment facts (this machine)

- Windows 11, Python 3.11.9, Node 22.19, npm 10.9, Docker 28.5, NVIDIA RTX 3050 6 GB (CUDA available for YOLO/CSRNet/training).
- **`make` is not installed.** The Makefile is still the canonical interface (it works in Docker, CI and WSL). A `scripts/dev.ps1` exposes the same targets (`setup`, `dev`, `test`, `lint`, `demo`, `train`) for native Windows. See DECISIONS.md.
- The parent directory `C:\Users\sagni` is itself a git repo. REWIND has its **own** repository at `C:\Users\sagni\Rewind` (branch `main`), so phase commits never touch the home-directory repo.

## 5. Risks and mitigations

| Risk | Mitigation |
|---|---|
| No licensed real crowd footage | Synthetic video renderer. The UI labels synthetic runs clearly. |
| CSRNet weights not bundled (licensing) | KDE fallback; `data/models/README.md` explains how to obtain the weights |
| Social force too slow for 1,000 agents on CPU | Spatial hash + vectorised NumPy; Numba JIT when installed; macro model for sweeps |
| ML overfits to synthetic data | Scenario-level splits; procedurally varied venues; physics scorer remains the explainable primary signal |
| Overclaiming | Section 13 copy rules enforced in narrator templates; a test greps UI strings and docs for banned phrases |

## 6. Phase log

### Phase 0 — Scaffold ✅
- **Built:** repo tree; `pyproject.toml` (with `dev`, `perf` and `deepsort` extras); `package.json` (Vite, React 18, TypeScript strict, Tailwind, Zustand, TanStack Query, Recharts, lucide, Vitest); Makefile plus `scripts/dev.ps1`; backend and frontend Dockerfiles; `docker-compose.yml` with a `gpu` profile; typed settings loader (YAML plus `REWIND__*` env overrides, config hash); key=value structured logging; `/api/health` (versions, GPU, model availability); uniform error envelope; React shell with routing and the control-room theme; GitHub Actions CI.
- **Tests:** backend 6 passed (settings, health, error envelope). Frontend 1 passed. ruff, mypy `--strict`, eslint and tsc are clean.
- **Acceptance:**
  - `uvicorn` and `vite` start, and `/api/health` returns OK, directly and through the Vite proxy.
  - `docker compose up` brings up both services; health is OK through the frontend proxy.
- **Known issues:**
  - `make` is not installed on the dev machine. `scripts/dev.ps1` mirrors the targets.
  - Ports 5173 and 5174 are used by other local apps, so Vite picks the next free port in local dev. Docker binds 5173 when it is free.
  - The Docker image uses CPU torch; GPU is available via the `gpu` profile.

### Phase 1 — Contracts ✅
- **Built:**
  - All pydantic contracts in `rewind/schemas/`: video, venue, perception (+ overlay frame), features, risk and explanation, events and timeline, simulation (+ status and comparison), validation and strategy, runs and jobs.
  - Mirrored TypeScript types in `frontend/src/types/index.ts`.
  - `scripts/gen_data_contracts.py` → `docs/DATA_CONTRACTS.md`.
  - Deterministic fixture factories for every contract: `rewind/fixtures.py` and `frontend/src/lib/fixtures.ts`.
  - First reusable visuals: `RiskChart`, `EventList`, `CausalChain`, `TwinRenderer`/`TwinCanvas`, UI primitives, colour and format helpers.
  - A `/dev/fixtures` page that renders the timeline, risk and twin from fixtures.
- **Tests:**
  - Backend: 25 passed (JSON round-trip for every contract, bounds, intervention validation, rejection of interventions before `t0`).
  - Frontend: 10 passed (fixture rendering, colour mapping, time formatting, twin transform).
- **Additive fields beyond Section 5:** `VideoMeta.synthetic`, `ScenarioResult.name` and `interventions`, and ValidationReport UI context (`calibration_window`, `validation_window`, `worst_zone`, observed/simulated series). Recorded in DECISIONS.md.

### Phase 2 — Ingest, calibration, venue ✅
- **Built:**
  - `VideoReader`: timestamp-based sampling (robust to variable frame rate), resizing to `max_width` with the scale kept, time-window reads.
  - `probe` → `VideoMeta`.
  - Homography: fit with RANSAC when there are more than 4 points; clear errors for fewer than 4 points or degenerate input; vectorised pixel↔world; `scale_homography` for resized frames; zone masks via `fillPoly`; exact per-pixel ground area from the Jacobian (`|det H| / w³`).
  - Venue graph (networkx):
    - Zones plus `OUTSIDE`; merged parallel portals; capacity = width × specific flow.
    - Queries: upstream, downstream, neighbours, outgoing capacity, exit and entry portals, nearest portal.
    - Congestion-weighted routing with an optional `via` zone; `apply_interventions` for portal changes at time `t`.
  - Venue validator: unknown zones, uniqueness, reachability from sources, source→exit, sink exit portals, portal-on-boundary within 0.2 m, calibration of at least 4 points.
  - Geometry helpers: walls including closed portals, vectorised zone locator, Poisson-disk sampling that relaxes spacing when overfull, portal normals.
  - Demo venue builder, `data/venues/demo_venue.json` and `data/venues/README.md`.
- **Tests:** 29 new, all passing.
  - Homography round trip < 0.5 px; known-square area and perspective area within 5 %.
  - Every venue validation error path; demo JSON matches the builder.
  - Routing, Gate C opening, congestion diversion, widen capacity, zone lookup, sampling.
  - Video sampling and time windows.
- **Decisions:**
  - Calibration image points are in original video pixels.
  - The demo calibration matches the synthetic top-down camera (32 px/m).

### Phase 3 — Perception ✅
- **Built:**
  - `YoloDetector`: YOLOv8, person class only, batched on GPU with FP16. Weights are fetched into `data/models`.
  - `BlobDetector` for synthetic top-down renders (D7).
  - `Tracker` protocol with `ByteTrackTracker` (supervision) and `DeepSortTracker` (optional `deep-sort-realtime`; falls back to ByteTrack).
  - Trajectories: ground point → world → Savitzky–Golay (5, 2) → finite-difference velocity; drops tracks under 1 s; speeds clipped at 4 m/s; zone assignment with shapely prepared geometries.
  - CSRNet (VGG-16 front end with 10 convs, dilated back end, 1×1 output). The loader handles `module.` prefixes and `state_dict` wrappers. Upsampling preserves the sum.
  - KDE fallback: normalised Gaussians at head points, σ ∝ bbox height, correct at frame edges.
  - Farneback flow → world velocities on an 8 px grid, masked to occupied cells, with per-zone mean \|curl\|.
  - Hybrid fusion: blend weight, fused count, velocity-source switch.
  - Overlay index and `GET /api/runs/{id}/overlay`.
  - Privacy `blur_heads` (top 25 % of each bbox).
  - Minimal scripted synthetic renderer: `rewind/synthetic/{scripted,render}.py` and `scripts/render_synthetic_video.py`.
  - First stages of `pipeline/analyze.py` with artefact caching.
- **Acceptance:**
  - On a 30 s synthetic clip (151 processed frames), detections equal ground truth (12, 20 and 45 people at t = 10, 20 and 28 s). KDE map counts are within ±1.4 of the detections. Tracks give a 1.22 m/s southward median. `tracks`, `density_zone` and `flow_zone` Parquet files are written.
  - The overlay endpoint returns tracks, 9 zones and a heatmap. With no weights, the run records `density: kde`.
  - Timings (RTX 3050): blob detect+track 13 s, density 3 s, flow 8 s for 30 s of video.
- **Tests:** 72 backend passing. They cover perception units (KDE, CSRNet, blob counts, YOLO on `bus.jpg`, ByteTrack ID stability, trajectories, flow translation recovery, fusion, blur) and an integration test (8 s clip → artefacts, accuracy against ground truth, overlay API, cached rerun).
- **Known issues:**
  - The CSRNet path is verified only with random weights, because no licensed weights are bundled.
  - YOLO accuracy on real footage depends on the camera; see `data/models/README.md`.

### Phase 4 — Features ✅
- **Built:**
  - `crowd_metrics.py`: pure functions for speed stats, velocity variance, dominant direction (robust to bidirectional flow), speed-weighted direction entropy, counterflow index, flow instability, bottleneck pressure, crowd pressure (Helbing 2007) and portal flux.
  - `zone_features.py`: `FeatureEngine` (raw window rows, then instability, causal smoothing and range enforcement), `downstream_capacity`, video window assembly (fusion per zone per 1 s window, track-transition or portal-flux in/outflow) and `ZoneTimeseries` conversion.
  - Analysis stage `features` → `features.parquet` + `features_meta.json`.
- **Acceptance:**
  - Vector-field tests: uniform flow gives entropy 0 and counterflow 0; 50/50 opposing streams give counterflow ≈ 0.5; random directions give entropy ≈ 1.
  - Hypothesis property tests keep entropy and counterflow within 0..1.
  - The 30 s clip gives `features.parquet` with 270 rows (9 zones × 30 s). A2 inflow ≈ 3.5–4 p/s against a scripted 4.2 p/s.
- **Tests:** 89 backend passing.
- **Known issue:** `mypy` reports 2 forward references to `run_risk` and `run_reconstruction` until Phases 5–6 land.
