# REWIND — Master Build Prompt for the Coding Agent

> **How to use this file:** Put it in the root of an empty repository as `REWIND_AGENT_PROMPT.md` and tell your agent:
> *"Read REWIND_AGENT_PROMPT.md fully. Then build the project phase by phase exactly as specified. After each phase, run its acceptance checks, fix failures, and report before moving on."*

---

## 0. Your role and working rules

You are a senior engineer building **REWIND**, a complete, production-quality hackathon project. You write clean, typed, tested, documented code. Follow these rules for the entire build:

1. **Read this whole document before writing any code.** Then write `docs/PLAN.md` summarising your understanding and the phase order, and keep it updated as you go.
2. **Build in the phases defined in Section 14, in order.** Do not start a phase until the previous phase's acceptance checks pass.
3. **The data contracts in Section 5 are law.** Every module reads and writes those exact schemas. If you need to change one, update the schema file, the TypeScript types, and this plan together.
4. **Nothing is dropped.** Every component in this document must exist and work. If something is hard, build a simple working version first, then improve it.
5. **Every module gets unit tests** (`pytest` for backend, `vitest` for frontend). Run them after every change you make to that module.
6. **No hard-coded paths or magic numbers.** All tunable values live in `backend/config/default.yaml` and are loaded through a typed settings object.
7. **Type everything.** Python: full type hints, `pydantic` v2 models, `mypy --strict`-clean where practical. TypeScript: `strict: true`, no `any`.
8. **Log, don't print.** Use Python `logging` with structured messages; progress for long jobs goes over WebSocket.
9. **Deterministic by default.** Every random process takes a seed from config or request.
10. **Commit after each phase** with a clear message (`phase-3: crowd feature engine`).
11. **When a requirement is ambiguous, pick the simplest reasonable option, write the decision in `docs/DECISIONS.md`, and continue.** Do not stall.
12. **Never claim more than the system does.** UI copy and docs must follow the positioning rules in Section 13.

---

## 1. Project overview

**Name:** REWIND
**Subtitle:** AI Incident Reconstruction & Prevention Engine
**Tagline:** "Reconstruct the past. Simulate the alternative."

**What it does:** REWIND takes CCTV footage of a crowd plus a venue floor plan. It:

1. Detects and tracks people, estimates crowd density and motion.
2. Computes crowd-dynamics features per zone over time (density, velocity, direction conflict, flow instability, bottleneck pressure, crowd pressure).
3. Scores escalating risk over time with a physics-based scorer **and** a temporal ML model.
4. Reconstructs the incident as a timeline of events and a causal chain showing where it started and how it spread.
5. Explains **why** risk rose, using feature contributions and plain-language reasoning.
6. Lets the operator **rewind** to any earlier moment and run **what-if simulations** (open a gate, redirect the crowd, restrict entry, widen an exit, do nothing) in a **digital twin** of the venue.
7. Compares scenarios side by side and produces a **prevention strategy**.
8. **Validates** the simulator by replaying the "do nothing" scenario and measuring how closely it matches the real footage.

**Scope:** 100% software. Crowd incidents only. Input is uploaded video (no live cameras needed).

---

## 2. Tech stack

### Backend (Python 3.11)
| Purpose | Library |
|---|---|
| API | `fastapi`, `uvicorn[standard]`, `python-multipart` |
| Realtime progress & streaming | FastAPI WebSockets |
| Schemas & settings | `pydantic` v2, `pydantic-settings`, `pyyaml` |
| Video & vision | `opencv-python-headless`, `numpy`, `scipy` |
| Detection | `ultralytics` (YOLOv8, person class) |
| Tracking | `supervision` (ByteTrack) — also implement a DeepSORT-compatible interface so the tracker is swappable |
| Density estimation | `torch`, `torchvision` (CSRNet implementation) |
| Tabular ML | `xgboost`, `scikit-learn`, `shap` |
| Temporal ML | `torch` (TCN and LSTM) |
| Graph | `networkx` |
| Geometry | `shapely` |
| Data storage | `pandas`, `pyarrow` (Parquet) |
| Performance (optional) | `numba` for the simulator inner loop |
| Testing & quality | `pytest`, `pytest-asyncio`, `httpx`, `ruff`, `mypy` |

### Frontend
| Purpose | Library |
|---|---|
| Framework | React 18 + TypeScript + Vite |
| Styling | Tailwind CSS |
| State | Zustand |
| Server data | TanStack Query |
| Charts | Recharts |
| Twin & overlays | HTML5 Canvas 2D (custom renderer, requestAnimationFrame) |
| Icons | lucide-react |
| Testing | Vitest + React Testing Library |

### Infrastructure
- Docker + `docker-compose.yml` (services: `backend`, `frontend`), optional GPU profile.
- `Makefile` with `make setup`, `make dev`, `make test`, `make lint`, `make demo`, `make train`.

---

## 3. Repository structure

Create exactly this layout (add files as needed, but keep the structure):

