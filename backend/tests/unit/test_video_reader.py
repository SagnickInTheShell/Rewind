from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from rewind.ingest.video_reader import VideoOpenError, VideoReader, probe, processed_size


def _write_video(path: Path, fps: float = 25.0, seconds: float = 2.0, size: tuple[int, int] = (320, 240)) -> None:
    w, h = size
    vw = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    for i in range(int(fps * seconds)):
        img = np.full((h, w, 3), i % 255, np.uint8)
        vw.write(img)
    vw.release()


def test_probe_and_sampling(tmp_path: Path) -> None:
    p = tmp_path / "v.mp4"
    _write_video(p, fps=25, seconds=2)
    meta = probe(p, "vid", fps_processed=5.0)
    assert meta.frame_count == 50
    assert meta.duration_s == pytest.approx(2.0)
    reader = VideoReader(p, fps_processed=5.0, max_width=160)
    frames = list(reader.frames())
    assert len(frames) == 10
    ts = [f.t for f in frames]
    assert np.allclose(np.diff(ts), 0.2, atol=1e-6)
    assert frames[0].image.shape[1] == 160
    assert reader.scale == pytest.approx(0.5)
    assert np.allclose(reader.to_original_px(np.array([[80, 60]])), [[160, 120]])


def test_time_window(tmp_path: Path) -> None:
    p = tmp_path / "v.mp4"
    _write_video(p, fps=10, seconds=3)
    reader = VideoReader(p, fps_processed=2.0, max_width=640)
    frames = list(reader.frames(t_start=1.0, t_end=2.0))
    assert [round(f.t, 2) for f in frames] == [1.0, 1.5, 2.0]


def test_processed_size() -> None:
    assert processed_size(1920, 1080, 1280) == (1280, 720, pytest.approx(2 / 3))
    assert processed_size(640, 480, 1280) == (640, 480, 1.0)


def test_bad_file(tmp_path: Path) -> None:
    p = tmp_path / "x.mp4"
    p.write_bytes(b"not a video")
    with pytest.raises(VideoOpenError):
        probe(p, "x", 5.0)
