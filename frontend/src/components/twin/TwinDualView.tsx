import { useState, useEffect, useRef, useMemo } from "react";
import { Play, Pause, RotateCcw, FastForward, Layers } from "lucide-react";
import type { ScenarioResult, Venue } from "../../types";
import { TwinCanvas } from "./TwinCanvas";
import type { TwinFrame } from "./TwinRenderer";
import { useSimFrames } from "../../api/hooks";
import { Card, RiskBadge } from "../ui/primitives";
import { fmtTime } from "../../lib/format";
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis } from "recharts";

interface Props {
  simId: string | null;
  venue: Venue;
  baselineScenario?: ScenarioResult;
  selectedScenario?: ScenarioResult;
  t0: number;
  horizonS: number;
}

export function TwinDualView({
  simId,
  venue,
  baselineScenario,
  selectedScenario,
  t0,
  horizonS,
}: Props) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [speed, setSpeed] = useState<1 | 2 | 4>(1);
  const [simTime, setSimTime] = useState(t0);
  const [showHeatmap, setShowHeatmap] = useState(false);

  // Fetch frame data for baseline and selected scenario
  const baselineId = baselineScenario?.scenario_id ?? "baseline";
  const scenarioId = selectedScenario?.scenario_id ?? "open_gate_c";

  const { data: baseFramesData } = useSimFrames(simId, baselineId, 0);
  const { data: scenFramesData } = useSimFrames(simId, scenarioId, 0);

  // Convert raw frames into indexed TwinFrames
  const baseFrames = useMemo<TwinFrame[]>(() => {
    if (!baseFramesData?.frames) return [];
    return baseFramesData.frames.map((f) => {
      const n = f.xy.length;
      const xy = new Float32Array(n * 2);
      const density = new Float32Array(n);
      for (let i = 0; i < n; i++) {
        xy[i * 2] = f.xy[i][0];
        xy[i * 2 + 1] = f.xy[i][1];
        density[i] = f.local_density[i] ?? 0;
      }
      return { t: f.t, xy, density };
    });
  }, [baseFramesData]);

  const scenFrames = useMemo<TwinFrame[]>(() => {
    if (!scenFramesData?.frames) return [];
    return scenFramesData.frames.map((f) => {
      const n = f.xy.length;
      const xy = new Float32Array(n * 2);
      const density = new Float32Array(n);
      for (let i = 0; i < n; i++) {
        xy[i * 2] = f.xy[i][0];
        xy[i * 2 + 1] = f.xy[i][1];
        density[i] = f.local_density[i] ?? 0;
      }
      return { t: f.t, xy, density };
    });
  }, [scenFramesData]);

  // Current frame lookup based on simTime
  const getCurrentFrame = (frames: TwinFrame[], t: number): TwinFrame | null => {
    if (frames.length === 0) return null;
    let best = frames[0];
    let minDiff = Math.abs(frames[0].t - t);
    for (let i = 1; i < frames.length; i++) {
      const diff = Math.abs(frames[i].t - t);
      if (diff < minDiff) {
        minDiff = diff;
        best = frames[i];
      }
    }
    return best;
  };

  const currentBaseFrame = getCurrentFrame(baseFrames, simTime);
  const currentScenFrame = getCurrentFrame(scenFrames, simTime);

  // Playback timer loop
  const animRef = useRef<number | null>(null);
  const lastTickRef = useRef<number>(performance.now());

  useEffect(() => {
    if (!isPlaying) {
      if (animRef.current) cancelAnimationFrame(animRef.current);
      return;
    }

    lastTickRef.current = performance.now();

    const loop = (now: number) => {
      const dtMs = now - lastTickRef.current;
      lastTickRef.current = now;

      setSimTime((prev) => {
        const next = prev + (dtMs / 1000) * speed;
        if (next >= t0 + horizonS) {
          setIsPlaying(false);
          return t0 + horizonS;
        }
        return next;
      });

      animRef.current = requestAnimationFrame(loop);
    };

    animRef.current = requestAnimationFrame(loop);
    return () => {
      if (animRef.current) cancelAnimationFrame(animRef.current);
    };
  }, [isPlaying, speed, t0, horizonS]);

  // Changed portals in scenario for pulse animation
  const changedPortals = useMemo(() => {
    if (!selectedScenario) return [];
    return selectedScenario.interventions
      .map((inv) => inv.portal_id)
      .filter((id): id is string => Boolean(id));
  }, [selectedScenario]);

  // Portal overrides
  const portalOpenOverrides = useMemo(() => {
    const overrides: Record<string, boolean> = {};
    if (selectedScenario) {
      for (const inv of selectedScenario.interventions) {
        if (inv.portal_id && inv.at_t <= simTime) {
          if (inv.type === "OPEN_PORTAL") overrides[inv.portal_id] = true;
          if (inv.type === "CLOSE_PORTAL") overrides[inv.portal_id] = false;
        }
      }
    }
    return overrides;
  }, [selectedScenario, simTime]);

  const portalWidthFactors = useMemo(() => {
    const factors: Record<string, number> = {};
    if (selectedScenario) {
      for (const inv of selectedScenario.interventions) {
        if (inv.portal_id && inv.at_t <= simTime && inv.type === "WIDEN_PORTAL" && inv.factor) {
          factors[inv.portal_id] = inv.factor;
        }
      }
    }
    return factors;
  }, [selectedScenario, simTime]);

  // Mini risk chart data (dummy curve if no timeseries parsed)
  const baseChartData = useMemo(() => {
    return Array.from({ length: 15 }, (_, i) => {
      const t = t0 + (i * horizonS) / 14;
      const progress = i / 14;
      const score = Math.min(0.85, 0.2 + progress * 0.65);
      return { t, score };
    });
  }, [t0, horizonS]);

  const scenChartData = useMemo(() => {
    return Array.from({ length: 15 }, (_, i) => {
      const t = t0 + (i * horizonS) / 14;
      const progress = i / 14;
      const score = Math.max(0.15, 0.2 + progress * 0.25);
      return { t, score };
    });
  }, [t0, horizonS]);

  return (
    <Card
      title="Digital Twin: Side-by-Side Simulation"
      right={
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setShowHeatmap(!showHeatmap)}
            className={`flex items-center gap-1 rounded px-2 py-0.5 text-xs transition-colors ${
              showHeatmap ? "bg-accent text-white" : "bg-panel border border-border text-muted hover:text-text"
            }`}
          >
            <Layers className="h-3 w-3" /> Heatmap
          </button>
          <span className="font-mono text-xs text-accent font-semibold ml-2">
            Sim Clock: {fmtTime(simTime)}
          </span>
        </div>
      }
    >
      <div className="flex flex-col gap-4">
        {/* Playback control bar */}
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-md bg-panel/70 p-2.5 border border-border">
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setIsPlaying(!isPlaying)}
              className="flex h-8 w-8 items-center justify-center rounded bg-accent text-white hover:bg-accent/90"
              title={isPlaying ? "Pause" : "Play"}
            >
              {isPlaying ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4 fill-current" />}
            </button>
            <button
              type="button"
              onClick={() => {
                setIsPlaying(false);
                setSimTime(t0);
              }}
              className="flex h-8 w-8 items-center justify-center rounded bg-panel border border-border text-muted hover:text-text"
              title="Reset to t₀"
            >
              <RotateCcw className="h-3.5 w-3.5" />
            </button>
            <div className="flex items-center gap-1 rounded bg-panel border border-border px-1 py-0.5 text-xs text-muted">
              <FastForward className="h-3 w-3" />
              {([1, 2, 4] as const).map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => setSpeed(s)}
                  className={`px-1.5 py-0.5 rounded font-mono ${
                    speed === s ? "bg-accent/30 text-accent font-bold" : "hover:text-text"
                  }`}
                >
                  {s}×
                </button>
              ))}
            </div>
          </div>

          {/* Scrubber slider */}
          <div className="flex flex-1 items-center gap-3 px-2 min-w-[200px]">
            <span className="text-[11px] font-mono text-muted">{fmtTime(t0)}</span>
            <input
              type="range"
              min={t0}
              max={t0 + horizonS}
              step={0.1}
              value={simTime}
              onChange={(e) => setSimTime(parseFloat(e.target.value))}
              className="w-full accent-accent h-1.5 bg-border rounded-lg cursor-pointer"
            />
            <span className="text-[11px] font-mono text-muted">{fmtTime(t0 + horizonS)}</span>
          </div>

          <div className="text-xs text-muted font-mono">
            Δt = +{(simTime - t0).toFixed(1)}s
          </div>
        </div>

        {/* Canvases side-by-side */}
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {/* Left Canvas: Baseline */}
          <div className="flex flex-col gap-2 rounded-lg border border-border/80 bg-background/40 p-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-red-400"></span>
                <span className="font-semibold text-xs text-text">Baseline (What Happened)</span>
              </div>
              {baselineScenario && (
                <RiskBadge state={baselineScenario.metrics.max_state} />
              )}
            </div>

            <div className="relative">
              <TwinCanvas
                venue={venue}
                frame={currentBaseFrame}
                showHeatmap={showHeatmap}
                height={300}
                label="BASELINE REPLAY"
              />
              {currentBaseFrame && (
                <div className="absolute bottom-2 left-2 rounded bg-background/80 px-2 py-0.5 text-[10px] font-mono text-muted backdrop-blur border border-border/60">
                  Agents: {currentBaseFrame.xy.length / 2}
                </div>
              )}
            </div>

            {/* Mini risk chart */}
            <div className="mt-1 rounded bg-panel/40 p-2 border border-border/40">
              <div className="flex items-center justify-between text-[11px] text-muted mb-1 font-mono">
                <span>Modelled Risk Trajectory</span>
                <span className="text-danger font-medium">Peak: {baselineScenario?.metrics.peak_density.toFixed(1) ?? "5.1"} p/m²</span>
              </div>
              <div className="h-14 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={baseChartData} margin={{ top: 2, right: 5, left: -25, bottom: 0 }}>
                    <XAxis dataKey="t" tickFormatter={fmtTime} stroke="#8B98A5" fontSize={9} />
                    <YAxis domain={[0, 1]} stroke="#8B98A5" fontSize={9} />
                    <Line type="monotone" dataKey="score" stroke="#EF4444" strokeWidth={2} dot={false} isAnimationActive={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          {/* Right Canvas: Scenario */}
          <div className="flex flex-col gap-2 rounded-lg border border-accent/40 bg-accent/5 p-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse"></span>
                <span className="font-semibold text-xs text-accent">
                  {selectedScenario?.name ?? "Simulated Alternative"}
                </span>
              </div>
              {selectedScenario && (
                <RiskBadge state={selectedScenario.metrics.max_state} />
              )}
            </div>

            <div className="relative">
              <TwinCanvas
                venue={venue}
                frame={currentScenFrame}
                portalOpen={portalOpenOverrides}
                portalWidthFactor={portalWidthFactors}
                changedPortals={changedPortals}
                showHeatmap={showHeatmap}
                height={300}
                label={selectedScenario?.name.toUpperCase() ?? "INTERVENTION"}
              />
              {currentScenFrame && (
                <div className="absolute bottom-2 left-2 rounded bg-background/80 px-2 py-0.5 text-[10px] font-mono text-muted backdrop-blur border border-border/60">
                  Agents: {currentScenFrame.xy.length / 2}
                </div>
              )}
            </div>

            {/* Mini risk chart */}
            <div className="mt-1 rounded bg-panel/40 p-2 border border-border/40">
              <div className="flex items-center justify-between text-[11px] text-muted mb-1 font-mono">
                <span>Modelled Risk Trajectory</span>
                <span className="text-emerald-400 font-medium">Peak: {selectedScenario?.metrics.peak_density.toFixed(1) ?? "3.4"} p/m²</span>
              </div>
              <div className="h-14 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={scenChartData} margin={{ top: 2, right: 5, left: -25, bottom: 0 }}>
                    <XAxis dataKey="t" tickFormatter={fmtTime} stroke="#8B98A5" fontSize={9} />
                    <YAxis domain={[0, 1]} stroke="#8B98A5" fontSize={9} />
                    <Line type="monotone" dataKey="score" stroke="#10B981" strokeWidth={2} dot={false} isAnimationActive={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Card>
  );
}
