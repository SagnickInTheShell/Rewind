import { useExplanation } from "../../api/hooks";
import { ApiError } from "../../api/client";
import { useUiStore } from "../../store";
import { FEATURE_UNITS, fmtNum, fmtTime } from "../../lib/format";
import { riskColor } from "../../lib/colors";
import { Card, Empty, RiskBadge } from "../ui/primitives";

interface Props {
  runId: string;
  t: number;
  zone: string | null;
  shapAvailable: boolean;
}

export function ExplanationPanel({ runId, t, zone, shapAvailable }: Props) {
  const { explainMethod, setExplainMethod } = useUiStore();
  const method = shapAvailable ? explainMethod : "physics";
  const { data, error, isLoading } = useExplanation(runId, t, zone, method);
  const maxAbs = Math.max(1e-6, ...(data?.contributions.map((c) => Math.abs(c.contribution)) ?? [0]));

  return (
    <Card
      title="Why is risk here?"
      right={
        <div className="flex overflow-hidden rounded border border-border text-xs">
          {(["physics", "shap"] as const).map((m) => (
            <button
              key={m}
              disabled={m === "shap" && !shapAvailable}
              title={m === "shap" && !shapAvailable ? "Needs the trained XGBoost model (make train)" : undefined}
              onClick={() => setExplainMethod(m)}
              className={`px-2 py-1 ${method === m ? "bg-border text-text" : "text-muted"} disabled:opacity-40`}
            >
              {m === "physics" ? "Physics weights" : "SHAP (XGBoost)"}
            </button>
          ))}
        </div>
      }
    >
      {isLoading && <Empty>Loading explanation…</Empty>}
      {error && <Empty>{error instanceof ApiError ? error.message : "Explanation unavailable"}</Empty>}
      {data && (
        <div className="flex flex-col gap-3" data-testid="explanation">
          <div className="flex items-center gap-2">
            <span className="text-lg font-semibold">{data.zone_id}</span>
            <RiskBadge state={data.state} />
            <span
              className="num text-sm text-muted"
              title={data.method === "shap" ? "XGBoost escalation probability, explained with SHAP" : "Physics score = Σ weight × normalised feature"}
            >
              {data.method === "shap" ? "ML" : "physics"} score {fmtNum(data.score)} · {fmtTime(data.t)}
            </span>
          </div>
          <p className="text-[15px] leading-relaxed">{data.narrative}</p>
          <ul className="flex flex-col gap-1.5">
            {data.contributions.slice(0, 6).map((c) => (
              <li key={c.feature} className="grid grid-cols-[9rem_1fr_5.5rem] items-center gap-2 text-sm">
                <span className="truncate text-muted" title={c.feature}>
                  {c.label}
                </span>
                <span className="relative h-3 rounded bg-border">
                  <span
                    className="absolute top-0 h-3 rounded"
                    style={{
                      left: c.contribution >= 0 ? 0 : undefined,
                      right: c.contribution < 0 ? 0 : undefined,
                      width: `${(100 * Math.abs(c.contribution)) / maxAbs}%`,
                      background: c.contribution >= 0 ? riskColor(data.state) : "#38BDF8",
                    }}
                  />
                </span>
                <span className="num text-right" title={`contribution ${c.contribution.toFixed(3)}, share ${(100 * c.share).toFixed(0)}%`}>
                  {fmtNum(c.value, c.value < 0.1 ? 3 : 2)} <span className="text-muted">{FEATURE_UNITS[c.feature] ?? ""}</span>
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
}
