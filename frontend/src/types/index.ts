// Mirrors backend/rewind/schemas exactly (snake_case field names). See docs/DATA_CONTRACTS.md.

// ---- 5.1 Video ---------------------------------------------------------------------------
export interface VideoMeta {
  video_id: string;
  filename: string;
  fps_native: number;
  fps_processed: number;
  width: number;
  height: number;
  duration_s: number;
  frame_count: number;
  synthetic: boolean;
}

// ---- 5.2 Venue ---------------------------------------------------------------------------
export type ZoneKind = "floor" | "corridor" | "entry" | "exit" | "gate_area";
export type PortalKind = "gate" | "door" | "corridor";

export interface Point {
  x: number;
  y: number;
}
export interface Zone {
  zone_id: string;
  name: string;
  polygon: Point[];
  kind: ZoneKind;
}
export interface Portal {
  portal_id: string;
  name: string;
  from_zone: string;
  to_zone: string;
  segment: [Point, Point];
  width_m: number;
  is_open: boolean;
  bidirectional: boolean;
  kind: PortalKind;
}
export interface Wall {
  a: Point;
  b: Point;
}
export interface CameraCalibration {
  image_points: Point[];
  world_points: Point[];
}
export interface Venue {
  venue_id: string;
  name: string;
  bounds: [Point, Point];
  zones: Zone[];
  portals: Portal[];
  walls: Wall[];
  sources: string[];
  sinks: string[];
  calibration: CameraCalibration;
}

// ---- 5.3 Perception ------------------------------------------------------------------------
export type Vec2 = [number, number];
export interface Detection {
  t: number;
  bbox_xyxy: [number, number, number, number];
  conf: number;
}
export interface TrackPoint {
  t: number;
  px: Vec2;
  world: Vec2;
  vel: Vec2;
  zone_id: string | null;
}
export interface Track {
  track_id: string;
  points: TrackPoint[];
}
export interface OverlayTrack {
  track_id: string;
  bbox_xyxy: [number, number, number, number] | null;
  tail: Vec2[];
}
export interface OverlayZone {
  zone_id: string;
  polygon_px: Vec2[];
  density: number;
  count: number;
  state: string;
  mode: string;
}
export interface OverlayArrow {
  x: number;
  y: number;
  dx: number;
  dy: number;
}
export interface OverlayFrame {
  t: number;
  frame_width: number;
  frame_height: number;
  tracks: OverlayTrack[];
  zones: OverlayZone[];
  arrows: OverlayArrow[];
  heatmap: number[][] | null;
}

// ---- 5.4 Zone features ----------------------------------------------------------------------
export type FeatureSource = "tracks" | "density" | "fused" | "sim";
export interface ZoneFeatures {
  t: number;
  zone_id: string;
  count: number;
  density: number;
  mean_speed: number;
  speed_var: number;
  velocity_var: number;
  dominant_dir: number;
  direction_entropy: number;
  counterflow_index: number;
  flow_instability: number;
  inflow_rate: number;
  outflow_rate: number;
  bottleneck_pressure: number;
  crowd_pressure: number;
  source: FeatureSource;
}
export interface ZoneTimeseries {
  run_id: string;
  origin: "video" | "simulation";
  window_s: number;
  zones: string[];
  rows: ZoneFeatures[];
}

// ---- 5.5 Risk ----------------------------------------------------------------------------
export type RiskState = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
export const RISK_STATES: RiskState[] = ["LOW", "MEDIUM", "HIGH", "CRITICAL"];
export interface RiskPoint {
  t: number;
  zone_id: string;
  physics_score: number;
  ml_score: number | null;
  ensemble_score: number;
  state: RiskState;
}
export interface GlobalRiskPoint {
  t: number;
  max_score: number;
  worst_zone: string;
  state: RiskState;
}
export interface RiskSeries {
  run_id: string;
  zones: RiskPoint[];
  global_risk: GlobalRiskPoint[];
  methods: Record<string, boolean>;
}

// ---- 5.6 Explanation ---------------------------------------------------------------------
export interface Contribution {
  feature: string;
  label: string;
  value: number;
  contribution: number;
  share: number;
}
export type ExplanationMethod = "physics_weights" | "shap";
export interface Explanation {
  t: number;
  zone_id: string;
  score: number;
  state: RiskState;
  contributions: Contribution[];
  method: ExplanationMethod;
  narrative: string;
}

// ---- 5.7 Events and timeline ----------------------------------------------------------------
export type EventType =
  | "ENTRY_SURGE"
  | "DENSITY_RISING"
  | "DENSITY_THRESHOLD"
  | "BOTTLENECK_FORMED"
  | "COUNTERFLOW_EMERGED"
  | "INSTABILITY_RISING"
  | "RISK_STATE_CHANGE"
  | "SPILLOVER"
  | "PEAK_RISK"
  | "DE_ESCALATION";
