import { useState, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  Upload,
  User,
  Maximize2,
  Play,
  Pause,
  Clock,
  Users,
  Activity,
  MapPin,
  AlertTriangle,
  ChevronDown,
  Info,
} from "lucide-react";
import { useSession } from "../store";
import { api } from "../api/client";

interface Milestone {
  time: string;
  seconds: number;
  label: string;
  state: "normal" | "rising" | "bottleneck" | "opposing" | "unstable" | "critical";
}

const MILESTONES: Milestone[] = [
  { time: "12:31", seconds: 751, label: "Crowd enters\nGate B", state: "normal" },
  { time: "12:34", seconds: 754, label: "Density\nincreases", state: "rising" },
  { time: "12:36", seconds: 756, label: "Bottleneck\nforms", state: "bottleneck" },
  { time: "12:37", seconds: 757, label: "Opposing\nmovement", state: "opposing" },
  { time: "12:38", seconds: 758, label: "Flow becomes\nunstable", state: "unstable" },
  { time: "12:39", seconds: 759, label: "Critical state", state: "critical" },
];

export default function HomePage() {
  const navigate = useNavigate();
  const { setRun, setSim } = useSession();
  const [isPlaying, setIsPlaying] = useState(false);
  const [activeMilestoneIndex, setActiveMilestoneIndex] = useState(4); // 12:38 (active in image)
  const [selectedScenario, setSelectedScenario] = useState("open_gate_c");
  const [isSimulating, setIsSimulating] = useState(false);

  // Auto-load demo data on mount if not loaded
  useEffect(() => {
    api.loadDemo().then((res) => {
      setRun(res.run.run_id);
      if (res.sim_id) setSim(res.sim_id);
    }).catch(() => {
      // ignore
    });
  }, [setRun, setSim]);

  // Dynamic simulation outcomes based on chosen scenario
  const scenarioResults: Record<
    string,
    { label: string; peakDensity: number; flowInstability: number; riskState: "Low" | "Medium" | "High" }
  > = {
    open_gate_c: {
      label: "Open Gate C at 12:35",
      peakDensity: 2.1,
      flowInstability: 28,
      riskState: "Low",
    },
    redirect_b: {
      label: "Redirect from Zone B2 at 12:35",
      peakDensity: 2.6,
      flowInstability: 35,
      riskState: "Low",
    },
    restrict_entry: {
      label: "Restrict Entry 50% at 12:35",
      peakDensity: 2.3,
      flowInstability: 31,
      riskState: "Low",
    },
    widen_gate_b: {
      label: "Widen Gate B ×1.5 at 12:35",
      peakDensity: 2.8,
      flowInstability: 42,
      riskState: "Medium",
    },
  };

  const currentResult = scenarioResults[selectedScenario] ?? scenarioResults.open_gate_c;

  const handleRunSimulation = () => {
    setIsSimulating(true);
    setTimeout(() => {
      setIsSimulating(false);
    }, 900);
  };

  return (
    <div className="flex-1 bg-[#090D14] text-[#E6EDF3] p-8 overflow-y-auto">
      {/* Top Header */}
      <div className="flex items-start justify-between mb-8">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight text-white flex items-center gap-2">
            From Footage to{" "}
            <span className="bg-gradient-to-r from-[#FF2A6D] via-[#FF3B5C] to-[#E11D48] bg-clip-text text-transparent drop-shadow-sm">
              Foresight
            </span>
          </h1>
          <p className="text-[#8B98A5] text-sm mt-1 font-normal">
            Understand what happened. Rewind and explore what could have.
          </p>
        </div>

        {/* Top-Right Actions */}
        <div className="flex items-center gap-3">
          <Link
            to="/upload"
            className="flex items-center gap-2 bg-[#17202E] hover:bg-[#202C3D] text-[#E6EDF3] text-sm font-semibold px-4 py-2.5 rounded-xl border border-[#2B3A4F] transition-all shadow-sm"
          >
            <Upload className="w-4 h-4 text-gray-300" />
            <span>Upload Video</span>
          </Link>
          <div className="w-10 h-10 rounded-full bg-[#17202E] border border-[#2B3A4F] flex items-center justify-center text-[#8B98A5] shadow-sm">
            <User className="w-5 h-5 text-gray-300" />
          </div>
        </div>
      </div>

      {/* Main Grid: Left Column (~63%) & Right Column (~37%) */}
      <div className="grid grid-cols-1 xl:grid-cols-[1.65fr_1fr] gap-6">
        {/* LEFT COLUMN: Video Player & Incident Timeline */}
        <div className="flex flex-col gap-6">
          {/* Video Player Card */}
          <div className="relative rounded-2xl bg-[#0F141C] border border-[#1E2633] overflow-hidden shadow-2xl flex flex-col">
            {/* Top Badges */}
            <div className="absolute top-4 left-4 z-20 flex items-center gap-2 bg-[#000000]/70 backdrop-blur-md px-3 py-1.5 rounded-lg border border-white/10 text-xs font-mono text-gray-200">
              <span className="w-2 h-2 rounded-full bg-[#FF3B5C] animate-pulse"></span>
              <span>CCTV_Stadium_01.mp4</span>
            </div>

            <button
              type="button"
              className="absolute top-4 right-4 z-20 p-2 rounded-lg bg-[#000000]/70 backdrop-blur-md border border-white/10 text-gray-300 hover:text-white transition-colors"
              title="Fullscreen"
            >
              <Maximize2 className="w-4 h-4" />
            </button>

            {/* Video Canvas / Visual Frame */}
            <div className="relative aspect-[16/9] w-full overflow-hidden bg-black flex items-center justify-center">
              {/* CCTV Background Image */}
              <img
                src="/stadium_cctv_frame.jpg"
                alt="Stadium CCTV Crowd View"
                className="w-full h-full object-cover"
              />

              {/* Dynamic Heatmap Glow on Floor */}
              <div
                className="absolute inset-0 pointer-events-none mix-blend-screen opacity-75"
                style={{
                  background:
                    "radial-gradient(ellipse 45% 35% at 30% 70%, rgba(255, 30, 0, 0.85) 0%, rgba(255, 110, 0, 0.65) 45%, rgba(255, 215, 0, 0.4) 70%, transparent 100%), radial-gradient(ellipse 35% 30% at 75% 55%, rgba(0, 200, 255, 0.45) 0%, rgba(0, 255, 160, 0.25) 50%, transparent 90%)",
                }}
              />

              {/* Floating Overlay HUD Callout 1: Critical Density (Gate B) */}
              <div
                className="absolute top-[32%] left-[28%] z-10 flex flex-col p-2.5 rounded-xl bg-[#180B10]/90 backdrop-blur-md border border-[#FF3B5C]/80 shadow-lg shadow-red-950/60 min-w-[140px] animate-fade-in cursor-pointer hover:scale-105 transition-transform"
                onClick={() => navigate("/analysis")}
              >
                <div className="flex items-center gap-1.5">
                  <AlertTriangle className="w-3.5 h-3.5 text-[#FF3B5C] shrink-0" />
                  <span className="text-xs font-bold text-white tracking-wide">
                    Critical Density
                  </span>
                </div>
                <div className="text-[11px] text-gray-300 mt-0.5">Gate B</div>
                <div className="text-[10px] font-mono text-gray-400">12:38 PM</div>
              </div>

              {/* Floating Overlay HUD Callout 2: Rising Density (Zone A) */}
              <div
                className="absolute top-[43%] left-[42%] z-10 flex flex-col p-2.5 rounded-xl bg-[#1A140A]/90 backdrop-blur-md border border-[#F59E0B]/80 shadow-lg shadow-amber-950/60 min-w-[130px] animate-fade-in cursor-pointer hover:scale-105 transition-transform"
                onClick={() => navigate("/analysis")}
              >
                <div className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-[#F59E0B]"></span>
                  <span className="text-xs font-bold text-white tracking-wide">
                    Rising Density
                  </span>
                </div>
                <div className="text-[11px] text-gray-300 mt-0.5">Zone A</div>
                <div className="text-[10px] font-mono text-gray-400">12:36 PM</div>
              </div>

              {/* Floating Overlay HUD Callout 3: Normal (Gate C) */}
              <div
                className="absolute top-[34%] right-[37%] z-10 flex flex-col p-2.5 rounded-xl bg-[#09151F]/90 backdrop-blur-md border border-[#0EA5E9]/80 shadow-lg shadow-sky-950/60 min-w-[110px] animate-fade-in cursor-pointer hover:scale-105 transition-transform"
                onClick={() => navigate("/analysis")}
              >
                <div className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-[#0EA5E9]"></span>
                  <span className="text-xs font-bold text-white tracking-wide">
                    Normal
                  </span>
                </div>
                <div className="text-[11px] text-gray-300 mt-0.5">Gate C</div>
                <div className="text-[10px] font-mono text-gray-400">12:34 PM</div>
              </div>
            </div>

            {/* Bottom Video Control Bar */}
            <div className="px-5 py-3.5 bg-[#0C1017] border-t border-[#1E2633] flex items-center justify-between gap-4">
              <button
                type="button"
                onClick={() => setIsPlaying(!isPlaying)}
                className="text-white hover:text-[#FF3B5C] transition-colors p-1"
              >
                {isPlaying ? (
                  <Pause className="w-5 h-5 fill-current" />
                ) : (
                  <Play className="w-5 h-5 fill-current" />
                )}
              </button>

              {/* Progress Scrubber */}
              <div className="flex-1 relative flex items-center">
                <div className="w-full h-1 bg-[#1E2633] rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-[#FF3B5C] via-[#FF4655] to-[#FF5E3A] rounded-full"
                    style={{ width: "84%" }}
                  />
                </div>
                {/* Playhead Dot */}
                <div
                  className="absolute top-1/2 -translate-y-1/2 w-3.5 h-3.5 bg-[#FF3B5C] rounded-full border-2 border-white shadow-md shadow-red-500/50 cursor-pointer"
                  style={{ left: "84%" }}
                />
              </div>

              {/* Timestamp & Speed */}
              <div className="flex items-center gap-3">
                <span className="font-mono text-xs text-gray-300 tracking-wider">
                  12:38 / 15:00
                </span>
                <span className="px-2 py-0.5 rounded bg-[#17202E] border border-[#2B3A4F] text-[11px] font-mono text-gray-300">
                  1x
                </span>
              </div>
            </div>
          </div>

          {/* Incident Timeline Card */}
          <div className="flex flex-col gap-6">
            <h2 className="text-lg font-bold text-white tracking-tight">
              Incident Timeline
            </h2>

            {/* Horizontal Timeline Track */}
            <div className="relative px-4 pt-2 pb-6">
              {/* Segmented Line between milestones */}
              <div className="absolute top-[18px] left-6 right-6 h-1 flex rounded-full overflow-hidden">
                <div className="flex-[3] bg-[#475569]"></div>
                <div className="flex-[2] bg-[#F97316]"></div>
                <div className="flex-[1] bg-[#EA580C]"></div>
                <div className="flex-[1] bg-[#EF4444]"></div>
                <div className="flex-[1] bg-[#DC2626]"></div>
              </div>

              {/* Milestones Nodes */}
              <div className="relative flex justify-between">
                {MILESTONES.map((m, idx) => {
                  const isActive = idx === activeMilestoneIndex;
                  return (
                    <div
                      key={m.time}
                      onClick={() => setActiveMilestoneIndex(idx)}
                      className="flex flex-col items-center cursor-pointer group text-center"
                    >
                      {/* Node Indicator */}
                      <div className="relative flex items-center justify-center w-7 h-7">
                        {isActive ? (
                          <>
                            <div className="absolute inset-0 rounded-full bg-[#FF3B5C]/30 animate-ping"></div>
                            <div className="w-5 h-5 rounded-full border-2 border-[#FF3B5C] bg-[#180B10] flex items-center justify-center z-10 shadow-lg shadow-red-500/50">
                              <div className="w-2.5 h-2.5 rounded-full bg-[#FF3B5C]"></div>
                            </div>
                          </>
                        ) : idx <= 1 ? (
                          <div className="w-3.5 h-3.5 rounded-full bg-[#64748B] group-hover:scale-125 transition-transform z-10"></div>
                        ) : idx === 2 ? (
                          <div className="w-3.5 h-3.5 rounded-full bg-[#F97316] group-hover:scale-125 transition-transform z-10"></div>
                        ) : idx === 3 ? (
                          <div className="w-3.5 h-3.5 rounded-full bg-[#EA580C] group-hover:scale-125 transition-transform z-10"></div>
                        ) : (
                          <div className="w-3.5 h-3.5 rounded-full bg-[#DC2626] group-hover:scale-125 transition-transform z-10"></div>
                        )}
                      </div>

                      {/* Time text */}
                      <span
                        className={`text-xs font-mono font-semibold mt-2.5 ${
                          isActive ? "text-[#FF3B5C]" : "text-gray-300"
                        }`}
                      >
                        {m.time}
                      </span>

                      {/* Label text */}
                      <span className="text-[11px] text-gray-400 mt-1 max-w-[85px] leading-tight whitespace-pre-line group-hover:text-gray-200 transition-colors">
                        {m.label}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>

        {/* RIGHT COLUMN: Incident Summary & Rewind & Simulate */}
        <div className="flex flex-col gap-6">
          {/* Card 1: Incident Summary */}
          <div className="rounded-2xl bg-[#111722] border border-[#1E2633] p-5 shadow-xl flex flex-col gap-5">
            {/* Header */}
            <div className="flex items-center justify-between">
              <h3 className="text-base font-bold text-white tracking-wide">
                Incident Summary
              </h3>
              <span className="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-[#30121A] border border-[#FF3B5C]/40 text-xs font-bold text-[#FF4766]">
                <AlertTriangle className="w-3.5 h-3.5" /> High Risk
              </span>
            </div>

            {/* 4 Metric Badges in a Row */}
            <div className="grid grid-cols-4 gap-2.5">
              {/* Peak Risk Time */}
              <div className="flex flex-col items-center justify-center p-3 rounded-xl bg-[#0D121B] border border-[#1B2330] text-center">
                <div className="w-8 h-8 rounded-full bg-red-500/15 flex items-center justify-center text-[#FF4766] mb-2">
                  <Clock className="w-4 h-4" />
                </div>
                <div className="text-sm font-bold text-white font-mono">12:38 PM</div>
                <div className="text-[10px] text-gray-400 mt-0.5">Peak Risk Time</div>
              </div>

              {/* Max Density */}
              <div className="flex flex-col items-center justify-center p-3 rounded-xl bg-[#0D121B] border border-[#1B2330] text-center">
                <div className="w-8 h-8 rounded-full bg-blue-500/15 flex items-center justify-center text-[#38BDF8] mb-2">
                  <Users className="w-4 h-4" />
                </div>
                <div className="text-sm font-bold text-white font-mono">4.8</div>
                <div className="text-[10px] text-gray-400 mt-0.5">Max Density<br/>(people/m²)</div>
              </div>

              {/* Flow Instability */}
              <div className="flex flex-col items-center justify-center p-3 rounded-xl bg-[#0D121B] border border-[#1B2330] text-center">
                <div className="w-8 h-8 rounded-full bg-purple-500/15 flex items-center justify-center text-[#C084FC] mb-2">
                  <Activity className="w-4 h-4" />
                </div>
                <div className="text-sm font-bold text-white font-mono">72%</div>
                <div className="text-[10px] text-gray-400 mt-0.5">Flow Instability</div>
              </div>

              {/* Critical Zone */}
              <div className="flex flex-col items-center justify-center p-3 rounded-xl bg-[#0D121B] border border-[#1B2330] text-center">
                <div className="w-8 h-8 rounded-full bg-indigo-500/15 flex items-center justify-center text-[#818CF8] mb-2">
                  <MapPin className="w-4 h-4" />
                </div>
                <div className="text-sm font-bold text-white font-mono">Gate B</div>
                <div className="text-[10px] text-gray-400 mt-0.5">Critical Zone</div>
              </div>
            </div>

            {/* Key Factors Progress Bars */}
            <div className="flex flex-col gap-3.5 pt-2">
              <h4 className="text-xs font-semibold uppercase tracking-wider text-gray-300">
                Key Factors
              </h4>

              {/* Factor 1: High Density */}
              <div className="flex items-center gap-3">
                <span className="text-xs text-gray-300 w-36 shrink-0 font-medium">
                  High Density
                </span>
                <div className="flex-1 h-2 bg-[#1B2330] rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-[#FF4766] to-[#EF4444] rounded-full"
                    style={{ width: "92%" }}
                  />
                </div>
                <span className="text-xs font-mono text-gray-300 w-8 text-right font-medium">
                  92%
                </span>
              </div>

              {/* Factor 2: Bottleneck Pressure */}
              <div className="flex items-center gap-3">
                <span className="text-xs text-gray-300 w-36 shrink-0 font-medium">
                  Bottleneck Pressure
                </span>
                <div className="flex-1 h-2 bg-[#1B2330] rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-[#FB923C] to-[#EA580C] rounded-full"
                    style={{ width: "78%" }}
                  />
                </div>
                <span className="text-xs font-mono text-gray-300 w-8 text-right font-medium">
                  78%
                </span>
              </div>

              {/* Factor 3: Opposing Movement */}
              <div className="flex items-center gap-3">
                <span className="text-xs text-gray-300 w-36 shrink-0 font-medium">
                  Opposing Movement
                </span>
                <div className="flex-1 h-2 bg-[#1B2330] rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-[#FBBF24] to-[#F59E0B] rounded-full"
                    style={{ width: "65%" }}
                  />
                </div>
                <span className="text-xs font-mono text-gray-300 w-8 text-right font-medium">
                  65%
                </span>
              </div>

              {/* Factor 4: Velocity Variation */}
              <div className="flex items-center gap-3">
                <span className="text-xs text-gray-300 w-36 shrink-0 font-medium">
                  Velocity Variation
                </span>
                <div className="flex-1 h-2 bg-[#1B2330] rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-[#818CF8] to-[#6366F1] rounded-full"
                    style={{ width: "48%" }}
                  />
                </div>
                <span className="text-xs font-mono text-gray-300 w-8 text-right font-medium">
                  48%
                </span>
              </div>
            </div>
          </div>

          {/* Card 2: Rewind & Simulate */}
          <div className="rounded-2xl bg-[#111722] border border-[#1E2633] p-5 shadow-xl flex flex-col gap-4">
            {/* Header */}
            <div>
              <div className="flex items-center gap-2">
                <span className="text-[#FF3B5C] font-bold text-base flex items-center">
                  ◀◀
                </span>
                <h3 className="text-base font-bold text-white tracking-wide">
                  Rewind & Simulate
                </h3>
              </div>
              <p className="text-xs text-gray-400 mt-1 font-normal">
                What if we opened Gate C earlier?
              </p>
            </div>

            {/* Dropdown Selector */}
            <div className="relative">
              <select
                value={selectedScenario}
                onChange={(e) => setSelectedScenario(e.target.value)}
                className="w-full appearance-none bg-[#0D121B] border border-[#2B3A4F] text-[#E6EDF3] text-sm rounded-xl px-4 py-3 pr-10 focus:outline-none focus:border-[#FF3B5C] transition-colors font-medium cursor-pointer"
              >
                <option value="open_gate_c">Open Gate C at 12:35</option>
                <option value="redirect_b">Redirect from Zone B2 at 12:35</option>
                <option value="restrict_entry">Restrict Entry 50% at 12:35</option>
                <option value="widen_gate_b">Widen Gate B ×1.5 at 12:35</option>
              </select>
              <ChevronDown className="w-4 h-4 text-gray-400 absolute right-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
            </div>

            {/* Run Simulation Button */}
            <button
              type="button"
              onClick={handleRunSimulation}
              disabled={isSimulating}
              className="w-full py-3.5 px-4 rounded-xl font-bold text-sm text-white bg-gradient-to-r from-[#FF2E5D] via-[#FF3B5C] to-[#FF5238] hover:opacity-95 active:scale-[0.99] transition-all flex items-center justify-center gap-2 shadow-lg shadow-red-500/25"
            >
              {isSimulating ? (
                <>
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                  <span>Simulating Alternative...</span>
                </>
              ) : (
                <>
                  <Play className="w-4 h-4 fill-current" />
                  <span>Run Simulation</span>
                </>
              )}
            </button>

            {/* Simulation Result Comparison */}
            <div className="flex flex-col gap-3 pt-1">
              <div className="flex items-center gap-1.5 text-xs text-gray-300 font-semibold">
                <span>Simulation Result</span>
                <Info className="w-3.5 h-3.5 text-gray-500" />
              </div>

              <div className="grid grid-cols-2 gap-3">
                {/* Original Card */}
                <div className="rounded-xl bg-[#160E13] border border-[#FF3B5C]/20 p-3.5 flex flex-col gap-2.5">
                  <div className="text-xs font-bold text-[#FF4766]">Original</div>
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-gray-400">Peak Density</span>
                    <span className="font-mono font-bold text-white">4.8</span>
                  </div>
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-gray-400">Flow Instability</span>
                    <span className="font-mono font-bold text-white">72%</span>
                  </div>
                  <div className="flex items-center justify-between text-xs pt-1">
                    <span className="text-gray-400">Risk Level</span>
                    <span className="px-2 py-0.5 rounded-full bg-[#E11D48] text-[11px] font-bold text-white">
                      Critical
                    </span>
                  </div>
                </div>

                {/* Simulated Card */}
                <div className="rounded-xl bg-[#0B1713] border border-[#10B981]/25 p-3.5 flex flex-col gap-2.5">
                  <div className="text-xs font-bold text-[#10B981]">Simulated</div>
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-gray-400">Peak Density</span>
                    <span className="font-mono font-bold text-white">
                      {currentResult.peakDensity.toFixed(1)}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-gray-400">Flow Instability</span>
                    <span className="font-mono font-bold text-white">
                      {currentResult.flowInstability}%
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-xs pt-1">
                    <span className="text-gray-400">Risk Level</span>
                    <span
                      className={`px-2 py-0.5 rounded-full text-[11px] font-bold text-white ${
                        currentResult.riskState === "Low"
                          ? "bg-[#10B981]"
                          : "bg-[#F59E0B]"
                      }`}
                    >
                      {currentResult.riskState}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
