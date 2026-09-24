import { useState } from "react";
import { Plus, Trash2, Zap, Play, Layers } from "lucide-react";
import type { Intervention, ScenarioSpec, SimModel, SimulationRequest, Venue } from "../../types";
import { Button, Card } from "../ui/primitives";
import { fmtTime } from "../../lib/format";

interface Props {
  runId: string;
  venue: Venue;
  t0: number;
  onSimulate: (req: SimulationRequest) => void;
  isLoading: boolean;
}

export function InterventionBuilder({ runId, venue, t0, onSimulate, isLoading }: Props) {
  const [model, setModel] = useState<SimModel>("macro");
  const [horizonS, setHorizonS] = useState(60);
  const [scenarios, setScenarios] = useState<ScenarioSpec[]>([
    {
      scenario_id: "baseline",
      name: "Baseline (Do Nothing)",
      interventions: [],
    },
    {
      scenario_id: "open_gate_c",
      name: "Open Gate C",
      interventions: [
        {
          type: "OPEN_PORTAL",
          at_t: t0,
          portal_id: "GATE_C",
        },
      ],
    },
  ]);

  const applyPreset = (presetName: string) => {
    if (presetName === "open_gate_c") {
      setScenarios((prev) => [
        ...prev.filter((s) => s.scenario_id !== "open_gate_c"),
        {
          scenario_id: "open_gate_c",
          name: "Open Gate C",
          interventions: [{ type: "OPEN_PORTAL", at_t: t0, portal_id: "GATE_C" }],
        },
      ]);
    } else if (presetName === "redirect_b") {
      setScenarios((prev) => [
        ...prev.filter((s) => s.scenario_id !== "redirect_b"),
        {
          scenario_id: "redirect_b",
          name: "Redirect from Zone B2",
          interventions: [
            {
              type: "REDIRECT",
              at_t: t0,
              from_zone: "B2",
              to_zone: "C1",
              fraction: 0.5,
            },
          ],
        },
      ]);
    } else if (presetName === "restrict_entry") {
      setScenarios((prev) => [
        ...prev.filter((s) => s.scenario_id !== "restrict_entry"),
        {
          scenario_id: "restrict_entry",
          name: "Restrict Entry 50%",
          interventions: [
            {
              type: "RESTRICT_ENTRY",
              at_t: t0,
              portal_id: "GATE_A",
              fraction: 0.5,
            },
          ],
        },
      ]);
    } else if (presetName === "widen_gate_b") {
      setScenarios((prev) => [
        ...prev.filter((s) => s.scenario_id !== "widen_gate_b"),
        {
          scenario_id: "widen_gate_b",
          name: "Widen Gate B ×1.5",
          interventions: [
            {
              type: "WIDEN_PORTAL",
              at_t: t0,
              portal_id: "GATE_B",
              factor: 1.5,
            },
          ],
        },
      ]);
    } else if (presetName === "all_5") {
      setScenarios([
        { scenario_id: "baseline", name: "Baseline (Do Nothing)", interventions: [] },
        { scenario_id: "open_gate_c", name: "Open Gate C", interventions: [{ type: "OPEN_PORTAL", at_t: t0, portal_id: "GATE_C" }] },
        { scenario_id: "redirect_b", name: "Redirect from Zone B2", interventions: [{ type: "REDIRECT", at_t: t0, from_zone: "B2", to_zone: "C1", fraction: 0.5 }] },
        { scenario_id: "restrict_entry", name: "Restrict Entry 50%", interventions: [{ type: "RESTRICT_ENTRY", at_t: t0, portal_id: "GATE_A", fraction: 0.5 }] },
        { scenario_id: "widen_gate_b", name: "Widen Gate B ×1.5", interventions: [{ type: "WIDEN_PORTAL", at_t: t0, portal_id: "GATE_B", factor: 1.5 }] },
      ]);
    }
  };

  const addScenario = () => {
    const id = `scenario_${Date.now().toString().slice(-4)}`;
    setScenarios((prev) => [
      ...prev,
      {
        scenario_id: id,
        name: `Custom Scenario ${prev.length}`,
        interventions: [
          {
            type: "OPEN_PORTAL",
            at_t: t0,
            portal_id: venue.portals[0]?.portal_id ?? "GATE_C",
          },
        ],
      },
    ]);
  };

  const removeScenario = (id: string) => {
    if (id === "baseline") return; // Keep baseline
    setScenarios((prev) => prev.filter((s) => s.scenario_id !== id));
  };

  const addIntervention = (scenarioId: string) => {
    setScenarios((prev) =>
      prev.map((s) => {
        if (s.scenario_id !== scenarioId) return s;
        return {
          ...s,
          interventions: [
            ...s.interventions,
            {
              type: "OPEN_PORTAL",
              at_t: t0,
              portal_id: venue.portals[0]?.portal_id ?? "GATE_C",
            },
          ],
        };
      })
    );
  };

  const removeIntervention = (scenarioId: string, idx: number) => {
    setScenarios((prev) =>
      prev.map((s) => {
        if (s.scenario_id !== scenarioId) return s;
        return {
          ...s,
          interventions: s.interventions.filter((_, i) => i !== idx),
        };
      })
    );
  };

  const updateIntervention = (scenarioId: string, idx: number, update: Partial<Intervention>) => {
    setScenarios((prev) =>
      prev.map((s) => {
        if (s.scenario_id !== scenarioId) return s;
        const newInvs = [...s.interventions];
        newInvs[idx] = { ...newInvs[idx], ...update };
        return { ...s, interventions: newInvs };
      })
    );
  };

  const handleSubmit = () => {
    onSimulate({
      run_id: runId,
      t0,
      horizon_s: horizonS,
      scenarios,
      seeds: [0, 1, 2],
      model,
    });
  };

  return (
    <Card
      title="Intervention Builder"
      right={
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted">Simulate from t₀ = {fmtTime(t0)}</span>
          <span className="text-xs text-muted">| Horizon:</span>
          <select
            value={horizonS}
            onChange={(e) => setHorizonS(Number(e.target.value))}
            className="rounded border border-border bg-panel px-2 py-0.5 text-xs text-text"
          >
            <option value={30}>30s</option>
            <option value={60}>60s</option>
            <option value={120}>120s</option>
          </select>
        </div>
      }
    >
      <div className="flex flex-col gap-4">
        {/* Preset quick actions */}
        <div className="flex flex-wrap items-center gap-2 border-b border-border pb-3">
          <span className="text-xs font-semibold uppercase tracking-wider text-muted">Presets:</span>
          <button
            type="button"
            onClick={() => applyPreset("open_gate_c")}
            className="flex items-center gap-1 rounded bg-panel px-2.5 py-1 text-xs hover:bg-border transition-colors text-text"
          >
            <Zap className="h-3 w-3 text-warning" /> Open Gate C
          </button>
          <button
            type="button"
            onClick={() => applyPreset("redirect_b")}
            className="flex items-center gap-1 rounded bg-panel px-2.5 py-1 text-xs hover:bg-border transition-colors text-text"
          >
            <Zap className="h-3 w-3 text-warning" /> Redirect from Zone B2
          </button>
          <button
            type="button"
            onClick={() => applyPreset("restrict_entry")}
            className="flex items-center gap-1 rounded bg-panel px-2.5 py-1 text-xs hover:bg-border transition-colors text-text"
          >
            <Zap className="h-3 w-3 text-warning" /> Restrict Entry 50%
          </button>
          <button
            type="button"
            onClick={() => applyPreset("widen_gate_b")}
            className="flex items-center gap-1 rounded bg-panel px-2.5 py-1 text-xs hover:bg-border transition-colors text-text"
          >
            <Zap className="h-3 w-3 text-warning" /> Widen Gate B ×1.5
          </button>
          <button
            type="button"
            onClick={() => applyPreset("all_5")}
            className="flex items-center gap-1 rounded bg-accent/20 border border-accent/40 px-2.5 py-1 text-xs hover:bg-accent/30 transition-colors text-accent font-medium ml-auto"
          >
            <Layers className="h-3 w-3" /> Load 5-Scenario Suite
          </button>
        </div>

        {/* Scenarios list */}
        <div className="flex flex-col gap-3">
          {scenarios.map((scenario) => {
            const isBaseline = scenario.scenario_id === "baseline";
            return (
              <div
                key={scenario.scenario_id}
                className={`rounded border p-3 ${
                  isBaseline ? "border-border/60 bg-panel/50" : "border-border bg-panel"
                }`}
              >
                <div className="flex items-center justify-between gap-3 mb-2">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-sm text-text">{scenario.name}</span>
                    <span className="text-xs text-muted font-mono">[{scenario.scenario_id}]</span>
                  </div>
                  {!isBaseline && (
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => addIntervention(scenario.scenario_id)}
                        className="flex items-center gap-1 text-xs text-accent hover:underline"
                      >
                        <Plus className="h-3 w-3" /> Add Action
                      </button>
                      <button
                        type="button"
                        onClick={() => removeScenario(scenario.scenario_id)}
                        className="text-muted hover:text-danger p-1"
                        title="Delete scenario"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  )}
                </div>

                {isBaseline ? (
                  <p className="text-xs text-muted italic">
                    Unmodified trajectory: crowd continues on observed path without intervention.
                  </p>
                ) : scenario.interventions.length === 0 ? (
                  <p className="text-xs text-muted italic">No interventions added yet.</p>
                ) : (
                  <div className="flex flex-col gap-2 pt-1">
                    {scenario.interventions.map((inv, idx) => (
                      <div
                        key={idx}
                        className="flex flex-wrap items-center gap-2 rounded bg-background/60 p-2 text-xs border border-border/40"
                      >
                        <span className="font-mono text-muted text-[11px]">#{idx + 1}</span>
                        {/* Intervention Type */}
                        <select
                          value={inv.type}
                          onChange={(e) =>
                            updateIntervention(scenario.scenario_id, idx, {
                              type: e.target.value as Intervention["type"],
                            })
                          }
                          className="rounded border border-border bg-panel px-2 py-1 text-xs text-text"
                        >
                          <option value="OPEN_PORTAL">Open Portal</option>
                          <option value="CLOSE_PORTAL">Close Portal</option>
                          <option value="REDIRECT">Redirect Flow</option>
                          <option value="RESTRICT_ENTRY">Restrict Entry</option>
                          <option value="WIDEN_PORTAL">Widen Portal</option>
                        </select>

                        {/* Portal / Zone parameters */}
                        {inv.type === "OPEN_PORTAL" || inv.type === "CLOSE_PORTAL" || inv.type === "RESTRICT_ENTRY" || inv.type === "WIDEN_PORTAL" ? (
                          <select
                            value={inv.portal_id ?? ""}
                            onChange={(e) =>
                              updateIntervention(scenario.scenario_id, idx, { portal_id: e.target.value })
                            }
                            className="rounded border border-border bg-panel px-2 py-1 text-xs text-text"
                          >
                            <option value="">Select Portal...</option>
                            {venue.portals.map((p) => (
                              <option key={p.portal_id} value={p.portal_id}>
                                {p.portal_id} ({p.from_zone} → {p.to_zone}, {p.width_m}m)
                              </option>
                            ))}
                          </select>
                        ) : null}

                        {inv.type === "REDIRECT" && (
                          <div className="flex items-center gap-1.5">
                            <select
                              value={inv.from_zone ?? ""}
                              onChange={(e) =>
                                updateIntervention(scenario.scenario_id, idx, { from_zone: e.target.value })
                              }
                              className="rounded border border-border bg-panel px-2 py-1 text-xs text-text"
                            >
                              <option value="">From Zone...</option>
                              {venue.zones.map((z) => (
                                <option key={z.zone_id} value={z.zone_id}>
                                  Zone {z.zone_id}
                                </option>
                              ))}
                            </select>
                            <span className="text-muted">→</span>
                            <select
                              value={inv.to_zone ?? ""}
                              onChange={(e) =>
                                updateIntervention(scenario.scenario_id, idx, { to_zone: e.target.value })
                              }
                              className="rounded border border-border bg-panel px-2 py-1 text-xs text-text"
                            >
                              <option value="">Via/To Zone...</option>
                              {venue.zones.map((z) => (
                                <option key={z.zone_id} value={z.zone_id}>
                                  Zone {z.zone_id}
                                </option>
                              ))}
                            </select>
                          </div>
                        )}

                        {/* Modifiers: fraction or factor */}
                        {(inv.type === "REDIRECT" || inv.type === "RESTRICT_ENTRY") && (
                          <div className="flex items-center gap-1">
                            <span className="text-muted">Fraction:</span>
                            <input
                              type="number"
                              min={0.1}
                              max={1.0}
                              step={0.1}
                              value={inv.fraction ?? 0.5}
                              onChange={(e) =>
                                updateIntervention(scenario.scenario_id, idx, {
                                  fraction: parseFloat(e.target.value),
                                })
                              }
                              className="w-16 rounded border border-border bg-panel px-1.5 py-0.5 text-xs text-text"
                            />
                          </div>
                        )}

                        {inv.type === "WIDEN_PORTAL" && (
                          <div className="flex items-center gap-1">
                            <span className="text-muted">Factor:</span>
                            <input
                              type="number"
                              min={1.1}
                              max={3.0}
                              step={0.1}
                              value={inv.factor ?? 1.5}
                              onChange={(e) =>
                                updateIntervention(scenario.scenario_id, idx, {
                                  factor: parseFloat(e.target.value),
                                })
                              }
                              className="w-16 rounded border border-border bg-panel px-1.5 py-0.5 text-xs text-text"
                            />
                            <span className="text-muted">×</span>
                          </div>
                        )}

                        {/* Time */}
                        <div className="flex items-center gap-1 ml-auto">
                          <span className="text-muted">at t =</span>
                          <span className="font-mono text-accent">{fmtTime(inv.at_t)}</span>
                        </div>

                        <button
                          type="button"
                          onClick={() => removeIntervention(scenario.scenario_id, idx)}
                          className="text-muted hover:text-danger p-0.5"
                          title="Remove action"
                        >
                          <Trash2 className="h-3 w-3" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Footer controls: Add scenario & Run simulation */}
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border pt-3">
          <Button variant="ghost" onClick={addScenario} className="text-xs">
            <Plus className="h-3.5 w-3.5 mr-1" /> Add Custom Scenario
          </Button>

          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5 text-xs">
              <span className="text-muted">Engine:</span>
              <label className="flex items-center gap-1 cursor-pointer">
                <input
                  type="radio"
                  name="sim_model"
                  value="macro"
                  checked={model === "macro"}
                  onChange={() => setModel("macro")}
                  className="accent-accent"
                />
                <span>Macro (Fast ~1s)</span>
              </label>
              <label className="flex items-center gap-1 cursor-pointer ml-2">
                <input
                  type="radio"
                  name="sim_model"
                  value="social_force"
                  checked={model === "social_force"}
                  onChange={() => setModel("social_force")}
                  className="accent-accent"
                />
                <span>Social Force (Micro)</span>
              </label>
            </div>

            <Button
              onClick={handleSubmit}
              disabled={isLoading || scenarios.length === 0}
              className="bg-accent text-white hover:bg-accent/90 px-4 py-1.5 text-xs font-semibold shadow-sm"
            >
              {isLoading ? (
                "Simulating..."
              ) : (
                <>
                  <Play className="h-3.5 w-3.5 mr-1 fill-current" /> Run Simulation ({scenarios.length} scenarios)
                </>
              )}
            </Button>
          </div>
        </div>
      </div>
    </Card>
  );
}
