import { NavLink, useNavigate } from "react-router-dom";
import { PlayCircle, Rewind } from "lucide-react";
import { api } from "../../api/client";
import { useRisk, useRun } from "../../api/hooks";
import { useSession, useTimeStore } from "../../store";
import { valueAt } from "../../lib/series";
import { RiskBadge } from "./primitives";

const links = [
  { to: "/", label: "Upload" },
  { to: "/analysis", label: "What happened" },
  { to: "/rewind", label: "Simulate the alternative" },
];

export function TopBar() {
  const navigate = useNavigate();
  const { runId, setRun, setSim } = useSession();
  const { data: run } = useRun(runId);
  const { data: risk } = useRisk(run?.status === "DONE" ? runId : null);
  const t = useTimeStore((s) => s.currentTime);
  const setTime = useTimeStore((s) => s.setTime);
  const now = risk ? valueAt(risk.global_risk, t, (p) => p.t) : undefined;

  const demo = async () => {
    try {
      const d = await api.loadDemo();
      setRun(d.run.run_id);
      if (d.sim_id) setSim(d.sim_id);
      setTime(0, "event");
      navigate("/analysis");
    } catch {
      navigate("/");
    }
  };

  return (
    <header className="flex h-14 shrink-0 items-center gap-6 border-b border-border bg-panel px-5">
      <div className="flex items-center gap-2">
        <Rewind className="h-6 w-6 text-accent" aria-hidden />
        <span className="text-lg font-bold tracking-[0.2em]">REWIND</span>
      </div>
      <nav className="flex gap-1">
        {links.map((l) => (
          <NavLink
            key={l.to}
            to={l.to}
            end={l.to === "/"}
            className={({ isActive }) =>
              `rounded px-3 py-1.5 text-sm ${isActive ? "bg-border text-text" : "text-muted hover:text-text"}`
            }
          >
            {l.label}
          </NavLink>
        ))}
      </nav>
      <div className="ml-auto flex items-center gap-3">
        {run && (
          <span className="max-w-xs truncate text-sm text-muted" title={run.run_id}>
            {run.video.filename}
            {run.video.synthetic ? " · synthetic" : ""}
          </span>
        )}
        {now && <RiskBadge state={now.state} title={`Global modelled risk at this moment (worst zone ${now.worst_zone})`} />}
        <button onClick={demo} className="flex items-center gap-1 rounded border border-border px-2 py-1 text-sm hover:bg-border">
          <PlayCircle className="h-4 w-4" /> Demo
        </button>
      </div>
    </header>
  );
}
