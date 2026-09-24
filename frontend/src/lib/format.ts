/** Seconds → "m:ss" (or "h:mm:ss" past an hour). */
export function fmtTime(s: number | null | undefined): string {
  if (s == null || !Number.isFinite(s)) return "--:--";
  const neg = s < 0;
  const total = Math.floor(Math.abs(s));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const sec = total % 60;
  const body = h > 0 ? `${h}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}` : `${m}:${String(sec).padStart(2, "0")}`;
  return neg ? `-${body}` : body;
}

export function fmtNum(v: number | null | undefined, digits = 2): string {
  if (v == null || !Number.isFinite(v)) return "–";
  return v.toFixed(digits);
}

/** Density with enough precision to be meaningful for sparse scenes (0.053 rather than 0.1 or 0.0). */
export function fmtDensity(d: number | null | undefined): string {
  if (d == null || !Number.isFinite(d)) return "–";
  if (d < 0.1) return d.toFixed(3);
  if (d < 1) return d.toFixed(2);
  return d.toFixed(1);
}

export function fmtPct(v: number | null | undefined, digits = 0): string {
  if (v == null || !Number.isFinite(v)) return "–";
  return `${(v * 100).toFixed(digits)}%`;
}

export function fmtDelta(v: number, digits = 2): string {
  const s = v.toFixed(digits);
  return v > 0 ? `+${s}` : s;
}

export const FEATURE_UNITS: Record<string, string> = {
  count: "people",
  density: "p/m²",
  mean_speed: "m/s",
  speed_var: "(m/s)²",
  velocity_var: "(m/s)²",
  direction_entropy: "",
  counterflow_index: "",
  flow_instability: "m/s²",
  inflow_rate: "p/s",
  outflow_rate: "p/s",
  bottleneck_pressure: "× cap",
  crowd_pressure: "1/s²",
};
