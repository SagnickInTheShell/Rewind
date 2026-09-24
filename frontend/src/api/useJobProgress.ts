import { useEffect, useRef, useState } from "react";
import type { ProgressEvent } from "../types";
import { api, wsUrl } from "./client";

export interface JobProgressState {
  stage: string;
  percent: number;
  message: string;
  eta_s: number | null;
  done: boolean;
  error: string | null;
  /** stages seen so far, in order */
  history: string[];
  connected: boolean;
}

const INITIAL: JobProgressState = {
  stage: "queued",
  percent: 0,
  message: "",
  eta_s: null,
  done: false,
  error: null,
  history: [],
  connected: false,
};

/** Pure reducer (unit-tested): folds a WebSocket progress event into the state. */
export function applyProgress(s: JobProgressState, ev: ProgressEvent): JobProgressState {
  if (ev.stage === "heartbeat") return s;
  const history = ev.stage && !s.history.includes(ev.stage) ? [...s.history, ev.stage] : s.history;
  return {
    ...s,
    stage: ev.stage,
    percent: ev.percent >= 0 ? ev.percent : s.percent,
    message: ev.message,
    eta_s: ev.eta_s,
    done: ev.done,
    error: ev.error,
    history,
  };
}

/** Subscribes to /ws/jobs/{jobId}; reconnects with back-off and falls back to polling the job status. */
export function useJobProgress(jobId: string | null | undefined): JobProgressState {
  const [state, setState] = useState<JobProgressState>(INITIAL);
  const finished = useRef(false);

  useEffect(() => {
    setState(INITIAL);
    finished.current = false;
    if (!jobId) return;
    let ws: WebSocket | null = null;
    let attempt = 0;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let cancelled = false;

    const poll = async () => {
      try {
        const st = await api.getJob(jobId);
        setState((s) =>
          applyProgress(s, {
            stage: st.state === "DONE" ? "done" : st.stage,
            percent: st.percent,
            message: st.message,
            eta_s: st.eta_s,
            done: st.state === "DONE",
            error: st.state === "FAILED" ? st.error ?? "failed" : null,
          }),
        );
        if (st.state === "DONE" || st.state === "FAILED") finished.current = true;
      } catch {
        /* ignore transient errors */
      }
    };

    const connect = () => {
      if (cancelled || finished.current) return;
      ws = new WebSocket(wsUrl(`/ws/jobs/${jobId}`));
      ws.onopen = () => {
        attempt = 0;
        setState((s) => ({ ...s, connected: true }));
      };
      ws.onmessage = (msg) => {
        const ev = JSON.parse(String(msg.data)) as ProgressEvent;
        setState((s) => applyProgress(s, ev));
        if (ev.done || ev.error) finished.current = true;
      };
      ws.onclose = () => {
        setState((s) => ({ ...s, connected: false }));
        if (cancelled || finished.current) return;
        attempt += 1;
        void poll();
        timer = setTimeout(connect, Math.min(8000, 500 * 2 ** attempt));
      };
    };
    connect();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
      ws?.close();
    };
  }, [jobId]);

  return state;
}
