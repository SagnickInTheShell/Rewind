// Framework-free renderer for the video overlay (tracks, heatmap, zone grid, flow arrows).
import type { OverlayFrame } from "../../types";
import { riskColor, viridisRgb } from "../../lib/colors";
import { fmtDensity } from "../../lib/format";
import type { OverlayToggles } from "../../store";

export interface OverlayDrawOptions extends OverlayToggles {
  selectedZone?: string | null;
}

export interface Fit {
  scale: number;
  ox: number;
  oy: number;
}

/** Letterbox fit of a (fw × fh) frame inside a (cw × ch) box, as done by <video object-fit: contain>. */
export function fitFrame(fw: number, fh: number, cw: number, ch: number): Fit {
  const scale = Math.min(cw / Math.max(fw, 1), ch / Math.max(fh, 1));
  return { scale, ox: (cw - fw * scale) / 2, oy: (ch - fh * scale) / 2 };
}

export class OverlayRenderer {
  private ctx: CanvasRenderingContext2D;
  private heat: HTMLCanvasElement | null = null;
  private dpr = 1;
  private cssW = 0;
  private cssH = 0;

  constructor(private canvas: HTMLCanvasElement) {
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("2D canvas not supported");
    this.ctx = ctx;
  }

  resize(cssW: number, cssH: number, dpr = window.devicePixelRatio || 1): void {
    this.dpr = dpr;
    this.cssW = cssW;
    this.cssH = cssH;
    this.canvas.width = Math.round(cssW * dpr);
    this.canvas.height = Math.round(cssH * dpr);
    this.canvas.style.width = `${cssW}px`;
    this.canvas.style.height = `${cssH}px`;
  }

  clear(): void {
    this.ctx.setTransform(1, 0, 0, 1, 0, 0);
    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
  }

  draw(frame: OverlayFrame | null | undefined, opts: OverlayDrawOptions): void {
    this.clear();
    if (!frame) return;
    const g = this.ctx;
    const fit = fitFrame(frame.frame_width, frame.frame_height, this.cssW, this.cssH);
    g.setTransform(this.dpr * fit.scale, 0, 0, this.dpr * fit.scale, this.dpr * fit.ox, this.dpr * fit.oy);
    const px = 1 / fit.scale; // one CSS pixel in frame units

    if (opts.heatmap && frame.heatmap) this.drawHeat(frame);

    if (opts.zones) {
      for (const z of frame.zones) {
        if (!z.polygon_px.length) continue;
        const c = riskColor(z.state);
        const sel = opts.selectedZone === z.zone_id;
        g.beginPath();
        z.polygon_px.forEach(([x, y], i) => (i === 0 ? g.moveTo(x, y) : g.lineTo(x, y)));
        g.closePath();
        g.fillStyle = `${c}${z.state === "LOW" ? "10" : "30"}`;
        g.fill();
        g.lineWidth = (sel ? 3 : 1.5) * px;
        g.strokeStyle = sel ? "#E6EDF3" : `${c}aa`;
        g.stroke();
        const cx = z.polygon_px.reduce((a, p) => a + p[0], 0) / z.polygon_px.length;
        const cy = z.polygon_px.reduce((a, p) => a + p[1], 0) / z.polygon_px.length;
        const label = `${z.zone_id} · ${Math.round(z.count)} ppl · ${fmtDensity(z.density)}/m²`;
        const mode = z.mode === "sparse" ? "sparse: tracking" : "dense: density+flow";
        g.font = `600 ${14 * px}px Inter, sans-serif`;
        const w = Math.max(g.measureText(label).width, g.measureText(mode).width) + 12 * px;
        g.fillStyle = "rgba(11,15,20,0.72)";
        g.fillRect(cx - w / 2, cy - 20 * px, w, 38 * px);
        g.fillStyle = c;
        g.textAlign = "center";
        g.textBaseline = "middle";
        g.fillText(label, cx, cy - 8 * px);
        g.font = `${12 * px}px Inter, sans-serif`;
        g.fillStyle = "#8B98A5";
        g.fillText(mode, cx, cy + 9 * px);
      }
    }

    if (opts.boxes) {
      g.lineWidth = 1.5 * px;
      for (const tr of frame.tracks) {
        if (tr.tail.length > 1) {
          g.beginPath();
          tr.tail.forEach(([x, y], i) => (i === 0 ? g.moveTo(x, y) : g.lineTo(x, y)));
          g.strokeStyle = "rgba(56,189,248,0.55)";
          g.stroke();
        }
        if (tr.bbox_xyxy) {
          const [x1, y1, x2, y2] = tr.bbox_xyxy;
          g.strokeStyle = "rgba(56,189,248,0.95)";
          g.strokeRect(x1, y1, x2 - x1, y2 - y1);
        }
      }
    }

    if (opts.arrows) {
      g.strokeStyle = "rgba(230,237,243,0.85)";
      g.fillStyle = "rgba(230,237,243,0.85)";
      g.lineWidth = 1.6 * px;
      for (const a of frame.arrows) {
        const len = Math.hypot(a.dx, a.dy);
        if (len < 2) continue;
        const ex = a.x + a.dx;
        const ey = a.y + a.dy;
        g.beginPath();
        g.moveTo(a.x, a.y);
        g.lineTo(ex, ey);
        g.stroke();
        const ang = Math.atan2(a.dy, a.dx);
        const h = Math.min(8 * px, len * 0.4);
        g.beginPath();
        g.moveTo(ex, ey);
        g.lineTo(ex - h * Math.cos(ang - 0.5), ey - h * Math.sin(ang - 0.5));
        g.lineTo(ex - h * Math.cos(ang + 0.5), ey - h * Math.sin(ang + 0.5));
        g.closePath();
        g.fill();
      }
    }
  }

  private drawHeat(frame: OverlayFrame): void {
    const grid = frame.heatmap!;
    const rows = grid.length;
    const cols = rows ? grid[0].length : 0;
    if (!rows || !cols || typeof document === "undefined") return;
    if (!this.heat) this.heat = document.createElement("canvas");
    this.heat.width = cols;
    this.heat.height = rows;
    const hg = this.heat.getContext("2d");
    if (!hg) return;
    const img = hg.createImageData(cols, rows);
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const d = grid[r][c];
        const i = 4 * (r * cols + c);
        const v = Math.min(d / 6, 1);
        const [R, G, B] = viridisRgb(v);
        img.data[i] = R;
        img.data[i + 1] = G;
        img.data[i + 2] = B;
        img.data[i + 3] = d < 0.05 ? 0 : Math.round(90 + 110 * v);
      }
    }
    hg.putImageData(img, 0, 0);
    const g = this.ctx;
    g.imageSmoothingEnabled = true;
    g.drawImage(this.heat, 0, 0, frame.frame_width, frame.frame_height);
  }
}
