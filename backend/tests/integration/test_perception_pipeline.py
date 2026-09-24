from __future__ import annotations

from pathlib import Path

import httpx
import numpy as np
import pandas as pd
import pytest

from rewind.main import create_app
from rewind.pipeline.analyze import AnalysisPipeline, create_run
from rewind.settings import get_settings
from rewind.storage.run_store import RunStore
from tests.helpers import install_clip, render_clip


@pytest.fixture(scope="session")
def clip(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return render_clip(tmp_path_factory.mktemp("clips") / "clip.webm", duration=8.0)


async def test_perception_stages_produce_artefacts_and_overlay(clip: Path) -> None:
    s = get_settings()
    vid = install_clip(s, clip)
    store = RunStore(s)
    meta = create_run(store, s, vid, "demo_venue", run_id="run_perc")
    AnalysisPipeline(store, s, meta.run_id).run(until="features")
    for art in ("detections", "track_boxes", "tracks", "density_zone", "heat", "flow_zone", "flow_curl", "arrows"):
        assert store.exists("run_perc", art), art
    meta = store.load_meta("run_perc")
    assert meta.methods["density"] == "kde"  # no CSRNet weights → fallback
    assert meta.methods["detector"].startswith("blob")

    gt = pd.read_parquet(clip.with_suffix(".gt.parquet"))
    det = store.read_df("run_perc", "detections")
    t = 6.0
    n_gt = int((np.isclose(gt.t, t)).sum())
    n_det = int((np.isclose(det.t, t)).sum())
    assert n_gt > 10 and abs(n_det - n_gt) <= max(2, 0.1 * n_gt)

    tracks = store.read_df("run_perc", "tracks")
    assert tracks["vy"].median() > 0.5  # crowd walks south
    dz = store.read_df("run_perc", "density_zone")
    at = dz[np.isclose(dz.t, t)]
    assert at["count_map"].sum() == pytest.approx(n_det, abs=2.0)

    app = create_app()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/api/runs/run_perc/overlay", params={"t": t})
        assert r.status_code == 200
        body = r.json()
        assert body["tracks"] and body["zones"] and body["heatmap"]
        assert len(body["zones"]) == 9
        r404 = await c.get("/api/runs/nope/overlay", params={"t": 1})
        assert r404.status_code == 404

    # cached rerun is fast and changes nothing
    before = store.path("run_perc", "tracks").stat().st_mtime
    AnalysisPipeline(store, s, "run_perc").run(until="motion")
    assert store.path("run_perc", "tracks").stat().st_mtime == before




async def test_feature_stage_output(clip: Path) -> None:
    from rewind.schemas.features import ZoneFeatures

    s = get_settings()
    vid = install_clip(s, clip, "vid_feat")
    store = RunStore(s)
    create_run(store, s, vid, "demo_venue", run_id="run_feat")
    AnalysisPipeline(store, s, "run_feat").run(until="features")
    f = store.read_df("run_feat", "features")
    assert f["zone_id"].nunique() == 9
    assert len(f) == 9 * int(np.ceil(f["t"].max()))
    for r in f.to_dict("records")[:50]:
        ZoneFeatures.model_validate(r)
    a2 = f[f.zone_id == "A2"]
    assert a2["inflow_rate"].max() > 1.0  # people entering through Gate A
    assert a2["mean_speed"].max() > 0.8
    assert store.exists("run_feat", "features_meta")
