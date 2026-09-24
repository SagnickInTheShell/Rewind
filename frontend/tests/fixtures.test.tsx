import { render, screen } from "@testing-library/react";
import { EventList } from "../src/components/timeline/EventList";
import { CausalChain } from "../src/components/timeline/CausalChain";
import { RiskChart } from "../src/components/timeline/RiskChart";
import { TwinCanvas } from "../src/components/twin/TwinCanvas";
import { fakeAgentFrames, fakeRisk, fakeTimeline, fakeVenue } from "../src/lib/fixtures";
import { agentFrameToTwin, fitTransform } from "../src/components/twin/TwinRenderer";

describe("fixture rendering", () => {
  it("renders the event list and causal chain from the fixture timeline", () => {
    const tl = fakeTimeline();
    render(
      <>
        <EventList events={tl.events} chain={tl.chain} />
        <CausalChain events={tl.events} chain={tl.chain} />
      </>,
    );
    expect(screen.getByText("Bottleneck detected at Gate B")).toBeInTheDocument();
    expect(screen.getByTestId("causal-chain")).toHaveTextContent("origin");
  });

  it("renders the risk chart container", () => {
    const r = fakeRisk();
    render(<RiskChart global={r.global_risk} />);
    expect(screen.getByTestId("risk-chart")).toBeInTheDocument();
  });

  it("renders the twin canvas without a 2D context", () => {
    const f = agentFrameToTwin(fakeAgentFrames(1, 10)[0]);
    render(<TwinCanvas venue={fakeVenue()} frame={f} />);
    expect(screen.getByTestId("twin-canvas")).toBeInTheDocument();
  });

  it("fixture risk is bounded and has a global point per second", () => {
    const r = fakeRisk(60);
    expect(r.global_risk).toHaveLength(60);
    for (const p of r.zones) {
      expect(p.ensemble_score).toBeGreaterThanOrEqual(0);
      expect(p.ensemble_score).toBeLessThanOrEqual(1);
    }
  });

  it("fits the venue inside the canvas", () => {
    const tf = fitTransform(fakeVenue(), 600, 400, 20);
    expect(30 * tf.scale).toBeLessThanOrEqual(560 + 1e-6);
    expect(20 * tf.scale).toBeLessThanOrEqual(360 + 1e-6);
  });
});
