import { ShieldCheck, AlertTriangle, BookOpen, ArrowDownRight } from "lucide-react";
import type { PreventionPlan, Recommendation } from "../../types";
import { Card } from "../ui/primitives";

interface Props {
  plan: PreventionPlan | null | undefined;
}

export function PreventionPlanCard({ plan }: Props) {
  if (!plan || !plan.recommendations || plan.recommendations.length === 0) {
    return null;
  }

  return (
    <Card
      title="Prevention Plan & Recommendations"
      right={
        <div className="flex items-center gap-1.5 text-xs text-muted">
          <ShieldCheck className="h-4 w-4 text-accent" /> Ranked by simulated risk mitigation
        </div>
      }
    >
      <div className="flex flex-col gap-5">
        {/* Ranked Recommendations */}
        <div className="flex flex-col gap-3">
          {plan.recommendations.map((rec: Recommendation) => (
            <div
              key={rec.rank}
              className="flex flex-col gap-2 rounded-lg border border-border/80 bg-panel/60 p-4 transition-all hover:border-accent/40"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-2.5">
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-accent/20 border border-accent/40 text-xs font-bold text-accent font-mono">
                    #{rec.rank}
                  </span>
                  <h4 className="font-semibold text-sm text-text">{rec.headline}</h4>
                </div>
                <span className="text-[11px] font-mono rounded bg-panel px-2 py-0.5 text-muted border border-border">
                  Scenario: {rec.scenario_id}
                </span>
              </div>

              {/* Deltas if any */}
              {rec.deltas && Object.keys(rec.deltas).length > 0 && (
                <div className="flex flex-wrap items-center gap-2 pt-1">
                  {Object.entries(rec.deltas).map(([k, v]) => {
                    const isReduction = v < 0;
                    return (
                      <span
                        key={k}
                        className={`inline-flex items-center gap-1 rounded px-2 py-0.5 text-xs font-mono font-medium ${
                          isReduction
                            ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30"
                            : "bg-warning/15 text-warning border border-warning/30"
                        }`}
                      >
                        <ArrowDownRight className="h-3 w-3" />
                        {k.replace(/_/g, " ")}: {v > 0 ? `+${v.toFixed(1)}` : v.toFixed(1)}
                      </span>
                    );
                  })}
                </div>
              )}

              {/* Confidence note */}
              {rec.confidence_note && (
                <p className="text-xs text-muted font-sans italic">
                  Confidence: {rec.confidence_note}
                </p>
              )}

              {/* Caveat */}
              {rec.caveat && (
                <div className="flex items-start gap-1.5 rounded bg-background/50 p-2 text-[11px] text-muted border border-border/40">
                  <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-warning mt-0.5" />
                  <span>{rec.caveat}</span>
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Key Lessons */}
        {plan.key_lessons && plan.key_lessons.length > 0 && (
          <div className="rounded-lg border border-border/60 bg-panel/40 p-4">
            <div className="flex items-center gap-2 mb-2 text-xs font-semibold uppercase tracking-wider text-muted">
              <BookOpen className="h-3.5 w-3.5 text-accent" /> Key Operational Lessons
            </div>
            <ul className="flex flex-col gap-1.5 pl-4 list-disc text-xs text-text/90">
              {plan.key_lessons.map((lesson, idx) => (
                <li key={idx} className="leading-relaxed">
                  {lesson}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </Card>
  );
}
