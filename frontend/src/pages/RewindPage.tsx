import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { History, AlertTriangle } from "lucide-react";
import { useSession, useTimeStore } from "../store";
import {
  useRun,
  useVenue,
  useTimeline,
  useSimulation,
  useComparison,
  usePlan,
  useValidation,
} from "../api/hooks";
import { api } from "../api/client";
import { Empty } from "../components/ui/primitives";
import { fmtTime } from "../lib/format";
import { InterventionBuilder } from "../components/scenarios/InterventionBuilder";
import { TwinDualView } from "../components/twin/TwinDualView";
import { ComparisonTable } from "../components/scenarios/ComparisonTable";
import { ValidationCard } from "../components/validation/ValidationCard";
import { PreventionPlanCard } from "../components/strategy/PreventionPlanCard";
import type { SimulationRequest } from "../types";

export default function RewindPage() {
  const { runId, simId, setSim } = useSession();
  const { data: run } = useRun(runId, true);
  const { data: venue } = useVenue(run?.venue_id);
  const { data: timeline } = useTimeline(runId);
  const { data: validation } = useValidation(runId);

  // Simulation status & results
  const effectiveSimId = simId ?? (runId === "demo" ? "sim_demo" : null);
  const { data: simStatus, isLoading: simLoading } = useSimulation(effectiveSimId);
  const { data: comparison } = useComparison(effectiveSimId);
  const { data: plan } = usePlan(effectiveSimId);

  // Time state for rewind
  const { currentTime, setTime } = useTimeStore();

  // Selected scenario in comparison table to view in twin
  const [selectedScenarioId, setSelectedScenarioId] = useState<string>("open_gate_c");
  const [isSimulating, setIsSimulating] = useState(false);
  const [isRewinding, setIsRewinding] = useState(false);

  // Recommended t0: origin_time or 20s before first peak
  const defaultT0 = timeline?.origin_time ?? Math.max(0, (run?.video.duration_s ?? 60) * 0.3);
  const [t0, setT0] = useState<number>(defaultT0);

  useEffect(() => {
    if (timeline?.origin_time != null) {
      setT0(Math.round(timeline.origin_time));
    }
  }, [timeline?.origin_time]);

  // Handle the big animated REWIND action
  const handleRewind = () => {
    setIsRewinding(true);
    const start = currentTime;
    const target = t0;
    const durationMs = 800;
    const startTime = performance.now();

    const animate = (now: number) => {
      const elapsed = now - startTime;
      const progress = Math.min(1, elapsed / durationMs);
      // smooth easeOutCubic
      const ease = 1 - Math.pow(1 - progress, 3);
      const current = start + (target - start) * ease;
      setTime(current, "rewind");

      if (progress < 1) {
        requestAnimationFrame(animate);
      } else {
        setTime(target, "rewind");
        setIsRewinding(false);
      }
    };

    requestAnimationFrame(animate);
  };

  // Launch simulation
  const handleSimulate = async (req: SimulationRequest) => {
    try {
      setIsSimulating(true);
      const res = await api.createSimulation(req);
      setSim(res.sim_id);
      setSelectedScenarioId(req.scenarios[1]?.scenario_id ?? "open_gate_c");
    } catch (err) {
      console.error("Simulation request failed", err);
    } finally {
      setIsSimulating(false);
    }
  };

  // Baseline scenario & selected scenario objects
  const baselineScenario = simStatus?.results.find((r) => r.scenario_id === "baseline");
  const selectedScenario =
    simStatus?.results.find((r) => r.scenario_id === selectedScenarioId) ??
    simStatus?.results.find((r) => r.scenario_id !== "baseline") ??
    baselineScenario;

  if (!runId) {
    return (
      <Empty>
        <div className="flex flex-col items-center gap-3">
          <p>No active run selected.</p>
          <Link to="/" className="text-accent underline">
            Upload footage or load the demo
          </Link>
        </div>
      </Empty>
    );
  }

  if (!venue) {
    return <Empty>Loading venue and run metadata…</Empty>;
  }

  return (
    <div className="flex flex-col gap-5 p-4 max-w-7xl mx-auto">
      {/* Top Banner with Rewind Action */}
      <div className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-accent/40 bg-gradient-to-r from-panel via-panel to-accent/10 p-5 shadow-lg">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2">
            <span className="rounded bg-accent/20 px-2 py-0.5 text-xs font-mono font-semibold text-accent uppercase">
              Phase 9 Digital Twin
            </span>
            <span className="text-xs text-muted">Run: {run?.video.filename ?? runId}</span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-text">
            Simulate the Alternative
          </h1>
          <p className="text-xs text-muted max-w-2xl leading-relaxed">
            Rewind to an earlier moment before peak escalation, apply architectural or procedural
            interventions, and simulate alternative crowd dynamics in the digital twin.
          </p>
        </div>

        {/* Big REWIND Button */}
        <div className="flex items-center gap-3">
          <div className="flex flex-col items-end">
            <span className="text-[11px] text-muted">Rewind Target (t₀)</span>
            <div className="flex items-center gap-1">
              <input
                type="number"
                min={0}
                max={run?.video.duration_s ?? 300}
                value={t0}
                onChange={(e) => setT0(Math.max(0, parseFloat(e.target.value) || 0))}
                className="w-16 rounded border border-border bg-panel px-2 py-1 text-center font-mono text-xs text-accent font-bold"
              />
              <span className="text-xs text-muted font-mono">({fmtTime(t0)})</span>
            </div>
          </div>

          <button
            type="button"
            onClick={handleRewind}
            disabled={isRewinding}
            className="flex items-center gap-2 rounded-xl bg-accent px-5 py-3 text-sm font-bold text-white shadow-md hover:bg-accent/90 active:scale-95 transition-all"
          >
            <History className={`h-5 w-5 ${isRewinding ? "animate-spin" : ""}`} />
            <span>REWIND TO t₀</span>
          </button>
        </div>
      </div>

      {/* Intervention Builder */}
      <InterventionBuilder
        runId={runId}
        venue={venue}
        t0={t0}
        onSimulate={handleSimulate}
        isLoading={isSimulating || simLoading}
      />

      {/* Side-by-Side Digital Twin View */}
      <TwinDualView
        simId={effectiveSimId}
        venue={venue}
        baselineScenario={baselineScenario}
        selectedScenario={selectedScenario}
        t0={t0}
        horizonS={simStatus?.request?.horizon_s ?? 60}
      />

      {/* Comparison Table */}
      <ComparisonTable
        comparison={comparison}
        selectedScenarioId={selectedScenarioId}
        onSelectScenario={setSelectedScenarioId}
      />

      {/* Bottom Grid: Validation & Prevention Plan */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <ValidationCard validation={validation} />
        <PreventionPlanCard plan={plan} />
      </div>

      {/* Persistent Ethical Disclaimer (Section 13) */}
      <div className="mt-4 flex items-center justify-center gap-2 rounded-lg border border-border/40 bg-panel/30 py-3 px-4 text-center text-xs text-muted">
        <AlertTriangle className="h-4 w-4 shrink-0 text-warning/80" />
        <span>
          <strong>Ethical Notice:</strong> Simulation output under modelled assumptions. Not a
          guarantee of real-world outcomes. Intended to support, not replace, trained crowd-safety
          professionals.
        </span>
      </div>
    </div>
  );
}
