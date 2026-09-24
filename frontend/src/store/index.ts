import { create } from "zustand";
import { persist } from "zustand/middleware";

/** Which run / simulation the user is looking at (remembered across reloads). */
interface SessionState {
  runId: string | null;
  simId: string | null;
  setRun: (runId: string | null) => void;
  setSim: (simId: string | null) => void;
}

export const useSession = create<SessionState>()(
  persist(
    (set) => ({
      runId: null,
      simId: null,
      setRun: (runId) => set({ runId, simId: null }),
      setSim: (simId) => set({ simId }),
    }),
    { name: "rewind-session" },
  ),
);

export type TimeSource = "video" | "chart" | "event" | "scrubber" | "rewind" | "twin";

/** The single shared clock: video, overlay, chart, zone grid and explanations all follow it. */
interface TimeState {
  currentTime: number;
  duration: number;
  playing: boolean;
  /** who moved the clock last — the video element only seeks for non-video sources */
  source: TimeSource;
  /** bumped on every external seek so the video element can react */
  seekNonce: number;
  selectedZone: string | null;
  hoverZone: string | null;
  selectedEventId: string | null;
  setTime: (t: number, source: TimeSource) => void;
  setDuration: (d: number) => void;
  setPlaying: (p: boolean) => void;
  selectZone: (z: string | null) => void;
  setHoverZone: (z: string | null) => void;
  selectEvent: (id: string | null, t?: number, zone?: string) => void;
}

export const clampTime = (t: number, duration: number) =>
  Math.min(Math.max(Number.isFinite(t) ? t : 0, 0), duration > 0 ? duration : Number.MAX_SAFE_INTEGER);

export const useTimeStore = create<TimeState>((set, get) => ({
  currentTime: 0,
  duration: 0,
  playing: false,
  source: "video",
  seekNonce: 0,
  selectedZone: null,
  hoverZone: null,
  selectedEventId: null,
  setTime: (t, source) =>
    set((s) => ({
      currentTime: clampTime(t, s.duration),
      source,
      seekNonce: source === "video" ? s.seekNonce : s.seekNonce + 1,
    })),
  setDuration: (d) => set({ duration: d }),
  setPlaying: (p) => set({ playing: p }),
  selectZone: (z) => set({ selectedZone: z }),
  setHoverZone: (z) => set({ hoverZone: z }),
  selectEvent: (id, t, zone) => {
    set({ selectedEventId: id, selectedZone: zone ?? get().selectedZone });
    if (t != null) get().setTime(t, "event");
  },
}));

export interface OverlayToggles {
  boxes: boolean;
  heatmap: boolean;
  zones: boolean;
  arrows: boolean;
}

interface UiState {
  overlay: OverlayToggles;
  explainMethod: "physics" | "shap";
  setOverlay: (k: keyof OverlayToggles, v: boolean) => void;
  setExplainMethod: (m: "physics" | "shap") => void;
}

export const useUiStore = create<UiState>()(
  persist(
    (set) => ({
      overlay: { boxes: true, heatmap: false, zones: true, arrows: false },
      explainMethod: "physics",
      setOverlay: (k, v) => set((s) => ({ overlay: { ...s.overlay, [k]: v } })),
      setExplainMethod: (m) => set({ explainMethod: m }),
    }),
    { name: "rewind-ui" },
  ),
);
