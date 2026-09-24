// Framework-free canvas renderer for the digital twin. React only calls setVenue/draw.
import type { Portal, Venue } from "../../types";
import { BUCKET_COLORS, DENSITY_BUCKETS, densityBucket, THEME, viridis } from "../../lib/colors";

export interface TwinFrame {
  t: number;
  /** interleaved x,y in metres (length 2n) */
  xy: Float32Array;
  /** local density per agent, people/m² (length n) */
  density: Float32Array;
}

export interface TwinDrawState {
  frame: TwinFrame | null;
  /** portal_id -> open? (overrides the venue default, e.g. after an intervention) */
  portalOpen?: Record<string, boolean>;
  /** portal ids changed by the scenario; drawn pulsing */
  changedPortals?: string[];
  /** portal_id -> width multiplier */
  portalWidthFactor?: Record<string, number>;
  showHeatmap?: boolean;
  /** animation clock in ms for pulsing */
  clockMs?: number;
  label?: string;
}

export interface Transform {
  scale: number;
  ox: number;
  oy: number;
}

export function fitTransform(venue: Venue, width: number, height: number, pad = 24): Transform {
  const [min, max] = venue.bounds;
  const w = Math.max(max.x - min.x, 1e-6);
  const h = Math.max(max.y - min.y, 1e-6);
  const scale = Math.min((width - 2 * pad) / w, (height - 2 * pad) / h);
  const ox = (width - w * scale) / 2 - min.x * scale;
  const oy = (height - h * scale) / 2 - min.y * scale;
  return { scale, ox, oy };
}

const HEAT_CELL_M = 1.0;

export class TwinRenderer {
  private ctx: CanvasRenderingContext2D;
  private venue: Venue | null = null;
  private tf: Transform = { scale: 1, ox: 0, oy: 0 };
  private staticLayer: HTMLCanvasElement | null = null;
  private dpr = 1;

  constructor(private canvas: HTMLCanvasElement) {
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("2D canvas not supported");
    this.ctx = ctx;
  }

  resize(cssWidth: number, cssHeight: number, dpr = window.devicePixelRatio || 1): void {
    this.dpr = dpr;
    this.canvas.width = Math.round(cssWidth * dpr);
    this.canvas.height = Math.round(cssHeight * dpr);
    this.canvas.style.width = `${cssWidth}px`;
    this.canvas.style.height = `${cssHeight}px`;
    if (this.venue) this.setVenue(this.venue);
  }

  setVenue(venue: Venue): void {
    this.venue = venue;
    this.tf = fitTransform(venue, this.canvas.width / this.dpr, this.canvas.height / this.dpr);
    this.staticLayer = this.renderStatic();
  }

  get transform(): Transform {
    return this.tf;
  }

  private wx(x: number): number {
    return x * this.tf.scale + this.tf.ox;
  }
  private wy(y: number): number {
    return y * this.tf.scale + this.tf.oy;
  }

  private renderStatic(): HTMLCanvasElement | null {
    if (!this.venue || typeof document === "undefined") return null;
    const off = document.createElement("canvas");
    off.width = this.canvas.width;
    off.height = this.canvas.height;
    const g = off.getContext("2d");
    if (!g) return null;
    g.scale(this.dpr, this.dpr);
    g.fillStyle = THEME.bg;
    g.fillRect(0, 0, off.width, off.height);
    // zones
    for (const z of this.venue.zones) {
      g.beginPath();
      z.polygon.forEach((p, i) => (i === 0 ? g.moveTo(this.wx(p.x), this.wy(p.y)) : g.lineTo(this.wx(p.x), this.wy(p.y))));
      g.closePath();
      g.fillStyle = "#101720";
      g.fill();
      g.strokeStyle = "#1c2733";
      g.lineWidth = 1;
      g.setLineDash([4, 4]);
      g.stroke();
      g.setLineDash([]);
      const cx = z.polygon.reduce((a, p) => a + p.x, 0) / z.polygon.length;
      const cy = z.polygon.reduce((a, p) => a + p.y, 0) / z.polygon.length;
      g.fillStyle = "#3a4756";
      g.font = "600 14px Inter, sans-serif";
      g.textAlign = "center";
      g.textBaseline = "middle";
      g.fillText(z.zone_id, this.wx(cx), this.wy(cy));
    }
    // walls
    g.strokeStyle = "#8B98A5";
    g.lineWidth = 3;
    g.lineCap = "round";
    for (const w of this.venue.walls) {
      g.beginPath();
      g.moveTo(this.wx(w.a.x), this.wy(w.a.y));
      g.lineTo(this.wx(w.b.x), this.wy(w.b.y));
      g.stroke();
    }
    return off;
  }

