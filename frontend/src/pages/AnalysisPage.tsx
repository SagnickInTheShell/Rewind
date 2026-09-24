import { useEffect, useMemo } from "react";
import { Link } from "react-router-dom";
import { useHealth, useRisk, useRun, useTimeline, useVenue, useFeatures } from "../api/hooks";
import { useSession, useTimeStore } from "../store";
import { VideoPlayer } from "../components/video/VideoPlayer";
import { ZoneGrid } from "../components/zones/ZoneGrid";
import { ExplanationPanel } from "../components/explain/ExplanationPanel";
import { RiskChart } from "../components/timeline/RiskChart";
import { EventList } from "../components/timeline/EventList";
import { CausalChain } from "../components/timeline/CausalChain";
import { Card, Empty, RiskBadge } from "../components/ui/primitives";
import { RunInfo } from "../components/ui/RunInfo";
import { valueAt } from "../lib/series";
import { fmtTime } from "../lib/format";
import type { IncidentEvent } from "../types";

export default function AnalysisPage() {
  const runId = useSession((s) => s.runId);
  const { data: run } = useRun(runId, true);
  const { data: venue } = useVenue(run?.venue_id);
  const ready = run?.status === "DONE";
  const { data: risk } = useRisk(ready ? runId : null);
  const { data: timeline } = useTimeline(ready ? runId : null);
  const { data: features } = useFeatures(ready ? runId : null);
  const { data: health } = useHealth();
  const { currentTime, selectedZone, hoverZone, selectedEventId, selectZone, setHoverZone, selectEvent, setTime, setDuration } =
    useTimeStore();

  useEffect(() => {
    // the run metadata knows the duration even before the browser has loaded the video
    if (run) setDuration(run.video.duration_s);
  }, [run, setDuration]);

  const g = risk?.global_risk ?? [];
  const now = valueAt(g, currentTime, (p) => p.t);
  const explainZone = selectedZone ?? now?.worst_zone ?? null;

  useEffect(() => {
    // start on the first escalation so the first view is meaningful
    if (timeline && currentTime === 0 && timeline.origin_time != null) setTime(Math.max(0, timeline.origin_time - 5), "event");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [timeline]);

  const onEvent = (e: IncidentEvent) => selectEvent(e.event_id, e.t_start, e.zone_id);
  const shapAvailable = Boolean(health?.models?.xgb);
  const riskZones = useMemo(() => risk?.zones ?? [], [risk]);

  if (!runId) {
    return (
      <Empty>
        <div className="flex flex-col items-center gap-3">
          <p>No run selected.</p>
          <Link to="/" className="text-accent underline">
            Upload footage or load the demo
          </Link>
        </div>
      </Empty>
    );
  }
  if (!run || !venue) return <Empty>Loading run…</Empty>;
  if (!ready) return <Empty>Analysis is {run.status.toLowerCase()}… progress is shown on the Upload page.</Empty>;

  return (
    <div className="flex flex-col gap-4 p-4">
      <div className="flex items-center gap-3">
        <h1 className="text-2xl font-semibold">This is what happened</h1>
        {now && (
          <RiskBadge state={now.state} large title={`Worst zone ${now.worst_zone} · ensemble score ${now.max_score.toFixed(2)}`} />
        )}
        <span className="text-muted">{run.video.filename}</span>
        <div className="ml-auto max-w-[55%]">
          <RunInfo run={run} />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[3fr_2fr]">
        <Card title="Footage with analysis overlay">
          <VideoPlayer runId={run.run_id} videoId={run.video.video_id} synthetic={run.video.synthetic} />
        </Card>
        <div className="flex min-w-0 flex-col gap-4">
          <Card title="Zones" right={<span className="text-xs text-muted">click a zone to explain it</span>}>
            <ZoneGrid
              venue={venue}
              risk={riskZones}
              features={features}
              t={currentTime}
              selectedZone={explainZone}
              onSelect={(z) => selectZone(z === selectedZone ? null : z)}
              onHover={setHoverZone}
            />
          </Card>
          <ExplanationPanel runId={run.run_id} t={currentTime} zone={explainZone} shapAvailable={shapAvailable} />
        </div>
      </div>

      <Card
        title="Risk timeline"
        right={
          <span className="text-xs text-muted">
            Worst-zone ensemble score · hover a zone to overlay it · click to seek · {fmtTime(currentTime)}
          </span>
        }
      >
        <RiskChart
          global={g}
          zones={riskZones}
          hoverZone={hoverZone ?? selectedZone}
          events={timeline?.events ?? []}
          currentTime={currentTime}
          onSeek={(t) => setTime(t, "chart")}
          height={240}
        />
      </Card>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[2fr_3fr]">
        <Card title="Causal chain (origin → peak)">
          {timeline && (
            <div className="flex flex-col gap-3">
              <p className="text-[15px] leading-relaxed">{timeline.summary}</p>
              <CausalChain events={timeline.events} chain={timeline.chain} onSelect={onEvent} />
            </div>
          )}
        </Card>
        <Card title={`Events (${timeline?.events.length ?? 0})`}>
          <div className="max-h-80 overflow-auto">
            {timeline && (
              <EventList events={timeline.events} chain={timeline.chain} selectedId={selectedEventId} onSelect={onEvent} />
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}