```
rewind/
├── REWIND_AGENT_PROMPT.md
├── README.md
├── Makefile
├── docker-compose.yml
├── .env.example
├── docs/
│   ├── PLAN.md
│   ├── DECISIONS.md
│   ├── ARCHITECTURE.md          # includes Mermaid diagrams
│   ├── DATA_CONTRACTS.md        # generated from pydantic schemas
│   └── DEMO_SCRIPT.md
├── data/
│   ├── videos/                  # uploaded videos (gitignored)
│   ├── venues/                  # venue JSON files
│   │   └── demo_venue.json
│   ├── runs/                    # per-run outputs (gitignored)
│   ├── models/                  # weights (gitignored), with README on how to obtain
│   └── synthetic/               # simulator-generated training data (gitignored)
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── config/
│   │   └── default.yaml
│   ├── rewind/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI app factory
│   │   ├── settings.py          # typed config loader
│   │   ├── logging_setup.py
│   │   ├── schemas/             # ALL pydantic data contracts
│   │   │   ├── video.py
│   │   │   ├── perception.py
│   │   │   ├── features.py
│   │   │   ├── risk.py
│   │   │   ├── events.py
│   │   │   ├── venue.py
│   │   │   ├── simulation.py
│   │   │   └── validation.py
│   │   ├── ingest/
│   │   │   └── video_reader.py
│   │   ├── calibration/
│   │   │   └── homography.py
│   │   ├── perception/
│   │   │   ├── detector.py
│   │   │   ├── tracker.py
│   │   │   ├── trajectories.py
│   │   │   ├── density/
│   │   │   │   ├── csrnet.py
│   │   │   │   └── fallback_kde.py
│   │   │   ├── optical_flow.py
│   │   │   └── fusion.py        # hybrid sparse/dense switching
│   │   ├── features/
│   │   │   ├── zone_features.py
│   │   │   └── crowd_metrics.py # pure math functions
│   │   ├── risk/
│   │   │   ├── physics_scorer.py
│   │   │   ├── temporal_model.py
│   │   │   ├── xgb_model.py
│   │   │   ├── ensemble.py
│   │   │   └── states.py        # hysteresis state machine
│   │   ├── explain/
│   │   │   ├── contributions.py
│   │   │   └── narrator.py
│   │   ├── reconstruction/
│   │   │   ├── event_detector.py
│   │   │   ├── causal_chain.py
│   │   │   └── timeline.py
│   │   ├── venue/
│   │   │   ├── graph.py
│   │   │   └── geometry.py
│   │   ├── simulation/
│   │   │   ├── social_force.py
│   │   │   ├── spatial_hash.py
│   │   │   ├── routing.py
│   │   │   ├── macro_flow.py    # fast graph-level flow model
│   │   │   ├── initializer.py   # reconstructed state -> agents
│   │   │   ├── interventions.py
│   │   │   ├── runner.py
│   │   │   └── recorder.py
│   │   ├── validation/
│   │   │   ├── replay.py
│   │   │   └── calibrate.py
│   │   ├── strategy/
│   │   │   └── prevention.py
│   │   ├── training/
│   │   │   ├── synth_dataset.py
│   │   │   ├── train_temporal.py
│   │   │   ├── train_xgb.py
│   │   │   └── evaluate.py
│   │   ├── pipeline/
│   │   │   ├── analyze.py       # orchestrates the full analysis job
│   │   │   └── jobs.py          # async job manager + progress
│   │   ├── storage/
│   │   │   └── run_store.py
│   │   └── api/
│   │       ├── videos.py
│   │       ├── analysis.py
│   │       ├── venues.py
│   │       ├── simulations.py
│   │       ├── validation.py
│   │       └── ws.py
│   └── tests/
│       ├── unit/
│       └── integration/
└── frontend/
    ├── Dockerfile
    ├── package.json
    ├── vite.config.ts
    ├── tailwind.config.ts
    ├── src/
    │   ├── main.tsx
    │   ├── App.tsx
    │   ├── api/                 # typed client + WebSocket hook
    │   ├── types/               # mirrors backend schemas exactly
    │   ├── store/               # Zustand stores
    │   ├── pages/
    │   │   ├── UploadPage.tsx
    │   │   ├── AnalysisPage.tsx
    │   │   └── RewindPage.tsx
    │   ├── components/
    │   │   ├── video/           # player + overlay canvas
    │   │   ├── zones/           # zone heatmap grid
    │   │   ├── timeline/        # risk chart + event list + scrubber
    │   │   ├── explain/         # contribution bars + narrative
    │   │   ├── twin/            # digital twin canvas renderer
    │   │   ├── scenarios/       # intervention builder + comparison table
    │   │   ├── validation/
    │   │   ├── strategy/
    │   │   └── ui/              # buttons, cards, badges, layout
    │   └── lib/                 # colors, formatters, math helpers
    └── tests/
```

---

## 4. System architecture

```
CCTV VIDEO + VENUE JSON
        │
        ▼
[Ingest] frame sampling, metadata
        │
        ▼
[Calibration] homography pixel <-> world metres, zone polygons
        │
        ├──────────────────────────────┐
        ▼                              ▼
[Detection + Tracking]           [Density (CSRNet)]      [Optical Flow]
 YOLOv8 + ByteTrack               per-pixel density        Farneback dense flow
        │                              │                        │
        └───────────────┬──────────────┴────────────────────────┘
                        ▼
                [Fusion] hybrid sparse/dense per zone
                        ▼
                [Crowd Feature Engine] per zone, per 1 s window
                        ▼
      ┌─────────────────┼──────────────────┐
      ▼                 ▼                  ▼
[Physics scorer]  [Temporal model]   [XGBoost model]
      └─────────────────┼──────────────────┘
                        ▼
                [Ensemble + state machine]  → risk timeline
                        ▼
      ┌─────────────────┼──────────────────┐
      ▼                 ▼                  ▼
[Explainability]  [Event detector]   [Causal chain on venue graph]
                        ▼
                  INCIDENT VIEW
                        │
                 operator picks t0 + interventions
                        ▼
[Initializer] reconstructed state at t0 → agents in digital twin
                        ▼
[Simulator] social force (micro) + graph routing; macro flow for fast sweeps
                        ▼
[Same feature engine + same risk scorer on simulated output]
                        ▼
[Comparison] + [Validation replay] + [Prevention strategy]
```

Key design principle: **the simulator outputs the same `ZoneTimeseries` schema as the video pipeline**, so the same risk scorer, explainer, and charts work on both real and simulated data. This is what makes the side-by-side comparison fair.

---

## 5. Data contracts (implement in `backend/rewind/schemas/`, mirror in `frontend/src/types/`)

All times are **seconds from video start** (`float`). All world coordinates are **metres** in the venue frame. All IDs are strings.

### 5.1 Video
```python
class VideoMeta(BaseModel):
    video_id: str
    filename: str
    fps_native: float
    fps_processed: float          # from config, default 5.0
    width: int
    height: int
    duration_s: float
    frame_count: int
```

### 5.2 Venue (input JSON, see Section 11 for a full example)
```python
class Point(BaseModel): x: float; y: float

class Zone(BaseModel):
    zone_id: str                  # "A1", "B2", ...
    name: str
    polygon: list[Point]          # world metres
    kind: Literal["floor", "corridor", "entry", "exit", "gate_area"]

class Portal(BaseModel):          # a gate, door, or corridor connection between zones
    portal_id: str                # "GATE_A", "GATE_B", "GATE_C", "C_B1_B2"
    name: str
    from_zone: str
    to_zone: str
    segment: tuple[Point, Point]  # physical opening in world metres
    width_m: float
    is_open: bool = True
    bidirectional: bool = True
    kind: Literal["gate", "door", "corridor"]

class Wall(BaseModel):
    a: Point; b: Point

class CameraCalibration(BaseModel):
    image_points: list[Point]     # >= 4 pixel points
    world_points: list[Point]     # matching world points in metres

class Venue(BaseModel):
    venue_id: str
    name: str
    bounds: tuple[Point, Point]   # min, max
    zones: list[Zone]
    portals: list[Portal]
    walls: list[Wall]
    sources: list[str]            # zone_ids where people enter
    sinks: list[str]              # zone_ids where people leave
    calibration: CameraCalibration
```

### 5.3 Perception
```python
class Detection(BaseModel):
    t: float; bbox_xyxy: tuple[float, float, float, float]; conf: float

class TrackPoint(BaseModel):
    t: float
    px: tuple[float, float]       # foot point in pixels (bottom-centre of bbox)
    world: tuple[float, float]    # metres
    vel: tuple[float, float]      # m/s, smoothed
    zone_id: str | None

class Track(BaseModel):
    track_id: str
    points: list[TrackPoint]
```
Tracks are stored as Parquet (`tracks.parquet`: track_id, t, px_x, px_y, wx, wy, vx, vy, zone_id), not JSON.

