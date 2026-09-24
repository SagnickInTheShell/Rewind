import { NavLink } from "react-router-dom";
import { Rewind } from "lucide-react";

const links = [
  { to: "/", label: "Upload" },
  { to: "/analysis", label: "What happened" },
  { to: "/rewind", label: "Simulate the alternative" },
];

export function TopBar() {
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
      <div className="ml-auto text-sm text-muted">Reconstruct the past. Simulate the alternative.</div>
    </header>
  );
}
