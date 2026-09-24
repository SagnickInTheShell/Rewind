import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { api } from "./client";

export const useHealth = () => useQuery({ queryKey: ["health"], queryFn: api.health, staleTime: 30_000 });
export const useVenues = () => useQuery({ queryKey: ["venues"], queryFn: api.listVenues });
export const useVenue = (id: string | null | undefined) =>
  useQuery({ queryKey: ["venue", id], queryFn: () => api.getVenue(id!), enabled: !!id });
export const useRuns = () => useQuery({ queryKey: ["runs"], queryFn: api.listRuns });
export const useRun = (id: string | null | undefined, refetchWhileRunning = false) =>
  useQuery({
    queryKey: ["run", id],
    queryFn: () => api.getRun(id!),
    enabled: !!id,
    refetchInterval: (q) => (refetchWhileRunning && q.state.data?.status === "RUNNING" ? 2000 : false),
  });
export const useRunVenue = (id: string | null | undefined) =>
  useQuery({ queryKey: ["run-venue", id], queryFn: () => api.getRunVenue(id!), enabled: !!id });
export const useRisk = (id: string | null | undefined) =>
  useQuery({ queryKey: ["risk", id], queryFn: () => api.getRisk(id!), enabled: !!id, staleTime: Infinity });
export const useTimeline = (id: string | null | undefined) =>
  useQuery({ queryKey: ["timeline", id], queryFn: () => api.getTimeline(id!), enabled: !!id, staleTime: Infinity });
export const useFeatures = (id: string | null | undefined, zone?: string) =>
  useQuery({
    queryKey: ["features", id, zone],
    queryFn: () => api.getFeatures(id!, zone),
    enabled: !!id,
    staleTime: Infinity,
  });

/** Processed frames are 0.2 s apart; quantise so scrubbing re-uses cached overlays. */
export const quantise = (t: number, step = 0.2) => Math.round(t / step) * step;

export const useOverlay = (id: string | null | undefined, t: number, heatmap: boolean) => {
  const tq = Number(quantise(t).toFixed(2));
  return useQuery({
    queryKey: ["overlay", id, tq, heatmap],
    queryFn: () => api.getOverlay(id!, tq, heatmap),
    enabled: !!id,
    staleTime: Infinity,
    placeholderData: keepPreviousData,
  });
};

export const useExplanation = (
  id: string | null | undefined,
  t: number,
  zone: string | null | undefined,
  method: "physics" | "shap",
) => {
  const tq = Math.max(1, Math.round(t));
  return useQuery({
    queryKey: ["explanation", id, tq, zone, method],
    queryFn: () => api.getExplanation(id!, tq, zone, method),
    enabled: !!id,
    staleTime: Infinity,
    placeholderData: keepPreviousData,
    retry: false,
  });
};

export const useValidation = (id: string | null | undefined) =>
  useQuery({ queryKey: ["validation", id], queryFn: () => api.getValidation(id!), enabled: !!id, retry: false });

export const useSimulation = (simId: string | null | undefined) =>
  useQuery({
    queryKey: ["simulation", simId],
    queryFn: () => api.getSimulation(simId!),
    enabled: !!simId,
    refetchInterval: (q) => (q.state.data?.status === "RUNNING" ? 1500 : false),
  });

export const useComparison = (simId: string | null | undefined) =>
  useQuery({
    queryKey: ["comparison", simId],
    queryFn: () => api.getComparison(simId!),
    enabled: !!simId,
    retry: false,
  });

export const usePlan = (simId: string | null | undefined) =>
  useQuery({
    queryKey: ["plan", simId],
    queryFn: () => api.getPlan(simId!),
    enabled: !!simId,
    retry: false,
  });

export const useSimFrames = (
  simId: string | null | undefined,
  scenarioId: string | null | undefined,
  seed = 0
) =>
  useQuery({
    queryKey: ["frames", simId, scenarioId, seed],
    queryFn: () => api.getFrames(simId!, scenarioId!, seed),
    enabled: !!simId && !!scenarioId,
    staleTime: Infinity,
  });