  private drawPortal(p: Portal, open: boolean, changed: boolean, widthFactor: number, clockMs: number): void {
    const g = this.ctx;
    let [a, b] = p.segment;
    if (widthFactor !== 1) {
      const mx = (a.x + b.x) / 2;
      const my = (a.y + b.y) / 2;
      a = { x: mx + (a.x - mx) * widthFactor, y: my + (a.y - my) * widthFactor };
      b = { x: mx + (b.x - mx) * widthFactor, y: my + (b.y - my) * widthFactor };
    }
    const isGate = p.kind !== "corridor";
    if (!isGate && open && !changed) return;
    const pulse = changed ? 0.5 + 0.5 * Math.sin(clockMs / 180) : 1;
    g.save();
    g.lineCap = "round";
    g.lineWidth = isGate ? 7 : 4;
    g.strokeStyle = open ? `rgba(34,197,94,${0.55 + 0.45 * pulse})` : "#4B5563";
    if (changed) {
      g.shadowColor = open ? "#22C55E" : "#EF4444";
      g.shadowBlur = 8 + 10 * pulse;
    }
    g.beginPath();
    g.moveTo(this.wx(a.x), this.wy(a.y));
    g.lineTo(this.wx(b.x), this.wy(b.y));
    g.stroke();
    if (isGate) {
      g.shadowBlur = 0;
      g.fillStyle = THEME.text;
      g.font = "600 13px Inter, sans-serif";
      g.textAlign = "center";
      const mx = this.wx((a.x + b.x) / 2);
      const my = this.wy((a.y + b.y) / 2);
      const [min, max] = this.venue!.bounds;
      const outX = (a.x + b.x) / 2 <= min.x + 0.01 ? -1 : (a.x + b.x) / 2 >= max.x - 0.01 ? 1 : 0;
      const outY = (a.y + b.y) / 2 <= min.y + 0.01 ? -1 : (a.y + b.y) / 2 >= max.y - 0.01 ? 1 : 0;
      g.textBaseline = "middle";
      g.fillText(p.name, mx + outX * 30, my + outY * 13);
    }
    g.restore();
  }

  private drawHeatmap(frame: TwinFrame): void {
    if (!this.venue) return;
    const [min, max] = this.venue.bounds;
    const cols = Math.ceil((max.x - min.x) / HEAT_CELL_M);
    const rows = Math.ceil((max.y - min.y) / HEAT_CELL_M);
    const grid = new Float32Array(cols * rows);
    const n = frame.density.length;
    for (let i = 0; i < n; i++) {
      const c = Math.floor((frame.xy[2 * i] - min.x) / HEAT_CELL_M);
      const r = Math.floor((frame.xy[2 * i + 1] - min.y) / HEAT_CELL_M);
      if (c >= 0 && c < cols && r >= 0 && r < rows) grid[r * cols + c] += 1 / (HEAT_CELL_M * HEAT_CELL_M);
    }
    const g = this.ctx;
    const s = HEAT_CELL_M * this.tf.scale;
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const v = grid[r * cols + c];
        if (v <= 0) continue;
        g.fillStyle = viridis(v / 6, 0.45);
        g.fillRect(this.wx(min.x + c * HEAT_CELL_M), this.wy(min.y + r * HEAT_CELL_M), s + 0.5, s + 0.5);
      }
    }
  }

  draw(state: TwinDrawState): void {
    const g = this.ctx;
    g.setTransform(1, 0, 0, 1, 0, 0);
    if (this.staticLayer) g.drawImage(this.staticLayer, 0, 0);
    else {
      g.fillStyle = THEME.bg;
      g.fillRect(0, 0, this.canvas.width, this.canvas.height);
    }
    g.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
    if (!this.venue) return;
    const frame = state.frame;
    if (frame && state.showHeatmap) this.drawHeatmap(frame);

    // agents: one path per density bucket
    if (frame) {
      const n = frame.density.length;
      const r = Math.max(1.6, 0.25 * this.tf.scale);
      const buckets: number[][] = Array.from({ length: DENSITY_BUCKETS }, () => []);
      for (let i = 0; i < n; i++) buckets[densityBucket(frame.density[i])].push(i);
      for (let b = 0; b < DENSITY_BUCKETS; b++) {
        const idx = buckets[b];
        if (idx.length === 0) continue;
        g.beginPath();
        for (const i of idx) {
          const x = this.wx(frame.xy[2 * i]);
          const y = this.wy(frame.xy[2 * i + 1]);
          g.moveTo(x + r, y);
          g.arc(x, y, r, 0, Math.PI * 2);
        }
        g.fillStyle = BUCKET_COLORS[b];
        g.fill();
      }
    }

    const changed = new Set(state.changedPortals ?? []);
    for (const p of this.venue.portals) {
      const open = state.portalOpen?.[p.portal_id] ?? p.is_open;
      this.drawPortal(p, open, changed.has(p.portal_id), state.portalWidthFactor?.[p.portal_id] ?? 1, state.clockMs ?? 0);
    }

    if (state.label) {
      g.fillStyle = "rgba(11,15,20,0.8)";
      g.fillRect(8, 8, g.measureText(state.label).width + 24, 28);
      g.fillStyle = THEME.text;
      g.font = "600 15px Inter, sans-serif";
      g.textAlign = "left";
      g.textBaseline = "middle";
      g.fillText(state.label, 20, 22);
    }
    if (frame) {
      g.fillStyle = THEME.muted;
      g.font = "13px 'JetBrains Mono', monospace";
      g.textAlign = "right";
      g.textBaseline = "top";
      g.fillText(`${frame.density.length} agents`, this.canvas.width / this.dpr - 10, 10);
    }
  }
}

export function agentFrameToTwin(f: { t: number; xy: [number, number][]; local_density: number[] }): TwinFrame {
  const xy = new Float32Array(f.xy.length * 2);
  f.xy.forEach(([x, y], i) => {
    xy[2 * i] = x;
    xy[2 * i + 1] = y;
  });
  return { t: f.t, xy, density: Float32Array.from(f.local_density) };
}
