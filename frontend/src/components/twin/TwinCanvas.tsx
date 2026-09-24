import { useEffect, useRef } from "react";
import type { Venue } from "../../types";
import { TwinRenderer, type TwinDrawState } from "./TwinRenderer";

interface Props extends TwinDrawState {
  venue: Venue;
  height?: number;
}

/** Thin React wrapper: owns the canvas, forwards props to the TwinRenderer. */
export function TwinCanvas({ venue, height = 360, ...state }: Props) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rendererRef = useRef<TwinRenderer | null>(null);
  const stateRef = useRef<TwinDrawState>(state);
  stateRef.current = state;

  useEffect(() => {
    const canvas = canvasRef.current;
    const wrap = wrapRef.current;
    if (!canvas || !wrap) return;
    let r: TwinRenderer;
    try {
      r = new TwinRenderer(canvas);
    } catch {
      return; // no 2D context (e.g. jsdom)
    }
    rendererRef.current = r;
    const fit = () => {
      r.resize(wrap.clientWidth || 600, height);
      r.setVenue(venue);
      r.draw(stateRef.current);
    };
    fit();
    const ro = typeof ResizeObserver !== "undefined" ? new ResizeObserver(fit) : null;
    ro?.observe(wrap);
    return () => ro?.disconnect();
  }, [venue, height]);

  useEffect(() => {
    rendererRef.current?.draw(state);
  });

  return (
    <div ref={wrapRef} className="w-full overflow-hidden rounded border border-border">
      <canvas ref={canvasRef} data-testid="twin-canvas" />
    </div>
  );
}
