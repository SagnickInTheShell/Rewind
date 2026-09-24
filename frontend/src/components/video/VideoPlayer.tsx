import { useEffect, useRef } from "react";
import { Pause, Play } from "lucide-react";
import { api } from "../../api/client";
import { useOverlay } from "../../api/hooks";
import { useTimeStore, useUiStore } from "../../store";
import { fmtTime } from "../../lib/format";
import { OverlayRenderer } from "./OverlayRenderer";
import { Toggle } from "../ui/primitives";

interface Props {
  runId: string;
  videoId: string;
  synthetic?: boolean;
}

export function VideoPlayer({ runId, videoId, synthetic }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const rendererRef = useRef<OverlayRenderer | null>(null);
  const { currentTime, duration, playing, seekNonce, selectedZone, setTime, setDuration, setPlaying } = useTimeStore();
  const { overlay, setOverlay } = useUiStore();
  const { data: frame } = useOverlay(runId, currentTime, overlay.heatmap);

  // external seeks (chart, events, rewind) move the video
  useEffect(() => {
    const v = videoRef.current;
    if (v && Math.abs(v.currentTime - currentTime) > 0.05) v.currentTime = currentTime;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [seekNonce]);

  // playback drives the shared clock at display rate
  useEffect(() => {
    const v = videoRef.current;
    if (!v) return;
    let raf = 0;
    const tick = () => {
      setTime(v.currentTime, "video");
      raf = requestAnimationFrame(tick);
    };
    if (playing) {
      void v.play().catch(() => setPlaying(false));
      raf = requestAnimationFrame(tick);
    } else v.pause();
    return () => cancelAnimationFrame(raf);
  }, [playing, setTime, setPlaying]);

  useEffect(() => {
    const canvas = canvasRef.current;
    const wrap = wrapRef.current;
    if (!canvas || !wrap) return;
    let r: OverlayRenderer;
    try {
      r = new OverlayRenderer(canvas);
    } catch {
      return;
    }
    rendererRef.current = r;
    const fit = () => r.resize(wrap.clientWidth, wrap.clientHeight);
    fit();
    const ro = typeof ResizeObserver !== "undefined" ? new ResizeObserver(fit) : null;
    ro?.observe(wrap);
    return () => ro?.disconnect();
  }, []);

  useEffect(() => {
    rendererRef.current?.draw(frame, { ...overlay, selectedZone });
  }, [frame, overlay, selectedZone]);

  return (
    <div className="flex flex-col gap-2">
      <div ref={wrapRef} className="relative aspect-video w-full overflow-hidden rounded-lg border border-border bg-black">
        <video
          ref={videoRef}
          src={api.videoStreamUrl(videoId)}
          className="absolute inset-0 h-full w-full object-contain"
          muted
          playsInline
          preload="auto"
          onLoadedMetadata={(e) => setDuration(e.currentTarget.duration)}
          onEnded={() => setPlaying(false)}
          onSeeked={(e) => !playing && setTime(e.currentTarget.currentTime, "video")}
          data-testid="video"
        />
        <canvas ref={canvasRef} className="pointer-events-none absolute inset-0" data-testid="overlay-canvas" />
        {synthetic && (
          <span className="absolute left-2 top-2 rounded bg-black/70 px-2 py-0.5 text-xs font-semibold text-risk-medium">
            SYNTHETIC FOOTAGE
          </span>
        )}
      </div>
      <div className="flex items-center gap-3">
        <button
          className="rounded-full bg-accent p-2 text-bg hover:bg-sky-300"
          onClick={() => setPlaying(!playing)}
          aria-label={playing ? "Pause" : "Play"}
        >
          {playing ? <Pause className="h-5 w-5" /> : <Play className="h-5 w-5" />}
        </button>
        <span className="num text-2xl font-semibold">{fmtTime(currentTime)}</span>
        <span className="num text-muted">/ {fmtTime(duration)}</span>
        <input
          type="range"
          className="flex-1 accent-sky-400"
          min={0}
          max={duration || 0}
          step={0.1}
          value={currentTime}
          onChange={(e) => setTime(Number(e.target.value), "scrubber")}
          aria-label="Scrub video"
        />
      </div>
      <div className="flex flex-wrap gap-4">
        <Toggle label="Boxes + track tails" checked={overlay.boxes} onChange={(v) => setOverlay("boxes", v)} />
        <Toggle label="Density heatmap" checked={overlay.heatmap} onChange={(v) => setOverlay("heatmap", v)} />
        <Toggle label="Zone grid (risk)" checked={overlay.zones} onChange={(v) => setOverlay("zones", v)} />
        <Toggle label="Flow arrows" checked={overlay.arrows} onChange={(v) => setOverlay("arrows", v)} />
      </div>
    </div>
  );
}
