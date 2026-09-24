import type { RiskState } from "../types";

export const THEME = {
  bg: "#0B0F14",
  panel: "#121821",
  border: "#1F2A37",
  text: "#E6EDF3",
  muted: "#8B98A5",
  accent: "#38BDF8",
} as const;

export const RISK_COLORS: Record<RiskState, string> = {
  LOW: "#22C55E",
  MEDIUM: "#EAB308",
  HIGH: "#F97316",
  CRITICAL: "#EF4444",
};

export function riskColor(state: string | null | undefined): string {
  if (state && state in RISK_COLORS) return RISK_COLORS[state as RiskState];
  return THEME.muted;
}

// Viridis control points (perceptually uniform), sampled at 0, .25, .5, .75, 1.
const VIRIDIS: [number, number, number][] = [
  [68, 1, 84],
  [59, 82, 139],
  [33, 145, 140],
  [94, 201, 98],
  [253, 231, 37],
];

export function viridisRgb(v: number): [number, number, number] {
  const x = Math.min(Math.max(Number.isFinite(v) ? v : 0, 0), 1) * (VIRIDIS.length - 1);
  const i = Math.min(Math.floor(x), VIRIDIS.length - 2);
  const f = x - i;
  const a = VIRIDIS[i];
  const b = VIRIDIS[i + 1];
  return [
    Math.round(a[0] + (b[0] - a[0]) * f),
    Math.round(a[1] + (b[1] - a[1]) * f),
    Math.round(a[2] + (b[2] - a[2]) * f),
  ];
}

export function viridis(v: number, alpha = 1): string {
  const [r, g, b] = viridisRgb(v);
  return alpha >= 1 ? `rgb(${r},${g},${b})` : `rgba(${r},${g},${b},${alpha})`;
}

/** Density (people/m²) → 0..1 for the heatmap scale; saturates at `max`. */
export function densityNorm(d: number, max = 6): number {
  return Math.min(Math.max(d / max, 0), 1);
}

/** Density bucket index used by the twin renderer (one path per bucket). */
export const DENSITY_BUCKETS = 8;
export function densityBucket(d: number, max = 6): number {
  return Math.min(DENSITY_BUCKETS - 1, Math.max(0, Math.floor(densityNorm(d, max) * DENSITY_BUCKETS)));
}
export const BUCKET_COLORS: string[] = Array.from({ length: DENSITY_BUCKETS }, (_, i) =>
  viridis((i + 0.5) / DENSITY_BUCKETS),
);