### 5.4 Zone features (the central contract)
```python
class ZoneFeatures(BaseModel):
    t: float                      # window end time
    zone_id: str
    count: float                  # people in zone (fused estimate)
    density: float                # persons / m²
    mean_speed: float             # m/s
    speed_var: float              # (m/s)²
    velocity_var: float           # variance of velocity vectors, (m/s)² — used in crowd pressure
    dominant_dir: float           # radians
    direction_entropy: float      # 0..1 normalised
    counterflow_index: float      # 0..1
    flow_instability: float       # >= 0
    inflow_rate: float            # persons / s entering zone
    outflow_rate: float           # persons / s leaving zone
    bottleneck_pressure: float    # inflow / outgoing capacity, >= 0
    crowd_pressure: float         # density * velocity_var  (1/s²)
    source: Literal["tracks", "density", "fused", "sim"]

class ZoneTimeseries(BaseModel):
    run_id: str
    origin: Literal["video", "simulation"]
    window_s: float               # default 1.0
    zones: list[str]
    rows: list[ZoneFeatures]      # stored as features.parquet on disk
```

### 5.5 Risk
```python
RiskState = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]

class RiskPoint(BaseModel):
    t: float
    zone_id: str
    physics_score: float          # 0..1
    ml_score: float | None        # 0..1, probability of escalation
    ensemble_score: float         # 0..1
    state: RiskState              # after hysteresis

class GlobalRiskPoint(BaseModel):
    t: float
    max_score: float
    worst_zone: str
    state: RiskState
```

### 5.6 Explanation
```python
class Contribution(BaseModel):
    feature: str                  # "density", "bottleneck_pressure", ...
    label: str                    # human label, "Bottleneck pressure"
    value: float                  # raw feature value
    contribution: float           # signed contribution to the score
    share: float                  # 0..1 share of positive contributions

class Explanation(BaseModel):
    t: float
    zone_id: str
    score: float
    state: RiskState
    contributions: list[Contribution]   # sorted by contribution desc
    method: Literal["physics_weights", "shap"]
    narrative: str                # plain-language sentence(s)
```

### 5.7 Events and timeline
```python
EventType = Literal[
  "ENTRY_SURGE", "DENSITY_RISING", "DENSITY_THRESHOLD", "BOTTLENECK_FORMED",
  "COUNTERFLOW_EMERGED", "INSTABILITY_RISING", "RISK_STATE_CHANGE",
  "SPILLOVER", "PEAK_RISK", "DE_ESCALATION"
]

class IncidentEvent(BaseModel):
    event_id: str
    t_start: float
    t_end: float | None
    zone_id: str
    type: EventType
    severity: RiskState
    title: str                    # "Bottleneck detected at Gate B"
    detail: str
    evidence: dict[str, float]    # feature values that triggered it
    caused_by: list[str]          # upstream event_ids (causal chain)

class IncidentTimeline(BaseModel):
    run_id: str
    events: list[IncidentEvent]   # sorted by t_start
    origin_zone: str | None
    origin_time: float | None
    chain: list[str]              # ordered event_ids of the main causal chain
    summary: str
```

### 5.8 Simulation
```python
InterventionType = Literal["NONE", "OPEN_PORTAL", "CLOSE_PORTAL", "REDIRECT",
                           "RESTRICT_ENTRY", "WIDEN_PORTAL"]

class Intervention(BaseModel):
    type: InterventionType
    at_t: float                   # absolute video time when it takes effect (>= t0)
    portal_id: str | None = None  # OPEN/CLOSE/WIDEN
    from_zone: str | None = None  # REDIRECT
    to_zone: str | None = None    # REDIRECT target
    fraction: float | None = None # REDIRECT share of agents 0..1
    factor: float | None = None   # RESTRICT_ENTRY inflow multiplier, WIDEN width multiplier

class ScenarioSpec(BaseModel):
    scenario_id: str
    name: str                     # "Open Gate C at 12:35"
    interventions: list[Intervention]

class SimulationRequest(BaseModel):
    run_id: str                   # the analysed video run
    t0: float                     # rewind point
    horizon_s: float              # default 240
    scenarios: list[ScenarioSpec] # always auto-include baseline NONE
    seeds: list[int] = [0, 1, 2, 3, 4]
    model: Literal["social_force", "macro"] = "social_force"

class AgentFrame(BaseModel):     # for twin playback, downsampled to 10 Hz
    t: float
    xy: list[tuple[float, float]]
    local_density: list[float]

class ScenarioResult(BaseModel):
    scenario_id: str
    timeseries_path: str          # features.parquet of simulated run
    risk_path: str
    frames_path: str              # frames.npz (agent positions)
    metrics: "ScenarioMetrics"

class ScenarioMetrics(BaseModel):
    peak_density: float; peak_density_zone: str
    peak_crowd_pressure: float
    time_in_high_s: float; time_in_critical_s: float
    max_state: RiskState
    mean_evacuation_rate: float
    agents_remaining: int
    seed_std: dict[str, float]    # std across seeds for each metric
```

### 5.9 Validation
```python
class ValidationReport(BaseModel):
    run_id: str
    t0: float
    horizon_s: float
    per_zone_density_rmse: dict[str, float]
    per_zone_density_corr: dict[str, float]
    overall_density_rmse: float
    peak_time_error_s: float
    peak_density_error_pct: float
    state_agreement: float        # fraction of windows where risk states match
    calibrated_params: dict[str, float]
    verdict: Literal["GOOD", "FAIR", "POOR"]
```

### 5.10 Strategy
```python
class Recommendation(BaseModel):
    rank: int
    scenario_id: str
    headline: str                 # "Opening Gate C at 12:35 lowered modelled peak risk from CRITICAL to MEDIUM"
    deltas: dict[str, float]      # metric changes vs baseline
    confidence_note: str          # based on seed variance + validation verdict
    caveat: str                   # always present, see Section 13

class PreventionPlan(BaseModel):
    run_id: str
    recommendations: list[Recommendation]
    key_lessons: list[str]
```

Generate `docs/DATA_CONTRACTS.md` from these models with a small script, and generate the TypeScript types by hand in `frontend/src/types/` (keep field names identical, snake_case).

---

## 6. Configuration (`backend/config/default.yaml`)

