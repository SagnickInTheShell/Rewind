// Deterministic fake data for every contract (mirrors backend/rewind/fixtures.py).
import type {
  AgentFrame,
  Comparison,
  Explanation,
  GlobalRiskPoint,
  IncidentTimeline,
  Portal,
  PreventionPlan,
  RiskPoint,
  RiskSeries,
  RiskState,
  RunMeta,
  ValidationReport,
  Venue,
  VideoMeta,
  Zone,
  ZoneFeatures,
} from "../types";

const ROWS = ["A", "B", "C"];

export function stateFor(score: number): RiskState {
  if (score >= 0.75) return "CRITICAL";
  if (score >= 0.55) return "HIGH";
  if (score >= 0.35) return "MEDIUM";
  return "LOW";
}

/** Small seeded PRNG (mulberry32). */
export function rng(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function fakeVideoMeta(): VideoMeta {
  return {
    video_id: "vid_fixture",
    filename: "fixture.mp4",
    fps_native: 25,
    fps_processed: 5,
    width: 1280,
    height: 720,
    duration_s: 180,
    frame_count: 4500,
    synthetic: true,
  };
}

export function fakeVenue(width = 30, height = 20): Venue {
  const cw = width / 3;
  const ch = height / 3;
  const zones: Zone[] = [];
  const portals: Portal[] = [];
  ROWS.forEach((row, r) => {
    for (let c = 0; c < 3; c++) {
      const x0 = c * cw;
      const y0 = r * ch;
      zones.push({
        zone_id: `${row}${c + 1}`,
        name: `Zone ${row}${c + 1}`,
        kind: "floor",
        polygon: [
          { x: x0, y: y0 },
          { x: x0 + cw, y: y0 },
          { x: x0 + cw, y: y0 + ch },
          { x: x0, y: y0 + ch },
        ],
      });
    }
  });
  portals.push(
    gate("GATE_A", "OUTSIDE", "A2", 13, 0, 17, 0, true),
    gate("GATE_B", "C2", "OUTSIDE", 13.5, height, 16.5, height, true),
    gate("GATE_C", "C3", "OUTSIDE", width, 15, width, 18.5, false),
  );
  return {
    venue_id: "fixture_venue",
    name: "Fixture Plaza",
    bounds: [
      { x: 0, y: 0 },
      { x: width, y: height },
    ],
    zones,
    portals,
    walls: [
      { a: { x: 0, y: 0 }, b: { x: width, y: 0 } },
      { a: { x: width, y: 0 }, b: { x: width, y: height } },
      { a: { x: width, y: height }, b: { x: 0, y: height } },
      { a: { x: 0, y: height }, b: { x: 0, y: 0 } },
    ],
    sources: ["A2"],
    sinks: ["C2", "C3"],
    calibration: { image_points: [], world_points: [] },
  };
}

function gate(
  id: string,
  from: string,
  to: string,
  x1: number,
  y1: number,
  x2: number,
  y2: number,
  open: boolean,
): Portal {
  return {
    portal_id: id,
    name: id.replace("GATE_", "Gate "),
    from_zone: from,
    to_zone: to,
    segment: [
      { x: x1, y: y1 },
      { x: x2, y: y2 },
    ],
    width_m: Math.hypot(x2 - x1, y2 - y1),
    is_open: open,
    bidirectional: false,
    kind: "gate",
  };
}

const LAG: Record<string, number> = { A2: -20, B2: 0, C2: 5, B1: 20, B3: 25, C1: 30, C3: 30 };
const AMP: Record<string, number> = { A2: 0.5, B2: 1, C2: 0.95, B1: 0.6, B3: 0.55, C1: 0.45, C3: 0.45 };

export function escalation(t: number, zone: string, tPeak = 120): number {
  const a = AMP[zone] ?? 0.25;
  const x = (t - (tPeak - 60 + (LAG[zone] ?? 40))) / 25;
  return a / (1 + Math.exp(-x));
}

export const ZONE_IDS = ROWS.flatMap((r) => [1, 2, 3].map((c) => `${r}${c}`));

export function fakeFeatures(duration = 180): ZoneFeatures[] {
  const rows: ZoneFeatures[] = [];
  for (let k = 1; k <= duration; k++) {
    for (const z of ZONE_IDS) {
      const e = escalation(k, z);
      const density = 0.5 + 5 * e;
      const vv = 0.02 + 0.3 * e * e;
      rows.push({
        t: k,
        zone_id: z,
        count: density * 66.7,
        density,
        mean_speed: 1.3 * (1 - 0.8 * e),
        speed_var: 0.05 + 0.1 * e,
        velocity_var: vv,
        dominant_dir: Math.PI / 2,
        direction_entropy: Math.min(0.2 + 0.7 * e, 1),
        counterflow_index: Math.min(0.05 + 0.5 * e, 1),
        flow_instability: 0.1 + 0.8 * e,
        inflow_rate: 2 + 6 * e,
        outflow_rate: 2 + 2 * e,
        bottleneck_pressure: 0.3 + 2 * e,
        crowd_pressure: density * vv * 0.1,
        source: density > 1.5 ? "fused" : "tracks",
      });
    }
  }
  return rows;
}

export function fakeRisk(duration = 180): RiskSeries {
  const zones: RiskPoint[] = [];
  const global_risk: GlobalRiskPoint[] = [];
  for (let k = 1; k <= duration; k++) {
    let worst: RiskPoint | null = null;
    for (const z of ZONE_IDS) {
      const s = Math.min(escalation(k, z) * 0.95, 1);
      const p: RiskPoint = {
        t: k,
        zone_id: z,
        physics_score: s,
        ml_score: Math.min(s * 1.05, 1),
        ensemble_score: s,
        state: stateFor(s),
      };
      zones.push(p);
      if (!worst || p.ensemble_score > worst.ensemble_score) worst = p;
    }
    if (worst)
      global_risk.push({ t: k, max_score: worst.ensemble_score, worst_zone: worst.zone_id, state: worst.state });
  }
  return { run_id: "run_fixture", zones, global_risk, methods: { physics: true, temporal: true, xgb: true } };
}

export function fakeExplanation(t = 120, zone = "B2"): Explanation {
  return {
    t,
    zone_id: zone,
    score: 0.54,
    state: "MEDIUM",
    method: "physics_weights",
    narrative:
      "Risk in Zone B2 (near Gate B) appears to have risen mainly because density climbed from 2.8 to 4.6 people/m² while opposing movement increased (counterflow 0.41).",
    contributions: [
      { feature: "density", label: "Density", value: 4.6, contribution: 0.19, share: 0.35 },
      { feature: "crowd_pressure", label: "Crowd pressure", value: 0.03, contribution: 0.15, share: 0.28 },
      { feature: "bottleneck_pressure", label: "Bottleneck pressure", value: 1.7, contribution: 0.12, share: 0.22 },
      { feature: "counterflow_index", label: "Counterflow", value: 0.41, contribution: 0.05, share: 0.09 },
      { feature: "flow_instability", label: "Flow instability", value: 0.2, contribution: 0.03, share: 0.06 },
    ],
  };
}

export function fakeTimeline(): IncidentTimeline {
  const specs: [string, number, string, IncidentTimeline["events"][number]["type"], RiskState, string][] = [
    ["e1", 40, "A2", "ENTRY_SURGE", "MEDIUM", "Entry surge at Gate A"],
    ["e2", 55, "B2", "DENSITY_RISING", "MEDIUM", "Density rising in Zone B2"],
    ["e3", 75, "C2", "BOTTLENECK_FORMED", "HIGH", "Bottleneck detected at Gate B"],
    ["e4", 90, "B2", "COUNTERFLOW_EMERGED", "HIGH", "Counterflow emerged in Zone B2"],
    ["e5", 100, "B2", "RISK_STATE_CHANGE", "HIGH", "Zone B2 risk rose to HIGH"],
    ["e6", 120, "B2", "PEAK_RISK", "CRITICAL", "Peak modelled risk in Zone B2"],
  ];
  let prev: string | null = null;
  const events = specs.map(([id, t, z, type, sev, title]) => {
    const ev = {
      event_id: id,
      t_start: t,
      t_end: t + 10,
      zone_id: z,
      type,
      severity: sev,
      title,
      detail: `${title}.`,
      evidence: { density: 3 },
      caused_by: prev ? [prev] : [],
    };
    prev = id;
    return ev;
  });
  return {
    run_id: "run_fixture",
    events,
    origin_zone: "A2",
    origin_time: 40,
    chain: events.map((e) => e.event_id),
    summary: "The escalation appears to have originated with an entry surge at Gate A at 0:40.",
  };
}

export function fakeRunMeta(): RunMeta {
  return {
    run_id: "run_fixture",
    video: fakeVideoMeta(),
    venue_id: "fixture_venue",
    methods: { detector: "yolov8s", tracker: "bytetrack", density: "kde" },
    config_hash: "abc123",
    timings_s: {},
    status: "DONE",
    job_id: null,
    created_at: "2026-01-01T00:00:00Z",
    notes: [],
  };
}

export function fakeAgentFrames(nFrames = 100, nAgents = 400, seed = 0): AgentFrame[] {
  const r = rng(seed);
  const xy: [number, number][] = Array.from({ length: nAgents }, () => [r() * 30, r() * 20]);
  const frames: AgentFrame[] = [];
  for (let k = 0; k < nFrames; k++) {
    for (const p of xy) {
      p[0] = Math.min(30, Math.max(0, p[0] + (r() - 0.5) * 0.2));
      p[1] = Math.min(20, Math.max(0, p[1] + 0.05 + (r() - 0.5) * 0.2));
    }
    frames.push({
      t: 60 + k * 0.1,
      xy: xy.map((p) => [p[0], p[1]] as [number, number]),
      local_density: xy.map((p) => 5 * Math.exp(-((p[0] - 15) ** 2 + (p[1] - 16) ** 2) / 30)),
    });
  }
  return frames;
}

export function fakeComparison(): Comparison {
  const mk = (id: string, name: string, peak: number, crit: number, state: RiskState, best = false) => ({
    scenario_id: id,
    name,
    peak_density: peak,
    peak_crowd_pressure: peak * 0.006,
    time_in_high_s: crit * 3,
    time_in_critical_s: crit,
    max_state: state,
    seed_std: { peak_density: 0.2, time_in_high_s: 4 },
    is_best: best,
    risk_series: Array.from({ length: 60 }, (_, i) => [60 + i * 2, Math.min(1, (peak / 6) * (i / 60))] as [number, number]),
  });
  return {
    sim_id: "sim_fixture",
    t0: 60,
    horizon_s: 120,
    validation_verdict: "GOOD",
    rows: [
      mk("baseline", "Baseline (do nothing)", 5.4, 30, "CRITICAL"),
      mk("open_c", "Open Gate C", 3.2, 0, "MEDIUM", true),
      mk("restrict", "Restrict entry 50%", 3.9, 0, "HIGH"),
    ],
  };
}

export function fakeValidation(): ValidationReport {
  return {
    run_id: "run_fixture",
    t0: 90,
    horizon_s: 90,
    per_zone_density_rmse: { B2: 0.4 },
    per_zone_density_corr: { B2: 0.9 },
    overall_density_rmse: 0.42,
    peak_time_error_s: 6,
    peak_density_error_pct: 8,
    state_agreement: 0.82,
    calibrated_params: { tau: 0.5 },
    verdict: "GOOD",
    calibration_window: [0, 90],
    validation_window: [90, 180],
    worst_zone: "B2",
    observed_series: Array.from({ length: 90 }, (_, i) => [90 + i, 0.5 + 5 * escalation(90 + i, "B2")] as [number, number]),
    simulated_series: Array.from({ length: 90 }, (_, i) => [90 + i, 0.6 + 4.8 * escalation(92 + i, "B2")] as [number, number]),
  };
}

export function fakePlan(): PreventionPlan {
  return {
    run_id: "run_fixture",
    recommendations: [
      {
        rank: 1,
        scenario_id: "open_c",
        headline: "Opening Gate C at 1:00 lowered modelled peak risk from CRITICAL to MEDIUM",
        deltas: { peak_density: -2.2, time_in_critical_s: -30 },
        confidence_note: "Low variability across seeds; validation GOOD.",
        caveat:
          "Simulation output under modelled assumptions. Not a guarantee of real-world outcomes. Intended to support, not replace, trained crowd-safety professionals.",
      },
    ],
    key_lessons: ["Gate B capacity was exceeded about 45 s before the modelled peak."],
  };
}
