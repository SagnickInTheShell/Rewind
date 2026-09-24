import { CheckCircle2, Circle, Loader2, XCircle } from "lucide-react";
import type { JobProgressState } from "../../api/useJobProgress";
import { fmtTime } from "../../lib/format";

export const ANALYSIS_STAGES: [string, string][] = [
  ["detect", "Detecting people"],
  ["track", "Tracking"],
  ["density", "Density"],
  ["motion", "Motion"],
  ["features", "Features"],
  ["risk", "Risk"],
  ["reconstruction", "Reconstruction"],
];

export type StageStatus = "pending" | "active" | "done" | "failed";

/** Status of each stage given the progress state (pure; unit-tested). */
export function stageStatuses(stages: [string, string][], p: JobProgressState): StageStatus[] {
  const idx = stages.findIndex(([k]) => k === p.stage);
  const seen = stages.map(([k]) => p.history.includes(k));
  const lastSeen = seen.lastIndexOf(true);
  const current = idx >= 0 ? idx : lastSeen;
  return stages.map((_, i) => {
    if (p.done) return "done";
    if (p.error && i === current) return "failed";
    if (i < current) return "done";
    if (i === current) return "active";
    return "pending";
  });
}

export function JobStages({ progress, stages = ANALYSIS_STAGES }: { progress: JobProgressState; stages?: [string, string][] }) {
  const statuses = stageStatuses(stages, progress);
  return (
    <div className="flex flex-col gap-2" data-testid="job-stages">
      <div className="flex items-center gap-3">
        <div className="h-2 flex-1 overflow-hidden rounded bg-border">
          <div className="h-2 bg-accent transition-all" style={{ width: `${progress.percent}%` }} />
        </div>
        <span className="num w-14 text-right">{progress.percent.toFixed(0)}%</span>
        {progress.eta_s != null && !progress.done && <span className="num text-sm text-muted">ETA {fmtTime(progress.eta_s)}</span>}
      </div>
      <ol className="grid grid-cols-1 gap-1 sm:grid-cols-2">
        {stages.map(([k, label], i) => (
          <li key={k} className="flex items-center gap-2 text-sm">
            {statuses[i] === "done" && <CheckCircle2 className="h-4 w-4 text-risk-low" />}
            {statuses[i] === "active" && <Loader2 className="h-4 w-4 animate-spin text-accent" />}
            {statuses[i] === "pending" && <Circle className="h-4 w-4 text-muted" />}
            {statuses[i] === "failed" && <XCircle className="h-4 w-4 text-risk-critical" />}
            <span className={statuses[i] === "pending" ? "text-muted" : ""}>{label}</span>
          </li>
        ))}
      </ol>
      {progress.message && <p className="truncate text-sm text-muted">{progress.message}</p>}
      {progress.error && <p className="text-sm text-risk-critical">{progress.error}</p>}
    </div>
  );
}