```yaml
video:
  fps_processed: 5.0
  max_width: 1280
perception:
  yolo_model: "yolov8s.pt"
  yolo_conf: 0.25
  yolo_imgsz: 1280
  tracker: "bytetrack"          # or "deepsort"
  density_model_path: "data/models/csrnet.pth"
  density_fallback: "kde"       # used if weights missing
  hybrid_switch_density: 1.5    # p/m²: above this, trust density over detections
  hybrid_blend_band: 0.5        # linear blend width around switch point
  flow:
    method: "farneback"
    downscale: 0.5
features:
  window_s: 1.0
  direction_bins: 8
  counterflow_angle_deg: 120
  specific_flow_p_per_m_s: 1.3  # portal capacity per metre width (configurable literature default)
  smoothing_window: 5
risk:
  weights:                      # physics scorer weights, must sum to 1
    density: 0.25
    crowd_pressure: 0.25
    bottleneck_pressure: 0.20
    counterflow_index: 0.15
    flow_instability: 0.15
  norm:                         # value at which each feature saturates to 1.0
    density: 6.0
    crowd_pressure: 0.05
    bottleneck_pressure: 2.0
    counterflow_index: 0.6
    flow_instability: 1.0
  thresholds: {medium: 0.35, high: 0.55, critical: 0.75}
  hysteresis: 0.05
  min_dwell_s: 3.0
  ensemble: {physics: 0.5, temporal: 0.3, xgb: 0.2}
  escalation_horizon_s: 60
  density_levels: {caution: 2.0, high: 4.0, critical: 5.0}
  crowd_pressure_turbulence: 0.02
simulation:
  dt: 0.05
  record_hz: 10
  agent_radius_m: [0.22, 0.28]
  desired_speed: {mean: 1.34, std: 0.26}
  tau: 0.5
  A: 2000.0
  B: 0.08
  k_body: 120000.0
  kappa_friction: 240000.0
  mass: 80.0
  wall_A: 2000.0
  wall_B: 0.08
  reroute_every_s: 2.0
  congestion_weight: 1.5
  max_agents: 3000
validation:
  good_rmse: 0.5
  fair_rmse: 1.0
```
Note in `docs/DECISIONS.md` that the crowd-pressure turbulence threshold, specific flow, and social force parameters are literature-derived defaults that are calibrated per venue in Phase 10.

---

## 7. Backend module specifications

### 7.1 Ingest (`ingest/video_reader.py`)
- Open with OpenCV, read metadata into `VideoMeta`.
- Yield `(t, frame_bgr)` at `fps_processed` by skipping frames (use timestamps, not frame index math, to handle variable frame rate).
- Resize so width ≤ `max_width`, keeping aspect ratio; store the scale factor so pixel coordinates can be mapped back.

### 7.2 Calibration (`calibration/homography.py`)
- `fit_homography(image_points, world_points) -> H` with `cv2.findHomography(..., RANSAC)`. Require ≥ 4 points; raise a clear error otherwise.
- `pixel_to_world(pts, H)` and `world_to_pixel(pts, H_inv)` vectorised.
- `zone_masks(venue, H_inv, frame_shape) -> dict[zone_id, np.ndarray[bool]]`: project each zone polygon into the image and rasterise with `cv2.fillPoly`. Cache per run.
- `pixel_area_m2(H, frame_shape)`: per-pixel ground area map (for converting density maps to persons/m²), computed from the Jacobian of the homography at each pixel (or by projecting pixel corners on a coarse grid and interpolating).
- Unit tests: round-trip pixel→world→pixel error < 0.5 px; known square maps to known area.

### 7.3 Detection (`perception/detector.py`)
- Wrap Ultralytics YOLOv8, class 0 (person) only, `imgsz` and `conf` from config.
- Return `list[Detection]` per frame. Batch frames when GPU is available.

### 7.4 Tracking (`perception/tracker.py`, `perception/trajectories.py`)
- Interface `class Tracker(Protocol): def update(detections, frame) -> list[tuple[track_id, bbox]]`.
- `ByteTrackTracker` using `supervision.ByteTrack`. `DeepSortTracker` stub that satisfies the protocol (can wrap `deep-sort-realtime` if installed; otherwise raise a clear NotImplementedError and fall back to ByteTrack — record this in DECISIONS.md).
- Foot point = bottom-centre of bbox → world via homography → assign zone with `shapely` point-in-polygon (use prepared geometries).
- Smooth each trajectory with Savitzky–Golay (window 5, order 2) when length ≥ 5; velocity = finite difference of smoothed world positions.
- Drop tracks shorter than 1 s; clip implausible speeds > 4 m/s.

### 7.5 Density (`perception/density/`)
- `csrnet.py`: implement CSRNet (VGG-16 front end, first 10 conv layers; dilated back end 512-512-512-256-128-64 with dilation 2; 1×1 output conv). Load weights from `density_model_path`. Output density map; upsample to frame size and rescale so the sum is preserved.
- If weights are missing, log a warning and use `fallback_kde.py`: place a Gaussian (σ scaled by local bbox height) at each detection's head point to build a density map. Record in the run metadata which method was used, and show it in the UI.
- Write `data/models/README.md` explaining how to obtain CSRNet weights trained on ShanghaiTech (Part A for dense, Part B for sparse) and where to put them.
- Per zone: `count = sum(density_map * zone_mask)`, `density = count / zone_area_m2`.

### 7.6 Optical flow (`perception/optical_flow.py`)
- Farneback dense flow on grayscale frames downscaled by `flow.downscale`, between consecutive processed frames.
- Convert pixel displacement to world velocity: for a grid of sample points (every 8 px) inside each zone mask, project start and end points through the homography and divide by Δt.
- Only use sample points where density > small threshold (ignore empty floor).
- Output per zone per frame: array of world velocity vectors (used by the feature engine).

### 7.7 Fusion (`perception/fusion.py`)
- Per zone per window, compute detection-based density `ρ_det` and density-map-based `ρ_map`.
- Blend weight `w = clip((ρ_map - (switch - band/2)) / band, 0, 1)`; fused count = `(1-w)*count_det + w*count_map`.
- Velocity source: tracks when `w < 0.5` and ≥ 3 tracks in the zone, else optical flow vectors. Set `source` in `ZoneFeatures` accordingly.
- This hybrid is a feature to highlight in the pitch: **tracking where the crowd is sparse, density and flow where it is packed.**

### 7.8 Crowd feature engine (`features/crowd_metrics.py`, `features/zone_features.py`)
Implement each metric as a pure, unit-tested function. Given the velocity vectors `v_i` in a zone during a window:

| Feature | Definition |
|---|---|
| `mean_speed` | mean of ‖v_i‖ |
| `speed_var` | variance of ‖v_i‖ |
| `velocity_var` | mean of ‖v_i − v̄‖² (variance of the velocity vector field) |
| `dominant_dir` | angle of the mean unit vector (circular mean) |
| `direction_entropy` | Shannon entropy of an 8-bin histogram of directions (weighted by speed, ignore ‖v‖ < 0.1), divided by log(8) |
| `counterflow_index` | share of vectors whose angle differs from `dominant_dir` by more than 120° |
| `flow_instability` | ‖v̄_t − v̄_{t−1}‖ / Δt averaged with the change in direction entropy; also add mean absolute curl of the flow field when optical flow is the source |
| `inflow_rate` / `outflow_rate` | tracks: count crossings of portal segments by direction; density mode: use continuity, Δcount/Δt split by flow direction across the shared portal segment (flux = ρ · v·n · width) |
| `bottleneck_pressure` | inflow_rate / Σ capacity of the zone's open outgoing portals, where capacity = width_m × specific_flow |
| `crowd_pressure` | density × velocity_var (Helbing et al. 2007 "crowd pressure") |

- Apply rolling mean smoothing (`smoothing_window`) to each feature per zone.
- Output: `features.parquet` + `ZoneTimeseries` metadata JSON.
- Unit tests with synthetic vector fields: uniform flow → entropy ≈ 0, counterflow 0; two opposing streams 50/50 → counterflow ≈ 0.5; random directions → entropy ≈ 1.

