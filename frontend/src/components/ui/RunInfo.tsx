import { Info } from "lucide-react";
import type { RunMeta } from "../../types";
import { Pill } from "./primitives";

/** Honesty panel: which methods produced this run (Section 10). */
export function RunInfo({ run }: { run: RunMeta }) {
  const m = run.methods;
  const rows: [string, string | undefined][] = [
    ["Detector", m.detector],
    ["Tracker", m.tracker],
    ["Density", m.density === "kde" ? "KDE fallback (no CSRNet weights)" : m.density],
    ["Density basis", m.density_basis],
    ["Calibration", m.calibration],
    ["Calibration fit", m.calibration_fit],
    ["Motion", m.flow],
    ["Risk", m.risk],
    ["Camera", m.camera_view],
  ];
  return (
    <div className="flex flex-col gap-2 text-sm" data-testid="run-info">
      {run.notes.map((n) => (
        <div key={n} className="flex gap-2 rounded border border-risk-medium/40 bg-risk-medium/10 p-2 text-risk-medium">
          <Info className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          <span>{n}</span>
        </div>
      ))}
      <div className="flex flex-wrap gap-1.5">
        {rows
          .filter(([, v]) => v)
          .map(([k, v]) => (
            <Pill key={k}>
              <span className="text-muted">{k}:</span> <span className="text-text">{v}</span>
            </Pill>
          ))}
      </div>
    </div>
  );
}
