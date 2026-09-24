import { Link } from "react-router-dom";
import { useSession } from "../store";
import { useComparison, usePlan, useValidation, useRun } from "../api/hooks";
import { ComparisonTable } from "../components/scenarios/ComparisonTable";
import { PreventionPlanCard } from "../components/strategy/PreventionPlanCard";
import { ValidationCard } from "../components/validation/ValidationCard";
import { Empty } from "../components/ui/primitives";
import { BarChart3, AlertTriangle } from "lucide-react";

export default function InsightsPage() {
  const { runId, simId } = useSession();
  const effectiveSimId = simId ?? (runId === "demo" ? "sim_demo" : null);
  const { data: run } = useRun(runId);
  const { data: comparison } = useComparison(effectiveSimId);
  const { data: plan } = usePlan(effectiveSimId);
  const { data: validation } = useValidation(runId);

  if (!runId) {
    return (
      <div className="flex-1 bg-[#090D14] text-[#E6EDF3] p-8 overflow-y-auto">
        <Empty>
          <div className="flex flex-col items-center gap-3">
            <p>No active run selected.</p>
            <Link to="/" className="text-[#FF3B5C] underline">
              Return to Home Dashboard
            </Link>
          </div>
        </Empty>
      </div>
    );
  }

  return (
    <div className="flex-1 bg-[#090D14] text-[#E6EDF3] p-8 overflow-y-auto max-w-7xl mx-auto flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-center justify-between pb-2 border-b border-[#1E2633]">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-[#FF3B5C]" />
            <h1 className="text-2xl font-bold tracking-tight text-white">
              Incident Insights & Prevention Strategy
            </h1>
          </div>
          <p className="text-xs text-[#8B98A5]">
            Comprehensive multi-scenario comparative analytics and validated operational recommendations for{" "}
            <span className="font-semibold text-white">{run?.video.filename ?? runId}</span>.
          </p>
        </div>
      </div>

      {/* Comparison Table */}
      <ComparisonTable
        comparison={comparison}
        selectedScenarioId={null}
        onSelectScenario={() => {}}
      />

      {/* Prevention Plan & Validation Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <PreventionPlanCard plan={plan} />
        <ValidationCard validation={validation} />
      </div>

      {/* Ethical Disclaimer */}
      <div className="mt-4 flex items-center justify-center gap-2 rounded-xl border border-[#1E2633] bg-[#0E131C] py-3.5 px-4 text-center text-xs text-[#8B98A5]">
        <AlertTriangle className="h-4 w-4 shrink-0 text-amber-500/80" />
        <span>
          <strong>Ethical Notice:</strong> Simulation output under modelled assumptions. Not a guarantee of
          real-world outcomes. Intended to support, not replace, trained crowd-safety professionals.
        </span>
      </div>
    </div>
  );
}