export interface IncidentEvent {
  event_id: string;
  t_start: number;
  t_end: number | null;
  zone_id: string;
  type: EventType;
  severity: RiskState;
  title: string;
  detail: string;
  evidence: Record<string, number>;
  caused_by: string[];
}
export interface IncidentTimeline {
  run_id: string;
  events: IncidentEvent[];
  origin_zone: string | null;
  origin_time: number | null;
  chain: string[];
  summary: string;
}

// ---- 5.8 Simulation -------------------------------------------------------------------------
export type InterventionType =
  | "NONE"
  | "OPEN_PORTAL"
  | "CLOSE_PORTAL"
  | "REDIRECT"
  | "RESTRICT_ENTRY"
  | "WIDEN_PORTAL";
export interface Intervention {
  type: InterventionType;
  at_t: number;
  portal_id?: string | null;
  from_zone?: string | null;
  to_zone?: string | null;
  fraction?: number | null;
  factor?: number | null;
}
export interface ScenarioSpec {
  scenario_id: string;
  name: string;
  interventions: Intervention[];
}
export type SimModel = "social_force" | "macro";
export interface SimulationRequest {
  run_id: string;
  t0: number;
  horizon_s: number;
  scenarios: ScenarioSpec[];
  seeds: number[];
  model: SimModel;
}
export interface AgentFrame {
  t: number;
  xy: Vec2[];
  local_density: number[];
}
export interface ScenarioMetrics {
  peak_density: number;
  peak_density_zone: string;
  peak_crowd_pressure: number;
  time_in_high_s: number;
  time_in_critical_s: number;
  max_state: RiskState;
  mean_evacuation_rate: number;
  agents_remaining: number;
  seed_std: Record<string, number>;
}
export interface ScenarioResult {
  scenario_id: string;
  name: string;
  timeseries_path: string;
  risk_path: string;
  frames_path: string;
  metrics: ScenarioMetrics;
  interventions: Intervention[];
}
export type JobState = "QUEUED" | "RUNNING" | "DONE" | "FAILED";
export interface SimulationStatus {
  sim_id: string;
  run_id: string;
  status: JobState;
  request: SimulationRequest;
  results: ScenarioResult[];
  error: string | null;
}
export interface ComparisonRow {
  scenario_id: string;
  name: string;
  peak_density: number;
  peak_crowd_pressure: number;
  time_in_high_s: number;
  time_in_critical_s: number;
  max_state: RiskState;
  seed_std: Record<string, number>;
  is_best: boolean;
  risk_series: Vec2[];
}
export type Verdict = "GOOD" | "FAIR" | "POOR";
export interface Comparison {
  sim_id: string;
  t0: number;
  horizon_s: number;
  rows: ComparisonRow[];
  validation_verdict: Verdict | null;
}

// ---- 5.9 Validation ----------------------------------------------------------------------
export interface ValidationReport {
  run_id: string;
  t0: number;
  horizon_s: number;
  per_zone_density_rmse: Record<string, number>;
  per_zone_density_corr: Record<string, number>;
  overall_density_rmse: number;
  peak_time_error_s: number;
  peak_density_error_pct: number;
  state_agreement: number;
  calibrated_params: Record<string, number>;
  verdict: Verdict;
  calibration_window: Vec2;
  validation_window: Vec2;
  worst_zone: string;
  observed_series: Vec2[];
  simulated_series: Vec2[];
}

// ---- 5.10 Strategy -----------------------------------------------------------------------
export interface Recommendation {
  rank: number;
  scenario_id: string;
  headline: string;
  deltas: Record<string, number>;
  confidence_note: string;
  caveat: string;
}
export interface PreventionPlan {
  run_id: string;
  recommendations: Recommendation[];
  key_lessons: string[];
}

// ---- Runs and jobs -----------------------------------------------------------------------
export interface JobStatus {
  job_id: string;
  kind: string;
  state: JobState;
  stage: string;
  percent: number;
  message: string;
  eta_s: number | null;
  error: string | null;
  result_id: string | null;
}
export interface ProgressEvent {
  stage: string;
  percent: number;
  message: string;
  eta_s: number | null;
  done: boolean;
  error: string | null;
}
export interface RunMeta {
  run_id: string;
  video: VideoMeta;
  venue_id: string;
  methods: Record<string, string>;
  config_hash: string;
  timings_s: Record<string, number>;
  status: JobState;
  job_id: string | null;
  created_at: string;
  notes: string[];
}
export interface CreateRunResponse {
  run_id: string;
  job_id: string;
}
export interface CreateSimResponse {
  sim_id: string;
  job_id: string;
}
export interface HealthResponse {
  status: string;
  version: string;
  python: string;
  gpu_available: boolean;
  gpu_name: string | null;
  versions: Record<string, string>;
  models: Record<string, string | boolean>;
  config_hash: string;
}
export interface ApiErrorBody {
  error: { code: string; message: string; detail: unknown };
}
