import { Award, CheckCircle2 } from "lucide-react";
import type { Comparison, ComparisonRow } from "../../types";
import { Card, RiskBadge } from "../ui/primitives";

interface Props {
  comparison: Comparison | null | undefined;
  selectedScenarioId: string | null;
  onSelectScenario: (scenarioId: string) => void;
}

export function ComparisonTable({ comparison, selectedScenarioId, onSelectScenario }: Props) {
  if (!comparison || !comparison.rows || comparison.rows.length === 0) {
    return (
      <Card title="Scenario Comparison">
        <p className="text-xs text-muted italic p-4 text-center">
          No simulation results available yet. Run a simulation above to compare intervention outcomes.
        </p>
      </Card>
    );
  }

  const rows = comparison.rows;
  const bestRow = rows.find((r) => r.is_best);

  return (
    <Card
      title="Scenario Comparison"
      right={
        bestRow ? (
          <div className="flex items-center gap-1.5 text-xs text-emerald-400 font-medium">
            <Award className="h-4 w-4" /> Recommended: {bestRow.name}
          </div>
        ) : null
      }
    >
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead>
            <tr className="border-b border-border bg-panel/80 text-muted uppercase tracking-wider text-[11px]">
              <th className="py-2.5 px-3">Scenario</th>
              <th className="py-2.5 px-3">Max State</th>
              <th className="py-2.5 px-3">Peak Density</th>
              <th className="py-2.5 px-3">Peak Pressure</th>
              <th className="py-2.5 px-3">Time in HIGH</th>
              <th className="py-2.5 px-3">Time in CRITICAL</th>
              <th className="py-2.5 px-3">Seed Spread (σ)</th>
              <th className="py-2.5 px-3 text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/60">
            {rows.map((row: ComparisonRow) => {
              const isSelected = selectedScenarioId === row.scenario_id;
              const isBaseline = row.scenario_id === "baseline";
              const isBest = row.is_best;

              return (
                <tr
                  key={row.scenario_id}
                  onClick={() => onSelectScenario(row.scenario_id)}
                  className={`cursor-pointer transition-colors ${
                    isSelected
                      ? "bg-accent/15 border-l-2 border-accent"
                      : isBest
                      ? "bg-emerald-950/20 hover:bg-panel"
                      : "hover:bg-panel/70"
                  }`}
                >
                  <td className="py-3 px-3">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-text">{row.name}</span>
                      {isBest && (
                        <span className="rounded bg-emerald-500/20 border border-emerald-500/40 px-1.5 py-0.2 text-[10px] font-semibold text-emerald-400 uppercase">
                          Best Outcome
                        </span>
                      )}
                      {isBaseline && (
                        <span className="rounded bg-border/60 px-1.5 py-0.2 text-[10px] text-muted">
                          Observed / Baseline
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="py-3 px-3">
                    <RiskBadge state={row.max_state} />
                  </td>
                  <td className="py-3 px-3 font-mono">
                    <span className={row.peak_density >= 5.0 ? "text-danger font-semibold" : "text-text"}>
                      {row.peak_density.toFixed(2)}{" "}
                      <span className="text-[10px] text-muted">p/m²</span>
                    </span>
                  </td>
                  <td className="py-3 px-3 font-mono">
                    {row.peak_crowd_pressure ? row.peak_crowd_pressure.toFixed(3) : "—"}
                  </td>
                  <td className="py-3 px-3 font-mono">
                    <span className={row.time_in_high_s > 0 ? "text-warning" : "text-muted"}>
                      {row.time_in_high_s.toFixed(0)}s
                    </span>
                  </td>
                  <td className="py-3 px-3 font-mono">
                    <span className={row.time_in_critical_s > 0 ? "text-danger font-bold" : "text-muted"}>
                      {row.time_in_critical_s.toFixed(0)}s
                    </span>
                  </td>
                  <td className="py-3 px-3 font-mono text-muted text-[11px]">
                    {row.seed_std?.peak_density != null ? (
                      `±${row.seed_std.peak_density.toFixed(2)} p/m²`
                    ) : (
                      "±0.0"
                    )}
                  </td>
                  <td className="py-3 px-3 text-right">
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onSelectScenario(row.scenario_id);
                      }}
                      className={`rounded px-2.5 py-1 text-xs font-medium transition-colors ${
                        isSelected
                          ? "bg-accent text-white"
                          : "bg-panel border border-border text-muted hover:text-text hover:border-accent"
                      }`}
                    >
                      {isSelected ? (
                        <span className="flex items-center gap-1">
                          <CheckCircle2 className="h-3 w-3" /> Selected
                        </span>
                      ) : (
                        "View Twin"
                      )}
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
