import { act } from "@testing-library/react";
import { clampTime, useTimeStore } from "../src/store";
import { applyProgress, type JobProgressState } from "../src/api/useJobProgress";
import { ANALYSIS_STAGES, stageStatuses } from "../src/components/ui/JobStages";
import { indexAtOrBefore, valueAt, groupBy } from "../src/lib/series";
import { fitFrame } from "../src/components/video/OverlayRenderer";
import { pairsComplete } from "../src/components/ui/CalibrationHelper";
import { quantise } from "../src/api/hooks";

describe("shared time store", () => {
  beforeEach(() => {
    useTimeStore.setState({ currentTime: 0, duration: 100, seekNonce: 0, source: "video", selectedZone: null });
  });

  it("video ticks update time without triggering a seek", () => {
    act(() => useTimeStore.getState().setTime(12.5, "video"));
    const s = useTimeStore.getState();
    expect(s.currentTime).toBe(12.5);
    expect(s.seekNonce).toBe(0);
  });

  it("chart / event seeks bump the seek nonce so the video follows", () => {
    act(() => useTimeStore.getState().setTime(40, "chart"));
    expect(useTimeStore.getState().seekNonce).toBe(1);
    act(() => useTimeStore.getState().selectEvent("ev_003", 55, "B2"));
    const s = useTimeStore.getState();
    expect(s.currentTime).toBe(55);
    expect(s.selectedZone).toBe("B2");
    expect(s.selectedEventId).toBe("ev_003");
    expect(s.seekNonce).toBe(2);
  });

  it("clamps to [0, duration]", () => {
    expect(clampTime(-5, 100)).toBe(0);
    expect(clampTime(150, 100)).toBe(100);
    expect(clampTime(Number.NaN, 100)).toBe(0);
    act(() => useTimeStore.getState().setTime(500, "scrubber"));
    expect(useTimeStore.getState().currentTime).toBe(100);
  });
});

describe("job progress", () => {
  const init: JobProgressState = { stage: "queued", percent: 0, message: "", eta_s: null, done: false, error: null, history: [], connected: false };

  it("folds events and records stage history", () => {
    let s = applyProgress(init, { stage: "detect", percent: 10, message: "a", eta_s: 20, done: false, error: null });
    s = applyProgress(s, { stage: "heartbeat", percent: -1, message: "", eta_s: null, done: false, error: null });
    s = applyProgress(s, { stage: "density", percent: 45, message: "b", eta_s: 10, done: false, error: null });
    expect(s.history).toEqual(["detect", "density"]);
    expect(s.percent).toBe(45);
    const st = stageStatuses(ANALYSIS_STAGES, s);
    expect(st.slice(0, 4)).toEqual(["done", "done", "active", "pending"]);
    const done = applyProgress(s, { stage: "done", percent: 100, message: "Done", eta_s: 0, done: true, error: null });
    expect(stageStatuses(ANALYSIS_STAGES, done).every((x) => x === "done")).toBe(true);
  });
});

describe("helpers", () => {
  it("binary search on series", () => {
    const xs = [{ t: 1 }, { t: 2 }, { t: 3 }];
    expect(indexAtOrBefore(xs, 0.5, (x) => x.t)).toBe(-1);
    expect(indexAtOrBefore(xs, 2.5, (x) => x.t)).toBe(1);
    expect(valueAt(xs, 99, (x) => x.t)?.t).toBe(3);
    expect(groupBy(xs, (x) => (x.t > 1 ? "b" : "a")).get("b")).toHaveLength(2);
  });

  it("letterbox fit", () => {
    const f = fitFrame(1280, 720, 640, 640);
    expect(f.scale).toBe(0.5);
    expect(f.ox).toBe(0);
    expect(f.oy).toBe(140);
  });

  it("calibration needs 4 complete pairs", () => {
    const p = { image: { x: 1, y: 1 }, world: { x: 0, y: 0 } };
    expect(pairsComplete([p, p, p])).toBe(false);
    expect(pairsComplete([p, p, p, p, { image: p.image, world: null }])).toBe(true);
  });

  it("quantises overlay time to processed frames", () => {
    expect(quantise(1.29)).toBeCloseTo(1.2);
    expect(quantise(1.31)).toBeCloseTo(1.4);
  });
});
