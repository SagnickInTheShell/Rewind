import type { IncidentEvent } from "../../types";
import { fmtTime } from "../../lib/format";
import { riskColor } from "../../lib/colors";

interface Props {
  events: IncidentEvent[];
  chain?: string[];
  selectedId?: string | null;
  onSelect?: (e: IncidentEvent) => void;
}

export function EventList({ events, chain = [], selectedId, onSelect }: Props) {
  const onChain = new Set(chain);
  return (
    <ul className="flex flex-col gap-1" data-testid="event-list">
      {events.map((e) => (
        <li key={e.event_id}>
          <button
            onClick={() => onSelect?.(e)}
            className={`flex w-full items-start gap-3 rounded px-2 py-1.5 text-left hover:bg-border ${selectedId === e.event_id ? "bg-border" : ""}`}
          >
            <span className="num w-14 shrink-0 text-sm text-muted">{fmtTime(e.t_start)}</span>
            <span className="mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: riskColor(e.severity) }} />
            <span className="min-w-0 flex-1">
              <span className="block text-sm font-medium">
                {e.title}
                {onChain.has(e.event_id) && <span className="ml-2 text-xs text-accent">causal chain</span>}
              </span>
              <span className="block truncate text-xs text-muted">{e.detail}</span>
            </span>
            <span className="num shrink-0 text-xs text-muted">{e.zone_id}</span>
          </button>
        </li>
      ))}
    </ul>
  );
}
