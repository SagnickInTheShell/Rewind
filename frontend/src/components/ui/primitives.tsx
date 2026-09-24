import type { ButtonHTMLAttributes, ReactNode } from "react";
import { riskColor } from "../../lib/colors";

export function Card({
  title,
  right,
  children,
  className = "",
}: {
  title?: ReactNode;
  right?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`flex min-h-0 flex-col rounded-lg border border-border bg-panel ${className}`}>
      {(title || right) && (
        <header className="flex items-center gap-2 border-b border-border px-4 py-2">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-muted">{title}</h2>
          <div className="ml-auto flex items-center gap-2">{right}</div>
        </header>
      )}
      <div className="min-h-0 flex-1 p-4">{children}</div>
    </section>
  );
}

type Variant = "primary" | "ghost" | "danger";
export function Button({
  variant = "ghost",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  const styles: Record<Variant, string> = {
    primary: "bg-accent text-bg hover:bg-sky-300 font-semibold",
    ghost: "border border-border text-text hover:bg-border",
    danger: "bg-risk-critical text-white hover:bg-red-400 font-semibold",
  };
  return (
    <button
      className={`inline-flex items-center justify-center gap-2 rounded px-3 py-1.5 text-sm transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${styles[variant]} ${className}`}
      {...props}
    />
  );
}

export function RiskBadge({ state, title, large = false }: { state: string; title?: string; large?: boolean }) {
  const c = riskColor(state);
  return (
    <span
      title={title}
      className={`inline-flex items-center gap-1.5 rounded font-semibold ${large ? "px-3 py-1 text-base" : "px-2 py-0.5 text-xs"}`}
      style={{ color: c, background: `${c}22`, border: `1px solid ${c}66` }}
    >
      <span className="h-2 w-2 rounded-full" style={{ background: c }} />
      {state}
    </span>
  );
}

export function Pill({ children, tone = "muted" }: { children: ReactNode; tone?: "muted" | "accent" | "warn" }) {
  const cls = {
    muted: "border-border text-muted",
    accent: "border-accent/50 text-accent",
    warn: "border-risk-medium/50 text-risk-medium",
  }[tone];
  return <span className={`rounded border px-2 py-0.5 text-xs ${cls}`}>{children}</span>;
}

export function Toggle({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label className="inline-flex cursor-pointer select-none items-center gap-1.5 text-sm text-muted">
      <input type="checkbox" className="accent-sky-400" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      {label}
    </label>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="flex h-full items-center justify-center p-6 text-center text-muted">{children}</div>;
}
