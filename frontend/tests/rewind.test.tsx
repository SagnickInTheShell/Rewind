import { render, screen } from "@testing-library/react";
import { ComparisonTable } from "../src/components/scenarios/ComparisonTable";
import { PreventionPlanCard } from "../src/components/strategy/PreventionPlanCard";
import type { Comparison, PreventionPlan } from "../src/types";

describe("Rewind and Scenario UI components", () => {
  it("renders comparison table with best outcome highlighted", () => {
    const comparison: Comparison = {
      sim_id: "sim_test",
      t0: 30,
      horizon_s: 60,
      validation_verdict: "GOOD",
      rows: [
        {
          scenario_id: "baseline",
          name: "Baseline (Do Nothing)",
          peak_density: 5.2,
          peak_crowd_pressure: 0.045,
          time_in_high_s: 18,
          time_in_critical_s: 12,
          max_state: "CRITICAL",
          seed_std: { peak_density: 0.3 },
          is_best: false,
          risk_series: [],
        },
        {
          scenario_id: "open_gate_c",
          name: "Open Gate C",
          peak_density: 3.1,
          peak_crowd_pressure: 0.012,
          time_in_high_s: 4,
          time_in_critical_s: 0,
          max_state: "MEDIUM",
          seed_std: { peak_density: 0.2 },
          is_best: true,
          risk_series: [],
        },
      ],
    };

    render(
      <ComparisonTable
        comparison={comparison}
        selectedScenarioId="open_gate_c"
        onSelectScenario={() => {}}
      />
    );

    expect(screen.getByText("Scenario Comparison")).toBeInTheDocument();
    expect(screen.getByText("Open Gate C")).toBeInTheDocument();
    expect(screen.getByText("Best Outcome")).toBeInTheDocument();
    expect(screen.getByText("Recommended: Open Gate C")).toBeInTheDocument();
  });

  it("renders prevention plan card with caveat and ethical notice", () => {
    const plan: PreventionPlan = {
      run_id: "demo",
      recommendations: [
        {
          rank: 1,
          scenario_id: "open_gate_c",
          headline: "Opening Gate C at 12:35 lowered modelled peak risk from CRITICAL to MEDIUM",
          deltas: { peak_density: -2.1, time_in_critical: -12.0 },
          confidence_note: "High consistency across 3 simulator seeds (std < 0.25 p/m²).",
          caveat: "Simulation output under modelled assumptions. Not a guarantee of real-world outcomes.",
        },
      ],
      key_lessons: ["Early portal opening relieves downstream corridor pressure before turbulence onset."],
    };

    render(<PreventionPlanCard plan={plan} />);

    expect(screen.getByText("Prevention Plan & Recommendations")).toBeInTheDocument();
    expect(
      screen.getByText("Opening Gate C at 12:35 lowered modelled peak risk from CRITICAL to MEDIUM")
    ).toBeInTheDocument();
    expect(
      screen.getByText("Simulation output under modelled assumptions. Not a guarantee of real-world outcomes.")
    ).toBeInTheDocument();
  });
});
