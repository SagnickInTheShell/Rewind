import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, Legend } from "recharts";
import { CheckCircle2, AlertCircle, XCircle, Info } from "lucide-react";
import type { ValidationReport, Verdict } from "../../types";
import { Card } from "../ui/primitives";
import { fmtTime } from "../../lib/format";

interface Props {
  validation: ValidationReport | null | undefined;
}

export function ValidationCard({ validation }: Props) {
  if (!validation) {
    return (
      <Card title="Simulation Replay Validation">
        <p className="text-xs text-muted italic p-4 text-center">
          No validation report available for this run.
        </p>
      </Card>
    );
  }

  // Combine observed and simulated series into charting data
  const chartData: Array<{ t: number; observed?: number; simulated?: number }> = [];
  const tMap = new Map<number, { observed?: number; simulated?: number }>();

  for (const pt of validation.observed_series || []) {
    const t = Math.round(pt[0] * 10) / 10;
    if (!tMap.has(t)) tMap.set(t, {});
    tMap.get(t)!.observed = pt[1];
  }
  for (const pt of validation.simulated_series || []) {
    const t = Math.round(pt[0] * 10) / 10;
    if (!tMap.has(t)) tMap.set(t, {});
    tMap.get(t)!.simulated = pt[1];
  }

  const sortedTs = Array.from(tMap.keys()).sort((a, b) => a - b);
  for (const t of sortedTs) {
    chartData.push({
      t,
      observed: tMap.get(t)?.observed,
      simulated: tMap.get(t)?.simulated,
    });
  }

  const getVerdictBadge = (v: Verdict) => {
    switch (v) {
      case "GOOD":
        return (
          <span className="flex items-center gap-1 rounded bg-emerald-500/20 border border-emerald-500/40 px-2 py-0.5 text-xs font-bold text-emerald-400">
            <CheckCircle2 className="h-3.5 w-3.5" /> VERDICT: GOOD
          </span>
        );
      case "FAIR":
        return (
          <span className="flex items-center gap-1 rounded bg-yellow-500/20 border border-yellow-500/40 px-2 py-0.5 text-xs font-bold text-yellow-400">
            <AlertCircle className="h-3.5 w-3.5" /> VERDICT: FAIR
          </span>
        );
      case "POOR":
        return (
          <span className="flex items-center gap-1 rounded bg-red-500/20 border border-red-500/40 px-2 py-0.5 text-xs font-bold text-red-400">
            <XCircle className="h-3.5 w-3.5" /> VERDICT: POOR
          </span>
        );
      default:
        return null;
    }
  };

  return (
    <Card
      title="Do-Nothing Replay vs Real Footage"
      right={getVerdictBadge(validation.verdict)}
    >
      <div className="flex flex-col gap-4">
        {/* Metric summary grid */}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div className="rounded border border-border bg-panel p-2.5">
            <div className="text-[11px] text-muted">Overall Density RMSE</div>
            <div className="font-mono text-base font-bold text-text">
              {validation.overall_density_rmse.toFixed(2)}{" "}
              <span className="text-xs text-muted font-normal">p/m²</span>
            </div>
          </div>
          <div className="rounded border border-border bg-panel p-2.5">
            <div className="text-[11px] text-muted">Risk State Agreement</div>
            <div className="font-mono text-base font-bold text-emerald-400">
              {(validation.state_agreement * 100).toFixed(0)}%
            </div>
          </div>
          <div className="rounded border border-border bg-panel p-2.5">
            <div className="text-[11px] text-muted">Peak Time Error</div>
            <div className="font-mono text-base font-bold text-text">
              {validation.peak_time_error_s.toFixed(1)}s
            </div>
          </div>
          <div className="rounded border border-border bg-panel p-2.5">
            <div className="text-[11px] text-muted">Peak Density Error</div>
            <div className="font-mono text-base font-bold text-text">
              {validation.peak_density_error_pct.toFixed(1)}%
            </div>
          </div>
        </div>

        {/* Overlaid density chart */}
        <div className="rounded border border-border bg-panel/50 p-3">
          <div className="flex items-center justify-between mb-2">
            <div className="text-xs font-medium text-text">
              Worst Zone ({validation.worst_zone}) Density Trajectory Over Time
            </div>
            <div className="text-[11px] text-muted font-mono">
              Horizon: {validation.horizon_s}s from t₀={fmtTime(validation.t0)}
            </div>
          </div>
          <div className="h-44 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 5, right: 15, left: -20, bottom: 0 }}>
                <XAxis
                  dataKey="t"
                  tickFormatter={fmtTime}
                  stroke="#8B98A5"
                  fontSize={11}
                  tickLine={false}
                />
                <YAxis stroke="#8B98A5" fontSize={11} tickLine={false} unit=" p/m²" />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#121821",
                    borderColor: "#1F2A37",
                    borderRadius: "6px",
                    fontSize: "12px",
                  }}
                  labelFormatter={(t) => `t = ${fmtTime(Number(t))}`}
                  // eslint-disable-next-line @typescript-eslint/no-explicit-any
                  formatter={(value: any, name: any) => [
                    `${Number(value ?? 0).toFixed(2)} p/m²`,
                    name === "observed" ? "Observed (Footage)" : "Simulated (Replay)",
                  ]}
                />
                <Legend
                  wrapperStyle={{ fontSize: "11px", paddingTop: "4px" }}
                  formatter={(val) => (val === "observed" ? "Observed Video Footage" : "Simulated Do-Nothing Replay")}
                />
                <Line
                  type="monotone"
                  dataKey="observed"
                  stroke="#38BDF8"
                  strokeWidth={2}
                  dot={false}
                  isAnimationActive={false}
                />
                <Line
                  type="monotone"
                  dataKey="simulated"
                  stroke="#F59E0B"
                  strokeWidth={2}
                  strokeDasharray="4 4"
                  dot={false}
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Methodology note */}
        <div className="flex items-start gap-2 rounded bg-panel p-2.5 text-xs text-muted border border-border/50">
          <Info className="h-4 w-4 shrink-0 text-accent mt-0.5" />
          <div className="leading-relaxed">
            <span className="font-semibold text-text">Out-of-sample validation:</span> Calibrated via Nelder–Mead on first 50% window ({fmtTime(validation.calibration_window?.[0] ?? 0)}–{fmtTime(validation.calibration_window?.[1] ?? 0)}), validated on non-overlapping evaluation window ({fmtTime(validation.validation_window?.[0] ?? 0)}–{fmtTime(validation.validation_window?.[1] ?? 0)}).
          </div>
        </div>
      </div>
    </Card>
  );
}
