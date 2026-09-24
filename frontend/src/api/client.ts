// Typed API client. All routes live under /api (proxied to the backend by Vite in dev).
import type {
  ApiErrorBody,
  Comparison,
  CreateRunResponse,
  CreateSimResponse,
  Explanation,
  HealthResponse,
  IncidentTimeline,
  JobStatus,
  OverlayFrame,
  PreventionPlan,
  RiskSeries,
  RunMeta,
  SimulationRequest,
  SimulationStatus,
  ValidationReport,
  Venue,
  VideoMeta,
  ZoneFeatures,
} from "../types";

export const API_BASE = "/api";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public detail?: unknown,
  ) {
    super(message);
  }
}

function isErrorBody(x: unknown): x is ApiErrorBody {
  return typeof x === "object" && x !== null && "error" in x;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  const text = await res.text();
  const body: unknown = text ? JSON.parse(text) : null;
  if (!res.ok) {
    if (isErrorBody(body)) throw new ApiError(res.status, body.error.code, body.error.message, body.error.detail);
    throw new ApiError(res.status, "http_error", res.statusText);
  }
  return body as T;
}

const q = (params: Record<string, string | number | boolean | null | undefined>): string => {
  const s = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null) s.set(k, String(v));
  const str = s.toString();
  return str ? `?${str}` : "";
};

export interface VenueSummary {
  venue_id: string;
  name: string;
  zones: number;
  portals: number;
}

export interface DemoLoadResponse {
  run: RunMeta;
  sim_id: string | null;
  has_validation: boolean;
}

export const api = {
  health: () => request<HealthResponse>("/health"),
  // videos
  listVideos: () => request<VideoMeta[]>("/videos"),
  getVideo: (id: string) => request<VideoMeta>(`/videos/${id}`),
  videoStreamUrl: (id: string) => `${API_BASE}/videos/${id}/stream`,
  frameUrl: (id: string, t = 0, original = false) => `${API_BASE}/videos/${id}/frame${q({ t, original })}`,
  // venues
  listVenues: () => request<VenueSummary[]>("/venues"),
  getVenue: (id: string) => request<Venue>(`/venues/${id}`),
  putVenue: (v: Venue) => request<Venue>(`/venues/${v.venue_id}`, { method: "PUT", body: JSON.stringify(v) }),
  // runs
  createRun: (video_id: string, venue_id: string, force = false, sensitive = false) =>
    request<CreateRunResponse>("/runs", { method: "POST", body: JSON.stringify({ video_id, venue_id, force, sensitive }) }),
  listRuns: () => request<RunMeta[]>("/runs"),
  getRun: (id: string) => request<RunMeta>(`/runs/${id}`),
  getFeatures: (id: string, zone?: string, t_from?: number, t_to?: number) =>
    request<ZoneFeatures[]>(`/runs/${id}/features${q({ zone, t_from, t_to })}`),
  getRisk: (id: string) => request<RiskSeries>(`/runs/${id}/risk`),
  getExplanation: (id: string, t: number, zone?: string | null, method: "physics" | "shap" = "physics") =>
    request<Explanation>(`/runs/${id}/explanations${q({ t, zone: zone ?? undefined, method })}`),
  getTimeline: (id: string) => request<IncidentTimeline>(`/runs/${id}/timeline`),
  getOverlay: (id: string, t: number, heatmap = true) => request<OverlayFrame>(`/runs/${id}/overlay${q({ t, heatmap })}`),
  getJob: (id: string) => request<JobStatus>(`/jobs/${id}`),
  // validation
  validate: (runId: string, t0?: number, horizon_s?: number) =>
    request<{ job_id: string }>(`/runs/${runId}/validate`, { method: "POST", body: JSON.stringify({ t0, horizon_s }) }),
  getValidation: (runId: string) => request<ValidationReport>(`/runs/${runId}/validation`),
  // simulations
  createSimulation: (req: SimulationRequest) =>
    request<CreateSimResponse>("/simulations", { method: "POST", body: JSON.stringify(req) }),
  getSimulation: (simId: string) => request<SimulationStatus>(`/simulations/${simId}`),
  getComparison: (simId: string) => request<Comparison>(`/simulations/${simId}/comparison`),
  getPlan: (simId: string) => request<PreventionPlan>(`/simulations/${simId}/plan`),
  framesUrl: (simId: string, scenarioId: string, seed = 0, t_from?: number, t_to?: number) =>
    `${API_BASE}/simulations/${simId}/frames/${scenarioId}${q({ seed, t_from, t_to })}`,
  getFrames: (simId: string, scenarioId: string, seed = 0, t_from?: number, t_to?: number) =>
    request<{ scenario_id: string; frames: Array<{ t: number; xy: [number, number][]; local_density: number[] }> }>(
      `/simulations/${simId}/frames/${scenarioId}${q({ seed, t_from, t_to })}`
    ),
  // demo
  loadDemo: () => request<DemoLoadResponse>("/demo/load", { method: "POST" }),
};

/** Upload with progress reporting (fetch has no upload progress events). */
export function uploadVideo(
  file: File,
  opts: { synthetic?: boolean; onProgress?: (fraction: number) => void } = {},
): Promise<VideoMeta> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE}/videos`);
    xhr.timeout = 5 * 60 * 1000; // 5 minute timeout for large uploads
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) opts.onProgress?.(e.loaded / e.total);
    };
    xhr.onload = () => {
      const body: unknown = xhr.responseText ? JSON.parse(xhr.responseText) : null;
      if (xhr.status >= 200 && xhr.status < 300) resolve(body as VideoMeta);
      else if (isErrorBody(body)) reject(new ApiError(xhr.status, body.error.code, body.error.message, body.error.detail));
      else reject(new ApiError(xhr.status, "http_error", xhr.statusText || `Server returned ${xhr.status}`));
    };
    xhr.onerror = () => reject(new ApiError(0, "network", "Upload failed — could not connect to backend. Make sure the backend server is running."));
    xhr.ontimeout = () => reject(new ApiError(0, "timeout", "Upload timed out — the file may be too large or the server is unresponsive."));
    const form = new FormData();
    form.append("file", file);
    form.append("synthetic", String(Boolean(opts.synthetic)));
    xhr.send(form);
  });
}

export function wsUrl(path: string): string {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${window.location.host}${path}`;
}
