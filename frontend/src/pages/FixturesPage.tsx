import { useEffect, useMemo, useState } from "react";
import { Card } from "../components/ui/primitives";
import { RiskChart } from "../components/timeline/RiskChart";
import { EventList } from "../components/timeline/EventList";
import { CausalChain } from "../components/timeline/CausalChain";
import { TwinCanvas } from "../components/twin/TwinCanvas";
import { agentFrameToTwin } from "../components/twin/TwinRenderer";
import { fakeAgentFrames, fakeRisk, fakeTimeline, fakeVenue } from "../lib/fixtures";

/** Developer page: renders every major visual from fixture data (Phase 1 acceptance). */
export default function FixturesPage() {
  const risk = useMemo(() => fakeRisk(), []);
  const timeline = useMemo(() => fakeTimeline(), []);
  const venue = useMemo(() => fakeVenue(), []);
  const frames = useMemo(() => fakeAgentFrames(200, 1500).map(agentFrameToTwin), []);
  const [k, setK] = useState(0);
  useEffect(() => {
    let raf = 0;
    const loop = () => {
      setK((v) => (v + 1) % frames.length);
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [frames.length]);

  return (
    <div className="grid grid-cols-2 gap-4 p-4">
      <Card title="Risk timeline (fixture)">
        <RiskChart global={risk.global_risk} zones={risk.zones} events={timeline.events} hoverZone="B2" currentTime={100} />
      </Card>
      <Card title="Digital twin (fixture)">
        <TwinCanvas venue={venue} frame={frames[k]} changedPortals={["GATE_C"]} portalOpen={{ GATE_C: true }} clockMs={k * 16} label="Fixture" />
      </Card>
      <Card title="Events (fixture)">
        <EventList events={timeline.events} chain={timeline.chain} />
      </Card>
      <Card title="Causal chain (fixture)">
        <CausalChain events={timeline.events} chain={timeline.chain} />
      </Card>
    </div>
  );
}
