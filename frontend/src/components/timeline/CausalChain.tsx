import { ChevronRight } from "lucide-react";
import type { IncidentEvent } from "../../types";
import { riskColor } from "../../lib/colors";
import { fmtTime } from "../../lib/format";

interface Props {
  events: IncidentEvent[];
  chain: string[];
  onSelect?: (e: IncidentEvent) => void;
}

/** Main causal chain as connected chips, origin → peak. */
export function CausalChain({ events, chain, onSelect }: Props) {
  const byId = new Map(events.map((e) => [e.event_id, e]));
  const items = chain.map((id) => byId.get(id)).filter((e): e is IncidentEvent => !!e);
  if (!items.length) return <div className="text-sm text-muted">No causal chain identified.</div>;
  return (
    <div className="flex flex-wrap items-center gap-1" data-testid="causal-chain">
      {items.map((e, i) => (
        <div key={e.event_id} className="flex items-center gap-1">
          {i > 0 && <ChevronRight className="h-4 w-4 text-muted" aria-hidden />}
          <button
            onClick={() => onSelect?.(e)}
            className="rounded border px-2 py-1 text-left text-xs hover:bg-border"
            style={{ borderColor: `${riskColor(e.severity)}88` }}
          >
            <span className="num mr-1 text-muted">{fmtTime(e.t_start)}</span>
            <span className="font-medium">{e.type.replace(/_/g, " ").toLowerCase()}</span>
            <span className="ml-1 text-muted">{e.zone_id}</span>
            {i === 0 && <span className="ml-1 text-accent">origin</span>}
          </button>
        </div>
      ))}
    </div>
  );
}