### 7.9 Risk scoring (`risk/`)

**Physics scorer (`physics_scorer.py`)** — always available, fully explainable:
- Normalise each feature: `n_f = clip(value / norm_f, 0, 1)`.
- `physics_score = Σ weight_f × n_f`.
- Contribution of feature f = `weight_f × n_f` (exact, no approximation).

**State machine (`states.py`)**:
- Map score to state using thresholds; apply hysteresis (a state is only lowered when the score drops below threshold − hysteresis) and a minimum dwell time before changing state. This prevents flicker in the UI.
- Override rules: density ≥ `density_levels.critical` or crowd_pressure ≥ `crowd_pressure_turbulence` forces at least HIGH.

**Temporal model (`temporal_model.py`)**:
- Input: sliding window of the last 30 windows (30 s) of the 12 numeric features for one zone, plus the same features aggregated over its graph neighbours (mean), giving 24 channels.
- Two architectures behind one interface: `TCNClassifier` (4 dilated causal conv blocks, dilations 1-2-4-8, 64 channels, dropout 0.2) and `LSTMClassifier` (2 layers, hidden 64). Config selects the active one; train both and report both.
- Target: `will_escalate` = 1 if the zone's physics state reaches HIGH or CRITICAL within the next `escalation_horizon_s` seconds (label computed from ground-truth simulator output, see 7.15).
- Loss: focal loss (γ = 2) or class-weighted BCE to handle imbalance.
- Output `ml_score` = predicted probability.

**XGBoost model (`xgb_model.py`)**:
- Input: hand-crafted window aggregates (last value, mean, max, slope via linear fit over last 10 s) for each feature and its neighbour mean.
- Same target. `scale_pos_weight` for imbalance. Explained with SHAP TreeExplainer.

**Ensemble (`ensemble.py`)**:
- `ensemble_score = w_p × physics + w_t × temporal + w_x × xgb` (weights from config; if a model is missing, renormalise the remaining weights).
- Also produce `GlobalRiskPoint` per window (worst zone).

### 7.10 Explainability (`explain/`)
- `contributions.py`: for each (t, zone), build `Contribution` list from physics weights; when requested and XGBoost exists, also compute SHAP values and return an `Explanation` with `method="shap"`. The UI can toggle between the two.
- `narrator.py`: template-based sentences, no LLM required. Rules:
  - Name the top 2 contributors and their trend over the previous 30 s ("rising", "stable", "falling").
  - Mention the zone name and nearest portal.
  - Example: *"Risk in Zone B2 (near Gate B) rose to HIGH mainly because density climbed from 2.8 to 4.6 people/m² while opposing movement increased (counterflow 0.41). Bottleneck pressure at Gate B is 1.7× its estimated capacity."*
  - Always use hedged verbs from Section 13.

### 7.11 Incident reconstruction (`reconstruction/`)
**Event detector (`event_detector.py`)**, per zone, on smoothed features:
| Event | Trigger |
|---|---|
| `ENTRY_SURGE` | source zone inflow_rate > mean + 2σ of the first 60 s for ≥ 5 s |
| `DENSITY_RISING` | density slope over 20 s > 0.05 p/m²/s |
| `DENSITY_THRESHOLD` | density crosses caution / high / critical levels (one event per level) |
| `BOTTLENECK_FORMED` | bottleneck_pressure > 1.0 for ≥ 5 s |
| `COUNTERFLOW_EMERGED` | counterflow_index > 0.25 for ≥ 5 s |
| `INSTABILITY_RISING` | flow_instability slope positive and value > 0.5 × norm for ≥ 5 s |
| `RISK_STATE_CHANGE` | every state change from the state machine |
| `SPILLOVER` | a neighbour zone of an already HIGH zone becomes HIGH within 30 s |
| `PEAK_RISK` | global maximum of ensemble_score |
| `DE_ESCALATION` | state drops from HIGH/CRITICAL to MEDIUM or below |
- Merge consecutive duplicate events; keep `t_start`, `t_end`, and `evidence`.

**Causal chain (`causal_chain.py`)**:
- Build a directed event graph: event e1 → e2 if e1 happens before e2, and (same zone, or e1's zone is upstream of e2's zone in the venue graph), and Δt ≤ 90 s, and e1's type is a plausible cause of e2's type (define an allowed cause-type matrix, e.g. ENTRY_SURGE → DENSITY_RISING → BOTTLENECK_FORMED → COUNTERFLOW_EMERGED / INSTABILITY_RISING → RISK_STATE_CHANGE).
- Weight edges by temporal proximity and evidence strength.
- Main chain = highest-weight path ending at `PEAK_RISK`. Origin = first event on that chain → `origin_zone`, `origin_time`.
- Fill each event's `caused_by`.

**Timeline (`timeline.py`)**: assemble `IncidentTimeline` with a 2–3 sentence `summary` built by the narrator.

### 7.12 Venue graph (`venue/graph.py`, `venue/geometry.py`)
- `networkx.DiGraph`: nodes = zones (attributes: area_m2, centroid, polygon, kind); edges = open portals (attributes: portal_id, width_m, capacity = width × specific_flow, length = centroid distance, is_open). Bidirectional portals create two edges.
- Functions: `apply_interventions(graph, interventions, t)`, `upstream(zone)`, `downstream(zone)`, `neighbours(zone)`, `route(zone_from, sinks, weights)`.
- `geometry.py`: wall segments list for the simulator, point-in-zone lookup, random point sampling inside a polygon with minimum spacing (Poisson-disk style).
- Validate venue on load: every zone reachable from a source, every source can reach a sink when all portals are open, portal segments lie on zone boundaries (tolerance 0.2 m). Return readable errors.

### 7.13 Simulation (`simulation/`)
**Social force model (`social_force.py`)**, Helbing & Molnár / Helbing, Farkas & Vicsek formulation. For each agent i:
- Driving force: `m (v0_i e_i − v_i) / τ`, where `e_i` points to the next waypoint (centre of the next portal segment on its route, or the nearest point of that segment).
- Agent–agent force: `A exp((r_ij − d_ij)/B) n_ij + k g(r_ij − d_ij) n_ij + κ g(r_ij − d_ij) Δv_ji t_ij` with `g(x) = max(x, 0)`.
- Wall force: same form with wall parameters, using the closest point on each nearby wall segment. Closed portals are treated as walls.
- Integrate with semi-implicit Euler at `dt`; cap speed at 1.3 × v0.
- Neighbour search with a uniform spatial hash (`spatial_hash.py`, cell size 1 m, only 3×3 neighbouring cells). Vectorise with NumPy; optionally JIT with Numba.
- Local density per agent = neighbours within 1 m radius / (π × 1²) — used for twin colouring.

