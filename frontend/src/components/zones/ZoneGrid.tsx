import { useMemo } from "react";
import type { RiskPoint, Venue, ZoneFeatures } from "../../types";
import { riskColor } from "../../lib/colors";
import { centroid, groupBy, valueAt } from "../../lib/series";

interface Props {
  venue: Venue;
  risk: RiskPoint[];
  features?: ZoneFeatures[];
  t: number;
  selectedZone?: string | null;
  onSelect?: (zone: string) => void;
  onHover?: (zone: string | null) => void;
}

/** Floor-plan zone grid coloured by the current risk state, with density numbers. */
export function ZoneGrid({ venue, risk, features, t, selectedZone, onSelect, onHover }: Props) {
  const byZone = useMemo(() => groupBy(risk, (r) => r.zone_id), [risk]);
  const featByZone = useMemo(() => groupBy(features ?? [], (f) => f.zone_id), [features]);
  const [min, max] = venue.bounds;
  const w = max.x - min.x;
  const h = max.y - min.y;
  const pad = Math.max(w, h) * 0.03;
  return (
    <svg
      viewBox={`${min.x - pad} ${min.y - pad} ${w + 2 * pad} ${h + 2 * pad}`}
      className="w-full"
      role="img"
      aria-label="Zone risk grid"
      data-testid="zone-grid"
    >
      {venue.zones.map((z) => {
        const rp = valueAt(byZone.get(z.zone_id) ?? [], t, (r) => r.t);
        const fp = valueAt(featByZone.get(z.zone_id) ?? [], t, (f) => f.t);
        const state = rp?.state ?? "LOW";
        const c = riskColor(state);
        const cen = centroid(z.polygon);
        const sel = selectedZone === z.zone_id;
        const fs = Math.min(w, h) * 0.06;
        return (
          <g
            key={z.zone_id}
            onClick={() => onSelect?.(z.zone_id)}
            onMouseEnter={() => onHover?.(z.zone_id)}
            onMouseLeave={() => onHover?.(null)}
            className="cursor-pointer"
            style={{ transition: "fill 300ms" }}
          >
            <title>{`${z.name}: ${state}, ensemble score ${rp ? rp.ensemble_score.toFixed(2) : "–"} (physics ${rp ? rp.physics_score.toFixed(2) : "–"}${rp?.ml_score != null ? `, ML ${rp.ml_score.toFixed(2)}` : ""})`}</title>
            <polygon
              points={z.polygon.map((p) => `${p.x},${p.y}`).join(" ")}
              fill={`${c}${state === "LOW" ? "33" : "66"}`}
              stroke={sel ? "#E6EDF3" : "#0B0F14"}
              strokeWidth={sel ? w * 0.008 : w * 0.004}
              style={{ transition: "fill 300ms" }}
            />
            <text x={cen.x} y={cen.y - fs * 0.35} textAnchor="middle" fontSize={fs} fontWeight={700} fill="#E6EDF3">
              {z.zone_id}
            </text>
            <text x={cen.x} y={cen.y + fs * 0.85} textAnchor="middle" fontSize={fs * 0.72} fill="#E6EDF3" fontFamily="JetBrains Mono">
              {fp ? `${fp.density.toFixed(1)}/m²` : "–"}
            </text>
          </g>
        );
      })}
      {venue.portals
        .filter((p) => p.kind === "gate")
        .map((p) => (
          <line
            key={p.portal_id}
            x1={p.segment[0].x}
            y1={p.segment[0].y}
            x2={p.segment[1].x}
            y2={p.segment[1].y}
            stroke={p.is_open ? "#22C55E" : "#4B5563"}
            strokeWidth={w * 0.012}
            strokeLinecap="round"
          >
            <title>{`${p.name} (${p.is_open ? "open" : "closed"}, ${p.width_m} m)`}</title>
          </line>
        ))}
    </svg>
  );
}
