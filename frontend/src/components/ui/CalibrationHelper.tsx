import { useMemo, useRef, useState } from "react";
import { Trash2 } from "lucide-react";
import { api, ApiError } from "../../api/client";
import type { Point, Venue } from "../../types";
import { Button } from "./primitives";

interface Pair {
  image: Point | null;
  world: Point | null;
}

export function pairsComplete(pairs: Pair[]): boolean {
  return pairs.filter((p) => p.image && p.world).length >= 4;
}

/** Click ≥ 4 ground points on the first frame and their matches on the floor plan; saves into venue.calibration. */
export function CalibrationHelper({ videoId, venue, onSaved }: { videoId: string; venue: Venue; onSaved: (v: Venue) => void }) {
  const [pairs, setPairs] = useState<Pair[]>(() =>
    venue.calibration.image_points.map((p, i) => ({ image: p, world: venue.calibration.world_points[i] ?? null })),
  );
  const [msg, setMsg] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const imgRef = useRef<HTMLImageElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const [min, max] = venue.bounds;
  const w = max.x - min.x;
  const h = max.y - min.y;

  const nextSlot = (key: "image" | "world") => {
    const i = pairs.findIndex((p) => p[key] === null);
    return i >= 0 ? i : pairs.length;
  };

  const put = (key: "image" | "world", pt: Point) =>
    setPairs((ps) => {
      const i = nextSlot(key);
      const copy = ps.map((p) => ({ ...p }));
      if (i >= copy.length) copy.push({ image: null, world: null });
      copy[i][key] = { x: Math.round(pt.x * 100) / 100, y: Math.round(pt.y * 100) / 100 };
      return copy;
    });

  const onImageClick = (e: React.MouseEvent<HTMLImageElement>) => {
    const img = imgRef.current!;
    const r = img.getBoundingClientRect();
    put("image", {
      x: ((e.clientX - r.left) * img.naturalWidth) / r.width,
      y: ((e.clientY - r.top) * img.naturalHeight) / r.height,
    });
  };

  const onPlanClick = (e: React.MouseEvent<SVGSVGElement>) => {
    const svg = svgRef.current!;
    const pt = svg.createSVGPoint();
    pt.x = e.clientX;
    pt.y = e.clientY;
    const m = svg.getScreenCTM();
    if (!m) return;
    const p = pt.matrixTransform(m.inverse());
    put("world", { x: p.x, y: p.y });
  };

  const save = async () => {
    const done = pairs.filter((p) => p.image && p.world) as { image: Point; world: Point }[];
    if (done.length < 4) {
      setMsg("Need at least 4 complete point pairs.");
      return;
    }
    setSaving(true);
    try {
      const v = await api.putVenue({
        ...venue,
        calibration: { image_points: done.map((p) => p.image), world_points: done.map((p) => p.world) },
      });
      setMsg("Calibration saved.");
      onSaved(v);
    } catch (e) {
      const detail = e instanceof ApiError && Array.isArray(e.detail) ? `: ${(e.detail as string[]).join("; ")}` : "";
      setMsg(`${e instanceof Error ? e.message : "Save failed"}${detail}`);
    } finally {
      setSaving(false);
    }
  };

  const imgMarkers = useMemo(() => pairs.map((p, i) => ({ i, p: p.image })).filter((m) => m.p), [pairs]);

  return (
    <div className="flex flex-col gap-3" data-testid="calibration-helper">
      <p className="text-sm text-muted">
        Click a ground point on the frame (floor markings, gate posts), then the same point on the floor plan. Repeat for at
        least 4 points spread across the floor. Pixel coordinates are in the original video resolution.
      </p>
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        <div className="relative">
          <img
            ref={imgRef}
            src={api.frameUrl(videoId, 0, true)}
            alt="First video frame"
            className="w-full cursor-crosshair rounded border border-border"
            onClick={onImageClick}
          />
          {imgRef.current &&
            imgMarkers.map(({ i, p }) => (
              <span
                key={i}
                className="pointer-events-none absolute flex h-5 w-5 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full bg-accent text-xs font-bold text-bg"
                style={{
                  left: `${(100 * p!.x) / (imgRef.current!.naturalWidth || 1)}%`,
                  top: `${(100 * p!.y) / (imgRef.current!.naturalHeight || 1)}%`,
                }}
              >
                {i + 1}
              </span>
            ))}
        </div>
        <svg
          ref={svgRef}
          viewBox={`${min.x - 1} ${min.y - 1} ${w + 2} ${h + 2}`}
          className="w-full cursor-crosshair rounded border border-border bg-bg"
          onClick={onPlanClick}
        >
          {venue.zones.map((z) => (
            <polygon key={z.zone_id} points={z.polygon.map((p) => `${p.x},${p.y}`).join(" ")} fill="#121821" stroke="#1F2A37" strokeWidth={0.1} />
          ))}
          {venue.walls.map((wl, i) => (
            <line key={i} x1={wl.a.x} y1={wl.a.y} x2={wl.b.x} y2={wl.b.y} stroke="#8B98A5" strokeWidth={0.25} />
          ))}
          {pairs.map((p, i) =>
            p.world ? (
              <g key={i}>
                <circle cx={p.world.x} cy={p.world.y} r={0.6} fill="#38BDF8" />
                <text x={p.world.x} y={p.world.y + 0.35} fontSize={0.9} textAnchor="middle" fill="#0B0F14" fontWeight={700}>
                  {i + 1}
                </text>
              </g>
            ) : null,
          )}
        </svg>
      </div>
      <table className="text-sm">
        <thead className="text-muted">
          <tr>
            <th className="text-left">#</th>
            <th className="text-left">Image (px)</th>
            <th className="text-left">World (m)</th>
            <th />
          </tr>
        </thead>
        <tbody className="num">
          {pairs.map((p, i) => (
            <tr key={i}>
              <td>{i + 1}</td>
              <td>{p.image ? `${p.image.x.toFixed(0)}, ${p.image.y.toFixed(0)}` : "—"}</td>
              <td>
                {p.world ? (
                  <span className="flex gap-1">
                    {(["x", "y"] as const).map((k) => (
                      <input
                        key={k}
                        type="number"
                        step={0.1}
                        className="w-20 rounded border border-border bg-bg px-1"
                        value={p.world![k]}
                        onChange={(e) =>
                          setPairs((ps) => ps.map((q, j) => (j === i ? { ...q, world: { ...q.world!, [k]: Number(e.target.value) } } : q)))
                        }
                      />
                    ))}
                  </span>
                ) : (
                  "—"
                )}
              </td>
              <td>
                <button aria-label={`Remove pair ${i + 1}`} onClick={() => setPairs((ps) => ps.filter((_, j) => j !== i))}>
                  <Trash2 className="h-4 w-4 text-muted hover:text-risk-critical" />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="flex items-center gap-3">
        <Button variant="primary" onClick={save} disabled={saving || !pairsComplete(pairs)}>
          Save calibration
        </Button>
        <Button onClick={() => setPairs([])}>Clear</Button>
        {msg && <span className="text-sm text-muted">{msg}</span>}
      </div>
    </div>
  );
}
