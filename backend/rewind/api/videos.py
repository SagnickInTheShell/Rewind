"""Video upload, listing, range streaming and frame export."""

from __future__ import annotations

import logging
import mimetypes
import re
import secrets
from collections.abc import Iterator
from pathlib import Path

import cv2
import numpy as np
from fastapi import APIRouter, File, Form, Header, Query, UploadFile
from fastapi.responses import Response, StreamingResponse

from rewind.api.deps import settings, store
from rewind.api.errors import ApiError, not_found
from rewind.ingest.video_reader import VideoOpenError, VideoReader, probe
from rewind.pipeline.analyze import save_video_meta
from rewind.privacy import blur_heads
from rewind.schemas.video import VideoMeta
from rewind.storage.run_store import read_model

log = logging.getLogger(__name__)
router = APIRouter(tags=["videos"])

ALLOWED_EXT = {".mp4", ".webm", ".mov", ".avi", ".mkv", ".m4v"}
CHUNK = 1024 * 1024


@router.post("/videos", response_model=VideoMeta, summary="Upload a video (multipart)")
async def upload_video(file: UploadFile = File(...),
                       synthetic: bool = Form(False, description="footage is synthetic (rendered)")) -> VideoMeta:
    s, st = settings(), store()
    name = Path(file.filename or "video.mp4").name
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED_EXT:
        raise ApiError(415, "unsupported_media", f"unsupported video type '{ext}'",
                       {"allowed": sorted(ALLOWED_EXT)})
    video_id = f"vid_{secrets.token_hex(5)}"
    dst = s.videos_dir / f"{video_id}{ext}"
    limit = s.app.max_upload_mb * 1024 * 1024
    size = 0
    with open(dst, "wb") as fh:
        while chunk := await file.read(CHUNK):
            size += len(chunk)
            if size > limit:
                fh.close()
                dst.unlink(missing_ok=True)
                raise ApiError(413, "too_large", f"upload exceeds {s.app.max_upload_mb} MB")
            fh.write(chunk)
    try:
        meta = probe(dst, video_id, s.video.fps_processed, synthetic=synthetic).model_copy(update={"filename": name})
    except VideoOpenError as exc:
        dst.unlink(missing_ok=True)
        raise ApiError(422, "bad_video", str(exc)) from exc
    save_video_meta(st, meta)
    log.info("video uploaded", extra={"kv": {"video_id": video_id, "bytes": size}})
    return meta


@router.get("/videos", response_model=list[VideoMeta], summary="List uploaded videos")
def list_videos() -> list[VideoMeta]:
    s = settings()
    out = []
    for p in sorted(s.videos_dir.glob("*.json")):
        if p.name.endswith(".synthetic.json"):
            continue
        try:
            out.append(read_model(p, VideoMeta))
        except Exception:
            continue
    return out


@router.get("/videos/{video_id}", response_model=VideoMeta, summary="Video metadata")
def get_video(video_id: str) -> VideoMeta:
    st = store()
    p = st.video_meta_path(video_id)
    if not p.exists():
        raise not_found("video", video_id)
    return read_model(p, VideoMeta)


def _file_iter(path: Path, start: int, end: int) -> Iterator[bytes]:
    with open(path, "rb") as fh:
        fh.seek(start)
        remaining = end - start + 1
        while remaining > 0:
            data = fh.read(min(CHUNK, remaining))
            if not data:
                break
            remaining -= len(data)
            yield data


@router.get("/videos/{video_id}/stream", summary="Video file with HTTP Range support")
def stream_video(video_id: str, range_header: str | None = Header(None, alias="range")) -> Response:
    try:
        path = store().video_path(video_id)
    except FileNotFoundError as exc:
        raise not_found("video", video_id) from exc
    size = path.stat().st_size
    ctype = mimetypes.guess_type(path.name)[0] or ("video/webm" if path.suffix == ".webm" else "video/mp4")
    headers = {"Accept-Ranges": "bytes", "Cache-Control": "no-cache"}
    if range_header:
        m = re.match(r"bytes=(\d*)-(\d*)", range_header)
        if not m:
            raise ApiError(416, "bad_range", "invalid Range header")
        s_, e_ = m.groups()
        if s_ == "":
            start = max(0, size - int(e_ or 0))
            end = size - 1
        else:
            start = int(s_)
            end = int(e_) if e_ else size - 1
        end = min(end, size - 1)
        if start > end or start >= size:
            return Response(status_code=416, headers={"Content-Range": f"bytes */{size}"})
        headers.update({"Content-Range": f"bytes {start}-{end}/{size}", "Content-Length": str(end - start + 1)})
        return StreamingResponse(_file_iter(path, start, end), status_code=206, media_type=ctype, headers=headers)
    headers["Content-Length"] = str(size)
    return StreamingResponse(_file_iter(path, 0, size - 1), media_type=ctype, headers=headers)


@router.get("/videos/{video_id}/frame", summary="One frame as JPEG (processed resolution)",
            responses={200: {"content": {"image/jpeg": {}}}})
def video_frame(video_id: str, t: float = Query(0.0, ge=0), original: bool = Query(
        False, description="return the frame at original resolution (used for calibration)")) -> Response:
    s, st = settings(), store()
    try:
        path = st.video_path(video_id)
    except FileNotFoundError as exc:
        raise not_found("video", video_id) from exc
    max_w = 100000 if original else s.video.max_width
    reader = VideoReader(path, s.video.fps_processed, max_w)
    img: np.ndarray | None = None
    for fr in reader.frames(t_start=t):
        img = fr.image
        break
    if img is None:
        raise ApiError(404, "no_frame", f"no frame at t={t}")
    if s.app.blur_heads_in_exports:
        img = _blur_from_runs(video_id, t, img, reader.scale)
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not ok:
        raise ApiError(500, "encode_failed", "could not encode frame")
    return Response(content=buf.tobytes(), media_type="image/jpeg")


def _blur_from_runs(video_id: str, t: float, img: np.ndarray, scale: float) -> np.ndarray:
    """Blur heads using detections from any run of this video (privacy setting)."""
    st = store()
    s = settings()
    for meta in st.list_runs():
        if meta.video.video_id != video_id or not st.exists(meta.run_id, "detections"):
            continue
        det = st.read_df(meta.run_id, "detections")
        if det.empty:
            continue
        near = det[(det["t"] - t).abs() <= 0.5 / s.video.fps_processed + 1e-6]
        from rewind.ingest.video_reader import processed_size

        _, _, run_scale = processed_size(meta.video.width, meta.video.height, s.video.max_width)
        boxes = near[["x1", "y1", "x2", "y2"]].to_numpy() / run_scale * scale
        return blur_heads(img, boxes)
    return img
