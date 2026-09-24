"""Upload → analyse (job + WebSocket progress) → query every run endpoint."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from rewind.main import create_app
from rewind.settings import get_settings
from rewind.venue.demo import build_demo_venue
from rewind.venue.graph import save_venue
from tests.helpers import render_clip


@pytest.fixture(scope="module")
def clip(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return render_clip(tmp_path_factory.mktemp("apiclip") / "clip.mp4", duration=10.0)


def test_full_analysis_via_api(clip: Path) -> None:
    s = get_settings()
    save_venue(build_demo_venue(), s.venues_dir / "demo_venue.json")
    client = TestClient(create_app())

    with open(clip, "rb") as fh:
        r = client.post("/api/videos", files={"file": ("clip.mp4", fh, "video/mp4")}, data={"synthetic": "true"})
    assert r.status_code == 200, r.text
    video = r.json()
    assert video["synthetic"] is True and video["duration_s"] > 9

    assert client.get("/api/videos").json()[0]["video_id"] == video["video_id"]
    rng = client.get(f"/api/videos/{video['video_id']}/stream", headers={"Range": "bytes=0-99"})
    assert rng.status_code == 206 and len(rng.content) == 100
    assert rng.headers["content-range"].startswith("bytes 0-99/")
    frame = client.get(f"/api/videos/{video['video_id']}/frame", params={"t": 1.0})
    assert frame.status_code == 200 and frame.headers["content-type"] == "image/jpeg"

    venues = client.get("/api/venues").json()
    assert venues[0]["venue_id"] == "demo_venue"

    r = client.post("/api/runs", json={"video_id": video["video_id"], "venue_id": "demo_venue"})
    assert r.status_code == 200, r.text
    run_id, job_id = r.json()["run_id"], r.json()["job_id"]

    stages = []
    with client.websocket_connect(f"/ws/jobs/{job_id}") as ws:
        while True:
            ev = ws.receive_json()
            if ev["stage"] != "heartbeat":
                stages.append(ev["stage"])
            assert ev.get("error") is None, ev
            if ev.get("done"):
                break
    assert "detect" in stages and "reconstruction" in stages
    assert client.get(f"/api/jobs/{job_id}").json()["state"] == "DONE"

    meta = client.get(f"/api/runs/{run_id}").json()
    assert meta["status"] == "DONE" and meta["methods"]["density"] == "kde"
    assert any("Synthetic" in n for n in meta["notes"])

    feats = client.get(f"/api/runs/{run_id}/features", params={"zone": "A2", "t_from": 2, "t_to": 6}).json()
    assert feats and all(f["zone_id"] == "A2" and 2 <= f["t"] <= 6 for f in feats)
    risk = client.get(f"/api/runs/{run_id}/risk").json()
    assert len(risk["global_risk"]) >= 9 and risk["methods"]["physics"]
    ex = client.get(f"/api/runs/{run_id}/explanations", params={"t": 5}).json()
    assert ex["method"] == "physics_weights" and ex["contributions"] and ex["narrative"]
    ex_zone = client.get(f"/api/runs/{run_id}/explanations", params={"t": 5, "zone": "A2"}).json()
    assert ex_zone["zone_id"] == "A2"
    tl = client.get(f"/api/runs/{run_id}/timeline").json()
    assert tl["run_id"] == run_id and "summary" in tl
    ov = client.get(f"/api/runs/{run_id}/overlay", params={"t": 5}).json()
    assert ov["zones"][0]["state"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
    shap = client.get(f"/api/runs/{run_id}/explanations", params={"t": 5, "method": "shap"})
    assert shap.status_code in (200, 409)


def test_api_errors() -> None:
    client = TestClient(create_app())
    assert client.get("/api/runs/nope").json()["error"]["code"] == "not_found"
    r = client.post("/api/runs", json={"video_id": "x", "venue_id": "y"})
    assert r.status_code == 404
    r = client.post("/api/videos", files={"file": ("a.txt", b"hello", "text/plain")})
    assert r.status_code == 415
    r = client.post("/api/videos", files={"file": ("a.mp4", b"not a video", "video/mp4")})
    assert r.status_code == 422
    assert client.post("/api/demo/load").status_code == 404


def test_venue_put_validation() -> None:
    s = get_settings()
    save_venue(build_demo_venue(), s.venues_dir / "demo_venue.json")
    client = TestClient(create_app())
    v = client.get("/api/venues/demo_venue").json()
    v["sources"] = ["NOPE"]
    r = client.put("/api/venues/demo_venue", json=v)
    assert r.status_code == 422 and "source 'NOPE' is not a zone" in r.json()["error"]["detail"]
    v["sources"] = ["A2"]
    v["calibration"]["image_points"] = v["calibration"]["image_points"][:3]
    v["calibration"]["world_points"] = v["calibration"]["world_points"][:3]
    assert client.put("/api/venues/demo_venue", json=v).status_code == 422
    good = build_demo_venue().model_dump()
    assert client.put("/api/venues/demo_venue", json=good).status_code == 200
