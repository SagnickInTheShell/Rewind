import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { Film, PlayCircle, Upload } from "lucide-react";
import { api, uploadVideo } from "../api/client";
import { useVenue, useVenues } from "../api/hooks";
import { useJobProgress } from "../api/useJobProgress";
import { useSession, useTimeStore } from "../store";
import type { VideoMeta } from "../types";
import { Button, Card, Toggle } from "../components/ui/primitives";
import { TwinCanvas } from "../components/twin/TwinCanvas";
import { JobStages } from "../components/ui/JobStages";
import { CalibrationHelper } from "../components/ui/CalibrationHelper";
import { fmtTime } from "../lib/format";

export default function UploadPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { setRun, setSim } = useSession();
  const setTime = useTimeStore((s) => s.setTime);
  const { data: venues } = useVenues();
  const [venueId, setVenueId] = useState<string>("demo_venue");
  const { data: venue } = useVenue(venueId);
  const [video, setVideo] = useState<VideoMeta | null>(null);
  const [uploadPct, setUploadPct] = useState<number | null>(null);
  const [synthetic, setSynthetic] = useState(false);
  const [sensitive, setSensitive] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [pendingRun, setPendingRun] = useState<string | null>(null);
  const [showCalib, setShowCalib] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const progress = useJobProgress(jobId);

  useEffect(() => {
    if (venues?.length && !venues.some((v) => v.venue_id === venueId)) setVenueId(venues[0].venue_id);
  }, [venues, venueId]);

  useEffect(() => {
    if (progress.done && pendingRun) {
      setRun(pendingRun);
      setTime(0, "event");
      void qc.invalidateQueries({ queryKey: ["run", pendingRun] });
      navigate("/analysis");
    }
  }, [progress.done, pendingRun, setRun, setTime, navigate, qc]);

  const onFile = useCallback(
    async (file: File) => {
      setError(null);
      setVideo(null);
      setUploadPct(0);
      try {
        const meta = await uploadVideo(file, { synthetic: synthetic || /synthetic/i.test(file.name), onProgress: setUploadPct });
        setVideo(meta);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Upload failed");
      } finally {
        setUploadPct(null);
      }
    },
    [synthetic],
  );

  const analyse = async () => {
    if (!video) return;
    setError(null);
    try {
      const r = await api.createRun(video.video_id, venueId, false, sensitive);
      setPendingRun(r.run_id);
      setJobId(r.job_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not start analysis");
    }
  };

  const loadDemo = async () => {
    setError(null);
    try {
      const d = await api.loadDemo();
      setRun(d.run.run_id);
      if (d.sim_id) setSim(d.sim_id);
      setTime(0, "event");
      navigate("/analysis");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Demo not available");
    }
  };

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-4 p-6">
      <div className="flex items-center gap-4">
        <div>
          <h1 className="text-3xl font-semibold">Reconstruct an incident</h1>
          <p className="mt-1 text-muted">
            Upload crowd footage and a venue plan. REWIND identifies escalating risk patterns in crowd dynamics and lets you
            explore modelled alternatives.
          </p>
        </div>
        <Button variant="primary" className="ml-auto px-4 py-2 text-base" onClick={loadDemo} data-testid="load-demo">
          <PlayCircle className="h-5 w-5" /> Load demo
        </Button>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card title="1 · Footage">
          <label
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragOver(false);
              const f = e.dataTransfer.files[0];
              if (f) void onFile(f);
            }}
            className={`flex h-44 cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed ${dragOver ? "border-accent bg-accent/5" : "border-border"}`}
            data-testid="dropzone"
          >
            <Upload className="h-8 w-8 text-muted" />
            <span>Drop a video here or click to choose</span>
            <span className="text-xs text-muted">mp4, webm, mov, avi, mkv</span>
            <input type="file" accept="video/*" className="hidden" onChange={(e) => e.target.files?.[0] && void onFile(e.target.files[0])} />
          </label>
          {uploadPct != null && (
            <div className="mt-3 h-2 overflow-hidden rounded bg-border">
              <div className="h-2 bg-accent" style={{ width: `${uploadPct * 100}%` }} />
            </div>
          )}
          <div className="mt-3 flex flex-wrap gap-4">
            <Toggle label="Synthetic footage" checked={synthetic} onChange={setSynthetic} />
            <Toggle label="Real incident with casualties (adds a respectful note)" checked={sensitive} onChange={setSensitive} />
          </div>
          {video && (
            <div className="mt-3 flex items-center gap-2 text-sm" data-testid="uploaded-video">
              <Film className="h-4 w-4 text-accent" />
              <span className="font-medium">{video.filename}</span>
              <span className="num text-muted">
                {video.width}×{video.height} · {video.fps_native.toFixed(1)} fps · {fmtTime(video.duration_s)}
              </span>
              {video.synthetic && <span className="text-risk-medium">synthetic</span>}
            </div>
          )}
        </Card>

        <Card title="2 · Venue">
          <select
            className="mb-3 w-full rounded border border-border bg-bg px-2 py-1.5"
            value={venueId}
            onChange={(e) => setVenueId(e.target.value)}
            aria-label="Venue"
          >
            {venues?.map((v) => (
              <option key={v.venue_id} value={v.venue_id}>
                {v.name} ({v.zones} zones, {v.portals} portals)
              </option>
            ))}
          </select>
          {venue && <TwinCanvas venue={venue} frame={null} height={230} />}
          {venue && video && (
            <Button className="mt-3" onClick={() => setShowCalib((s) => !s)}>
              {showCalib ? "Hide" : "Open"} calibration helper
            </Button>
          )}
        </Card>
      </div>

      {showCalib && venue && video && (
        <Card title="Camera calibration">
          <CalibrationHelper videoId={video.video_id} venue={venue} onSaved={() => void qc.invalidateQueries({ queryKey: ["venue", venueId] })} />
        </Card>
      )}

      <Card title="3 · Analyse">
        <div className="flex flex-col gap-3">
          <div className="flex items-center gap-3">
            <Button variant="primary" className="px-5 py-2 text-base" disabled={!video || !!jobId} onClick={analyse} data-testid="analyse">
              Analyse
            </Button>
            {!video && <span className="text-muted">Upload a video first.</span>}
          </div>
          {jobId && <JobStages progress={progress} />}
          {error && <p className="text-risk-critical">{error}</p>}
        </div>
      </Card>
    </div>
  );
}