**Routing (`routing.py`)**:
- Each agent has a target sink. Route = shortest path on the venue graph with edge weight `length × (1 + congestion_weight × (density_of_target_zone / density_levels.high))`.
- Recompute routes every `reroute_every_s` with probability 0.3 per agent (people don't all react at once).

**Macro flow model (`macro_flow.py`)** — fast, for generating thousands of training scenarios:
- Zone-level mass balance per step: flow across each open portal = `min(demand_upstream, supply_downstream, capacity)`, with speed–density relation `v(ρ) = v_free × (1 − ρ/ρ_jam)`, ρ_jam = 5.4 p/m².
- Produces `ZoneTimeseries` directly. Velocity variance and counterflow come from simple stochastic terms tied to density and opposing flows through shared portals (document the approximations).

**Initializer (`initializer.py`)** — turns the reconstructed state at `t0` into agents:
- For each zone: n = round(fused count at t0); sample positions with minimum spacing; initial velocity = zone mean flow vector + Gaussian noise (σ = sqrt(velocity_var)).
- Assign target sinks by matching each agent's velocity direction to the downstream path it best fits; ties → nearest open sink.
- Boundary condition for t > t0: inflow at each source = observed inflow_rate extrapolated (use the mean of the 30 s before t0, or the actual observed series when replaying for validation).

**Interventions (`interventions.py`)**:
| Type | Effect |
|---|---|
| NONE | baseline |
| OPEN_PORTAL | portal becomes passable (removed from walls, edge added) at `at_t`; routes recompute immediately for agents within 30 m |
| CLOSE_PORTAL | reverse of open |
| REDIRECT | `fraction` of agents in `from_zone` get new target via `to_zone` |
| RESTRICT_ENTRY | source inflow × `factor` |
| WIDEN_PORTAL | portal width × `factor` (segment extended symmetrically if geometry allows; capacity updated) |

**Runner (`runner.py`)**:
- For each scenario × seed: run from t0 to t0 + horizon; record agent positions at `record_hz` (`recorder.py` → `frames.npz` with float16 positions) and compute zone features every `window_s` by the **same feature engine** (source = "sim").
- Score with the same risk pipeline → metrics per seed → aggregate mean and std into `ScenarioMetrics`.
- Run scenarios in a `ProcessPoolExecutor`; stream progress over WebSocket.
- Always include the baseline `NONE` scenario automatically.
- Sanity checks (unit tests): agent count is conserved (except sources/sinks); agents never pass through walls or closed portals; with no people nothing happens; opening an extra exit never increases evacuation time in a simple two-room test.

### 7.14 Validation (`validation/`)
**Replay (`replay.py`)**: run the baseline from a chosen t0 using the *observed* source inflows; compare simulated vs observed per-zone density series over the horizon: RMSE, Pearson correlation, peak time error, peak density error %, and risk-state agreement. Verdict from config thresholds.

**Calibrate (`calibrate.py`)**: on the first 50% of the video (never the part used for validation), grid-search or use `scipy.optimize` (Nelder–Mead) over `desired_speed.mean`, `tau`, `A`, `B` to minimise density RMSE with the macro model first, then refine with 2–3 social-force runs. Save calibrated params per run. Report the split clearly in the UI to show there is no leakage.

### 7.15 Training data and training (`training/`)
**Synthetic dataset (`synth_dataset.py`)**:
- Generate ≥ 2,000 scenarios with the macro model (and ≥ 100 with social force for a realism check) on procedurally varied venues: 2–4 gates, random gate widths 1.5–6 m, random inflow profiles (steady, ramp, surge), random counterflow injections, random gate closures mid-run.
- Record features, compute ground-truth states with the physics scorer, create `will_escalate` labels with the horizon.
- Split by **scenario**, not by window (train 70 / val 15 / test 15), to avoid leakage.

**Training scripts**: `train_temporal.py` (both TCN and LSTM, early stopping on val PR-AUC), `train_xgb.py`. Save to `data/models/` with a JSON model card (data, metrics, date, config hash).

**Evaluation (`evaluate.py`)**: report PR-AUC, ROC-AUC, recall and precision at the HIGH threshold, **mean lead time** (seconds between first positive prediction and the actual escalation), and a confusion matrix — on the synthetic test set and on any labelled real clips. Save plots to `docs/eval/`. These numbers go on a pitch slide.

### 7.16 Prevention strategy (`strategy/prevention.py`)
- Rank non-baseline scenarios by: lowest max_state, then lowest time_in_critical, then lowest peak crowd pressure, then smallest intervention (fewer changes preferred).
- For each, compute deltas vs baseline and write a headline with the narrator.
- `confidence_note`: combine seed std (low/medium/high variability) with the validation verdict.
- `key_lessons`: derived from the causal chain (e.g. "Gate B capacity was exceeded ~3 minutes before the peak; interventions after 12:37 had little modelled effect").

### 7.17 Pipeline orchestration (`pipeline/`)
- `analyze.py`: ingest → calibration → detection + tracking → density → flow → fusion → features → risk → explanations → events → timeline. Each stage writes its artefact to `data/runs/{run_id}/` and is **skipped if the artefact already exists** (cache), unless `force=true`.
- `jobs.py`: in-process async job manager (`asyncio` + thread/process pool) with states `QUEUED, RUNNING, DONE, FAILED`, stage name, percent, ETA, and error message. Progress events are pushed to `/ws/jobs/{job_id}`.

### 7.18 Storage (`storage/run_store.py`)
```
data/runs/{run_id}/
  meta.json            # VideoMeta, venue_id, methods used, config hash, timings
  tracks.parquet
  density_zone.parquet
  flow_zone.parquet
  features.parquet
  risk.parquet
  global_risk.parquet
  explanations.parquet
  timeline.json
  overlays/            # optional pre-rendered heatmap PNG frames for fast playback
  simulations/{sim_id}/
     request.json
     {scenario_id}/seed_{n}/features.parquet, risk.parquet, frames.npz
     results.json
     comparison.json
     plan.json
  validation.json
```

---

## 8. API specification (`backend/rewind/api/`)

All routes are under `/api`. Return pydantic models; errors return `{"error": {"code", "message", "detail"}}` with correct HTTP status.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | status, versions, GPU available, which models are loaded |
| POST | `/api/videos` | multipart upload → `VideoMeta` |
| GET | `/api/videos/{video_id}/stream` | video file with HTTP range support for the player |
| GET | `/api/venues` | list venues |
| GET/PUT | `/api/venues/{venue_id}` | get / save venue JSON (validated) |
| POST | `/api/runs` | body `{video_id, venue_id, force?}` → starts analysis job → `{run_id, job_id}` |
| GET | `/api/runs/{run_id}` | run meta + status |
| GET | `/api/runs/{run_id}/features?zone=&t_from=&t_to=` | ZoneFeatures rows |
| GET | `/api/runs/{run_id}/risk` | per-zone RiskPoints + global risk |
| GET | `/api/runs/{run_id}/explanations?t=&zone=&method=` | Explanation for a moment |
| GET | `/api/runs/{run_id}/timeline` | IncidentTimeline |
| GET | `/api/runs/{run_id}/overlay?t=` | tracks + zone densities + flow arrows for one timestamp (for the video overlay) |
| POST | `/api/simulations` | `SimulationRequest` → `{sim_id, job_id}` |
| GET | `/api/simulations/{sim_id}` | status + `ScenarioResult` list |
| GET | `/api/simulations/{sim_id}/frames/{scenario_id}?seed=0&t_from=&t_to=` | agent frames (binary: little-endian float16 array + small JSON header) for the twin |
| GET | `/api/simulations/{sim_id}/comparison` | table data for all scenarios |
| GET | `/api/simulations/{sim_id}/plan` | PreventionPlan |
| POST | `/api/runs/{run_id}/validate` | body `{t0, horizon_s}` → job → ValidationReport |
| GET | `/api/runs/{run_id}/validation` | latest ValidationReport |
| POST | `/api/demo/load` | loads the pre-computed demo run from cache instantly |
| WS | `/ws/jobs/{job_id}` | progress events `{stage, percent, message, eta_s}` then `{done: true}` or `{error}` |

CORS allowed for the Vite dev origin. Add OpenAPI tags and examples for every route.

---

## 9. Frontend specification

### 9.1 Visual design
- Dark "control room" theme: background `#0B0F14`, panels `#121821`, borders `#1F2A37`, text `#E6EDF3`, muted `#8B98A5`.
- Risk colours (use everywhere consistently): LOW `#22C55E`, MEDIUM `#EAB308`, HIGH `#F97316`, CRITICAL `#EF4444`. Heatmaps use a perceptual scale (viridis-like) for density and the risk colours for state.
- Font: Inter for UI, JetBrains Mono for numbers and timestamps.
- Layout: top bar (logo "REWIND", run name, global risk badge, demo button), three main routes.
- Everything must be readable on a projector: minimum 14 px text, strong contrast, big timestamps.
- Smooth, meaningful motion only (heatmap transitions, scrubber). No gratuitous animations.

### 9.2 Pages
**UploadPage**
- Drag-and-drop video upload with progress; venue selector (with a preview of the floor plan); "Analyse" button.
- Calibration helper: show the first frame, let the user click 4+ points on the image and enter/select matching points on the floor plan; save into the venue's `calibration`.
- After starting, show a stage-by-stage progress list driven by the WebSocket (Detecting people → Tracking → Density → Motion → Features → Risk → Reconstruction).
- "Load demo" button that calls `/api/demo/load`.

**AnalysisPage** ("This is what happened")
- Left (60%): video player with a synchronised overlay canvas. Toggles: bounding boxes + track tails, density heatmap, zone grid with risk colours, flow arrows. A small badge shows "sparse mode: tracking" or "dense mode: density + flow" per zone.
- Right (40%): zone heatmap grid (A1…C3) coloured by current state with density numbers; explanation panel (contribution bar chart + narrative; toggle physics vs SHAP).
- Bottom: risk timeline chart (global ensemble score line with coloured state bands; per-zone lines on hover), event markers on the chart, and the event list. Clicking an event seeks the video and highlights the zone. A causal-chain strip shows the main chain as connected chips from origin to peak.
- The whole page shares one `currentTime` in a Zustand store; video, chart, grid, and explanations all follow it.

**RewindPage** ("Simulate the alternative")
- Big **REWIND** button: animates the scrubber backwards to the chosen t0 (default: 2 minutes before the first HIGH state, editable).
- Intervention builder: add any number of scenarios; each scenario is a list of interventions picked from dropdowns populated from the venue (gates, zones) with time pickers ≥ t0 and sliders for fraction/factor. Presets: "Open Gate C", "Redirect from Zone B", "Restrict entry 50%", "Widen exit ×1.5".
- "Run simulation" → progress via WebSocket.
- **Digital twin view**: side-by-side canvases, left = baseline ("what happened", replayed), right = selected scenario. Floor plan drawn from venue geometry (walls, zones, portals; open gates green, closed grey, changed gates pulse). Agents are dots coloured by local density; optional density heatmap layer. Synchronised play/pause, speed 1×/2×/4×, and a shared timeline. A mini risk chart under each canvas.
- Comparison table: Scenario | Peak density | Peak crowd pressure | Time in HIGH | Time in CRITICAL | Max state | Variation across seeds. Best row highlighted.
- Validation card: "Do-nothing replay vs real footage" — overlaid density lines (observed vs simulated) for the worst zone, RMSE, correlation, verdict badge, and a note on the calibration/validation split.
- Prevention plan card: ranked recommendations with headline, deltas, confidence note, caveat.
- Persistent footer disclaimer (Section 13).

### 9.3 Frontend engineering
- `src/api/client.ts`: typed fetch wrapper; `useJobProgress(jobId)` WebSocket hook with reconnect.
- TanStack Query for all GETs; cache per run.
- Canvas renderers are plain TypeScript classes (`TwinRenderer`, `OverlayRenderer`) with `draw(state)` methods, decoupled from React; React only passes props. Target 60 fps for 3,000 agents (draw with a single path per colour bucket).
- Decode binary frame payloads with `DataView` into `Float32Array` (convert from float16).
- Vitest tests: store time sync, frame decoding, colour mapping, intervention builder validation.

---

## 10. Explainability & honesty features visible in the UI
- Every risk number shows its method (physics / ML / ensemble) on hover.
- Explanations always list the top contributing features with values.
- Simulation results always show the spread across seeds.
- The validation verdict is displayed next to every scenario result.
- The density method used (CSRNet or fallback) and tracker are shown in the run info panel.

---

## 11. Demo venue (`data/venues/demo_venue.json`)

Create a realistic demo venue: a 30 m × 20 m plaza divided into a 3×3 grid of zones (A1…C3), with:
- **GATE_A** (entry, 4 m wide) on the north side of A2 — the source.
- **GATE_B** (main exit, 3 m wide) on the south side of C2 — the sink that gets overloaded.
- **GATE_C** (side exit, 3.5 m wide) on the east side of C3 — **closed** at the start; the intervention opens it.
- Internal portals between all adjacent zones (full-width openings), plus a partial wall between B1 and C1 to create a natural bottleneck.
- Calibration points that match the demo video's camera view (placeholder values plus a note to recalibrate using the UploadPage helper).

Also create `data/venues/README.md` explaining the venue format with this example.

---

## 12. Demo mode and assets
- `make demo` runs the full analysis on the demo video and a default simulation (Baseline, Open Gate C, Redirect from B2, Restrict entry 50%, Widen Gate B ×1.5), then validation, and stores everything under `data/runs/demo/`.
- `POST /api/demo/load` loads that run instantly so the live presentation never waits on processing.
- `docs/DEMO_SCRIPT.md` contains the 3-minute script:
  - 0:00 upload / load demo — "This is what happened."
  - 0:20 heatmap escalates — "Zone B2 shows escalating risk."
  - 0:50 timeline — "At 12:36 the first bottleneck appeared at Gate B."
  - 1:10 explanation — "Density rose while opposing movement developed."
  - 1:30 press REWIND — "What if Gate C had been opened two minutes earlier?"
  - 1:45 twin side-by-side — crowd redistributes, risk falls.
  - 2:15 second scenario — restrict entry; comparison table.
  - 2:30 validation card — "Our do-nothing replay matched the real footage with X RMSE."
  - 2:40 closing — "REWIND doesn't just explain incidents. It lets us explore how they could have unfolded differently."
- Data sources: document in README where to get test footage (public crowd-counting and crowd-behaviour datasets such as ShanghaiTech for density weights, plus any public crowd videos you are licensed to use). The agent must not download or bundle anything with unclear licensing; leave clear placeholders and instructions instead.
- Also provide `scripts/render_synthetic_video.py`: renders a social-force simulation of the demo venue as a top-down video (people as blobs) so the whole pipeline can be tested end to end even without real footage. Label it clearly as synthetic in the UI.

---

## 13. Positioning, language, and ethics rules (apply to UI copy, docs, and narrator)
- Never say "predicts stampedes", "prevents disasters", or "would have saved". Say:
  - "identifies escalating risk patterns in crowd dynamics"
  - "the simulation estimates how the intervention could have changed the **modelled** crowd dynamics"
- Every recommendation carries the caveat: *"Simulation output under modelled assumptions. Not a guarantee of real-world outcomes. Intended to support, not replace, trained crowd-safety professionals."*
- Footer disclaimer on RewindPage with the same meaning.
- **Privacy by design:** no face recognition, no identity, no re-identification across videos. Track IDs are anonymous and per run. Add an optional "blur faces/heads in exported frames" setting (Gaussian blur on the top 25% of each bbox). Mention this in the README and pitch.
- If a real incident video with casualties is used, the UI shows a respectful note on the run page; prefer synthetic or non-tragic footage for the demo.

---

## 14. Build phases with acceptance checks

| Phase | Build | Acceptance checks |
|---|---|---|
| 0. Scaffold | Repo tree, pyproject, package.json, Makefile, Docker, config loader, logging, health route, empty React shell with routing and theme | `make setup`, `make dev` start both apps; `/api/health` OK; `docker compose up` works; lint + type check pass |
| 1. Contracts | All pydantic schemas, TS types, DATA_CONTRACTS.md generator, fixture factories producing fake data for every schema | Schema round-trip tests pass; frontend renders fake timeline/risk/twin data from fixtures |
| 2. Ingest + calibration + venue | Video reader, homography, zone masks, venue loader + validator + graph, demo venue JSON | Unit tests for homography round trip, area, venue validation errors, graph routing |
| 3. Perception | YOLO, ByteTrack (+DeepSORT interface), trajectories, CSRNet + KDE fallback, optical flow, fusion | Runs on a 30 s clip; outputs tracks/density/flow Parquet; overlay endpoint returns data; fallback works with no weights |
| 4. Features | All crowd metrics + zone feature engine | Synthetic vector-field tests pass; features.parquet produced for the clip |
| 5. Physics risk + states + explanations | Physics scorer, hysteresis, contributions, narrator | Monotonicity tests (more density → higher score); no state flicker on noisy input; narratives generated |
| 6. Reconstruction | Event detector, causal chain, timeline | Synthetic escalation series produces the expected ordered chain and origin zone |
| 7. API + jobs + analysis UI | Full analysis pipeline, job manager, WebSocket progress, AnalysisPage complete | Upload → analyse → scrub video with synced overlay, chart, grid, events, explanations |
| 8. Simulation | Social force, spatial hash, routing, macro model, initializer, interventions, runner, recorder | Conservation, wall, and two-room sanity tests pass; 1,000 agents × 240 s runs in < 60 s on CPU (macro < 2 s) |
| 9. Rewind UI | Intervention builder, twin renderer side-by-side, comparison table, prevention plan | Run 5 scenarios from t0 and play them back at 60 fps; table and plan populated |
| 10. Validation + calibration | Replay, calibrate, validation card | Report generated with non-overlapping calibration/validation windows |
| 11. ML | Synthetic dataset, TCN + LSTM + XGBoost training, evaluation, ensemble wired in, SHAP toggle | Models saved with model cards; eval report with PR-AUC and lead time; ensemble scores shown in UI |
| 12. Demo + polish | Synthetic video renderer, demo mode, demo script, README, ARCHITECTURE.md with Mermaid diagrams, final UI polish, performance pass | `make demo` succeeds from clean clone; `/api/demo/load` is instant; full test suite green |

After each phase, print a short report: what was built, test results, known issues, and the next phase.

---

## 15. Testing strategy
- **Unit:** every function in `crowd_metrics.py`, homography, venue validation, state machine, event triggers, causal chain, social force forces (two agents repel, wall repels), spatial hash correctness vs brute force, interventions, strategy ranking.
- **Property tests** (optional, `hypothesis`): feature ranges (entropy and counterflow within 0..1), scorer bounded 0..1.
- **Integration:** 10 s synthetic video → full analysis → timeline non-empty; simulation request → results + plan; API contract tests with `httpx.AsyncClient`.
- **Frontend:** store sync, binary decoding, builder validation, snapshot of comparison table.
- `make test` runs everything; CI-ready GitHub Actions workflow in `.github/workflows/ci.yml` (lint, type check, tests; skip GPU tests).

---

## 16. Performance targets
- Analysis of a 3-minute 1080p video at 5 fps processed: ≤ 5 min on a laptop GPU, ≤ 15 min on CPU (document actual timings in meta.json).
- Overlay endpoint responds in < 100 ms (pre-computed per timestamp).
- Twin playback at 60 fps with 3,000 agents.
- Simulation of 5 scenarios × 5 seeds with social force: ≤ 3 min for 1,000 agents; macro model mode for instant previews.

---

## 17. README contents
1. One-line pitch + screenshot/GIF placeholders.
2. The problem and what REWIND does (the four questions: where did it begin, what made it escalate, what could have been done differently, would redistributing the crowd have helped).
3. Architecture diagram (Mermaid) and pipeline explanation.
4. Tech stack.
5. Quick start (Docker and local), `make demo`.
6. How to add a venue and calibrate a camera.
7. Model details: hybrid perception, crowd metrics with formulas, risk ensemble, training on simulated data, evaluation results.
8. Simulation details and validation results.
9. Limitations and honest positioning (Section 13).
10. Privacy and ethics.
11. Team and acknowledgements (cite Helbing et al. for the social force model and crowd pressure, Li et al. for CSRNet, Zhang et al. for ByteTrack, Ultralytics for YOLOv8).

---

## 18. Definition of done
- Every component in this document exists, is wired end to end, and is covered by tests.
- A new team member can clone the repo, run `make setup && make demo && make dev`, open the app, press "Load demo", and walk through the full 3-minute script without errors.
- The UI never displays a claim that violates Section 13.
- `docs/PLAN.md` and `docs/DECISIONS.md` reflect what was actually built.

**Start now with Phase 0. Before writing code, write `docs/PLAN.md` and show it.**
