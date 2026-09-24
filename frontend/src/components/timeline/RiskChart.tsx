import { useMemo } from "react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { GlobalRiskPoint, IncidentEvent, RiskPoint } from "../../types";
import { RISK_COLORS, THEME, riskColor } from "../../lib/colors";
import { fmtNum, fmtTime } from "../../lib/format";

export interface Thresholds {
  medium: number;
  high: number;
  critical: number;
}
export const DEFAULT_THRESHOLDS: Thresholds = { medium: 0.35, high: 0.55, critical: 0.75 };

interface Props {
  global: GlobalRiskPoint[];
  zones?: RiskPoint[];
  hoverZone?: string | null;
  events?: IncidentEvent[];
  currentTime?: number;
  onSeek?: (t: number) => void;
  height?: number;
  thresholds?: Thresholds;
  compact?: boolean;
}

interface Row {
  t: number;
  score: number;
  zone?: number;
  worst: string;
  state: string;
}

export function RiskChart({
  global,
  zones,
  hoverZone,
  events = [],
  currentTime,
  onSeek,
  height = 220,
  thresholds = DEFAULT_THRESHOLDS,
  compact = false,
}: Props) {
  const data = useMemo<Row[]>(() => {
    const zmap = new Map<number, number>();
    if (hoverZone && zones) for (const p of zones) if (p.zone_id === hoverZone) zmap.set(p.t, p.ensemble_score);
    return global.map((g) => ({ t: g.t, score: g.max_score, zone: zmap.get(g.t), worst: g.worst_zone, state: g.state }));
  }, [global, zones, hoverZone]);

  const tMin = data.length ? data[0].t : 0;
  const tMax = data.length ? data[data.length - 1].t : 1;

  return (
    <div style={{ height }} data-testid="risk-chart">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart
          data={data}
          margin={{ top: 8, right: 12, bottom: 0, left: compact ? -24 : -8 }}
          onClick={(e) => {
            const t = e?.activeLabel;
            if (onSeek && t != null) onSeek(Number(t));
          }}
        >
          <ReferenceArea y1={0} y2={thresholds.medium} fill={RISK_COLORS.LOW} fillOpacity={0.06} />
          <ReferenceArea y1={thresholds.medium} y2={thresholds.high} fill={RISK_COLORS.MEDIUM} fillOpacity={0.07} />
          <ReferenceArea y1={thresholds.high} y2={thresholds.critical} fill={RISK_COLORS.HIGH} fillOpacity={0.08} />
          <ReferenceArea y1={thresholds.critical} y2={1} fill={RISK_COLORS.CRITICAL} fillOpacity={0.09} />
          <CartesianGrid stroke={THEME.border} strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="t"
            type="number"
            domain={[tMin, tMax]}
            tickFormatter={(v: number) => fmtTime(v)}
            stroke={THEME.muted}
            tick={{ fontSize: 13, fontFamily: "JetBrains Mono" }}
          />
          <YAxis domain={[0, 1]} ticks={[0, 0.35, 0.55, 0.75, 1]} stroke={THEME.muted} tick={{ fontSize: 13 }} hide={compact} />
          {!compact && (
            <Tooltip
              contentStyle={{ background: THEME.panel, border: `1px solid ${THEME.border}`, color: THEME.text }}
              labelFormatter={(v) => fmtTime(Number(v))}
              formatter={(v: number, name: string) => [fmtNum(v), name === "score" ? "Ensemble (worst zone)" : `Zone ${hoverZone}`]}
            />
          )}
          <Area type="monotone" dataKey="score" stroke={THEME.accent} strokeWidth={2} fill={THEME.accent} fillOpacity={0.12} isAnimationActive={false} dot={false} />
          {hoverZone && <Line type="monotone" dataKey="zone" stroke="#c084fc" strokeWidth={1.5} dot={false} isAnimationActive={false} />}
          {events.map((e) => (
            <ReferenceLine
              key={e.event_id}
              x={e.t_start}
              stroke={riskColor(e.severity)}
              strokeDasharray="2 3"
              strokeOpacity={0.8}
              ifOverflow="discard"
            />
          ))}
          {currentTime != null && <ReferenceLine x={currentTime} stroke={THEME.text} strokeWidth={2} ifOverflow="discard" />}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
